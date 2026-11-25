"""Tests for event-loop offloading, /compare optimization, N+1 crowns query, Ollama resilience, and collage cache eviction."""

import asyncio
import os
import sys
import tempfile
import threading
import time
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
from playhouse.sqlite_ext import SqliteExtDatabase
from telegram import Chat as TgChat, Update, User as TgUser

# Ensure src is importable
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import ai  # noqa: E402
import commands  # noqa: E402
import config  # noqa: E402
import db  # noqa: E402
import lastfm  # noqa: E402
import services  # noqa: E402
from lastfm import LastfmClient, Period  # noqa: E402
from services import CollageOptions, CollageService, LastfmService, ViewService  # noqa: E402


class TestOffloadedBlockingIO(unittest.IsolatedAsyncioTestCase):
    async def test_np_and_status_offload_album_and_cover_calls_under_semaphore(self):
        loop_thread = threading.get_ident()
        observed_threads: list[int] = []

        album = MagicMock()
        album.title = "In Rainbows"

        def get_cover_sync():
            observed_threads.append(threading.get_ident())
            return "https://img.example/cover.jpg"

        album.get_cover_image.side_effect = get_cover_sync

        track = MagicMock()
        track.artist = SimpleNamespace(name="Radiohead")
        track.title = "Nude"
        track.get_url.return_value = "https://last.fm/music/Radiohead/_/Nude"

        def get_album_sync():
            observed_threads.append(threading.get_ident())
            return album

        track.get_album.side_effect = get_album_sync

        user = MagicMock(lastfm_username="alice_lfm", telegram_username="alice")
        mock_lfm_svc = MagicMock()
        mock_lfm_svc.get_now_playing = AsyncMock(return_value=(user, track))

        played = MagicMock()
        played.timestamp = None
        played.track = track
        played.album = "In Rainbows"
        mock_lfm_svc.get_recent_tracks = AsyncMock(return_value=[played])

        view_service = ViewService(mock_lfm_svc)

        with patch("services._run_lastfm_call", wraps=services._run_lastfm_call) as spy_run:
            # /np without cover -> 1 call (get_album)
            _, _, cover_none = await view_service.build_np_response(1, show_cover=False)
            self.assertIsNone(cover_none)
            self.assertEqual(spy_run.await_count, 1)

            # /np with cover -> 2 more calls (get_album + get_cover_image)
            _, _, cover_url = await view_service.build_np_response(1, show_cover=True)
            self.assertEqual(cover_url, "https://img.example/cover.jpg")
            self.assertEqual(spy_run.await_count, 3)

            # /status with cover -> 2 more calls (get_album + get_cover_image)
            with patch("services.db.get_linked_user", return_value=user):
                _, _, st_cover = await view_service.build_status_response(1, show_cover=True)
            self.assertEqual(st_cover, "https://img.example/cover.jpg")
            self.assertEqual(spy_run.await_count, 5)

        self.assertEqual(len(observed_threads), 5)
        self.assertTrue(all(tid != loop_thread for tid in observed_threads))

    async def test_build_changelog_response_offloads_file_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            changelog_path = Path(tmpdir) / "CHANGELOG.md"
            changelog_path.write_text("# v1.0.0\n- Faster bot", encoding="utf-8")

            with (
                patch("services.config.CHANGELOG_PATH", changelog_path),
                patch("services.asyncio.to_thread", wraps=asyncio.to_thread) as spy_thread,
            ):
                out = await ViewService.build_changelog_response()

            spy_thread.assert_awaited_once_with(
                changelog_path.read_text, encoding="utf-8"
            )
            self.assertIn("Faster bot", out)

            missing_path = Path(tmpdir) / "MISSING.md"
            with patch("services.config.CHANGELOG_PATH", missing_path):
                fallback = await ViewService.build_changelog_response()
            self.assertEqual(fallback, "Changelog not available.")

    async def test_collage_export_offloads_to_thread_and_falls_back_to_png(self):
        loop_thread = threading.get_ident()
        export_threads: list[int] = []

        def fake_export(img, path, format=None, **kwargs):
            export_threads.append(threading.get_ident())
            if format == "WEBP":
                raise KeyError("WEBP")
            img.save(path, format=format)

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("services.CollageGenerator") as mock_gen_cls,
                patch("services.export_image", side_effect=fake_export),
                patch("services.asyncio.to_thread", wraps=asyncio.to_thread) as spy_thread,
            ):
                mock_gen = MagicMock()
                mock_gen.generate_async = AsyncMock(
                    return_value=Image.new("RGB", (64, 64), color=(10, 20, 30))
                )
                mock_gen_cls.return_value = mock_gen

                svc = CollageService(
                    api_key="k",
                    api_secret="s",
                    cache_dir=tmpdir,
                    cleanup_interval_seconds=9999,
                )
                bio = await svc.generate_collage_image(
                    "alice", CollageOptions(cols=2, rows=2), export_format="WEBP"
                )

        self.assertIsInstance(bio, BytesIO)
        self.assertEqual(bio.name, "collage.png")
        self.assertEqual(len(export_threads), 2)
        self.assertTrue(all(tid != loop_thread for tid in export_threads))
        self.assertTrue(
            any(
                call.args and call.args[0] == CollageService._export_collage_to_bytes
                for call in spy_thread.await_args_list
            )
        )

    async def test_log_command_and_track_group_member_use_to_thread(self):
        @commands.log_command("ping")
        async def dummy(update, context):
            return "pong"

        mock_user = MagicMock(spec=TgUser, id=42, username="alice", is_bot=False)
        mock_chat = MagicMock(
            spec=TgChat, id=-1001, type="supergroup", title="Music", username=None
        )
        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.effective_chat = mock_chat
        mock_context = MagicMock(args=["x"])

        with (
            patch("commands.db.log_command") as mock_log,
            patch("commands.asyncio.to_thread", wraps=asyncio.to_thread) as spy_thread,
        ):
            res = await dummy(mock_update, mock_context)

        self.assertEqual(res, "pong")
        mock_log.assert_called_once()
        self.assertIs(spy_thread.await_args_list[0].args[0], mock_log)

        with (
            patch("commands.db.get_linked_user", return_value=MagicMock()) as mock_get,
            patch("commands.db.track_chat_member") as mock_track,
            patch("commands.asyncio.to_thread", wraps=asyncio.to_thread) as spy_thread,
        ):
            await commands.track_group_member(mock_update, mock_context)

        mock_get.assert_called_once_with(42)
        mock_track.assert_called_once()
        called_funcs = [c.args[0] for c in spy_thread.await_args_list]
        self.assertEqual(called_funcs, [mock_get, mock_track])


class TestCompareOptimization(unittest.IsolatedAsyncioTestCase):
    def test_compute_common_artists_case_insensitive_order_and_limit(self):
        a1 = [
            {"name": "Radiohead", "plays": 500},
            {"name": "Portishead", "plays": 300},
            {"name": "Slowdive", "plays": 200},
        ]
        a2 = [
            {"name": "slowdive", "plays": 999},
            {"name": "RADIOHEAD", "plays": 120},
            {"name": "Björk", "plays": 400},
        ]
        common = lastfm.compute_common_artists(a1, a2, limit=10)
        self.assertEqual(
            common,
            [
                {"name": "Radiohead", "plays1": 500, "plays2": 120},
                {"name": "Slowdive", "plays1": 200, "plays2": 999},
            ],
        )
        self.assertEqual(len(lastfm.compute_common_artists(a1, a2, limit=1)), 1)

    async def test_compare_makes_four_concurrent_calls_and_formats_output(self):
        mock_network = MagicMock()

        def make_top_item(name: str, weight: int):
            item = MagicMock()
            item.item = MagicMock()
            item.item.name = name
            item.weight = str(weight)
            return item

        u1_mock = MagicMock()
        u1_mock.get_playcount.return_value = 1234
        u1_mock.get_top_artists.return_value = [
            make_top_item("Radiohead", 500),
            make_top_item("Portishead", 300),
            make_top_item("Burial", 200),
            make_top_item("Slowdive", 100),
        ]

        u2_mock = MagicMock()
        u2_mock.get_playcount.return_value = 5678
        u2_mock.get_top_artists.return_value = [
            make_top_item("Björk", 800),
            make_top_item("slowdive", 400),
            make_top_item("radiohead", 250),
            make_top_item("Aphex Twin", 150),
        ]

        def get_user_side_effect(uname: str):
            return u1_mock if uname == "alice_lfm" else u2_mock

        mock_network.get_user.side_effect = get_user_side_effect

        client = LastfmClient.__new__(LastfmClient)
        client.client = mock_network
        lfm_service = LastfmService(client)
        view_service = ViewService(lfm_service)

        linked_user = SimpleNamespace(lastfm_username="alice_lfm")
        with patch("services.db.get_linked_user", return_value=linked_user):
            out = await view_service.build_compare_response(1, "bob_lfm")

        # Exactly 2 playcount calls + 2 top_artists(limit=50) calls; 0 top_albums/top_tracks
        u1_mock.get_playcount.assert_called_once_with()
        u2_mock.get_playcount.assert_called_once_with()
        u1_mock.get_top_artists.assert_called_once_with(period=Period.OVERALL, limit=50)
        u2_mock.get_top_artists.assert_called_once_with(period=Period.OVERALL, limit=50)
        u1_mock.get_top_albums.assert_not_called()
        u1_mock.get_top_tracks.assert_not_called()
        u2_mock.get_top_albums.assert_not_called()
        u2_mock.get_top_tracks.assert_not_called()

        self.assertIn("alice_lfm", out)
        self.assertIn("bob_lfm", out)
        self.assertIn("1,234", out)
        self.assertIn("5,678", out)
        self.assertIn("Common Artists (2)", out)
        self.assertIn("Radiohead (500 / 250)", out)
        self.assertIn("Slowdive (100 / 400)", out)
        self.assertIn("Radiohead (500), Portishead (300), Burial (200)", out)
        self.assertIn("Björk (800), slowdive (400), radiohead (250)", out)

    async def test_compare_runs_all_four_calls_concurrently(self):
        in_flight = 0
        max_in_flight = 0

        async def slow_playcount(username: str) -> int:
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.03)
            in_flight -= 1
            return 100

        async def slow_top_artists(
            username: str, period: Period = Period.OVERALL, limit: int = 50
        ) -> list[dict]:
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.03)
            in_flight -= 1
            return [{"name": "Shared Band", "plays": 10}]

        mock_lfm_svc = MagicMock()
        mock_lfm_svc.get_user_playcount = AsyncMock(side_effect=slow_playcount)
        mock_lfm_svc.get_user_top_artists = AsyncMock(side_effect=slow_top_artists)
        view_service = ViewService(mock_lfm_svc)

        with patch(
            "services.db.get_linked_user",
            return_value=SimpleNamespace(lastfm_username="u1"),
        ):
            await view_service.build_compare_response(1, "u2")

        self.assertEqual(max_in_flight, 4)


class TestCrownsLeaderboardQueryOptimization(unittest.TestCase):
    def setUp(self):
        self.orig_db = db.db
        self.test_db = SqliteExtDatabase(":memory:", pragmas={"foreign_keys": 1})
        db.db = self.test_db
        db.db.bind(db.MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(db.MODELS)

    def tearDown(self):
        self.test_db.drop_tables(db.MODELS)
        self.test_db.close()
        db.db = self.orig_db
        self.orig_db.bind(db.MODELS, bind_refs=False, bind_backrefs=False)

    def _count_queries(self, fn, *args, **kwargs):
        orig_execute = self.test_db.execute_sql
        query_count = 0

        def counting_execute(*exec_args, **exec_kwargs):
            nonlocal query_count
            query_count += 1
            return orig_execute(*exec_args, **exec_kwargs)

        with patch.object(self.test_db, "execute_sql", side_effect=counting_execute):
            result = fn(*args, **kwargs)
        return result, query_count

    def test_empty_chat_returns_empty_without_extra_queries(self):
        result, qcount = self._count_queries(db.get_chat_crowns_leaderboard, -9999)
        self.assertEqual(result, [])
        self.assertEqual(qcount, 1)

        db.get_or_create_chat(-8888, "Empty Chat", "group")
        result2, qcount2 = self._count_queries(db.get_chat_crowns_leaderboard, -8888)
        self.assertEqual(result2, [])
        self.assertEqual(qcount2, 2)

    def test_ten_user_leaderboard_executes_at_most_three_queries(self):
        chat_id = -10042
        # Create 12 users with varying crown counts (up to 5 crowns each)
        for i in range(1, 13):
            u = db.create_or_update_user(1000 + i, f"user_{i}", f"lfm_{i}")
            crown_total = (i % 5) + 1
            for j in range(1, crown_total + 1):
                db.upsert_crown(
                    chat_id,
                    f"Artist_{i}_{j}",
                    f"https://last.fm/music/Artist_{i}_{j}",
                    u,
                    j * 100 + i,
                )

        leaderboard, qcount = self._count_queries(
            db.get_chat_crowns_leaderboard, chat_id, limit=10
        )

        self.assertLessEqual(qcount, 3)
        self.assertEqual(len(leaderboard), 10)

        # Verify descending crown_count order and exact top-3 samples per user
        counts = [entry["crown_count"] for entry in leaderboard]
        self.assertEqual(counts, sorted(counts, reverse=True))
        for entry in leaderboard:
            self.assertIsNotNone(entry["user"].telegram_username)
            self.assertLessEqual(len(entry["samples"]), 3)
            self.assertEqual(len(entry["samples"]), min(entry["crown_count"], 3))
            sample_plays = [s["plays"] for s in entry["samples"]]
            self.assertEqual(sample_plays, sorted(sample_plays, reverse=True))


class TestOllamaResilienceAndBounds(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.orig_ready = ai._MODEL_READY
        self.orig_last_check = ai._LAST_MODEL_CHECK
        self.orig_sem = ai.OLLAMA_SEMAPHORE

    async def asyncTearDown(self):
        ai._MODEL_READY = self.orig_ready
        ai._LAST_MODEL_CHECK = self.orig_last_check
        ai.OLLAMA_SEMAPHORE = self.orig_sem

    async def test_timeout_returns_fallback_and_resets_model_ready(self):
        ai._MODEL_READY = True
        ai._LAST_MODEL_CHECK = time.time()
        ai.OLLAMA_SEMAPHORE = asyncio.Semaphore(1)

        async def slow_generate(**kwargs):
            await asyncio.sleep(0.2)
            return SimpleNamespace(response="too late")

        with (
            patch.object(ai.config, "OLLAMA_TIMEOUT", 0.02),
            patch.object(ai.client, "generate", side_effect=slow_generate),
        ):
            vibe = await ai.generate_vibe(["Artist - Track"])
            self.assertIn("Couldn't analyze your vibe", vibe)
            self.assertFalse(ai._MODEL_READY)

            ai._MODEL_READY = True
            roast = await ai.generate_roast(["Artist"], ["Track"])
            self.assertIn("roasting circuits are fried", roast)
            self.assertFalse(ai._MODEL_READY)

            ai._MODEL_READY = True
            recs = await ai.generate_recommendations(["Artist"])
            self.assertIn("Couldn't generate recommendations", recs)
            self.assertFalse(ai._MODEL_READY)

    async def test_concurrency_semaphore_caps_in_flight_at_one(self):
        ai._MODEL_READY = True
        ai._LAST_MODEL_CHECK = time.time()
        ai.OLLAMA_SEMAPHORE = asyncio.Semaphore(1)

        in_flight = 0
        max_in_flight = 0

        async def tracked_generate(**kwargs):
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.03)
            in_flight -= 1
            return SimpleNamespace(response="ok")

        with patch.object(ai.client, "generate", side_effect=tracked_generate):
            results = await asyncio.gather(
                ai.generate_vibe(["A - B"]),
                ai.generate_roast(["A"], ["B"]),
                ai.generate_recommendations(["A"]),
            )

        self.assertEqual(results, ["ok", "ok", "ok"])
        self.assertEqual(max_in_flight, 1)

    async def test_recovery_after_ollama_restart(self):
        ai._MODEL_READY = True
        ai._LAST_MODEL_CHECK = time.time() - 120.0
        ai.OLLAMA_SEMAPHORE = asyncio.Semaphore(1)

        with patch.object(
            ai.client, "generate", side_effect=ConnectionError("Ollama restarted")
        ):
            failed = await ai.generate_vibe(["A - B"])
        self.assertIn("Couldn't analyze your vibe", failed)
        self.assertFalse(ai._MODEL_READY)

        # Simulate cooldown elapsed; next call triggers ensure_model_exists and recovers
        ai._LAST_MODEL_CHECK = time.time() - 120.0
        list_resp = SimpleNamespace(models=[SimpleNamespace(model=config.OLLAMA_MODEL)])
        with (
            patch.object(
                ai.client, "list", AsyncMock(return_value=list_resp)
            ) as mock_list,
            patch.object(
                ai.client,
                "generate",
                AsyncMock(return_value=SimpleNamespace(response="Recovered vibe!")),
            ),
        ):
            recovered = await ai.generate_vibe(["A - B"])

        mock_list.assert_awaited_once()
        self.assertTrue(ai._MODEL_READY)
        self.assertEqual(recovered, "Recovered vibe!")


class TestCollageDiskCacheEviction(unittest.IsolatedAsyncioTestCase):
    def test_cleanup_cache_sync_ttl_and_max_size_eviction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            now = time.time()
            expired = Path(tmpdir) / "expired.jpg"
            old_kept = Path(tmpdir) / "old_kept.jpg"
            mid_kept = Path(tmpdir) / "mid_kept.jpg"
            newest = Path(tmpdir) / "newest.jpg"

            expired.write_bytes(b"a" * 50)
            old_kept.write_bytes(b"b" * 600)
            mid_kept.write_bytes(b"c" * 600)
            newest.write_bytes(b"d" * 600)

            os.utime(expired, (now - 1000, now - 1000))
            os.utime(old_kept, (now - 300, now - 300))
            os.utime(mid_kept, (now - 200, now - 200))
            os.utime(newest, (now - 100, now - 100))

            # TTL = 500s evicts expired.jpg; cap = 1200 bytes evicts old_kept.jpg
            deleted = CollageService._cleanup_cache_sync(
                tmpdir, max_age_seconds=500.0, max_bytes=1200
            )

            self.assertEqual(deleted, 2)
            self.assertFalse(expired.exists())
            self.assertFalse(old_kept.exists())
            self.assertTrue(mid_kept.exists())
            self.assertTrue(newest.exists())

    async def test_maybe_cleanup_cache_throttling_and_error_resilience(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("services.CollageGenerator"):
                svc = CollageService(
                    api_key="k",
                    api_secret="s",
                    cache_dir=tmpdir,
                    cache_max_age_days=1,
                    cache_max_mb=1,
                    cleanup_interval_seconds=3600.0,
                )

            with patch.object(
                CollageService, "_cleanup_cache_sync", return_value=3
            ) as mock_sync:
                first = await svc.maybe_cleanup_cache()
                second = await svc.maybe_cleanup_cache()

            self.assertEqual(first, 3)
            self.assertEqual(second, 0)
            mock_sync.assert_called_once()

            # Reset throttle and simulate OSError in cleanup: must not raise
            svc._last_cleanup = None
            with patch.object(
                CollageService, "_cleanup_cache_sync", side_effect=OSError("disk busy")
            ):
                res = await svc.maybe_cleanup_cache()
            self.assertEqual(res, 0)

    def test_cleanup_cache_sync_ignores_oserror_on_remove(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            now = time.time()
            f = Path(tmpdir) / "locked.jpg"
            f.write_bytes(b"x" * 100)
            os.utime(f, (now - 1000, now - 1000))

            with patch("services.os.remove", side_effect=OSError("permission denied")):
                deleted = CollageService._cleanup_cache_sync(
                    tmpdir, max_age_seconds=10.0, max_bytes=10
                )
            self.assertEqual(deleted, 0)


if __name__ == "__main__":
    unittest.main()
