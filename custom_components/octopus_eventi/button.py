"""Pulsanti: aggiungere l'evento preparato, annullare il prossimo evento."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OctopusEventiConfigEntry
from .entita import EntitaOctopusEventi


async def async_setup_entry(
    hass: HomeAssistant, entry: OctopusEventiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    g = entry.runtime_data
    async_add_entities([Aggiungi(g, "aggiungi", "button"), Annulla(g, "annulla_prossimo", "button")])


class Aggiungi(EntitaOctopusEventi, ButtonEntity):
    _attr_icon = "mdi:calendar-plus"

    async def async_press(self) -> None:
        await self.gestore.async_aggiungi_bozza()


class Annulla(EntitaOctopusEventi, ButtonEntity):
    _attr_icon = "mdi:calendar-remove"

    async def async_press(self) -> None:
        await self.gestore.async_annulla_prossimo()
