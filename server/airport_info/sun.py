"""Approximate sunrise / sunset (NOAA algorithm, ±2 min) for NOTAM 'SR-SS' schedules."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone


def sun_times(lat: float, lon: float, d: date) -> tuple[datetime, datetime]:
    n = d.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (n - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
                       - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
    la = math.radians(lat)
    cos_ha = (math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(decl))) - math.tan(la) * math.tan(decl)
    cos_ha = max(-1.0, min(1.0, cos_ha))
    ha = math.degrees(math.acos(cos_ha))
    midnight = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    rise = 720 - 4 * (lon + ha) - eqtime
    sset = 720 - 4 * (lon - ha) - eqtime
    return midnight + timedelta(minutes=round(rise)), midnight + timedelta(minutes=round(sset))
