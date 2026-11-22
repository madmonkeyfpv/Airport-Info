# Airport-Info
Screens for local airport — live arrivals, departures, NOTAMs, latest activity, weather and local
restricted/danger airspace for **any UK airport** (choose by ICAO `EGBJ` or IATA `GLO`).
Runs as a **website** and as a **Home Assistant** dashboard (same board in both).

![TV display](docs/screenshots/tv_egbb.jpg)
![Weather station](docs/screenshots/weather_egsu.jpg)

Two screens: the **information board** (`/`) and the **weather station** (`/weather`: wind rose with the
airfield's runways, QNH/QFE, RVR, crosswind components). `/?view=rotate` alternates them.
A **radio strip** lists the airfield's frequencies with an open/closed estimate (from NOTAMs and optional
opening hours) and the current ATIS letter where a real text ATIS exists. Default airport: **EGSU Duxford**.

## Quick start
```bash
pip install -r server/requirements.txt
PYTHONPATH=server python -m airport_info.app
# open http://localhost:8080  ·  settings: http://localhost:8080/settings.html
```
or `docker compose up -d --build`.

**Home Assistant:** follow the step-by-step guide → [docs/SETUP_HOME_ASSISTANT.md](docs/SETUP_HOME_ASSISTANT.md)
(add-on with sidebar panel, TV/kiosk URLs, full-screen dashboard card, optional sensors).

## Data
- Flights: FlightAware airport board (web scrape)
- NOTAMs: NATS AIS PIB feed (free, official UK)
- Airspace: UK AIP ENR 5.1 areas (YAIXM dataset, scraped) + NOTAM activations
- Weather: METAR via aviationweather.gov

**Information only — not for operational use. Always check official sources before flight.**

Developer / AI handover notes: [CLAUDE.md](CLAUDE.md). Original KIMS design: [reference/](reference/).
