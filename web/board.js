// Airport Info — shared display renderer.
// Pure functions: renderBoard(data) -> HTML string, BOARD_CSS -> stylesheet string.
// Used by the website (web/index.html) and the Home Assistant card (web/card/airport-info-card.js),
// so both surfaces stay pixel-identical. No framework, no build step.

const TZ = 'Europe/London';

export const esc = v => String(v ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const d = iso => { if (!iso) return null; const x = new Date(iso); return Number.isFinite(x.getTime()) ? x : null; };

export function fmt(cfg) {
  const h12 = cfg.clock === '12h';
  const time = x => x ? new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: h12 ? 'numeric' : '2-digit', minute: '2-digit', hour12: h12 }).format(x).toUpperCase() : '—';
  const date = x => x ? new Intl.DateTimeFormat('en-GB', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' }).format(x) : '';
  const longDate = x => x ? new Intl.DateTimeFormat('en-GB', { timeZone: TZ, weekday: 'long', day: 'numeric', month: 'short' }).format(x).toUpperCase() : '';
  const zulu = x => x ? new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(x).replace(':', '') + 'Z' : '';
  const zuluDate = x => x ? new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: '2-digit', month: 'short' }).format(x).toUpperCase() : '';
  const dayKey = x => new Intl.DateTimeFormat('en-CA', { timeZone: TZ }).format(x);
  const relDay = (x, now) => {
    if (!x) return '';
    const k = dayKey(x), t = dayKey(now), tm = dayKey(new Date(now.getTime() + 86400000)), ys = dayKey(new Date(now.getTime() - 86400000));
    return k === t ? 'TODAY' : k === tm ? 'TOMORROW' : k === ys ? 'YESTERDAY' : date(x).toUpperCase();
  };
  return { time, date, longDate, zulu, zuluDate, relDay };
}

// ---- icons (inline SVG so they work outside Home Assistant) ------------------------------
const PLANE = 'M20.56 3.91c.59.59.59 1.54 0 2.12l-3.89 3.89 2.12 9.19-1.41 1.42-3.88-7.43-3.9 3.9.36 2.47-1.07 1.06-1.76-3.18-3.19-1.77 1.06-1.08 2.5.37 3.87-3.87-7.43-3.91 1.42-1.41 9.19 2.12 3.89-3.89c.56-.58 1.56-.58 2.12 0z';
const svg = (inner, cls = '') => `<svg class="aib-ic ${cls}" viewBox="0 0 24 24" aria-hidden="true">${inner}</svg>`;
const ICON = {
  plane: svg(`<path d="${PLANE}" fill="currentColor"/>`),
  landing: svg(`<g transform="rotate(100 12 11) translate(1.2 -1.5) scale(.86)"><path d="${PLANE}" fill="currentColor"/></g><rect x="2.5" y="20" width="19" height="2" rx="1" fill="currentColor"/>`),
  takeoff: svg(`<g transform="rotate(-10 12 11) translate(1.2 -1.5) scale(.86)"><path d="${PLANE}" fill="currentColor"/></g><rect x="2.5" y="20" width="19" height="2" rx="1" fill="currentColor"/>`),
  check: svg('<circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M7 12.5l3.2 3.2L17 9" stroke="#0b1626" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'),
  arrow: svg('<path d="M4 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'),
  shield: svg('<path d="M12 2l8 3v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5z" fill="currentColor"/>'),
  doc: svg('<path d="M6 2h8l5 5v15H6z" fill="currentColor" opacity=".9"/><path d="M9 12h7M9 16h7M9 8h3" stroke="#0b1626" stroke-width="1.8" stroke-linecap="round"/>'),
  clock: svg('<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2.2" fill="none"/><path d="M12 7v5l3.5 2" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round"/>'),
  radio: svg('<path d="M4 9a10 10 0 0 1 16 0M7 12a6 6 0 0 1 10 0M10 15a2.5 2.5 0 0 1 4 0" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round"/><circle cx="12" cy="18.5" r="1.8" fill="currentColor"/>'),
  wind: svg('<path d="M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>'),
};

// ---- helpers ---------------------------------------------------------------------------
const placeLabel = p => {
  if (!p || (!p.name && !p.code)) return { name: '', code: '' };
  return { name: p.name || '', code: p.code || p.label || '' };
};
const typeLabel = f => f.type_name || (f.type_code ? f.type_code : '') || 'Aircraft type not reported';
const minutesUntil = (x, now) => x ? Math.max(0, Math.ceil((x - now) / 60000)) : null;
const remainingText = m => m === null ? '' : m === 0 ? 'DUE NOW' : m < 60 ? `${m} MIN REMAINING` : `${Math.floor(m / 60)}H ${String(m % 60).padStart(2, '0')}M REMAINING`;

function temperature(wx, cfg) {
  if (!wx || wx.temp_c === null || wx.temp_c === undefined) return '—';
  const t = cfg.temp_unit === 'F' ? wx.temp_c * 9 / 5 + 32 : wx.temp_c;
  return `${Math.round(t)}°${cfg.temp_unit === 'F' ? 'F' : 'C'}`;
}

// ---- flight cards ----------------------------------------------------------------------
function renderArrival(f, ctx) {
  const { F, now } = ctx;
  const eta = d(f.arrival_time);
  const mins = minutesUntil(eta, now);
  const enroute = f.status === 'enroute';
  const urgency = enroute && mins !== null && mins <= 30 ? 'urgent' : enroute && mins !== null && mins <= 60 ? 'soon' : enroute ? 'enroute' : 'scheduled';
  const o = placeLabel(f.origin);
  const banner = urgency === 'urgent' ? 'ARRIVING WITHIN 30 MINUTES' : urgency === 'soon' ? 'ARRIVING WITHIN 60 MINUTES' : '';
  const progress = enroute && Number.isFinite(f.progress)
    ? `<div class="aib-progress"><div class="aib-progress-fill" style="width:${Math.max(2, Math.min(100, f.progress))}%"></div></div>` : '';
  return `<div class="aib-flight ${urgency}">
    ${banner ? `<div class="aib-flight-banner">${banner}</div>` : ''}
    <div class="aib-flight-top">
      <div class="aib-flight-left">
        <div class="aib-flight-ident">${esc(f.ident)}</div>
        <div class="aib-flight-type">${esc(typeLabel(f))}${f.operator ? ` · <span class="aib-op">${esc(f.operator)}</span>` : ''}</div>
        <div class="aib-flight-place">FROM <strong>${esc(o.name || 'UNKNOWN')}</strong>${o.code ? ` <span class="aib-code">${esc(o.code)}</span>` : ''}</div>
      </div>
      <div class="aib-flight-right">
        <div class="aib-flight-clock">${esc(F.time(eta))}</div>
        <div class="aib-flight-day">${esc(F.relDay(eta, now))}${ctx.cfg.show_zulu && eta ? ` · ${esc(F.zulu(eta))}` : ''}</div>
        <div class="aib-flight-state">${enroute ? 'EN ROUTE' : 'SCHEDULED'}${f.arrival_estimated ? ' · EST' : ''}</div>
        ${enroute && mins !== null ? `<div class="aib-flight-remaining">${esc(remainingText(mins))}</div>` : ''}
      </div>
    </div>
    ${progress}
  </div>`;
}

function renderDeparture(f, ctx) {
  const { F, now } = ctx;
  const etd = d(f.departure_time);
  const mins = minutesUntil(etd, now);
  const soon = mins !== null && mins <= 30;
  const dst = placeLabel(f.destination);
  return `<div class="aib-flight departure ${soon ? 'boarding' : ''}">
    <div class="aib-flight-top">
      <div class="aib-flight-left">
        <div class="aib-flight-ident">${esc(f.ident)}</div>
        <div class="aib-flight-type">${esc(typeLabel(f))}${f.operator ? ` · <span class="aib-op">${esc(f.operator)}</span>` : ''}</div>
        <div class="aib-flight-place">TO <strong>${esc(dst.name || 'DESTINATION NOT FILED')}</strong>${dst.code ? ` <span class="aib-code">${esc(dst.code)}</span>` : ''}</div>
      </div>
      <div class="aib-flight-right">
        <div class="aib-flight-clock">${esc(F.time(etd))}</div>
        <div class="aib-flight-day">${esc(F.relDay(etd, now))}${ctx.cfg.show_zulu && etd ? ` · ${esc(F.zulu(etd))}` : ''}</div>
        <div class="aib-flight-state">${soon ? 'DEPARTING SOON' : 'SCHEDULED'}</div>
        ${mins !== null && mins <= 120 ? `<div class="aib-flight-remaining dep">${esc(remainingText(mins).replace('REMAINING', 'TO DEPARTURE'))}</div>` : ''}
      </div>
    </div>
  </div>`;
}

const emptyFlights = (text, sub) => `<div class="aib-empty">
  <div class="aib-empty-icon">${ICON.plane}</div>
  <div class="aib-empty-main">${text}</div>
  ${sub ? `<div class="aib-empty-sub">${sub}</div>` : ''}
</div>`;

// ---- latest activity -------------------------------------------------------------------
function renderActivity(f, arrival, ctx) {
  const { F, now } = ctx;
  const kind = arrival ? 'arrival' : 'departure';
  const label = arrival ? 'LAST ARRIVAL' : 'LAST DEPARTURE';
  const icon = arrival ? ICON.landing : ICON.takeoff;
  if (!f) {
    return `<div class="aib-activity ${kind}"><div class="aib-activity-label"><span>${label}</span>${icon}</div>
      <div class="aib-activity-empty">NO ACTIVITY IN THE LAST 24 HOURS</div></div>`;
  }
  const t = d(arrival ? f.arrival_time : f.departure_time);
  const p = placeLabel(arrival ? f.origin : f.destination);
  const status = arrival ? 'LANDED' : (f.status === 'airborne' ? 'AIRBORNE' : 'DEPARTED');
  return `<div class="aib-activity ${kind}">
    <div class="aib-activity-label"><span>${label}</span>${icon}</div>
    <div class="aib-activity-ident">${esc(f.ident)}</div>
    <div class="aib-activity-type">${esc(typeLabel(f))}</div>
    <div class="aib-activity-place">
      <div class="aib-activity-code">${arrival ? 'FROM' : 'TO'} ${esc(p.code || '—')}</div>
      <div class="aib-activity-name">${p.name ? esc(p.name) : `<span class="aib-pending">${arrival ? 'Origin not reported' : 'Destination not filed'}</span>`}</div>
    </div>
    <div class="aib-activity-bottom">
      <div class="aib-activity-time">${esc(F.time(t))}</div>
      <div class="aib-activity-status">${ICON.check}${status}</div>
      <div class="aib-activity-date">${esc(F.relDay(t, now))}${ctx.cfg.show_zulu && t ? ` · ${esc(F.zulu(t))}` : ''}</div>
    </div>
  </div>`;
}

// ---- NOTAMs ----------------------------------------------------------------------------
const KIND_LABEL = {
  closure: 'CLOSURE', surface: 'RUNWAY SURFACE', fuel: 'FUEL', lighting: 'LIGHTING', navaid: 'NAV AID',
  works: 'WORKS', hours: 'HOURS / SERVICES', airspace: 'AIRSPACE', obstacle: 'OBSTACLE', general: 'GENERAL',
};
const RWYCC_TONE = c => c >= 5 ? 'good' : c >= 3 ? 'medium' : c === 2 ? 'caution' : 'poor';

function renderNotam(n, ctx) {
  const { F } = ctx;
  const start = d(n.start), end = d(n.end);
  const row = (label, x, extra = '') => x ? `<div><span>${label}</span> ${esc(F.date(x))} ${esc(F.time(x))} LOCAL${ctx.cfg.show_zulu ? ` · ${esc(F.zuluDate(x))} ${esc(F.zulu(x))}` : ''}${extra}</div>` : '';
  const endRow = n.permanent ? '<div><span>UNTIL</span> PERMANENT</div>' : row('UNTIL', end, n.end_estimated ? ' (EST)' : '');
  const surface = n.surface ? `<div class="aib-notam-cond-title">RWYCC ASSESSMENT · NOT A PILOT BRAKING REPORT</div>
    <div class="aib-thirds">${n.surface.rwycc.map((c, i) => `<div class="aib-third ${RWYCC_TONE(c)}"><div>${['FIRST', 'MIDDLE', 'LAST'][i]} THIRD</div><strong>${esc(n.surface.names[i])}</strong><span>RWYCC ${c}</span></div>`).join('')}</div>` : '';
  const upcoming = n.state === 'scheduled';
  return `<div class="aib-notam ${esc(n.kind)} ${upcoming ? 'upcoming' : ''}">
    <div class="aib-notam-top"><span>${esc(n.id)} · ${esc(KIND_LABEL[n.kind] || 'NOTICE')}</span><span class="aib-notam-state ${upcoming ? 'upcoming' : ''}">${upcoming ? 'UPCOMING' : 'ACTIVE'}</span></div>
    <div class="aib-notam-title">${esc(n.title)}</div>
    ${surface}
    <div class="aib-notam-text">${esc(n.text)}</div>
    <div class="aib-notam-dates">${row('FROM', start)}${endRow}${n.schedule ? `<div><span>HOURS</span> ${esc(n.schedule)} (UTC)</div>` : ''}</div>
  </div>`;
}

// ---- airspace --------------------------------------------------------------------------
const AREA_STATE = {
  active: ['ACTIVE', 'AIRSPACE ACTIVE NOW'],
  scheduled: ['SCHEDULED', 'UPCOMING ACTIVATION'],
  cold: ['COLD', 'NOT ACTIVATED'],
  permanent: ['PERMANENT', 'H24 RESTRICTED AREA'],
  published: ['AIP HOURS', 'ACTIVE PER PUBLISHED SCHEDULE'],
  unknown: ['UNKNOWN', 'STATUS UNAVAILABLE'],
};
const TYPE_NAME = { D: 'DANGER AREA', R: 'RESTRICTED AREA', P: 'PROHIBITED AREA', T: 'TEMP RESTRICTED', A: 'RESERVED AREA', M: 'TEMP RESERVED AREA' };

function scheduleCell(label, x, ctx) {
  const { F, now } = ctx;
  if (!x) return `<div class="aib-sched-cell"><div class="aib-sched-label">${label}</div><div class="aib-sched-na">NOT REPORTED</div></div>`;
  return `<div class="aib-sched-cell"><div class="aib-sched-label">${label}</div>
    <div class="aib-sched-time">${esc(F.time(x))}</div>
    <div class="aib-sched-date">${esc(F.relDay(x, now))}</div>
    ${ctx.cfg.show_zulu ? `<div class="aib-sched-zulu">${esc(F.zuluDate(x))} ${esc(F.zulu(x))}</div>` : ''}</div>`;
}

const levelText = (lo, hi) => {
  const norm = s => String(s || '').toUpperCase().replace(/\s+/g, ' ').trim();
  const l = norm(lo) || 'SFC', h = norm(hi);
  return h ? `${l} – ${h}` : l;
};

function renderArea(a, ctx) {
  const [label, sub] = AREA_STATE[a.state] || AREA_STATE.unknown;
  const timed = (a.state === 'active' || a.state === 'scheduled');
  const bottom = timed
    ? `<div class="aib-sched">${scheduleCell(a.state === 'active' ? 'SINCE' : 'START', d(a.start), ctx)}${scheduleCell('END', d(a.end), ctx)}</div>`
    : `<div class="aib-area-idle">${esc(levelText(a.lower, a.upper))}<br><span>${a.distance_nm <= 0.1 ? 'OVERHEAD AIRFIELD' : `${esc(a.distance_nm)} NM ${esc(a.bearing || '')}`}</span></div>`;
  return `<div class="aib-area ${esc(a.state)}">
    <div class="aib-area-head">
      <div class="aib-area-id">${esc(a.id)}</div>
      <div class="aib-area-name">${esc(a.name)}</div>
      <div class="aib-area-type">${esc(a.label || TYPE_NAME[a.type] || 'AIRSPACE')}${a.notam ? ` · ${esc(a.notam)}` : ''}</div>
    </div>
    <div class="aib-area-center"><div class="aib-area-state">${label}</div><div class="aib-area-sub">${sub}</div></div>
    <div class="aib-area-bottom">${bottom}</div>
  </div>`;
}

function renderAirspaceSummary(panel, cfg) {
  const s = panel.summary;
  const label = { hot: 'ACTIVE', warning: 'WARNINGS', scheduled: 'SCHEDULED', cold: 'CLEAR' }[s.state];
  const parts = [];
  if (s.active_areas) parts.push(`${s.active_areas} AREA${s.active_areas > 1 ? 'S' : ''} ACTIVE`);
  if (s.scheduled_areas) parts.push(`${s.scheduled_areas} SCHEDULED`);
  if (s.active_warnings) parts.push(`${s.active_warnings} WARNING${s.active_warnings > 1 ? 'S' : ''} ACTIVE`);
  if (s.scheduled_warnings && !s.active_warnings) parts.push(`${s.scheduled_warnings} WARNING${s.scheduled_warnings > 1 ? 'S' : ''} UPCOMING`);
  return `<div class="aib-summary ${s.state}">
    <div class="aib-summary-left"><div class="aib-summary-name">OTHER AREAS &amp; NAV WARNINGS</div>
    <div class="aib-summary-detail">${parts.length ? parts.join(' · ') : `NOTHING REPORTED WITHIN ${esc(cfg.warning_range_nm)} NM`}</div></div>
    <div class="aib-summary-state">${label}</div></div>`;
}

// ---- radio strip -----------------------------------------------------------------------
export function renderRadio(radio, ctx, compact = false) {
  if (!radio) return '';
  const { F, now } = ctx;
  const groups = radio.groups || [];
  if (!groups.length && !radio.atis) return '';
  const max = compact ? 4 : 6;
  const status = g => {
    const u = d(g.until);
    const far = u && u - now > 6 * 86400000;
    switch (g.status) {
      case 'open': return `<span class="aib-rs open">OPEN${u && !far ? ` · UNTIL ${esc(F.time(u))}` : far ? ' · H24' : ''}</span>`;
      case 'closed': return `<span class="aib-rs closed">CLOSED${g.note === 'NOTAM' ? ' · NOTAM' : ''}${u && !far ? ` · ${g.note === 'NOTAM' ? 'UNTIL' : 'OPENS'} ${esc(F.time(u))}${F.relDay(u, now) !== 'TODAY' ? ' ' + esc(F.relDay(u, now)) : ''}` : ''}</span>`;
      case 'limited': return `<span class="aib-rs limited">HOURS CHANGED · NOTAM</span>`;
      default: return `<span class="aib-rs published">${g.note === 'CLOSES' && u ? `CLOSES ${esc(F.time(u))} · NOTAM` : 'NO NOTAM CHANGES'}</span>`;
    }
  };
  const closingSoon = g => g.note === 'CLOSES' && g.until && g.status !== 'published'
    ? `<span class="aib-rs limited">CLOSES ${esc(F.time(d(g.until)))}</span>` : '';
  const atisReports = radio.atis?.reports || [];
  const atisChip = g => {
    const letters = atisReports.map(r => `<div class="aib-atis-letter ${r.stale ? 'stale' : ''}" title="${esc(r.text)}">
        <div class="aib-atis-l">${esc(r.letter)}</div>
        <div class="aib-atis-meta">${r.kind !== 'ATIS' ? esc(r.kind.slice(0, 3)) + ' · ' : ''}${r.runway ? 'RWY ' + esc(r.runway) + ' · ' : ''}${esc(F.zulu(d(r.received)))}${r.stale ? ' · MAY BE OUT OF DATE' : ''}</div>
      </div>`).join('');
    return `<div class="aib-radio-chip atis">
      <div class="aib-radio-name">${esc(g ? g.name : 'ATIS')}</div>
      <div class="aib-radio-main">${g ? `<span class="aib-radio-freq">${esc(g.freqs.slice(0, 2).join(' / '))}</span>` : ''}${letters || '<span class="aib-rs published">NO TEXT ATIS FEED · LISTEN ON FREQUENCY</span>'}</div>
    </div>`;
  };
  const chips = [];
  const atisGroup = groups.find(g => g.service === 'atis');
  if (atisGroup || atisReports.length) chips.push(atisChip(atisGroup));
  for (const g of groups.filter(g => g.service !== 'atis').slice(0, max - chips.length)) {
    chips.push(`<div class="aib-radio-chip ${esc(g.status)}">
      <div class="aib-radio-name">${esc(g.name)}</div>
      <div class="aib-radio-main"><span class="aib-radio-freq">${esc(g.freqs.slice(0, 2).join(' / '))}</span>${status(g)}${closingSoon(g)}</div>
    </div>`);
  }
  const note = radio.notams_unavailable ? 'NOTAM FEED UNAVAILABLE · STATUS UNKNOWN'
    : `STATUS ESTIMATED FROM NOTAMS${radio.hours_configured ? ' &amp; PUBLISHED HOURS' : ''}`;
  return `<div class="aib-radio ${compact ? 'compact' : ''}">
    <div class="aib-radio-title">${ICON.radio}<span>RADIO</span></div>
    <div class="aib-radio-chips">${chips.join('')}</div>
    <div class="aib-radio-note">${note}</div>
  </div>`;
}

// ---- header ----------------------------------------------------------------------------
function renderHeader(data, ctx) {
  const { F, now, cfg } = ctx;
  const ap = data.airport;
  const wx = data.weather;
  const codes = [ap.icao, ap.iata].filter(Boolean).join(' / ');
  const title = cfg.title || ap.display_name;
  const subtitle = cfg.subtitle || `${codes} · AIRPORT INFORMATION`;
  const wxLine = wx ? [
    wx.wind ? `${ICON.wind}<span>${esc(wx.wind)}</span>` : '',
    wx.qnh ? `<span>Q${esc(wx.qnh)}</span>` : '',
    wx.flight_category ? `<span class="aib-cat ${esc(String(wx.flight_category).toLowerCase())}">${esc(wx.flight_category)}</span>` : '',
  ].filter(Boolean).join('') : '';
  const wxSrc = wx && !wx.is_local ? `<div class="aib-wx-src">METAR ${esc(wx.source_icao)} · ${esc(wx.distance_nm)} NM</div>` : '';
  return `<header class="aib-header">
    <div class="aib-brand">
      <div class="aib-title">${esc(title)}</div>
      <div class="aib-subtitle">${esc(subtitle)}</div>
    </div>
    <div class="aib-header-right">
      <div class="aib-clocks">
        <div class="aib-clock"><div class="aib-clock-time" data-clock="local">${esc(F.time(now))}</div><div class="aib-clock-label">LOCAL · ${esc(F.longDate(now))}</div></div>
        ${cfg.show_zulu ? `<div class="aib-clock zulu"><div class="aib-clock-time" data-clock="utc">${esc(F.zulu(now))}</div><div class="aib-clock-label">UTC</div></div>` : ''}
      </div>
      <div class="aib-wx">
        <div class="aib-temp">${esc(temperature(wx, cfg))}</div>
        <div class="aib-wx-line">${wxLine}</div>
        ${wxSrc}
      </div>
    </div>
  </header>`;
}

// ---- complete board --------------------------------------------------------------------
export function renderBoard(data, opts = {}) {
  const cfg = { ...(data.settings || {}), ...(opts.settings || {}) };
  const now = opts.now || new Date();
  const F = fmt(cfg);
  const ctx = { F, now, cfg };
  const fl = data.flights;
  const arrivals = fl ? fl.arrivals : null;
  const departures = fl ? fl.departures : null;
  const notams = data.notams;
  const panel = data.airspace;
  const unavailable = what => `<div class="aib-unavailable">${what} TEMPORARILY UNAVAILABLE<br><span>Retrying automatically</span></div>`;

  const arrivalsHtml = !arrivals ? unavailable('FLIGHT DATA') : arrivals.length ? arrivals.map(f => renderArrival(f, ctx)).join('') : emptyFlights('NO FLIGHT PLANS SCHEDULED', 'No inbound aircraft currently reported');
  const departuresHtml = !departures ? unavailable('FLIGHT DATA') : departures.length ? departures.map(f => renderDeparture(f, ctx)).join('') : emptyFlights('NO FLIGHT PLANS SCHEDULED', 'No scheduled departures currently reported');
  const notamHtml = !notams ? unavailable('NOTAM FEED') : notams.length ? notams.map(n => renderNotam(n, ctx)).join('') : `<div class="aib-notam-empty">${ICON.check}<div>NO OPERATIONAL NOTAMS REPORTED</div></div>`;
  const airspaceHtml = !panel ? unavailable('AIRSPACE STATUS') : `
      <div class="aib-area-heading">RESTRICTED &amp; DANGER AREAS · ${esc(cfg.airspace_range_nm)} NM</div>
      <div class="aib-area-grid" style="--cols:${Math.max(1, Math.min(3, panel.cards.length || 1))}">${panel.cards.length ? panel.cards.map(a => renderArea(a, ctx)).join('') : `<div class="aib-area-none">NO RESTRICTED OR DANGER AREAS WITHIN ${esc(cfg.airspace_range_nm)} NM</div>`}</div>
      ${renderAirspaceSummary(panel, cfg)}`;

  const src = data.sources || {};
  const upd = x => x ? F.time(d(x)) : '—';
  const wx = data.weather;
  const footer = `<footer class="aib-footer">
    <span>FLIGHTS: FLIGHTAWARE ${esc(upd(src.flightaware?.updated))}${src.flightaware?.error ? ' ⚠' : ''}</span>
    <span>NOTAM: NATS AIS ${esc(upd(src.notam?.updated))}${src.notam?.error ? ' ⚠' : ''}</span>
    <span>WX: ${wx ? `METAR ${esc(wx.source_icao)} ${esc(F.zulu(d(wx.observed)))}` : 'UNAVAILABLE'}</span>
    <span class="aib-footer-warn">INFORMATION ONLY · NOT FOR OPERATIONAL USE · ALWAYS CHECK OFFICIAL SOURCES</span>
  </footer>`;

  const countLabel = n => n === null || n === undefined ? '' : `${n} AIRCRAFT`;
  return `<div class="aib-screen theme-${esc(cfg.theme || 'navy')}">
    ${renderHeader(data, ctx)}
    ${cfg.show_radio === false ? '' : renderRadio(data.radio, ctx)}
    <main class="aib-layout">
      <div class="aib-row aib-top">
        <section class="aib-panel" data-panel="arrivals">
          <div class="aib-panel-header"><span>${ICON.landing}LIVE &amp; EXPECTED ARRIVALS</span><span class="aib-count">${countLabel(arrivals?.length)}</span></div>
          <div class="aib-panel-body aib-scroll">${arrivalsHtml}</div>
        </section>
        <section class="aib-panel" data-panel="departures">
          <div class="aib-panel-header"><span>${ICON.takeoff}EXPECTED DEPARTURES</span><span class="aib-count">${countLabel(departures?.length)}</span></div>
          <div class="aib-panel-body aib-scroll">${departuresHtml}</div>
        </section>
      </div>
      <div class="aib-row aib-bottom">
        <section class="aib-panel" data-panel="notams">
          <div class="aib-panel-header"><span>${ICON.doc}${esc(data.airport.icao || data.airport.iata)} NOTAMS</span><span class="aib-count">${notams ? notams.length : ''}</span></div>
          <div class="aib-panel-body aib-scroll aib-notams">${notamHtml}</div>
        </section>
        <section class="aib-panel" data-panel="activity">
          <div class="aib-panel-header"><span>${ICON.clock}LATEST ACTIVITY</span></div>
          <div class="aib-panel-body aib-activity-grid">${fl ? renderActivity(fl.latest_arrival, true, ctx) + renderActivity(fl.latest_departure, false, ctx) : unavailable('FLIGHT DATA')}</div>
        </section>
        <section class="aib-panel" data-panel="airspace">
          <div class="aib-panel-header"><span>${ICON.shield}LOCAL AIRSPACE</span></div>
          <div class="aib-panel-body aib-airspace">${airspaceHtml}</div>
        </section>
      </div>
    </main>
    ${footer}
  </div>`;
}

// Live clock tick without a full re-render.
export function tickClocks(root, settings = {}) {
  const F = fmt(settings);
  const now = new Date();
  root.querySelectorAll('[data-clock="local"]').forEach(el => { el.textContent = F.time(now); });
  root.querySelectorAll('[data-clock="utc"]').forEach(el => { el.textContent = F.zulu(now); });
}

// Gentle auto-scroll for overflowing panels on wall displays (no touch / mouse).
export function autoScroll(root, { speed = 18, pause = 4000 } = {}) {
  const els = [...root.querySelectorAll('.aib-scroll')];
  const state = new Map(els.map(el => [el, { dir: 1, waitUntil: performance.now() + pause, pos: el.scrollTop }]));
  let last = performance.now(), raf;
  const step = t => {
    const dt = (t - last) / 1000; last = t;
    for (const el of els) {
      const s = state.get(el);
      const max = el.scrollHeight - el.clientHeight;
      if (max <= 4 || el.matches(':hover') || t < s.waitUntil) continue;
      s.pos = Math.max(0, Math.min(max, s.pos + s.dir * speed * dt * (s.dir < 0 ? 4 : 1)));
      el.scrollTop = s.pos;
      if (s.pos >= max || s.pos <= 0) { s.dir *= -1; s.waitUntil = t + pause; }
    }
    raf = requestAnimationFrame(step);
  };
  raf = requestAnimationFrame(step);
  return () => cancelAnimationFrame(raf);
}

export const BOARD_CSS = `
.aib-screen, .aib-screen * { box-sizing: border-box; }
.aib-screen {
  --bg: #08111e; --bg2: #0c1828; --panel: #142234; --panel-head: #1c3045; --card: #213349; --card2: #27394f;
  --line: #3a5067; --line-soft: #2c4258; --text: #f1f5fa; --muted: #a9bfd4; --dim: #7f95ab;
  --blue: #45b7df; --sky: #7dd3fc; --green: #86efac; --green-d: #9bd9b4; --amber: #f3c875; --orange: #f0a34c; --red: #f16b68; --pink: #ff9292;
  width: 100%; height: 100%; display: flex; flex-direction: column; overflow: hidden;
  background: radial-gradient(1200px 600px at 10% -10%, #11243b 0%, transparent 60%), var(--bg);
  color: var(--text); font-family: "Barlow", "Inter", "Segoe UI", Roboto, Arial, Helvetica, sans-serif;
  -webkit-font-smoothing: antialiased; font-variant-numeric: tabular-nums;
}
.aib-screen.theme-midnight { --bg: #05070c; --bg2: #090d15; --panel: #0e131d; --panel-head: #151c29; --card: #182131; --card2: #1d283a; --line: #2b3648; --line-soft: #222c3c; }
.aib-screen.theme-high-contrast { --bg: #000; --panel: #0b0b0b; --panel-head: #161616; --card: #1b1b1b; --card2: #222; --line: #666; --muted: #e0e0e0; --dim: #c0c0c0; }
.aib-ic { width: 1.25em; height: 1.25em; flex: 0 0 auto; vertical-align: -0.22em; }

/* header */
.aib-header { flex: 0 0 auto; display: flex; justify-content: space-between; align-items: center; gap: 16px;
  padding: 10px 22px; background: linear-gradient(180deg, #13233a, #0f1d2f); border-bottom: 2px solid #344b62; }
.aib-brand { min-width: 0; }
.aib-title { font-size: clamp(22px, 2.3vw, 42px); font-weight: 800; letter-spacing: .04em; line-height: 1.05; color: #fff; text-transform: uppercase; }
.aib-subtitle { margin-top: 5px; font-size: clamp(11px, .95vw, 17px); font-weight: 700; letter-spacing: .14em; color: var(--muted); }
.aib-header-right { display: flex; align-items: center; gap: clamp(14px, 2vw, 34px); }
.aib-clocks { display: flex; gap: clamp(12px, 1.6vw, 28px); }
.aib-clock { text-align: right; }
.aib-clock-time { font-size: clamp(22px, 2.2vw, 40px); font-weight: 800; line-height: 1; color: #fff; }
.aib-clock.zulu .aib-clock-time { color: var(--sky); }
.aib-clock-label { margin-top: 4px; font-size: clamp(9px, .7vw, 13px); font-weight: 700; letter-spacing: .1em; color: var(--dim); }
.aib-wx { text-align: right; padding-left: clamp(12px, 1.6vw, 28px); border-left: 1px solid var(--line); }
.aib-temp { font-size: clamp(30px, 3vw, 56px); font-weight: 800; line-height: 1; color: #fff; }
.aib-wx-line { display: flex; gap: 8px; justify-content: flex-end; align-items: center; margin-top: 4px; font-size: clamp(10px, .8vw, 14px); font-weight: 700; color: var(--muted); white-space: nowrap; }
.aib-wx-src { font-size: clamp(8px, .62vw, 11px); color: var(--dim); font-weight: 700; letter-spacing: .06em; margin-top: 2px; }
.aib-cat { padding: 1px 6px; border-radius: 4px; font-weight: 800; color: #08111e; background: var(--green); }
.aib-cat.mvfr { background: #60a5fa; } .aib-cat.ifr { background: var(--red); } .aib-cat.lifr { background: #e879f9; }

/* layout */
.aib-layout { flex: 1 1 auto; min-height: 0; padding: 12px; display: grid; grid-template-rows: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
.aib-row { min-height: 0; min-width: 0; display: grid; gap: 12px; }
.aib-top { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.aib-bottom { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.aib-panel { display: flex; flex-direction: column; min-height: 0; min-width: 0; overflow: hidden;
  background: linear-gradient(180deg, var(--panel), #111e2f); border: 2px solid var(--line); border-radius: 12px; box-shadow: 0 6px 24px rgba(0,0,0,.25); }
.aib-panel-header { flex: 0 0 auto; min-height: 48px; padding: 0 16px; display: flex; align-items: center; justify-content: space-between; gap: 8px;
  background: var(--panel-head); border-bottom: 1px solid var(--line); font-size: clamp(13px, 1.12vw, 21px); font-weight: 800; letter-spacing: .05em; color: #fff; }
.aib-panel-header > span:first-child { display: flex; align-items: center; gap: 10px; min-width: 0; }
.aib-panel-header .aib-ic { color: var(--sky); }
.aib-count { font-size: clamp(10px, .85vw, 15px); color: var(--sky); white-space: nowrap; letter-spacing: .06em; }
.aib-panel-body { flex: 1 1 auto; min-height: 0; min-width: 0; overflow: hidden; }
.aib-scroll { overflow-y: auto; scrollbar-width: thin; scrollbar-color: #536a80 transparent; }
.aib-unavailable { margin: auto; padding: 30px 12px; text-align: center; color: var(--amber); font-weight: 800; font-size: clamp(13px, 1vw, 17px); letter-spacing: .05em; }
.aib-unavailable span { color: var(--dim); font-weight: 600; font-size: .8em; }

/* flights */
[data-panel="arrivals"] .aib-panel-body, [data-panel="departures"] .aib-panel-body { display: flex; flex-direction: column; gap: 10px; padding: 12px; }
.aib-flight { flex: 0 0 auto; min-width: 0; padding: 14px 16px; border-radius: 10px; border: 1px solid #4a6680; border-left: 6px solid var(--blue);
  background: linear-gradient(180deg, var(--card2), var(--card)); }
.aib-flight.enroute { border-left-color: #e3c052; }
.aib-flight.soon { border-color: var(--orange); border-left-color: var(--orange); background: linear-gradient(180deg, #3d2b17, #2e2416); box-shadow: 0 0 0 1px rgba(240,163,76,.3), 0 0 22px rgba(240,163,76,.18); }
.aib-flight.urgent { border-color: var(--red); border-left-color: var(--red); background: linear-gradient(180deg, #45222a, #341c22); animation: aib-pulse 2.2s ease-in-out infinite; }
.aib-flight.departure { border-left-color: #65a9d8; }
.aib-flight.departure.boarding { border-left-color: var(--green); }
.aib-flight-banner { margin: -4px 0 10px; font-size: clamp(10px, .85vw, 15px); font-weight: 800; letter-spacing: .08em; color: var(--orange); }
.aib-flight.urgent .aib-flight-banner { color: var(--pink); }
.aib-flight-top { display: flex; justify-content: space-between; gap: 12px; min-width: 0; }
.aib-flight-left { flex: 1 1 auto; min-width: 0; }
.aib-flight-right { flex: 0 0 auto; min-width: 100px; text-align: right; }
.aib-flight-ident { font-size: clamp(22px, 2vw, 36px); font-weight: 800; line-height: 1.1; color: #fff; letter-spacing: .02em; overflow-wrap: anywhere; }
.aib-flight-type { margin-top: 4px; font-size: clamp(12px, 1.05vw, 19px); color: #dce7f1; line-height: 1.3; overflow-wrap: anywhere; }
.aib-op { color: var(--muted); }
.aib-flight-place { margin-top: 7px; font-size: clamp(11px, .95vw, 17px); font-weight: 700; color: var(--muted); overflow-wrap: anywhere; }
.aib-flight-place strong { color: #fff; }
.aib-code { color: var(--orange); font-weight: 800; margin-left: 4px; }
.aib-flight-clock { font-size: clamp(22px, 2vw, 36px); font-weight: 800; color: #fff; white-space: nowrap; line-height: 1.1; }
.aib-flight-day { margin-top: 3px; font-size: clamp(10px, .78vw, 14px); font-weight: 700; color: var(--dim); white-space: nowrap; }
.aib-flight-state { margin-top: 6px; font-size: clamp(10px, .85vw, 15px); font-weight: 800; color: #a9d4f0; letter-spacing: .05em; }
.aib-flight.soon .aib-flight-state, .aib-flight.enroute .aib-flight-state { color: var(--amber); }
.aib-flight-remaining { margin-top: 6px; font-size: clamp(11px, .9vw, 16px); font-weight: 800; color: var(--amber); white-space: nowrap; }
.aib-flight-remaining.dep { color: var(--green); }
.aib-progress { height: 8px; margin-top: 12px; border-radius: 10px; background: #0e1c2a; overflow: hidden; }
.aib-progress-fill { height: 100%; border-radius: 10px; background: linear-gradient(90deg, #3a9cc4, #57c8ef); }
.aib-flight.soon .aib-progress-fill { background: linear-gradient(90deg, #d9822f, #f7a23c); }
.aib-flight.urgent .aib-progress-fill { background: linear-gradient(90deg, #d94a47, #ff7a77); }
.aib-empty { flex: 1 1 auto; min-height: 110px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; text-align: center; color: var(--green-d); }
.aib-empty-icon .aib-ic { width: clamp(38px, 4vw, 70px); height: clamp(38px, 4vw, 70px); opacity: .75; color: var(--blue); }
.aib-empty-main { font-size: clamp(16px, 1.5vw, 28px); font-weight: 800; letter-spacing: .06em; }
.aib-empty-sub { font-size: clamp(11px, .9vw, 16px); color: var(--muted); }

/* latest activity */
.aib-activity-grid { padding: 12px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.aib-activity { min-width: 0; min-height: 0; padding: 13px; display: flex; flex-direction: column; gap: 6px; overflow: hidden; border-radius: 10px;
  background: linear-gradient(180deg, var(--card2), var(--card)); border: 1px solid #4b6075; }
.aib-activity-label { display: flex; align-items: center; justify-content: space-between; gap: 6px; font-size: clamp(10px, .82vw, 15px); font-weight: 800; letter-spacing: .06em; color: #b7c8d9; }
.aib-activity-label .aib-ic { width: clamp(20px, 1.6vw, 30px); height: clamp(20px, 1.6vw, 30px); }
.aib-activity.arrival .aib-activity-label .aib-ic, .aib-activity.arrival .aib-activity-status { color: var(--green); }
.aib-activity.departure .aib-activity-label .aib-ic, .aib-activity.departure .aib-activity-status { color: var(--sky); }
.aib-activity-ident { font-size: clamp(21px, 1.9vw, 34px); font-weight: 800; color: #fff; line-height: 1.1; overflow-wrap: anywhere; }
.aib-activity-type { font-size: clamp(12px, 1.05vw, 19px); font-weight: 700; color: #fff; line-height: 1.25; overflow-wrap: anywhere; }
.aib-activity-place { font-size: clamp(11px, .9vw, 16px); font-weight: 700; line-height: 1.3; color: var(--muted); overflow-wrap: anywhere; }
.aib-activity-name { margin-top: 2px; color: #fff; font-weight: 600; font-size: .95em; }
.aib-pending { color: var(--dim); font-style: italic; font-weight: 500; }
.aib-activity-bottom { margin-top: auto; padding-top: 9px; border-top: 1px solid #41556a; display: grid; grid-template-columns: 1fr auto; align-items: end; row-gap: 2px; }
.aib-activity-time { font-size: clamp(18px, 1.6vw, 30px); font-weight: 800; color: #fff; }
.aib-activity-status { display: flex; align-items: center; gap: 5px; font-size: clamp(10px, .8vw, 14px); font-weight: 800; letter-spacing: .06em; justify-self: end; }
.aib-activity-status .aib-ic { width: 1.1em; height: 1.1em; }
.aib-activity-date { grid-column: 1 / -1; font-size: clamp(10px, .8vw, 14px); color: #b4c7d8; font-weight: 600; }
.aib-activity-empty { margin: auto 0; font-size: clamp(11px, .85vw, 14px); font-weight: 800; text-align: center; color: #9fb3c7; }

/* notams */
.aib-notams { padding: 10px; }
.aib-notam { margin-bottom: 9px; padding: 11px 12px; border: 1px solid #526578; border-left: 4px solid #e5b65c; border-radius: 8px; background: var(--card); }
.aib-notam.closure, .aib-notam.fuel { border-left-color: var(--red); }
.aib-notam.surface { border-left-color: var(--orange); background: #303746; }
.aib-notam.lighting, .aib-notam.navaid { border-left-color: var(--amber); }
.aib-notam.general, .aib-notam.hours, .aib-notam.works { border-left-color: var(--blue); }
.aib-notam.upcoming { opacity: .85; border-style: dashed; border-left-style: solid; }
.aib-notam-top { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 6px; font-size: clamp(9px, .72vw, 13px); font-weight: 800; letter-spacing: .05em; color: #f0ca82; }
.aib-notam-state { color: #9ce5b5; white-space: nowrap; }
.aib-notam-state.upcoming { color: var(--sky); }
.aib-notam-title { color: #fff; font-size: clamp(13px, 1.02vw, 19px); font-weight: 800; line-height: 1.25; overflow-wrap: anywhere; }
.aib-notam-cond-title { margin: 8px 0 5px; color: #b7c9da; font-size: clamp(8px, .62vw, 11px); font-weight: 800; }
.aib-thirds { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 5px; padding: 7px; border-radius: 7px; background: #182739; }
.aib-third { text-align: center; display: flex; flex-direction: column; gap: 3px; font-size: clamp(8px, .62vw, 11px); font-weight: 700; color: #b9c9da; }
.aib-third strong { font-size: clamp(10px, .78vw, 14px); }
.aib-third.good strong { color: #9ce5b5; } .aib-third.medium strong { color: #ffd18a; } .aib-third.caution strong { color: #ff9c80; } .aib-third.poor strong { color: #ff7777; }
.aib-notam-text { margin-top: 6px; font-size: clamp(10px, .74vw, 13px); color: #b9c9da; line-height: 1.35; white-space: pre-wrap; overflow-wrap: anywhere; font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace; }
.aib-notam-dates { display: flex; flex-direction: column; gap: 2px; margin-top: 8px; padding-top: 6px; border-top: 1px solid #526578; font-size: clamp(9px, .7vw, 12px); color: #b6c9db; line-height: 1.35; }
.aib-notam-dates span { display: inline-block; min-width: 46px; font-weight: 800; color: var(--dim); }
.aib-notam-empty { padding: 30px 10px; display: flex; flex-direction: column; align-items: center; gap: 10px; text-align: center; font-size: clamp(13px, 1vw, 18px); font-weight: 800; color: #a2d4b6; }
.aib-notam-empty .aib-ic { width: 40px; height: 40px; color: var(--green); }

/* airspace */
.aib-airspace { padding: 11px; display: flex; flex-direction: column; gap: 9px; }
.aib-area-heading { flex: 0 0 auto; font-size: clamp(9px, .75vw, 14px); font-weight: 800; letter-spacing: .08em; color: #b8c8d9; }
.aib-area-grid { flex: 1 1 auto; min-height: 0; display: grid; grid-template-columns: repeat(var(--cols, 2), minmax(0, 1fr)); gap: 9px; }
.aib-area-none { grid-column: 1 / -1; margin: auto; text-align: center; color: var(--green-d); font-weight: 800; font-size: clamp(12px, .95vw, 17px); }
.aib-area { min-width: 0; min-height: 0; padding: 10px 11px; display: flex; flex-direction: column; gap: 6px; overflow: hidden; border-radius: 10px; border: 2px solid #607668; background: #26362f; }
.aib-area.cold { background: linear-gradient(180deg, #273b33, #22322b); border-color: #607668; }
.aib-area.scheduled { background: linear-gradient(180deg, #45391f, #3a301d); border-color: #e3b15c; }
.aib-area.active { background: linear-gradient(180deg, #4a2529, #3d2025); border-color: var(--red); animation: aib-pulse 2.2s ease-in-out infinite; }
.aib-area.permanent { background: linear-gradient(180deg, #3d2536, #33202e); border-color: #c06aa0; }
.aib-area.published { background: linear-gradient(180deg, #3a3626, #312e22); border-color: #a99a62; }
.aib-area.unknown { background: #30333c; border-color: #80858d; }
.aib-area-head { flex: 0 0 auto; min-width: 0; }
.aib-area-id { font-size: clamp(14px, 1.15vw, 21px); font-weight: 800; color: #fff; }
.aib-area-name { font-size: clamp(10px, .78vw, 14px); font-weight: 700; color: #dbe5ee; overflow-wrap: anywhere; line-height: 1.2; }
.aib-area-type { margin-top: 2px; font-size: clamp(8px, .6vw, 11px); font-weight: 700; color: var(--dim); letter-spacing: .05em; overflow-wrap: anywhere; }
.aib-area-center { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; text-align: center; }
.aib-area-state { font-size: clamp(17px, 1.6vw, 30px); font-weight: 800; letter-spacing: .03em; line-height: 1.05; }
.aib-area.cold .aib-area-state { color: var(--green-d); } .aib-area.scheduled .aib-area-state { color: var(--amber); }
.aib-area.active .aib-area-state { color: var(--pink); } .aib-area.permanent .aib-area-state { color: #f0a6d3; }
.aib-area.published .aib-area-state { color: #e6d58e; } .aib-area.unknown .aib-area-state { color: #c4c8d0; }
.aib-area-sub { font-size: clamp(8px, .65vw, 12px); font-weight: 800; color: #c6d1dd; letter-spacing: .04em; }
.aib-area-bottom { flex: 0 0 auto; border-top: 1px solid rgba(255,255,255,.18); padding-top: 7px; }
.aib-area-idle { text-align: center; font-size: clamp(10px, .78vw, 14px); font-weight: 800; color: #dbe5ee; line-height: 1.35; }
.aib-area-idle span { color: var(--dim); font-weight: 700; font-size: .9em; }
.aib-sched { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
.aib-sched-label { margin-bottom: 3px; font-size: clamp(8px, .62vw, 11px); font-weight: 800; color: #d8b9a2; }
.aib-sched-time { font-size: clamp(13px, 1.05vw, 19px); font-weight: 800; color: #fff; white-space: nowrap; }
.aib-sched-date { font-size: clamp(9px, .7vw, 12px); font-weight: 700; color: #e3e5e9; }
.aib-sched-zulu { font-size: clamp(8px, .62vw, 11px); font-weight: 700; color: #b8c9d9; }
.aib-sched-na { font-size: 11px; color: #b7c7d8; }
.aib-summary { flex: 0 0 auto; min-height: 50px; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 7px 13px; border-radius: 9px; border: 1px solid #607668; background: #26362f; }
.aib-summary-name { font-size: clamp(11px, .9vw, 16px); font-weight: 800; color: #fff; }
.aib-summary-detail { margin-top: 2px; font-size: clamp(8px, .65vw, 12px); font-weight: 700; color: #c6d1dd; letter-spacing: .03em; }
.aib-summary-state { flex: 0 0 auto; font-size: clamp(14px, 1.2vw, 22px); font-weight: 800; color: var(--green-d); }
.aib-summary.hot { background: #422327; border-color: var(--red); } .aib-summary.hot .aib-summary-state { color: var(--pink); }
.aib-summary.warning { background: #3d2d1b; border-color: var(--orange); } .aib-summary.warning .aib-summary-state { color: var(--orange); }
.aib-summary.scheduled { background: #403521; border-color: #e3b15c; } .aib-summary.scheduled .aib-summary-state { color: var(--amber); }

/* radio strip */
.aib-radio { flex: 0 0 auto; display: flex; align-items: stretch; gap: 10px; padding: 8px 12px 0; min-width: 0; }
.aib-radio-title { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; padding: 0 10px;
  border-radius: 10px; background: var(--panel-head); border: 1px solid var(--line); color: var(--sky); font-size: clamp(9px, .7vw, 13px); font-weight: 800; letter-spacing: .1em; }
.aib-radio-title .aib-ic { width: clamp(18px, 1.4vw, 26px); height: clamp(18px, 1.4vw, 26px); }
.aib-radio-chips { flex: 1 1 auto; min-width: 0; display: flex; gap: 8px; overflow: hidden; }
.aib-radio-chip { flex: 1 1 0; min-width: 0; padding: 6px 12px; border-radius: 10px; background: linear-gradient(180deg, var(--card2), var(--card)); border: 1px solid #41586f; border-left: 4px solid #607a92; }
.aib-radio-chip.open { border-left-color: var(--green); } .aib-radio-chip.closed { border-left-color: var(--red); }
.aib-radio-chip.limited { border-left-color: var(--orange); } .aib-radio-chip.atis { border-left-color: var(--sky); flex-grow: 1.6; }
.aib-radio-name { font-size: clamp(9px, .7vw, 13px); font-weight: 800; letter-spacing: .06em; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-transform: uppercase; }
.aib-radio-main { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; row-gap: 2px; margin-top: 2px; }
.aib-radio-freq { font-size: clamp(16px, 1.35vw, 26px); font-weight: 800; color: #fff; white-space: nowrap; }
.aib-rs { font-size: clamp(9px, .68vw, 12px); font-weight: 800; letter-spacing: .05em; padding: 2px 7px; border-radius: 5px; white-space: nowrap; }
.aib-rs.open { color: #08111e; background: var(--green); } .aib-rs.closed { color: #fff; background: #b8403d; }
.aib-rs.limited { color: #08111e; background: var(--orange); } .aib-rs.published { color: var(--muted); background: rgba(255,255,255,.07); }
.aib-atis-letter { display: flex; align-items: center; gap: 7px; }
.aib-atis-l { width: clamp(24px, 1.9vw, 36px); height: clamp(24px, 1.9vw, 36px); display: grid; place-items: center; border-radius: 6px; background: var(--sky); color: #08111e; font-size: clamp(16px, 1.35vw, 26px); font-weight: 800; }
.aib-atis-letter.stale .aib-atis-l { background: #7f95ab; }
.aib-atis-meta { font-size: clamp(9px, .66vw, 12px); font-weight: 800; color: var(--muted); letter-spacing: .04em; line-height: 1.2; max-width: 11em; }
.aib-radio-note { flex: 0 0 auto; align-self: center; max-width: 9em; font-size: clamp(8px, .58vw, 11px); font-weight: 700; color: var(--dim); letter-spacing: .05em; line-height: 1.25; text-align: right; }
.aib-radio.compact { padding: 0; flex-wrap: wrap; } .aib-radio.compact .aib-radio-title { display: none; }
.aib-radio.compact .aib-radio-chips { flex-wrap: wrap; } .aib-radio.compact .aib-radio-chip { flex: 1 1 45%; }
.aib-radio.compact .aib-radio-note { max-width: none; text-align: left; }

/* footer */
.aib-footer { flex: 0 0 auto; display: flex; gap: 18px; align-items: center; padding: 5px 16px 7px; font-size: clamp(8px, .62vw, 12px); font-weight: 700; letter-spacing: .06em; color: var(--dim); }
.aib-footer-warn { margin-left: auto; color: #c7a76a; }

@keyframes aib-pulse { 0%, 100% { box-shadow: inset 0 0 0 0 rgba(241,107,104,.1); } 50% { box-shadow: inset 0 0 0 3px rgba(241,107,104,.42); } }
@media (prefers-reduced-motion: reduce) { .aib-flight.urgent, .aib-area.active { animation: none; } }

@media (max-height: 820px) and (min-width: 1001px) {
  .aib-header { padding: 7px 16px; } .aib-layout { padding: 8px; gap: 8px; } .aib-row { gap: 8px; }
  .aib-panel-header { min-height: 40px; } .aib-activity { gap: 3px; padding: 10px; } .aib-area { gap: 4px; padding: 8px; }
}

/* phone / tablet portrait: stacked, scrolling page (like the mobile dashboard) */
@media (max-width: 1000px), (orientation: portrait) and (max-width: 1200px) {
  .aib-screen { height: auto; min-height: 100%; overflow: visible; }
  .aib-header { flex-wrap: wrap; padding: 14px 16px; }
  .aib-header-right { width: 100%; justify-content: space-between; }
  .aib-title { font-size: 24px; } .aib-subtitle { font-size: 12px; }
  .aib-clock-time { font-size: 24px; } .aib-temp { font-size: 34px; }
  .aib-layout { display: flex; flex-direction: column; padding: 10px; gap: 12px; }
  .aib-row { display: flex; flex-direction: column; gap: 12px; }
  .aib-panel-body { overflow: visible; }
  .aib-scroll { max-height: 75vh; overflow-y: auto; }
  .aib-panel-header { font-size: 16px; } .aib-count { font-size: 13px; }
  .aib-flight-ident { font-size: 26px; } .aib-flight-clock { font-size: 26px; }
  .aib-flight-type { font-size: 15px; } .aib-flight-place { font-size: 14px; } .aib-flight-state, .aib-flight-day, .aib-flight-remaining { font-size: 12px; }
  .aib-activity-ident { font-size: 24px; } .aib-activity-type { font-size: 15px; } .aib-activity-time { font-size: 22px; }
  .aib-area-grid { min-height: 230px; } .aib-area-state { font-size: 22px; } .aib-area-sub, .aib-area-type, .aib-sched-label { font-size: 10px; }
  .aib-notam-title { font-size: 15px; } .aib-notam-text { font-size: 12px; } .aib-notam-dates, .aib-notam-top { font-size: 11px; }
  .aib-footer { flex-wrap: wrap; gap: 6px 14px; font-size: 10px; padding: 8px 12px 14px; }
  .aib-footer-warn { margin-left: 0; }
  .aib-radio { flex-wrap: wrap; padding: 10px 10px 0; } .aib-radio-title { flex-direction: row; padding: 6px 10px; }
  .aib-radio-chips { flex-wrap: wrap; } .aib-radio-chip { flex: 1 1 100%; } .aib-radio-freq { font-size: 20px; }
  .aib-radio-note { max-width: none; text-align: left; } .aib-rs, .aib-atis-meta { font-size: 11px; }
}
@media (max-width: 520px) {
  .aib-clock.zulu { display: none; }
  .aib-activity-grid { grid-template-columns: 1fr; }
}
`;
