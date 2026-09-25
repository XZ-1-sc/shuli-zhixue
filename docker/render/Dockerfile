FROM node:20-alpine AS frontend-build
WORKDIR /workspace/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE_URL=""
RUN npm run build

FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 STATIC_DIR=/workspace/frontend/dist
WORKDIR /workspace/backend
COPY backend/requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY data /workspace/data
COPY --from=frontend-build /workspace/frontend/dist /workspace/frontend/dist
EXPOSE 8000
CMD ["sh", "-c", "if [ \"${RUN_DB_MIGRATIONS:-0}\" = \"1\" ]; then alembic upgrade head; fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
