"""Regression test: the container start script must work with a WIPED environment.

The Home Assistant base image starts CMD through s6-overlay, which resets the environment, so Dockerfile
ENV values (PYTHONPATH, WEB_DIR, DATA_DIR) never reach the app. run.sh must set everything itself.
Add-on 0.2.0-0.2.2 failed on a real HA box with "No module named 'airport_info'" because of this.
"""
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_run_sh_starts_with_empty_environment(tmp_path):
    (tmp_path / "options.json").write_text(json.dumps({"admin_token": "secret"}))
    port = _free_port()
    # Minimal PATH, but with the test interpreter's directory first: on CI the Python that has the
    # requirements installed lives outside /usr/bin (e.g. /opt/hostedtoolcache/...). In the add-on image
    # python3 is /usr/local/bin/python3 with requirements installed, which this PATH also covers.
    path = os.pathsep.join([os.path.dirname(sys.executable), "/usr/local/bin", "/usr/bin", "/bin"])
    env = {"PATH": path, "APP_DIR": str(ROOT), "DATA_DIR": str(tmp_path), "PORT": str(port)}
    proc = subprocess.Popen(["sh", str(ROOT / "run.sh")], cwd="/", env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        body = None
        for _ in range(60):
            try:
                body = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1))
                break
            except OSError:
                if proc.poll() is not None:
                    break
                time.sleep(0.25)
        assert body and body["ok"], proc.stdout.read().decode() if proc.poll() is not None else "no response"
        # admin token from options.json is enforced
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", data=b"{}", method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("save without admin token should be refused")
        except urllib.error.HTTPError as e:
            assert e.code == 401
        # the web UI is served from the app directory
        assert urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).status == 200
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_card_modules_are_cors_enabled(tmp_path):
    """The HA card is imported cross-origin; it and the shared modules it imports must all send CORS headers.
    (Missing on board.js/weather.js caused "Custom element doesn't exist: airport-info-card" in 0.2.4.)"""
    port = _free_port()
    path = os.pathsep.join([os.path.dirname(sys.executable), "/usr/local/bin", "/usr/bin", "/bin"])
    env = {"PATH": path, "APP_DIR": str(ROOT), "DATA_DIR": str(tmp_path), "PORT": str(port)}
    proc = subprocess.Popen(["sh", str(ROOT / "run.sh")], cwd="/", env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                break
            except OSError:
                time.sleep(0.25)
        card = urllib.request.urlopen(f"http://127.0.0.1:{port}/card/airport-info-card.js", timeout=5)
        imports = [line.split("'")[1] for line in card.read().decode().splitlines()
                   if line.startswith("import ") and "'" in line]
        assert imports, "card should import the shared renderers"
        for rel in ["card/airport-info-card.js"] + [i.replace("../", "") for i in imports]:
            r = urllib.request.urlopen(f"http://127.0.0.1:{port}/{rel}", timeout=5)
            assert r.headers.get("Access-Control-Allow-Origin") == "*", rel
    finally:
        proc.terminate()
        proc.wait(timeout=10)
