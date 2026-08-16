# Design: Improve Bot Concurrency

## Context

The bot is a single-process python-telegram-bot (PTB 22.x) application running `run_polling()` with default sequential update processing. Handlers are async, but `LastfmService` performs synchronous pylast HTTP calls and peewee SQLite calls directly on the event loop. `ai.py` already uses `ollama.AsyncClient` (non-blocking), and `CollageService.generate_collage_image` already runs in `asyncio.to_thread`. The NiceGUI admin process (`src/admin.py`) shares the same SQLite file in a separate process. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**

- Make updates process in parallel without changing observable command outputs.
- Keep the event loop free of network I/O waits.
- Bound Last.fm API pressure under concurrent load.

**Non-Goals:**

- Reducing single-request latency of `/collage` itself (bounded by Last.fm cover-image downloads in `lastfmcollagegenerator`; caching is future work).
- Per-user rate limiting or spam protection (a custom `BaseUpdateProcessor` could be added later without spec changes).
- Replacing pylast with an async HTTP client.
- Fixing the unrelated latent tuple-assignment bug at `db.py:101` (tracked separately).

## Decisions

### 1. Enable concurrency via `ApplicationBuilder.concurrent_updates(True)`

`ApplicationBuilder().concurrent_updates(True)` maps to 256 concurrent updates in PTB 22.x.

- *Alternatives considered:* an explicit `int` cap or a custom `BaseUpdateProcessor` for fairness/rate limiting — rejected for v1: with ~20 users 256 is safe, and a custom processor adds complexity without a current need.

### 2. Offload at the service boundary, not per call-site

`LastfmService` methods become async and wrap pylast calls in `asyncio.to_thread` (shared `ThreadPoolExecutor`). Handlers already `await` `ViewService` async methods, so the change is contained in `src/services.py`; `commands.py` only needs await-side updates where it calls the service directly (`vibe`, `roast`, `recommend`).

- *Alternatives considered:* wrapping at each handler call-site (scattered, error-prone — rejected); replacing pylast with aiohttp (large rewrite for marginal gain at 20 users — rejected).

### 3. Semaphore for Last.fm concurrency (default 8, env `LASTFM_MAX_CONCURRENT`)

An `asyncio.Semaphore` acquired inside the service's async wrappers caps in-flight Last.fm requests. Unauthenticated Last.fm API keys are limited to roughly 5 requests/second; 8 concurrent requests at typical 300ms latency stays near that envelope.

- *Alternatives considered:* no cap (risks 429s under parallel `/tops` bursts — rejected); time-based token bucket (unnecessary complexity — rejected).

### 4. DB stays synchronous on the event loop

SQLite reads/writes are local and take microseconds; keeping peewee on the loop avoids all cross-thread connection concerns (peewee autoconnect per thread, `check_same_thread`). Add a `busy_timeout` pragma as hardening for the cross-process admin dashboard, which shares the WAL database.

- *Alternative considered:* moving DB calls to threads too — rejected unless profiling shows contention.

### 5. Dedicated low-concurrency semaphore for collage generation

`lastfmcollagegenerator` performs its own Last.fm requests (top items + cover images) inside its worker thread, bypassing the service semaphore. With concurrent updates, several collages could run at once. A separate semaphore of 2 bounds collage-side API pressure while still allowing parallel collages.

- *Alternative considered:* reusing the main semaphore — rejected, it would not cover the generator's internal calls and would couple unrelated flows.

### 6. Model readiness at startup with lazy fallback

`post_init` in `bot.py` awaits `ai.ensure_model_exists()`; `ai.py` caches the result in a module-level flag. AI commands skip the per-invocation `client.list()` call when ready; if readiness failed at startup, commands retry lazily until it succeeds.

- *Alternative considered:* full removal of the check (would break first-run containers — rejected).

### 7. Intra-command parallelism via `asyncio.gather`

- `/compare`: fetch both users' stats and the common-artists list concurrently (`gather` of three to_thread coroutines), then format exactly as today.
- `/roast`: fetch top artists and top tracks concurrently.

- *Alternative considered:* leaving sequential (keeps latency high for the two slowest non-collage commands — rejected).

### 8. pylast thread-safety: spike first, fallback documented

`LastfmClient` shares one `LastFMNetwork` instance across threads once decisions 2/7 land. **Verified (task 1.1):** pylast 7.x creates a fresh `httpx.Client` per request and closes it in a `finally` block — there is no shared HTTP session or connection pool. The only shared mutable state (`last_call_time`/`limit_rate`) is untouched because rate limiting is not enabled. Sharing the client across worker threads is safe; no fallback needed.

- *Alternative considered:* a `threading.Lock` around the shared client — rejected, it would re-serialize the intra-command parallelism from decision 7.

## Risks / Trade-offs

- [Last.fm 429 rate limits under parallel load] → Service semaphore (decision 3) + collage semaphore (decision 5).
- [pylast shared client not thread-safe] → Spike task verifies; fallback is per-call client construction (decision 8).
- [Ollama generation queueing when several AI commands run at once] → Requests queue server-side; model is tiny (0.5b). If needed, `OLLAMA_NUM_PARALLEL` is an ops knob, not a code change.
- [SQLite write contention with admin dashboard process] → WAL already enabled; add `busy_timeout` pragma (decision 4).
- [256 concurrent updates could allow update floods] → Acceptable for the current user base; per-user locks are future work (non-goal).

## Migration Plan

- Deploy is a single container rebuild (`docker compose up -d --build`); no database schema or data migration.
- Rollback: revert the commit — no persisted state is affected by this change.
- Verification: send `/roast` and `/np` concurrently from two accounts and confirm `/np` responds while `/roast` is still generating; monitor bot logs for pylast exceptions under parallel load.

## Open Questions

None blocking. Future considerations that do not change this design: `OLLAMA_NUM_PARALLEL` tuning, collage/cover caching with TTL, per-user rate limiting via `BaseUpdateProcessor`.
