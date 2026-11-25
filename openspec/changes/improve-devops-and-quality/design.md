# Design

## Context

See `proposal.md` for motivation and scope. This change is planned and implemented in parallel with sibling changes that own `src/bot.py`, `src/commands.py`, `src/services.py`, `src/db.py`, `src/admin.py`, and `src/ai.py`. Therefore, all edits are strictly scoped to:

- `pyproject.toml`, `uv.lock`
- `Dockerfile`, `.dockerignore`, `docker-compose.yml`
- `.env.template`
- `.github/workflows/deploy.yml`
- `src/config.py`
- `tests/test_config.py` (new)

Current codebase observations that shape the design:
- `src/services.py:458` reads `config.CHANGELOG_PATH` (`PROJECT_ROOT / "CHANGELOG.md"`), yet `.dockerignore` currently excludes `CHANGELOG.md` while failing to exclude `src/tests.py` or `tests/`.
- `src/ai.py` reads `OLLAMA_HOST` (default `"http://ollama:11434"`) and `OLLAMA_MODEL` (default `"qwen2.5:0.5b"`).
- `src/admin.py` reads `ADMIN_USERNAME` (`"admin"`), `ADMIN_PASSWORD` (`"changeme"`), `ADMIN_PORT` (`5000`), and `ADMIN_SECRET_KEY` (random hex fallback).
- Running `uv run ruff check --select E4,E7,E9,F,I,B,UP,ASYNC src/` on the current unmodified `src/` reports 49 pre-existing issues in sibling-owned files (`42 UP045`, `4 I001`, `2 UP035`, `1 ASYNC230`), whereas `E4,E7,E9,F,B` has 0 issues and `E4,E7,E9,F,B,UP,ASYNC` with `ignore = ["UP035", "UP045", "ASYNC230"]` has 0 issues.
- `Caddyfile` reverse-proxies `admin:8080`, so publishing `8080:8080` on all interfaces in `docker-compose.yml` is unnecessary and exposes the admin UI externally.

## Goals / Non-Goals

**Goals:**
- Ensure `uv run ruff check src/ tests/` passes cleanly in CI on day one without modifying any sibling-owned source files.
- Produce a smaller, non-root, cache-friendly multi-stage Docker image on `python:3.14-slim-trixie` with runtime healthchecks.
- Lock down admin port exposure to loopback (`127.0.0.1:8080:8080`) and wire service healthchecks in `docker-compose.yml`.
- Centralize all runtime configuration in `src/config.py` with backwards-compatible defaults, add `validate_bot_config()`, and cover it with unit tests in `tests/test_config.py`.

**Non-Goals:**
- Refactoring `src/bot.py`, `src/ai.py`, `src/admin.py`, or `src/services.py` to consume the new `src/config.py` constants or call `validate_bot_config()` (owned by sibling parallel changes).
- Changing `Caddyfile` or `deploy.sh`.
- Introducing `pytest` or replacing `unittest` (repo uses standard-library `unittest`).

## Decisions

### 1. Pragmatic `[tool.ruff.lint]` rule set compatible with untouched `src/`
- **Decision**: Move `exclude`, `line-length = 88`, `indent-width = 4`, and `target-version = "py314"` into `[tool.ruff]`. Set `[tool.ruff.lint]` to `select = ["E4", "E7", "E9", "F", "B", "UP", "ASYNC"]` with `ignore = ["UP035", "UP045", "ASYNC230"]`. Move `ruff==0.14.10` to `[dependency-groups] dev`.
- **Rationale**: Adds high-value bugbear (`B`), pyupgrade (`UP`), and async (`ASYNC`) checks without breaking CI on pre-existing `Optional[...]` annotations (`UP045`), legacy typing imports (`UP035`), or blocking `open()` (`ASYNC230`) in sibling-owned modules. Omitting `I` avoids 4 `I001` import-order failures in sibling-owned files.
- **Alternatives considered**:
  - Keeping only `E4, E7, E9, F`: misses bugbear and async pitfalls.
  - Enabling `I` / full `UP` with `per-file-ignores` per sibling file: brittle against parallel edits in sibling branches.

### 2. Multi-stage `Dockerfile` using `/app/.venv` and non-root `appuser`
- **Decision**:
  - **Stage 1 (`builder`)**: `python:3.14-slim-trixie` + `uv` from `ghcr.io/astral-sh/uv:latest`, installs `build-essential` and `*-dev` headers (`zlib1g-dev`, `libjpeg-dev`, `libpng-dev`, `libwebp-dev`, `libfreetype6-dev`), copies only `pyproject.toml` and `uv.lock`, and runs `uv sync --locked --no-install-project --compile-bytecode --no-dev` into `/app/.venv` (`UV_PROJECT_ENVIRONMENT="/app/.venv"`).
  - **Stage 2 (`runtime`)**: `python:3.14-slim-trixie`, installs only runtime shared libraries (`zlib1g`, `libjpeg62-turbo`, `libpng16-16t64`, `libwebp7`, `libfreetype6`), creates system user `appuser` (UID/GID 1000), copies `/app/.venv` from `builder`, copies `src/` and `CHANGELOG.md` with `--chown=appuser:appuser`, creates `/app/data` owned by `appuser`, sets `PATH="/app/.venv/bin:$PATH"`, switches to `USER appuser`, and defines `HEALTHCHECK`.
- **Rationale**: Copying `/app/.venv` between stages cleanly isolates compiled Python packages from `/usr/local`, maximizes Docker layer caching when only `src/` changes, and drops ~200MB+ of compiler toolchains from the runtime image. Using Debian Trixie's `libpng16-16t64` matches the `python:3.14-slim-trixie` base image.
- **Healthcheck**: Uses Python's stdlib (`sqlite3` check against `DB_SQLITE_NAME` or `/app/data/lastfmbucket-bot.db`) so no extra `curl`/`wget` binary is needed in the slim image.
- **Alternatives considered**:
  - Single-stage build with `apt-get purge`: leaves orphaned dependencies and breaks layer caching cleanly.
  - Installing into `/usr/local/`: harder to copy cleanly between stages without dragging unrelated system files.

### 3. `.dockerignore` hygiene
- **Decision**: Ignore `.git`, `.github`, `.venv`, `.ruff_cache`, `docs/`, `openspec/`, `data/`, `tests/`, `src/tests.py`, `tests.py`, markdown dev docs (`ARCHITECTURE.md`, `CONTEXT.md`, `PROJECT.md`, `SKILL.md`, `README.md`), `LICENSE`, `deploy.sh`, `Caddyfile`, `docker-compose.yml`, `.env`, `.env.template`. Remove `CHANGELOG.md` from `.dockerignore` so it is included in the image for `/changelog`.
- **Rationale**: Prevents test files, local SQLite databases, and planning docs from bloating or leaking into the Docker build context while fixing the missing `CHANGELOG.md` bug at runtime.

### 4. `docker-compose.yml` networking and healthchecks
- **Decision**:
  - Change `admin.ports` from `"8080:8080"` to `"127.0.0.1:8080:8080"`.
  - Add `healthcheck` to `ollama` (`["CMD", "ollama", "list"]`) and `admin` (Python `urllib.request.urlopen("http://127.0.0.1:8080/login")` check, overriding the image's default bot healthcheck).
  - Update `bot.depends_on` to `ollama: condition: service_healthy`.
- **Rationale**: Prevents direct external access to the admin panel while preserving local host access and internal Docker network routing from Caddy (`reverse_proxy admin:8080`). Waiting for `ollama` to be healthy reduces spurious connection errors during `bot` `post_init`.

### 5. CI quality gate in `.github/workflows/deploy.yml`
- **Decision**: Add `pull_request` (branches: `[main]`) trigger alongside `push` (`main`) and `workflow_dispatch`. Add a `test-and-lint` job using `astral-sh/setup-uv@v5` (`enable-cache: true`), running `uv sync --locked`, `uv run ruff check src/ tests/`, `uv run python -m unittest src/tests.py`, and `uv run python -m unittest discover -s tests`. Set `needs: test-and-lint` and `if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'` on `build-and-push`.
- **Rationale**: Blocks broken or lint-failing code from reaching GHCR and gives PRs fast automated feedback without needing a separate workflow file.

### 6. Centralized `src/config.py` and `validate_bot_config()`
- **Decision**:
  - Keep all existing module-level constants and names intact.
  - Guard `DB_SQLITE_NAME` against empty strings (`os.getenv("DB_SQLITE_NAME") or "data/lastfmbucket-bot.db"`).
  - Add module-level constants:
    - `OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")`
    - `OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")`
    - `OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30.0"))`
    - `OLLAMA_MAX_CONCURRENT = int(os.getenv("OLLAMA_MAX_CONCURRENT", "2"))`
    - `ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")`
    - `ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")`
    - `ADMIN_PORT = int(os.getenv("ADMIN_PORT", "5000"))`
    - `ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY") or secrets.token_hex(16)`
    - `COLLAGE_CACHE_MAX_MB = int(os.getenv("COLLAGE_CACHE_MAX_MB", "100"))`
    - `COLLAGE_CACHE_TTL_DAYS = int(os.getenv("COLLAGE_CACHE_TTL_DAYS", "7"))`
  - Add `validate_bot_config() -> None`: inspects `TELEGRAM_BOT_TOKEN`, `LASTFM_API_KEY`, and `LASTFM_API_SECRET` (treating `None` or whitespace-only values as missing) and raises `ValueError` listing all missing variable names if any are absent.
- **Rationale**: Defaults match existing values in `src/ai.py` and `src/admin.py` for seamless future adoption by sibling changes. Keeping `validate_bot_config()` opt-in (not called on import) preserves testability and allows `src/admin.py` to import `config` without Telegram/Last.fm credentials.

## Risks / Trade-offs

- **[Bind mount permissions with non-root UID 1000]** → If an existing host `./data` directory is owned by `root:root` with `0755` permissions, the non-root `appuser` (UID 1000) will fail to write to SQLite. **Mitigation**: Document `chown -R 1000:1000 ./data` in the migration notes; UID 1000 matches the default non-root user on standard Linux hosts.
- **[Debian Trixie package name drift]** → `libpng16-16t64` is specific to Debian Trixie's 64-bit `time_t` transition. **Mitigation**: Pin the base image to `python:3.14-slim-trixie` and verify with a Docker build check if Docker is available.
- **[`bot` waiting on `ollama` healthcheck]** → If `ollama` fails to start on a host without `/dev/dri`, `bot` would not start under `condition: service_healthy`. **Mitigation**: Use a fast, lightweight `ollama list` healthcheck with reasonable retries/start_period so healthy Ollama instances pass immediately; note that hosts without GPU passthrough already need `devices` adjusted per deployment.
- **[`ADMIN_SECRET_KEY` fallback randomness]** → When `ADMIN_SECRET_KEY` is unset, `secrets.token_hex(16)` generates a new key per process restart (matching existing `src/admin.py` behavior), invalidating admin sessions on restart. **Mitigation**: `.env.template` explicitly documents setting a persistent `ADMIN_SECRET_KEY`.

## Migration Plan

1. On existing deployments using `./data:/app/data`, ensure the host `./data` directory is writable by UID/GID `1000:1000` (`chown -R 1000:1000 ./data`) before upgrading to the non-root container image.
2. Update `.env` on deployed hosts to set a real `ADMIN_SECRET_KEY` (replacing any accidental `data/lastfmbucket-bot.db` value) and verify `DB_SQLITE_NAME=data/lastfmbucket-bot.db`.
3. Rollback: revert to the previous container image tag (`ghcr.io/<repo>:<previous-sha>`) and previous `docker-compose.yml` if any runtime permission issue occurs.
