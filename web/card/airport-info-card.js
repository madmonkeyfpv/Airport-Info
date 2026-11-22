// Airport Info — Home Assistant Lovelace card.
// Renders the exact same board as the website (shared ../board.js) inside Home Assistant.
//
// Load as a dashboard resource (type: module), either straight from the Airport Info server:
//     http://<server>:8080/card/airport-info-card.js
// or copied into /config/www/airport-info/ (copy board.js alongside, one folder up: see docs).
//
// Card config:
//   type: custom:airport-info-card
//   server: http://192.168.1.50:8080   # Airport Info server / add-on URL (required unless same origin)
//   airport: EGBJ                        # optional – overrides the server's saved airport
//   full_screen: true                    # optional – fixed full-viewport kiosk layout (default true)
//   view: board                          # optional – board | weather | rotate (alternate, rotate_seconds)
//   settings:                            # optional – any server setting override
//     theme: midnight
//     temp_unit: C
import { renderBoard, BOARD_CSS, tickClocks, autoScroll } from '../board.js';
import { renderWeather, WEATHER_CSS, tickWeatherClock } from '../weather.js';

const VERSION = '0.1.0';

class AirportInfoCard extends HTMLElement {
  setConfig(config) {
    this._config = { full_screen: true, ...config };
    this._server = String(config.server || new URL('..', import.meta.url).href).replace(/\/$/, '');
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

  set hass(_hass) { /* data comes from the Airport Info server; hass not required */ }

  connectedCallback() { if (this._config) this._start(); }

  disconnectedCallback() { this._stop(); }

  _stop() {
    clearTimeout(this._timer); clearTimeout(this._rotate); clearInterval(this._tick); clearInterval(this._rerender);
    this._rotate = null;
    if (this._stopScroll) this._stopScroll();
    this._timer = this._tick = this._rerender = this._stopScroll = null;
  }

  _start() {
    this._stop();
    this._load();
    this._tick = setInterval(() => { if (this._data) { tickClocks(this._root, this._data.settings); tickWeatherClock(this._root); } }, 1000);
    this._rerender = setInterval(() => this._render(), 30000);
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
      const r = await fetch(`${this._server}/api/data?${this._query()}`, { cache: 'no-store' });
      if (!r.ok) throw new Error(await r.text());
      this._data = await r.json();
      wait = Math.max(15, Number(this._data.settings?.refresh_seconds) || 60);
      this._render();
    } catch (e) {
      if (!this._data) {
        this._root.innerHTML = `<div class="msg"><div><b>CANNOT REACH AIRPORT INFO SERVER</b><br>${String(this._server).replace(/</g, '&lt;')}<br><small>${String(e.message || e).replace(/</g, '&lt;').slice(0, 160)}</small></div></div>`;
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

  static getStubConfig() { return { server: 'http://homeassistant.local:8080', airport: 'EGSU' }; }
}

if (!customElements.get('airport-info-card')) {
  customElements.define('airport-info-card', AirportInfoCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: 'airport-info-card', name: 'Airport Info Board', description: 'UK airport arrivals, departures, NOTAMs and airspace status.', preview: false });
  console.info(`%c AIRPORT-INFO-CARD %c v${VERSION} `, 'background:#1c3045;color:#7dd3fc;font-weight:700', 'background:#08111e;color:#fff');
}
