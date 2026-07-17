FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps ./apps
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["sh", "-c", "if [ \"$SERVICE_ROLE\" = \"agent\" ]; then python -m http.server \"$PORT\" >/tmp/health.log 2>&1 & exec python apps/mirror_agent/bridge.py start; else exec uvicorn apps.api.main:app --host 0.0.0.0 --port \"$PORT\"; fi"]
