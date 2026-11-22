"""METAR weather from aviationweather.gov (free, no key).

If the selected airfield has no METAR (common at small UK airfields) or its last
report is stale (airfield closed overnight), the nearest fresh METAR within
`max_nm` is used and flagged with `source_icao` / `distance_nm`.
"""
from __future__ import annotations

import math
import re
import time

from .geo import distance_nm

API = "https://aviationweather.gov/api/data/metar"
STALE_SECONDS = 3 * 3600


def _visibility(raw: str, cover: str | None) -> str:
    if " CAVOK" in raw or cover == "CAVOK":
        return "10 KM+"
    m = re.search(r"KT\s+(?:\d{3}V\d{3}\s+)?(\d{4})(?:NDV)?\b", raw)
    if m:
        v = int(m[1])
        return "10 KM+" if v == 9999 else (f"{v / 1000:g} KM" if v >= 5000 else f"{v} M")
    m = re.search(r"\b(\d{1,2})SM\b", raw)
    return f"{m[1]} SM" if m else ""


_RVR = re.compile(r"\bR(\d{2}[LRC]?)/([PM])?(\d{4})(?:V([PM])?(\d{4}))?(FT)?([UDN])?(?=\s|$)")


def parse_rvr(raw: str) -> list[dict]:
    """METAR RVR groups, e.g. R24/0600N, R27L/P1500, R09/0400V0800U (metres unless FT)."""
    body = raw.split(" RMK")[0]
    out = []
    for m in _RVR.finditer(body):
        out.append({
            "runway": m[1],
            "min_m": int(m[3]), "min_qual": {"P": "above", "M": "below"}.get(m[2] or "", ""),
            "max_m": int(m[5]) if m[5] else None, "max_qual": {"P": "above", "M": "below"}.get(m[4] or "", ""),
            "feet": bool(m[6]),
            "tendency": {"U": "up", "D": "down", "N": "steady"}.get(m[7] or "", ""),
        })
    return out


def _sky(m: dict, raw: str) -> str:
    if " CAVOK" in raw:
        return "CAVOK"
    layers = [f"{c['cover']}{int(c['base']) // 100:03d}" if c.get("base") is not None else c["cover"]
              for c in m.get("clouds") or []]
    vv = re.search(r"\bVV(\d{3})\b", raw)
    if vv:
        layers.append(f"VV{vv[1]}")
    if layers:
        return " ".join(layers)
    for code in ("NSC", "NCD", "SKC", "CLR"):
        if f" {code}" in raw:
            return code
    return m.get("cover") or ""


def derived(qnh: float | None, temp: float | None, dew: float | None, elev_ft: float | None) -> dict:
    out = {}
    if qnh:
        out["qnh_inhg"] = round(qnh * 0.0295300, 2)
        if elev_ft is not None:
            out["qfe"] = round(qnh - elev_ft / 27.0)
            pa = elev_ft + (1013.25 - qnh) * 27.0
            out["pressure_alt_ft"] = round(pa)
            if temp is not None:
                isa = 15 - 1.98 * pa / 1000
                out["density_alt_ft"] = int(round((pa + 118.8 * (temp - isa)) / 10) * 10)
    if temp is not None and dew is not None:
        g = lambda t: math.exp(17.625 * t / (243.04 + t))
        out["humidity"] = round(100 * g(dew) / g(temp))
    return out


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
    raw = m.get("rawOb") or ""
    var = re.search(r"\b(\d{3})V(\d{3})\b", raw)
    return {
        "wind_var_from": int(var[1]) if var else None,
        "wind_var_to": int(var[2]) if var else None,
        "visibility_text": _visibility(raw, m.get("cover")),
        "sky": _sky(m, raw),
        "weather": m.get("wxString") or "",
        "rvr": parse_rvr(raw),
        "clouds": m.get("clouds") or [],
        **derived(m.get("altim"), m.get("temp"), m.get("dewp"), airport.get("elev")),
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
