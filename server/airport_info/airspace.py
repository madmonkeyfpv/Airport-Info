"""UK restricted / danger / prohibited airspace near an airport, with live activation status.

Static geometry: UK AIP ENR 5.1 areas from the community-maintained YAIXM dataset
(https://gitlab.com/ahsparrow/airspace, public domain, updated each AIRAC). It is scraped
from GitHub raw and cached on disk; a bundled snapshot is used if the download fails.

Live status: NATS PIB NOTAMs (see notams.py). Activation (QRDCA etc.), installation of
temporary areas (TDA/TRA, QRDCS/QRTCS) and deactivation (QRDCD) are matched to areas by
their designator (e.g. 'EGD123A' -> D123A).
"""
from __future__ import annotations

import math
import pathlib
import re
import time

import yaml

from .geo import bearing_deg, compass, distance_nm, parse_dms, polygon_distance_nm

SRC = "https://raw.githubusercontent.com/ahsparrow/airspace/master/airspace.yaml"
BUNDLED = pathlib.Path(__file__).parent / "data" / "uk_airspace.yaml"
CARD_TYPES = {"D", "R", "P"}
STATE_RANK = {"active": 0, "scheduled": 1, "permanent": 2, "published": 3, "cold": 4, "unknown": 5}


def _circle(lat: float, lon: float, r_nm: float, n: int = 24) -> list[tuple[float, float]]:
    return [(lat + r_nm / 60 * math.cos(2 * math.pi * i / n),
             lon + r_nm / 60 * math.sin(2 * math.pi * i / n) / math.cos(math.radians(lat))) for i in range(n)]


def _poly(boundary: list[dict]) -> list[tuple[float, float]]:
    pts = []
    for seg in boundary:
        if "circle" in seg:
            c = parse_dms(seg["circle"]["centre"])
            r = float(str(seg["circle"]["radius"]).split()[0])
            if c:
                pts.extend(_circle(c[0], c[1], r))
        elif "line" in seg:
            pts.extend(p for p in (parse_dms(x) for x in seg["line"]) if p)
        elif "arc" in seg:
            c = parse_dms(seg["arc"]["centre"])
            to = parse_dms(seg["arc"]["to"])
            if c and pts and to:
                # approximate arc with midpoint on the circle
                r = float(str(seg["arc"]["radius"]).split()[0])
                a0 = math.atan2((pts[-1][1] - c[1]) * math.cos(math.radians(c[0])), pts[-1][0] - c[0])
                a1 = math.atan2((to[1] - c[1]) * math.cos(math.radians(c[0])), to[0] - c[0])
                cw = seg["arc"].get("dir", "cw") == "cw"
                da = (a1 - a0) % (2 * math.pi) if cw else -((a0 - a1) % (2 * math.pi))
                for k in range(1, 8):
                    a = a0 + da * k / 8
                    pts.append((c[0] + r / 60 * math.cos(a),
                                c[1] + r / 60 * math.sin(a) / math.cos(math.radians(c[0]))))
            if to:
                pts.append(to)
    return pts


def parse_areas(text: str) -> list[dict]:
    data = yaml.safe_load(text)
    areas = []
    for a in data.get("airspace", []):
        if a.get("type") not in CARD_TYPES:
            continue
        name = a["name"]
        designator = name.split()[0]
        geoms = a.get("geometry") or []
        polys = [_poly(g.get("boundary") or []) for g in geoms]
        areas.append({
            "id": designator,
            "name": " ".join(name.split()[1:]) or designator,
            "type": a["type"],
            "rules": a.get("rules") or [],
            "upper": geoms[0].get("upper") if geoms else "",
            "lower": geoms[0].get("lower") if geoms else "",
            "polygons": [p for p in polys if p],
        })
    return areas


class AirspaceDB:
    def __init__(self, cache_dir: pathlib.Path):
        self.cache_file = cache_dir / "uk_airspace.yaml"
        self.areas: list[dict] = []
        self.loaded_at = 0.0
        self.source = ""

    def load_local(self):
        for f in (self.cache_file, BUNDLED):
            if f.exists():
                self.areas = parse_areas(f.read_text())
                self.source = str(f)
                self.loaded_at = f.stat().st_mtime
                return

    async def refresh(self, session, max_age: float = 86400):
        if self.areas and time.time() - self.loaded_at < max_age:
            return
        try:
            async with session.get(SRC) as r:
                r.raise_for_status()
                text = await r.text()
            areas = parse_areas(text)
            if len(areas) > 50:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                self.cache_file.write_text(text)
                self.areas, self.loaded_at, self.source = areas, time.time(), SRC
                return
        except Exception:  # noqa: BLE001 - fall back to cached / bundled copy
            pass
        if not self.areas:
            self.load_local()
        self.loaded_at = time.time()

    def nearby(self, lat: float, lon: float, range_nm: float) -> list[dict]:
        out = []
        for a in self.areas:
            d = min((polygon_distance_nm(lat, lon, p) for p in a["polygons"]), default=math.inf)
            if d <= range_nm:
                pts = [pt for p in a["polygons"] for pt in p]
                clat = sum(p[0] for p in pts) / len(pts)
                clon = sum(p[1] for p in pts) / len(pts)
                out.append({k: v for k, v in a.items() if k != "polygons"} |
                           {"distance_nm": round(d, 1),
                            "bearing": compass(bearing_deg(lat, lon, clat, clon))})
        return sorted(out, key=lambda x: x["distance_nm"])


def _matches(area_id: str, notam_ids: list[str]) -> bool:
    for nid in notam_ids:
        if nid == area_id or (len(nid) == 4 and area_id.startswith(nid)):
            return True
    return False


_NOT_PLACES = {"TDA", "TRA", "BVLOS", "VLOS", "UAS", "RPAS", "SUA", "ATZ", "CTR", "CTA", "TMZ", "RMZ", "AMSL", "AGL", "TEMPORARY", "TEMPO", "NOTAM"}


def _place(text: str) -> str:
    for m in re.finditer(r"\(([A-Z][A-Z\s,.'/-]{2,50})\)", text.upper()):
        name = " ".join(m[1].split())
        if name not in _NOT_PLACES and len(name) > 3:
            return " ".join(w if w.rstrip(",") in ("RAF", "MOD", "HMS", "USAF", "UK", "AAC") else w.title()
                            for w in name.split())
    return ""


def build_panel(static_areas: list[dict], airspace_notams: list[dict], pinned: list[str],
                cards: int = 2, warning_range_nm: float = 10) -> dict:
    """Combine static areas + NOTAMs into the card list and the 'other activity' summary bar."""
    items = []
    used_notams = set()
    for a in static_areas:
        rel = [n for n in airspace_notams if n["code23"][:1] == "R" and _matches(a["id"], n["area_ids"])]
        deact = [n for n in rel if n["code45"] == "CD" and n["state"] == "active"]
        act = [n for n in rel if n["code45"] != "CD" and n["state"] == "active"]
        sch = sorted([n for n in rel if n["code45"] != "CD" and n["state"] == "scheduled"],
                     key=lambda n: n["next_start"] or "")
        used_notams.update(n["id"] for n in rel)
        if act and not deact:
            state, ref = "active", act[0]
        elif sch and not deact:
            state, ref = "scheduled", sch[0]
        elif deact:
            state, ref = "cold", deact[0]
        elif a["type"] in ("R", "P"):
            state, ref = "permanent", None
        elif "NOTAM" in a["rules"]:
            state, ref = "cold", None
        else:
            state, ref = "published", None
        items.append({
            "id": a["id"], "name": a["name"], "type": a["type"], "temporary": False,
            "state": state, "distance_nm": a["distance_nm"], "bearing": a.get("bearing", ""),
            "upper": ref["upper"] if ref and ref.get("upper") else a["upper"],
            "lower": ref["lower"] if ref and ref.get("lower") else a["lower"],
            "start": ref["next_start"] if ref else None, "end": ref["next_end"] if ref else None,
            "notam": ref["id"] if ref else None,
            "notam_activated": "NOTAM" in a["rules"],
        })
    # Temporary areas only defined by NOTAM (TDA / TRA / RA(T))
    for n in airspace_notams:
        if n["code23"][:1] != "R" or n["id"] in used_notams or n["code45"] == "CD":
            continue
        if n["code23"] in ("RO",):
            continue
        used_notams.add(n["id"])
        ident = n["area_ids"][0] if n["area_ids"] else ""
        tm = re.search(r"\b(EG[TR][RA]\d{3}[A-Z]?)\b", n["text"].upper())
        named = re.search(r"\b(TRA\s?\d{3}[A-Z]?|ARA\s?\d{1,3}[A-Z]?|[A-Z]{2,5}MTA|MTA\s?\d+)\b", n["text"].upper())
        ident = ident or (tm[1][2:] if tm else named[1] if named else "")
        label = {"RD": "TEMP DANGER AREA", "RT": "TEMP RESTRICTED AREA", "RA": "RESERVED AREA",
                 "RM": "TEMP RESERVED AREA", "RR": "RESTRICTED AREA"}.get(n["code23"], "TEMP AIRSPACE")
        short = {"RD": "TDA", "RT": "RA(T)", "RA": "TRA", "RM": "TRA", "RR": "RA"}.get(n["code23"], "TEMP")
        items.append({
            "id": ident or short, "name": _place(n["text"]) or label.title(), "type": n["code23"][1],
            "temporary": True, "state": n["state"], "distance_nm": n["distance_nm"], "bearing": "",
            "upper": n.get("upper") or "", "lower": n.get("lower") or "",
            "start": n["next_start"], "end": n["next_end"], "notam": n["id"],
            "notam_activated": True, "label": label,
            "lower_fl": int(n["lower_fl"]) if str(n.get("lower_fl", "")).isdigit() else 0,
        })

    pinned_u = [p.upper().replace("EG", "", 1) if p.upper().startswith("EG") else p.upper() for p in pinned or []]
    chosen = [i for p in pinned_u for i in items if i["id"].upper() == p][:cards]
    rest = [i for i in items if i not in chosen]
    # Live activity close in jumps the queue; otherwise nearest first (stable signage).
    # Upper airspace (base FL195+) is irrelevant to most aerodrome users, so it ranks last.
    rest.sort(key=lambda i: (1 if i.get("lower_fl", 0) >= 195 else 0,
                             0 if i["state"] in ("active", "scheduled") and i["distance_nm"] <= warning_range_nm else 1,
                             i["distance_nm"]))
    while len(chosen) < cards and rest:
        chosen.append(rest.pop(0))

    warnings = [n for n in airspace_notams if n["code23"][:1] == "W" and n["distance_nm"] <= warning_range_nm]
    others = [i for i in rest]
    act_other = [i for i in others if i["state"] == "active"]
    sch_other = [i for i in others if i["state"] == "scheduled"]
    act_warn = [w for w in warnings if w["state"] == "active"]
    sch_warn = [w for w in warnings if w["state"] == "scheduled"]
    if act_other:
        summary_state = "hot"
    elif act_warn:
        summary_state = "warning"
    elif sch_other or sch_warn:
        summary_state = "scheduled"
    else:
        summary_state = "cold"
    return {
        "cards": chosen,
        "others": others,
        "warnings": [{
            "id": w["id"], "subject": w["subject"], "state": w["state"], "distance_nm": w["distance_nm"],
            "place": _place(w["text"]), "start": w["next_start"], "end": w["next_end"], "text": w["text"],
            "upper": w.get("upper"),
        } for w in warnings],
        "summary": {
            "state": summary_state,
            "active_areas": len(act_other), "scheduled_areas": len(sch_other),
            "active_warnings": len(act_warn), "scheduled_warnings": len(sch_warn),
        },
    }
