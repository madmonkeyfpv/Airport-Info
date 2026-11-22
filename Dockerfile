# Airport Info — one image for both uses:
#  * plain Docker / docker compose (website + API)          -> base python:3.13-slim
#  * Home Assistant add-on (config.yaml + build.yaml at root) -> HA passes BUILD_FROM (Alpine base-python)
# The image is built entirely from this repository's files, so it works for a private repo
# installed as a *local* add-on as well as a public add-on repository.
ARG BUILD_FROM=python:3.13-slim
FROM ${BUILD_FROM}
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server/ server/
COPY web/ web/
COPY run.sh /run.sh
RUN chmod a+x /run.sh
ENV PYTHONPATH=/app/server PORT=8080 DATA_DIR=/data WEB_DIR=/app/web
EXPOSE 8080
CMD ["/run.sh"]
