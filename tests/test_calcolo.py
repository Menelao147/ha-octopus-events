"""Test del modulo di calcolo: python3 -m pytest tests (oppure python3 tests/test_calcolo.py)."""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "octopus_eventi"))
import calcolo as c  # noqa: E402

ROMA = ZoneInfo("Europe/Rome")


def ora(testo: str) -> datetime:
    return datetime.strptime(testo, "%Y-%m-%d %H").replace(tzinfo=ROMA)


def test_pasqua():
    assert c.pasqua(2026) == date(2026, 4, 5)
    assert c.pasqua(2027) == date(2027, 3, 28)
    assert c.pasqua(2024) == date(2024, 3, 31)


def test_festivi():
    f = c.festivi(2026)
    assert date(2026, 4, 6) in f  # Pasquetta
    assert date(2026, 10, 4) in f  # San Francesco, festivo dal 2026
    assert date(2025, 10, 4) not in c.festivi(2025)
    assert c.festivo(date(2026, 5, 1))  # venerdì, festa
    assert not c.festivo(date(2026, 5, 4))  # lunedì
    assert c.festivo(date(2026, 7, 12), {date(2026, 7, 12)}) and not c.festivo(date(2026, 7, 13), {date(2026, 7, 12)})


def test_giorni_candidati_feriali_e_festivi():
    # Martedì 20/10/2026: feriali precedenti, senza weekend.
    feriali = c.giorni_candidati(date(2026, 10, 20))
    assert feriali[:6] == [date(2026, 10, 19), date(2026, 10, 16), date(2026, 10, 15), date(2026, 10, 14), date(2026, 10, 13), date(2026, 10, 12)]
    # Venerdì 1/5 è festivo: si usano weekend e festivi (Pasquetta compresa).
    festivi = c.giorni_candidati(date(2026, 5, 1))
    assert festivi[:3] == [date(2026, 4, 26), date(2026, 4, 25), date(2026, 4, 19)]
    assert date(2026, 4, 6) in festivi
    # Giorni esclusi.
    assert date(2026, 10, 19) not in c.giorni_candidati(date(2026, 10, 20), {date(2026, 10, 19)})


def test_ore_finestra_con_cambio_ora():
    # Evento alle 19 di novembre riportato su un giorno di ottobre con l'ora legale: sempre le 19 locali.
    ore = c.ore_finestra(ora("2026-11-03 19"), ora("2026-11-03 21"), date(2026, 10, 20))
    assert [o.hour for o in ore] == [19, 20]
    assert ore[0].utcoffset() == timedelta(hours=2)


def _orari(valori: dict[str, float]) -> dict[float, float]:
    return {ora(k).timestamp(): v for k, v in valori.items()}


def test_consumo_abituale():
    consumi = {}
    for n in range(1, 30):
        g = date(2026, 10, 20) - timedelta(days=n)
        consumi[f"{g} 19"] = 0.4 if g.weekday() < 5 else 5.0  # i weekend non devono contare
    del consumi["2026-10-16 19"]  # giorno senza dati: scartato
    r = c.consumo_abituale(ora("2026-10-20 19"), ora("2026-10-20 20"), _orari(consumi))
    assert len(r.giorni) == 10
    assert abs(r.valore - 0.4) < 1e-9
    assert date(2026, 10, 16) in r.scartati


def test_consumo_abituale_due_ore():
    consumi = {}
    for n in range(1, 40):
        g = date(2026, 5, 24) - timedelta(days=n)
        consumi[f"{g} 12"] = 0.2
        consumi[f"{g} 13"] = 0.3
    r = c.consumo_abituale(ora("2026-05-24 12"), ora("2026-05-24 14"), _orari(consumi))
    assert abs(r.valore - 0.5) < 1e-9


def test_esito_energy_break():
    soglie = [c.Soglia(20, 1), c.Soglia(50, 3)]
    assert c.esito(c.ENERGY_BREAK, 0.4, 0.2, soglie).premio == 3
    assert c.esito(c.ENERGY_BREAK, 0.4, 0.3, soglie).premio == 1
    e = c.esito(c.ENERGY_BREAK, 0.4, 0.36, [c.Soglia(50, 2)])
    assert e.premio == 0 and abs(e.variazione - 10) < 1e-9  # esempio del regolamento
    assert [round(k, 3) for _, k in c.obiettivi(0.4, soglie)] == [0.32, 0.2]


def test_esito_power_up():
    e = c.esito(c.POWER_UP, 0.4, 1.0, [])  # esempio del regolamento
    assert abs(e.premio - 0.6) < 1e-9 and abs(e.variazione - 150) < 1e-9
    assert c.esito(c.POWER_UP, 0.4, 0.3, []).premio == 0


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
