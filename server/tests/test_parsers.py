"""Offline tests for the scrapers/parsers using captured fixtures (22 Nov 2026)."""
import pathlib
from datetime import datetime, timezone

from airport_info import airports
from airport_info.airspace import AirspaceDB, build_panel
from airport_info.app import process_flights
from airport_info.flightaware import parse_board
from airport_info.geo import distance_nm, parse_dms
from airport_info.notams import aerodrome_notams, nearby_airspace_notams, parse_pib, schedule_windows

FX = pathlib.Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 22, 22, 45, tzinfo=timezone.utc)


def test_airport_lookup_icao_and_iata():
    assert airports.resolve("EGBJ")["iata"] == "GLO"
    assert airports.resolve("glo")["icao"] == "EGBJ"
    assert airports.resolve("LCY")["icao"] == "EGLC"
    assert airports.resolve("KIMS") is None  # UK only
    assert airports.search("glouc")[0]["icao"] == "EGBJ"


def test_dms():
    lat, lon = parse_dms("5230N00153W")
    assert abs(lat - 52.5) < 1e-6 and abs(lon + 1.8833) < 1e-3
    lat, lon = parse_dms("510029N 0023845W")
    assert 51.0 < lat < 51.01 and -2.65 < lon < -2.64
    assert 110 < distance_nm(51.89, -2.17, 50.0, -2.17) < 117


def test_flightaware_board_12h():
    b = parse_board((FX / "fa_EGBB_en-US.html").read_text())
    assert all(len(b[k]) == 20 for k in ("arrivals", "departures", "enroute", "scheduled"))
    f = b["enroute"][0]
    assert f["ident"] == "EAG3636" and f["origin"]["code"] == "EGAC" and f["progress"] == 99
    assert f["departure_time"] == "2026-11-22T17:05:00+00:00"
    assert f["arrival_time"] == "2026-11-22T18:02:00+00:00" and f["arrival_estimated"]
    # Cross-midnight arrival in another zone (+04) resolves to next day
    uae = next(x for x in b["departures"] if x["ident"] == "UAE38")
    assert uae["arrival_time"] == "2026-11-23T04:33:00+00:00"


def test_flightaware_ga_board():
    b = parse_board((FX / "fa_EGBJ_en-US.html").read_text())
    a = b["arrivals"][0]
    assert a["registration"] == "G-CNAX" and a["arrival_time"] == "2026-11-22T17:57:00+00:00"
    assert b["enroute"] == [] and b["scheduled"] == []
    p = process_flights(b, NOW)
    assert p["latest_arrival"]["ident"] == "G-CNAX"
    assert p["arrivals"] == []


def test_flightaware_24h_format():
    html = (FX / "fa_EGBJ_en-US.html").read_text().replace("05:52p", "17:52").replace("05:57p", "17:57")
    a = parse_board(html)["arrivals"][0]
    assert a["departure_time"] == "2026-11-22T17:52:00+00:00"


def test_stale_inbound_removed():
    b = parse_board((FX / "fa_EGBB_en-US.html").read_text())
    p = process_flights(b, NOW)
    assert all(f["arrival_time"] >= "2026-11-22T22:15" for f in p["arrivals"])


def test_notams():
    ns = parse_pib((FX / "pib_subset.xml").read_bytes())
    egbj = aerodrome_notams(ns, "EGBJ", NOW)
    titles = [n["title"] for n in egbj]
    assert "HOLDING POINT N2 — CLOSED" in titles
    assert len({n["id"] for n in egbj}) == len(egbj)  # de-duplicated
    egbb = aerodrome_notams(ns, "EGBB", NOW)
    closed = next(n for n in egbb if n["title"] == "AERODROME — CLOSED")
    assert closed["state"] == "scheduled" and closed["next_start"].startswith("2026-11-23T23:30")


def test_schedule_windows():
    n = {"start": datetime(2026, 11, 1, tzinfo=timezone.utc), "end": datetime(2026, 12, 1, tzinfo=timezone.utc),
         "schedule": "MON-FRI 0800-1600, SAT 1000-1200", "lat": 52, "lon": -2}
    w = [x for x in schedule_windows(n, NOW) if x[0] > NOW]  # NOW is a Sunday
    assert w[0][0].isoformat() == "2026-11-23T08:00:00+00:00"
    assert any(s.weekday() == 5 and s.hour == 10 for s, _ in w)
    n["schedule"] = "SR-SS"
    s, e = [x for x in schedule_windows(n, NOW) if x[0] > NOW][0]
    assert 7 <= s.hour <= 8 and 15 <= e.hour <= 17


def test_airspace_panel():
    ns = parse_pib((FX / "pib_subset.xml").read_bytes())
    db = AirspaceDB(pathlib.Path("/nonexistent"))
    db.load_local()
    ap = airports.resolve("EGBJ")
    static = db.nearby(ap["lat"], ap["lon"], 30)
    assert [a["id"] for a in static[:2]] == ["R105", "R155"]
    panel = build_panel(static, nearby_airspace_notams(ns, ap["lat"], ap["lon"], 30, NOW), [], 2, 10)
    assert [c["state"] for c in panel["cards"]] == ["permanent", "permanent"]
    pinned = build_panel(static, [], ["D216"], 2, 10)
    assert pinned["cards"][0]["id"] == "D216"
    lc = airports.resolve("EGLC")
    p2 = build_panel(db.nearby(lc["lat"], lc["lon"], 30), nearby_airspace_notams(ns, lc["lat"], lc["lon"], 30, NOW), [], 2, 10)
    assert p2["cards"][0]["id"] == "D180B" and p2["cards"][0]["state"] == "active"


def test_weather_derived_and_runways():
    from airport_info.weather import derived, _visibility, _sky
    d = derived(1019, 2, 0, 125)
    assert d["qfe"] == 1014 and d["qnh_inhg"] == 30.09
    assert -1600 <= d["density_alt_ft"] <= -1550 and d["humidity"] == 87
    assert _visibility("METAR EGSS 222250Z AUTO 03006KT 9999 NCD 02/00 Q1019", None) == "10 KM+"
    assert _visibility("METAR EGXX 222250Z 24010KT 200V280 4000 BR", None) == "4000 M"
    assert _sky({"clouds": [{"cover": "FEW", "base": 3500}, {"cover": "BKN", "base": 12000}]}, "X") == "FEW035 BKN120"
    egsu = airports.resolve("EGSU")
    assert {r["le"] for r in egsu["runways"]} == {"06", "06L"}
    assert 55 < egsu["runways"][0]["le_hdg"] < 65
