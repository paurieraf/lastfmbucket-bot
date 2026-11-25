# Spec Delta

## Purpose

Defines centralized, environment-driven application configuration, backwards-compatible defaults, environment template documentation, and explicit startup validation for required bot credentials.

## ADDED Requirements

### Requirement: Centralized runtime configuration defaults
The configuration module SHALL expose centralized environment-driven settings for Ollama (`OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_MAX_CONCURRENT`), the admin dashboard (`ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_PORT`, `ADMIN_SECRET_KEY`), and collage caching (`COLLAGE_CACHE_MAX_MB`, `COLLAGE_CACHE_TTL_DAYS`), while preserving full backwards compatibility with all existing exported constants.

#### Scenario: Default values when environment variables are unset
- **WHEN** the configuration module is loaded with no optional environment variables set
- **THEN** all Ollama, admin, collage cache, and legacy settings resolve to their documented default values with the expected types (`str`, `int`, `float`, or `Path`)

#### Scenario: Environment variables override defaults
- **WHEN** environment variables such as `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_MAX_CONCURRENT`, `ADMIN_PORT`, `COLLAGE_CACHE_MAX_MB`, or `COLLAGE_CACHE_TTL_DAYS` are set in the process environment
- **THEN** the configuration module reflects those overridden values with proper type conversion

#### Scenario: Relative and empty database path handling
- **WHEN** `DB_SQLITE_NAME` is unset or empty
- **THEN** it resolves to `data/lastfmbucket-bot.db` relative to `PROJECT_ROOT`
- **AND** when `DB_SQLITE_NAME` is an absolute path, it is preserved unchanged

### Requirement: Explicit bot credential validation
The configuration module SHALL provide a `validate_bot_config()` helper that checks whether required bot credentials (`TELEGRAM_BOT_TOKEN`, `LASTFM_API_KEY`, `LASTFM_API_SECRET`) are present and non-blank, without failing at module import time.

#### Scenario: Importing config without bot credentials
- **WHEN** the configuration module is imported in an environment where `TELEGRAM_BOT_TOKEN`, `LASTFM_API_KEY`, or `LASTFM_API_SECRET` are unset
- **THEN** module import succeeds without raising an exception

#### Scenario: Validation succeeds with all required credentials
- **WHEN** `validate_bot_config()` is called and `TELEGRAM_BOT_TOKEN`, `LASTFM_API_KEY`, and `LASTFM_API_SECRET` are all non-empty strings
- **THEN** `validate_bot_config()` returns without raising an error

#### Scenario: Validation fails listing all missing credentials
- **WHEN** `validate_bot_config()` is called and one or more of `TELEGRAM_BOT_TOKEN`, `LASTFM_API_KEY`, or `LASTFM_API_SECRET` are `None` or whitespace-only
- **THEN** `validate_bot_config()` raises a `ValueError` whose message lists every missing environment variable name

### Requirement: Accurate environment template documentation
The `.env.template` file SHALL accurately document required and optional runtime variables without copy-paste errors, including `DB_SQLITE_NAME=data/lastfmbucket-bot.db`, a valid non-path placeholder for `ADMIN_SECRET_KEY`, and documented entries for `OLLAMA_HOST`, `OLLAMA_MODEL`, `LASTFM_MAX_CONCURRENT`, and `ADMIN_PORT`.

#### Scenario: Operator creates `.env` from `.env.template`
- **WHEN** an operator copies `.env.template` to `.env`
- **THEN** `DB_SQLITE_NAME` defaults to `data/lastfmbucket-bot.db`, `ADMIN_SECRET_KEY` does not contain a database file path, and `OLLAMA_HOST`, `OLLAMA_MODEL`, `LASTFM_MAX_CONCURRENT`, and `ADMIN_PORT` are documented with valid defaults
