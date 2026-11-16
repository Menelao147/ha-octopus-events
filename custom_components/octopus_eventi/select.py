"""Scelte del nuovo evento: tipo e durata."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OctopusEventiConfigEntry, calcolo
from .entita import EntitaOctopusEventi

DURATE = ["1", "2", "3", "4"]


async def async_setup_entry(
    hass: HomeAssistant, entry: OctopusEventiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    g = entry.runtime_data
    async_add_entities([Tipo(g, "nuovo_tipo", "select"), Durata(g, "nuova_durata", "select"), Mostrato(g, "evento_mostrato", "select")])


class Tipo(EntitaOctopusEventi, SelectEntity):
    _attr_icon = "mdi:flash"
    _attr_options = list(calcolo.TIPI)

    @property
    def current_option(self) -> str:
        return self.gestore.bozza["tipo"]

    async def async_select_option(self, option: str) -> None:
        self.gestore.imposta_bozza("tipo", option)


class Durata(EntitaOctopusEventi, SelectEntity):
    _attr_icon = "mdi:timer-outline"
    _attr_options = DURATE

    @property
    def current_option(self) -> str:
        return str(self.gestore.bozza["durata"])

    async def async_select_option(self, option: str) -> None:
        self.gestore.imposta_bozza("durata", int(option))


GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
NOMI = {calcolo.ENERGY_BREAK: "Energy Break", calcolo.POWER_UP: "Power Up"}
NESSUNO = "Nessun evento concluso"


def etichetta(e: dict) -> str:
    inizio = dt_util.as_local(dt_util.parse_datetime(e["inizio"]))
    return f"{GIORNI[inizio.weekday()]} {inizio.day}/{inizio.month}/{inizio:%y} {inizio:%H}:00 · {NOMI[e['tipo']]}"


class Mostrato(EntitaOctopusEventi, SelectEntity):
    """Evento concluso da mostrare nei grafici dello storico; negli attributi i suoi dati."""

    _attr_icon = "mdi:history"

    @property
    def options(self) -> list[str]:
        return [etichetta(e) for e in self.gestore.conclusi()] or [NESSUNO]

    @property
    def current_option(self) -> str:
        e = self.gestore.evento_mostrato()
        return etichetta(e) if e else NESSUNO

    async def async_select_option(self, option: str) -> None:
        for e in self.gestore.conclusi():
            if etichetta(e) == option:
                self.gestore.scegli_mostrato(e["id"])
                return

    @property
    def extra_state_attributes(self) -> dict | None:
        e = self.gestore.evento_mostrato()
        if e is None:
            return None
        abituale = (e.get("abituale") or {}).get("valore")
        return self.gestore.riepilogo(e) | {
            "obiettivi": [
                {"riduzione": s.percentuale, "euro": s.euro, "consumo_massimo": round(kwh, 3)}
                for s, kwh in calcolo.obiettivi(abituale, self.gestore.soglie(e))
            ]
            if e["tipo"] == calcolo.ENERGY_BREAK
            else [],
        }
