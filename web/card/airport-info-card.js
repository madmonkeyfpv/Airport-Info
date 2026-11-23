// Airport Info — Home Assistant Lovelace card.
// Renders the exact same board as the website (shared ../board.js) inside Home Assistant.
//
// Recommended (HA add-on 0.2.6+): the add-on installs this card into Home Assistant's own www folder, so add the
// dashboard resource (type: JavaScript module):
//     /local/airport-info/card/airport-info-card.js?v=<add-on version>
// It is then served by HA itself (same origin): works over http, https, Nabu Casa and the mobile apps. Data is
// fetched through the add-on's ingress URL using a Home Assistant session (needs an ADMIN user, like add-on panels).
// Alternative (plain Docker, or non-admin users on http): load it from the server, http://<IP>:8765/card/..., and
// set `server:`.
//
// Card config:
//   type: custom:airport-info-card
//   server: http://192.168.1.50:8765   # optional with the /local resource; required when loading from the server
//   airport: EGBJ                        # optional – PINS this screen to another airport (it then no longer
//                                        #   follows the settings page; a warning is shown on screen). Leave unset.
//   full_screen: true                    # optional – fixed full-viewport kiosk layout (default true)
//   view: board                          # optional – board | weather | rotate (alternate, rotate_seconds)
//   settings:                            # optional – any server setting override
//     theme: midnight
//     temp_unit: C
import { renderBoard, BOARD_CSS, tickClocks, autoScroll } from '../board.js';
import { renderWeather, WEATHER_CSS, tickWeatherClock } from '../weather.js';

const VERSION = '0.2.6';

class AirportInfoCard extends HTMLElement {
  setConfig(config) {
    this._config = { full_screen: true, ...config };
    this._base = null;  // resolved lazily: '<server>/' or the add-on ingress URL (ends with '/')
    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' });
      const font = document.createElement('link');
      font.rel = 'stylesheet';
      font.href = 'https://fonts.googleapis.com/css2?family=Barlow:wght@500;600;700;800&display=swap';
      document.head.appendChild(font);
    }
    this.shadowRoot.innerHTML = `<style>${BOARD_CSS}${WEATHER_CSS}
      :host { display: block; }
      .wrap { position: relative; width: 100%; height: ${this._config.height || '100%'}; min-height: 600px; background: #08111e; }
      .wrap.full { position: fixed; inset: 0; z-index: 1; height: 100dvh; min-height: 0; }
      .msg { height: 100%; display: grid; place-items: center; color: #a9bfd4; font: 700 16px Barlow, Arial, sans-serif; letter-spacing: .08em; text-align: center; padding: 20px; }
      .msg b { color: #f16b68; }
    </style><div class="wrap ${this._config.full_screen ? 'full' : ''}"><div class="msg">LOADING AIRPORT INFORMATION…</div></div>`;
    this._root = this.shadowRoot.querySelector('.wrap');
    if (this.isConnected) this._start();
  }

  set hass(hass) {
    // Only needed for the ingress route (creating a Supervisor ingress session); data never goes through hass.
    const first = !this._hass;
    this._hass = hass;
    if (first && this._waitingForHass && this.isConnected) { this._waitingForHass = false; this._load(); }
  }

  // ---- where to fetch data from ---------------------------------------------------------------------------------
  async _resolveBase() {
    const server = this._config.server ? String(this._config.server).replace(/\/$/, '') : '';
    const mixed = server && location.protocol === 'https:' && server.startsWith('http:');
    if (server && !mixed) return { base: server + '/' };
    // Loaded from HA's /local/airport-info/ (installed by the add-on)? addon.json tells us the ingress URL.
    let meta = null;
    try {
      const r = await fetch(new URL('../addon.json', import.meta.url), { cache: 'no-store' });
      if (r.ok) meta = await r.json();
    } catch (e) { /* not installed by the add-on */ }
    if (meta?.ingress_url) {
      if (!this._hass) return { waitForHass: true };
      await this._ingressSession();
      return { base: meta.ingress_url.endsWith('/') ? meta.ingress_url : meta.ingress_url + '/', ingress: true };
    }
    if (mixed) throw new Error(`Home Assistant is open over https, so the browser blocks ${server}. Use the resource /local/airport-info/card/airport-info-card.js (add-on 0.2.6+) or open Home Assistant over http.`);
    // Loaded straight from the Airport Info server: data lives next to the card.
    return { base: new URL('..', import.meta.url).href };
  }

  // Same mechanism Home Assistant's own add-on panels use: ask the Supervisor (via HA's websocket) for an ingress
  // session cookie, and keep it valid. Requires an administrator account.
  async _ingressSession() {
    const valid = async () => {
      if (!this._ingressToken) return false;
      try {
        await this._hass.callWS({ type: 'supervisor/api', endpoint: '/ingress/validate_session', method: 'post', data: { session: this._ingressToken } });
        return true;
      } catch (e) { return false; }
    };
    if (await valid()) return;
    let res;
    try {
      res = await this._hass.callWS({ type: 'supervisor/api', endpoint: '/ingress/session', method: 'post' });
    } catch (e) {
      throw new Error('Could not open a Home Assistant ingress session — the card needs an administrator account for this route. ' +
        'For non-admin users open Home Assistant over http and set server: http://<IP>:8765 on the card.');
    }
    this._ingressToken = res.session;
    document.cookie = `ingress_session=${res.session};path=/api/hassio_ingress/;SameSite=Strict${location.protocol === 'https:' ? ';Secure' : ''}`;
    clearInterval(this._sessionTimer);
    this._sessionTimer = setInterval(() => valid().then(ok => { if (!ok) this._ingressToken = null; }), 60000);
  }

  async _fetch(path) {
    if (!this._base) {
      const r = await this._resolveBase();
      if (r.waitForHass) { this._waitingForHass = true; throw Object.assign(new Error('waiting for Home Assistant'), { quiet: true }); }
      this._base = r.base; this._viaIngress = !!r.ingress;
    }
    let res = await fetch(this._base + path, { cache: 'no-store', credentials: this._viaIngress ? 'same-origin' : 'omit' });
    if (this._viaIngress && (res.status === 401 || res.status === 403)) {  // session expired: renew once
      this._ingressToken = null; await this._ingressSession();
      res = await fetch(this._base + path, { cache: 'no-store', credentials: 'same-origin' });
    }
    return res;
  }

  connectedCallback() { if (this._config) this._start(); }

  disconnectedCallback() { this._stop(); }

  _stop() {
    clearTimeout(this._timer); clearTimeout(this._rotate); clearInterval(this._tick); clearInterval(this._rerender); clearInterval(this._sync); clearInterval(this._sessionTimer);
    this._rotate = null;
    if (this._stopScroll) this._stopScroll();
    this._timer = this._tick = this._rerender = this._stopScroll = null;
  }

  _start() {
    this._stop();
    this._load();
    this._tick = setInterval(() => { if (this._data) { tickClocks(this._root, this._data.settings); tickWeatherClock(this._root); } }, 1000);
    this._rerender = setInterval(() => this._render(), 30000);
    // Follow the settings page: reload as soon as the saved settings change (polls a tiny fingerprint).
    this._sync = setInterval(async () => {
      if (!this._data || this._checking) return;
      this._checking = true;
      try {
        const r = await this._fetch('api/settings/version');
        if (r.ok && (await r.json()).version !== this._data.settings_version) {
          clearTimeout(this._rotate); this._rotate = null;
          await this._load();
        }
      } catch (e) { /* server unreachable: normal refresh will retry */ } finally { this._checking = false; }
    }, 5000);
  }

  _query() {
    const q = new URLSearchParams();
    if (this._config.airport) q.set('airport', this._config.airport);
    if (this._config.view) q.set('view', this._config.view);
    if (this._config.rotate_seconds) q.set('rotate_seconds', this._config.rotate_seconds);
    Object.entries(this._config.settings || {}).forEach(([k, v]) => q.set(k, Array.isArray(v) ? v.join(',') : String(v)));
    return q.toString();
  }

  async _load() {
    clearTimeout(this._timer);
    let wait = 60;
    try {
      const r = await this._fetch(`api/data?${this._query()}`);
      if (!r.ok) throw new Error(await r.text());
      this._data = await r.json();
      wait = Math.max(15, Number(this._data.settings?.refresh_seconds) || 60);
      this._render();
    } catch (e) {
      if (e.quiet) return;  // resumes when Home Assistant hands the card its hass object
      this._base = null;   // re-resolve next time (e.g. ingress URL changed after an add-on update)
      if (!this._data) {
        const where = this._config.server || 'Airport Info add-on';
        this._root.innerHTML = `<div class="msg"><div><b>CANNOT REACH AIRPORT INFO</b><br>${String(where).replace(/</g, '&lt;')}<br><small>${String(e.message || e).replace(/</g, '&lt;').slice(0, 300)}</small></div></div>`;
      }
      wait = 20;
    }
    this._timer = setTimeout(() => this._load(), wait * 1000);
  }

  _render() {
    if (!this._data) return;
    const scroll = {};
    this._root.querySelectorAll('[data-panel] .aib-scroll').forEach(el => { scroll[el.closest('[data-panel]').dataset.panel] = el.scrollTop; });
    const view = this._data.settings?.view || 'board';
    if (view !== 'rotate') this._page = view === 'weather' ? 'weather' : 'board';
    this._page = this._page || 'board';
    this._root.innerHTML = this._page === 'weather' ? renderWeather(this._data) : renderBoard(this._data);
    if (view === 'rotate' && !this._rotate) {
      this._rotate = setTimeout(() => {
        this._rotate = null;
        this._page = this._page === 'board' ? 'weather' : 'board';
        this._render();
      }, Math.max(10, Number(this._data.settings.rotate_seconds) || 30) * 1000);
    }
    this._root.querySelectorAll('[data-panel] .aib-scroll').forEach(el => { el.scrollTop = scroll[el.closest('[data-panel]').dataset.panel] || 0; });
    if (this._stopScroll) this._stopScroll();
    this._stopScroll = this._page === 'board' && window.matchMedia('(min-width: 1001px) and (orientation: landscape)').matches ? autoScroll(this._root) : null;
  }

  getCardSize() { return 12; }

  static getStubConfig() { return { view: 'board', full_screen: true }; }
}

if (!customElements.get('airport-info-card')) {
  customElements.define('airport-info-card', AirportInfoCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: 'airport-info-card', name: 'Airport Info Board', description: 'UK airport arrivals, departures, NOTAMs and airspace status.', preview: false });
  console.info(`%c AIRPORT-INFO-CARD %c v${VERSION} `, 'background:#1c3045;color:#7dd3fc;font-weight:700', 'background:#08111e;color:#fff');
}
