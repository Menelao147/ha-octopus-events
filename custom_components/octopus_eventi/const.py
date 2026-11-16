"""Costanti di Octopus Eventi."""

DOMAIN = "octopus_eventi"
NOME = "Octopus eventi"

CONF_SENSORE = "sensore_energia"
CONF_ESCLUDI_GIORNI_EVENTI = "escludi_giorni_eventi"
CONF_FESTIVI_EXTRA = "festivi_extra"

# Nei Power Up di maggio 2026 i risultati di Octopus tornano solo senza escludere i giorni con eventi
# precedenti, anche se il regolamento prevede l'esclusione.
PREDEFINITO_ESCLUDI_GIORNI_EVENTI = False

STORE_VERSIONE = 1
STORE_CHIAVE = f"{DOMAIN}.eventi"

SEGNALE_AGGIORNAMENTO = f"{DOMAIN}_aggiornato"

STATO_NESSUNO = "nessuno"
STATO_PROGRAMMATO = "programmato"
STATO_IN_CORSO = "in_corso"
STATO_CONCLUSO = "concluso"
STATI = [STATO_NESSUNO, STATO_PROGRAMMATO, STATO_IN_CORSO, STATO_CONCLUSO]

STORICO_MAX = 20
