"""Work out the addresses other devices (TVs, kiosk browsers) should use to reach this server.

Shown on the settings page so users can copy the exact URLs. The browser's own address is not enough:
inside Home Assistant the settings page is usually opened via ingress (https://<ha>/api/hassio_ingress/<token>/),
which a TV can't use. So:

* HA add-on: ask the Supervisor API (needs `hassio_api: true`) for the host's LAN IPv4 addresses, its hostname
  (→ <hostname>.local) and the host port mapped to the container's 8080 (default 8765, user-changeable).
* Plain Docker / Python: fall back to the Host header the user browsed to (if it isn't an ingress request),
  plus the machine's outbound IP (only meaningful with host networking).
"""
from __future__ import annotations

import os
import socket

SUPERVISOR = os.environ.get("SUPERVISOR_URL", "http://supervisor")  # override only for testing
CONTAINER_PORT = "8080/tcp"


def _supervisor_token() -> str | None:
    # s6-overlay (HA base image) resets the environment for CMD; the token is still on disk.
    tok = os.environ.get("SUPERVISOR_TOKEN")
    if tok:
        return tok
    try:
        with open("/run/s6/container_environment/SUPERVISOR_TOKEN") as f:
            return f.read().strip() or None
    except OSError:
        return None


async def _sv_get(session, path: str, token: str) -> dict | None:
    try:
        async with session.get(SUPERVISOR + path, headers={"Authorization": f"Bearer {token}"}, timeout=5) as r:
            if r.status != 200:
                return None
            body = await r.json(content_type=None)
            return body.get("data") if isinstance(body, dict) else None
    except Exception:  # noqa: BLE001 - not running under Supervisor / API unavailable
        return None


def bases_from_supervisor(self_info: dict | None, network: dict | None, host: dict | None) -> dict:
    """Pure function (unit-tested): Supervisor API payloads -> base URLs."""
    port = None
    if self_info:
        port = (self_info.get("network") or {}).get(CONTAINER_PORT)
    ips = []
    for iface in (network or {}).get("interfaces") or []:
        if not iface.get("enabled", True) or iface.get("connected") is False:
            continue
        addrs = ((iface.get("ipv4") or {}).get("address")) or []
        for a in addrs:
            ip = a.split("/")[0]
            if ip and not ip.startswith(("127.", "169.254.", "172.30.")):
                ips.append((0 if iface.get("primary") else 1, ip))
    ips = [ip for _, ip in sorted(ips)]
    hostname = (host or {}).get("hostname")
    bases = []
    if port:
        bases += [{"label": f"IP address ({ip})", "base": f"http://{ip}:{port}"} for ip in dict.fromkeys(ips)]
        if hostname:
            bases.append({"label": f"Hostname ({hostname}.local)", "base": f"http://{hostname}.local:{port}"})
    return {"bases": bases, "port": port, "direct_port_disabled": self_info is not None and not port,
            "source": "supervisor"}


def _outbound_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # TEST-NET address; no packet is actually sent for UDP connect
            ip = s.getsockname()[0]
            return None if ip.startswith(("127.", "172.17.", "172.30.", "192.0.2.")) else ip
    except OSError:
        return None


async def screen_links(session, request) -> dict:
    token = _supervisor_token()
    if token:
        self_info, network, host = (await _sv_get(session, "/addons/self/info", token),
                                    await _sv_get(session, "/network/info", token),
                                    await _sv_get(session, "/host/info", token))
        if self_info or network:
            out = bases_from_supervisor(self_info, network, host)
            out["ha_addon"] = True
            return out
    # Plain Docker / Python
    bases = []
    ingress = request.headers.get("X-Ingress-Path")
    host_hdr = request.headers.get("X-Forwarded-Host") or request.host
    if host_hdr and not ingress:
        scheme = request.headers.get("X-Forwarded-Proto") or request.scheme
        bases.append({"label": f"This address ({host_hdr})", "base": f"{scheme}://{host_hdr}"})
    ip = _outbound_ip()
    port = request.url.port or int(os.environ.get("PORT", "8080"))
    if ip and not any(ip in b["base"] for b in bases):
        bases.append({"label": f"IP address ({ip})", "base": f"http://{ip}:{port}"})
    return {"bases": bases, "port": port, "direct_port_disabled": False, "source": "request", "ha_addon": False}
