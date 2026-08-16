# Agent Quickstart & Repository Context

This document is an authoritative, dense single-file onboarding guide for AI coding agents working on `lastfmbucket-bot`.

---

## 1. Quick Orientation

- **Project Description:** A Telegram bot and companion NiceGUI web dashboard providing Last.fm music scrobble tracking, listening telemetry, interactive charts, taste comparisons, and local LLM-powered vibe analysis, roasts, and music recommendations.
- **Tech Stack:** Python >= 3.14, `uv`, `python-telegram-bot` 22.5, `peewee` 3.18.3 (SQLite in WAL mode), `pylast` 7.0.0, `nicegui` 2.x, `ollama` 0.4.0 (`qwen2.5:0.5b`), `ruff` 0.14.10, `sentry-sdk` 2.48.0.
- **Runtime Processes:**
  1. `python src/bot.py`: Telegram long-polling bot process.
  2. `python src/admin.py`: NiceGUI web admin dashboard (port `8080` in container, `5000` default local).
  3. `ollama/ollama`: Auxiliary Ollama container running `qwen2.5:0.5b`.

### 1.1 Directory Structure
```
lastfmbucket-bot/
├── .github/workflows/deploy.yml  # GitHub Actions CI/CD to Docker Hub & VPS
├── .env.template                 # Template for required & optional environment variables
├── .dockerignore                 # Container build exclusion patterns
├── .gitignore                    # Git tracking ignore patterns
├── .agignore                     # Antigravity & LLM agent context filter patterns
├── ARCHITECTURE.md               # Master system architecture & technical specification
├── CONTEXT.md                    # This fast-onboarding cheat sheet
├── SKILL.md                      # Agent operational skill instructions
├── Caddyfile                     # Reverse proxy configuration for admin domain
├── Dockerfile                    # Multi-stage Python 3.14 + uv container image
├── docker-compose.yml            # Multi-service compose config (bot, admin, ollama)
├── deploy.sh                     # Automated pull & rebuild script
├── pyproject.toml                # Project metadata, dependencies, and Ruff config
├── uv.lock                       # Pinned dependency lockfile
├── CHANGELOG.md                  # Application version history (served via /changelog)
├── data/                         # SQLite database volume storage
│   └── lastfmbucket-bot.db       # Primary SQLite 3 database file
└── src/                          # Source code root
    ├── admin.py                  # NiceGUI web administration application (5 routes)
    ├── ai.py                     # Ollama LLM integration (vibe, roast, recommend)
    ├── bot.py                    # Bot entrypoint, Sentry init, handler registration
    ├── callbacks.py              # 64-byte compact inline keyboard callback protocol
    ├── commands.py               # 13 Telegram bot command & callback handler functions
    ├── config.py                 # Environment variables loader & path resolver
    ├── db.py                     # Peewee ORM database schema (User, Chat, CommandLog)
    ├── lastfm.py                 # Low-level pylast client wrapper & enums
    ├── responses.py              # string.Template definitions for HTML & text output
    ├── services.py               # Business logic (LastfmService) & View builders (ViewService)
    └── tests.py                  # Unit test harness (currently empty / 0 bytes)
```

---

## 2. Command Cheat Sheet (All 14 Bot Commands)

| Command | Arguments | Handler | Description / Expected Behavior | Output Format |
|---|---|---|---|---|
| `/start` | None | `commands.start` | Checks if user exists in DB. If not, prompts to link account. | Plain text |
| `/set` | `<lastfm_user>` | `commands.lastfm_username_set` | Saves caller's Telegram ID $\leftrightarrow$ Last.fm username in SQLite. | HTML |
| `/np` | None | `commands.now_playing` | Displays currently playing track with interactive action buttons. | HTML + Buttons (`More info`, `🖼️ Cover`) |
| `/status` | None | `commands.status` | Displays recent 5 scrobbled tracks with relative time deltas (`humanize`). | HTML + Buttons (`Less info`, `🖼️ Cover`) |
| `/tops` | `[entity] [period]` *(optional)* | `commands.tops` | Shows top artists, albums, or tracks over 7d, 1m, 3m, 6m, 1y, or overall. | HTML List (Top 10) or 2-Tier Keyboard |
| `/collage` | `[size] [period] [entity] [tile_size] [theme:..] [overlay:..] [preset:..] [notext] [corner:..] [border:..] [border_color:..] [spacing:..] [fallback:..]` *(optional)* | `commands.collage` | Generates a composite visual image grid (1x1 to 20x20, max 400 tiles, dynamic resolution scaling) using `lastfmcollagegenerator` v0.8.0, with themes, overlays, social presets, tile geometry and a persistent artwork cache (`data/collage_cache/`). | Photo with caption or 4-Tier Keyboard (entity → size/preset → period → style) |
| `/compare` | `<target_user>` | `commands.compare` | Compares total scrobbles, top 3 artists, and common artists with another user. | HTML summary table |
| `/preferences`| None | `commands.preferences` | Displays account settings and an inline `Unlink your account` button. | HTML + Button |
| `/help` | None | `commands.help_command` | Fetches bot description dynamically from Telegram API. | Plain text |
| `/changelog` | None | `commands.changelog` | Reads and returns contents of `CHANGELOG.md` (up to 4000 chars). | HTML `<pre>` block |
| `/privacy` | None | `commands.privacy` | Displays data privacy and GDPR retention statement. | HTML |
| `/vibe` | None | `commands.vibe` | AI mood summary of current track + last 10 scrobbles via Ollama. | Markdown |
| `/roast` | None | `commands.roast` | AI humorous roast of overall top 10 artists + top 5 tracks via Ollama. | Markdown |
| `/recommend`| None | `commands.recommend` | AI recommendations for 5 lesser-known artists based on top 10 artists. | Markdown |

---

## 3. Database Schema & Peewee Query Cheat Sheet

### 3.1 Models (`src/db.py`)
```python
# User: Maps Telegram ID to Last.fm Username
class User(Model):
    telegram_id = BigIntegerField(unique=True)      # 64-bit Telegram user ID
    telegram_username = CharField(default="")       # Telegram @handle
    lastfm_username = CharField(default="")         # Linked Last.fm account handle

# Chat: Records chat context
class Chat(Model):
    telegram_id = BigIntegerField(unique=True)      # 64-bit Telegram chat ID
    telegram_chat_name = CharField(default="")      # Chat title or username
    chat_type = CharField(default="")               # "private", "group", "supergroup", "channel"

# CommandLog: Audit log of all command executions
class CommandLog(Model):
    user_id = BigIntegerField()                     # User who executed command
    username = CharField(default="")                # Username at execution time
    command = CharField()                           # Command name (e.g., "np", "tops")
    args = CharField(default="")                    # Argument string
    chat = ForeignKeyField(Chat, backref="command_logs", null=True)
    timestamp = BigIntegerField()                   # int(time.time()) epoch seconds
```

### 3.2 Common Peewee Query Patterns
```python
from db import User, Chat, CommandLog, db

# 1. Fetch user by Telegram ID
user = User.get_or_none(User.telegram_id == telegram_id)

# 2. Atomic user upsert
with db.atomic():
    user, created = User.get_or_create(
        telegram_id=telegram_id,
        defaults={"telegram_username": username, "lastfm_username": lastfm_name},
    )
    if not created:
        user.telegram_username = username  # NOTE: ensure string, not tuple!
        user.lastfm_username = lastfm_name
        user.save()

# 3. Aggregate log counts for today
import time
today_start = int(time.time()) - 86400
recent_count = CommandLog.select().where(CommandLog.timestamp >= today_start).count()

# 4. Filtered logs query with pagination
logs = (
    CommandLog.select()
    .where(CommandLog.command.contains(query_cmd) & CommandLog.username.contains(query_user))
    .order_by(CommandLog.timestamp.desc())
    .limit(100)
)
```

---

## 4. Last.fm Integration Reference (`src/lastfm.py`)

### 4.1 Enums
- **`Period`**: `WEEK` (`"7day"`), `ONE_MONTH` (`"1month"`), `THREE_MONTHS` (`"3month"`), `SIX_MONTHS` (`"6month"`), `YEAR` (`"12month"`), `OVERALL` (`"overall"`).
- **`EntityType`**: `ARTIST` (`"artist"`), `ALBUM` (`"album"`), `TRACK` (`"track"`).

### 4.2 Key Methods
```python
client = LastfmClient()

# Get currently playing track (or None)
track: pylast.Track | None = client.get_now_playing(username="alice")

# Get recent scrobbles
tracks: list[pylast.PlayedTrack] = client.get_recent_tracks(username="alice", limit=5)

# Get top items (returns list of pylast.TopItem wrapping Artist/Album/Track)
tops: list[pylast.TopItem] = client.get_tops(
    username="alice",
    entity_type=EntityType.ARTIST,
    period=Period.WEEK,
    limit=10,
)

# Get user listening summary stats
stats: dict | None = client.get_user_stats(username="alice")
# -> {"playcount": 14250, "top_artists": [...], "top_albums": [...], "top_tracks": [...]}

# Get common artists between two users
common: list[dict] = client.get_common_artists(username1="alice", username2="bob", limit=50)
# -> [{"name": "Radiohead", "user1_playcount": 500, "user2_playcount": 320}, ...]
```

---

## 5. Callback Protocol Cheat Sheet (`src/callbacks.py`)

Telegram inline buttons use a strict compact encoding:
$$\text{Format: } \texttt{"1|action|owner\_id|entity|period"}$$

- **Action Codes**: `nl` (`NP_LESS`), `nc` (`NP_LESS_COVER`), `nm` (`NP_MORE`), `pu` (`PREF_UNLINK`), `t` (`TOPS`).
- **Entity Codes**: `a` (`ARTIST`), `b` (`ALBUM`), `t` (`TRACK`).
- **Period Codes**: `w` (`WEEK`), `1` (`1_MONTH`), `3` (`3_MONTH`), `6` (`6_MONTH`), `y` (`1_YEAR`), `o` (`OVERALL`).
- **Owner Verification**: `owner_id` is always embedded to ensure group chat button clicks only alter the view for the original requester.

```python
from callbacks import Callback, Action, Entity, Period

# Encoding
data = Callback(action=Action.TOPS, owner_id=123456789, entity=Entity.ARTIST, period=Period.WEEK).encode()
# -> "1|t|123456789|a|w"

# Decoding
cb = Callback.decode("1|t|123456789|a|w")
assert cb.action == Action.TOPS
assert cb.owner_id == 123456789
assert cb.entity == Entity.ARTIST
```

---

## 6. AI / Ollama Integration Reference (`src/ai.py`)

- **Model:** `qwen2.5:0.5b` (lightweight, runs within 2GB RAM container).
- **Host:** Configured via `OLLAMA_HOST` (default: `http://ollama:11434`).

### Functions & Signatures
1. `generate_vibe(recent_tracks: list[str], current_track: str | None = None) -> str`
   - Temperature: `0.8`, Max tokens: `100`
2. `generate_roast(top_artists: list[str], top_tracks: list[str]) -> str`
   - Temperature: `0.9`, Max tokens: `120`
3. `generate_recommendations(top_artists: list[str]) -> str`
   - Temperature: `0.7`, Max tokens: `150`

---

## 7. Environment Variables Reference

| Variable | Target Module | Required? | Default | Description |
|---|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `src/config.py` | **Yes (Bot)** | None | Telegram Bot token from `@BotFather` |
| `LASTFM_API_KEY` | `src/config.py` | **Yes (Bot)** | None | Last.fm 2.0 Web Services API Consumer Key |
| `LASTFM_API_SECRET` | `src/config.py` | **Yes (Bot)** | None | Last.fm 2.0 Web Services Shared Secret |
| `DB_SQLITE_NAME` | `src/config.py` | No | `data/lastfmbucket-bot.db` | SQLite database file path (anchored to repo root) |
| `SENTRY_DSN` | `src/config.py` | No | None | Sentry telemetry DSN |
| `ADMIN_USERNAME` | `src/admin.py` | No | `admin` | Admin dashboard HTTP login username |
| `ADMIN_PASSWORD` | `src/admin.py` | No | `changeme` | Admin dashboard HTTP login password |
| `ADMIN_PORT` | `src/admin.py` | No | `5000` (`8080` in Docker) | Admin web server binding port |
| `ADMIN_SECRET_KEY` | `src/admin.py` | No | Ephemeral hex | Secret key for NiceGUI session cookies |
| `OLLAMA_HOST` | `src/ai.py` | No | `http://ollama:11434` | Ollama HTTP endpoint |

---

## 8. Development & Debugging Runbook

### 8.1 Setup & Linting
```bash
# 1. Install dependencies via uv
uv sync

# 2. Check code style and linting
uv run ruff check .

# 3. Auto-fix linting issues (e.g., pre-existing unused import `callbacks.period_from_lastfm` in `src/services.py`)
uv run ruff check . --fix

# 4. Check formatting
uv run ruff format . --check

# 5. Apply formatting
uv run ruff format .
```

### 8.2 Testing & Test Harness Setup

> **⚠️ Test Dependencies Notice:**
> `pyproject.toml` does not currently include `pytest` or test runner dependencies. Incoming developers and agents **MUST** first install test dependencies before executing test suites:
> ```bash
> uv add --dev pytest pytest-cov pytest-asyncio
> ```
>
> **Note on `src/tests.py`:**
> `src/tests.py` is currently empty (0 bytes). When writing unit tests for handlers and services, use `unittest.mock` to mock `pylast` API calls and in-memory SQLite (`SqliteDatabase(':memory:')`) or `@patch` for `peewee` database operations.

```bash
# 1. Install test dependencies (required before running pytest)
uv add --dev pytest pytest-cov pytest-asyncio

# 2. Run unit tests via pytest
uv run pytest

# 3. Run unit tests with code coverage
uv run pytest --cov=src --cov-report=term-missing

# 4. Fallback built-in unittest runner (discovers tests without pytest installed)
uv run python -m unittest discover -s src -p "*test*.py"
```

#### Unit Test Template / Example (`src/tests.py`)
```python
import unittest
from unittest.mock import MagicMock, patch
from peewee import SqliteDatabase

from db import User, Chat, CommandLog
from services import LastfmService
from lastfm import LastfmClient

# Use an in-memory SQLite database for isolated tests
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

### 8.3 Running Locally
```bash
# 1. Run Telegram Bot (polling mode)
uv run python src/bot.py

# 2. Run NiceGUI Web Admin (http://localhost:5000)
uv run python src/admin.py

# 3. Run with local Ollama
ollama serve
ollama pull qwen2.5:0.5b
```

### 8.4 Docker & Production Deployment
```bash
# Start all containers in background
docker compose up -d --build

# View container logs
docker compose logs -f bot
docker compose logs -f admin
docker compose logs -f ollama

# Restart a service
docker compose restart bot
```

---

## 9. Known Gotchas & Architectural Traps

1. **Tuple Assignment Bug (`db.py:101`):** Never assign `user.telegram_username = (val,)`. Always use `user.telegram_username = val`.
2. **Missing Album Guard (`services.py:154`):** Always verify `track.get_album() is not None` before accessing `.title` or `.get_cover_image()`.
3. **Pylast User Validation (`services.py:43`):** `LastFMNetwork.get_user()` does not perform an API call. Verify with `user.get_registered()` or `user.get_playcount()`.
4. **Synchronous Blocking in Handlers:** Pylast and Ollama calls are synchronous. When adding async handlers, wrap heavy I/O in `asyncio.to_thread`.
5. **Docker .dockerignore:** Never exclude `CHANGELOG.md` or other runtime-inspected files in `.dockerignore`.
