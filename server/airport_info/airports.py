"""UK airport lookup by ICAO (4 letters) or IATA (3 letters)."""
from __future__ import annotations

import json
import pathlib
from functools import lru_cache

DATA = pathlib.Path(__file__).parent / "data" / "uk_airports.json"


@lru_cache(maxsize=1)
def _all() -> list[dict]:
    return json.loads(DATA.read_text())


def resolve(code: str) -> dict | None:
    code = (code or "").strip().upper()
    if len(code) == 4:
        return next((a for a in _all() if a["icao"] == code), None)
    if len(code) == 3:
        return next((a for a in _all() if a["iata"] == code), None)
    return None


def search(query: str, limit: int = 15) -> list[dict]:
    q = (query or "").strip().upper()
    if not q:
        return []
    exact, starts, contains = [], [], []
    for a in _all():
        name = f"{a['name']} {a['city']}".upper()
        if q in (a["icao"], a["iata"]):
            exact.append(a)
        elif a["icao"].startswith(q) or a["iata"].startswith(q) or name.startswith(q):
            starts.append(a)
        elif q in name:
            contains.append(a)
    return (exact + starts + contains)[:limit]


def display_name(a: dict) -> str:
    """Tidy OurAirports names for a signage header ('Gloucestershire Airport' -> 'GLOUCESTERSHIRE AIRPORT')."""
    return a["name"].upper()
