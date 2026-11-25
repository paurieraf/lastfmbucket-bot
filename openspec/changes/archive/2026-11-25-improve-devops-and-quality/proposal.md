# Proposal

## Why

The project's packaging, containerization, deployment workflow, and configuration management have accumulated operational and quality gaps: `pyproject.toml` has Ruff settings misplaced under `[project]` and bundles `ruff` as a production dependency; the `Dockerfile` compiles C-extensions in a single stage as `root` with suboptimal layer caching and no `HEALTHCHECK`, while `.dockerignore` excludes `CHANGELOG.md` (which `/changelog` reads at runtime) and fails to exclude `src/tests.py` or `tests/`; `docker-compose.yml` exposes the admin dashboard on `0.0.0.0:8080` despite Caddy reverse-proxying it; `.env.template` contains a copy-paste bug (`ADMIN_SECRET_KEY=data/lastfmbucket-bot.db`) and omits several runtime variables; `.github/workflows/deploy.yml` publishes Docker images without running linting or unit tests; and runtime settings for Ollama, the admin dashboard, and collage caching are scattered across modules without centralized config or credential validation. Addressing these issues now establishes a secure, reproducible, and CI-verified operational baseline without touching feature modules owned by parallel changes.

## What Changes

- **Packaging & Linting (`pyproject.toml`, `uv.lock`)**:
  - Move misplaced Ruff keys (`exclude`, `line-length`, `indent-width`, `target-version`) from `[project]` to `[tool.ruff]`.
  - Move `ruff` out of production `[project.dependencies]` into `[dependency-groups] dev` and regenerate `uv.lock`.
  - Replace the placeholder `[project].description` (`"Add your description here"`) with a concise project description.
  - Configure pragmatic `[tool.ruff.lint]` rules (`E4`, `E7`, `E9`, `F`, `B`, `UP`, `ASYNC` with targeted ignores for pre-existing patterns in sibling-owned modules so `ruff check` passes cleanly without modifying out-of-scope files).
- **Container & Compose Hardening (`Dockerfile`, `.dockerignore`, `docker-compose.yml`)**:
  - Convert `Dockerfile` to a multi-stage build on `python:3.14-slim-trixie` so `build-essential` and `*-dev` headers stay out of the final runtime image while preserving required Pillow/image runtime shared libraries.
  - Optimize Docker layer caching by copying `pyproject.toml` and `uv.lock` first and running `uv sync --locked --no-install-project --compile-bytecode --no-dev` before copying `src/` and `CHANGELOG.md`.
  - Run the container as a dedicated non-root user with ownership of `/app/data`, and define a `HEALTHCHECK`.
  - Update `.dockerignore` to exclude `src/tests.py`, `tests/`, and dev/planning docs while keeping `CHANGELOG.md` available to the image.
  - Bind the `admin` service port in `docker-compose.yml` to `127.0.0.1:8080:8080` instead of `0.0.0.0:8080`, and add service healthchecks and appropriate `depends_on` conditions.
- **CI Quality Gate (`.github/workflows/deploy.yml`)**:
  - Add a `test-and-lint` job that runs on `pull_request` to `main`, `push` to `main`, and `workflow_dispatch`, executing `uv run ruff check src/ tests/` and both `src/tests.py` and `tests/` unittest suites.
  - Gate `build-and-push` on `needs: test-and-lint` and restrict image publishing to `push` on `main` and `workflow_dispatch`.
- **Centralized Configuration & Validation (`src/config.py`, `.env.template`, `tests/test_config.py`)**:
  - Add centralized settings in `src/config.py` (`OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_MAX_CONCURRENT`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_PORT`, `ADMIN_SECRET_KEY`, `COLLAGE_CACHE_MAX_MB`, `COLLAGE_CACHE_TTL_DAYS`) while preserving 100% backwards compatibility with all existing constants.
  - Add `validate_bot_config()` to verify required credentials (`TELEGRAM_BOT_TOKEN`, `LASTFM_API_KEY`, `LASTFM_API_SECRET`) and raise a clear `ValueError` listing all missing variables.
  - Fix `.env.template` (`DB_SQLITE_NAME`, `ADMIN_SECRET_KEY`) and document `OLLAMA_HOST`, `OLLAMA_MODEL`, `LASTFM_MAX_CONCURRENT`, and `ADMIN_PORT`.
  - Add unit tests in `tests/test_config.py`.

## Capabilities

### New Capabilities
- `app-configuration`: Centralized environment-driven settings, safe defaults, `.env.template` documentation, and explicit startup validation for required bot credentials.
- `container-runtime`: Multi-stage non-root Docker build, build-context hygiene, container healthchecks, and localhost-only admin port binding in Docker Compose.
- `ci-quality-gate`: Validated Python project metadata, dev-isolated linting configuration, and a GitHub Actions lint-and-test gate preceding Docker image publication.

### Modified Capabilities
<!-- No existing spec requirements are modified; all changes introduce new operational and configuration capabilities. -->

## Impact

- **Owned files modified/added**: `pyproject.toml`, `uv.lock`, `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.env.template`, `.github/workflows/deploy.yml`, `src/config.py`, `tests/test_config.py`.
- **Untouched modules**: `src/bot.py`, `src/commands.py`, `src/services.py`, `src/db.py`, `src/admin.py`, `src/ai.py` remain untouched in this change to avoid conflicts with sibling parallel changes; existing `src/config.py` exports remain 100% backwards-compatible.
- **Dependencies**: `ruff` moves from runtime dependencies to `[dependency-groups] dev` (reduces production image footprint; `uv.lock` regenerated).
- **Deployment**: Docker image shrinks via multi-stage build and runs as non-root; admin port is no longer exposed on public interfaces (`127.0.0.1:8080:8080`); PRs gain automated lint + unit test verification.
