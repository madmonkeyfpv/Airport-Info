"""aiohttp web server: JSON API + static display website.

Endpoints
  GET  /api/data?airport=EGSU[&other setting overrides]  -> everything the display needs
  GET  /api/airports?q=glou                               -> airport search (UK)
  GET  /api/settings                                      -> current saved settings
  GET  /api/links                                         -> LAN addresses + host port for TVs (settings page)
  GET  /api/settings/version                              -> settings fingerprint (screens poll every 5 s to stay in sync)
  POST /api/settings  (JSON body; header X-Admin-Token if ADMIN_TOKEN is set)
  GET  /health
  /                -> web display (web/index.html)
  /weather         -> weather station page (same as /?view=weather)
  /settings.html   -> settings page
  /card/*          -> Home Assistant Lovelace card files (same renderer as the website)

Environment
  PORT (8080), HOST (0.0.0.0), DATA_DIR (./data), WEB_DIR (../web), ADMIN_TOKEN (unset = open)
"""
from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import re
import time
from datetime import datetime, timedelta, timezone

import aiohttp
from aiohttp import web

from . import __version__, airports
from .airspace import AirspaceDB, build_panel
from .flightaware import fetch_board
from .notams import PIB_URL, aerodrome_notams, nearby_airspace_notams, parse_pib
from .links import screen_links
from .radio import build_radio, fetch_datis
from .settings import Settings
from .weather import fetch_weather

log = logging.getLogger("airport_info")
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

TTL = {"flights": 120, "weather": 600, "pib": 900, "airspace": 86400, "atis": 300}


class Cache:
    """Tiny TTL cache that serves the last good value if a refresh fails."""

    def __init__(self):
        self.data: dict[str, tuple[float, object, str | None]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    async def get(self, key: str, ttl: float, fn):
        entry = self.data.get(key)
        if entry and time.time() - entry[0] < ttl:
            return entry[1], entry[0], entry[2]
        lock = self.locks.setdefault(key, asyncio.Lock())
        async with lock:
            entry = self.data.get(key)
            if entry and time.time() - entry[0] < ttl:
                return entry[1], entry[0], entry[2]
            try:
                value = await fn()
                self.data[key] = (time.time(), value, None)
                return value, time.time(), None
            except Exception as exc:  # noqa: BLE001
                log.warning("refresh %s failed: %s", key, exc)
                if entry:
                    # keep stale data, retry sooner
                    self.data[key] = (time.time() - ttl + 60, entry[1], str(exc))
                    return entry[1], entry[0], str(exc)
                return None, None, str(exc)


def _clean_operator(op: str) -> str:
    op = re.sub(r'\s*"[^"]*"', "", op or "")
    op = re.sub(r"\s*\([^)]*\)\s*$", "", op)
    return op.strip()


def _dt(s):
    return datetime.fromisoformat(s) if s else None


def process_flights(board: dict, now: datetime) -> dict:
    for lst in board.values():
        for f in lst:
            f["operator"] = _clean_operator(f.get("operator", ""))

    recent_arr = sorted([f for f in board.get("arrivals", []) if f.get("arrival_time")],
                        key=lambda f: f["arrival_time"], reverse=True)
    recent_dep = sorted([f for f in board.get("departures", []) if f.get("departure_time")],
                        key=lambda f: f["departure_time"], reverse=True)
    landed_urls = {f["url"] for f in recent_arr}
    departed_urls = {f["url"] for f in recent_dep}

    inbound = []
    for f in board.get("enroute", []):
        if f["status"] == "cancelled" or f["url"] in landed_urls:
            continue
        eta = _dt(f.get("arrival_time"))
        if eta and eta < now - timedelta(minutes=30):
            continue  # stale track (lost coverage) – FlightAware keeps these for hours
        inbound.append(f)
    inbound.sort(key=lambda f: f.get("arrival_time") or "9999")

    outbound = []
    for f in board.get("scheduled", []):
        if f["status"] == "cancelled" or f["url"] in departed_urls:
            continue
        etd = _dt(f.get("departure_time"))
        if etd and etd < now - timedelta(minutes=60):
            continue
        outbound.append(f)
    outbound.sort(key=lambda f: f.get("departure_time") or "9999")

    def latest(lst, key):
        for f in lst:
            t = _dt(f.get(key))
            if t and now - timedelta(hours=24) <= t <= now + timedelta(minutes=10):
                return f
        return None

    return {
        "arrivals": inbound,
        "departures": outbound,
        "latest_arrival": latest(recent_arr, "arrival_time"),
        "latest_departure": latest(recent_dep, "departure_time"),
        "recent_arrivals": recent_arr[:10],
        "recent_departures": recent_dep[:10],
    }


class App:
    def __init__(self, data_dir: pathlib.Path, web_dir: pathlib.Path, admin_token: str | None):
        self.data_dir = data_dir
        self.web_dir = web_dir
        self.admin_token = admin_token or None
        self.settings = Settings(data_dir / "settings.json")
        self.cache = Cache()
        self.airspace = AirspaceDB(data_dir)
        self.airspace.load_local()
        self.session: aiohttp.ClientSession | None = None

    async def on_startup(self, _app):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=45),
            headers={"User-Agent": f"AirportInfoDisplay/{__version__} (+https://github.com/madmonkeyfpv/airport-info)"},
        )

    async def on_cleanup(self, _app):
        if self.session:
            await self.session.close()

    # --- data sources ---------------------------------------------------------------
    async def _pib(self):
        async def fetch():
            async with self.session.get(PIB_URL) as r:
                r.raise_for_status()
                raw = await r.read()
            return await asyncio.get_running_loop().run_in_executor(None, parse_pib, raw)
        return await self.cache.get("pib", TTL["pib"], fetch)

    async def _flights(self, icao: str):
        return await self.cache.get(f"fa:{icao}", TTL["flights"], lambda: fetch_board(self.session, icao))

    async def _weather(self, ap: dict):
        return await self.cache.get(f"wx:{ap['icao'] or ap['iata']}", TTL["weather"], lambda: fetch_weather(self.session, ap))

    async def _datis(self, ap: dict):
        if not ap.get("icao") or not any("ATIS" in (f.get("type", "") + f.get("name", "")).upper()
                                         for f in ap.get("frequencies") or []):
            return None, None, None  # no ATIS published: don't query
        return await self.cache.get(f"atis:{ap['icao']}", TTL["atis"], lambda: fetch_datis(self.session, ap["icao"]))

    async def build(self, cfg: dict, overrides=()) -> dict:
        ap = airports.resolve(cfg["airport"])
        if not ap:
            raise web.HTTPNotFound(text=f"Unknown UK airport code '{cfg['airport']}'. Use a 4-letter ICAO or 3-letter IATA code.")
        now = datetime.now(timezone.utc)
        asyncio.ensure_future(self.airspace.refresh(self.session))
        fa_key = ap["icao"] or ap["iata"]
        (board, fa_t, fa_err), (wx, wx_t, wx_err), (pib, pib_t, pib_err), (datis, atis_t, atis_err) = await asyncio.gather(
            self._flights(fa_key), self._weather(ap), self._pib(), self._datis(ap))

        flights = process_flights(board, now) if board else None
        notams, panel = None, None
        if pib is not None:
            notams = aerodrome_notams(pib, ap["icao"], now, cfg["include_obstacle_notams"], cfg["include_airspace_notams"]) if ap["icao"] else []
            near_n = nearby_airspace_notams(pib, ap["lat"], ap["lon"], cfg["airspace_range_nm"], now)
            static = self.airspace.nearby(ap["lat"], ap["lon"], cfg["airspace_range_nm"])
            panel = build_panel(static, near_n, cfg["airspace_pinned"], cfg["airspace_cards"], cfg["warning_range_nm"])

        radio = build_radio(ap, pib or [], now, cfg["service_hours"], datis) if cfg["show_radio"] else None
        if radio is not None and pib is None:
            radio["notams_unavailable"] = True

        iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat() if t else None
        return {
            "version": __version__,
            "generated_at": now.isoformat(),
            "settings_version": self.settings.version,
            "overrides": sorted(overrides),  # settings this screen overrides via its URL / card config
            "settings": cfg,
            "airport": {**ap, "display_name": airports.display_name(ap), "timezone": "Europe/London"},
            "weather": wx,
            "flights": flights,
            "notams": notams,
            "airspace": panel,
            "radio": radio,
            "sources": {
                "atis": {"updated": iso(atis_t), "error": atis_err},
                "flightaware": {"updated": iso(fa_t), "error": fa_err, "url": f"https://www.flightaware.com/live/airport/{fa_key}"},
                "metar": {"updated": iso(wx_t), "error": wx_err},
                "notam": {"updated": iso(pib_t), "error": pib_err, "provider": "NATS AIS PIB"},
                "airspace": {"source": self.airspace.source},
            },
        }

    # --- handlers -------------------------------------------------------------------
    async def h_data(self, request):
        cfg = self.settings.effective(request.query)
        overrides = [k for k in request.query if k in self.settings.values and request.query[k] != ""]
        return web.json_response(await self.build(cfg, overrides))

    async def h_airports(self, request):
        return web.json_response(airports.search(request.query.get("q", "")))

    async def h_links(self, request):
        """Addresses for TVs / kiosk browsers (real LAN IP + host port), shown on the settings page."""
        resp = web.json_response(await screen_links(self.session, request))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    async def h_settings_version(self, _request):
        resp = web.json_response({"version": self.settings.version, "airport": self.settings.values["airport"]})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    async def h_settings_get(self, _request):
        return web.json_response({**self.settings.values, "_admin_token_required": bool(self.admin_token)})

    async def h_settings_post(self, request):
        if self.admin_token and request.headers.get("X-Admin-Token") != self.admin_token:
            raise web.HTTPUnauthorized(text="Admin token required")
        body = await request.json()
        if "airport" in body and not airports.resolve(str(body["airport"])):
            raise web.HTTPBadRequest(text=f"Unknown UK airport code '{body['airport']}'")
        try:
            return web.json_response(self.settings.update(body))
        except (ValueError, KeyError) as exc:
            raise web.HTTPBadRequest(text=str(exc))

    async def h_health(self, _request):
        return web.json_response({"ok": True, "version": __version__})

    async def h_index(self, _request):
        return web.FileResponse(self.web_dir / "index.html")


@web.middleware
async def cors(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response()
    else:
        resp = await handler(request)
    if request.path.startswith(("/api/", "/card/")):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Admin-Token"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    if request.path.endswith((".js", ".html", ".css")) or request.path == "/":
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def make_app() -> web.Application:
    data_dir = pathlib.Path(os.environ.get("DATA_DIR", ROOT / "server" / "data"))
    web_dir = pathlib.Path(os.environ.get("WEB_DIR", ROOT / "web"))
    a = App(data_dir, web_dir, os.environ.get("ADMIN_TOKEN"))
    app = web.Application(middlewares=[cors])
    app.on_startup.append(a.on_startup)
    app.on_cleanup.append(a.on_cleanup)
    app.router.add_get("/api/data", a.h_data)
    app.router.add_get("/api/airports", a.h_airports)
    app.router.add_get("/api/settings", a.h_settings_get)
    app.router.add_get("/api/settings/version", a.h_settings_version)
    app.router.add_get("/api/links", a.h_links)
    app.router.add_post("/api/settings", a.h_settings_post)
    app.router.add_route("OPTIONS", "/api/{tail:.*}", a.h_health)
    app.router.add_get("/health", a.h_health)
    app.router.add_get("/", a.h_index)
    app.router.add_get("/weather", lambda r: web.HTTPFound("./?view=weather" + ("&" + r.query_string if r.query_string else "")))
    app.router.add_static("/", web_dir, show_index=False)
    app["state"] = a
    return app


def main():
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    web.run_app(make_app(), host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    main()
