"""Sensori di Octopus eventi: tutti riferiti all'evento in corso, al prossimo o all'ultimo concluso."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OctopusEventiConfigEntry, calcolo
from .const import STATI
from .entita import EntitaOctopusEventi
from .gestore import Gestore


@dataclass(frozen=True)
class Descrizione:
    chiave: str
    valore: Callable[[Gestore, dict[str, Any] | None], Any]
    device_class: SensorDeviceClass | None = None
    unita: str | None = None
    cifre: int | None = None
    icona: str | None = None
    opzioni: list[str] | None = None


def _abituale(e: dict[str, Any] | None) -> float | None:
    return ((e or {}).get("abituale") or {}).get("valore")


def _esito(g: Gestore, e: dict[str, Any] | None) -> calcolo.Esito:
    return calcolo.esito(e["tipo"], _abituale(e), e.get("consumo"), g.soglie(e)) if e else calcolo.Esito(None, None)


def _variazione(e: dict[str, Any] | None) -> float | None:
    """Consumo rispetto alla media, in %: negativo se ridotto (Energy Break), positivo se aumentato (Power Up)."""
    abituale, consumo = _abituale(e), (e or {}).get("consumo")
    if not abituale or consumo is None:
        return None
    return (consumo - abituale) / abituale * 100


def _rispetto_media(e: dict[str, Any] | None) -> float | None:
    v = _variazione(e)
    return None if v is None else 100 + v


def _data(e: dict[str, Any] | None, campo: str):
    return dt_util.parse_datetime(e[campo]) if e and e.get(campo) else None


DESCRIZIONI = [
    Descrizione("stato", lambda g, e: g.stato(e), SensorDeviceClass.ENUM, icona="mdi:octopus", opzioni=STATI),
    Descrizione("inizio", lambda g, e: _data(e, "inizio"), SensorDeviceClass.TIMESTAMP),
    Descrizione("fine", lambda g, e: _data(e, "fine"), SensorDeviceClass.TIMESTAMP),
    Descrizione(
        "consumo_abituale", lambda g, e: _abituale(e), SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, 3, "mdi:chart-bell-curve"
    ),
    Descrizione(
        "consumo", lambda g, e: (e or {}).get("consumo"), SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, 3, "mdi:lightning-bolt"
    ),
    Descrizione("variazione", lambda g, e: _variazione(e), unita=PERCENTAGE, cifre=0, icona="mdi:percent"),
    # Consumo come percentuale della media (100 = uguale): comodo per le barre delle dashboard.
    Descrizione("rispetto_media", lambda g, e: _rispetto_media(e), unita=PERCENTAGE, cifre=0, icona="mdi:gauge"),
    Descrizione("tipo", lambda g, e: e["tipo"] if e else "nessuno", SensorDeviceClass.ENUM, icona="mdi:flash",
                opzioni=["energy_break", "power_up", "nessuno"]),
    Descrizione(
        "sconto_stimato",
        lambda g, e: _esito(g, e).premio if e and e["tipo"] == calcolo.ENERGY_BREAK else None,
        SensorDeviceClass.MONETARY, "EUR", 2, "mdi:piggy-bank",
    ),
    Descrizione(
        "energia_gratuita",
        lambda g, e: _esito(g, e).premio if e and e["tipo"] == calcolo.POWER_UP else None,
        SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, 3, "mdi:gift",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: OctopusEventiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(SensoreOctopusEventi(entry.runtime_data, d) for d in DESCRIZIONI)


class SensoreOctopusEventi(EntitaOctopusEventi, SensorEntity):
    def __init__(self, gestore: Gestore, descrizione: Descrizione) -> None:
        super().__init__(gestore, descrizione.chiave, "sensor")
        self.descrizione = descrizione
        self._attr_device_class = descrizione.device_class
        self._attr_native_unit_of_measurement = descrizione.unita
        self._attr_suggested_display_precision = descrizione.cifre
        self._attr_icon = descrizione.icona
        self._attr_options = descrizione.opzioni

    @property
    def native_value(self) -> Any:
        return self.descrizione.valore(self.gestore, self.gestore.attuale())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        e = self.gestore.attuale()
        chiave = self.descrizione.chiave
        if chiave == "stato":
            if e is None:
                return {"storico": self.gestore.storico()}
            return {
                "id": e["id"],
                "tipo": e["tipo"],
                "inizio": e["inizio"],
                "fine": e["fine"],
                "soglie": e.get("soglie", []),
                "adesione_entro": e.get("adesione_entro"),
                "note": e.get("note"),
                "storico": self.gestore.storico(),
            }
        if chiave == "consumo_abituale" and e:
            abituale = e.get("abituale") or {}
            return {
                "giorni": abituale.get("giorni", []),
                "scartati": abituale.get("scartati", []),
                "provvisorio": abituale.get("provvisorio"),
                "obiettivi": [
                    {"riduzione": s.percentuale, "euro": s.euro, "consumo_massimo": round(kwh, 3)}
                    for s, kwh in calcolo.obiettivi(abituale.get("valore"), self.gestore.soglie(e))
                ]
                if e["tipo"] == calcolo.ENERGY_BREAK
                else [],
            }
        if chiave == "consumo" and e:
            return {"definitivo": e.get("consumo_definitivo", False)}
        return None
