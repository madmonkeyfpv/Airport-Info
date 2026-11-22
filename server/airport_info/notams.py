"""UK NOTAMs from the free NATS AIS PIB XML feed.

Feed: https://pibs.nats.co.uk/operational/pibs/PIB.xml  (all UK NOTAM, refreshed by NATS
several times a day; ~2 MB). One download serves every airport, so it is cached globally.

Each NOTAM is decoded into a structured dict with an interpreted plain-English title
built from the ICAO Q-code (subject = Code23, condition = Code45), the raw Item E text,
validity, an optional daily schedule (Item D) expanded into concrete UTC windows, and
the Q-line position/radius (used for "nearby airspace" filtering).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

from .geo import distance_nm, parse_dms
from .sun import sun_times

PIB_URL = "https://pibs.nats.co.uk/operational/pibs/PIB.xml"

# --- Q-code decoding (subset relevant to aerodrome signage) -------------------------
SUBJECT = {
    "MR": "RUNWAY", "MS": "STOPWAY", "MT": "THRESHOLD", "MD": "DECLARED DISTANCES",
    "MX": "TAXIWAY", "MA": "MOVEMENT AREA", "MN": "APRON", "MP": "AIRCRAFT STANDS",
    "MK": "PARKING AREA", "MW": "RUNWAY STRENGTH", "MY": "RAPID EXIT TAXIWAY",
    "LA": "APPROACH LIGHTING", "LB": "AERODROME BEACON", "LC": "RWY CENTRELINE LIGHTS",
    "LE": "RUNWAY EDGE LIGHTS", "LH": "HIGH INTENSITY RWY LIGHTS", "LI": "RWY END ID LIGHTS",
    "LL": "LOW INTENSITY RWY LIGHTS", "LP": "PAPI", "LR": "RUNWAY LIGHTING",
    "LT": "THRESHOLD LIGHTS", "LX": "TAXIWAY CENTRELINE LIGHTS", "LY": "TAXIWAY EDGE LIGHTS",
    "LW": "HELIPORT LIGHTING", "LG": "LIGHTING", "LJ": "RUNWAY ALIGNMENT LIGHTS",
    "LV": "VASIS", "LZ": "TDZ LIGHTS", "LF": "SEQUENCED FLASHING LIGHTS",
    "FA": "AERODROME", "FU": "FUEL", "FF": "FIRE AND RESCUE", "FH": "HELICOPTER LANDING AREA",
    "FM": "MET SERVICE", "FP": "HELIPORT", "FS": "SNOW REMOVAL", "FT": "TRANSMISSOMETER",
    "FW": "WIND INDICATOR", "FZ": "CUSTOMS",
    "IC": "ILS", "ID": "ILS DME", "IG": "GLIDE PATH", "II": "INNER MARKER", "IL": "LOCALIZER",
    "IM": "MIDDLE MARKER", "IO": "OUTER MARKER", "IS": "ILS CAT I", "IT": "ILS CAT II",
    "IU": "ILS CAT III", "IW": "MLS", "IX": "LOCATOR", "IY": "MIDDLE LOCATOR",
    "NA": "ALL NAVAIDS", "NB": "NDB", "NC": "DECCA", "ND": "DME", "NF": "FAN MARKER",
    "NL": "LOCATOR", "NM": "VOR/DME", "NN": "TACAN", "NO": "OMEGA", "NT": "VORTAC",
    "NV": "VOR", "NX": "DIRECTION FINDER",
    "CA": "AIR/GROUND FACILITY", "CE": "EN-ROUTE RADAR", "CG": "GCA", "CL": "SELCAL",
    "CM": "SURFACE MOVEMENT RADAR", "CP": "PAR", "CR": "SURVEILLANCE RADAR", "CS": "SSR",
    "CT": "TERMINAL AREA RADAR",
    "SA": "ATIS", "SB": "ATS REPORTING OFFICE", "SC": "AREA CONTROL", "SE": "FIS",
    "SF": "AFIS", "SL": "FLOW CONTROL", "SO": "OCEANIC CONTROL", "SP": "APPROACH CONTROL",
    "SS": "FLIGHT SERVICE STATION", "ST": "AERODROME CONTROL TOWER", "SU": "UPPER AREA CONTROL",
    "SV": "VOLMET", "SY": "UPPER ADVISORY",
    "PA": "STAR", "PB": "STANDARD VFR ARRIVAL", "PD": "SID", "PE": "STANDARD VFR DEPARTURE",
    "PH": "HOLDING PROCEDURE", "PI": "INSTRUMENT APPROACH", "PK": "VFR APPROACH",
    "PU": "MISSED APPROACH", "PT": "TRANSITION ALTITUDE", "PF": "FLOW PROCEDURE",
    "PL": "OBSTACLE CLEARANCE LIMIT", "PM": "AERODROME OPERATING MINIMA", "PN": "NOISE ABATEMENT",
    "PO": "OBSTACLE CLEARANCE ALTITUDE", "PX": "MINIMUM HOLDING ALTITUDE", "PZ": "ADIZ PROCEDURE",
    "OB": "OBSTACLE", "OL": "OBSTACLE LIGHTS", "OA": "AIS", "OE": "AIRCRAFT ENTRY REQUIREMENTS",
    "AA": "MINIMUM ALTITUDE", "AC": "CONTROL ZONE", "AD": "ADIZ", "AE": "CONTROL AREA",
    "AF": "FIR", "AH": "UPPER CONTROL AREA", "AL": "MINIMUM USABLE FL", "AN": "AREA NAV ROUTE",
    "AO": "OCEANIC CONTROL AREA", "AP": "REPORTING POINT", "AR": "ATS ROUTE", "AT": "TMA",
    "AU": "UIR", "AV": "UPPER ADVISORY AREA", "AX": "INTERSECTION", "AZ": "ATZ",
    "RA": "AIRSPACE RESERVATION", "RD": "DANGER AREA", "RM": "MILITARY OPERATING AREA",
    "RO": "OVERFLYING", "RP": "PROHIBITED AREA", "RR": "RESTRICTED AREA", "RT": "TEMPORARY RESTRICTED AREA",
    "WA": "AIR DISPLAY", "WB": "AEROBATICS", "WC": "CAPTIVE BALLOON / KITE", "WD": "DEMOLITION OF EXPLOSIVES",
    "WE": "EXERCISES", "WF": "AIR REFUELLING", "WG": "GLIDER FLYING", "WH": "BLASTING",
    "WJ": "BANNER / TARGET TOWING", "WL": "ASCENT OF FREE BALLOON", "WM": "MISSILE / GUN / ROCKET FIRING",
    "WP": "PARACHUTE / PARAGLIDING", "WR": "RADIOACTIVE MATERIALS", "WS": "BURNING OR BLOWING GAS",
    "WT": "MASS MOVEMENT OF AIRCRAFT", "WU": "UNMANNED AIRCRAFT", "WV": "FORMATION FLIGHT",
    "WW": "SIGNIFICANT VOLCANIC ACTIVITY", "WY": "AERIAL SURVEY", "WZ": "MODEL FLYING",
    "GA": "GNSS AIRFIELD-SPECIFIC", "GW": "GNSS AREA-WIDE",
}
CONDITION = {
    "AC": "WITHDRAWN FOR MAINTENANCE", "AD": "AVAILABLE FOR DAYLIGHT OPERATION",
    "AF": "FLIGHT CHECKED AND RELIABLE", "AG": "OPERATING BUT GROUND CHECKED ONLY",
    "AH": "HOURS OF SERVICE CHANGED", "AK": "RESUMED NORMAL OPERATION", "AL": "OPERATIVE (SUBJECT TO LIMITATIONS)",
    "AM": "MILITARY OPERATIONS ONLY", "AN": "AVAILABLE FOR NIGHT OPERATION", "AO": "OPERATIONAL",
    "AP": "PRIOR PERMISSION REQUIRED", "AR": "AVAILABLE ON REQUEST", "AS": "UNSERVICEABLE",
    "AU": "NOT AVAILABLE", "AW": "COMPLETELY WITHDRAWN", "AX": "PREVIOUSLY PROMULGATED SHUTDOWN CANCELLED",
    "CA": "ACTIVATED", "CC": "COMPLETED", "CD": "DEACTIVATED", "CE": "ERECTED", "CF": "FREQUENCY CHANGED",
    "CG": "DOWNGRADED", "CH": "CHANGED", "CI": "IDENTIFICATION CHANGED", "CL": "REALIGNED",
    "CM": "DISPLACED", "CN": "CANCELLED", "CO": "OPERATING", "CP": "REDUCED POWER",
    "CR": "TEMPORARILY REPLACED", "CS": "INSTALLED", "CT": "ON TEST, DO NOT USE",
    "HA": "BRAKING ACTION", "HB": "FRICTION COEFFICIENT", "HC": "COVERED BY COMPACTED SNOW",
    "HD": "COVERED BY DRY SNOW", "HE": "COVERED BY WATER", "HF": "FREE OF SNOW AND ICE",
    "HG": "GRASS CUTTING IN PROGRESS", "HH": "HAZARD", "HI": "COVERED BY ICE", "HJ": "LAUNCH PLANNED",
    "HK": "BIRD MIGRATION", "HL": "SNOW CLEARANCE COMPLETED", "HM": "MARKED", "HN": "COVERED BY WET SNOW",
    "HO": "OBSCURED BY SNOW", "HP": "SNOW CLEARANCE IN PROGRESS", "HQ": "OPERATION CANCELLED",
    "HR": "STANDING WATER", "HS": "SANDING IN PROGRESS", "HT": "APPROACH ACCORDING TO SIGNAL AREA ONLY",
    "HU": "LAUNCH IN PROGRESS", "HV": "WORK COMPLETED", "HW": "WORK IN PROGRESS",
    "HX": "CONCENTRATION OF BIRDS", "HY": "SNOW BANKS EXIST", "HZ": "COVERED BY FROZEN RUTS",
    "LA": "OPERATING ON AUXILIARY POWER", "LB": "RESERVED FOR BASED AIRCRAFT", "LC": "CLOSED",
    "LD": "UNSAFE", "LE": "OPERATING WITHOUT AUXILIARY POWER", "LF": "INTERFERENCE",
    "LG": "OPERATING WITHOUT IDENTIFICATION", "LH": "UNSERVICEABLE FOR HEAVY AIRCRAFT",
    "LI": "CLOSED TO IFR", "LK": "OPERATING AS FIXED LIGHT", "LL": "USABLE FOR LIMITED LENGTH",
    "LN": "CLOSED TO NIGHT OPERATIONS", "LP": "PROHIBITED", "LR": "RESTRICTED TO RUNWAYS AND TAXIWAYS",
    "LS": "SUBJECT TO INTERRUPTION", "LT": "LIMITED", "LV": "CLOSED TO VFR", "LW": "WILL TAKE PLACE",
    "LX": "CAUTION ADVISED",
    "XX": "",
    "TT": "TRIGGER NOTAM",
}

OUT_OF_SERVICE = re.compile(r"\bU/S\b|OUT OF SERVICE|UNSERVICEABLE|\bUNAVBL\b|NOT AVBL|UNAVAILABLE")

MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
WEEKDAYS = {d: i for i, d in enumerate(["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"])}


def _ts(raw: str | None) -> datetime | None:
    raw = (raw or "").strip()
    m = re.match(r"^(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", raw)
    if not m:
        return None
    try:
        return datetime(2000 + int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_pib(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    out = []
    for n in root.iter("Notam"):
        q = n.find("QLine")
        t = lambda tag, el=n: (el.findtext(tag) or "").strip() if el is not None else ""
        pos = parse_dms(t("Coordinates"))
        series, number, year = t("Series"), t("Number"), t("Year")
        end_raw = t("EndValidity")
        out.append({
            "id": f"{series}{number.zfill(4)}/{year}",
            "type": t("Type"),
            "section": n.get("PIBSection"),
            "fir": t("FIR", q),
            "code23": t("Code23", q),
            "code45": t("Code45", q),
            "purpose": t("Purpose", q),
            "scope": t("Scope", q),
            "lower_fl": t("Lower", q),
            "upper_fl": t("Upper", q),
            "lat": pos[0] if pos else None,
            "lon": pos[1] if pos else None,
            "radius_nm": float(t("Radius") or 0) if t("Radius").isdigit() else 0,
            "locations": t("ItemA").split(),
            "start": _ts(t("StartValidity")),
            "end": _ts(end_raw),
            "end_estimated": "EST" in end_raw.upper(),
            "permanent": "PERM" in end_raw.upper(),
            "schedule": t("ItemD"),
            "text": t("ItemE"),
            "lower": t("ItemF"),
            "upper": t("ItemG"),
        })
    return out


# --- Item D schedule expansion -------------------------------------------------------

def _expand_weekday_ranges(text: str) -> str:
    def rep(m):
        a, b = WEEKDAYS[m[1]], WEEKDAYS[m[2]]
        days = [(a + i) % 7 for i in range(((b - a) % 7) + 1)]
        inv = {v: k for k, v in WEEKDAYS.items()}
        return " ".join(inv[d] for d in days)
    return re.sub(r"\b(MON|TUE|WED|THU|FRI|SAT|SUN)\s*-\s*(MON|TUE|WED|THU|FRI|SAT|SUN)\b", rep, text)


def schedule_windows(notam: dict, now: datetime, horizon_days: int = 8) -> list[tuple[datetime, datetime]] | None:
    """Expand Item D into UTC windows. Returns None when no usable schedule (whole validity applies)."""
    start, end = notam.get("start"), notam.get("end")
    text = (notam.get("schedule") or "").upper()
    if not text or not start or "H24" in text:
        return None
    text = re.sub(r"\bSR\s*-\s*SS\b", "SRSS", text)
    if re.search(r"\bSR\b|\bSS\b", text):  # offsets like SR-30 etc. not supported
        return None
    text = _expand_weekday_ranges(text.replace(",", " , "))
    text = re.sub(r"\b(\d{4})\s+-\s+(\d{4})\b", r"\1-\2", text)
    tokens = re.findall(r"\d{4}-\d{4}|SRSS|\d{2}-\d{2}|\d{2}|[A-Z]{3,5}|,", text)
    specs, month, days, weekdays, daily = [], None, set(), set(), False
    last_was_time = False
    for tok in tokens:
        if re.fullmatch(r"\d{4}-\d{4}", tok) or tok == "SRSS":
            specs.append((month, set(days), set(weekdays), daily,
                          *(("SR", "SS") if tok == "SRSS" else (tok[:4], tok[5:]))))
            last_was_time = True
            continue
        if last_was_time and tok != ",":
            days, weekdays, daily = set(), set(), False
        last_was_time = False
        if tok in MONTHS:
            month = MONTHS[tok]
        elif tok in WEEKDAYS:
            weekdays.add(WEEKDAYS[tok])
        elif tok == "DAILY":
            daily = True
        elif re.fullmatch(r"\d{2}-\d{2}", tok):
            a, b = int(tok[:2]), int(tok[3:])
            days.update(range(a, b + 1) if b >= a else list(range(a, 32)) + list(range(1, b + 1)))
        elif re.fullmatch(r"\d{2}", tok):
            days.add(int(tok))
    if not specs:
        return None
    limit = min(end or now + timedelta(days=horizon_days), now + timedelta(days=horizon_days))
    windows = []
    d: date = max(start, now - timedelta(days=1)).date()
    while datetime(d.year, d.month, d.day, tzinfo=timezone.utc) <= limit:
        for (mon, ds, wds, _daily, t1, t2) in specs:
            if ds and (d.day not in ds or (mon and d.month != mon)):
                continue
            if not ds and wds and d.weekday() not in wds:
                continue
            if t1 == "SR":
                if notam.get("lat") is None:
                    return None
                ws, we = sun_times(notam["lat"], notam["lon"], d)
            else:
                ws = datetime(d.year, d.month, d.day, int(t1[:2]) % 24, int(t1[2:]), tzinfo=timezone.utc)
                we = datetime(d.year, d.month, d.day, int(t2[:2]) % 24, int(t2[2:]), tzinfo=timezone.utc)
            if t2 in ("2400", "2359"):
                we = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(days=1)
            if we <= ws:
                we += timedelta(days=1)
            ws, we = max(ws, start), min(we, end) if end else we
            if we > ws:
                windows.append((ws, we))
        d += timedelta(days=1)
    return sorted(windows)


def activity(notam: dict, now: datetime) -> dict:
    """Return {'state': active|scheduled|expired, 'next_start', 'next_end'} for a NOTAM."""
    start, end = notam.get("start"), notam.get("end")
    if end and end < now:
        return {"state": "expired", "next_start": None, "next_end": None}
    wins = schedule_windows(notam, now)
    if wins is None:
        wins = [(start or now, end or now + timedelta(days=3650))]
    for ws, we in wins:
        if ws <= now < we:
            return {"state": "active", "next_start": ws, "next_end": we}
    upcoming = [w for w in wins if w[0] > now]
    if upcoming:
        return {"state": "scheduled", "next_start": upcoming[0][0], "next_end": upcoming[0][1]}
    return {"state": "expired", "next_start": None, "next_end": None}


# --- Aerodrome NOTAM interpretation --------------------------------------------------

def _where(text: str) -> str:
    rwy = re.search(r"\bRWY\s*(\d{2}[LRC]?(?:/\d{2}[LRC]?)?)\b", text)
    if rwy:
        return "RWY " + rwy[1]
    twy = re.search(r"\bTWY\s*([A-Z]{1,2}\d{0,2})\b", text)
    if twy:
        return "TWY " + twy[1]
    return ""


def classify(n: dict) -> str:
    c, t = n["code23"], n["text"].upper()
    if c[:1] == "O" and c in ("OB", "OL") or t.startswith("OBST"):
        return "obstacle"
    if re.search(r"SNOWTAM|RWYCC|BRAKING ACTION|\bGRF\b", t):
        return "surface"
    if c == "FU" or re.search(r"\b(?:100LL|JET[ -]?A1?|AVGAS|MOGAS|FUEL)\b", t):
        return "fuel"
    if c[:1] == "L":
        return "lighting"
    if c[:1] in ("I", "N", "G") or re.search(r"\b(?:ILS|LOC|VOR|NDB|DME|RNP)\b", t):
        return "navaid"
    if n["code45"] in ("LC",) or re.search(r"\b(?:CLSD|CLOSED)\b", t):
        return "closure"
    if c[:1] in ("R", "W"):
        return "airspace"
    if c[:1] in ("M",) and n["code45"] in ("HW",):
        return "works"
    if c[:1] in ("S", "C", "F") and n["code45"] in ("AH", "LT"):
        return "hours"
    return "general"


PRIORITY = {"closure": 0, "surface": 1, "fuel": 2, "lighting": 3, "navaid": 4, "works": 5,
            "hours": 6, "airspace": 7, "general": 8, "obstacle": 9}


def _keyword_condition(t: str) -> str:
    if re.search(r"\b(?:CLSD|CLOSED)\b", t):
        return "CLOSED"
    if OUT_OF_SERVICE.search(t):
        return "OUT OF SERVICE"
    if re.search(r"\bWIP\b|WORK IN PROGRESS", t):
        return "WORK IN PROGRESS"
    if re.search(r"\bNOT ACPT\b|NOT ACCEPTED", t):
        return "RESTRICTED"
    if re.search(r"\bPPR\b", t):
        return "PPR"
    return ""


def title_for(n: dict, kind: str) -> str:
    t = n["text"].upper()
    subject = SUBJECT.get(n["code23"], "")
    cond = CONDITION.get(n["code45"], "") or _keyword_condition(t)
    where = _where(t)
    if re.search(r"\bAD CLSD\b|AERODROME CLOSED", t):
        return "AERODROME — CLOSED"
    if kind == "closure":
        hp = re.search(r"\bHOLDING POINT\s+([A-Z]\d{0,2})\b", t)
        return f"{where or ('HOLDING POINT ' + hp[1] if hp else subject or 'AERODROME')} — CLOSED"
    if kind == "fuel":
        grade = "100LL" if re.search(r"100LL|AVGAS", t) else "JET A1" if re.search(r"JET[ -]?A", t) else "FUEL"
        return f"{grade} — {'UNAVAILABLE' if OUT_OF_SERVICE.search(t) or n['code45'] in ('AU', 'AS') else 'NOTICE'}"
    if kind == "lighting":
        light = next((k for k in ("PAPI", "APAPI", "ALS", "MALSR", "REIL", "HIRL", "MIRL", "ABN") if re.search(rf"\b{k}\b", t)), subject or "LIGHTING")
        state = "OUT OF SERVICE" if OUT_OF_SERVICE.search(t) or n["code45"] == "AS" else (cond or "NOTICE")
        return f"{where + ' — ' if where else ''}{light} {state}".strip()
    if kind == "navaid":
        aid = next((k for k in ("ILS", "LOC", "GP", "DME", "VOR", "NDB", "RNP") if re.search(rf"\b{k}\b", t)), subject or "NAVAID")
        state = "OUT OF SERVICE" if OUT_OF_SERVICE.search(t) or n["code45"] == "AS" else (cond or "NOTICE")
        return f"{where + ' — ' if where and where.startswith('RWY') else ''}{aid} {state}".strip()
    if kind == "hours":
        return f"{subject or 'AERODROME'} — HOURS CHANGED" if n["code45"] == "AH" else f"{subject} — {cond}".strip(" —")
    head = where if where and subject in ("RUNWAY", "TAXIWAY", "") else \
        (f"{where} {subject}" if where else subject or "AERODROME")
    return f"{head} — {cond or 'NOTICE'}"


RWYCC_NAMES = {6: "DRY", 5: "GOOD", 4: "GOOD–MEDIUM", 3: "MEDIUM", 2: "MEDIUM–POOR", 1: "POOR", 0: "LESS THAN POOR"}


def surface_condition(text: str) -> dict | None:
    t = text.upper()
    m = re.search(r"\bRWYCC\s*([0-6])\s*/\s*([0-6])\s*/\s*([0-6])\b", t) or \
        re.search(r"\b([0-6])/([0-6])/([0-6])\s+(?:\d{2,3}/\d{2,3}/\d{2,3}|NR|DRY|WET)", t)
    if not m:
        return None
    codes = [int(m[i]) for i in (1, 2, 3)]
    return {"rwycc": codes, "names": [RWYCC_NAMES[c] for c in codes]}


def interpret(n: dict, now: datetime) -> dict:
    kind = classify(n)
    act = activity(n, now)
    return {
        "id": n["id"],
        "kind": kind,
        "title": title_for(n, kind),
        "text": n["text"],
        "start": n["start"].isoformat() if n["start"] else None,
        "end": n["end"].isoformat() if n["end"] else None,
        "end_estimated": n["end_estimated"],
        "permanent": n["permanent"],
        "schedule": n["schedule"],
        "state": act["state"],
        "next_start": act["next_start"].isoformat() if act["next_start"] else None,
        "next_end": act["next_end"].isoformat() if act["next_end"] else None,
        "surface": surface_condition(n["text"]) if kind == "surface" else None,
        "lower": n["lower"], "upper": n["upper"],
        "qcode": f"Q{n['code23']}{n['code45']}",
        "priority": PRIORITY.get(kind, 8),
    }


def aerodrome_notams(all_notams: list[dict], icao: str, now: datetime, include_obstacles: bool = False,
                     include_airspace: bool = False, upcoming_days: int = 7) -> list[dict]:
    out, seen = [], set()
    for n in all_notams:
        if icao not in n["locations"] or n["type"] == "C" or n["id"] in seen:
            continue
        seen.add(n["id"])
        item = interpret(n, now)
        if item["state"] == "expired":
            continue
        if item["state"] == "scheduled" and item["next_start"] and \
                datetime.fromisoformat(item["next_start"]) > now + timedelta(days=upcoming_days):
            continue
        if item["kind"] == "obstacle" and not include_obstacles:
            continue
        if item["kind"] == "airspace" and not include_airspace:
            continue
        out.append(item)
    out.sort(key=lambda i: (i["state"] != "active", i["priority"], i["start"] or ""))
    return out


def nearby_airspace_notams(all_notams: list[dict], lat: float, lon: float, range_nm: float,
                           now: datetime) -> list[dict]:
    """R* (restricted/danger/TRA) and W* (warnings) NOTAMs whose Q-circle comes within range_nm."""
    out, seen = [], set()
    for n in all_notams:
        if n["code23"][:1] not in ("R", "W") or n["lat"] is None or n["type"] == "C" or n["id"] in seen:
            continue
        seen.add(n["id"])
        if n["radius_nm"] >= 100:  # FIR-wide / global advisories
            continue
        d = distance_nm(lat, lon, n["lat"], n["lon"])
        edge = max(0.0, d - n["radius_nm"])
        if edge > range_nm:
            continue
        act = activity(n, now)
        if act["state"] == "expired":
            continue
        if n["code45"] in ("TT",):  # trigger NOTAMs point at AIP SUPs; not an activation
            continue
        ids = sorted(set(m.group(1) + m.group(2) + (m.group(3) or "")
                         for m in re.finditer(r"\bEG\s?([DRP])\s?(\d{3})([A-Z])?\b", n["text"].upper())))
        out.append({**{k: v for k, v in n.items() if k not in ("start", "end")},
                    "start": n["start"].isoformat() if n["start"] else None,
                    "end": n["end"].isoformat() if n["end"] else None,
                    "state": act["state"],
                    "next_start": act["next_start"].isoformat() if act["next_start"] else None,
                    "next_end": act["next_end"].isoformat() if act["next_end"] else None,
                    "distance_nm": round(edge, 1),
                    "area_ids": ids,
                    "subject": SUBJECT.get(n["code23"], "AIRSPACE"),
                    "condition": CONDITION.get(n["code45"], "")})
    out.sort(key=lambda a: (a["state"] != "active", a["distance_nm"]))
    return out
