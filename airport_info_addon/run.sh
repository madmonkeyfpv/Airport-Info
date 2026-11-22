#!/usr/bin/env sh
# Read add-on options (admin token) and start the server. Settings persist in /config (addon_config).
if [ -f /data/options.json ]; then
  ADMIN_TOKEN=$(python3 -c "import json;print(json.load(open('/data/options.json')).get('admin_token') or '')")
  export ADMIN_TOKEN
fi
exec python3 -m airport_info.app
