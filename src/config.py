import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

## Paths
PROJECT_ROOT = Path(__file__).parent.parent
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"

## DB
_db_path = os.getenv("DB_SQLITE_NAME", "data/lastfmbucket-bot.db")
# Make relative paths relative to project root, not current directory
if not os.path.isabs(_db_path):
    DB_SQLITE_NAME = str(PROJECT_ROOT / _db_path)
else:
    DB_SQLITE_NAME = _db_path

# Ensure the database directory exists
Path(DB_SQLITE_NAME).parent.mkdir(parents=True, exist_ok=True)

## Last.fm
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_SECRET = os.getenv("LASTFM_API_SECRET")

## Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

## Sentry
SENTRY_DSN = os.getenv("SENTRY_DSN")
