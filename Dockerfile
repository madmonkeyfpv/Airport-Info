# Airport Info — one image for both uses (plain Docker / docker compose, and the Home Assistant add-on).
# Base: Home Assistant's multi-arch Python image (amd64 + arm64). build.yaml is deprecated by the
# Supervisor, so the base image is set here; the Supervisor builds for the host's platform.
# The image is built entirely from this repository's files (works as a local add-on too).
ARG BUILD_FROM=ghcr.io/home-assistant/base-python:3.13-alpine3.22
FROM ${BUILD_FROM}
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server/ server/
COPY web/ web/
COPY run.sh /run.sh
RUN chmod a+x /run.sh
# Informational only: under s6-overlay (HA base image) ENV is reset before CMD runs, so run.sh sets these itself.
ENV PYTHONPATH=/app/server PORT=8080 DATA_DIR=/data WEB_DIR=/app/web
EXPOSE 8080
CMD ["/run.sh"]
