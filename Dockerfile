# Production image: backend + frontend in one container (the API serves the web app).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
# /data is where local-disk storage lives. In production mount a PERSISTENT volume here, or use STORAGE_BACKEND=s3.
RUN useradd -m -u 1000 app && mkdir -p /data/uploads /data/private && chown -R app:app /data /app
USER app
ENV UPLOAD_DIR=/data/uploads PRIVATE_DIR=/data/private PORT=8000 WEB_CONCURRENCY=2 TRUST_PROXY=true
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD curl -fsS http://localhost:${PORT}/api/health || exit 1
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*'"]
