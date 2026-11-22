# Home Assistant add-on image. The add-on build context is this folder only, so the
# application source is fetched from the GitHub repository at build time.
ARG BUILD_FROM=ghcr.io/home-assistant/base-python:3.12-alpine3.20
FROM ${BUILD_FROM}
ARG AIRPORT_INFO_REF=main
RUN apk add --no-cache curl tar \
 && mkdir -p /app \
 && curl -fsSL "https://codeload.github.com/madmonkeyfpv/airport-info/tar.gz/${AIRPORT_INFO_REF}" \
    | tar -xz -C /app --strip-components=1 \
 && pip install --no-cache-dir -r /app/server/requirements.txt
COPY run.sh /run.sh
RUN chmod a+x /run.sh
ENV PYTHONPATH=/app/server PORT=8080 DATA_DIR=/config WEB_DIR=/app/web
CMD ["/run.sh"]
