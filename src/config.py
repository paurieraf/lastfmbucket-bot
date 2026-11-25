import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

## Paths
PROJECT_ROOT = Path(__file__).parent.parent
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"

## DB
_db_path = (os.getenv("DB_SQLITE_NAME") or "").strip() or "data/lastfmbucket-bot.db"
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
LASTFM_MAX_CONCURRENT = int(os.getenv("LASTFM_MAX_CONCURRENT") or "8")

## Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

## Sentry
SENTRY_DSN = os.getenv("SENTRY_DSN")

## Ollama
OLLAMA_HOST = os.getenv("OLLAMA_HOST") or "http://ollama:11434"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL") or "qwen2.5:0.5b"
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT") or "30.0")
OLLAMA_MAX_CONCURRENT = int(os.getenv("OLLAMA_MAX_CONCURRENT") or "2")

## Admin Dashboard
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME") or "admin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or "changeme"
ADMIN_PORT = int(os.getenv("ADMIN_PORT") or "5000")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY") or secrets.token_hex(16)

## Collage Cache
COLLAGE_CACHE_MAX_MB = int(os.getenv("COLLAGE_CACHE_MAX_MB") or "100")
COLLAGE_CACHE_TTL_DAYS = int(os.getenv("COLLAGE_CACHE_TTL_DAYS") or "7")


def validate_bot_config() -> None:
    """Validate that required bot credentials are set and non-blank."""
    required = {
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "LASTFM_API_KEY": LASTFM_API_KEY,
        "LASTFM_API_SECRET": LASTFM_API_SECRET,
    }
    missing = [
        name for name, value in required.items() if not (value and value.strip())
    ]
    if missing:
        raise ValueError(
            "Missing required configuration environment variable(s): "
            + ", ".join(missing)
        )
