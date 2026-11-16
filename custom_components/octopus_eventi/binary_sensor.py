"""Sensore binario: evento in corso."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OctopusEventiConfigEntry
from .const import STATO_IN_CORSO
from .entita import EntitaOctopusEventi


async def async_setup_entry(
    hass: HomeAssistant, entry: OctopusEventiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([InCorso(entry.runtime_data, "in_corso", "binary_sensor")])


class InCorso(EntitaOctopusEventi, BinarySensorEntity):
    _attr_icon = "mdi:timer-sand"

    @property
    def is_on(self) -> bool:
        return self.gestore.stato(self.gestore.attuale()) == STATO_IN_CORSO

    @property
    def extra_state_attributes(self) -> dict | None:
        e = self.gestore.attuale()
        return {"tipo": e["tipo"]} if e else None
