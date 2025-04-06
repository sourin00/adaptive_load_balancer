FROM python:3.9-slim

WORKDIR /app
COPY app.py GeoLite2-Country.mmdb .

RUN pip install flask prometheus_client requests prometheus-api-client redis docker geoip2 gunicorn

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]