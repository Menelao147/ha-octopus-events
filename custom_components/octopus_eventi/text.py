"""Soglie del nuovo Energy Break, per esempio "50:2" oppure "20:1, 50:3" (riduzione in % : euro)."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OctopusEventiConfigEntry, soglie_da_testo
from .entita import EntitaOctopusEventi


async def async_setup_entry(
    hass: HomeAssistant, entry: OctopusEventiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([Soglie(entry.runtime_data, "nuove_soglie", "text")])


class Soglie(EntitaOctopusEventi, TextEntity):
    _attr_icon = "mdi:target"
    _attr_native_max = 60

    @property
    def native_value(self) -> str:
        return self.gestore.bozza["soglie"]

    async def async_set_value(self, value: str) -> None:
        try:
            soglie_da_testo(value)
        except vol.Invalid as err:
            raise ServiceValidationError(str(err)) from err
        self.gestore.imposta_bozza("soglie", value.strip())
