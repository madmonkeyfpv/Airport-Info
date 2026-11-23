#!/usr/bin/env sh
# Start the Airport Info server.
#
# Everything is set HERE rather than relying on Dockerfile ENV: the Home Assistant base image runs this via
# s6-overlay, which resets the environment before starting CMD, so ENV values (PYTHONPATH etc.) are lost.
# (That caused "No module named 'airport_info'" in add-on v0.2.0–0.2.2.)
APP_DIR="${APP_DIR:-/app}"
cd "$APP_DIR" || exit 1
export PYTHONPATH="$APP_DIR/server"
export WEB_DIR="$APP_DIR/web"
export DATA_DIR="${DATA_DIR:-/data}"   # persistent in both the HA add-on and the docker-compose volume
export PORT="${PORT:-8080}"
export HOST="${HOST:-0.0.0.0}"
mkdir -p "$DATA_DIR"

# Supervisor API token (HA add-on only): also wiped by s6, but s6 keeps a copy on disk.
if [ -z "$SUPERVISOR_TOKEN" ] && [ -f /run/s6/container_environment/SUPERVISOR_TOKEN ]; then
  SUPERVISOR_TOKEN=$(cat /run/s6/container_environment/SUPERVISOR_TOKEN)
  export SUPERVISOR_TOKEN
fi

# Inside a Home Assistant add-on, /data/options.json holds the add-on options (admin token).
if [ -f "$DATA_DIR/options.json" ]; then
  ADMIN_TOKEN=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('admin_token') or '')" "$DATA_DIR/options.json")
  export ADMIN_TOKEN
fi

echo "[airport-info] starting: app=$APP_DIR data=$DATA_DIR port=$PORT"
exec python3 -m airport_info.app
