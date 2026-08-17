# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0] - 2026-08-17

### Added
- Upgraded `lastfmcollagegenerator` to **v1.3.1**.
- **Native Async I/O**: Switched `CollageService` from blocking thread workers (`asyncio.to_thread`) to native `await generate_async()`, boosting bot concurrency and responsiveness.
- **Optimized WebP Export & Fallback Resilience**: Integrated library's `export_image` utility with automatic fallback detection for missing WebP codecs, ensuring robust export across environments.
- **Visual Filters**: Added `filter:` (alias `fx:`) option supporting `duotone`, `bw`/`grayscale`, `sepia`, `cyberpunk`, `sunset`, `matrix`, and custom `duotone:<color1>,<color2>`.
- **Bold Typography & Custom Text Flags**: Added `bold` CLI flag for bold styling and `noplaycount` / `nocount` flags to toggle scrobble playcounts.
- **Adaptive Theme**: Added `theme:adaptive` supporting dynamic palette extraction from artwork.

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
