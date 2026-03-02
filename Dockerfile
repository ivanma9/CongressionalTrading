FROM python:3.12-slim

RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock LICENSE README.md ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY static/ static/

ENV DATABASE_PATH=/data/congressional_trades.db

ENV PORT=8000
EXPOSE ${PORT}

CMD uv run uvicorn congressional_trading.main:app --host 0.0.0.0 --port ${PORT}
