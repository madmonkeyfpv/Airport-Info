"""Radio strip: published frequencies, estimated open/closed status, and text ATIS where it really exists.

* Frequencies: OurAirports airport-frequencies (built into uk_airports.json).
* Status is an ESTIMATE. There is no live feed of which UK frequency is staffed. It is derived from:
    1. aerodrome NOTAMs (AD CLSD, ATC CLSD, AFIS/A-G/ATIS not available, frequency U/S, hours changes),
    2. optional `service_hours` setting (published opening hours, UK local time),
  and is labelled as such on screen.
* ATIS letter: only from real text D-ATIS (scraped from atis.guru; exists for a handful of large UK
  airports). A letter is never inferred or invented. Old reports are flagged as possibly out of date.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .notams import _expand_weekday_ranges, activity

LONDON = ZoneInfo("Europe/London")
ATIS_URL = "https://atis.guru/atis/"

SERVICE_ORDER = ["atis", "afis", "ag", "twr", "app", "rdr", "dir", "gnd", "del", "other"]
SERVICE_LABEL = {"atis": "ATIS", "afis": "AFIS / INFO", "ag": "AIR / GROUND", "twr": "TOWER", "app": "APPROACH",
                 "rdr": "RADAR", "dir": "DIRECTOR", "gnd": "GROUND", "del": "DELIVERY", "other": "RADIO"}
ATC = {"twr", "app", "rdr", "dir", "gnd", "del"}


def classify_frequency(f: dict) -> str | None:
    t = f"{f.get('type', '')} {f.get('name', '')}".upper()
    if re.search(r"FIRE|EMR|RESCUE|RFFS", t):
        return None
    if "ATIS" in t:
        return "atis"
    if re.search(r"AFIS|INFO", t):
        return "afis"
    if re.search(r"A/G|RADIO|UNICOM|CTAF|AIR.?GROUND", t):
        return "ag"
    for key, pat in (("twr", r"TWR|TOWER"), ("app", r"APP|APPROACH|ZONE"), ("rdr", r"RDR|RADAR"),
                     ("dir", r"DIR|DIRECTOR"), ("gnd", r"GND|GROUND"), ("del", r"DEL|CLD|DELIVERY|CLNC")):
        if re.search(pat, t):
            return key
    return "other"


def group_frequencies(freqs: list[dict]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    generic = {"APP", "APPROACH", "TWR", "TOWER", "GND", "GROUND", "RDR", "RADAR", "DIR", "DIRECTOR", "DEL",
               "CLD", "DELIVERY", "ATIS", "AFIS", "INFO", "A/G", "RADIO", ""}
    for f in freqs:
        svc = classify_frequency(f)
        if not svc:
            continue
        name = f.get("name") or ""
        if name.upper().strip() in generic:
            name = SERVICE_LABEL[svc]
        key = (svc, re.sub(r"\s*\(.*?\)", "", name).upper())
        g = groups.setdefault(key, {"service": svc, "name": name, "freqs": []})
        if f["text"] not in g["freqs"]:
            g["freqs"].append(f["text"])
    out = sorted(groups.values(), key=lambda g: (SERVICE_ORDER.index(g["service"]), g["freqs"][0]))
    return out


# --- opening hours (local time) ------------------------------------------------------

def hours_windows(text: str, now: datetime, days: int = 8) -> list[tuple[datetime, datetime]] | None:
    """'0900-1700' or 'MON-FRI 0800-1800, SAT SUN 0900-1700' in UK local time -> UTC windows. None if unset/invalid."""
    text = (text or "").upper().strip()
    if not text:
        return None
    if text in ("H24", "24H", "24/7"):
        return [(now - timedelta(days=1), now + timedelta(days=days))]
    text = _expand_weekday_ranges(text)
    specs, current = [], set()
    for part in re.split(r"[,;]", text):
        names = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        wd_idx = {i for i, d in enumerate(names) if re.search(rf"\b{d}\b", part)}
        if wd_idx:
            current = wd_idx
        for a, b in re.findall(r"(\d{4})\s*-\s*(\d{4})", part):
            specs.append((set(current) if current else set(range(7)), a, b))
    if not specs:
        return None
    local_now = now.astimezone(LONDON)
    out = []
    for i in range(-1, days):
        d = (local_now + timedelta(days=i)).date()
        for wds, a, b in specs:
            if d.weekday() not in wds:
                continue
            s = datetime(d.year, d.month, d.day, int(a[:2]) % 24, int(a[2:]), tzinfo=LONDON)
            e = datetime(d.year, d.month, d.day, int(b[:2]) % 24, int(b[2:]), tzinfo=LONDON)
            if b in ("2400", "2359"):
                e = datetime(d.year, d.month, d.day, tzinfo=LONDON) + timedelta(days=1)
            if e <= s:
                e += timedelta(days=1)
            out.append((s.astimezone(timezone.utc), e.astimezone(timezone.utc)))
    return sorted(out)


# --- NOTAM effects --------------------------------------------------------------------

NOT_AVAIL = r"(?:CLSD|CLOSED|NOT AVBL|NOT AVAILABLE|UNAVBL|U/S|OUT OF SERVICE|WITHDRAWN|SUSPENDED|NOT PROVIDED)"
EFFECTS = [
    ("all", re.compile(rf"\b(?:AD|AERODROME|AIRFIELD)\s+{NOT_AVAIL}")),
    ("atc", re.compile(rf"\b(?:ATC|ATS|ATCU|AIR TRAFFIC CONTROL)\b[^.]{{0,40}}?{NOT_AVAIL}")),
    ("twr", re.compile(rf"\b(?:TWR|TOWER|ADC)\b[^.]{{0,30}}?{NOT_AVAIL}")),
    ("app", re.compile(rf"\b(?:APP|APPROACH|APC)\b[^.]{{0,30}}?{NOT_AVAIL}")),
    ("rdr", re.compile(rf"\b(?:RDR|RADAR|LARS)\b[^.]{{0,30}}?{NOT_AVAIL}")),
    ("afis", re.compile(rf"\bAFIS\b[^.]{{0,30}}?{NOT_AVAIL}")),
    ("ag", re.compile(rf"\b(?:A/G|AIR/GROUND|AIR-GROUND)\b[^.]{{0,30}}?{NOT_AVAIL}")),
    ("atis", re.compile(rf"\bATIS\b[^.]{{0,30}}?{NOT_AVAIL}")),
]
QCODE_SERVICE = {"ST": "twr", "SP": "app", "SA": "atis", "SF": "afis", "CA": "ag", "CR": "rdr", "CT": "rdr"}


def notam_effects(notam: dict) -> set[str]:
    """Which services an aerodrome NOTAM closes / withdraws."""
    text = " ".join(notam.get("text", "").upper().split())
    hits = {svc for svc, pat in EFFECTS if pat.search(text)}
    c23, c45 = notam.get("code23", ""), notam.get("code45", "")
    if c23 == "FA" and c45 == "LC":
        hits.add("all")
    if c23 in QCODE_SERVICE and c45 in ("LC", "AS", "AU", "AW", "CN"):
        hits.add(QCODE_SERVICE[c23])
    return hits


def _affects(group: dict, effects: set[str]) -> bool:
    svc = group["service"]
    if "all" in effects:
        return True
    if svc in effects:
        return True
    return "atc" in effects and svc in ATC


def _freq_mentioned(group: dict, text: str) -> bool:
    for f in group["freqs"]:
        if re.search(rf"\b{re.escape(f)}\d*\b[^.]{{0,30}}?{NOT_AVAIL}", text) or \
           re.search(rf"{NOT_AVAIL}[^.]{{0,20}}\b{re.escape(f)}", text):
            return True
    return False


def build_radio(airport: dict, raw_notams: list[dict], now: datetime, service_hours: str = "",
                datis: dict | None = None) -> dict:
    groups = group_frequencies(airport.get("frequencies") or [])
    icao = airport.get("icao")
    relevant = []
    seen = set()
    for n in raw_notams or []:
        if not icao or icao not in n["locations"] or n["type"] == "C" or n["id"] in seen:
            continue
        seen.add(n["id"])
        effects = notam_effects(n)
        text = " ".join(n["text"].upper().split())
        act = activity(n, now)
        if act["state"] == "expired":
            continue
        relevant.append((n, effects, text, act))

    windows = hours_windows(service_hours, now)
    for g in groups:
        status, until, note, notam_id = "published", None, "", None
        if windows is not None:
            cur = next((w for w in windows if w[0] <= now < w[1]), None)
            nxt = next((w for w in windows if w[0] > now), None)
            if cur:
                status, until = "open", cur[1]
            else:
                status, until = "closed", nxt[0] if nxt else None
        upcoming = None
        for n, effects, text, act in relevant:
            if not (_affects(g, effects) or _freq_mentioned(g, text)):
                continue
            if act["state"] == "active":
                status, until, notam_id = "closed", act["next_end"], n["id"]
                note = "NOTAM"
                break
            if act["state"] == "scheduled" and act["next_start"] and act["next_start"] - now < timedelta(hours=24):
                if upcoming is None or act["next_start"] < upcoming[0]:
                    upcoming = (act["next_start"], n["id"])
        if status != "closed" and upcoming:
            note, notam_id = "CLOSES", upcoming[1]
            until = upcoming[0] if status != "open" or not until or upcoming[0] < until else until
        if status == "published":
            # hours-changed NOTAMs (AH) for this service: flag so people check
            for n, effects, text, act in relevant:
                if n.get("code45") == "AH" and act["state"] == "active" and \
                        (QCODE_SERVICE.get(n.get("code23")) == g["service"] or n.get("code23") == "FA"):
                    status, note, notam_id = "limited", "HOURS CHANGED", n["id"]
                    break
        g.update({"status": status, "until": until.isoformat() if until else None, "note": note, "notam": notam_id})

    atis = None
    if datis and datis.get("reports"):
        atis = datis
    return {
        "groups": groups,
        "hours_configured": windows is not None,
        "service_hours": service_hours,
        "atis": atis,
        "has_atis_frequency": any(g["service"] == "atis" for g in groups),
    }


# --- D-ATIS scrape -----------------------------------------------------------------------

def parse_datis(html: str, now: datetime) -> dict | None:
    # atis.guru streams its content inside <template> elements (Blazor SSR); BeautifulSoup excludes
    # template text from get_text(), so unwrap them first.
    html = re.sub(r"</?template[^>]*>", "", html)
    soup = BeautifulSoup(html, "html.parser")
    reports = []
    for card in soup.select(".card-body"):
        title = card.find(class_="card-title")
        body = card.find(class_="atis")
        if not title or not body:
            continue
        kind = " ".join(title.get_text(" ", strip=True).split()).upper()
        if "ATIS" not in kind:
            continue  # METAR / TAF cards
        text = body.get_text("\n", strip=True)
        up = text.upper()
        m = re.search(r"\bATIS\s+([A-Z])\b", up) or re.search(r"\bINFORMATION\s+([A-Z])\b", up)
        if not m:
            continue
        sub = card.find(class_="card-subtitle")
        received = None
        if sub:
            tm = re.search(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})\s*UTC", sub.get_text())
            if tm:
                received = datetime(*map(int, tm.groups()), tzinfo=timezone.utc)
        age = (now - received).total_seconds() / 60 if received else None
        if age is not None and age > 180:
            continue  # too old to be meaningful
        rwy = re.search(r"\b(?:LANDING|DEPARTURE|DEP|ARR)?\s*(?:RWY|RUNWAY)\s+(?:IN USE\s+)?(\d{2}[LRC]?)", up)
        reports.append({
            "kind": "ARRIVAL" if "ARR" in kind else "DEPARTURE" if "DEP" in kind else "ATIS",
            "letter": m[1],
            "received": received.isoformat() if received else None,
            "age_min": round(age) if age is not None else None,
            "stale": age is None or age > 75,
            "runway": rwy[1] if rwy else None,
            "text": text,
        })
    return {"reports": reports, "source": "atis.guru (aircraft datalink D-ATIS)"} if reports else None


async def fetch_datis(session, icao: str) -> dict | None:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AirportInfoDisplay)"}
    async with session.get(ATIS_URL + icao.upper(), headers=headers) as r:
        if r.status != 200:
            return None
        html = await r.text()
    return parse_datis(html, datetime.now(timezone.utc))
