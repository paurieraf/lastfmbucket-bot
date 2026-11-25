# Design

## Context

`src/admin.py` implements a standalone NiceGUI (v3.5.0) admin dashboard backed by Peewee (v3.18.3) models defined in `src/db.py` (`User`, `Chat`, `CommandLog`, `ChatMember`, `Crown`). See `proposal.md` for motivation and scope.

**Ownership & environment constraints:**
- Only `src/admin.py` and the new `tests/test_admin.py` may be modified or created. `src/db.py`, `src/config.py`, `docker-compose.yml`, and `.env.template` are owned by sibling parallel changes and MUST remain untouched.
- The project's `.venv` runs Python 3.14 with `nicegui`, `peewee`, and `python-dotenv`, and does **not** include `pytest`. Tests must use Python stdlib `unittest`.
- `src/db.py` executes `db.connect()`, `db.create_tables(MODELS, safe=True)`, and `run_migrations()` at import time.

## Goals / Non-Goals

**Goals:**
- Harden authentication and startup behavior in `src/admin.py` without changing external env var names (`ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_PORT`, `ADMIN_SECRET_KEY`).
- Eliminate duplicate-timestamp Quasar `row_key` collisions and N+1 queries across all admin tables.
- Extract shared UI helpers (navigation header, confirmation dialog) and pure query/auth helpers so core logic is unit-testable without starting a NiceGUI server.
- Provide full model visibility in the admin UI by adding `/crowns`, `/members`, and Dashboard cards for Linked Users and Total Crowns.

**Non-Goals:**
- Modifying database schemas, migrations, or `src/db.py` helper functions.
- Multi-user accounts, RBAC, or persistent/distributed rate-limit backends (e.g., Redis).
- Browser/E2E UI automation tests or adding new third-party dependencies.

## Decisions

### 1. Explicit `.env` loading and weak-password detection
- **Decision**: Call `load_dotenv()` at the top of `src/admin.py` before reading `ADMIN_*` environment variables and before importing `db`. Add a helper `is_weak_password(password: str) -> bool` (returns `True` when `(password or "").strip() == ""` or `password == "changeme"`) and `warn_if_weak_password(password: str, log: logging.Logger | None = None) -> bool` invoked inside `run_admin()`.
- **Rationale**: Removes implicit reliance on `db` -> `config` calling `load_dotenv()`. Using `logging.getLogger(__name__)` keeps startup warnings structured and testable via `assertLogs`, while never printing `ADMIN_PASSWORD` or `ADMIN_SECRET_KEY`.
- **Alternatives considered**: Raising an exception on `"changeme"` was rejected because local dev and existing deployments without `.env` overrides might rely on startup succeeding while operators see the warning.

### 2. Constant-time credential verification
- **Decision**: Add `verify_credentials(username: str, password: str, expected_username: str | None = None, expected_password: str | None = None) -> bool` using `secrets.compare_digest`. Evaluate both comparisons unconditionally (`user_ok = secrets.compare_digest(...)`, `pass_ok = secrets.compare_digest(...)`, `return user_ok and pass_ok`) so short-circuiting does not leak whether the username matched. Default `expected_*` to module-level `ADMIN_USERNAME` / `ADMIN_PASSWORD`, while allowing explicit overrides in unit tests.
- **Rationale**: Prevents timing side-channel attacks and decouples auth verification from NiceGUI widgets for direct unit testing.

### 3. In-memory per-IP / session brute-force rate limiter
- **Decision**: Implement a `LoginRateLimiter` class in `src/admin.py` with configurable `max_attempts: int = 5`, `window_seconds: int = 300`, `lockout_seconds: int = 300`, and an injectable `clock: Callable[[], float] = time.monotonic`.
  - Tracks per-key failure timestamps (pruned to `window_seconds`) and `locked_until` timestamps.
  - Exposes `is_locked(key) -> tuple[bool, int]` (locked status + remaining whole seconds), `record_failure(key) -> tuple[bool, int]`, `record_success(key) -> None`, and `reset() -> None`.
  - Instantiate a module-level `login_rate_limiter = LoginRateLimiter()`.
  - In `login_page(client: Client)`, resolve the client key via a helper `get_client_rate_limit_key(client) -> str`: check `X-Forwarded-For` header (first comma-separated entry) on `client.request` if present, else `client.ip`, else `app.storage.browser.get("id")` or `"anonymous"`.
- **Rationale**: Works out-of-the-box behind Caddy (`Caddyfile` is in the repo) and in direct local runs, requires no extra dependencies, and is 100% deterministic to test with a fake clock.
- **Alternatives considered**: Storing attempts only in `app.storage.user` was rejected because an attacker can clear cookies to bypass per-session throttling.

### 4. Pure query helpers with `JOIN.LEFT_OUTER` and unique `id` row keys
- **Decision**: Extract data-fetching and row-shaping helpers from the NiceGUI page functions:
  - `format_timestamp(ts: int | None) -> str`: returns `"-"` if `ts is None or ts <= 0`, otherwise `datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")`.
  - `get_dashboard_stats() -> dict[str, int]`: computes `total_users`, `linked_users` (`User.select().where((User.lastfm_username != "") & User.lastfm_username.is_null(False)).count()`), `total_chats`, `total_crowns`, `total_commands`, and `commands_today`.
  - `fetch_command_log_rows(limit: int = 100, command_filter: str = "", user_filter: str = "") -> list[dict]`: queries `CommandLog.select(CommandLog, Chat).join(Chat, JOIN.LEFT_OUTER).order_by(CommandLog.timestamp.desc(), CommandLog.id.desc()).limit(limit)`. Each row dict includes `"id": c.id` and accesses `c.chat` safely only when `c.chat_id is not None` (Peewee with `LEFT_OUTER` join populates `c.chat` without issuing another query; checking `c.chat_id` prevents a lazy fetch on `NULL`).
  - `fetch_crown_rows(artist_filter: str = "", chat_filter: str = "", limit: int = 200) -> list[dict]`: queries `Crown.select(Crown, Chat, User).join(Chat, JOIN.LEFT_OUTER).switch(Crown).join(User, JOIN.LEFT_OUTER).order_by(Crown.updated_at.desc(), Crown.id.desc()).limit(limit)`. Supports filtering on `Crown.artist_name.contains(...)` and `Chat.telegram_chat_name.contains(...)`. Row dict includes `"id"`, `"chat_name"`, `"artist_name"`, `"holder"` (`telegram_username` or `lastfm_username` or `str(telegram_id)`), `"playcount"`, `"updated_at"`.
  - `fetch_chat_member_rows(chat_filter: str = "", user_filter: str = "", limit: int = 200) -> list[dict]`: queries `ChatMember.select(ChatMember, Chat, User).join(Chat, JOIN.LEFT_OUTER).switch(ChatMember).join(User, JOIN.LEFT_OUTER).order_by(ChatMember.last_active.desc(), ChatMember.id.desc()).limit(limit)`. Supports filtering on `Chat.telegram_chat_name.contains(...)` and `(User.telegram_username.contains(...) | User.lastfm_username.contains(...))`. Row dict includes `"id"`, `"chat_name"`, `"telegram_username"`, `"lastfm_username"`, `"last_active"`, `"opt_out"`.
  - `delete_user_by_id(user_id: int) -> int` and `delete_crown_by_id(crown_id: int) -> int`: thin Peewee delete helpers.
  - All `ui.table(...)` calls use `row_key="id"`.
- **Rationale**: Fixes Quasar duplicate-key rendering bugs on Dashboard and `/logs`, guarantees O(1) SQL queries per table load instead of O(N+1), and allows direct unit testing against an in-memory SQLite database.

### 5. Shared navigation header and confirmation dialog helpers
- **Decision**:
  - Extract `render_nav_header(active_path: str = "") -> None` rendering `ui.header().classes("bg-blue-600")` with navigation buttons for `/`, `/users`, `/chats`, `/logs`, `/crowns`, `/members`, and Logout. Highlight the active route button (e.g. `underline` / `bg-blue-700` class).
  - Extract `open_confirm_dialog(title: str, message: str, on_confirm: Callable[[], None]) -> None` using NiceGUI `ui.dialog()` with Cancel and Confirm Delete buttons. Use it in `/users` (warning that deleting a user also cascades to their chat memberships and crowns) and `/crowns` (confirming crown removal).
- **Rationale**: Eliminates 4x copy-pasted header markup (which would otherwise become 6x with `/crowns` and `/members`) and provides a consistent safety barrier for destructive operations.

### 6. Unit testing architecture (`tests/test_admin.py`)
- **Decision**: Create `tests/test_admin.py` using stdlib `unittest`:
  - Ensure `src` is on `sys.path` so `import admin` and `import db` work when invoked from repo root (`uv run python -m unittest discover -s tests`).
  - Use a per-test in-memory `SqliteDatabase(":memory:", pragmas={"foreign_keys": 1})` bound to `db.MODELS` in `setUp` and restored to `db.db` in `tearDown`.
  - Verify single-query execution (no N+1) by wrapping `test_db.execute_sql` with a counter during `fetch_command_log_rows`, `fetch_crown_rows`, and `fetch_chat_member_rows` calls across multiple seeded rows (including a `CommandLog` with `chat=None`).
  - Cover `verify_credentials`, `is_weak_password` / `warn_if_weak_password`, `LoginRateLimiter` (lockout, cooldown expiry, reset on success, per-key isolation), `format_timestamp`, `get_dashboard_stats`, `fetch_*_rows` (filters, `id` uniqueness with duplicate timestamps, single-query join), and `delete_*_by_id` (including cascade behavior on `User`).

## Risks / Trade-offs

- **In-memory rate limiter resets on restart** → Acceptable for a single-instance admin container; keeps zero external dependencies.
- **Client IP spoofing via `X-Forwarded-For` if exposed directly** → The admin service is intended behind Caddy/reverse proxy; rate limiting is defense-in-depth alongside strong `ADMIN_PASSWORD`.
- **Import-time DB connection in `src/db.py`** → `src/db.py` is outside this change's owned scope; `tests/test_admin.py` rebinds `db.MODELS` to an in-memory SQLite database in `setUp`/`tearDown` so tests never mutate the production/local SQLite file.
