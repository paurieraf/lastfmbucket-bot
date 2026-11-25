"""Unit tests for the hardened NiceGUI admin dashboard (src/admin.py)."""

import datetime
import logging
from pathlib import Path
import secrets
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from peewee import SqliteDatabase

# Ensure src/ is importable when running unittest from repository root.
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import admin  # noqa: E402
import db  # noqa: E402


class FakeClock:
    """Deterministic monotonic clock for rate-limiter tests."""

    def __init__(self, initial: float = 1000.0) -> None:
        self.now = initial

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestAuthAndStartupHardening(unittest.TestCase):
    """Tests for weak-password detection, credential verification, and rate limiting."""

    def test_is_weak_password(self):
        self.assertTrue(admin.is_weak_password(None))
        self.assertTrue(admin.is_weak_password(""))
        self.assertTrue(admin.is_weak_password("   "))
        self.assertTrue(admin.is_weak_password("changeme"))
        self.assertFalse(admin.is_weak_password("S3cur3-Admin-Pass!"))

    def test_warn_if_weak_password_logs_without_leaking_secrets(self):
        test_logger = logging.getLogger("test.admin.weak_password")
        with self.assertLogs(test_logger, level="WARNING") as captured:
            warned = admin.warn_if_weak_password("changeme", log=test_logger)
        self.assertTrue(warned)
        joined = "\n".join(captured.output)
        self.assertIn("ADMIN_PASSWORD", joined)
        self.assertNotIn("changeme", joined)
        self.assertNotIn(admin.ADMIN_SECRET_KEY, joined)

        with self.assertLogs(test_logger, level="WARNING") as captured_empty:
            self.assertTrue(admin.warn_if_weak_password("", log=test_logger))
        self.assertIn("weak or empty", "\n".join(captured_empty.output))

    def test_warn_if_weak_password_silent_for_strong_password(self):
        test_logger = logging.getLogger("test.admin.strong_password")
        with self.assertNoLogs(test_logger, level="WARNING"):
            warned = admin.warn_if_weak_password("V3ryStr0ng!Pass", log=test_logger)
        self.assertFalse(warned)

    def test_verify_credentials(self):
        self.assertTrue(
            admin.verify_credentials(
                "operator",
                "s3cr3t-pass",
                expected_username="operator",
                expected_password="s3cr3t-pass",
            )
        )
        self.assertFalse(
            admin.verify_credentials(
                "wrong",
                "s3cr3t-pass",
                expected_username="operator",
                expected_password="s3cr3t-pass",
            )
        )
        self.assertFalse(
            admin.verify_credentials(
                "operator",
                "wrong",
                expected_username="operator",
                expected_password="s3cr3t-pass",
            )
        )
        self.assertFalse(
            admin.verify_credentials(
                "", "", expected_username="operator", expected_password="s3cr3t-pass"
            )
        )
        self.assertFalse(
            admin.verify_credentials(
                None,
                None,
                expected_username="operator",
                expected_password="s3cr3t-pass",
            )
        )
        self.assertTrue(
            admin.verify_credentials(
                "ünicøde",
                "pässwörd",
                expected_username="ünicøde",
                expected_password="pässwörd",
            )
        )

    def test_verify_credentials_does_not_short_circuit(self):
        with patch("admin.secrets.compare_digest", wraps=secrets.compare_digest) as spy:
            result = admin.verify_credentials(
                "wrong-user",
                "correct-pass",
                expected_username="admin",
                expected_password="correct-pass",
            )
        self.assertFalse(result)
        self.assertEqual(spy.call_count, 2)

    def test_rate_limiter_lockout_cooldown_and_reset(self):
        clock = FakeClock(initial=100.0)
        limiter = admin.LoginRateLimiter(
            max_attempts=3, window_seconds=60, lockout_seconds=120, clock=clock
        )

        # Below threshold: not locked
        self.assertEqual(limiter.record_failure("10.0.0.1"), (False, 0))
        self.assertEqual(limiter.record_failure("10.0.0.1"), (False, 0))
        self.assertEqual(limiter.is_locked("10.0.0.1"), (False, 0))

        # Threshold reached: locked for 120s
        self.assertEqual(limiter.record_failure("10.0.0.1"), (True, 120))
        self.assertEqual(limiter.is_locked("10.0.0.1"), (True, 120))

        # Another key remains unaffected (per-key isolation)
        self.assertEqual(limiter.is_locked("10.0.0.2"), (False, 0))

        # During cooldown, client stays locked
        clock.advance(50.0)
        self.assertEqual(limiter.is_locked("10.0.0.1"), (True, 70))
        self.assertEqual(limiter.record_failure("10.0.0.1"), (True, 70))

        # After cooldown expires, client is unlocked with a fresh slate
        clock.advance(70.0)
        self.assertEqual(limiter.is_locked("10.0.0.1"), (False, 0))
        self.assertEqual(limiter.record_failure("10.0.0.1"), (False, 0))

        # Success clears failure history
        limiter.record_success("10.0.0.1")
        self.assertEqual(limiter.record_failure("10.0.0.1"), (False, 0))
        self.assertEqual(limiter.record_failure("10.0.0.1"), (False, 0))
        self.assertEqual(limiter.record_failure("10.0.0.1"), (True, 120))

    def test_rate_limiter_window_prunes_old_attempts(self):
        clock = FakeClock(initial=100.0)
        limiter = admin.LoginRateLimiter(
            max_attempts=3, window_seconds=60, lockout_seconds=120, clock=clock
        )
        limiter.record_failure("10.0.0.5")
        limiter.record_failure("10.0.0.5")
        clock.advance(61.0)
        # Prior attempts expired; a single new failure must not trigger lockout
        self.assertEqual(limiter.record_failure("10.0.0.5"), (False, 0))

    def test_get_client_rate_limit_key(self):
        forwarded_client = SimpleNamespace(
            ip="127.0.0.1",
            request=SimpleNamespace(
                headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"}
            ),
        )
        self.assertEqual(
            admin.get_client_rate_limit_key(forwarded_client), "203.0.113.10"
        )

        direct_client = SimpleNamespace(
            ip="198.51.100.42", request=SimpleNamespace(headers={})
        )
        self.assertEqual(
            admin.get_client_rate_limit_key(direct_client), "198.51.100.42"
        )

        self.assertEqual(admin.get_client_rate_limit_key(None), "anonymous")


class TestAdminQueriesAndMutations(unittest.TestCase):
    """Tests for query helpers, N+1 prevention, row keys, and delete helpers."""

    def setUp(self) -> None:
        self.test_db = SqliteDatabase(":memory:", pragmas={"foreign_keys": 1})
        self.test_db.bind(db.MODELS)
        self.test_db.connect()
        self.test_db.create_tables(db.MODELS)

    def tearDown(self) -> None:
        self.test_db.close()
        db.db.bind(db.MODELS)

    def _count_queries(self, fn, *args, **kwargs):
        original_execute = self.test_db.execute_sql
        query_count = 0

        def counting_execute(*exec_args, **exec_kwargs):
            nonlocal query_count
            query_count += 1
            return original_execute(*exec_args, **exec_kwargs)

        with patch.object(self.test_db, "execute_sql", side_effect=counting_execute):
            result = fn(*args, **kwargs)
        return result, query_count

    def test_format_timestamp(self):
        self.assertEqual(admin.format_timestamp(None), "-")
        self.assertEqual(admin.format_timestamp(0), "-")
        self.assertEqual(admin.format_timestamp(-5), "-")
        ts = 1700000000
        expected = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        self.assertEqual(admin.format_timestamp(ts), expected)

    def test_get_dashboard_stats(self):
        now_ts = int(datetime.datetime.now().timestamp())
        yesterday_ts = now_ts - 86400 * 2

        u1 = db.User.create(
            telegram_id=1, telegram_username="alice", lastfm_username="alice_lfm"
        )
        db.User.create(telegram_id=2, telegram_username="bob", lastfm_username="")
        c1 = db.Chat.create(
            telegram_id=-1001, telegram_chat_name="Music Club", chat_type="supergroup"
        )
        db.Crown.create(
            chat=c1, artist_name="Radiohead", user=u1, playcount=150, updated_at=now_ts
        )
        db.CommandLog.create(
            user_id=1,
            username="alice",
            command="/np",
            args="",
            chat=c1,
            timestamp=now_ts,
        )
        db.CommandLog.create(
            user_id=2,
            username="bob",
            command="/wk",
            args="Radiohead",
            chat=c1,
            timestamp=yesterday_ts,
        )

        stats = admin.get_dashboard_stats()
        self.assertEqual(
            stats,
            {
                "total_users": 2,
                "linked_users": 1,
                "total_chats": 1,
                "total_crowns": 1,
                "total_commands": 2,
                "commands_today": 1,
            },
        )

    def test_fetch_command_log_rows_single_query_and_unique_ids(self):
        c1 = db.Chat.create(
            telegram_id=-1001, telegram_chat_name="Indie Heads", chat_type="group"
        )
        same_ts = 1700001234
        log1 = db.CommandLog.create(
            user_id=1,
            username="alice",
            command="/np",
            args="",
            chat=c1,
            timestamp=same_ts,
        )
        log2 = db.CommandLog.create(
            user_id=2,
            username="bob",
            command="/np",
            args="all",
            chat=c1,
            timestamp=same_ts,
        )
        log3 = db.CommandLog.create(
            user_id=3,
            username="",
            command="/chart",
            args="3x3",
            chat=None,
            timestamp=same_ts + 10,
        )

        rows, query_count = self._count_queries(admin.fetch_command_log_rows, limit=10)
        self.assertEqual(query_count, 1)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["id"] for r in rows], [log3.id, log2.id, log1.id])
        self.assertEqual(len({r["id"] for r in rows}), 3)

        # Verify chat=None and empty username fallbacks
        self.assertEqual(rows[0]["chat_name"], "-")
        self.assertEqual(rows[0]["chat_type"], "-")
        self.assertEqual(rows[0]["username"], "-")
        self.assertEqual(rows[1]["chat_name"], "Indie Heads")
        self.assertEqual(rows[1]["chat_type"], "group")

        # Verify filters
        filtered_cmd = admin.fetch_command_log_rows(command_filter="chart")
        self.assertEqual([r["id"] for r in filtered_cmd], [log3.id])
        filtered_user = admin.fetch_command_log_rows(user_filter="ali")
        self.assertEqual([r["id"] for r in filtered_user], [log1.id])

    def test_fetch_crown_rows_single_query_filters_and_fallbacks(self):
        chat_named = db.Chat.create(
            telegram_id=-1001, telegram_chat_name="Vinyl Room", chat_type="group"
        )
        chat_unnamed = db.Chat.create(
            telegram_id=-1002, telegram_chat_name="", chat_type="group"
        )
        u_tg = db.User.create(
            telegram_id=11, telegram_username="tg_user", lastfm_username="lfm_user"
        )
        u_lfm = db.User.create(
            telegram_id=12, telegram_username="", lastfm_username="only_lfm"
        )
        u_id = db.User.create(telegram_id=13, telegram_username="", lastfm_username="")

        cr1 = db.Crown.create(
            chat=chat_named,
            artist_name="Portishead",
            user=u_tg,
            playcount=420,
            updated_at=100,
        )
        cr2 = db.Crown.create(
            chat=chat_named,
            artist_name="Massive Attack",
            user=u_lfm,
            playcount=310,
            updated_at=200,
        )
        cr3 = db.Crown.create(
            chat=chat_unnamed,
            artist_name="Boards of Canada",
            user=u_id,
            playcount=99,
            updated_at=300,
        )

        rows, query_count = self._count_queries(admin.fetch_crown_rows)
        self.assertEqual(query_count, 1)
        self.assertEqual([r["id"] for r in rows], [cr3.id, cr2.id, cr1.id])
        self.assertEqual(rows[0]["chat_name"], "-")
        self.assertEqual(rows[0]["holder"], "13")
        self.assertEqual(rows[1]["holder"], "only_lfm")
        self.assertEqual(rows[2]["holder"], "tg_user")
        self.assertEqual(rows[2]["chat_name"], "Vinyl Room")

        self.assertEqual(
            [r["id"] for r in admin.fetch_crown_rows(artist_filter="Portis")], [cr1.id]
        )
        self.assertEqual(
            [r["id"] for r in admin.fetch_crown_rows(chat_filter="Vinyl")],
            [cr2.id, cr1.id],
        )

    def test_fetch_chat_member_rows_single_query_and_filters(self):
        c1 = db.Chat.create(
            telegram_id=-2001, telegram_chat_name="Shoegaze", chat_type="supergroup"
        )
        c2 = db.Chat.create(telegram_id=-2002, telegram_chat_name="", chat_type="group")
        u1 = db.User.create(
            telegram_id=21, telegram_username="mbv_fan", lastfm_username="loveless91"
        )
        u2 = db.User.create(telegram_id=22, telegram_username="", lastfm_username="")

        m1 = db.ChatMember.create(chat=c1, user=u1, last_active=500, opt_out=False)
        m2 = db.ChatMember.create(chat=c2, user=u2, last_active=600, opt_out=True)

        rows, query_count = self._count_queries(admin.fetch_chat_member_rows)
        self.assertEqual(query_count, 1)
        self.assertEqual([r["id"] for r in rows], [m2.id, m1.id])
        self.assertEqual(rows[0]["chat_name"], "-")
        self.assertEqual(rows[0]["telegram_username"], "-")
        self.assertEqual(rows[0]["lastfm_username"], "-")
        self.assertEqual(rows[0]["opt_out"], "Yes")
        self.assertEqual(rows[1]["chat_name"], "Shoegaze")
        self.assertEqual(rows[1]["opt_out"], "No")

        self.assertEqual(
            [r["id"] for r in admin.fetch_chat_member_rows(chat_filter="Shoe")], [m1.id]
        )
        self.assertEqual(
            [r["id"] for r in admin.fetch_chat_member_rows(user_filter="loveless")],
            [m1.id],
        )

    def test_delete_crown_and_cascading_user_delete(self):
        chat = db.Chat.create(
            telegram_id=-3001, telegram_chat_name="Cascade Chat", chat_type="group"
        )
        u1 = db.User.create(
            telegram_id=31, telegram_username="u1", lastfm_username="u1_lfm"
        )
        u2 = db.User.create(
            telegram_id=32, telegram_username="u2", lastfm_username="u2_lfm"
        )
        db.ChatMember.create(chat=chat, user=u1, last_active=100)
        db.ChatMember.create(chat=chat, user=u2, last_active=100)
        cr1 = db.Crown.create(
            chat=chat, artist_name="Slowdive", user=u1, playcount=50, updated_at=100
        )
        cr2 = db.Crown.create(
            chat=chat, artist_name="Ride", user=u2, playcount=40, updated_at=100
        )

        # Deleting a crown removes only that crown
        self.assertEqual(admin.delete_crown_by_id(cr2.id), 1)
        self.assertIsNone(db.Crown.get_or_none(db.Crown.id == cr2.id))
        self.assertIsNotNone(db.Crown.get_or_none(db.Crown.id == cr1.id))

        # Deleting u1 cascades to u1's ChatMember and Crown, preserving u2
        self.assertEqual(admin.delete_user_by_id(u1.id), 1)
        self.assertIsNone(db.User.get_or_none(db.User.id == u1.id))
        self.assertEqual(
            db.ChatMember.select().where(db.ChatMember.user == u1.id).count(), 0
        )
        self.assertEqual(db.Crown.select().where(db.Crown.user == u1.id).count(), 0)
        self.assertIsNotNone(db.User.get_or_none(db.User.id == u2.id))
        self.assertEqual(
            db.ChatMember.select().where(db.ChatMember.user == u2.id).count(), 1
        )

    def test_expected_routes_registered(self):
        from nicegui import core

        registered_paths = {getattr(r, "path", None) for r in core.app.routes}
        for expected in (
            "/login",
            "/",
            "/users",
            "/chats",
            "/logs",
            "/crowns",
            "/members",
        ):
            self.assertIn(expected, registered_paths)


if __name__ == "__main__":
    unittest.main()
