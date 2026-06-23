# ─── Stage 1: Build Vue frontend ──────────────────────────────────────────────
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ─── Stage 2: API only (dev compose with separate Vite container) ─────────────
FROM python:3.11-slim AS api

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

# ─── Stage 3: API + built frontend (Telegram / single URL) ────────────────────
FROM api AS app

COPY --from=frontend-build /app/frontend/dist ./static
