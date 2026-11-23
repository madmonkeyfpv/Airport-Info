"""Live nearby traffic from ADS-B (adsb.lol community feed, open data, no key).

Small UK airfields have no scheduled flights and most VFR GA flights file no flight plan, so FlightAware's
"expected" tables stay empty. This module shows what is actually flying near the airfield right now, classified
from position, height, closing speed and climb rate:

  approaching   heading for the field (closing > 25 kt) and low / descending  -> ETA in minutes
  circuit       within ~2.5 NM and below ~1,500 ft above the field
  ground        reporting "ground" within ~1.5 NM of the field
  departed      within ~6 NM, moving away, climbing or still low
  nearby        anything else low enough to be local traffic

Limits (also stated on screen): only aircraft with ADS-B / Mode S, seen by community receivers; nothing before
take-off. Information only.
"""
from __future__ import annotations

import math

from .geo import bearing_deg, compass, distance_nm

API = "https://api.adsb.lol/v2/point/{lat:.4f}/{lon:.4f}/{radius}"
STALE_POSITION_S = 60

# Friendly names for common ICAO type codes (GA + Duxford's warbirds); unknown codes are shown as-is.
TYPE_NAMES = {
    "C150": "Cessna 150", "C152": "Cessna 152", "C172": "Cessna 172", "C182": "Cessna 182", "C206": "Cessna 206",
    "C210": "Cessna 210", "C310": "Cessna 310", "C42": "Ikarus C42", "P28A": "Piper PA-28", "P28R": "Piper Arrow",
    "P28B": "Piper PA-28", "PA34": "Piper Seneca", "PA32": "Piper Saratoga", "PA18": "Piper Super Cub",
    "J3": "Piper Cub", "DR40": "Robin DR400", "R200": "Robin HR200", "G115": "Grob Tutor", "G109": "Grob G109",
    "SR20": "Cirrus SR20", "SR22": "Cirrus SR22", "DA40": "Diamond DA40", "DA42": "Diamond DA42",
    "DA62": "Diamond DA62", "DV20": "Diamond Katana", "TB20": "Socata Trinidad", "TB10": "Socata Tobago",
    "BE36": "Beech Bonanza", "BE58": "Beech Baron", "BE20": "King Air 200", "PC12": "Pilatus PC-12",
    "TBM9": "Daher TBM 900", "AA5": "Grumman AA-5", "RV7": "Van's RV-7", "RV8": "Van's RV-8", "RV9": "Van's RV-9",
    "RV6": "Van's RV-6", "EUPA": "EuroFOX", "SIRA": "SIAI Marchetti", "CH60": "Zenith", "AUS5": "Auster",
    "DHC1": "DH Chipmunk", "DH82": "DH Tiger Moth", "DH89": "DH Dragon Rapide", "SPIT": "Supermarine Spitfire",
    "HURI": "Hawker Hurricane", "P51": "P-51 Mustang", "T6": "T-6 Harvard", "B17": "B-17 Flying Fortress",
    "DC3": "Douglas DC-3", "C47": "C-47 Dakota", "BU31": "Bücker Jungmann", "YK52": "Yak-52", "YK50": "Yak-50",
    "EXTR": "Extra 300", "EA30": "Extra 300", "CAP2": "CAP 232", "PTS2": "Pitts Special", "S2": "Pitts Special",
    "EC35": "Airbus H135", "EC45": "Airbus H145", "EC30": "Airbus H130", "R44": "Robinson R44",
    "R22": "Robinson R22", "R66": "Robinson R66", "A109": "Leonardo AW109", "A139": "Leonardo AW139",
    "B06": "Bell JetRanger", "B407": "Bell 407", "AS50": "Airbus AS350", "GLID": "Glider",
}


def type_name(code: str | None) -> str:
    code = (code or "").strip().upper()
    return TYPE_NAMES.get(code, code)


def _num(v):
    return v if isinstance(v, (int, float)) else None


def classify(ac: dict, field: dict, qnh: float | None, max_ft_agl: int) -> dict | None:
    """Turn one adsb.lol aircraft record into a display item, or None if it isn't local traffic."""
    lat, lon = _num(ac.get("lat")), _num(ac.get("lon"))
    if lat is None or lon is None or (_num(ac.get("seen_pos")) or 0) > STALE_POSITION_S:
        return None
    d = distance_nm(field["lat"], field["lon"], lat, lon)
    elev = field.get("elev") or 0
    on_ground = ac.get("alt_baro") == "ground"
    alt_baro = _num(ac.get("alt_baro"))
    if on_ground:
        if d > 1.5:
            return None  # aircraft parked at a different airfield nearby
        alt_ft, agl = elev, 0
    else:
        if alt_baro is None:
            return None
        # Pressure altitude -> altitude on the local QNH (≈27 ft per hPa); geometric altitude if no QNH.
        alt_ft = round(alt_baro + (qnh - 1013.25) * 27) if qnh else (_num(ac.get("alt_geom")) or alt_baro)
        agl = alt_ft - elev
        if agl > max_ft_agl:
            return None  # transit / airliner traffic, not local
    gs = _num(ac.get("gs")) or 0
    track = _num(ac.get("track"))
    vs = _num(ac.get("baro_rate"))
    if vs is None:
        vs = _num(ac.get("geom_rate"))
    # Community ADS-B occasionally carries corrupt values (seen live: a PA-28 at 415 kt climbing 64,900 fpm).
    # Nothing this low near an airfield does that, so drop implausible numbers rather than display them.
    if gs > 400:
        gs, track = 0, None
    if vs is not None and abs(vs) > 6000:
        vs = None
    brg_from_field = bearing_deg(field["lat"], field["lon"], lat, lon)
    closing = 0.0
    if track is not None and gs:
        to_field = (brg_from_field + 180) % 360
        closing = gs * math.cos(math.radians(track - to_field))

    eta = None
    climbing_away = vs is not None and vs > 500 and closing < -15
    if on_ground:
        status = "ground"
    elif climbing_away and d <= 6:
        status = "departed"       # climbing away from the field: just took off
    elif d <= 2.5 and agl <= 1500:
        status = "circuit"
    elif closing > 25 and (agl <= 2500 or (vs is not None and vs < -200)):
        status = "approaching"
        eta = max(1, round(d / closing * 60))
    elif d <= 6 and closing < -15 and ((vs is not None and vs > 200) or agl <= 1500):
        status = "departed"
    else:
        status = "nearby"
    reg = (ac.get("r") or "").strip()
    callsign = (ac.get("flight") or "").strip()
    ident = reg or callsign or ac.get("hex", "").upper()
    return {
        "hex": ac.get("hex"),
        "ident": ident,
        # Hide callsigns that merely restate the registration (G-CKVV / GCKVV, or D-EGCK broadcasting GEGCK).
        "callsign": callsign if callsign and callsign.replace("-", "")[1:] != reg.replace("-", "")[1:] else "",
        "type_code": (ac.get("t") or "").strip(),
        "type_name": type_name(ac.get("t")),
        "status": status,
        "eta_min": eta,
        "distance_nm": round(d, 1),
        "bearing": compass(brg_from_field),
        "alt_ft": int(alt_ft),
        "agl_ft": int(agl),
        "gs_kt": round(gs),
        "vs_fpm": int(vs) if vs is not None else None,
        "track": track,
        "squawk": ac.get("squawk"),
        "emergency": (ac.get("emergency") not in (None, "none")) or ac.get("squawk") in ("7500", "7600", "7700"),
        "seen_s": _num(ac.get("seen_pos")),
    }


ORDER = {"approaching": 0, "circuit": 1, "ground": 2, "departed": 3, "nearby": 4}


def build_traffic(payload: dict, field: dict, qnh: float | None, range_nm: float, max_ft_agl: int) -> dict:
    items = [c for c in (classify(a, field, qnh, max_ft_agl) for a in (payload or {}).get("ac") or []) if c]
    items = [c for c in items if c["distance_nm"] <= range_nm]
    items.sort(key=lambda c: (ORDER[c["status"]], c["eta_min"] or 0, c["distance_nm"]))
    return {"aircraft": items, "range_nm": range_nm, "max_ft_agl": max_ft_agl, "source": "adsb.lol (ADS-B, ODbL)"}


async def fetch_traffic(session, field: dict, range_nm: float) -> dict:
    # Query a little wider than the display range so aircraft about to enter it are included.
    url = API.format(lat=field["lat"], lon=field["lon"], radius=int(min(250, max(5, range_nm + 5))))
    async with session.get(url, headers={"User-Agent": "AirportInfoDisplay (home airfield display)"}) as r:
        r.raise_for_status()
        return await r.json(content_type=None)
