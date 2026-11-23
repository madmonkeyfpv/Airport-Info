"""Install the dashboard card into Home Assistant's own web folder (HA add-on only).

Why: when the card is loaded from the add-on's port (http://<ip>:8765/...), browsers block it whenever Home Assistant
itself is opened over https (Nabu Casa, the iOS/Android app with an external URL, a reverse proxy): mixed content.
Copying the card into /homeassistant/www/airport-info/ lets HA serve it as /local/airport-info/... from the SAME
origin over whatever connection the dashboard uses. The card then fetches its data through the add-on's ingress
URL (also same origin), which is recorded in addon.json next to the files.

Layout written (mirrors web/ so the card's relative imports keep working):
  www/airport-info/board.js, weather.js        shared renderers
  www/airport-info/card/airport-info-card.js   the card (imports rewritten with ?v=<version> for cache busting)
  www/airport-info/addon.json                  {"version", "ingress_url", "port"}
"""
from __future__ import annotations

import json
import logging
import pathlib
import re

log = logging.getLogger("airport_info")
FILES = ["board.js", "weather.js", "card/airport-info-card.js"]


def install_card_files(ha_config_dir: pathlib.Path, web_dir: pathlib.Path, version: str,
                       ingress_url: str | None = None, port: int | None = None) -> pathlib.Path | None:
    """Copy the card + shared modules into <ha_config>/www/airport-info. Returns the target dir, or None."""
    if not ha_config_dir.is_dir():
        return None
    target = ha_config_dir / "www" / "airport-info"
    try:
        for rel in FILES:
            src = (web_dir / rel).read_text()
            # Version the relative ES-module imports so browsers never mix old and new files after an update.
            src = re.sub(r"""(from\s+['"])(\.\.?/[^'"?]+\.js)(['"])""", rf"\g<1>\g<2>?v={version}\g<3>", src)
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(src)
        (target / "addon.json").write_text(json.dumps({"version": version, "ingress_url": ingress_url, "port": port}))
        log.info("dashboard card installed to %s (resource: /local/airport-info/card/airport-info-card.js?v=%s)",
                 target, version)
        return target
    except OSError as exc:
        log.warning("could not install dashboard card into %s: %s", target, exc)
        return None
