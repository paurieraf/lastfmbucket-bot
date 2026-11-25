import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config  # noqa: E402


class TestConfig(unittest.TestCase):
    def _reload_config(self, env: dict[str, str]):
        with patch.dict(os.environ, env, clear=True), patch("dotenv.load_dotenv"):
            return importlib.reload(config)

    def tearDown(self):
        with patch("dotenv.load_dotenv"):
            importlib.reload(config)

    def test_defaults_when_env_unset(self):
        cfg = self._reload_config({})
        self.assertIsInstance(cfg.PROJECT_ROOT, Path)
        self.assertIsInstance(cfg.CHANGELOG_PATH, Path)
        self.assertEqual(
            cfg.DB_SQLITE_NAME, str(cfg.PROJECT_ROOT / "data/lastfmbucket-bot.db")
        )
        self.assertIsNone(cfg.TELEGRAM_BOT_TOKEN)
        self.assertIsNone(cfg.LASTFM_API_KEY)
        self.assertIsNone(cfg.LASTFM_API_SECRET)
        self.assertIsNone(cfg.SENTRY_DSN)
        self.assertEqual(cfg.LASTFM_MAX_CONCURRENT, 8)
        self.assertIsInstance(cfg.LASTFM_MAX_CONCURRENT, int)

        self.assertEqual(cfg.OLLAMA_HOST, "http://ollama:11434")
        self.assertEqual(cfg.OLLAMA_MODEL, "qwen2.5:0.5b")
        self.assertEqual(cfg.OLLAMA_TIMEOUT, 30.0)
        self.assertIsInstance(cfg.OLLAMA_TIMEOUT, float)
        self.assertEqual(cfg.OLLAMA_MAX_CONCURRENT, 2)
        self.assertIsInstance(cfg.OLLAMA_MAX_CONCURRENT, int)

        self.assertEqual(cfg.ADMIN_USERNAME, "admin")
        self.assertEqual(cfg.ADMIN_PASSWORD, "changeme")
        self.assertEqual(cfg.ADMIN_PORT, 5000)
        self.assertIsInstance(cfg.ADMIN_PORT, int)
        self.assertIsInstance(cfg.ADMIN_SECRET_KEY, str)
        self.assertEqual(len(cfg.ADMIN_SECRET_KEY), 32)

        self.assertEqual(cfg.COLLAGE_CACHE_MAX_MB, 100)
        self.assertIsInstance(cfg.COLLAGE_CACHE_MAX_MB, int)
        self.assertEqual(cfg.COLLAGE_CACHE_TTL_DAYS, 7)
        self.assertIsInstance(cfg.COLLAGE_CACHE_TTL_DAYS, int)

    def test_env_overrides(self):
        cfg = self._reload_config(
            {
                "LASTFM_MAX_CONCURRENT": "12",
                "OLLAMA_HOST": "http://localhost:11434",
                "OLLAMA_MODEL": "llama3.2:1b",
                "OLLAMA_TIMEOUT": "45.5",
                "OLLAMA_MAX_CONCURRENT": "4",
                "ADMIN_USERNAME": "superadmin",
                "ADMIN_PASSWORD": "strong-password",
                "ADMIN_PORT": "8080",
                "ADMIN_SECRET_KEY": "custom-secret",
                "COLLAGE_CACHE_MAX_MB": "250",
                "COLLAGE_CACHE_TTL_DAYS": "14",
            }
        )
        self.assertEqual(cfg.LASTFM_MAX_CONCURRENT, 12)
        self.assertEqual(cfg.OLLAMA_HOST, "http://localhost:11434")
        self.assertEqual(cfg.OLLAMA_MODEL, "llama3.2:1b")
        self.assertEqual(cfg.OLLAMA_TIMEOUT, 45.5)
        self.assertEqual(cfg.OLLAMA_MAX_CONCURRENT, 4)
        self.assertEqual(cfg.ADMIN_USERNAME, "superadmin")
        self.assertEqual(cfg.ADMIN_PASSWORD, "strong-password")
        self.assertEqual(cfg.ADMIN_PORT, 8080)
        self.assertEqual(cfg.ADMIN_SECRET_KEY, "custom-secret")
        self.assertEqual(cfg.COLLAGE_CACHE_MAX_MB, 250)
        self.assertEqual(cfg.COLLAGE_CACHE_TTL_DAYS, 14)

    def test_db_sqlite_name_resolution(self):
        # Empty string falls back to default under PROJECT_ROOT
        cfg = self._reload_config({"DB_SQLITE_NAME": ""})
        self.assertEqual(
            cfg.DB_SQLITE_NAME, str(cfg.PROJECT_ROOT / "data/lastfmbucket-bot.db")
        )

        # Whitespace-only falls back to default under PROJECT_ROOT
        cfg = self._reload_config({"DB_SQLITE_NAME": "   "})
        self.assertEqual(
            cfg.DB_SQLITE_NAME, str(cfg.PROJECT_ROOT / "data/lastfmbucket-bot.db")
        )

        # Relative path resolves against PROJECT_ROOT
        cfg = self._reload_config({"DB_SQLITE_NAME": "data/test-rel.db"})
        self.assertEqual(cfg.DB_SQLITE_NAME, str(cfg.PROJECT_ROOT / "data/test-rel.db"))

        # Absolute path is preserved unchanged
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_db = str(Path(tmpdir) / "nested" / "bot.db")
            cfg = self._reload_config({"DB_SQLITE_NAME": abs_db})
            self.assertEqual(cfg.DB_SQLITE_NAME, abs_db)
            self.assertTrue(Path(abs_db).parent.exists())

    def test_validate_bot_config_success(self):
        cfg = self._reload_config(
            {
                "TELEGRAM_BOT_TOKEN": "123:abc",
                "LASTFM_API_KEY": "key123",
                "LASTFM_API_SECRET": "secret456",
            }
        )
        cfg.validate_bot_config()

    def test_validate_bot_config_missing_single(self):
        cfg = self._reload_config(
            {
                "TELEGRAM_BOT_TOKEN": "123:abc",
                "LASTFM_API_KEY": "key123",
            }
        )
        with self.assertRaises(ValueError) as ctx:
            cfg.validate_bot_config()
        msg = str(ctx.exception)
        self.assertIn("LASTFM_API_SECRET", msg)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", msg)
        self.assertNotIn("LASTFM_API_KEY", msg)

    def test_validate_bot_config_missing_multiple_and_whitespace(self):
        cfg = self._reload_config(
            {
                "TELEGRAM_BOT_TOKEN": "   ",
                "LASTFM_API_KEY": "",
            }
        )
        with self.assertRaises(ValueError) as ctx:
            cfg.validate_bot_config()
        msg = str(ctx.exception)
        self.assertIn("TELEGRAM_BOT_TOKEN", msg)
        self.assertIn("LASTFM_API_KEY", msg)
        self.assertIn("LASTFM_API_SECRET", msg)


if __name__ == "__main__":
    unittest.main()
