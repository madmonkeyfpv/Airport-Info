# Installing Airport Info on Home Assistant

This guide takes you from nothing to the airport screens running on your TVs, using Home Assistant.
Allow about 20–30 minutes, most of it waiting for the add-on to build.

**What you end up with**
- **Information board:** arrivals, departures, NOTAMs, latest activity, local airspace and the radio strip.
- **Weather station page:** wind rose with the runways, QNH/QFE, RVR, crosswinds, and the radio box.
- **A settings page:** every screen follows the airport chosen there, switching within about 5 seconds of a save.
- **Ways to show it:** an *Airport Info* entry in the Home Assistant sidebar, plus optional full-screen dashboards and sensors.

> Information only. Not for operational use. Always get an official briefing before flight.

---

## 0. Before you start

| You need | Notes |
|---|---|
| **Home Assistant OS** or **Supervised** | These have the *Add-ons* menu: Settings → Add-ons. On **HA Container/Core** (no add-ons), use the [Docker method](#appendix-a--home-assistant-container--core-no-add-ons). |
| Internet access on the HA machine | The server fetches FlightAware, NATS NOTAMs, METARs and airspace data. |
| A 64-bit Home Assistant machine | Raspberry Pi 4/5, Home Assistant Green/Yellow, or any PC/NUC (amd64/aarch64). |
| A browser on any computer | Used to copy files to Home Assistant and to set things up. |

Find your Home Assistant address, e.g. `http://homeassistant.local:8123` or `http://192.168.1.50:8123`.
This guide writes **`<HA-IP>`** for the IP part, e.g. `192.168.1.50`.

---

## 1. Install the add-on

### Method A: add-on repository (recommended; the repository is public)
1. Go to **Settings → Add-ons → Add-on Store**, then **⋮** (top right) → **Repositories**.
2. Paste `https://github.com/madmonkeyfpv/Airport-Info` and click **Add**, then **Close**.
3. Refresh the page and scroll to **Airport Info add-ons**. Open **Airport Info** and click **Install**.

### Method B: local add-on (only if the repository is ever made private again)
1. **Install a way to copy files into Home Assistant.** The easiest is the **Samba share** add-on:
   - Settings → Add-ons → Add-on Store → search **Samba share** → Install.
   - On its **Configuration** tab, set a username and password, then **Save**.
   - Go to **Info** and click **Start**.
2. **Download the project.** On github.com, signed in, open the repository and click **Code → Download ZIP**. Unzip it.
3. **Copy it into the `addons` share.**
   - Windows: open `\\<HA-IP>\addons` in File Explorer.
   - Mac: Finder → Go → Connect to Server → `smb://<HA-IP>/addons`.
   - Log in with the Samba username and password.
   - Create a folder called **`airport_info`** and copy the **contents** of the unzipped folder into it.
   - `addons/airport_info/config.yaml` must exist, sitting directly inside `airport_info`.
4. **Find it in the store.** Settings → Add-ons → Add-on Store → **⋮** → **Check for updates**. Refresh the page. A **Local add-ons** section appears with **Airport Info**.
5. **Install.** Open **Airport Info** and click **Install**. Home Assistant builds it on your machine. This takes about 2–5 minutes on a PC or NUC and up to about 15 minutes on a Raspberry Pi.

---

## 2. Start it

On the add-on's **Info** tab:
1. Turn on **Start on boot**, **Watchdog** and **Show in sidebar**.
2. Click **Start**.
3. Open the **Log** tab. After a few seconds you should see `Running on http://0.0.0.0:8080`. That is the port
   *inside* the add-on; from your network it's reachable on port **8765**.

Optional, on the **Configuration** tab:
- **admin_token:** set a password here to stop anyone who can see the screens from changing the settings. Leave it blank on a trusted home network.
- **Network:** the board is also served directly on port **8765** for TVs and dashboards. If you see
  *"port … is already in use"* when starting, another add-on has that port. Change the number on the
  **Network** section of the Configuration tab, e.g. to 8766, **Save**, then **Start**. Use your number
  wherever this guide says `8765`. Add-on versions before 0.2.2 defaulted to 8080, which often clashes.

---

## 3. Choose the airport and options

1. Click **Airport Info** in the sidebar. The board opens, defaulting to **EGSU Duxford**.
2. Click the faint **⚙** at the bottom right, or open `http://<HA-IP>:8765/settings.html`.
3. Choose these settings:
   - **Airport:** type a code or a name, e.g. `EGSU`, `GLO` or `Gloucester`, and pick from the list. Any UK airport works.
   - **Screen:** *Information board*, *Weather station*, or *Rotate* (alternates every N seconds).
   - **Opening hours:** leave blank to use the built-in published hours (Duxford is included). Or enter hours like `0900-1700`, or seasonal hours like `15MAR-15OCT 1000-1800; 16OCT-14MAR 1000-1600`.
   - **Units, clock, theme and airspace radius:** as you prefer.
4. Click **SAVE SETTINGS**. Every screen switches within about 5 seconds.

---

## 4. Put it on the TVs

Pick whichever suits each screen. You can mix them, e.g. one TV on the board and another on the weather page.

### Option 1: a TV browser straight to the add-on (simplest)
On the TV's browser (smart TV, Fire TV Silk, Chromecast with a browser, or a Raspberry Pi in kiosk mode), open:

| Screen | Address |
|---|---|
| Information board | `http://<HA-IP>:8765/?kiosk` |
| Weather station | `http://<HA-IP>:8765/weather?kiosk` |
| Alternate both | `http://<HA-IP>:8765/?view=rotate&rotate_seconds=30&kiosk` |

Set the browser to full screen. `kiosk` hides the settings button.

### Option 2: the Home Assistant sidebar panel (works anywhere, including remote https)
- Click **Airport Info** in the sidebar.
- This goes through Home Assistant's own secure connection, so it also works away from home and with Nabu Casa.
- Use the ⚙ button for settings, and add `?view=weather` to the address for the weather page.

### Option 3: a full-screen Home Assistant dashboard (the card)
Use this if the TV already shows a Home Assistant dashboard, e.g. a wall tablet running the HA app or a kiosk browser.
1. **Add the card resource.** Settings → Dashboards → **⋮** → **Resources** → **Add resource**:
   - URL: `http://<HA-IP>:8765/card/airport-info-card.js`
   - Type: **JavaScript module**

   If you don't see *Resources*, turn on **Advanced mode** in your user profile.
2. **Create the dashboard.** Settings → Dashboards → **Add dashboard** → *New dashboard from scratch*, named e.g. *Airport*.
   - Open it, then **⋮** → **Edit dashboard** → **⋮** → **Raw configuration editor**.
   - Paste the contents of [`homeassistant/airport_info_dashboard.yaml`](../homeassistant/airport_info_dashboard.yaml).
   - Replace `homeassistant.local` with `<HA-IP>`, then **Save**.
3. **Open it on the TV.** It has two views: *Airport Information* (the board) and *Airfield Weather*.

> **Important: http vs https.** Browsers block an `http://` card on an `https://` page. Open this dashboard on the TV using the **local http address**, `http://<HA-IP>:8123/...`, not your Nabu Casa or https address. For remote viewing, use Option 2.

Card options, for reference:

```yaml
type: custom:airport-info-card
server: http://<HA-IP>:8765   # where the add-on is reachable
view: board                   # board | weather | rotate
rotate_seconds: 30            # when view: rotate
full_screen: true             # fills the screen like the original kiosk
# airport: EGLL               # ONLY to pin this screen to a different airport (shows an orange warning)
```

---

## 5. Optional: sensors for automations

[`homeassistant/airport_info_package.yaml`](../homeassistant/airport_info_package.yaml) creates sensors you can use in automations:
- temperature;
- the number of inbound aircraft;
- the next arrival time;
- the NOTAM count;
- airspace state;
- the ATIS letter.

For example, you could announce an arrival within 30 minutes.

1. Copy the file to `/config/packages/airport_info_package.yaml`, using Samba (`\\<HA-IP>\config`) or the File editor add-on.
2. Change `homeassistant.local:8765` in it to `<HA-IP>:8765`.
3. In `configuration.yaml`, add the following, unless it is already there:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
4. Developer tools → **Check configuration** → **Restart**.

---

## 6. Updating

1. **Method A:** when a new version is published, the add-on shows **Update**, usually within a day; for sooner, use Add-on Store → ⋮ → **Check for updates**. Click it.
2. **Method B:**
   - Download the new ZIP and replace the files in `addons/airport_info`.
   - Settings → Add-ons → Add-on Store → ⋮ → **Check for updates**.
   - Open Airport Info and click **Update**, or **Rebuild** if the version number didn't change.
   - Your settings are kept, because they are stored in the add-on's data.
3. **If you use the dashboard card:** hard-refresh the TV browser afterwards so it loads the new card.

---

## 7. Troubleshooting

| What you see | Fix |
|---|---|
| Card says **CANNOT REACH AIRPORT INFO SERVER** | Check the add-on is running. Open `http://<HA-IP>:8765/health` in a browser; it should say `"ok": true`. Check the `server:` URL in the card. |
| Dashboard card blank, or the browser console mentions *mixed content* | You opened HA over https. Use `http://<HA-IP>:8123` on that screen, or use Option 2 (sidebar). |
| *Airport Info* missing from the store (Method B) | `config.yaml` must be directly inside `addons/airport_info/`. Run **Check for updates**, then refresh. |
| Add-on fails to build | Look at **Settings → System → Logs → Supervisor**. The build needs internet access to download Python packages. |
| **Cannot start app … port … is already in use** | Another add-on uses that port. Configuration tab → **Network** → pick another number, e.g. 8766 → Save → Start. Then use that number in TV URLs, the card `server:` and the sensor package. The sidebar panel is unaffected. |
| "No flight plans scheduled" | This is normal at small airfields. FlightAware only lists flights with filed plans or tracking. |
| "FLIGHT DATA / NOTAM FEED TEMPORARILY UNAVAILABLE" | An upstream site is down or slow. It retries automatically, and the footer shows the last update time. |
| Orange **SCREEN PINNED TO …** badge | That screen has `?airport=` in its address or `airport:` in its card. Remove it to follow the settings page. |
| Radio shows **NO NOTAM CHANGES** instead of open/closed | No opening hours are known for that airport. Add them on the settings page. |
| Settings won't save: "Admin token required" | Enter the token set on the add-on's Configuration tab in the settings page's Admin box. |

---

## Appendix A: Home Assistant Container / Core (no add-ons)

Run the server with Docker on the same machine or any always-on computer:

```bash
git clone <repository URL> airport-info && cd airport-info
docker compose up -d --build      # serves on port 8080 (plain Docker); settings saved in ./data
```

Then follow steps 3–5, using that machine's IP in place of `<HA-IP>` and port **8080** in place of `8765`. The sidebar panel (Option 2) is
add-on only. Instead, add a **Webpage** dashboard card pointing at `http://<server-ip>:8080/?kiosk`.

## Appendix B: what's tested

- **Automated tests:** 15 offline tests run on every change.
- **Browser checks** with live data:
  - board;
  - weather page;
  - HA card;
  - settings sync;
  - the board under a simulated Home Assistant ingress path.
- **Not yet tried on a real Home Assistant box:** building the add-on image itself. Report any build error from the Supervisor log and it can be fixed quickly.
