# Design: Optimize Bot Concurrency, Queries, and AI Resilience

## Context

See `proposal.md` for motivation and scope. This change is sequenced after `fix-bot-stability-and-security` and `improve-devops-and-quality` are merged, so centralized configuration (`src/config.py` with `OLLAMA_*` and `COLLAGE_CACHE_*` settings) and passive group-member tracking (`src/bot.py`) are available.

Current bottlenecks observed in the codebase:
- `ViewService.build_np_response` (`src/services.py:214-216`) and `ViewService.build_status_response` (`src/services.py:335-337`) call `track.get_album()` and `album.get_cover_image()` synchronously on the event loop; both trigger `pylast` HTTP calls.
- `CollageService.generate_collage_image` (`src/services.py:1198-1220`) runs Pillow `export_image()`, `open()`, and `os.remove()` synchronously on the event loop (violating Ruff `ASYNC230` and stalling updates on large grids like 10×10 / 4K).
- `@log_command` (`src/commands.py:54`) and passive member tracking (`src/bot.py`) invoke synchronous Peewee/SQLite writes on the event loop; `ViewService.build_changelog_response` (`src/services.py:458`) reads `CHANGELOG.md` synchronously.
- `ViewService.build_compare_response` (`src/services.py:527-533`) executes `get_user_stats` (4 HTTP calls × 2 users, including unused `top_albums` and `top_tracks`) plus `get_common_artists` (2 more HTTP calls) = 10 HTTP calls total.
- `db.get_chat_crowns_leaderboard` (`src/db.py:389-424`) executes `1 + 1 + 2N` SQL queries (1 `Chat` lookup, 1 grouped count query, N lazy FK `User` lookups on `entry.user`, and N per-user top-3 `Crown` queries = 22 queries for top 10).
- `src/ai.py` creates `ollama.AsyncClient(host=OLLAMA_HOST)` directly from `os.getenv`, with no timeout, no concurrency semaphore (despite `OLLAMA_NUM_PARALLEL=1` and a 2 GB RAM limit in `docker-compose.yml`), and never resets `_MODEL_READY = False` if generation fails after Ollama restarts.
- `src/tests.py::TestBotCoreAndLifecycle.test_post_init_registers_commands` calls `bot.post_init(mock_app)` without mocking `ai.ensure_model_exists`, triggering a live connection attempt to `http://ollama:11434`.
- `data/collage_cache` is populated by `lastfmcollagegenerator` with no eviction policy.
- `logging.basicConfig(...)` is called at import time in five library modules (`db.py`, `lastfm.py`, `services.py`, `ai.py`, `commands.py`), and `load_dotenv()` is duplicated in `bot.py` and `commands.py`.

## Goals / Non-Goals

**Goals:**
- Zero blocking network, disk, SQLite write, or Pillow image-export operations on the `asyncio` event loop in command/update paths.
- Reduce `/compare` from 10 Last.fm HTTP requests to 4 concurrent requests without changing user-visible output format.
- Reduce `db.get_chat_crowns_leaderboard` from `2 + 2N` SQL queries to a constant 3 queries while preserving exact return structure and ordering.
- Protect the 2 GB Ollama container from request pile-ups and hangs via centralized config, explicit timeouts, a concurrency semaphore (default 1), and automatic `_MODEL_READY` reset on failure.
- Bound `data/collage_cache` disk growth via throttled off-thread TTL + max-size eviction.
- Keep logging configuration strictly at entrypoints (`src/bot.py`, `src/admin.py`) and `load_dotenv()` strictly in `src/config.py`.

**Non-Goals:**
- Migrating Peewee/SQLite to an async ORM (e.g. `aiosqlite` / SQLAlchemy async). `asyncio.to_thread` with SQLite WAL mode and `busy_timeout=5000` is sufficient for this bot's write volume.
- Replacing `pylast` with a custom async Last.fm HTTP client.
- Changing user-facing message templates or Telegram callback schemas.
- Adding a background cron daemon for cache cleanup (throttled in-process cleanup off-thread avoids extra lifecycle complexity).

## Decisions

### 1. Offloading remaining blocking I/O via `_run_lastfm_call` and `asyncio.to_thread`
- **Last.fm album/cover lookups (`src/services.py`)**:
  - In `ViewService.build_np_response`:
    ```python
    album = await _run_lastfm_call(track.get_album)
    track_album = album.title if album else ""
    cover_image = (
        await _run_lastfm_call(album.get_cover_image)
        if (show_cover and album)
        else None
    )
    ```
  - In `ViewService.build_status_response`:
    ```python
    if show_cover:
        try:
            last_played_track_album = await _run_lastfm_call(last_played_track.get_album)
            if last_played_track_album:
                cover_url = await _run_lastfm_call(last_played_track_album.get_cover_image)
        except Exception:
            pass
    ```
  - *Alternative considered*: Wrapping `get_album` + `get_cover_image` in a single helper passed to `_run_lastfm_call`. Running them as separate `_run_lastfm_call` calls (when `show_cover=True`) keeps each Last.fm HTTP call individually accounted for by `LASTFM_SEMAPHORE` and avoids holding a semaphore slot across two sequential network round-trips unnecessarily.
- **Pillow collage export & temp file I/O (`src/services.py`)**:
  - Extract a synchronous helper `_export_collage_to_bytes(image, export_format: str) -> BytesIO` on `CollageService` (or module-level) that performs `NamedTemporaryFile`, `export_image(...)` with PNG fallback, reading bytes into `BytesIO`, and `os.remove(tmp_path)` inside `try/finally`.
  - Call `await asyncio.to_thread(_export_collage_to_bytes, image, export_format)` from `CollageService.generate_collage_image`.
  - This eliminates `ASYNC230` (blocking `open()` in async function) and keeps Pillow CPU compression off the event loop.
- **SQLite writes in `@log_command` (`src/commands.py`) and passive member tracking (`src/bot.py`)**:
  - Wrap `db.log_command(...)` in `await asyncio.to_thread(db.log_command, ...)` inside `@log_command`.
  - Wrap `db.track_chat_member(...)` in `await asyncio.to_thread(db.track_chat_member, ...)` inside the passive chat-member tracking handler in `src/bot.py`.
  - *Note on test compatibility*: Existing tests patch `db.log_command` / `commands.db.log_command` with a synchronous `MagicMock`; `asyncio.to_thread(db.log_command, ...)` calls that mock with the exact same keyword arguments, preserving full backward compatibility.
- **Changelog read (`src/services.py`)**:
  - In `ViewService.build_changelog_response`, replace `config.CHANGELOG_PATH.read_text(encoding="utf-8")` with `await asyncio.to_thread(config.CHANGELOG_PATH.read_text, encoding="utf-8")`.
  - *Alternative considered*: Caching `CHANGELOG.md` forever at import time. Offloading `read_text` via `asyncio.to_thread` avoids stale-file edge cases if `CHANGELOG.md` is updated or patched in tests while costing negligible overhead.

### 2. Optimizing `/compare` from 10 to 4 concurrent Last.fm HTTP calls
- **Design**:
  - Add two focused methods on `LastfmClient` (`src/lastfm.py`):
    - `get_user_playcount(self, username: str) -> int | None`: fetches `self.client.get_user(username).get_playcount()` (returns `int` or `None` on error).
    - `get_user_top_artists(self, username: str, period: Period = Period.OVERALL, limit: int = 50) -> list[dict] | None`: fetches `get_top_artists(period=period, limit=limit)` and returns `[{"name": item.item.name, "plays": int(item.weight)}, ...]` (or `None` on error).
  - Add a pure helper `compute_common_artists(artists1: list[dict], artists2: list[dict], limit: int = 10) -> list[dict]` (in `src/lastfm.py` or `src/services.py`) that matches artist names case-insensitively (`name.lower()`), preserves `artists1` ordering and canonical casing, and returns up to `limit` dicts `{"name", "plays1", "plays2"}`—matching the exact behavior of `get_common_artists`.
  - Expose `get_user_playcount` and `get_user_top_artists` async wrappers on `LastfmService` via `_run_lastfm_call`.
  - In `ViewService.build_compare_response`:
    ```python
    playcount1, artists1, playcount2, artists2 = await asyncio.gather(
        self.lastfm_service.get_user_playcount(user.lastfm_username),
        self.lastfm_service.get_user_top_artists(user.lastfm_username, limit=50),
        self.lastfm_service.get_user_playcount(other_lastfm_username),
        self.lastfm_service.get_user_top_artists(other_lastfm_username, limit=50),
    )
    ```
    - If `playcount1 is None or artists1 is None` -> return `compare_user_not_found` for `user.lastfm_username`.
    - If `playcount2 is None or artists2 is None` -> return `compare_user_not_found` for `other_lastfm_username`.
    - Slice `artists1[:3]` and `artists2[:3]` for top-3 display, and compute `common_artists = compute_common_artists(artists1, artists2, limit=10)` in memory.
  - Keep `LastfmClient.get_user_stats` and `LastfmClient.get_common_artists` intact if any external callers or tests reference them, or have `get_common_artists` delegate to `compute_common_artists`.
- *Alternative considered*: Fetching `get_user_compare_data(username)` (2 sequential calls per user) in parallel across 2 users. Splitting into 4 independent `_run_lastfm_call` tasks allows all 4 HTTP requests to run concurrently under `LASTFM_SEMAPHORE`, cutting latency in half while keeping total HTTP calls at 4.

### 3. Eliminating N+1 queries in `db.get_chat_crowns_leaderboard`
- **Design**:
  - Query 1: `chat = Chat.get_or_none(telegram_id=chat_id)` (return `[]` if not found).
  - Query 2: Eagerly join `User` when counting crowns:
    ```python
    crown_counts = list(
        Crown.select(Crown.user, User, fn.COUNT(Crown.id).alias("count"))
        .join(User)
        .where(Crown.chat == chat)
        .group_by(Crown.user)
        .order_by(SQL("count DESC"))
        .limit(limit)
    )
    ```
    If `not crown_counts`, return `[]`. Collect `user_ids = [entry.user_id for entry in crown_counts]`.
  - Query 3: Single batched SQLite window-function query for top-3 sample crowns per user:
    ```sql
    SELECT user_id, artist_name, artist_url, playcount
    FROM (
        SELECT
            user_id,
            artist_name,
            artist_url,
            playcount,
            ROW_NUMBER() OVER (
                PARTITION BY user_id
                ORDER BY playcount DESC, id ASC
            ) AS rn
        FROM crown
        WHERE chat_id = ? AND user_id IN (?, ?, ...)
    ) ranked
    WHERE rn <= 3
    ORDER BY user_id, playcount DESC, id ASC
    ```
    Group rows into `samples_by_user: dict[int, list[dict]]` and assemble `[{"user": entry.user, "crown_count": entry.count, "samples": samples_by_user.get(entry.user_id, [])} for entry in crown_counts]`.
  - *Alternative considered*: Fetching all crowns for those `user_ids` without a window function and slicing top-3 in Python. A window function pushes the top-3 filter into SQLite so users with hundreds of crowns don't transfer hundreds of unnecessary rows. SQLite 3.25+ (Python 3.14 bundles SQLite 3.45+) natively supports `ROW_NUMBER() OVER (...)`.

### 4. Hardening and bounding AI / Ollama (`src/ai.py` & `src/config.py`)
- **Configuration (`src/config.py`)**:
  - Ensure centralized settings exist with safe defaults:
    - `OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")`
    - `OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")`
    - `OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30.0"))`
    - `OLLAMA_MAX_CONCURRENT = int(os.getenv("OLLAMA_MAX_CONCURRENT", "1"))`
- **Client & Concurrency (`src/ai.py`)**:
  - Initialize `client = ollama.AsyncClient(host=config.OLLAMA_HOST, timeout=config.OLLAMA_TIMEOUT)`.
  - Define `OLLAMA_SEMAPHORE = asyncio.Semaphore(config.OLLAMA_MAX_CONCURRENT)` (matching `OLLAMA_NUM_PARALLEL=1` in the 2 GB container).
  - Centralize generation execution in an internal helper `_generate_text(prompt: str, options: dict) -> str`:
    ```python
    async with OLLAMA_SEMAPHORE:
        response = await asyncio.wait_for(
            client.generate(
                model=config.OLLAMA_MODEL,
                prompt=prompt,
                options=options,
            ),
            timeout=config.OLLAMA_TIMEOUT,
        )
        return response.response.strip()
    ```
  - On any exception inside `_generate_text` (including `asyncio.TimeoutError`, `httpx.TimeoutException`, `ConnectionError`, `ollama.ResponseError`, or `RuntimeError`):
    - Set `_MODEL_READY = False` (leaving `_LAST_MODEL_CHECK` untouched so the next request after cooldown—or immediately if the last check was >60 s ago—re-runs `ensure_model_exists()`, which itself updates `_LAST_MODEL_CHECK` in `finally:` so repeated failures respect the 60 s cooldown).
    - Re-raise so `generate_vibe`, `generate_roast`, and `generate_recommendations` log the error and return their respective friendly fallback messages.
  - Note: Also apply `asyncio.wait_for(..., timeout=config.OLLAMA_TIMEOUT)` to `client.list()` in `ensure_model_exists()` so startup / lazy readiness checks cannot hang indefinitely (while keeping `client.pull()` generous or guarded by the client timeout).
- **Test isolation (`src/tests.py`)**:
  - In `TestBotCoreAndLifecycle.test_post_init_registers_commands`, patch `bot.ai.ensure_model_exists` with `AsyncMock(return_value=True)` and assert it was awaited once.

### 5. Bounded collage disk cache eviction (`src/services.py` & `src/config.py`)
- **Configuration (`src/config.py`)**:
  - `COLLAGE_CACHE_DIR = ...` (default `PROJECT_ROOT / "data" / "collage_cache"`)
  - `COLLAGE_CACHE_MAX_AGE_DAYS = float(os.getenv("COLLAGE_CACHE_MAX_AGE_DAYS", "7"))`
  - `COLLAGE_CACHE_MAX_MB = float(os.getenv("COLLAGE_CACHE_MAX_MB", "200"))`
  - `COLLAGE_CACHE_CLEANUP_INTERVAL_SECONDS = float(os.getenv("COLLAGE_CACHE_CLEANUP_INTERVAL_SECONDS", "3600"))`
- **Eviction algorithm (`CollageService.cleanup_cache`)**:
  - Synchronous method `_cleanup_cache_sync(cache_dir: str, max_age_seconds: float, max_bytes: int) -> int`:
    1. Walk files in `cache_dir` (recursively via `os.walk` or `Path.rglob("*")`, skipping directories).
    2. For each file, `stat()` it (ignoring `FileNotFoundError` / `OSError`).
    3. If `now - st.st_mtime > max_age_seconds`, `os.remove()` it (ignoring `OSError`).
    4. Collect remaining `(mtime, size, path)` tuples; compute `total_size`.
    5. If `total_size > max_bytes`, sort ascending by `mtime` (oldest first) and delete files until `total_size <= max_bytes`.
    6. Return count of deleted files and log at `INFO` when > 0.
  - Async throttled trigger `maybe_cleanup_cache()` called at the end of `CollageService.generate_collage_image`:
    - Checks `time.monotonic() - self._last_cleanup >= self._cleanup_interval`.
    - If due, updates `self._last_cleanup = time.monotonic()` and runs `await asyncio.to_thread(self._cleanup_cache_sync, ...)` inside a `try/except Exception` block so cleanup failures never fail the user's collage response.

### 6. Logging and `load_dotenv()` hygiene
- Remove `logging.basicConfig(...)` from `src/db.py`, `src/lastfm.py`, `src/services.py`, `src/ai.py`, and `src/commands.py`, keeping `logger = logging.getLogger(__name__)` in each module.
- Also replace stray `logging.warning(...)` / `logging.info(...)` calls in `src/services.py` and `src/db.py` with `logger.warning(...)` / `logger.info(...)` where touched.
- Keep `logging.basicConfig(...)` in `src/bot.py` and add/keep it in `src/admin.py` entrypoint.
- Remove redundant `from dotenv import load_dotenv` + `load_dotenv()` from `src/bot.py` and `src/commands.py` since `src/config.py` calls `load_dotenv()` on import.

## Risks / Trade-offs

- **SQLite write concurrency under `asyncio.to_thread`** → Peewee's `SqliteExtDatabase` opens per-thread connections automatically; combined with WAL mode and `busy_timeout=5000` (already configured in `src/db.py`), concurrent thread writes serialize cleanly without `database is locked` errors.
- **Semaphore bound on Ollama (`OLLAMA_MAX_CONCURRENT=1`)** → Under simultaneous AI commands, the second user waits until the first finishes (or times out). This is intentional: the Ollama container runs with `OLLAMA_NUM_PARALLEL=1` and 2 GB RAM, so queuing in the bot prevents HTTP connection pile-ups and container OOMs.
- **Timeout on `asyncio.wait_for` vs `ollama.AsyncClient(timeout=...)`** → Using both ensures that both socket-level stalls (httpx) and hung async generators/responses are bounded by `config.OLLAMA_TIMEOUT`.
- **Throttled cache cleanup running at end of collage generation** → Adds a tiny off-thread directory scan at most once per hour. Running it after `generate_collage_image` builds the `BytesIO` (or via `asyncio.to_thread` with error isolation) ensures zero impact on normal requests and prevents race conditions with an in-progress generation.
- **Merge sequencing with `fix-bot-stability-and-security` and `improve-devops-and-quality`** → `src/config.py` and passive member tracking in `src/bot.py` may already define some of the `OLLAMA_*` / `COLLAGE_CACHE_*` keys or handler names. Tasks explicitly instruct checking existing `config.py` and `bot.py` definitions and reusing/extending them rather than duplicating.
