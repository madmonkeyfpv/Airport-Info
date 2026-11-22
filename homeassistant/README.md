# Home Assistant setup

The display is a custom Lovelace card that renders exactly the same board as the website
(`web/board.js` is shared). Data comes from the Airport Info server.

## 1. Run the server
Pick one:
- **Add-on** (HA OS / Supervised): add this GitHub repo as an add-on repository, install *Airport Info*, start it.
  (Requires the repository to be public so the add-on can download the source.)
- **Docker** anywhere on your network: `docker compose up -d` from the repo root.
- **Python**: `pip install -r server/requirements.txt && PYTHONPATH=server python -m airport_info.app`

Open `http://<server>:8080/settings.html` and choose the airport (ICAO e.g. `EGBJ` or IATA e.g. `GLO`).

## 2. Add the card resource
Settings → Dashboards → ⋮ → Resources → Add:
- URL: `http://<server>:8080/card/airport-info-card.js`
- Type: JavaScript module

> If Home Assistant is served over **https**, the browser blocks an http resource/API (mixed content).
> Either put the server behind the same https reverse proxy, or copy `web/board.js` to
> `/config/www/airport-info/board.js` and `web/card/airport-info-card.js` to
> `/config/www/airport-info/card/airport-info-card.js`, use resource `/local/airport-info/card/airport-info-card.js`,
> and set `server:` to an https URL of the server.

## 3. Add the dashboard
Create a dashboard from `airport_info_dashboard.yaml` (panel view, `full_screen: true` like the original kiosk).
Card options: `server`, `airport`, `full_screen`, `height`, `settings` (any server setting).

## 4. Optional sensors
`airport_info_package.yaml` creates REST sensors (temperature, inbound count, next arrival time,
NOTAM count, airspace state) for automations.

## Kiosk tips
- Browser kiosk without HA: just open `http://<server>:8080/?kiosk` full screen.
- Several screens can show different airports: `?airport=EGLC`, or `airport:` in the card config.
