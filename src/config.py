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

def _env_str(name: str, default: str) -> str:
    return (os.getenv(name) or "").strip() or default


## Last.fm
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_SECRET = os.getenv("LASTFM_API_SECRET")
LASTFM_MAX_CONCURRENT = int(_env_str("LASTFM_MAX_CONCURRENT", "8"))

## Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

## Sentry
SENTRY_DSN = os.getenv("SENTRY_DSN")

## Ollama
OLLAMA_HOST = _env_str("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = _env_str("OLLAMA_MODEL", "qwen2.5:0.5b")
OLLAMA_TIMEOUT = float(_env_str("OLLAMA_TIMEOUT", "30.0"))
OLLAMA_MAX_CONCURRENT = int(_env_str("OLLAMA_MAX_CONCURRENT", "2"))

## Admin Dashboard
ADMIN_USERNAME = _env_str("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or "changeme"
ADMIN_PORT = int(_env_str("ADMIN_PORT", "5000"))
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY") or secrets.token_hex(16)

## Collage Cache
COLLAGE_CACHE_MAX_MB = int(_env_str("COLLAGE_CACHE_MAX_MB", "100"))
COLLAGE_CACHE_TTL_DAYS = int(_env_str("COLLAGE_CACHE_TTL_DAYS", "7"))


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
