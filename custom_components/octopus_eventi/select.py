"""Scelte del nuovo evento: tipo e durata."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OctopusEventiConfigEntry, calcolo
from .entita import EntitaOctopusEventi

DURATE = ["1", "2", "3", "4"]


async def async_setup_entry(
    hass: HomeAssistant, entry: OctopusEventiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    g = entry.runtime_data
    async_add_entities([Tipo(g, "nuovo_tipo", "select"), Durata(g, "nuova_durata", "select")])


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
