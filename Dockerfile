# Quantum Sommelier — single-container deploy.
# Runs Redis + FastAPI (uvicorn) + Celery worker under supervisord.
# Stage 1 builds the frontend bundle; stage 2 runs it.

# ── Stage 1: frontend build ────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /build

# Install deps first for better cache
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund --silent

# Copy frontend sources and build
COPY app.jsx api.js data.js edu.js ./
COPY landing.jsx scanning.jsx tasting.jsx overlays.jsx ./
COPY styles.css styles-components.css styles-tasting.css styles-cork.css styles-mobile.css ./
COPY ["Quantum Sommelier.html", "favicon.svg", "build.mjs", "./"]
RUN node build.mjs

# ── Stage 2: runtime ───────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies:
#  - git: for cloning target repos
#  - redis-server: embedded broker for Celery
#  - supervisor: process manager for the three in-container services
#  - build-essential + libssl: tree-sitter native parsers
#  - ca-certificates, curl: TLS + diagnostics
RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      redis-server \
      supervisor \
      build-essential \
      libssl-dev \
      ca-certificates \
      curl \
      fonts-dejavu-core \
      fonts-liberation \
      fontconfig \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip \
 && pip install -r /app/backend/requirements.txt

# Copy backend source
COPY backend /app/backend

# Copy frontend bundle from stage 1
RUN mkdir -p /app/frontend
COPY --from=frontend /build/dist/ /app/frontend/

# Supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/qs.conf

# Ephemeral working directory for clones (PRD §8.4)
RUN mkdir -p /tmp/qs-work && chmod 700 /tmp/qs-work

ENV PYTHONPATH=/app \
    QS_FRONTEND_DIR=/app/frontend \
    QS_WORK_DIR=/tmp/qs-work \
    REDIS_URL=redis://127.0.0.1:6379/0 \
    PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/api/v1/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
