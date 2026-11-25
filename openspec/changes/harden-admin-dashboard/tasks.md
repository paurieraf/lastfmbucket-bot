# Tasks

> **Owned files**: Only `src/admin.py` and `tests/test_admin.py`. Do not modify `src/db.py`, `src/config.py`, `docker-compose.yml`, or `.env.template`.

## 1. Startup, Authentication Hardening, and Rate Limiting

- [ ] 1.1 Call `load_dotenv()` explicitly at the top of `src/admin.py` before reading `ADMIN_*` environment variables and importing `db`, configure module `logging`, and add `is_weak_password()` / `warn_if_weak_password()` invoked from `run_admin()` (without logging raw passwords or secret keys). Create `tests/test_admin.py` with `unittest` tests verifying weak/empty/strong password detection and that warnings never leak secrets (`uv run python -m unittest tests/test_admin.py -v`).
- [ ] 1.2 Add `verify_credentials()` in `src/admin.py` using `secrets.compare_digest` for both username and password without short-circuiting, and add unit tests in `tests/test_admin.py` covering valid, invalid username, invalid password, and empty inputs (`uv run python -m unittest tests/test_admin.py -v`).
- [ ] 1.3 Implement `LoginRateLimiter` (in-memory sliding window + lockout with injectable clock) and `get_client_rate_limit_key()` in `src/admin.py`, wire rate limiting and `verify_credentials()` into `/login`, and add unit tests in `tests/test_admin.py` verifying threshold lockout, blocking during cooldown, recovery after cooldown, reset on success, and per-key isolation (`uv run python -m unittest tests/test_admin.py -v`).

## 2. Query Helpers, N+1 Elimination, and Unique Row Keys

- [ ] 2.1 Harden `format_timestamp()` for `None`/non-positive timestamps and extract `get_dashboard_stats()` and `fetch_command_log_rows()` in `src/admin.py` using `CommandLog.select(CommandLog, Chat).join(Chat, JOIN.LEFT_OUTER)` with unique `"id"` row keys. Add in-memory SQLite unit tests in `tests/test_admin.py` verifying timestamp formatting, all 6 dashboard counts (`total_users`, `linked_users`, `total_chats`, `total_crowns`, `total_commands`, `commands_today`), distinct `id` keys on duplicate timestamps, `chat=None` fallback, filters, and single-query execution (`uv run python -m unittest tests/test_admin.py -v`).
- [ ] 2.2 Add `fetch_crown_rows()`, `fetch_chat_member_rows()`, `delete_user_by_id()`, and `delete_crown_by_id()` in `src/admin.py` using `JOIN.LEFT_OUTER` on `Chat` and `User` with unique `"id"` row keys. Add in-memory SQLite unit tests in `tests/test_admin.py` verifying filtering, fallback display labels, single-query execution (no N+1), crown deletion, and cascading user deletion (`uv run python -m unittest tests/test_admin.py -v`).

## 3. Shared UI Components, Dashboard Updates, and New Model Pages

- [ ] 3.1 Extract `render_nav_header(active_path: str = "")` (linking `/`, `/users`, `/chats`, `/logs`, `/crowns`, `/members`, and Logout) and `open_confirm_dialog(title, message, on_confirm)` in `src/admin.py`, replacing all 4 copy-pasted header blocks. Verify clean module import with `PYTHONPATH=src uv run python -c "import admin"`.
- [ ] 3.2 Update `/` (Dashboard) to render all 6 summary cards (Total Users, Linked Users, Total Chats, Total Crowns, Total Commands, Commands Today) and recent commands via `fetch_command_log_rows(limit=10)` with `row_key="id"`; update `/logs` to use `fetch_command_log_rows(...)` with `row_key="id"`; update `/users` to gate user deletion behind `open_confirm_dialog` warning of cascade deletion of memberships and crowns. Verify with `PYTHONPATH=src uv run python -c "import admin"` and `uv run ruff check src/admin.py`.
- [ ] 3.3 Add `/crowns` page (auth-gated, shared nav header, artist/chat filters + Clear, `fetch_crown_rows`, `row_key="id"`, confirmation-gated crown delete) and `/members` page (auth-gated, shared nav header, chat/user filters + Clear, `fetch_chat_member_rows`, `row_key="id"`). Verify all 7 routes (`/login`, `/`, `/users`, `/chats`, `/logs`, `/crowns`, `/members`) are registered on `nicegui.ui` via `PYTHONPATH=src uv run python -c "import admin; from nicegui import core; print(sorted(core.app.routes, key=lambda r: getattr(r, 'path', '')))"`.

## 4. Final Verification

- [ ] 4.1 Run the complete test suite (`uv run python -m unittest discover -s tests -v`), run lint and format checks (`uv run ruff check src/admin.py tests/test_admin.py && uv run ruff format --check src/admin.py tests/test_admin.py`), and verify via `git status` that only `src/admin.py` and `tests/test_admin.py` were changed outside `openspec/`.
