"""Date e ore del nuovo evento: inizio (ora intera) e termine per confermare la partecipazione."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OctopusEventiConfigEntry
from .entita import EntitaOctopusEventi


async def async_setup_entry(
    hass: HomeAssistant, entry: OctopusEventiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    g = entry.runtime_data
    async_add_entities([Data(g, "nuovo_inizio", "datetime", "inizio"), Data(g, "nuova_adesione", "datetime", "adesione")])


class Data(EntitaOctopusEventi, DateTimeEntity):
    def __init__(self, gestore, chiave: str, dominio: str, campo: str) -> None:
        super().__init__(gestore, chiave, dominio)
        self.campo = campo
        self._attr_icon = "mdi:calendar-clock" if campo == "inizio" else "mdi:email-check-outline"

    @property
    def native_value(self) -> datetime | None:
        valore = self.gestore.bozza.get(self.campo)
        return dt_util.parse_datetime(valore) if valore else None

    async def async_set_value(self, value: datetime) -> None:
        self.gestore.imposta_bozza(self.campo, value)
