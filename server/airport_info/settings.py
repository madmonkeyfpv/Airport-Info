"""Persistent display settings (JSON file). Every key can also be overridden per request via query string."""
from __future__ import annotations

import hashlib
import json
import pathlib
import threading

DEFAULTS = {
    "airport": "EGSU",            # ICAO (4) or IATA (3) code of any UK airport (default: Duxford)
    "title": "",                  # header override; blank = airport name
    "subtitle": "",               # blank = "ICAO / IATA · AIRPORT INFORMATION"
    "temp_unit": "C",             # C or F
    "clock": "24h",               # 24h or 12h
    "show_zulu": True,            # show UTC alongside local times
    "airspace_range_nm": 30,      # search radius for restricted/danger areas
    "airspace_cards": 2,          # number of area cards shown
    "airspace_pinned": [],        # e.g. ["D123", "R105"] to fix which areas are shown
    "warning_range_nm": 10,       # radius for nav warnings (drones, parachuting, etc.)
    "include_obstacle_notams": False,
    "include_airspace_notams": False,
    "refresh_seconds": 60,        # display refresh interval
    "theme": "navy",              # navy | midnight | high-contrast
    "show_radio": True,           # radio strip: frequencies, estimated status, D-ATIS letter where available
    # Opening hours override, UK local. Blank = use data/opening_hours.json for the airport (EGSU included).
    # Formats: "0900-1700", "MON-FRI 0800-1800, SAT SUN 0900-1700", "15MAR-15OCT 1000-1800; 16OCT-14MAR 1000-1600", "H24".
    "service_hours": "",
    "show_traffic": True,         # live nearby traffic (ADS-B via adsb.lol) in the arrivals panel
    "traffic_range_nm": 10,       # how far from the airfield to show traffic
    "traffic_max_ft_agl": 3000,   # ignore aircraft higher than this above the airfield (transit / airliners)
    "view": "board",              # board | weather | rotate  (rotate alternates both)
    "rotate_seconds": 30,         # time on each page when view = rotate
}

TYPES = {k: type(v) for k, v in DEFAULTS.items()}


def coerce(key: str, value):
    t = TYPES.get(key)
    if t is None:
        raise KeyError(key)
    if t is bool:
        return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
    if t is int:
        return int(float(value))
    if t is list:
        if isinstance(value, list):
            return [str(v).strip().upper() for v in value if str(v).strip()]
        return [v.strip().upper() for v in str(value).split(",") if v.strip()]
    return str(value).strip()


class Settings:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self._lock = threading.Lock()
        self.values = dict(DEFAULTS)
        if path.exists():
            try:
                stored = json.loads(path.read_text())
                for k, v in stored.items():
                    if k in DEFAULTS:
                        self.values[k] = coerce(k, v)
            except (ValueError, KeyError, TypeError):
                pass

    def update(self, changes: dict) -> dict:
        with self._lock:
            for k, v in changes.items():
                if k in DEFAULTS:
                    self.values[k] = coerce(k, v)
            self.values["airport"] = self.values["airport"].upper()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.values, indent=2))
            return dict(self.values)

    @property
    def version(self) -> str:
        """Fingerprint of the saved settings. Screens poll it and reload as soon as it changes,
        so every display (board, weather page, HA cards) switches airport together."""
        return hashlib.sha1(json.dumps(self.values, sort_keys=True).encode()).hexdigest()[:12]

    def effective(self, query) -> dict:
        out = dict(self.values)
        for k in DEFAULTS:
            if k in query and query[k] != "":
                try:
                    out[k] = coerce(k, query[k])
                except (ValueError, KeyError):
                    pass
        out["airport"] = out["airport"].upper()
        return out
