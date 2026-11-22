# Airport Info — website + API server (also used by the Home Assistant card).
FROM python:3.12-slim
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server/ server/
COPY web/ web/
ENV PYTHONPATH=/app/server PORT=8080 DATA_DIR=/data WEB_DIR=/app/web
VOLUME ["/data"]
EXPOSE 8080
CMD ["python", "-m", "airport_info.app"]
