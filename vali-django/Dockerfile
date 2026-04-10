FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --upgrade pip && pip install -e .

RUN mkdir -p /data
ENV DJANGO_SETTINGS_MODULE=valiproject.settings

EXPOSE 9090

CMD ["sh", "-c", "python manage.py migrate --noinput && exec uvicorn valiproject.asgi:application --host 0.0.0.0 --port 9090 --lifespan on"]
