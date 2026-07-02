FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# ffmpeg: needed by klara.pronunciation.audio to transcode webm/ogg/mp3
# uploads to WAV 16kHz mono (Azure Pronunciation Assessment's required format).
# libasound2: runtime dep of azure-cognitiveservices-speech on linux.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libasound2 \
    && rm -rf /var/lib/apt/lists/*

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN uv sync

EXPOSE 8000

# --ws-ping-*: protocol-level keepalive for /pronunciation/stream — a dead
# client is dropped by uvicorn and surfaces as ws.receive() raising in the
# session receiver (no app-level ping task needed).
CMD ["sh", "-c", "alembic upgrade head && uvicorn klara.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 10 --ws-ping-timeout 10 --reload --reload-dir /app/src"]
