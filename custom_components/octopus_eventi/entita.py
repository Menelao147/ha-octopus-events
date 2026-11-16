"""Base comune delle entità."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NOME, SEGNALE_AGGIORNAMENTO
from .gestore import Gestore


class EntitaOctopusEventi(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, gestore: Gestore, chiave: str, dominio: str) -> None:
        self.gestore = gestore
        self._attr_translation_key = chiave
        self._attr_unique_id = f"{gestore.entry.entry_id}_{chiave}"
        # Nomi delle entità fissi e in italiano, qualunque sia la lingua di HA.
        self.entity_id = f"{dominio}.octopus_eventi_{chiave}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gestore.entry.entry_id)},
            name=NOME,
            manufacturer="Octopus Energy Italia",
            model="Energy Break e Power Up",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SEGNALE_AGGIORNAMENTO}_{self.gestore.entry.entry_id}", self.async_write_ha_state
            )
        )
