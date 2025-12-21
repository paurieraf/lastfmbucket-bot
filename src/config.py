import os

from dotenv import load_dotenv

load_dotenv()

## DB
DB_SQLITE_NAME = os.getenv("DB_SQLITE_NAME")

## Last.fm
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_SECRET = os.getenv("LASTFM_API_SECRET")

## Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

## Sentry
SENTRY_DSN = os.getenv("SENTRY_DSN")
