"""Calcoli degli eventi Octopus (Energy Break e Power Up), senza dipendenze da Home Assistant.

Regole dal regolamento Energy Break di Octopus Energy Italia (versione del 19/10/2026):
- Consumo Abituale: media dei consumi nelle stesse fasce orarie, fino agli ultimi 10 giorni
  prima dell'evento, solo giorni dello stesso tipo (feriali, oppure weekend e festivi),
  esclusi i giorni in cui si è già svolto un evento.
- Riduzione: differenza percentuale tra Consumo Abituale e consumo durante l'evento.
- Premi: soglie di riduzione con il loro importo, comunicate evento per evento.
Per il Power Up si usa lo stesso Consumo Abituale; l'energia sopra la media è gratuita.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

ENERGY_BREAK = "energy_break"
POWER_UP = "power_up"
TIPI = (ENERGY_BREAK, POWER_UP)

GIORNI_RIFERIMENTO = 10
# Quanto indietro cercare i giorni dello stesso tipo: con 10 giorni di weekend servono circa 5 settimane.
GIORNI_RICERCA = 40


def pasqua(anno: int) -> date:
    """Domenica di Pasqua (calendario gregoriano, algoritmo anonimo)."""
    a, b, c = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = (h + l - 7 * m + 114) % 31 + 1
    return date(anno, mese, giorno)


def festivi(anno: int) -> set[date]:
    """Festività nazionali italiane (San Francesco, 4 ottobre, di nuovo festiva dal 2026)."""
    giorni = {
        date(anno, 1, 1),
        date(anno, 1, 6),
        date(anno, 4, 25),
        date(anno, 5, 1),
        date(anno, 6, 2),
        date(anno, 8, 15),
        date(anno, 11, 1),
        date(anno, 12, 8),
        date(anno, 12, 25),
        date(anno, 12, 26),
        pasqua(anno) + timedelta(days=1),
    }
    if anno >= 2026:
        giorni.add(date(anno, 10, 4))
    return giorni


def festivo(giorno: date, extra: set[date] | frozenset[date] = frozenset()) -> bool:
    """Vero per sabato, domenica, festività nazionali e giorni aggiunti (per esempio il patrono)."""
    return giorno.weekday() >= 5 or giorno in festivi(giorno.year) or giorno in extra


def giorni_candidati(
    giorno_evento: date,
    esclusi: set[date] | frozenset[date] = frozenset(),
    extra_festivi: set[date] | frozenset[date] = frozenset(),
    ricerca: int = GIORNI_RICERCA,
) -> list[date]:
    """Giorni dello stesso tipo dell'evento, dal più recente, esclusi i giorni con altri eventi."""
    tipo = festivo(giorno_evento, extra_festivi)
    return [
        g
        for g in (giorno_evento - timedelta(days=n) for n in range(1, ricerca + 1))
        if festivo(g, extra_festivi) == tipo and g not in esclusi
    ]


def ore_finestra(inizio: datetime, fine: datetime, giorno: date) -> list[datetime]:
    """Inizi delle ore della fascia dell'evento riportata su un altro giorno, con l'ora legale di quel giorno."""
    fuso = inizio.tzinfo
    primo = datetime.combine(giorno, inizio.timetz().replace(tzinfo=None), fuso)
    durata_ore = round((fine - inizio).total_seconds() / 3600)
    return [primo + timedelta(hours=n) for n in range(durata_ore)]


@dataclass
class ConsumoAbituale:
    valore: float | None
    giorni: list[tuple[date, float]] = field(default_factory=list)
    scartati: list[date] = field(default_factory=list)  # giorni dello stesso tipo senza dati completi


def consumo_abituale(
    inizio: datetime,
    fine: datetime,
    consumi_orari: dict[float, float],
    esclusi: set[date] | frozenset[date] = frozenset(),
    extra_festivi: set[date] | frozenset[date] = frozenset(),
    giorni: int = GIORNI_RIFERIMENTO,
) -> ConsumoAbituale:
    """Media del consumo della fascia sugli ultimi `giorni` giorni validi.

    `consumi_orari` ha come chiave l'inizio dell'ora (timestamp Unix) e come valore i kWh di quell'ora.
    Un giorno senza tutte le ore della fascia non conta.
    """
    risultato = ConsumoAbituale(valore=None)
    for giorno in giorni_candidati(inizio.date(), esclusi, extra_festivi):
        valori = [consumi_orari.get(ora.timestamp()) for ora in ore_finestra(inizio, fine, giorno)]
        if not valori or any(v is None for v in valori):
            risultato.scartati.append(giorno)
            continue
        risultato.giorni.append((giorno, sum(valori)))
        if len(risultato.giorni) == giorni:
            break
    if risultato.giorni:
        risultato.valore = sum(v for _, v in risultato.giorni) / len(risultato.giorni)
    return risultato


@dataclass
class Soglia:
    percentuale: float  # riduzione minima (Energy Break), in %
    euro: float


@dataclass
class Esito:
    variazione: float | None  # Energy Break: riduzione in %; Power Up: aumento in %
    premio: float | None  # Energy Break: euro; Power Up: kWh gratuiti
    soglia: Soglia | None = None


def esito(tipo: str, abituale: float | None, consumo: float | None, soglie: list[Soglia]) -> Esito:
    if abituale is None or consumo is None:
        return Esito(None, None)
    if tipo == POWER_UP:
        extra = max(consumo - abituale, 0.0)
        aumento = (consumo - abituale) / abituale * 100 if abituale > 0 else None
        return Esito(aumento, extra)
    if abituale <= 0:
        return Esito(None, None)
    riduzione = (abituale - consumo) / abituale * 100
    raggiunte = [s for s in soglie if riduzione >= s.percentuale]
    migliore = max(raggiunte, key=lambda s: s.euro, default=None)
    return Esito(riduzione, migliore.euro if migliore else 0.0, migliore)


def obiettivi(abituale: float | None, soglie: list[Soglia]) -> list[tuple[Soglia, float]]:
    """Energy Break: per ogni soglia, il consumo massimo in kWh per raggiungerla."""
    if abituale is None:
        return []
    return [(s, abituale * (1 - s.percentuale / 100)) for s in sorted(soglie, key=lambda s: s.percentuale)]
