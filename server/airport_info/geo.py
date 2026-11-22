"""Small geodesy helpers (nautical miles, DMS parsing, polygon distance)."""
from __future__ import annotations

import math
import re

EARTH_NM = 3440.065


def distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_NM * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def compass(deg: float) -> str:
    points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return points[int((deg + 22.5) // 45) % 8]


_DMS = re.compile(r"^(\d{2})(\d{2})(\d{2}(?:\.\d+)?)?([NS])\s*(\d{3})(\d{2})(\d{2}(?:\.\d+)?)?([EW])$")


def parse_dms(text: str) -> tuple[float, float] | None:
    """Parse '510029N 0023845W' (AIP) or '5230N00153W' (NOTAM Q-line)."""
    m = _DMS.match(text.strip().replace(" ", ""))
    if not m:
        return None
    lat = int(m[1]) + int(m[2]) / 60 + (float(m[3]) / 3600 if m[3] else 0)
    lon = int(m[5]) + int(m[6]) / 60 + (float(m[7]) / 3600 if m[7] else 0)
    if m[4] == "S":
        lat = -lat
    if m[8] == "W":
        lon = -lon
    return lat, lon


def _project(lat0: float, lat: float, lon: float) -> tuple[float, float]:
    """Equirectangular projection in nm around reference latitude lat0."""
    return lon * 60 * math.cos(math.radians(lat0)), lat * 60


def polygon_distance_nm(lat: float, lon: float, poly: list[tuple[float, float]]) -> float:
    """Distance from point to polygon edge (0 if inside). Good to ~1% at UK scales."""
    if not poly:
        return math.inf
    px, py = _project(lat, lat, lon)
    pts = [_project(lat, a, b) for a, b in poly]
    inside = False
    best = math.inf
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xin = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < xin:
                inside = not inside
        dx, dy = x2 - x1, y2 - y1
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L))
        best = min(best, math.hypot(px - (x1 + t * dx), py - (y1 + t * dy)))
    return 0.0 if inside else best
