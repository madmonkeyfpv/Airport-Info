# Airport-Info
Screens for local airport — live arrivals, departures, NOTAMs, latest activity, weather and local
restricted/danger airspace for **any UK airport** (choose by ICAO `EGBJ` or IATA `GLO`).
Runs as a **website** and as a **Home Assistant** dashboard (same board in both).

![TV display](docs/screenshots/tv_egbb.jpg)

## Quick start
```bash
pip install -r server/requirements.txt
PYTHONPATH=server python -m airport_info.app
# open http://localhost:8080  ·  settings: http://localhost:8080/settings.html
```
or `docker compose up -d --build`.

Home Assistant: see [homeassistant/README.md](homeassistant/README.md) (add-on, card resource, dashboard YAML).

## Data
- Flights: FlightAware airport board (web scrape)
- NOTAMs: NATS AIS PIB feed (free, official UK)
- Airspace: UK AIP ENR 5.1 areas (YAIXM dataset, scraped) + NOTAM activations
- Weather: METAR via aviationweather.gov

**Information only — not for operational use. Always check official sources before flight.**

Developer / AI handover notes: [CLAUDE.md](CLAUDE.md). Original KIMS design: [reference/](reference/).
