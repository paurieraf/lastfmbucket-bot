# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-08-17

### Added
- New **WhoKnows system (`/whoknows`, alias `/wk`)** with parallel scrobble lookups, canonical Last.fm artist resolution, URLs, podium badges (🥇, 🥈, 🥉), and dethronement notifications (⚔️).
- New **Crowns system (`/crowns`, alias `/mycrowns`)** for group Hall of Fame leaderboards and user crown showcases.
- New `ChatMember` and `Crown` database models with automatic member discovery in group chats.
- Group privacy toggle in `/preferences` to allow opting out of group rankings.
- New `👑 Qui ho coneix?` inline button on Now Playing cards.
- Upgraded `lastfmcollagegenerator` to v0.8.0 and exposed its new rendering options in `/collage`.
- New `/collage` CLI options: `theme:`, `overlay:`, `preset:` (short aliases `story|post|header|wallpaper|4k`), `notext`, `corner:`, `border:`, `border_color:`, `spacing:`, `fallback:`.
- New interactive style step (themes, overlays, Skip) and social preset buttons in the collage builder.
- Persistent artwork cache under `data/collage_cache/` (kept in the Docker volume).

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
