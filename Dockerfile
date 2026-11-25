FROM python:3.14-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install system build dependencies for C-extensions (such as Pillow)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT="/app/.venv"

# Copy dependency manifests first for optimal Docker layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --compile-bytecode --no-dev

FROM python:3.14-slim-trixie AS runtime

# Install runtime shared libraries required by Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    zlib1g \
    libjpeg62-turbo \
    libpng16-16t64 \
    libwebp7 \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser CHANGELOG.md ./CHANGELOG.md

# Create writable data directory for non-root user
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os, sqlite3; p = os.getenv('DB_SQLITE_NAME') or '/app/data/lastfmbucket-bot.db'; p = p if os.path.isabs(p) else os.path.join('/app', p); assert os.access(os.path.dirname(p), os.W_OK); conn = sqlite3.connect(p); conn.execute('SELECT 1'); conn.close()"

# Set the entrypoint
CMD ["python", "src/bot.py"]
