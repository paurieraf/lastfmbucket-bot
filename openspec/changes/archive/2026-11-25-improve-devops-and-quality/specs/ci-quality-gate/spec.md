# Spec Delta

## Purpose

Defines valid Python project metadata, dev-isolated linting configuration, and an automated GitHub Actions quality gate that runs linting and unit tests before publishing container images.

## ADDED Requirements

### Requirement: Valid pyproject metadata and dev-isolated linter
The `pyproject.toml` file SHALL place all Ruff configuration keys (`exclude`, `line-length`, `indent-width`, `target-version`) under `[tool.ruff]` rather than `[project]`, provide a meaningful `[project].description`, move `ruff` out of `[project.dependencies]` into `[dependency-groups] dev`, and keep `uv.lock` synchronized.

#### Scenario: Production dependency install excludes ruff
- **WHEN** dependencies are installed with `uv sync --locked --no-dev`
- **THEN** `ruff` is not installed in the production environment

#### Scenario: Development dependency install includes ruff with active lint rules
- **WHEN** dependencies are installed with `uv sync --locked` and `uv run ruff check src/ tests/` is executed
- **THEN** Ruff loads its configuration from `[tool.ruff]` and `[tool.ruff.lint]` without schema warnings and exits with status 0

### Requirement: Automated CI quality gate before image publishing
The `.github/workflows/deploy.yml` workflow SHALL execute a `test-and-lint` job on pull requests to `main`, pushes to `main`, and `workflow_dispatch`, and SHALL gate `build-and-push` on `test-and-lint` succeeding while restricting image publishing to `push` on `main` and `workflow_dispatch`.

#### Scenario: Pull request runs lint and tests without pushing images
- **WHEN** a pull request targeting `main` is opened or updated
- **THEN** the `test-and-lint` job runs `uv run ruff check src/ tests/`, `uv run python -m unittest src/tests.py`, and `uv run python -m unittest discover -s tests`
- **AND** the `build-and-push` job does not run

#### Scenario: Push to main gates Docker publish on quality checks
- **WHEN** commits are pushed to `main`
- **THEN** `test-and-lint` runs first
- **AND** `build-and-push` runs only if `test-and-lint` succeeds
