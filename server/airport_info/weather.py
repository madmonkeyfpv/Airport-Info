"""METAR weather from aviationweather.gov (free, no key).

If the selected airfield has no METAR (common at small UK airfields) or its last
report is stale (airfield closed overnight), the nearest fresh METAR within
`max_nm` is used and flagged with `source_icao` / `distance_nm`.
"""
from __future__ import annotations

import time

from .geo import distance_nm

API = "https://aviationweather.gov/api/data/metar"
STALE_SECONDS = 3 * 3600


def _summarise(m: dict, airport: dict) -> dict:
    wdir, wspd = m.get("wdir"), m.get("wspd")
    if wspd in (None, 0):
        wind = "CALM"
    elif isinstance(wdir, (int, float)):
        wind = f"{int(wdir):03d}° {int(wspd)}KT"
    else:
        wind = f"VRB {int(wspd)}KT"
    if m.get("wgst"):
        wind += f" G{int(m['wgst'])}"
    return {
        "source_icao": m.get("icaoId"),
        "source_name": m.get("name"),
        "is_local": m.get("icaoId") == airport.get("icao"),
        "distance_nm": round(distance_nm(airport["lat"], airport["lon"], m["lat"], m["lon"]), 1) if m.get("lat") else None,
        "observed": m.get("reportTime"),
        "obs_epoch": m.get("obsTime"),
        "temp_c": m.get("temp"),
        "dewpoint_c": m.get("dewp"),
        "wind": wind,
        "wind_dir": wdir if isinstance(wdir, (int, float)) else None,
        "wind_kt": wspd,
        "gust_kt": m.get("wgst"),
        "visibility": m.get("visib"),
        "qnh": round(m["altim"]) if isinstance(m.get("altim"), (int, float)) else None,
        "cover": m.get("cover"),
        "flight_category": m.get("fltCat"),
        "raw": m.get("rawOb"),
    }


async def fetch_weather(session, airport: dict, max_nm: float = 40) -> dict | None:
    now = time.time()
    if airport.get("icao"):
        async with session.get(API, params={"ids": airport["icao"], "format": "json"}) as r:
            data = await r.json(content_type=None) if r.status == 200 else []
        if data and now - (data[0].get("obsTime") or 0) < STALE_SECONDS:
            return _summarise(data[0], airport)
    d = 0.8  # ~48nm box
    lat, lon = airport["lat"], airport["lon"]
    bbox = f"{lat - d:.2f},{lon - d * 1.6:.2f},{lat + d:.2f},{lon + d * 1.6:.2f}"
    async with session.get(API, params={"bbox": bbox, "format": "json"}) as r:
        data = await r.json(content_type=None) if r.status == 200 else []
    fresh = [m for m in data or [] if now - (m.get("obsTime") or 0) < STALE_SECONDS and m.get("lat") is not None]
    if not fresh:
        return None
    best = min(fresh, key=lambda m: distance_nm(airport["lat"], airport["lon"], m["lat"], m["lon"]))
    s = _summarise(best, airport)
    if s["distance_nm"] is not None and s["distance_nm"] > max_nm:
        return None
    return s
