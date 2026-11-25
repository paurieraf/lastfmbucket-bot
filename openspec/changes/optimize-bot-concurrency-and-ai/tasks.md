# Tasks

## 1. Centralized Configuration & Logging Hygiene

- [ ] 1.1 Ensure `src/config.py` defines centralized Ollama (`OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_MAX_CONCURRENT`) and collage cache (`COLLAGE_CACHE_DIR`, `COLLAGE_CACHE_MAX_AGE_DAYS`, `COLLAGE_CACHE_MAX_MB`, `COLLAGE_CACHE_CLEANUP_INTERVAL_SECONDS`) settings with safe defaults, reusing any keys already added by prerequisite changes; verify importing `config` exposes all constants with expected default types.
- [ ] 1.2 Remove redundant `logging.basicConfig(...)` calls from library modules (`src/db.py`, `src/lastfm.py`, `src/services.py`, `src/ai.py`, `src/commands.py`), keep entrypoint logging configuration in `src/bot.py` and `src/admin.py`, and remove redundant `load_dotenv()` calls from `src/bot.py` and `src/commands.py`; verify via `rg "basicConfig|load_dotenv" src/` that `basicConfig` exists only in entrypoints and `load_dotenv` only in `src/config.py`.

## 2. Eliminate Remaining Event-Loop Blocking I/O

- [ ] 2.1 In `src/services.py`, offload `track.get_album()` and `album.get_cover_image()` in `ViewService.build_np_response` and `ViewService.build_status_response` via `_run_lastfm_call`, and offload `config.CHANGELOG_PATH.read_text(encoding="utf-8")` in `ViewService.build_changelog_response` via `asyncio.to_thread`; verify by creating `tests/test_concurrency_ai.py` with tests asserting these calls go through `_run_lastfm_call` / `asyncio.to_thread` and respect `LASTFM_SEMAPHORE`.
- [ ] 2.2 In `src/services.py`, extract synchronous Pillow `export_image()` + temp file read/remove logic in `CollageService.generate_collage_image` into a sync helper invoked via `asyncio.to_thread` (preserving PNG fallback on unsupported formats); verify with Ruff (`ASYNC230` clean) and tests in `tests/test_concurrency_ai.py` confirming off-thread execution and PNG fallback.
- [ ] 2.3 Offload synchronous SQLite writes in `@log_command` (`src/commands.py`) and passive chat-member tracking (`src/bot.py`) via `await asyncio.to_thread(...)`; verify existing `src/tests.py` command-logging tests still pass and add tests in `tests/test_concurrency_ai.py` confirming `asyncio.to_thread` is used for both paths.

## 3. Optimize `/compare` Last.fm API Calls

- [ ] 3.1 Add `get_user_playcount`, `get_user_top_artists`, and pure `compute_common_artists` to `src/lastfm.py`, expose async wrappers on `LastfmService`, and refactor `ViewService.build_compare_response` (`src/services.py`) to run all 4 Last.fm calls (`playcount` + `top_artists(limit=50)` × 2 users) concurrently via `asyncio.gather` and compute top-3 display + top-10 common artists in memory; verify with tests in `tests/test_concurrency_ai.py` asserting exactly 4 Last.fm calls (no `top_albums`/`top_tracks` or duplicate `top_artists`), concurrent execution, and identical output formatting.

## 4. Eliminate N+1 SQL Queries in Crowns Leaderboard

- [ ] 4.1 Refactor `db.get_chat_crowns_leaderboard` (`src/db.py`) to eagerly join `User` in the crown count query and fetch top-3 sample crowns per user in a single batched `ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY playcount DESC, id ASC)` query; verify with tests in `tests/test_concurrency_ai.py` counting executed SQL statements (`<= 3` queries for a 10-user leaderboard) and asserting exact ranking order, sample artist ordering, and empty-chat handling.

## 5. Harden and Bound Ollama AI Generation

- [ ] 5.1 Refactor `src/ai.py` to use `config.OLLAMA_*`, configure `ollama.AsyncClient(host=config.OLLAMA_HOST, timeout=config.OLLAMA_TIMEOUT)`, guard generation with `OLLAMA_SEMAPHORE = asyncio.Semaphore(config.OLLAMA_MAX_CONCURRENT)` and `asyncio.wait_for(..., timeout=config.OLLAMA_TIMEOUT)`, and reset `_MODEL_READY = False` on generation failure so lazy cooldown re-checks recover after an Ollama restart; verify with tests in `tests/test_concurrency_ai.py` covering timeout fallback, concurrency cap (`max_in_flight == 1`), and post-failure recovery via `ensure_model_exists`.
- [ ] 5.2 Update `TestBotCoreAndLifecycle.test_post_init_registers_commands` in `src/tests.py` to mock `ai.ensure_model_exists` (`AsyncMock(return_value=True)`); verify running `pytest src/tests.py -k test_post_init_registers_commands` completes immediately with zero network calls.

## 6. Bounded Collage Disk Cache Eviction

- [ ] 6.1 Implement synchronous `_cleanup_cache_sync` (TTL age eviction followed by oldest-first max-size eviction, ignoring transient `OSError`s) and throttled async `maybe_cleanup_cache` (via `asyncio.to_thread`) on `CollageService` (`src/services.py`), invoked safely after `generate_collage_image`; verify with tests in `tests/test_concurrency_ai.py` covering TTL expiry, max-size eviction order, throttling, and error resilience.

## 7. Integration Verification

- [ ] 7.1 Run the full test suite (`pytest` / `uv run pytest src/tests.py tests/test_concurrency_ai.py`) and linter (`uv run ruff check src/ tests/test_concurrency_ai.py`) to confirm all existing and new tests pass with zero lint errors.
