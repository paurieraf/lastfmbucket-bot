# Tasks: Improve Bot Concurrency

## 1. Verification spike

- [x] 1.1 Verify pylast `LastFMNetwork` thread-safety (shared HTTP session usage) by inspecting the installed pylast source; if unsafe, note per-call client construction as the chosen fallback from design.md decision 8

## 2. Concurrency setup

- [x] 2.1 Add `.concurrent_updates(True)` to `ApplicationBuilder` in `src/bot.py`
- [x] 2.2 Add `busy_timeout` pragma to `SqliteExtDatabase` in `src/db.py` (harden against cross-process writes from the admin dashboard)

## 3. Service-level offloading

- [x] 3.1 Create a shared `ThreadPoolExecutor` and an `asyncio.Semaphore` (default 8, `LASTFM_MAX_CONCURRENT` env) in `src/services.py` or `src/lastfm.py`
- [x] 3.2 Convert `LastfmService` methods (`set_lastfm_username`, `get_now_playing`, `get_recent_tracks`, `get_tops`) to async, wrapping pylast calls in `asyncio.to_thread` behind the semaphore
- [x] 3.3 Apply pylast thread-safety fallback from task 1.1 if required (per-call `LastFMNetwork`)
- [x] 3.4 Update `ViewService` methods to `await` the now-async `LastfmService` calls
- [x] 3.5 Update handlers in `src/commands.py` that call `lastfm_service` directly (`vibe`, `roast`, `recommend`) to `await` the async methods

## 4. AI model readiness

- [x] 4.1 Cache model readiness in `src/ai.py` (module-level flag set by `ensure_model_exists`, lazy retry on failure)
- [x] 4.2 Await `ai.ensure_model_exists()` in `post_init` in `src/bot.py`; log readiness outcome

## 5. Intra-command parallelism

- [x] 5.1 Parallelize `/compare` data fetches (both user stats + common artists) with `asyncio.gather`, preserving output format
- [x] 5.2 Parallelize `/roast` top artists + top tracks fetches with `asyncio.gather`

## 6. Collage API pressure

- [x] 6.1 Add a dedicated low-concurrency semaphore (2) around `CollageService.generate_collage_image` invocations in `src/commands.py` and `_handle_collage`

## 7. Verification

- [x] 7.1 Run `uv run ruff check .` and `uv run ruff format .` clean
- [x] 7.2 Manual test: send `/roast` and `/np` from two different accounts simultaneously; confirm `/np` responds while `/roast` is still running (check log timestamps)
- [x] 7.3 Manual test: send a burst of `/tops` commands; confirm no Last.fm 429 errors and the semaphore cap is respected
- [x] 7.4 Manual test: run `/vibe` and confirm no `client.list()` call per invocation (log or timing check)
