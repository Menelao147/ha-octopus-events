"""Octopus eventi: Energy Break e Power Up di Octopus Energy Italia."""

from __future__ import annotations

import re

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from . import calcolo
from .const import DOMAIN
from .gestore import Gestore

PIATTAFORME = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DATETIME,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.TEXT,
]

type OctopusEventiConfigEntry = ConfigEntry[Gestore]


def soglie_da_testo(valore: str | list) -> list[dict[str, float]]:
    """Soglie come "50:2" o "20:1, 50:3" (riduzione in % : euro), oppure lista di {percentuale, euro}."""
    if isinstance(valore, list):
        return [{"percentuale": float(s["percentuale"]), "euro": float(s["euro"])} for s in valore]
    soglie = []
    for parte in filter(None, (p.strip() for p in str(valore).split(","))):
        trovato = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*%?\s*[:=]\s*(\d+(?:[.,]\d+)?)\s*€?", parte)
        if not trovato:
            raise vol.Invalid(f"Soglia non valida: {parte!r} (esempio: 50:2)")
        soglie.append({"percentuale": float(trovato[1].replace(",", ".")), "euro": float(trovato[2].replace(",", "."))})
    return soglie


SCHEMA_AGGIUNGI = vol.Schema(
    {
        vol.Required("tipo"): vol.In(calcolo.TIPI),
        vol.Required("inizio"): cv.datetime,
        vol.Required("fine"): cv.datetime,
        vol.Optional("soglie", default=""): vol.Any(cv.string, list),
        vol.Optional("adesione_entro"): cv.datetime,
        vol.Optional("note"): cv.string,
    }
)
SCHEMA_ID = vol.Schema({vol.Required("id"): cv.string})
SCHEMA_RICALCOLA = vol.Schema({vol.Optional("id"): cv.string})
SCHEMA_ESITO = vol.Schema(
    {
        vol.Required("id"): cv.string,
        vol.Optional("variazione"): vol.Coerce(float),
        vol.Optional("premio"): vol.Coerce(float),
        vol.Optional("note"): cv.string,
    }
)


def _gestore(hass: HomeAssistant) -> Gestore:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        return entry.runtime_data
    raise ServiceValidationError("Octopus eventi non è configurata")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def aggiungi(call: ServiceCall) -> ServiceResponse:
        try:
            soglie = soglie_da_testo(call.data["soglie"])
        except (vol.Invalid, KeyError, TypeError, ValueError) as err:
            raise ServiceValidationError(str(err)) from err
        evento = await _gestore(hass).async_aggiungi(
            call.data["tipo"],
            call.data["inizio"],
            call.data["fine"],
            soglie,
            call.data.get("adesione_entro"),
            call.data.get("note"),
        )
        return _gestore(hass).riepilogo(evento)

    async def rimuovi(call: ServiceCall) -> None:
        await _gestore(hass).async_rimuovi(call.data["id"])

    async def ricalcola(call: ServiceCall) -> None:
        await _gestore(hass).async_ricalcola(call.data.get("id"))

    async def esito(call: ServiceCall) -> None:
        await _gestore(hass).async_registra_esito_octopus(
            call.data["id"], call.data.get("variazione"), call.data.get("premio"), call.data.get("note")
        )

    async def elenco(call: ServiceCall) -> ServiceResponse:
        g = _gestore(hass)
        return {"eventi": [g.riepilogo(e) | {"abituale": e.get("abituale")} for e in g.eventi]}

    hass.services.async_register(DOMAIN, "aggiungi_evento", aggiungi, SCHEMA_AGGIUNGI, SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "rimuovi_evento", rimuovi, SCHEMA_ID)
    hass.services.async_register(DOMAIN, "ricalcola", ricalcola, SCHEMA_RICALCOLA)
    hass.services.async_register(DOMAIN, "registra_esito_octopus", esito, SCHEMA_ESITO)
    hass.services.async_register(DOMAIN, "elenco_eventi", elenco, vol.Schema({}), SupportsResponse.ONLY)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OctopusEventiConfigEntry) -> bool:
    gestore = Gestore(hass, entry)
    await gestore.async_avvia()
    entry.runtime_data = gestore
    await hass.config_entries.async_forward_entry_setups(entry, PIATTAFORME)
    entry.async_on_unload(entry.add_update_listener(_opzioni_cambiate))
    return True


async def _opzioni_cambiate(hass: HomeAssistant, entry: OctopusEventiConfigEntry) -> None:
    await entry.runtime_data.async_ricalcola()


async def async_unload_entry(hass: HomeAssistant, entry: OctopusEventiConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PIATTAFORME)
    if ok:
        await entry.runtime_data.async_ferma()
    return ok
