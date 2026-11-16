# Octopus eventi

Integrazione per Home Assistant che segue gli eventi di **Octopus Energy Italia**:

- **Energy Break**: consumare meno della propria media in una fascia oraria, per uno sconto in bolletta;
- **Power Up**: consumare più della propria media; l'energia in più è gratuita.

Calcola il consumo abituale con le regole del regolamento di Octopus, misura il consumo durante l'evento e stima il risultato.

## Come calcola

- **Consumo abituale**: media del consumo nelle stesse ore dell'evento, sugli ultimi 10 giorni dello stesso tipo prima del giorno dell'evento. I tipi sono due: feriali, oppure sabato, domenica e festivi. Le feste nazionali sono comprese, Pasquetta e il 4 ottobre (dal 2026) inclusi; il patrono si aggiunge nelle opzioni.
- **Dati**: le statistiche orarie a lungo termine del sensore di energia scelto, come i dati orari del contatore 2G che usa Octopus. Un giorno senza tutte le ore della fascia non conta.
- **Giorni con altri eventi**: il regolamento dice di escluderli, ma nei Power Up di maggio 2026 i risultati comunicati da Octopus tornano solo senza esclusione. Per questo l'esclusione è un'opzione, spenta di default.
- **Consumo durante l'evento**: dal vivo, come differenza dalla lettura del sensore all'inizio (presa dallo storico, quindi vale anche dopo un riavvio). Circa 15 minuti dopo la fine viene sostituito dalla somma delle statistiche orarie.

Il calcolo è stato confrontato con i risultati comunicati da Octopus per alcuni eventi passati del 2026: riduzioni e consumi coincidono entro qualche punto percentuale.

## Installazione

HACS → Repository personalizzati → questo repository, categoria Integrazione. Poi Impostazioni → Dispositivi e servizi → Aggiungi integrazione → **Octopus eventi**, e scegli il sensore dell'energia prelevata dalla rete (kWh, cumulativo, con statistiche).

## Entità

Tutte riguardano l'evento in corso; se non ce n'è uno, il prossimo; altrimenti l'ultimo concluso.

| Entità | Contenuto |
|---|---|
| `sensor.octopus_eventi_stato` | `nessuno`, `programmato`, `in_corso`, `concluso`; attributi: tipo, orari, soglie, adesione, `storico` degli eventi conclusi |
| `sensor.octopus_eventi_inizio`, `sensor.octopus_eventi_fine` | orari dell'evento |
| `sensor.octopus_eventi_consumo_abituale` | kWh; attributi: giorni usati, giorni scartati, `obiettivi` (consumo massimo per ogni soglia) |
| `sensor.octopus_eventi_consumo` | kWh consumati durante l'evento; attributo `definitivo` |
| `sensor.octopus_eventi_variazione` | % rispetto alla media (negativa = consumo ridotto) |
| `sensor.octopus_eventi_rispetto_media` | consumo in % della media (100 = uguale), per le barre |
| `sensor.octopus_eventi_tipo` | `energy_break`, `power_up` o `nessuno` |
| `sensor.octopus_eventi_sconto_stimato` | euro (solo Energy Break) |
| `sensor.octopus_eventi_energia_gratuita` | kWh oltre la media (solo Power Up) |
| `binary_sensor.octopus_eventi_in_corso` | acceso durante l'evento |

### Inserire un evento dalla dashboard

Octopus annuncia gli eventi per email; l'integrazione non legge la posta. Per inserirli senza passare dai servizi:

| Entità | Contenuto |
|---|---|
| `select.octopus_eventi_nuovo_tipo` | Energy Break o Power Up |
| `datetime.octopus_eventi_nuovo_inizio` | inizio, arrotondato all'ora intera |
| `select.octopus_eventi_nuova_durata` | 1, 2, 3 o 4 ore |
| `text.octopus_eventi_nuove_soglie` | solo Energy Break: `50:2` oppure `20:1, 50:3` |
| `datetime.octopus_eventi_nuova_adesione` | termine per confermare la partecipazione dal modulo dell'email |
| `button.octopus_eventi_aggiungi` | aggiunge l'evento (se si sovrappone a uno esistente, lo aggiorna) |
| `button.octopus_eventi_annulla_prossimo` | toglie il prossimo evento in programma |

### Eventi passati

`select.octopus_eventi_evento_mostrato` elenca gli eventi conclusi (dal più recente); negli attributi i dati di quello scelto (orari, consumo abituale, consumo, variazione, premio, obiettivi, esito di Octopus), per i grafici dello storico.

Eventi sul bus per le automazioni: `octopus_eventi_inizio` e `octopus_eventi_fine`, con il riepilogo dell'evento (a fine evento, quando il consumo è definitivo).

## Servizi

- `octopus_eventi.aggiungi_evento`: tipo, inizio, fine (ore intere), soglie (`50:2` oppure `20:1, 50:3`: riduzione % : euro), adesione entro, note. Se l'evento si sovrappone a uno già inserito, lo aggiorna.
- `octopus_eventi.rimuovi_evento`, `octopus_eventi.ricalcola`.
- `octopus_eventi.registra_esito_octopus`: salva il risultato comunicato da Octopus, per confrontarlo con il calcolo.
- `octopus_eventi.elenco_eventi`: restituisce tutti gli eventi.

## Test

`python3 tests/test_calcolo.py` (oppure `pytest tests`): non serve Home Assistant.
