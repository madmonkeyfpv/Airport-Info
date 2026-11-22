#!/usr/bin/env sh
# Start the Airport Info server. Inside a Home Assistant add-on, /data/options.json holds the
# add-on options (admin token). /data is persistent in both Docker (volume) and the add-on.
if [ -f /data/options.json ]; then
  ADMIN_TOKEN=$(python3 -c "import json;print(json.load(open('/data/options.json')).get('admin_token') or '')")
  export ADMIN_TOKEN
fi
exec python3 -m airport_info.app
