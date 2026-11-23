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


def test_rvr():
    from airport_info.weather import parse_rvr
    r = parse_rvr("METAR EGLL 230650Z 24004KT 0300 R27L/0550N R27R/P1500U R09/0400V0800D FG VV001 05/05 Q1020")
    assert [x["runway"] for x in r] == ["27L", "27R", "09"]
    assert r[0]["min_m"] == 550 and r[0]["tendency"] == "steady"
    assert r[1]["min_qual"] == "above" and r[1]["tendency"] == "up"
    assert r[2]["max_m"] == 800 and r[2]["tendency"] == "down"
    assert parse_rvr("METAR EGSS 222250Z AUTO 03006KT 9999 NCD 02/00 Q1019") == []


def test_datis_parse():
    from airport_info.radio import parse_datis
    html = (FX / "datis_EGLL.html").read_text()
    d = parse_datis(html, datetime(2026, 11, 22, 22, 0, tzinfo=timezone.utc))
    arr = d["reports"][0]
    assert arr["kind"] == "ARRIVAL" and arr["letter"] == "Q" and arr["runway"] == "09L" and not arr["stale"]
    assert len(d["reports"]) == 1  # departure report from 0942Z is > 3 h old and dropped
    assert parse_datis(html, datetime(2026, 11, 23, 6, 0, tzinfo=timezone.utc)) is None


def test_radio_status_from_notams_and_hours():
    from airport_info.radio import build_radio, hours_windows, notam_effects
    ns = parse_pib((FX / "pib_subset.xml").read_bytes())
    bb = airports.resolve("EGBB")
    # C6878/26: "ATC CLSD. AD CLSD" MON-FRI 2330-0600 -> active Tuesday 01:00Z, upcoming Monday afternoon
    tue = build_radio(bb, ns, datetime(2026, 11, 24, 1, 0, tzinfo=timezone.utc))
    assert all(g["status"] == "closed" and g["notam"] == "C6878/26" for g in tue["groups"] if g["service"] != "atis")
    mon = build_radio(bb, ns, datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc))
    twr = next(g for g in mon["groups"] if g["service"] == "twr")
    assert twr["note"] == "CLOSES" and twr["until"].startswith("2026-11-23T23:30")
    assert notam_effects({"text": "AFIS NOT AVBL. A/G AVBL ON 122.075", "code23": "XX", "code45": "XX"}) == {"afis"}
    su = airports.resolve("EGSU")
    r = build_radio(su, [], datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc), "0900-1700")
    assert r["groups"][0]["status"] == "open" and r["groups"][0]["freqs"] == ["122.075"]
    w = hours_windows("MON-FRI 0800-1800, SAT SUN 0900-1700", NOW)
    assert any(s.weekday() == 5 and s.hour == 9 for s, _ in w)  # Saturday 0900 local = 0900Z in winter


def test_seasonal_hours_duxford():
    from airport_info.radio import hours_windows
    h = "15MAR-15OCT 1000-1800; 16OCT-14MAR 1000-1600"
    w = hours_windows(h, NOW)  # 22 Nov -> winter, GMT
    nxt = [x for x in w if x[0] > NOW][0]
    assert nxt[0].isoformat() == "2026-11-23T10:00:00+00:00" and nxt[1].isoformat() == "2026-11-23T16:00:00+00:00"
    july = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
    s, e = [x for x in hours_windows(h, july) if x[0] > july][0]
    assert s.isoformat() == "2026-07-01T09:00:00+00:00" and e.isoformat() == "2026-07-01T17:00:00+00:00"  # BST


def test_settings_version_changes_on_save(tmp_path):
    from airport_info.settings import Settings
    s = Settings(tmp_path / "settings.json")
    v0 = s.version
    assert s.effective({})["airport"] == "EGSU"
    s.update({"airport": "glo"})
    assert s.version != v0 and s.values["airport"] == "GLO"
    assert Settings(tmp_path / "settings.json").version == s.version  # stable across restarts


def test_screen_links_from_supervisor():
    from airport_info.links import bases_from_supervisor
    self_info = {"network": {"8080/tcp": 8765}, "ip_address": "172.30.33.7"}
    network = {"interfaces": [
        {"interface": "end0", "enabled": True, "connected": True, "primary": True,
         "ipv4": {"address": ["192.168.1.50/24"]}},
        {"interface": "hassio", "enabled": True, "connected": True, "primary": False,
         "ipv4": {"address": ["172.30.32.1/23"]}},
        {"interface": "wlan0", "enabled": False, "ipv4": {"address": ["10.0.0.9/24"]}},
    ]}
    out = bases_from_supervisor(self_info, network, {"hostname": "homeassistant"})
    assert [b["base"] for b in out["bases"]] == ["http://192.168.1.50:8765", "http://homeassistant.local:8765"]
    assert out["port"] == 8765 and not out["direct_port_disabled"]
    off = bases_from_supervisor({"network": {"8080/tcp": None}}, network, None)
    assert off["direct_port_disabled"] and off["bases"] == []
