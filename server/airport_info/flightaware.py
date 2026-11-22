"""FlightAware airport board web scraper.

Scrapes https://www.flightaware.com/live/airport/<ICAO>, which carries four tables:
  arrivals   - recent arrivals (most recent first)
  departures - recent departures (most recent first; airborne ones carry a progress bar)
  enroute    - inbound: airborne (progress bar) and scheduled
  scheduled  - scheduled departures

Times on the board are shown in each airport's local zone with an abbreviation
(e.g. "05:52p GMT", "<i>08:05a CET</i>" where italics = estimate). The flight's
history URL (/history/YYYYMMDD/HHMMZ/ORIG/DEST) gives the UTC filed departure,
which anchors the date so we can produce full ISO timestamps.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

BASE = "https://www.flightaware.com/live/airport/"

TZ_OFFSETS = {
    "GMT": 0, "UTC": 0, "Z": 0, "WET": 0, "BST": 1, "IST": 1, "WEST": 1,
    "CET": 1, "CEST": 2, "EET": 2, "EEST": 3, "MSK": 3,
    "EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "MST": -7, "MDT": -6,
    "PST": -8, "PDT": -7, "AKST": -9, "AKDT": -8, "HST": -10,
    "AST": -4, "ADT": -3, "NST": -3.5, "NDT": -2.5,
}

# Matches "05:52p" (en-US) and "17:52" (en-GB) with an optional weekday prefix.
_TIME = re.compile(r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+)?(\d{1,2}):(\d{2})\s*([ap])?", re.I)
_HIST = re.compile(r"/history/(\d{4})(\d{2})(\d{2})/(\d{2})(\d{2})Z(?:/([A-Z0-9]{3,4}))?(?:/([A-Z0-9]{3,4}))?")


def _offset_hours(abbr: str) -> float | None:
    abbr = (abbr or "").strip().upper()
    if abbr in TZ_OFFSETS:
        return TZ_OFFSETS[abbr]
    m = re.fullmatch(r"([+-])(\d{1,2})(?::?(\d{2}))?", abbr)
    if m:
        h = int(m[2]) + (int(m[3]) / 60 if m[3] else 0)
        return h if m[1] == "+" else -h
    return None


def _cell_time(td, anchor: datetime | None, after: datetime | None = None, local_offset: float = 0.0):
    """Return (datetime_utc|None, estimated: bool, raw_text)."""
    if td is None:
        return None, False, ""
    raw = td.get_text(" ", strip=True).replace("\xa0", " ")
    m = _TIME.search(raw)
    if not m:
        return None, False, raw
    tz_el = td.find(class_="tz")
    offset = _offset_hours(tz_el.get_text(strip=True) if tz_el else "")
    if offset is None:
        offset = local_offset
    hour = int(m[1]) if not m[3] else int(m[1]) % 12 + (12 if m[3].lower() == "p" else 0)
    minute = int(m[2])
    estimated = td.find("i") is not None
    ref = after or anchor or datetime.now(timezone.utc)
    base = datetime(ref.year, ref.month, ref.day, hour, minute, tzinfo=timezone.utc) - timedelta(hours=offset)
    candidates = [base + timedelta(days=d) for d in (-1, 0, 1, 2)]
    if after is not None:
        later = [c for c in candidates if c >= after - timedelta(minutes=10)]
        dt = min(later) if later else min(candidates, key=lambda c: abs(c - after))
    else:
        dt = min(candidates, key=lambda c: abs(c - ref))
    return dt, estimated, raw


def _airport_cell(td) -> dict:
    if td is None:
        return {}
    hint = td.find(class_="hint")
    link = td.find("a", href=True)
    code = ""
    if link and "/live/airport/" in link["href"]:
        code = link["href"].rstrip("/").split("/")[-1].upper()
    label = link.get_text(strip=True) if link else ""
    name = hint.get_text(" ", strip=True) if hint else ""
    title = hint.get("title", "") if hint else ""
    if not code and not name:
        return {}
    return {"code": code, "label": label, "name": name, "title": title}


def _parse_table(table, kind: str, local_offset: float) -> list[dict]:
    flights = []
    if table is None:
        return flights
    for tr in table.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 6:
            continue
        ident_a = tds[0].find("a", href=True)
        if not ident_a:
            continue  # placeholder row
        ident = ident_a.get_text(strip=True)
        href = ident_a["href"]
        hist = _HIST.search(href)
        anchor = None
        if hist:
            anchor = datetime(int(hist[1]), int(hist[2]), int(hist[3]), int(hist[4]), int(hist[5]), tzinfo=timezone.utc)
        op_span = tds[0].find("span", title=True)
        operator = op_span["title"] if op_span else ""
        type_span = tds[1].find("span")
        type_a = tds[1].find("a")
        type_name = (type_span.get("title") or "").strip() if type_span else ""
        type_code = type_a.get_text(strip=True) if type_a else ""
        place = _airport_cell(tds[2])
        dep, dep_est, dep_raw = _cell_time(tds[3], anchor, local_offset=local_offset)
        fill = tds[4].find(class_="track-panel-progress-fill")
        progress = None
        if fill and fill.get("style"):
            pm = re.search(r"width:\s*(\d+)%", fill["style"])
            progress = int(pm[1]) if pm else None
        arr, arr_est, arr_raw = _cell_time(tds[5], anchor, after=dep or anchor, local_offset=local_offset)

        row_text = tr.get_text(" ", strip=True).upper()
        if "CANCEL" in row_text:
            status = "cancelled"
        elif kind == "enroute":
            status = "enroute" if progress is not None else "scheduled"
        elif kind == "scheduled":
            status = "scheduled"
        elif kind == "arrivals":
            status = "arrived"
        else:
            status = "airborne" if (progress is not None and progress < 100) else "departed"

        registration = ident if re.fullmatch(r"[A-Z0-9]{1,2}-[A-Z0-9]{3,5}|N\d[0-9A-Z]{1,4}", ident) else ""
        f = {
            "ident": ident,
            "registration": registration,
            "operator": "" if operator.lower().startswith("unknown owner") else operator,
            "type_code": type_code,
            "type_name": type_name,
            "departure_time": dep.isoformat() if dep else None,
            "departure_estimated": dep_est,
            "arrival_time": arr.isoformat() if arr else None,
            "arrival_estimated": arr_est,
            "progress": progress,
            "status": status,
            "url": "https://www.flightaware.com" + href,
        }
        if kind in ("arrivals", "enroute"):
            f["origin"] = place
            if hist and hist[6]:
                f["origin"].setdefault("code", hist[6])
        else:
            f["destination"] = place
            if hist and hist[7]:
                f["destination"].setdefault("code", hist[7])
        flights.append(f)
    return flights


def parse_board(html: str, local_offset: float = 0.0) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for kind in ("arrivals", "departures", "enroute", "scheduled"):
        out[kind] = _parse_table(soup.find("table", attrs={"data-type": kind}), kind, local_offset)
    return out


async def fetch_board(session, icao: str, local_offset: float = 0.0) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "en-GB,en;q=0.9",
    }
    async with session.get(BASE + icao.upper(), headers=headers) as resp:
        resp.raise_for_status()
        html = await resp.text()
    return parse_board(html, local_offset)
