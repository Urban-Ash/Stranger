# Minimal production image for Stranger (Flask + Gunicorn)

FROM python:3.12-slim AS base

# Ensure logs flush immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install OS deps only if needed (kept slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Default port; can be overridden via env FLASK_PORT
ENV FLASK_PORT=5082
EXPOSE 5082

# Start with Gunicorn (module: app.app, variable: app)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5082", "app.app:app"]