# Home Assistant files

**Start here → [docs/SETUP_HOME_ASSISTANT.md](../docs/SETUP_HOME_ASSISTANT.md)** (full step-by-step install guide).

| File | What it is |
|---|---|
| `airport_info_dashboard.yaml` | Full-screen dashboard with two views (board, airfield weather) using the custom card |
| `airport_info_package.yaml` | Optional REST sensors for automations (temperature, inbound count, next arrival, NOTAMs, airspace, ATIS) |

The add-on itself is defined at the repository root (`config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `DOCS.md`),
so the repository is both an add-on repository and the add-on. The card (`web/card/airport-info-card.js`) and the
website share one renderer (`web/board.js`, `web/weather.js`), so they always look identical.

Keeping screens in sync: every screen follows the settings page within ~5 s. Don't set `airport:` on a card
unless that screen should be pinned to a different airport (pinned screens show an orange warning).
