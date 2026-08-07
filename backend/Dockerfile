FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY db /app/db
COPY ingest /app/ingest
COPY ml /app/ml
COPY models /app/models
RUN mkdir -p /var/lib/iddrv/inbox /var/lib/iddrv/processing /var/lib/iddrv/archive /var/lib/iddrv/quarantine /var/lib/iddrv/raw
EXPOSE 8000
