# CLAUDE.md — Airport Info (handover file)

**Read this first.** This file is the single source of truth for moving work between Claude Code
cloud sessions and the desktop app. Update the *Status / changelog* and *Next steps* sections at the
end of every working session so the next session can continue without re-discovery.

## What this project is
Information screens for a small UK airport (wall TVs in the terminal/clubhouse), originally a
Home Assistant `custom:button-card` kiosk for KIMS (Madison, Indiana, USA). Rebuilt so **any UK
airport** can be chosen by **ICAO (4-letter, e.g. EGBJ) or IATA (3-letter, e.g. GLO)** in settings,
and so the same board works both **inside Home Assistant** and as a **public website**.

Owner's requirements (verbatim intent):
- Originals (`reference/`) must **never be overwritten** — they are the design reference.
- Flight data: **FlightAware web scraper**. Restricted airspace: **web scraper**.
- NOTAMs: free UK API (owner called it "NOTAC"; implemented with the free **NATS AIS PIB XML feed**,
  which is the official free UK NOTAM feed — confirm with owner if "NOTAC" meant something else).
- Identical functionality to the original at any UK airport; professional look; creative licence OK.
- Owner does not need to approve merges; only ask critical questions.

## Layout
```
reference/                 ORIGINAL uploads (KIMS yaml + photos). READ-ONLY. Do not edit/move.
server/airport_info/       Python aiohttp backend (API + static site)
  app.py                   HTTP server, TTL cache, flight post-processing, /api/* routes
  flightaware.py           FlightAware airport-board scraper (4 tables) -> flight dicts
  notams.py                NATS PIB parser, Q-code decoder, Item D schedule expansion, interpretation
  airspace.py              UK D/R/P areas (YAIXM dataset) + NOTAM activation -> panel cards/summary
  weather.py               METAR (aviationweather.gov); falls back to nearest fresh METAR
  airports.py              UK airport lookup (ICAO/IATA/name search)
  settings.py              JSON-persisted settings (DEFAULTS documents every key)
  geo.py, sun.py           distance/DMS/polygon helpers; sunrise/sunset for SR-SS NOTAMs
  data/uk_airports.json    built by tools/build_airports.py (OurAirports, GB/IM/JE/GG)
  data/uk_airspace.yaml    bundled YAIXM snapshot (fallback; live copy refreshed daily to DATA_DIR)
server/tests/              pytest, offline fixtures captured 22 Nov 2026 (FA html, PIB subset)
web/board.js               SHARED renderer: renderBoard(data) + BOARD_CSS (+ tickClocks, autoScroll)
web/index.html             website / kiosk page (uses board.js)
web/settings.html          settings UI (airport autocomplete, units, airspace pins, theme)
web/card/airport-info-card.js  Home Assistant Lovelace card (imports ../board.js -> identical board)
homeassistant/             dashboard YAML, optional REST-sensor package, HA setup README
airport_info_addon/        Home Assistant add-on (repository.yaml at repo root makes repo an add-on repo)
Dockerfile, docker-compose.yml   website/server container
docs/screenshots/          rendered screenshots of the prototype (TV, phone, HA card, settings)
tools/build_airports.py    regenerate the UK airport DB
```

## Run / test
```bash
pip install -r server/requirements.txt        # aiohttp, PyYAML, beautifulsoup4
PYTHONPATH=server python -m airport_info.app   # http://localhost:8080  (PORT, DATA_DIR, WEB_DIR, ADMIN_TOKEN env)
pytest -q                                      # offline tests (pytest.ini sets pythonpath)
docker compose up -d --build                   # container on :8080, settings persisted in ./data
```
Display URLs: `/` (board), `/?airport=EGLC&theme=midnight&kiosk` (per-screen overrides, kiosk hides gear),
`/settings.html`, `/api/data?airport=GLO`, `/api/airports?q=glou`, `/card/airport-info-card.js`.
Screenshots: Playwright is preinstalled in cloud sessions (`require('playwright')`, `chromium.launch()`).

## Data sources & how they're used
| Panel | Source | Notes |
|---|---|---|
| Arrivals / departures / latest activity | Scrape `flightaware.com/live/airport/<ICAO>` | Tables `data-type=arrivals|departures|enroute|scheduled`. Times are local with tz abbr; **format depends on Accept-Language** (en-GB → `17:52`, en-US → `05:52p`) — parser handles both. History URL `/history/YYYYMMDD/HHMMZ/ORIG/DEST` anchors the date. Italic = estimate. Progress bar = airborne. Stale inbound (ETA > 30 min past) dropped. Cache 120 s. |
| NOTAMs | `https://pibs.nats.co.uk/operational/pibs/PIB.xml` (~2 MB, all UK) | Cached 15 min globally. Aerodrome NOTAMs = ItemA contains ICAO. Obstacles and airspace/warning NOTAMs hidden by default (settings). Titles built from Q-code (Code23 subject / Code45 condition) + keywords. Item D schedules (e.g. `MON-FRI 0800-1600`, `SR-SS`, date lists) expanded to UTC windows → ACTIVE / UPCOMING. RWYCC triplets rendered as thirds (UK GRF/SNOWTAM). |
| Local airspace cards | YAIXM UK airspace (`raw.githubusercontent.com/ahsparrow/airspace/master/airspace.yaml`, public domain, AIP ENR 5.1) + PIB R* NOTAMs | Areas within `airspace_range_nm`. State: NOTAM active → ACTIVE (pulse), future → SCHEDULED, `QRDCD` → COLD; else R/P → PERMANENT, D with NOTAM rule → COLD, other D → "AIP HOURS". NOTAM-only temporary areas (TDA/RA(T)/TRA) become cards too. Pins override auto (nearest; live activity within warning radius jumps the queue). |
| "Other areas & nav warnings" bar | Remaining R* items + W* NOTAMs (drones, parachuting, gliding, models) within `warning_range_nm` | Replaces original "JPG MOAs / ATCAA" bar (no MOAs in UK). |
| Temperature / wind / QNH / category | aviationweather.gov METAR JSON | If own METAR missing or >3 h old, nearest fresh METAR ≤40 NM, labelled "METAR EGxx · n NM". Cache 10 min. |

Mapping from original KIMS design → UK version: Fahrenheit → °C (setting), US local time → Europe/London
(24 h default, 12 h setting) with Zulu, FAA SUA (R-3403A/B) → UK D/R/P areas, FICON → RWYCC/GRF,
JPG MOA bar → other areas & nav warnings bar. Mobile layout (reference/IMG_2710) → responsive stacked
layout with "ARRIVING WITHIN 30/60 MINUTES" banners.

## Conventions
- Renderer is a pure function of the `/api/data` JSON — change UI in `web/board.js` only; both website and HA card pick it up.
- All CSS classes prefixed `aib-`. Colours are CSS variables on `.aib-screen` (themes: navy, midnight, high-contrast).
- Timestamps in the API are ISO-8601 UTC; formatting happens client-side (Europe/London).
- New settings: add to `settings.DEFAULTS`, `settings.html` `fields` list + form control, and use via `cfg` in board.js / app.py.
- Footer always shows "INFORMATION ONLY · NOT FOR OPERATIONAL USE" — keep it (safety).
- Git: develop on the branch named by the session; PRs may be merged without asking the owner.

## Known limitations / ideas
- FlightAware markup can change; tests in `server/tests` catch parser breakage using fixtures. FlightAware shows only ~20 rows per table; small GA fields often have no filed flight plans (empty state is normal).
- Danger areas without NOTAM-activation have published AIP hours that YAIXM doesn't carry → shown as "AIP HOURS" (not live). Possible upgrade: parse NATS eAIP ENR 5.1 hours, or the UK AUP/UUP.
- Docker image not built in the cloud session (no Docker daemon); Dockerfile is straightforward python:3.12-slim. Add-on downloads source from GitHub at build → repo must be public for the add-on.
- HA over https needs the server on https too (mixed content) — see homeassistant/README.md.
- Public website hosting not yet deployed (needs a host that runs the Python container, e.g. a VPS/Fly.io/Render; set ADMIN_TOKEN).

## Status / changelog
- **2026-11-22 (session 1, cloud)** — Moved originals to `reference/`. Built full prototype: backend
  (FlightAware scrape, NATS PIB NOTAMs, YAIXM airspace + NOTAM activation, METAR), shared renderer,
  website + settings page, HA card, HA add-on, REST package, Docker, 9 passing tests, CI workflow.
  Verified live against EGBJ, EGBB, EGLC, EGHH; screenshots in docs/screenshots.

## Next steps (suggested)
1. Owner to confirm the NOTAM provider ("NOTAC") and target airport + display resolution.
2. Deploy: run add-on or Docker on the HA host; add card resource; open dashboard on the TVs.
3. Choose public hosting for the website and set `ADMIN_TOKEN`.
4. Optional: AIP published-hours parsing for danger areas; more NOTAM title rules from real-world feedback.
