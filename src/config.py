import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

## Paths
PROJECT_ROOT = Path(__file__).parent.parent
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"

## DB
DB_SQLITE_NAME = os.getenv("DB_SQLITE_NAME")

## Last.fm
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_SECRET = os.getenv("LASTFM_API_SECRET")

## Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

## Sentry
SENTRY_DSN = os.getenv("SENTRY_DSN")
