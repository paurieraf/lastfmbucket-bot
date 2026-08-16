---
name: lastfmbucket-skill
description: Operational guide and repository skill for lastfmbucket-bot. Provides exact CLI commands, workflows, testing procedures, coding conventions, and architectural rules for developing and maintaining the Telegram bot, NiceGUI admin panel, and Ollama LLM integration.
license: MIT
metadata:
  author: lastfmbucket
  version: "1.0.0"
---

# `lastfmbucket-bot` Operational & Engineering Skill

This skill guides AI agents and engineers in developing, testing, debugging, and operating the `lastfmbucket-bot` repository.

---

## 1. Environment & Prerequisites

- **Python Runtime:** `>= 3.14`
- **Package Manager:** Astral `uv` (`>= 0.9.0`)
- **Containerization:** Docker & Docker Compose v2
- **Required External Services:**
  - Telegram Bot API token (from `@BotFather`)
  - Last.fm 2.0 API key & shared secret (from Last.fm API account)
  - Ollama daemon running `qwen2.5:0.5b` (port `11434`)

---

## 2. Standard CLI Commands

All development tasks should be executed using `uv run`.

### 2.1 Dependency Management
```bash
# Install / sync all dependencies
uv sync

# Add a runtime dependency
uv add <package_name>

# Add a development / test dependency
uv add --dev <package_name>
```

### 2.2 Code Quality, Linting & Formatting
```bash
# Run Ruff lint check across all files
uv run ruff check .

# Automatically fix fixable Ruff lint issues (e.g. pre-existing unused import `callbacks.period_from_lastfm` in `src/services.py`)
uv run ruff check . --fix

# Verify code formatting compliance
uv run ruff format . --check

# Format all Python code
uv run ruff format .
```

### 2.3 Running the Services Locally
```bash
# 1. Start the Telegram Bot (Polling Mode)
uv run python src/bot.py

# 2. Start the NiceGUI Admin Web UI (Defaults to http://localhost:5000)
uv run python src/admin.py

# 3. Pull & run local Ollama model for AI commands
ollama serve
ollama pull qwen2.5:0.5b
```

### 2.4 Testing & Verification

> **⚠️ Prerequisites & Test Environment Notice:**
> `pyproject.toml` does not currently include `pytest` or test runner dependencies. Incoming developers and agents **MUST** first install test dependencies before executing test suites:
> ```bash
> uv add --dev pytest pytest-cov pytest-asyncio
> ```
>
> **Note on `src/tests.py`:**
> `src/tests.py` is currently empty (0 bytes). When writing unit tests for bot commands, services, and callbacks, use `unittest.mock` to mock `pylast` API calls and bind models to an in-memory SQLite database (or mock database helper functions).

#### 2.4.1 Test Execution Commands
```bash
# 1. Install required test dependencies (not in pyproject.toml by default)
uv add --dev pytest pytest-cov pytest-asyncio

# 2. Run unit tests via pytest
uv run pytest

# 3. Run unit tests with code coverage
uv run pytest --cov=src --cov-report=term-missing

# 4. Fallback built-in unittest runner (discovers tests without pytest installed)
uv run python -m unittest discover -s src -p "*test*.py"
```

#### 2.4.2 Unit Test Template (`unittest.mock` for `pylast` and `peewee`)
```python
import unittest
from unittest.mock import MagicMock, patch
from peewee import SqliteDatabase

from db import User, Chat, CommandLog
from services import LastfmService
from lastfm import LastfmClient

# In-memory database for isolated test execution
test_db = SqliteDatabase(':memory:')
MODELS = [User, Chat, CommandLog]

class TestLastfmService(unittest.TestCase):
    def setUp(self):
        # Bind models to in-memory database
        test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        test_db.connect()
        test_db.create_tables(MODELS)

        # Mock LastfmClient
        self.mock_lastfm_client = MagicMock(spec=LastfmClient)
        self.service = LastfmService(lastfm_client=self.mock_lastfm_client)

    def tearDown(self):
        test_db.drop_tables(MODELS)
        test_db.close()

    def test_now_playing_user_not_found(self):
        user, track = self.service.get_now_playing(telegram_user_id=12345)
        self.assertIsNone(user)
        self.assertIsNone(track)

    @patch("db.get_user")
    def test_now_playing_success_with_mocked_db_and_pylast(self, mock_get_user):
        # Mock database user
        mock_user = MagicMock()
        mock_user.lastfm_username = "test_user"
        mock_get_user.return_value = mock_user

        # Mock pylast Track
        mock_track = MagicMock()
        mock_track.title = "Song Title"
        mock_track.artist.name = "Artist Name"
        self.mock_lastfm_client.get_now_playing.return_value = mock_track

        user, track = self.service.get_now_playing(telegram_user_id=999)
        self.assertEqual(user.lastfm_username, "test_user")
        self.assertEqual(track.title, "Song Title")
        self.mock_lastfm_client.get_now_playing.assert_called_once_with("test_user")

if __name__ == "__main__":
    unittest.main()
```

### 2.5 Docker Compose Operations
```bash
# Build and start all services in detached mode
docker compose up -d --build

# View logs for a specific service
docker compose logs -f bot
docker compose logs -f admin
docker compose logs -f ollama

# Restart a service
docker compose restart bot

# Stop all running containers
docker compose down
```

---

## 3. Architecture & Subsystem Rules

### 3.1 Telegram Bot & Asynchronous Handlers
1. **Never Block the Event Loop:**
   - `python-telegram-bot` runs an asynchronous `asyncio` event loop.
   - Pylast network requests, Peewee SQLite database writes, and synchronous Ollama inference calls **must not** run synchronously on the event loop.
   - Use `await asyncio.to_thread(func, *args)` for synchronous operations or adopt async clients (`ollama.AsyncClient`).
2. **Global Error Handling:**
   - Always ensure handlers catch domain exceptions (`pylast.WSError`, `httpx.HTTPError`) and notify the user with friendly messages rather than failing silently.
3. **Escaping Message Entities:**
   - Avoid legacy Telegram `Markdown` parse mode for AI-generated text or dynamic artist names containing underscores or asterisks. Prefer `ParseMode.HTML` with `html.escape()` or `ParseMode.MARKDOWN_V2` with `telegram.helpers.escape_markdown()`.

### 3.2 Callback Query Protocol (`src/callbacks.py`)
1. **Strict 64-Byte Payload Constraint:**
   - All inline button callbacks must use the compact schema: `v|action|owner_id|entity|period`.
   - Never place raw artist names, URLs, or long strings in `callback_data`.
2. **Owner Identity Verification:**
   - Always encode `owner_id` (the Telegram user ID who initiated the command) in the callback payload.
   - When handling button clicks in group chats, verify or fetch data for `owner_id` so other group members clicking the button do not corrupt state.

### 3.3 Database Operations (`src/db.py`)
1. **Atomic Transactions:**
   - Wrap all multi-step SQLite writes in `with db.atomic():`.
2. **String Assignment Rule:**
   - In `create_or_update_user`, ensure `user.telegram_username = telegram_username` is a plain string. Never use trailing commas like `(telegram_username,)` which cast strings into Python tuples.
3. **Schema Migrations:**
   - `db.create_tables(MODELS, safe=True)` only creates missing tables. If modifying models (e.g. adding columns to `Chat` or `User`), implement an explicit `ALTER TABLE` or migration step.

### 3.4 Last.fm Integration (`src/lastfm.py`, `src/services.py`)
1. **Safe Album & Artwork Navigation:**
   - Tracks without album information return `None` for `track.get_album()`.
   - Always defensively check:
     ```python
     album = track.get_album()
     album_title = album.title if album else ""
     cover_url = album.get_cover_image() if album else None
     ```
2. **Active User Existence Validation:**
   - `LastFMNetwork.get_user(username)` is a local object constructor that never makes an API call and never returns `None`.
   - To validate whether a user exists on Last.fm during `/set`, trigger an actual query:
     ```python
     try:
         user_obj.get_registered()
     except pylast.WSError:
         return None, False
     ```

### 3.5 NiceGUI Admin Dashboard (`src/admin.py`)
1. **Session Protection:**
   - Every administrative page handler (except `/login`) must invoke `if not check_auth(): return ui.navigate.to("/login")`.
   - Ensure `ADMIN_SECRET_KEY` is persistently configured in `.env` to prevent session invalidation on restart.
2. **Table Performance:**
   - Always specify pagination limits (e.g. `pagination=20`) on Quasar data tables (`ui.table`) to prevent large SQLite table scans from freezing the browser UI.

---

## 4. Key File Layout & Responsibilities

| File | Purpose |
|---|---|
| `src/bot.py` | Bot entrypoint, Sentry initialization, handler registration, long-polling startup. |
| `src/commands.py` | Command handlers for all 13 slash commands and inline button callbacks. |
| `src/callbacks.py` | Binary-safe compact callback data serializer/deserializer. |
| `src/services.py` | `LastfmService` (business logic) and `ViewService` (HTML & keyboard formatting). |
| `src/lastfm.py` | Low-level `pylast.LastFMNetwork` client wrapper and enums (`Period`, `EntityType`). |
| `src/ai.py` | Ollama client for music vibe analysis, humorous roasts, and artist recommendations. |
| `src/db.py` | Peewee models (`User`, `Chat`, `CommandLog`) and SQLite CRUD helper functions. |
| `src/admin.py` | NiceGUI standalone web administration application (5 routes). |
| `src/config.py` | Environment variable loader and path resolver. |
| `src/responses.py` | `string.Template` string definitions for all bot textual outputs. |
| `src/tests.py` | Unit test harness (currently empty / 0 bytes). |
| `ARCHITECTURE.md` | Authoritative system architecture and technical specification. |
| `CONTEXT.md` | Agent quickstart and cheat sheet reference. |
