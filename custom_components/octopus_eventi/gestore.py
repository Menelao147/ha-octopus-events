"""Gestione degli eventi: archivio, consumo abituale, consumo durante l'evento, esito."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.recorder import get_instance, history
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import calcolo
from .const import (
    CONF_ESCLUDI_GIORNI_EVENTI,
    CONF_FESTIVI_EXTRA,
    CONF_SENSORE,
    DOMAIN,
    PREDEFINITO_ESCLUDI_GIORNI_EVENTI,
    SEGNALE_AGGIORNAMENTO,
    STATO_CONCLUSO,
    STATO_IN_CORSO,
    STATO_NESSUNO,
    STATO_PROGRAMMATO,
    STORE_CHIAVE,
    STORE_VERSIONE,
    STORICO_MAX,
)

_LOGGER = logging.getLogger(__name__)

# Le statistiche orarie di un'ora sono pronte pochi minuti dopo la sua fine.
ATTESA_STATISTICHE = timedelta(minutes=15)
# Oltre questo tempo dalla fine, se mancano ancora statistiche, resta il valore misurato dal vivo.
LIMITE_STATISTICHE = timedelta(hours=6)


def _ts(valore: str | None) -> datetime | None:
    return dt_util.parse_datetime(valore) if valore else None


class Gestore:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.sensore: str = entry.data[CONF_SENSORE]
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSIONE, f"{STORE_CHIAVE}.{entry.entry_id}")
        self.eventi: list[dict[str, Any]] = []
        self._annulla: list = []
        self._in_lavorazione: set[str] = set()

    # ---------- opzioni ----------

    @property
    def escludi_giorni_eventi(self) -> bool:
        return self.entry.options.get(CONF_ESCLUDI_GIORNI_EVENTI, PREDEFINITO_ESCLUDI_GIORNI_EVENTI)

    @property
    def festivi_extra(self) -> set[date]:
        """Giorni festivi in più (per esempio il patrono), scritti come MM-GG, per ogni anno."""
        giorni: set[date] = set()
        oggi = dt_util.now().date()
        for voce in self.entry.options.get(CONF_FESTIVI_EXTRA, []):
            try:
                mese, giorno = (int(x) for x in voce.split("-"))
                for anno in (oggi.year - 1, oggi.year, oggi.year + 1):
                    giorni.add(date(anno, mese, giorno))
            except ValueError:
                _LOGGER.warning("Festivo non valido nelle opzioni: %s (formato MM-GG)", voce)
        return giorni

    # ---------- avvio e arresto ----------

    async def async_avvia(self) -> None:
        dati = await self._store.async_load() or {}
        self.eventi = sorted(dati.get("eventi", []), key=lambda e: e["inizio"])
        self._annulla.append(async_track_time_interval(self.hass, self._async_giro, timedelta(minutes=1)))
        self._annulla.append(async_track_state_change_event(self.hass, [self.sensore], self._sensore_cambiato))
        self.hass.async_create_task(self._async_giro(dt_util.utcnow()))

    async def async_ferma(self) -> None:
        for annulla in self._annulla:
            annulla()
        self._annulla.clear()
        await self._store.async_save(self._dati())

    def _dati(self) -> dict[str, Any]:
        return {"eventi": self.eventi}

    def _salva(self) -> None:
        self._store.async_delay_save(self._dati, 2)
        async_dispatcher_send(self.hass, f"{SEGNALE_AGGIORNAMENTO}_{self.entry.entry_id}")

    # ---------- eventi ----------

    def evento(self, id_evento: str) -> dict[str, Any]:
        for e in self.eventi:
            if e["id"] == id_evento:
                return e
        raise ServiceValidationError(f"Evento {id_evento} non trovato")

    def attuale(self, ora: datetime | None = None) -> dict[str, Any] | None:
        """Evento in corso, altrimenti il prossimo, altrimenti l'ultimo concluso."""
        ora = ora or dt_util.now()
        for e in self.eventi:
            if _ts(e["inizio"]) <= ora < _ts(e["fine"]):
                return e
        futuri = [e for e in self.eventi if _ts(e["inizio"]) > ora]
        if futuri:
            return futuri[0]
        return self.eventi[-1] if self.eventi else None

    def stato(self, evento: dict[str, Any] | None, ora: datetime | None = None) -> str:
        if evento is None:
            return STATO_NESSUNO
        ora = ora or dt_util.now()
        if ora < _ts(evento["inizio"]):
            return STATO_PROGRAMMATO
        if ora < _ts(evento["fine"]):
            return STATO_IN_CORSO
        return STATO_CONCLUSO

    def storico(self) -> list[dict[str, Any]]:
        ora = dt_util.now()
        conclusi = [e for e in self.eventi if _ts(e["fine"]) <= ora]
        return [self.riepilogo(e) for e in reversed(conclusi[-STORICO_MAX:])]

    def riepilogo(self, e: dict[str, Any]) -> dict[str, Any]:
        abituale = (e.get("abituale") or {}).get("valore")
        risultato = calcolo.esito(e["tipo"], abituale, e.get("consumo"), self.soglie(e))
        return {
            "id": e["id"],
            "tipo": e["tipo"],
            "inizio": e["inizio"],
            "fine": e["fine"],
            "consumo_abituale": _arrotonda(abituale),
            "consumo": _arrotonda(e.get("consumo")),
            "consumo_definitivo": e.get("consumo_definitivo", False),
            "variazione": _arrotonda(risultato.variazione, 1),
            "premio": _arrotonda(risultato.premio, 3 if e["tipo"] == calcolo.POWER_UP else 2),
            "esito_octopus": e.get("esito_octopus"),
        }

    @staticmethod
    def soglie(e: dict[str, Any]) -> list[calcolo.Soglia]:
        return [calcolo.Soglia(s["percentuale"], s["euro"]) for s in e.get("soglie", [])]

    async def async_aggiungi(
        self,
        tipo: str,
        inizio: datetime,
        fine: datetime,
        soglie: list[dict[str, float]],
        adesione_entro: datetime | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        inizio, fine = dt_util.as_local(inizio), dt_util.as_local(fine)
        if fine <= inizio:
            raise ServiceValidationError("La fine deve essere dopo l'inizio")
        if inizio.minute or inizio.second or fine.minute or fine.second:
            raise ServiceValidationError("Octopus usa i consumi orari: inizio e fine devono essere ore intere")
        doppio = next(
            (e for e in self.eventi if _ts(e["inizio"]) < fine and inizio < _ts(e["fine"])),
            None,
        )
        if doppio:
            # Lo stesso evento può arrivare due volte (annuncio e promemoria): si aggiornano i dati.
            evento = doppio
        else:
            evento = {"id": uuid.uuid4().hex[:8]}
            self.eventi.append(evento)
        evento.update(
            tipo=tipo,
            inizio=inizio.isoformat(),
            fine=fine.isoformat(),
            soglie=sorted(soglie, key=lambda s: s["percentuale"]),
            adesione_entro=adesione_entro.isoformat() if adesione_entro else evento.get("adesione_entro"),
            note=note if note is not None else evento.get("note"),
        )
        if fine <= dt_util.now():
            # Evento passato inserito a posteriori: nessuna notifica di inizio o fine.
            evento["stato_notificato"] = STATO_CONCLUSO
        self.eventi.sort(key=lambda e: e["inizio"])
        await self._async_calcola_abituale(evento)
        if self.escludi_giorni_eventi:
            # Un evento nuovo cambia i giorni esclusi degli eventi successivi.
            for altro in self.eventi:
                if altro is not evento and _ts(altro["inizio"]) > inizio and not _ts(altro["fine"]) <= dt_util.now():
                    await self._async_calcola_abituale(altro)
        self._salva()
        return evento

    async def async_rimuovi(self, id_evento: str) -> None:
        self.eventi.remove(self.evento(id_evento))
        self._salva()

    async def async_registra_esito_octopus(self, id_evento: str, variazione: float | None, premio: float | None, note: str | None) -> None:
        self.evento(id_evento)["esito_octopus"] = {"variazione": variazione, "premio": premio, "note": note}
        self._salva()

    async def async_ricalcola(self, id_evento: str | None = None) -> None:
        for e in [self.evento(id_evento)] if id_evento else self.eventi:
            await self._async_calcola_abituale(e)
            if _ts(e["fine"]) <= dt_util.now():
                await self._async_consumo_finale(e, forza=True)
        self._salva()

    # ---------- calcoli ----------

    async def _async_consumi_orari(self, inizio: datetime, fine: datetime) -> dict[float, float]:
        def leggi() -> dict[float, float]:
            righe = statistics_during_period(
                self.hass, dt_util.as_utc(inizio), dt_util.as_utc(fine), {self.sensore}, "hour", None, {"change"}
            )
            return {
                (r["start"] if isinstance(r["start"], float) else r["start"].timestamp()): r["change"]
                for r in righe.get(self.sensore, [])
                if r.get("change") is not None
            }

        return await get_instance(self.hass).async_add_executor_job(leggi)

    async def _async_calcola_abituale(self, e: dict[str, Any]) -> None:
        inizio, fine = _ts(e["inizio"]), _ts(e["fine"])
        oggi = dt_util.now().date()
        giorno = dt_util.as_local(inizio).date()
        da = dt_util.start_of_local_day(giorno - timedelta(days=calcolo.GIORNI_RICERCA + 1))
        consumi = await self._async_consumi_orari(da, dt_util.start_of_local_day(giorno))
        esclusi = (
            {dt_util.as_local(_ts(a["inizio"])).date() for a in self.eventi if _ts(a["inizio"]) < inizio}
            if self.escludi_giorni_eventi
            else set()
        )
        r = calcolo.consumo_abituale(dt_util.as_local(inizio), dt_util.as_local(fine), consumi, esclusi, self.festivi_extra)
        e["abituale"] = {
            "valore": r.valore,
            "giorni": [[g.isoformat(), round(v, 3)] for g, v in r.giorni],
            "scartati": [g.isoformat() for g in r.scartati if g < oggi],
            "calcolato": oggi.isoformat(),
            # Prima del giorno dell'evento mancano ancora i giorni più recenti.
            "provvisorio": oggi < giorno,
        }

    async def _async_riferimento(self, e: dict[str, Any]) -> float | None:
        """Lettura del contatore all'inizio dell'evento, dallo storico (vale anche dopo un riavvio)."""
        inizio = _ts(e["inizio"])

        def leggi() -> float | None:
            stati = history.get_significant_states(
                self.hass,
                dt_util.as_utc(inizio),
                dt_util.as_utc(inizio) + timedelta(seconds=1),
                [self.sensore],
                include_start_time_state=True,
                significant_changes_only=False,
                no_attributes=True,
            ).get(self.sensore, [])
            for s in stati:
                try:
                    return float(s.state)
                except (ValueError, AttributeError):
                    continue
            return None

        return await get_instance(self.hass).async_add_executor_job(leggi)

    async def _async_consumo_dal_vivo(self, e: dict[str, Any]) -> None:
        if e.get("riferimento") is None:
            e["riferimento"] = await self._async_riferimento(e)
        stato = self.hass.states.get(self.sensore)
        try:
            attuale = float(stato.state)
        except (AttributeError, ValueError):
            return
        if e["riferimento"] is not None:
            e["consumo"] = max(attuale - e["riferimento"], 0.0)

    async def _async_consumo_finale(self, e: dict[str, Any], forza: bool = False) -> None:
        inizio, fine = _ts(e["inizio"]), _ts(e["fine"])
        ore = calcolo.ore_finestra(dt_util.as_local(inizio), dt_util.as_local(fine), dt_util.as_local(inizio).date())
        consumi = await self._async_consumi_orari(inizio, fine)
        valori = [consumi.get(o.timestamp()) for o in ore]
        if None not in valori:
            e["consumo"] = sum(valori)
            e["consumo_definitivo"] = True
        elif forza or dt_util.now() - fine > LIMITE_STATISTICHE:
            # Statistiche incomplete (HA spento durante l'evento?): resta la misura dal vivo, se c'è.
            e["consumo_definitivo"] = True
            _LOGGER.warning("Statistiche orarie incomplete per l'evento %s: uso il consumo misurato dal vivo", e["id"])

    # ---------- giro periodico ----------

    async def _async_giro(self, _ora: datetime) -> None:
        ora = dt_util.now()
        cambiato = False
        for e in list(self.eventi):
            if e["id"] in self._in_lavorazione:
                continue
            self._in_lavorazione.add(e["id"])
            try:
                cambiato |= await self._async_aggiorna_evento(e, ora)
            except Exception:  # un evento con problemi non deve fermare gli altri
                _LOGGER.exception("Errore nell'aggiornare l'evento %s", e.get("id"))
            finally:
                self._in_lavorazione.discard(e["id"])
        if cambiato:
            self._salva()
        else:
            # Gli stati dipendono dall'ora anche senza dati nuovi.
            async_dispatcher_send(self.hass, f"{SEGNALE_AGGIORNAMENTO}_{self.entry.entry_id}")

    async def _async_aggiorna_evento(self, e: dict[str, Any], ora: datetime) -> bool:
        inizio, fine = _ts(e["inizio"]), _ts(e["fine"])
        oggi = ora.date()
        cambiato = False
        abituale = e.get("abituale") or {}
        if fine > ora and (not abituale or (abituale.get("provvisorio") and abituale.get("calcolato") != oggi.isoformat())):
            await self._async_calcola_abituale(e)
            cambiato = True
        if inizio <= ora < fine:
            if e.get("stato_notificato") != STATO_IN_CORSO:
                e["stato_notificato"] = STATO_IN_CORSO
                self.hass.bus.async_fire(f"{DOMAIN}_inizio", self.riepilogo(e))
            await self._async_consumo_dal_vivo(e)
            cambiato = True
        elif ora >= fine and not e.get("consumo_definitivo"):
            # Anche un evento passato senza misura dal vivo (HA spento, evento inserito dopo) si chiude con le statistiche.
            if ora - fine >= ATTESA_STATISTICHE:
                await self._async_consumo_finale(e)
                cambiato = True
            if e.get("consumo_definitivo") and e.get("stato_notificato") != STATO_CONCLUSO:
                e["stato_notificato"] = STATO_CONCLUSO
                self.hass.bus.async_fire(f"{DOMAIN}_fine", self.riepilogo(e))
        return cambiato

    @callback
    def _sensore_cambiato(self, event: Event[EventStateChangedData]) -> None:
        e = self.attuale()
        if e and self.stato(e) == STATO_IN_CORSO and e.get("riferimento") is not None:
            try:
                e["consumo"] = max(float(event.data["new_state"].state) - e["riferimento"], 0.0)
            except (AttributeError, TypeError, ValueError):
                return
            async_dispatcher_send(self.hass, f"{SEGNALE_AGGIORNAMENTO}_{self.entry.entry_id}")


def _arrotonda(valore: float | None, cifre: int = 3) -> float | None:
    return None if valore is None else round(valore, cifre)
