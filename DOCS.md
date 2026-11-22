# Airport Info add-on

UK airport information screens: arrivals/departures (FlightAware), NOTAMs (NATS), local airspace,
weather station (wind rose + runways), radio frequencies & ATIS.

- Open **Airport Info** in the sidebar (works locally and remotely via Home Assistant ingress).
- TVs / kiosk browsers: `http://<HA-IP>:8080/?kiosk` (board) or `http://<HA-IP>:8080/weather?kiosk`.
- Settings (airport, units, screen, hours): ⚙ button or `http://<HA-IP>:8080/settings.html`.
  All screens follow the settings page within ~5 seconds.

**Option `admin_token`**: if set, the settings page asks for it before saving.

Full guide: `docs/SETUP_HOME_ASSISTANT.md` in the repository.

Information only — not for operational use.
