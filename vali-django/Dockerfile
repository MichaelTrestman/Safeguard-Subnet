FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for bittensor's substrate-interface (websockets, crypto)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY . .

# /data is the PVC mount in k8s — sqlite/postgres state lives here
RUN mkdir -p /data
ENV DJANGO_SETTINGS_MODULE=valiproject.settings

EXPOSE 9090

# Migrations run at container start (idempotent). Then uvicorn serves
# the ASGI app, whose lifespan handler starts the background loop.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec uvicorn valiproject.asgi:application --host 0.0.0.0 --port 9090 --lifespan on"]
