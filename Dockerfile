FROM python:3.14-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

## Copy the project into the image
#COPY . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app
COPY . .
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
RUN uv sync --locked --compile-bytecode --no-dev

## Install dependencies
#COPY pyproject.toml .
#RUN uv pip install --system -r pyproject.toml
#COPY . .
#RUN uv pip install --system -e .

# Create data directory
RUN mkdir -p /app/data

WORKDIR /app

# Set the entrypoint
CMD ["python", "src/bot.py"]