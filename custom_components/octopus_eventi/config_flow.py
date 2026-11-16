"""Configurazione di Octopus eventi dall'interfaccia."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ESCLUDI_GIORNI_EVENTI,
    CONF_FESTIVI_EXTRA,
    CONF_SENSORE,
    DOMAIN,
    NOME,
    PREDEFINITO_ESCLUDI_GIORNI_EVENTI,
)

SELETTORE_SENSORE = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.ENERGY)
)


class OctopusEventiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=NOME, data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_SENSORE): SELETTORE_SENSORE}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return OctopusEventiOptionsFlow()


class OctopusEventiOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errori: dict[str, str] = {}
        if user_input is not None:
            festivi = [v.strip() for v in re.split(r"[,\s]+", user_input.get(CONF_FESTIVI_EXTRA, "")) if v.strip()]
            if all(re.fullmatch(r"(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])", v) for v in festivi):
                return self.async_create_entry(
                    data={
                        CONF_ESCLUDI_GIORNI_EVENTI: user_input[CONF_ESCLUDI_GIORNI_EVENTI],
                        CONF_FESTIVI_EXTRA: festivi,
                    }
                )
            errori[CONF_FESTIVI_EXTRA] = "festivi_non_validi"
        opzioni = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            errors=errori,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ESCLUDI_GIORNI_EVENTI,
                        default=opzioni.get(CONF_ESCLUDI_GIORNI_EVENTI, PREDEFINITO_ESCLUDI_GIORNI_EVENTI),
                    ): bool,
                    vol.Optional(
                        CONF_FESTIVI_EXTRA, default=", ".join(opzioni.get(CONF_FESTIVI_EXTRA, []))
                    ): str,
                }
            ),
        )
