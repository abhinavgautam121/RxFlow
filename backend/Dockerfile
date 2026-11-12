# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY backend .
COPY sql /sql
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.txt; else pip install --no-cache-dir -r requirements.txt; fi
EXPOSE 8000
CMD ["sh","-c","alembic upgrade head && python -m app.bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
