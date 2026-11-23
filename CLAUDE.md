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
- **Default airport: EGSU (Duxford)** — set in `settings.DEFAULTS`. Duxford has no METAR; nearest fresh station (usually EGSS Stansted, 13 NM) is used.
- Build the **weather-station page** shown in `reference/IMG_2709_weather_station.jpeg` (done: `web/weather.js`).
- Originals (`reference/`) must **never be overwritten** — they are the design reference.
- Flight data: **FlightAware web scraper**. Restricted airspace: **web scraper**.
- NOTAMs: free UK API — **NATS AIS PIB XML feed** (owner originally wrote "NOTAC"; owner confirmed
  on 2026-11-22 that the NATS feed is correct).
- Identical functionality to the original at any UK airport; professional look; creative licence OK.
- Owner does not need to approve merges; only ask critical questions.

## Layout
```
reference/                 ORIGINAL uploads (KIMS yaml + photos). READ-ONLY. Do not edit/move.
                           IMG_2709_weather_station.jpeg = KIMS weather-station screen (uploaded session 2;
                           renamed because IMG_2709.jpeg already existed and must not be overwritten)
server/airport_info/       Python aiohttp backend (API + static site)
  app.py                   HTTP server, TTL cache, flight post-processing, /api/* routes
  flightaware.py           FlightAware airport-board scraper (4 tables) -> flight dicts
  notams.py                NATS PIB parser, Q-code decoder, Item D schedule expansion, interpretation
  airspace.py              UK D/R/P areas (YAIXM dataset) + NOTAM activation -> panel cards/summary
  ha_install.py            HA add-on: copies card + board.js + weather.js into /homeassistant/www/airport-info/ at startup
                           (imports rewritten ?v=<version>) + addon.json {ingress_url, port}. Resource = /local/airport-info/
                           card/airport-info-card.js?v=X → same origin as HA (no mixed content, no CORS). Card then fetches
                           data via ingress_url using an ingress session from hass.callWS supervisor/api /ingress/session
                           (ADMIN users only). config.yaml maps homeassistant_config:rw.
  links.py                 /api/links: LAN base URLs for TVs (Supervisor API: host IPs, hostname, mapped host port;
                           fallback: request Host + outbound IP) → settings page "Screen addresses" with copy buttons
  traffic.py               live nearby traffic: adsb.lol /v2/point (free, ODbL) → classify approaching(ETA)/circuit/ground/
                           departed/nearby from distance, closing speed, QNH-corrected height, climb; drops stale/implausible
                           ADS-B values; shown in the arrivals panel (renderTraffic in board.js), /api/traffic polled every 15 s
  radio.py                 radio strip: frequency grouping, NOTAM/hours open-closed ESTIMATE, D-ATIS scrape (atis.guru)
  weather.py               METAR (aviationweather.gov); falls back to nearest fresh METAR
  airports.py              UK airport lookup (ICAO/IATA/name search)
  settings.py              JSON-persisted settings (DEFAULTS documents every key)
  geo.py, sun.py           distance/DMS/polygon helpers; sunrise/sunset for SR-SS NOTAMs
  data/uk_airports.json    built by tools/build_airports.py (OurAirports, GB/IM/JE/GG)
  data/uk_airspace.yaml    bundled YAIXM snapshot (fallback; live copy refreshed daily to DATA_DIR)
server/tests/              pytest, offline fixtures captured 22 Nov 2026 (FA html, PIB subset)
web/board.js               SHARED renderer: renderBoard(data) + BOARD_CSS (+ tickClocks, autoScroll)
web/weather.js             SHARED weather-station renderer: renderWeather(data) + WEATHER_CSS (wind rose + runways)
web/index.html             website / kiosk page (board.js + weather.js; view=board|weather|rotate)
web/settings.html          settings UI (airport autocomplete, units, airspace pins, theme)
web/card/airport-info-card.js  Home Assistant Lovelace card (imports ../board.js -> identical board)
homeassistant/             dashboard YAML, optional REST-sensor package, short README pointing to the guide
docs/SETUP_HOME_ASSISTANT.md   USER-FACING install guide for Home Assistant (keep it current with any change!)
config.yaml, run.sh,       HOME ASSISTANT ADD-ON lives at the REPO ROOT (repository.yaml + config.yaml):
  DOCS.md                  the repo is both the add-on repository and the add-on; build context = whole repo
Dockerfile                 ONE image for plain Docker and the add-on: ghcr.io/home-assistant/base-python:3.13-alpine3.22
                           (multi-arch amd64+arm64, verified). NO build.yaml (deprecated by Supervisor). arch: amd64, aarch64
                           PORTS: container always listens on 8080; HA add-on maps it to HOST 8765 by default (8080
                           clashed on the owner's HA, v0.2.2); plain Docker/compose keeps 8080:8080. Ingress uses 8080 internally.
docker-compose.yml         plain Docker deployment (settings persist in ./data)
docs/screenshots/          README screenshots (regenerated 2026-11-23 from v0.2.6; for README shots switch airport via
                           POST /api/settings, NOT ?airport= — that shows the orange 'SCREEN PINNED' badge)
tools/build_airports.py    regenerate the UK airport DB
```

## Run / test
```bash
pip install -r server/requirements.txt        # aiohttp, PyYAML, beautifulsoup4
PYTHONPATH=server python -m airport_info.app   # http://localhost:8080  (PORT, DATA_DIR, WEB_DIR, ADMIN_TOKEN env)
pytest -q                                      # offline tests (pytest.ini sets pythonpath)
docker compose up -d --build                   # container on :8080, settings persisted in ./data
```
Display URLs: `/` (board), `/weather` or `/?view=weather` (weather station), `/?view=rotate&rotate_seconds=30`,
`/?airport=EGLC&theme=midnight&kiosk` (per-screen overrides, kiosk hides gear),
`/settings.html`, `/api/data?airport=GLO`, `/api/airports?q=glou`, `/card/airport-info-card.js`.
Screenshots: Playwright is preinstalled in cloud sessions (`require('playwright')`, `chromium.launch()`).

## Data sources & how they're used
| Panel | Source | Notes |
|---|---|---|
| Arrivals / departures / latest activity | Scrape `flightaware.com/live/airport/<ICAO>` | Tables `data-type=arrivals|departures|enroute|scheduled`. Times are local with tz abbr; **format depends on Accept-Language** (en-GB → `17:52`, en-US → `05:52p`) — parser handles both. History URL `/history/YYYYMMDD/HHMMZ/ORIG/DEST` anchors the date. Italic = estimate. Progress bar = airborne. Stale inbound (ETA > 30 min past) dropped. Cache 120 s. |
| NOTAMs | `https://pibs.nats.co.uk/operational/pibs/PIB.xml` (~2 MB, all UK) | Cached 15 min globally. Aerodrome NOTAMs = ItemA contains ICAO. Obstacles and airspace/warning NOTAMs hidden by default (settings). Titles built from Q-code (Code23 subject / Code45 condition) + keywords. Item D schedules (e.g. `MON-FRI 0800-1600`, `SR-SS`, date lists) expanded to UTC windows → ACTIVE / UPCOMING. RWYCC triplets rendered as thirds (UK GRF/SNOWTAM). |
| Local airspace cards | YAIXM UK airspace (`raw.githubusercontent.com/ahsparrow/airspace/master/airspace.yaml`, public domain, AIP ENR 5.1) + PIB R* NOTAMs | Areas within `airspace_range_nm`. State: NOTAM active → ACTIVE (pulse), future → SCHEDULED, `QRDCD` → COLD; else R/P → PERMANENT, D with NOTAM rule → COLD, other D → "AIP HOURS". NOTAM-only temporary areas (TDA/RA(T)/TRA) become cards too. Pins override auto (nearest; live activity within warning radius jumps the queue). |
| Live nearby traffic (arrivals panel) | `https://api.adsb.lol/v2/point/{lat}/{lon}/{nm}` (community ADS-B, open data ODbL, no key) | Why: small UK fields have no schedules and VFR GA files no flight plans, so FlightAware's expected tables are empty there (verified EGSU/EGSC: 0 en-route/scheduled while 10–20 movements/day). Filter: within `traffic_range_nm` (3 NM since 0.3.1; stored 10 auto-migrated to 3), below `traffic_max_ft_agl` (3000 ft) using QNH-corrected altitude, `ground` only within 1.5 NM, positions ≤60 s old; gs>400 kt / |vs|>6000 fpm dropped as corrupt. Classify: climbing away → departed; ≤2.5 NM & ≤1500 ft → circuit; closing >25 kt & low/descending → approaching with ETA; else nearby. **Shown ONLY in a panel whose FlightAware list is blank (owner rule)**: both blank → arrivals gets approaching/circuit/nearby, departures gets departed/ground; one blank → that panel gets all; neither blank → none (FA unavailable counts as blank). Guarded by test_traffic_only_in_blank_panels (runs server/tests/js/traffic_panels.mjs in Node). Board shows max 8 (+N more). Cache 15 s; clients poll `/api/traffic` every 15 s. Settings `show_traffic`, `traffic_range_nm`, `traffic_max_ft_agl`. |
| "Other areas & nav warnings" bar | Remaining R* items + W* NOTAMs (drones, parachuting, gliding, models) within `warning_range_nm` | Replaces original "JPG MOAs / ATCAA" bar (no MOAs in UK). |
| Temperature / wind / QNH / category | aviationweather.gov METAR JSON | If own METAR missing or >3 h old, nearest fresh METAR ≤40 NM, labelled "METAR EGxx · n NM". Cache 10 min. Server also derives QFE (elev/27 ft per hPa), pressure & density altitude (API/sensors only — owner asked for RVR instead on the page), RVR groups (`rvr`, parsed from raw METAR), humidity, visibility text (metres/KM), sky layers, variable-wind range. |
| Radio strip (board top + weather page) | OurAirports airport-frequencies.csv (built into uk_airports.json; 8.33 kHz duplicates collapsed) + PIB NOTAMs + `service_hours` setting + atis.guru D-ATIS | Fire/EMR hidden. Status is an ESTIMATE (labelled on screen): active NOTAM closing AD/ATC/AFIS/A-G/ATIS or naming the frequency U/S → CLOSED (with NOTAM id); closure within 24 h → CLOSES hh:mm; outside configured hours → CLOSED/OPENS; otherwise "NO NOTAM CHANGES". ATIS letter only from real text D-ATIS (EGLL, EGKK, EGCC, EGPH… not small fields); reports >75 min flagged "may be out of date", >3 h dropped; only queried when the airport publishes an ATIS frequency. Never invent a letter. |
| Weather station page | same METAR + runways from OurAirports `runways.csv` (built into uk_airports.json) | Runway true heading computed from threshold coordinates. Wind shown TRUE (METAR is true; UK magnetic variation ≈ 0–2° so not converted — the original KIMS screen said MAG). Parallel runways placed by L/R suffix. Head/cross-wind per runway end, favoured runway = max headwind. |

Mapping from original KIMS design → UK version: Fahrenheit → °C (setting), US local time → Europe/London
(24 h default, 12 h setting) with Zulu, FAA SUA (R-3403A/B) → UK D/R/P areas, FICON → RWYCC/GRF,
JPG MOA bar → other areas & nav warnings bar. KIMS weather-station screen (AWOS wind with 2-min average)
→ `/weather` page from METAR (no AWOS feed exists for UK GA fields; the averaging dropdown was replaced by
the METAR source/age line). Mobile layout (reference/IMG_2710) → responsive stacked
layout with "ARRIVING WITHIN 30/60 MINUTES" banners.

## Conventions
- **Container start: `run.sh` must set PYTHONPATH/WEB_DIR/DATA_DIR/PORT itself.** The HA base image runs CMD via
  s6-overlay, which RESETS the environment, so Dockerfile `ENV` never reaches the app. Guarded by
  `server/tests/test_startup.py` (starts run.sh with an empty environment).
- Renderer is a pure function of the `/api/data` JSON — change UI in `web/board.js` only; both website and HA card pick it up.
- All CSS classes prefixed `aib-`. Colours are CSS variables on `.aib-screen` (themes: navy, midnight, high-contrast).
- Timestamps in the API are ISO-8601 UTC; formatting happens client-side (Europe/London).
- New settings: add to `settings.DEFAULTS`, `settings.html` `fields` list + form control, and use via `cfg` in board.js / app.py.
- Footer always shows "INFORMATION ONLY · NOT FOR OPERATIONAL USE" — keep it (safety).
- Git: develop on the branch named by the session; PRs may be merged without asking the owner,
  **but only after the GitHub Actions `test` check on the PR has passed.**
- **Releases to Home Assistant: bump `version` in root `config.yaml` (semver) in every PR that changes
  server/ or web/** — HA only offers "Update" when the version changes (Method A, public repo). Note the
  version in the changelog entry.

## Known limitations / ideas
- FlightAware markup can change; tests in `server/tests` catch parser breakage using fixtures. FlightAware shows only ~20 rows per table; small GA fields often have no filed flight plans (empty state is normal).
- Danger areas without NOTAM-activation have published AIP hours that YAIXM doesn't carry → shown as "AIP HOURS" (not live). Possible upgrade: parse NATS eAIP ENR 5.1 hours, or the UK AUP/UUP.
- Add-on build VERIFIED on the owner's HA (aarch64, Supervisor log 2026-11-23: v0.2.0 built in ~2 min and installed
  via the repository URL). Cloud sessions have no Docker daemon, so builds can only be checked via owner logs.
- Repo is now PUBLIC → guide's Method A (add-on repository URL) is the recommended install; Method B kept for reference.
- HA ingress (sidebar panel) works over HA's https; all web URLs are RELATIVE (`api/...`, `./?view=weather`) so
  the site works under `/api/hassio_ingress/<token>/` — never reintroduce absolute `/api/...` paths in web/*.html.
  The dashboard card loads from http://<HA-IP>:8080, so it needs HA opened over local http (mixed content).
- Public website hosting not yet deployed (needs a host that runs the Python container, e.g. a VPS/Fly.io/Render; set ADMIN_TOKEN).

## Status / changelog
- **2026-11-22 (session 1, cloud)** — Moved originals to `reference/`. Built full prototype: backend
  (FlightAware scrape, NATS PIB NOTAMs, YAIXM airspace + NOTAM activation, METAR), shared renderer,
  website + settings page, HA card, HA add-on, REST package, Docker, 9 passing tests, CI workflow.
  Verified live against EGBJ, EGBB, EGLC, EGHH; screenshots in docs/screenshots.

- **2026-11-22 (session 1, cont.)** — Default airport → EGSU. Added weather photo to reference (new name).
  Built weather-station page (`/weather`, HA card `view: weather`, `view: rotate` alternates with the board),
  runway DB (215 UK airfields), derived met values, airspace fixes (upper-airspace ranked last, TRA/MTA
  designators, multi-line place names). 10 tests passing.

- **2026-11-22** — Owner confirmed NATS PIB feed for NOTAMs.

- **2026-11-22** — Weather page: DENSITY ALT row replaced by RVR (owner request). Shows each METAR RVR
  group (runway, metres/feet, >/< qualifiers, ↑↓→ tendency) with source ICAO when not local; "NOT REPORTED"
  otherwise (normal — RVR only appears when vis/RVR < 1500 m). 11 tests.
- **2026-11-22** — Built the radio strip (owner approved): see radio.py / renderRadio in board.js; settings
  `show_radio`, `service_hours` (Duxford hours not set — owner to supply). 13 tests. Original offer: "Radio" strip = published frequencies (OurAirports
  airport-frequencies.csv) + open/closed estimated from NOTAMs + ATIS letter only where real D-ATIS text exists
  (atis.guru has EGLL; none for EGBB/EGSU). Duxford has no ATIS (A/G "Duxford Information" 122.075).
  Never fabricate an ATIS letter. Listening to UK ATC audio without licence is illegal — don't transcribe.

- **2026-11-22** — Seasonal opening hours (`15MAR-15OCT 1000-1800; 16OCT-14MAR 1000-1600`) supported;
  per-airport published hours in `server/airport_info/data/opening_hours.json` (EGSU from IWM pilot info,
  iwm.org.uk blocks automated fetches so taken from search-indexed IWM text); `service_hours` setting overrides.
  Strip shows "PPR REQUIRED". 14 tests.
- Cloudflare: the attached Cloudflare connector (deprecated Workers-bindings MCP) can list/read Workers and
  manage KV/D1/R2/Hyperdrive and search docs, but CANNOT deploy Worker code, Pages, Tunnels or DNS.
  Deployment options discussed with owner — see Next steps.

- **2026-11-22** — Screen sync: all screens (board, /weather, HA card) follow the settings page. Server exposes
  `/api/settings/version` (sha1 fingerprint of saved settings; also in /api/data as `settings_version`);
  clients poll it every 5 s and reload immediately on change (verified end-to-end: board, weather page and HA
  card all switched EGSU→GLO within ~5 s). A screen with `?airport=` / card `airport:` is deliberately pinned and
  shows an orange "SCREEN PINNED TO … · NOT FOLLOWING SETTINGS PAGE" badge (`overrides` in /api/data). 15 tests.
- Cloudflare decision pending from owner: (A) port backend to Workers (needs Workers Paid $5/mo: free plan 10 ms
  CPU can't parse the 2 MB PIB; FlightAware may block CF IPs — test first) or (B) Cloudflare Tunnel from the HA
  box (free, minimal code). Deploy from cloud session possible with a CF API token via request_credential + wrangler.

- **2026-11-22** — Hosting decision: owner chose to KEEP current setup (HA add-on / local Docker). Cloudflare
  Workers and Oracle Always Free were evaluated (Oracle: $0 but idle-reclaim risk, 2026 allowance cut, card needed;
  Cloudflare: $5/mo Workers Paid + JS rewrite) — parked. Moved the add-on to the repo root so it builds from local
  files (private repo OK as a local add-on), added ingress (sidebar panel), relative web URLs, and wrote
  docs/SETUP_HOME_ASSISTANT.md. Ingress verified with a prefix-stripping proxy simulation (board, /weather redirect,
  settings save all OK).

- **2026-11-22** — Owner asked about making the repo public for easy install. Pre-publication check: no
  secrets in tree/history, commit emails are GitHub noreply, reference photos carry no EXIF GPS/device data.
  Advised: public → Method A (add-on repository URL, one-click install + update button). Add-on v0.2.0.

- **2026-11-23** — Owner made the repo public and installed via the add-on repository: Supervisor log shows
  build + install of v0.2.0 OK on aarch64. Addressed log deprecations: removed build.yaml (base image now set in
  Dockerfile, multi-arch ghcr.io/home-assistant/base-python:3.13-alpine3.22), dropped armv7. Add-on v0.2.1.

- **2026-11-23** — Owner hit "Cannot start app … port 8080 is already in use" (another add-on owns host 8080).
  Workaround given: Network tab → 8765. Add-on 0.2.2 defaults the host port to 8765; guide/DOCS/dashboard/
  package/card examples updated to :8765 and a troubleshooting row added.

- **2026-11-23** — Add-on log: `ModuleNotFoundError: No module named 'airport_info'` on every start (crash loop).
  Root cause: s6-overlay in the HA base image resets the environment, dropping Dockerfile ENV PYTHONPATH.
  Fix: run.sh exports everything (cd /app, PYTHONPATH, WEB_DIR, DATA_DIR=/data, PORT) and logs a start line;
  regression test test_startup.py; server __version__ now tracks add-on version. Add-on 0.2.3. 16 tests.

- **2026-11-23** — Settings page "SCREEN ADDRESSES" section (owner request): every URL variant (board/weather/rotate
  kiosk, with-gear versions, settings, card resource, card YAML, health) built on the device's REAL LAN IP + host port,
  with COPY (clipboard API + execCommand fallback for http) and OPEN. Add-on now `hassio_api: true` (read-only) to
  query Supervisor `/addons/self/info` (network["8080/tcp"] = host port), `/network/info`, `/host/info`.
  SUPERVISOR_TOKEN read from /run/s6/container_environment (s6 wipes env). Tested with a mock Supervisor through the
  ingress simulation. Add-on 0.2.4. 17 tests.

- **2026-11-23** — CI failure on PR #13 (merged before CI finished — don't do that: wait for the `test` check).
  test_startup.py used a fixed PATH, so on GitHub runners it picked /usr/bin/python3 (no aiohttp) instead of
  setup-python's interpreter. Fixed by putting dirname(sys.executable) first on the test PATH. Test-only; the add-on
  image is unaffected (/usr/local/bin/python3 has the requirements).

- **2026-11-23** — Owner: HA card "Custom element doesn't exist". Root cause: card is imported CROSS-ORIGIN (HA :8123 →
  add-on :8765) as an ES module and imports ../board.js + ../weather.js, which had no CORS header (only /api/ and
  /card/ did) → module graph blocked. Reproduced with a page on another port (Chromium console: blocked by CORS).
  Fix: CORS on every .js/.css. Regression test test_card_modules_are_cors_enabled. /api/links returns `version`;
  settings page card resource URL now ends `?v=<version>` for cache busting. Verified card renders cross-origin.
  Add-on 0.2.5. 18 tests.

- **2026-11-23** — Owner (iPhone HA app) still saw "Custom element doesn't exist" (screenshot 01:12, one minute after
  0.2.5 merged, so 0.2.5 not yet installed; also iOS app over https would block an http resource anyway). Made the card
  robust: add-on installs it into HA www (served as /local/…, same origin), card resolves data base: `server:` if not
  mixed-content, else addon.json ingress_url + ingress session via hass websocket (cookie ingress_session, validated every
  60 s, renewed on 401), else fallback next-to-module. Tested end-to-end with a simulated HA origin (static /local + cookie-
  checked ingress proxy) + mock Supervisor; old server: route re-tested. Settings page shows the /local resource as
  RECOMMENDED. Guide Option 3 rewritten. Add-on 0.2.6. 19 tests.

- **2026-11-23** — README screenshots refreshed from 0.2.6 with live data (EGSU board + weather, EGBB board + weather +
  phone, HA card, EGLL radio strip, settings + screen addresses); README rewritten with a screenshot gallery. Removed
  obsolete tv_egbj / ha_card_eglc_midnight images. Docs-only (no add-on version bump).

- **2026-11-23** — Setup guide rewritten for readability (owner request), README-style: hero screenshot, 4-step quick
  start table, one recommended install path (repo URL), "Which should I use?" table for screens, short dashboard-card
  steps, top-5 troubleshooting with the rest + local install / sensors / non-admin / Docker in collapsible <details>.
  Every label quoted in the guide matches the app text (checked). Docs-only.
  Keep the guide in this style: lead with the common path, push rare cases into <details>.

- **2026-11-23** — Owner asked why EGSC/EGSU have no scheduled flights: FlightAware only has airline schedules + filed IFR
  plans; UK VFR GA rarely files and FA only sees GA once airborne. Built the live nearby-traffic panel (owner approved):
  traffic.py + renderTraffic + /api/traffic + 15 s client refresh (website + HA card), settings, HA sensor
  "Airport Info Nearby Traffic", README/guide/DOCS updated. Live-checked EGSU/EGSC/EGBB; fixed a real corrupt-value
  case (PA-28 "415 kt, 64,900 fpm"). Fixture adsb_EGSU.json. Add-on 0.3.0. 20 tests.

- **2026-11-23** — Owner: live traffic must only show when arrivals or departures are blank. Implemented per-panel
  (split inbound/local vs departing/ground when both blank; whole list in the single blank panel; none when both have
  plans). Verified live: EGSU split 2/1, EGBB (19/19 planned) none. Node-based renderer test. Still add-on 0.3.0
  (PR #19 not yet merged). 21 tests.

- **2026-11-23** — Owner: reduce GA traffic radius to 3 (NM). Default traffic_range_nm 10 → 3; settings load migrates a
  stored value equal to the old default (10) to 3 (MIGRATE_OLD_DEFAULTS), since the settings page saves every value.
  Add-on 0.3.1.

## Next steps (suggested)
1. Owner to confirm display resolution (assumed 1920×1080). NOTAM provider confirmed: NATS PIB.
   Duxford hours now built in (data/opening_hours.json, from IWM pilot info; "mid-month" read as the 15th —
   confirm exact season change dates with Duxford ATC 01223 833376 if precision matters).
2. Owner: update add-on to 0.3.1, restart it, set dashboard resource /local/airport-info/card/airport-info-card.js?v=0.3.1, choose airport, set up TVs (guide steps 2–4). Check add-on Log tab if issues.
3. Public hosting parked (owner: "keep it as is for now"). Options documented above if revisited.
4. Optional: AIP published-hours parsing for danger areas; more NOTAM title rules from real-world feedback.
