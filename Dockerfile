# syntax=docker/dockerfile:1.7

# ---- Stage 1: builder ----
FROM python:3.11-slim AS builder

# uv is 10x faster than pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (better layer caching)
COPY pyproject.toml ./
COPY src ./src
COPY README.md LICENSE CHANGELOG.md ./

# Build wheel
RUN uv build --wheel --out-dir /wheels

# ---- Stage 2: runtime ----
FROM python:3.11-slim AS runtime

# Create non-root user
RUN groupadd --system --gid 1000 forge \
    && useradd --system --uid 1000 --gid forge --home-dir /app --shell /bin/bash forge

WORKDIR /app

# Install runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy built wheel from builder
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels

# Copy examples & docs (optional, for reference)
COPY --chown=forge:forge examples /app/examples
COPY --chown=forge:forge docs /app/docs

USER forge

# Default command: show CLI help
CMD ["forge-agent", "--help"]
