# Proposal: Optimize Bot Concurrency, Queries, and AI Resilience

## Why

Although `bot-concurrency` introduced concurrent Telegram update handling and a Last.fm semaphore, several synchronous I/O and CPU-bound operations still execute directly on the `asyncio` event loop—including `pylast` album/cover lookups in `/np` and `/status`, Pillow collage export and temporary file I/O, SQLite writes in `@log_command` and passive chat-member tracking, and `CHANGELOG.md` disk reads. In addition, `/compare` performs 10 Last.fm HTTP requests (including unused album/track fetches and duplicate top-artist calls), `db.get_chat_crowns_leaderboard` executes an N+1 query pattern (22 queries for top 10), `src/ai.py` has no request timeout, concurrency bound, or restart recovery for the 2 GB Ollama container, and `data/collage_cache` grows on disk without eviction.

## What Changes

- **Eliminate all remaining event-loop blocking I/O**:
  - Offload `track.get_album()` and `album.get_cover_image()` in `ViewService.build_np_response` and `ViewService.build_status_response` via `_run_lastfm_call` (`asyncio.to_thread` + `LASTFM_SEMAPHORE`).
  - Offload synchronous Pillow `export_image()` and temporary file I/O in `CollageService.generate_collage_image` via `asyncio.to_thread`.
  - Offload synchronous SQLite writes in `@log_command` (`src/commands.py`) and passive member tracking (`src/bot.py`) via `asyncio.to_thread`.
  - Offload `CHANGELOG.md` reads in `ViewService.build_changelog_response` via `asyncio.to_thread`.
- **Optimize `/compare` Last.fm API usage**:
  - Refactor `LastfmClient`, `LastfmService`, and `ViewService.build_compare_response` so `/compare` makes 4 concurrent Last.fm calls total (`playcount` + `top_artists(limit=50)` for each of the two users) instead of 10, computing both top-3 display lists and common artists in memory.
- **Eliminate N+1 queries in crowns leaderboard**:
  - Refactor `db.get_chat_crowns_leaderboard` to join `User` eagerly and fetch top-3 sample crowns per user in a single batched window-function query (`ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY playcount DESC)`), reducing query count from `2 + 2N` to a constant 3 queries.
- **Harden and bound Ollama AI generation (`src/ai.py`)**:
  - Consume centralized configuration (`config.OLLAMA_HOST`, `config.OLLAMA_MODEL`, `config.OLLAMA_TIMEOUT`, `config.OLLAMA_MAX_CONCURRENT`).
  - Enforce explicit HTTP client timeout and `asyncio.wait_for` timeout guard on generation calls.
  - Bound concurrent Ollama generations with an `asyncio.Semaphore` (default `1`, matching `OLLAMA_NUM_PARALLEL=1` in the 2 GB container).
  - Reset `_MODEL_READY = False` on generation failure so the lazy cooldown re-check recovers automatically after an Ollama restart.
  - Mock `ai.ensure_model_exists` in `test_post_init_registers_commands` (`src/tests.py`) so unit tests never make live network calls to Ollama.
- **Add bounded collage disk cache eviction (`src/services.py`)**:
  - Enforce TTL age and maximum total size limits on `data/collage_cache` via a throttled off-thread cleanup routine (`asyncio.to_thread`).
- **Centralize logging and environment loading**:
  - Remove redundant `logging.basicConfig()` calls from library modules (`src/db.py`, `src/lastfm.py`, `src/services.py`, `src/ai.py`, `src/commands.py`) so logging is configured only at entrypoints (`src/bot.py`, `src/admin.py`).
  - Remove redundant `load_dotenv()` calls in `src/bot.py` and `src/commands.py` (already handled in `src/config.py`).
- **Add dedicated test coverage**:
  - Create `tests/test_concurrency_ai.py` covering non-blocking offloading, `/compare` 4-call optimization, crowns leaderboard query count and accuracy, Ollama timeout/semaphore/recovery behavior, and collage cache eviction.

## Capabilities

### New Capabilities

<!-- None: all behavioral requirements extend existing capabilities. -->

### Modified Capabilities

- `bot-concurrency`: Extend non-blocking I/O requirements to cover album/cover lookups, SQLite logging/tracking writes, and changelog reads; tighten `/compare` to 4 concurrent Last.fm calls; add bounded concurrency, timeout enforcement, and restart recovery for Ollama AI generation.
- `collage-async-pipeline`: Require image export and temp file I/O to execute off the event loop, and add bounded TTL + size-cap disk cache eviction for `data/collage_cache`.

## Impact

- **Affected source files**: `src/config.py`, `src/ai.py`, `src/lastfm.py`, `src/services.py`, `src/db.py`, `src/commands.py`, `src/bot.py`, `src/tests.py`.
- **New test file**: `tests/test_concurrency_ai.py`.
- **Dependencies**: No new third-party dependencies required; uses Python standard library (`asyncio.to_thread`, `asyncio.Semaphore`, `asyncio.wait_for`), SQLite window functions (SQLite 3.25+), and existing `ollama.AsyncClient(timeout=...)`.
- **Sequencing**: Planned to be implemented after `fix-bot-stability-and-security` and `improve-devops-and-quality` are merged, building cleanly on centralized `config.OLLAMA_*` / `config.COLLAGE_CACHE_*` settings and passive member tracking.
