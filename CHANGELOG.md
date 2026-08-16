# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-08-17

### Added
- Integrated `/collage` command with support for interactive builder (entity, size, period) and direct CLI arguments.
- Upgraded `lastfmcollagegenerator` to v0.6.0 supporting arbitrary NxM grids (up to 20x20, max 400 tiles), dynamic resolution scaling, and custom `tile_size` (50–600px).
- Expanded interactive grid presets (`3x3`, `4x4`, `5x5`, `3x5`, `10x5`, `10x10`).

## [0.1.0] - 2025-12-21

### Added
- Initial release of the bot.
- Docker support with Dockerfile and docker-compose.yml.
- GitHub Actions workflow for deployment.
- SQLite database support with Docker volume persistence.
