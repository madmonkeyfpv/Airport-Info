# Airport Info add-on

Runs the Airport Info server inside Home Assistant.

1. Settings → Add-ons → Add-on store → ⋮ → Repositories → add `https://github.com/madmonkeyfpv/airport-info`.
2. Install **Airport Info**, start it, open the Web UI (port 8080).
3. Choose your airport at `http://<ha-host>:8080/settings.html`.
4. Add the dashboard card — see `homeassistant/README.md` in the repository.

Option `admin_token`: if set, the settings page asks for it before saving.
