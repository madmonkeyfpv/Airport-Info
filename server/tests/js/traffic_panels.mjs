// Renders the board with live traffic under the four blank/non-blank combinations of the FlightAware lists
// and prints which panel shows which traffic. Used by test_traffic_panels in test_parsers.py.
import { renderBoard } from '../../../web/board.js';


const statuses = ['approaching', 'circuit', 'departed', 'ground', 'nearby'];
const aircraft = statuses.map((st, i) => ({ ident: `G-T${i}`, status: st, type_name: 'Cessna 152', distance_nm: 1 + i,
  bearing: 'N', alt_ft: 1000, gs_kt: 80, vs_fpm: 0, eta_min: st === 'approaching' ? 3 : null }));
const flight = { ident: 'EZY1', status: 'scheduled', arrival_time: new Date(Date.now() + 3600e3).toISOString(),
  departure_time: new Date(Date.now() + 3600e3).toISOString(), origin: {}, destination: {} };
const base = (arr, dep) => ({
  settings: { show_traffic: true }, airport: { icao: 'EGSU', display_name: 'DUXFORD' }, sources: {},
  flights: { arrivals: arr, departures: dep, latest_arrival: null, latest_departure: null },
  traffic: { aircraft, range_nm: 10, max_ft_agl: 3000 }, notams: [], airspace: null, radio: null, weather: null,
});
const panel = (html, name) => {
  const start = html.indexOf(`data-panel="${name}"`); const end = html.indexOf('</section>', start);
  const part = html.slice(start, end);
  return statuses.filter(st => part.includes(`aib-traffic ${st}`));
};
const out = {};
for (const [k, arr, dep] of [['both_blank', [], []], ['arr_blank', [], [flight]], ['dep_blank', [flight], []],
                             ['neither_blank', [flight], [flight]], ['fa_unavailable', null, null]]) {
  const d = base(arr, dep); if (arr === null) d.flights = null;
  const html = renderBoard(d);
  out[k] = { arrivals: panel(html, 'arrivals'), departures: panel(html, 'departures') };
}
console.log(JSON.stringify(out));
