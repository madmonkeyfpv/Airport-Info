"""Build server/airport_info/data/uk_airports.json from OurAirports (public domain).

Usage: python3 tools/build_airports.py
Re-run occasionally to pick up new/renamed airfields.
"""
import csv, io, json, pathlib, urllib.request

SRC = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv"
COUNTRIES = {"GB", "IM", "JE", "GG"}
KEEP_TYPES = {"large_airport", "medium_airport", "small_airport", "heliport"}
OUT = pathlib.Path(__file__).resolve().parent.parent / "server/airport_info/data/uk_airports.json"


def main():
    raw = urllib.request.urlopen(SRC, timeout=60).read().decode("utf-8")
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
        })
    rows.sort(key=lambda a: (a["icao"] or "ZZZZ", a["iata"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, separators=(",", ":")))
    print(f"wrote {len(rows)} airports to {OUT}")


if __name__ == "__main__":
    main()
