FROM python:3.13-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN python -m venv /app/.venv

COPY requirements.txt ./
RUN /app/.venv/bin/pip install --upgrade pip \
    && /app/.venv/bin/pip install -r requirements.txt

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY . .

RUN useradd --create-home --uid 1000 node && chown -R node:node /app
USER node

CMD ["python", "run.py"]
