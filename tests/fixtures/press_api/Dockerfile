FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

# The synthetic source is a standalone QA image. Keep the product image free
# of test modules while installing only the HTTP runtime it needs.
RUN pip install --no-cache-dir \
    'fastapi>=0.117,<0.118' \
    'uvicorn[standard]>=0.30,<1'

COPY tests/fixtures/press_api /app/tests/fixtures/press_api
RUN touch /app/tests/__init__.py /app/tests/fixtures/__init__.py /app/tests/fixtures/press_api/__init__.py

EXPOSE 8090
