"""Build server/airport_info/data/uk_airports.json from OurAirports (public domain).

Usage: python3 tools/build_airports.py
Re-run occasionally to pick up new/renamed airfields.
"""
import csv, io, json, math, pathlib, urllib.request

SRC = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv"
RWY_SRC = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/runways.csv"
COUNTRIES = {"GB", "IM", "JE", "GG"}
KEEP_TYPES = {"large_airport", "medium_airport", "small_airport", "heliport"}
OUT = pathlib.Path(__file__).resolve().parent.parent / "server/airport_info/data/uk_airports.json"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _bearing(lat1, lon1, lat2, lon2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def load_runways():
    raw = urllib.request.urlopen(RWY_SRC, timeout=60).read().decode("utf-8")
    out = {}
    for r in csv.DictReader(io.StringIO(raw)):
        if r["closed"] == "1" or not r["le_ident"]:
            continue
        la1, lo1, la2, lo2 = (_f(r[k]) for k in ("le_latitude_deg", "le_longitude_deg", "he_latitude_deg", "he_longitude_deg"))
        if None not in (la1, lo1, la2, lo2) and (la1, lo1) != (la2, lo2):
            hdg = _bearing(la1, lo1, la2, lo2)  # true heading from the threshold coordinates
        else:
            hdg = _f(r["le_heading_degT"])
            if hdg is None:
                digits = "".join(c for c in r["le_ident"] if c.isdigit())
                hdg = int(digits) * 10 if digits else None
        if hdg is None:
            continue
        out.setdefault(r["airport_ident"], []).append({
            "le": r["le_ident"], "he": r["he_ident"], "le_hdg": round(hdg, 1),
            "length_ft": int(_f(r["length_ft"]) or 0), "width_ft": int(_f(r["width_ft"]) or 0),
            "surface": r["surface"], "lighted": r["lighted"] == "1",
        })
    for lst in out.values():
        lst.sort(key=lambda x: -x["length_ft"])
    return out


def main():
    raw = urllib.request.urlopen(SRC, timeout=60).read().decode("utf-8")
    runways = load_runways()
    rows = []
    for r in csv.DictReader(io.StringIO(raw)):
        if r["iso_country"] not in COUNTRIES or r["type"] not in KEEP_TYPES:
            continue
        icao = (r.get("icao_code") or r.get("gps_code") or "").strip().upper()
        if not (len(icao) == 4 and icao.isalpha()):
            icao = r["ident"].upper() if len(r["ident"]) == 4 and r["ident"].isalpha() else ""
        iata = (r.get("iata_code") or "").strip().upper()
        if not icao and not iata:
            continue
        rows.append({
            "icao": icao, "iata": iata, "name": r["name"],
            "city": r["municipality"], "type": r["type"],
            "lat": round(float(r["latitude_deg"]), 5),
            "lon": round(float(r["longitude_deg"]), 5),
            "elev": int(float(r["elevation_ft"])) if r["elevation_ft"] else None,
            "runways": runways.get(r["ident"], []),
        })
    rows.sort(key=lambda a: (a["icao"] or "ZZZZ", a["iata"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, separators=(",", ":")))
    print(f"wrote {len(rows)} airports to {OUT}")


if __name__ == "__main__":
    main()
