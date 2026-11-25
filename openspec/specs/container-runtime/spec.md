# container-runtime Specification

## Purpose

Defines the hardened multi-stage container build, build-context hygiene, non-root runtime execution, healthchecks, and localhost-restricted admin networking for production deployments.

## Requirements

### Requirement: Multi-stage Docker build with optimized layer caching
The `Dockerfile` SHALL use a multi-stage build that installs Python dependencies from `pyproject.toml` and `uv.lock` before copying application source code, omits build-time compilers and `*-dev` header packages from the final runtime image, and retains required runtime shared libraries for image processing.

#### Scenario: Source-only edits reuse dependency layer cache
- **WHEN** application code under `src/` changes without modifying `pyproject.toml` or `uv.lock`
- **THEN** the Docker build reuses the cached dependency synchronization layer (`uv sync --locked --no-install-project --compile-bytecode --no-dev`)

#### Scenario: Runtime image excludes build toolchains
- **WHEN** the final runtime image is built
- **THEN** `build-essential` and `*-dev` header packages are absent from the runtime stage while runtime shared libraries required by Pillow remain installed

### Requirement: Build context excludes tests and development artifacts
The `.dockerignore` file SHALL exclude test suites (`src/tests.py`, `tests/`) and development/planning documentation from the Docker build context while preserving `CHANGELOG.md` for runtime `/changelog` command reads.

#### Scenario: Runtime image excludes tests and includes changelog
- **WHEN** the Docker image is built from the repository root
- **THEN** `src/tests.py` and `tests/` are not present in the image
- **AND** `CHANGELOG.md` is present at `/app/CHANGELOG.md`

### Requirement: Non-root container execution and healthcheck
The container image SHALL run as a non-root user with write access to `/app/data` and SHALL declare a `HEALTHCHECK` instruction.

#### Scenario: Container process runs as non-root with writable data directory
- **WHEN** a container starts from the built image
- **THEN** the default process runs as a non-root UID/GID and can read and write files inside `/app/data`

#### Scenario: Container reports health status
- **WHEN** the container runtime executes the configured `HEALTHCHECK`
- **THEN** it succeeds when the Python environment and `/app/data` SQLite storage are accessible and fails otherwise

### Requirement: Hardened Docker Compose networking and service dependencies
The `docker-compose.yml` file SHALL bind the `admin` service port exclusively to loopback (`127.0.0.1:8080:8080`) and configure healthchecks and `depends_on` relationships across services.

#### Scenario: Admin dashboard is not exposed on public interfaces
- **WHEN** the stack is started with `docker compose up`
- **THEN** the `admin` service publishes port `8080` only on `127.0.0.1` so external traffic must pass through the reverse proxy

#### Scenario: Service healthchecks and startup ordering
- **WHEN** the stack is started with `docker compose up`
- **THEN** `ollama` and `admin` define healthchecks and `bot` declares its dependency on `ollama`
