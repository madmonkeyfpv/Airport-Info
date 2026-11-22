// Airport Info — weather station page (wind rose with runways + current conditions).
// Pure renderer like board.js: renderWeather(data) -> HTML, WEATHER_CSS -> stylesheet.
// Shared by the website (index.html ?view=weather|rotate) and the Home Assistant card (view: weather|rotate).
import { esc, fmt } from './board.js';

const C = 200;           // SVG centre (viewBox 0 0 400 400)
const R_RING = 178;      // outer ring radius
const rad = deg => (deg - 90) * Math.PI / 180;   // 0° = north, clockwise
const pt = (deg, r) => [C + r * Math.cos(rad(deg)), C + r * Math.sin(rad(deg))];
const f1 = n => Number(n).toFixed(1);

function arcPath(from, to, r) {
  let sweep = ((to - from) % 360 + 360) % 360;
  if (sweep === 0) sweep = 360;
  const [x1, y1] = pt(from, r), [x2, y2] = pt(from + sweep, r);
  return `M${f1(x1)} ${f1(y1)} A${r} ${r} 0 ${sweep > 180 ? 1 : 0} 1 ${f1(x2)} ${f1(y2)}`;
}

function star() {
  // 8-point compass star: long cardinal points, short intercardinal points
  const pts = [];
  for (let i = 0; i < 16; i++) {
    const deg = i * 22.5;
    const r = i % 4 === 0 ? 150 : i % 2 === 0 ? 92 : 34;
    pts.push(pt(deg, r).map(f1).join(','));
  }
  const halves = [];
  for (let i = 0; i < 8; i++) {
    const deg = i * 45, r = i % 2 === 0 ? 150 : 92;
    const [tx, ty] = pt(deg, r), [lx, ly] = pt(deg - 22.5, 34);
    halves.push(`<path d="M${C} ${C} L${f1(tx)} ${f1(ty)} L${f1(lx)} ${f1(ly)} Z" class="wx-star-shade"/>`);
  }
  return `<polygon points="${pts.join(' ')}" class="wx-star"/>${halves.join('')}`;
}

function ticks() {
  let out = '';
  for (let d = 0; d < 360; d += 5) {
    const major = d % 30 === 0, mid = d % 10 === 0;
    const [x1, y1] = pt(d, R_RING - (major ? 16 : mid ? 10 : 6)), [x2, y2] = pt(d, R_RING);
    out += `<line x1="${f1(x1)}" y1="${f1(y1)}" x2="${f1(x2)}" y2="${f1(y2)}" class="wx-tick ${major ? 'major' : ''}"/>`;
  }
  for (let d = 0; d < 360; d += 30) {
    const label = { 0: 'N', 90: 'E', 180: 'S', 270: 'W' }[d] || String(d / 10).padStart(2, '0');
    const [x, y] = pt(d, R_RING + 13);
    out += `<text x="${f1(x)}" y="${f1(y)}" class="wx-ring-label ${d % 90 === 0 ? 'cardinal' : ''}">${label}</text>`;
  }
  return out;
}

function runwaysSvg(runways) {
  if (!runways?.length) return '';
  const longest = Math.max(...runways.map(r => r.length_ft || 0), 1);
  // Group near-parallel runways so they are drawn side by side.
  const groups = [];
  for (const r of runways.slice(0, 4)) {
    const g = groups.find(g => Math.abs((((g.hdg - r.le_hdg) % 180) + 270) % 180 - 90) < 8);
    if (g) g.items.push(r); else groups.push({ hdg: r.le_hdg, items: [r] });
  }
  let out = '';
  // Parallel runways: L is left of the le heading (-x in the rotated frame), R right; unsuffixed opposite any L/R.
  const side = r => /L$/.test(r.le) ? -1 : /R$/.test(r.le) ? 1 : 0;
  for (const g of groups) {
    const hasL = g.items.some(r => side(r) < 0), hasR = g.items.some(r => side(r) > 0);
    g.items.sort((a, b) => (side(a) || (hasL ? 1 : hasR ? -1 : 0)) - (side(b) || (hasL ? 1 : hasR ? -1 : 0)));
    g.items.forEach((r, i) => {
      const len = 120 + 110 * ((r.length_ft || longest * .6) / longest);
      const grass = /GRS|GRASS|TURF|GRE/i.test(r.surface || '');
      const w = grass ? 22 : 30;
      const offset = (i - (g.items.length - 1) / 2) * 36;
      const num = (txt, y, flip) => `<text x="0" y="${y}" class="wx-rwy-num" transform="rotate(${flip ? 180 : 0} 0 ${y})">${esc(txt)}</text>`;
      const bars = y => [-9, -4.5, 0, 4.5, 9].map(x => `<rect x="${x - 1.4}" y="${y}" width="2.8" height="12" class="wx-rwy-bar"/>`).join('');
      out += `<g transform="translate(${C} ${C}) rotate(${r.le_hdg}) translate(${offset} 0)">
        <rect x="${-w / 2}" y="${-len / 2}" width="${w}" height="${len}" rx="2" class="wx-rwy ${grass ? 'grass' : ''}"/>
        ${grass ? '' : `<line x1="0" y1="${-len / 2 + 46}" x2="0" y2="${len / 2 - 46}" class="wx-rwy-cl"/>`}
        ${grass ? '' : bars(len / 2 - 16) + bars(-len / 2 + 4)}
        ${num(r.le, len / 2 - 26, false)}
        ${num(r.he, -len / 2 + 26, true)}
      </g>`;
    });
  }
  return out;
}

function windSvg(wx) {
  if (!wx || wx.wind_kt === null || wx.wind_kt === undefined) return '';
  if (!wx.wind_kt) return `<text x="${C}" y="${C + 6}" class="wx-calm">CALM</text>`;
  const dir = wx.wind_dir;
  if (dir === null || dir === undefined) {
    return `<path d="${arcPath(0, 359.9, R_RING - 26)}" class="wx-wind-arc vrb"/><text x="${C}" y="${C + 6}" class="wx-calm">VRB ${esc(wx.wind_kt)}KT</text>`;
  }
  const from = wx.wind_var_from ?? dir - 8, to = wx.wind_var_to ?? dir + 8;
  const [lx, ly] = pt(dir, R_RING - 52);
  const [ax, ay] = pt(dir, R_RING - 30), [bx, by] = pt(dir - 4.5, R_RING - 14), [cx, cy] = pt(dir + 4.5, R_RING - 14);
  const [s1x, s1y] = pt(dir, R_RING - 40), [s2x, s2y] = pt(dir, 60);
  return `<path d="${arcPath(from, to, R_RING - 26)}" class="wx-wind-arc"/>
    <line x1="${f1(s1x)}" y1="${f1(s1y)}" x2="${f1(s2x)}" y2="${f1(s2y)}" class="wx-wind-line"/>
    <polygon points="${f1(ax)},${f1(ay)} ${f1(bx)},${f1(by)} ${f1(cx)},${f1(cy)}" class="wx-wind-head"/>
    <text x="${f1(lx)}" y="${f1(ly - 4)}" class="wx-wind-label">${String(dir).padStart(3, '0')}</text>
    <text x="${f1(lx)}" y="${f1(ly + 14)}" class="wx-wind-label">${wx.wind_kt}${wx.gust_kt ? 'G' + wx.gust_kt : ''} KT</text>`;
}

function components(wx, runways) {
  if (!wx || !wx.wind_kt || wx.wind_dir === null || wx.wind_dir === undefined || !runways?.length) return [];
  const ends = [];
  for (const r of runways) {
    for (const [ident, hdg] of [[r.le, r.le_hdg], [r.he, (r.le_hdg + 180) % 360]]) {
      const a = (wx.wind_dir - hdg) * Math.PI / 180;
      ends.push({ ident, head: Math.round(wx.wind_kt * Math.cos(a)), cross: Math.round(wx.wind_kt * Math.sin(a)), gustCross: wx.gust_kt ? Math.round(Math.abs(wx.gust_kt * Math.sin(a))) : null });
    }
  }
  return ends.sort((a, b) => b.head - a.head);
}

function rvrText(wx) {
  if (!wx) return '—';
  if (!wx.rvr?.length) return `<span class="wx-muted">NOT REPORTED</span>`;
  const unit = r => r.feet ? 'FT' : 'M';
  const val = (n, q) => `${q === 'above' ? '>' : q === 'below' ? '<' : ''}${n}`;
  const trend = { up: '↑', down: '↓', steady: '→' };
  const src = wx.is_local ? '' : ` <small>${esc(wx.source_icao)}</small>`;
  return wx.rvr.map(r => `<span class="wx-rvr">RWY ${esc(r.runway)} ${val(r.min_m, r.min_qual)}${r.max_m ? '–' + val(r.max_m, r.max_qual) : ''} ${unit(r)}${r.tendency ? ' ' + trend[r.tendency] : ''}</span>`).join('') + src;
}

export function renderWeather(data, opts = {}) {
  const cfg = { ...(data.settings || {}), ...(opts.settings || {}) };
  const now = opts.now || new Date();
  const F = fmt(cfg);
  const ap = data.airport;
  const wx = data.weather;
  const runways = ap.runways || [];
  const tUnit = cfg.temp_unit === 'F' ? 'F' : 'C';
  const temp = c => c === null || c === undefined ? '—' : tUnit === 'F' ? `${(c * 9 / 5 + 32).toFixed(1)} °F` : `${Number(c).toFixed(1)} °C`;
  const utcDate = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: '2-digit', month: '2-digit', year: 'numeric' }).format(now);
  const utcSecs = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(now);
  const comps = components(wx, runways);
  const best = comps[0];
  const obs = wx?.observed ? new Date(wx.observed) : null;
  const ageMin = obs ? Math.round((now - obs) / 60000) : null;

  const row = (label, value, cls = '') => `<div class="wx-row"><div class="wx-label">${label}</div><div class="wx-value ${cls}">${value}</div></div>`;
  const windText = !wx ? '—' : !wx.wind_kt ? 'CALM' : `${wx.wind_dir === null || wx.wind_dir === undefined ? 'VRB' : String(wx.wind_dir).padStart(3, '0')} @ ${wx.wind_kt} KT${wx.gust_kt ? ` G${wx.gust_kt}` : ''}${wx.wind_var_from !== null && wx.wind_var_from !== undefined ? ` <small>${String(wx.wind_var_from).padStart(3, '0')}V${String(wx.wind_var_to).padStart(3, '0')}</small>` : ''}`;
  const compHtml = comps.length ? `<div class="wx-comps">${comps.map((c, i) => `
      <div class="wx-comp ${i === 0 ? 'best' : ''}">
        <div class="wx-comp-rwy">RWY ${esc(c.ident)}</div>
        <div class="wx-comp-val">${c.head >= 0 ? `${c.head} KT HEAD` : `${-c.head} KT TAIL`}</div>
        <div class="wx-comp-val x">${Math.abs(c.cross)} KT X-WIND ${c.cross === 0 ? '' : c.cross > 0 ? 'R' : 'L'}${c.gustCross ? ` (G${c.gustCross})` : ''}</div>
      </div>`).join('')}</div>` : '';

  const srcLine = wx ? `METAR ${esc(wx.source_icao)}${wx.is_local ? '' : ` (${esc(wx.source_name || '')}) · ${esc(wx.distance_nm)} NM`} · OBSERVED ${esc(F.zulu(obs))}${ageMin !== null ? ` · ${ageMin} MIN AGO` : ''}` : 'NO METAR WITHIN 40 NM';

  return `<div class="wx-screen theme-${esc(cfg.theme || 'navy')}">
    <section class="wx-left">
      <div class="wx-title">${esc(cfg.title || ap.name)}</div>
      <div class="wx-rose-wrap">
        <svg class="wx-rose" viewBox="-12 -12 424 424" role="img" aria-label="Wind and runway diagram">
          <circle cx="${C}" cy="${C}" r="${R_RING}" class="wx-ring-bg"/>
          <circle cx="${C}" cy="${C}" r="${R_RING - 26}" class="wx-ring-inner"/>
          ${ticks()}
          ${star()}
          ${runwaysSvg(runways)}
          ${windSvg(wx)}
        </svg>
      </div>
      <div class="wx-src">WIND TRUE · ${srcLine}</div>
      ${best ? `<div class="wx-best">FAVOURED RUNWAY <strong>${esc(best.ident)}</strong></div>` : ''}
    </section>
    <section class="wx-right">
      <div class="wx-clock-row">
        <div><span class="wx-label">UTC</span> <span class="wx-clock" data-clock="utc-seconds">${esc(utcSecs)} Z</span></div>
        <div class="wx-clock" data-clock="utc-date">${esc(utcDate)}</div>
      </div>
      <div class="wx-clock-row local"><div><span class="wx-label">LOCAL</span> <span class="wx-clock small" data-clock="local">${esc(F.time(now))}</span></div><div class="wx-label">${esc(F.longDate(now))}</div></div>
      <div class="wx-table">
        ${row('WIND (TRUE)', windText)}
        ${row('TEMPERATURE', esc(temp(wx?.temp_c)))}
        ${row('DEW POINT', esc(temp(wx?.dewpoint_c)))}
        ${wx?.humidity !== undefined ? row('HUMIDITY', `${esc(wx.humidity)} %`) : ''}
        ${row('QNH', wx?.qnh ? `${esc(wx.qnh)} hPa <small>${esc(wx.qnh_inhg?.toFixed(2))} inHg</small>` : '—')}
        ${wx?.qfe ? row(`QFE <small>${esc(ap.elev)} FT</small>`, `${esc(wx.qfe)} hPa`) : ''}
        ${row('RVR', rvrText(wx))}
        ${row('VISIBILITY', esc(wx?.visibility_text || '—'))}
        ${row('SKY CONDITION', esc(wx?.sky || '—'))}
        ${wx?.weather ? row('WEATHER', esc(wx.weather)) : ''}
        ${row('FLIGHT RULES', wx?.flight_category ? `<span class="aib-cat ${esc(String(wx.flight_category).toLowerCase())}">${esc(wx.flight_category)}</span>` : '—')}
      </div>
      ${compHtml}
      <div class="wx-raw">${wx?.raw ? esc(wx.raw) : ''}</div>
      <div class="wx-foot">INFORMATION ONLY · NOT FOR OPERATIONAL USE · OBTAIN AN OFFICIAL BRIEFING</div>
    </section>
  </div>`;
}

export function tickWeatherClock(root) {
  const now = new Date();
  const s = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(now);
  root.querySelectorAll('[data-clock="utc-seconds"]').forEach(el => { el.textContent = `${s} Z`; });
}

export const WEATHER_CSS = `
.wx-screen, .wx-screen * { box-sizing: border-box; }
.wx-screen {
  --bg: #0b1324; --panel: #111a30; --gold: #e3b25c; --text: #e8eef6; --label: #d5dde8; --val: #7fb6ff; --dim: #7f95ab; --line: #2a3a55;
  width: 100%; height: 100%; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 2vw; padding: 2.2vh 2.4vw;
  background: radial-gradient(900px 700px at 25% 50%, #16223f 0%, transparent 70%), var(--bg); color: var(--text);
  font-family: "Barlow", "Inter", "Segoe UI", Roboto, Arial, sans-serif; font-variant-numeric: tabular-nums; overflow: hidden;
}
.wx-screen.theme-midnight { --bg: #05070c; } .wx-screen.theme-high-contrast { --bg: #000; --val: #9cd0ff; }
.wx-left { min-width: 0; min-height: 0; display: flex; flex-direction: column; align-items: center; }
.wx-title { font-size: clamp(22px, 2.4vw, 46px); font-weight: 600; color: var(--gold); text-align: center; letter-spacing: .01em; }
.wx-rose-wrap { flex: 1 1 auto; min-height: 0; width: 100%; display: flex; align-items: center; justify-content: center; padding: 1vh 0; }
.wx-rose { height: 100%; max-height: 100%; width: auto; max-width: 100%; aspect-ratio: 1; overflow: visible; }
.wx-ring-bg { fill: #1b2438; stroke: #2e3c58; stroke-width: 2; }
.wx-ring-inner { fill: #141c2e; stroke: #34425f; stroke-width: 1.5; }
.wx-tick { stroke: #5f6f8c; stroke-width: 1.2; } .wx-tick.major { stroke: #b9c4d6; stroke-width: 2; }
.wx-ring-label { fill: #8d9bb3; font-size: 11px; font-weight: 700; text-anchor: middle; dominant-baseline: middle; }
.wx-ring-label.cardinal { fill: #e8eef6; font-size: 14px; }
.wx-star { fill: #3a4560; } .wx-star-shade { fill: #2a3350; }
.wx-rwy { fill: #4a4033; stroke: var(--gold); stroke-width: 2; } .wx-rwy.grass { fill: #2f4a2c; stroke: #8fbf6a; }
.wx-rwy-cl { stroke: #f3ead8; stroke-width: 1.6; stroke-dasharray: 9 7; }
.wx-rwy-bar { fill: #f3ead8; }
.wx-rwy-num { fill: #ffffff; font-size: 15px; font-weight: 800; text-anchor: middle; dominant-baseline: middle; }
.wx-wind-arc { fill: none; stroke: #3b8cff; stroke-width: 13; stroke-linecap: butt; opacity: .95; }
.wx-wind-arc.vrb { opacity: .45; }
.wx-wind-line { stroke: #3b8cff; stroke-width: 3; stroke-dasharray: 2 6; stroke-linecap: round; opacity: .8; }
.wx-wind-head { fill: #7fb6ff; }
.wx-wind-label { fill: #7fb6ff; font-size: 15px; font-weight: 800; text-anchor: middle; dominant-baseline: middle; paint-order: stroke; stroke: #141c2e; stroke-width: 4px; }
.wx-calm { fill: #7fb6ff; font-size: 26px; font-weight: 800; text-anchor: middle; paint-order: stroke; stroke: #141c2e; stroke-width: 5px; }
.wx-src { font-size: clamp(9px, .72vw, 13px); font-weight: 700; letter-spacing: .06em; color: var(--dim); text-align: center; }
.wx-best { margin-top: .6vh; font-size: clamp(12px, 1vw, 18px); font-weight: 700; letter-spacing: .08em; color: var(--label); }
.wx-best strong { color: #86efac; font-size: 1.3em; margin-left: 6px; }
.wx-right { min-width: 0; min-height: 0; display: flex; flex-direction: column; justify-content: center; gap: 1.2vh; }
.wx-clock-row { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.wx-clock-row.local { margin-top: -0.6vh; padding-bottom: 1vh; border-bottom: 1px solid var(--line); }
.wx-clock { font-size: clamp(20px, 2vw, 38px); font-weight: 600; color: var(--gold); white-space: nowrap; }
.wx-clock.small { font-size: clamp(16px, 1.4vw, 26px); }
.wx-label { font-size: clamp(12px, 1.05vw, 20px); font-weight: 600; color: var(--label); letter-spacing: .04em; }
.wx-label small { color: var(--dim); font-size: .7em; }
.wx-table { display: flex; flex-direction: column; }
.wx-row { display: grid; grid-template-columns: minmax(0, .9fr) minmax(0, 1.1fr); align-items: baseline; gap: 12px; padding: .75vh 0; }
.wx-value { font-size: clamp(16px, 1.5vw, 30px); font-weight: 600; color: var(--val); overflow-wrap: anywhere; }
.wx-value small { font-size: .62em; color: var(--dim); margin-left: 6px; }
.wx-muted { color: var(--dim); font-size: .8em; }
.wx-rvr { display: inline-block; margin-right: 14px; white-space: nowrap; }
.wx-comps { display: flex; flex-wrap: wrap; gap: 8px; }
.wx-comp { flex: 1 1 120px; padding: 8px 10px; border-radius: 8px; background: var(--panel); border: 1px solid var(--line); }
.wx-comp.best { border-color: #86efac; }
.wx-comp-rwy { font-size: clamp(11px, .85vw, 15px); font-weight: 800; color: #fff; }
.wx-comp.best .wx-comp-rwy { color: #86efac; }
.wx-comp-val { font-size: clamp(10px, .78vw, 14px); font-weight: 700; color: var(--val); }
.wx-comp-val.x { color: var(--label); }
.wx-raw { font-family: "JetBrains Mono", Consolas, monospace; font-size: clamp(10px, .75vw, 14px); color: var(--dim); overflow-wrap: anywhere; }
.wx-foot { font-size: clamp(8px, .6vw, 11px); font-weight: 700; letter-spacing: .06em; color: #c7a76a; }
.wx-screen .aib-cat { padding: 1px 8px; border-radius: 4px; font-weight: 800; color: #08111e; background: #86efac; font-size: .8em; }
.wx-screen .aib-cat.mvfr { background: #60a5fa; } .wx-screen .aib-cat.ifr { background: #f16b68; } .wx-screen .aib-cat.lifr { background: #e879f9; }
@media (max-width: 1000px), (orientation: portrait) and (max-width: 1200px) {
  .wx-screen { grid-template-columns: 1fr; height: auto; min-height: 100%; padding: 16px; gap: 18px; overflow: visible; }
  .wx-rose-wrap { height: min(92vw, 520px); flex: none; }
  .wx-title { font-size: 26px; } .wx-value { font-size: 20px; } .wx-label { font-size: 14px; } .wx-clock { font-size: 24px; }
}
`;
