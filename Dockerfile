FROM python:3.14-slim-trixie
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
COPY . .
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
RUN uv sync --locked --compile-bytecode --no-dev

# Create data directory
RUN mkdir -p /app/data

WORKDIR /app

# Set the entrypoint
CMD ["python", "src/bot.py"]