# Proposal

## Why

The NiceGUI admin dashboard (`src/admin.py`) currently suffers from security weaknesses (plain `==` credential comparison, no brute-force protection, silent default `"changeme"` password, one-click cascading user deletion without confirmation, implicit `.env` loading), runtime bugs (`row_key="time"` breaks Quasar table rendering when two commands share a 1-second timestamp), N+1 database queries on every command log render, 4x copy-pasted navigation headers, and incomplete coverage of the `Crown` and `ChatMember` database models. Hardening and completing the admin dashboard now prevents accidental data loss, closes authentication gaps, fixes broken table rendering, and establishes unit test coverage for admin logic.

## What Changes

- **Fix Quasar table row keys**: Replace `row_key="time"` with unique `row_key="id"` on the Dashboard recent-commands table and the Command Logs table, including `id` in every row dictionary.
- **Eliminate N+1 queries**: Eagerly join related models (`CommandLog` with `Chat` via `JOIN.LEFT_OUTER`, and `Crown`/`ChatMember` with `Chat` and `User` via `JOIN.LEFT_OUTER`) inside reusable query helper functions.
- **Security hardening in `src/admin.py`**:
  - Call `load_dotenv()` explicitly at module startup instead of relying implicitly on `db` importing `config`.
  - Verify credentials in constant time using `secrets.compare_digest` via a dedicated `verify_credentials()` helper.
  - Detect weak/default `ADMIN_PASSWORD` (`""` or `"changeme"`) and log a prominent `WARNING` without ever logging raw credential values.
  - Add an in-memory per-IP / session brute-force rate limiter on `/login` that temporarily locks out repeated failed login attempts for a cooldown window.
  - Add a confirmation dialog before deleting a user in `/users` (highlighting that deletion cascades to memberships and crowns).
- **Navigation refactor**: Extract the 4x duplicated header/navigation bar into a single shared helper function used across all authenticated pages.
- **Complete admin model coverage**:
  - Add `/crowns` page displaying `Crown` records (chat, artist, holder, playcount, updated_at) with filtering and confirmation-gated deletion.
  - Add `/members` page displaying `ChatMember` records (chat, user, last_active, opt_out) with filtering.
  - Add **Linked Users** and **Total Crowns** summary cards to the Dashboard.
- **Unit tests**: Add `tests/test_admin.py` using Python `unittest` and an in-memory SQLite database to test credential verification, weak-password detection, rate limiting, timestamp formatting, and query helpers (verifying single-query joins and unique `id` row keys).

## Capabilities

### New Capabilities
- `admin-dashboard`: Web-based NiceGUI administrative interface for monitoring bot statistics, authenticating operators safely, and viewing/managing `User`, `Chat`, `CommandLog`, `ChatMember`, and `Crown` records.

### Modified Capabilities
<!-- No existing capabilities have requirement changes. -->

## Impact

- **Owned files**: Only `src/admin.py` (modified) and `tests/test_admin.py` (new).
- **Out of scope / untouched**: `docker-compose.yml`, `.env.template`, `src/config.py`, and `src/db.py` are explicitly untouched (owned by sibling parallel changes).
- **Dependencies**: Uses existing dependencies only (`nicegui`, `peewee`, `python-dotenv`, and Python stdlib `secrets`, `logging`, `time`, `unittest`). No new packages required.
