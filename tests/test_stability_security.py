import html
import sys
import tempfile
import time
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure src is importable
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pylast  # noqa: E402
import telegram  # noqa: E402
from playhouse.sqlite_ext import SqliteExtDatabase  # noqa: E402
from telegram import Update, User as TgUser  # noqa: E402
from telegram.ext import MessageHandler  # noqa: E402

import bot  # noqa: E402
import commands  # noqa: E402
import db  # noqa: E402
from callbacks import Action, Callback, Entity, Period  # noqa: E402
from lastfm import EntityType, LastfmClient, Period as LfmPeriod  # noqa: E402
from services import CollageService, GroupService, ViewService  # noqa: E402


class TestDatabaseDurabilityAndPrivacy(unittest.TestCase):
    def setUp(self):
        self.orig_db = db.db
        self.test_db = SqliteExtDatabase(
            ":memory:",
            pragmas={"foreign_keys": 1},
        )
        db.db = self.test_db
        db.db.bind(db.MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(db.MODELS)

    def tearDown(self):
        self.test_db.drop_tables(db.MODELS)
        self.test_db.close()
        db.db = self.orig_db
        self.orig_db.bind(db.MODELS, bind_refs=False, bind_backrefs=False)

    def test_sqlite_synchronous_pragma_is_normal(self):
        pragmas = dict(self.orig_db._pragmas)
        self.assertEqual(pragmas.get("synchronous"), 1)
        self.assertEqual(
            self.orig_db.execute_sql("PRAGMA synchronous").fetchone()[0], 1
        )

    def test_upsert_crown_preserves_existing_chat_metadata(self):
        user = db.create_or_update_user(101, "alice", "alice_lfm")
        db.get_or_create_chat(-100500, "Indie Club", "supergroup")

        db.upsert_crown(
            -100500,
            "Radiohead",
            "https://www.last.fm/music/Radiohead",
            user,
            420,
        )

        chat = db.Chat.get(db.Chat.telegram_id == -100500)
        self.assertEqual(chat.telegram_chat_name, "Indie Club")
        self.assertEqual(chat.chat_type, "supergroup")

    def test_run_migrations_creates_commandlog_indexes_idempotently(self):
        legacy_db = SqliteExtDatabase(":memory:")
        legacy_db.connect()
        legacy_db.execute_sql(
            "CREATE TABLE commandlog ("
            "id INTEGER NOT NULL PRIMARY KEY,"
            "user_id BIGINT NOT NULL,"
            "username VARCHAR(255) NOT NULL,"
            "command VARCHAR(255) NOT NULL,"
            "args VARCHAR(255) NOT NULL,"
            "chat_id INTEGER NULL,"
            "timestamp BIGINT NOT NULL"
            ")"
        )
        try:
            indexes_before = {
                row[1]
                for row in legacy_db.execute_sql("PRAGMA index_list('commandlog')").fetchall()
            }
            self.assertNotIn("idx_commandlog_timestamp", indexes_before)

            db.run_migrations(legacy_db)
            # Second call must remain idempotent
            db.run_migrations(legacy_db)

            indexes_after = {
                row[1]
                for row in legacy_db.execute_sql("PRAGMA index_list('commandlog')").fetchall()
            }
            self.assertIn("idx_commandlog_timestamp", indexes_after)
            self.assertIn("idx_commandlog_user_id", indexes_after)
            self.assertIn("idx_commandlog_command", indexes_after)
        finally:
            legacy_db.close()

    def test_delete_user_purges_command_logs_and_cascades(self):
        user = db.create_or_update_user(555, "alice", "alice_lfm")
        db.log_command(555, "alice", "np", "", -1001, "group", "Test Group")
        db.upsert_crown(-1001, "Radiohead", "https://url", user, 100)

        self.assertEqual(db.CommandLog.select().where(db.CommandLog.user_id == 555).count(), 1)
        self.assertEqual(db.ChatMember.select().count(), 1)
        self.assertEqual(db.Crown.select().count(), 1)

        db.delete_user(555)

        self.assertIsNone(db.get_user(555))
        self.assertEqual(db.CommandLog.select().where(db.CommandLog.user_id == 555).count(), 0)
        self.assertEqual(db.ChatMember.select().count(), 0)
        self.assertEqual(db.Crown.select().count(), 0)

    def test_delete_user_purges_command_logs_even_without_user_row(self):
        chat = db.get_or_create_chat(-1002, "Group", "group")
        db.CommandLog.create(
            user_id=777,
            username="ghost",
            command="help",
            args="",
            chat=chat,
            timestamp=int(time.time()),
        )
        self.assertIsNone(db.get_user(777))
        self.assertEqual(db.CommandLog.select().where(db.CommandLog.user_id == 777).count(), 1)

        db.delete_user(777)
        self.assertEqual(db.CommandLog.select().where(db.CommandLog.user_id == 777).count(), 0)


class TestLastfmValidation(unittest.TestCase):
    def _make_client(self) -> LastfmClient:
        client = LastfmClient.__new__(LastfmClient)
        client.client = MagicMock()
        return client

    def test_get_user_empty_returns_none(self):
        client = self._make_client()
        self.assertIsNone(client.get_user("   "))
        client.client.get_user.assert_not_called()

    def test_get_user_validates_with_api_and_returns_user(self):
        client = self._make_client()
        mock_user = MagicMock()
        mock_user.get_registered.return_value = "2010-01-01"
        client.client.get_user.return_value = mock_user

        res = client.get_user("  valid_user ")
        self.assertIs(res, mock_user)
        client.client.get_user.assert_called_once_with("valid_user")
        mock_user.get_registered.assert_called_once_with()

    def test_get_user_returns_none_on_wserror(self):
        client = self._make_client()
        mock_user = MagicMock()
        mock_user.get_registered.side_effect = pylast.WSError(
            "user.getInfo", "6", "User not found"
        )
        client.client.get_user.return_value = mock_user

        self.assertIsNone(client.get_user("missing_user"))

    def test_get_artist_canonical_info_uses_properly_capitalized_and_handles_missing(self):
        client = self._make_client()
        mock_artist = MagicMock()
        mock_artist.get_name.return_value = "Radiohead"
        mock_artist.get_url.return_value = "https://www.last.fm/music/Radiohead"
        client.client.get_artist.return_value = mock_artist

        info = client.get_artist_canonical_info(" radiohead ")
        self.assertEqual(info, ("Radiohead", "https://www.last.fm/music/Radiohead"))
        mock_artist.get_name.assert_called_once_with(properly_capitalized=True)

        # Missing artist raises WSError
        mock_artist.get_name.side_effect = pylast.WSError(
            "artist.getInfo", "6", "The artist you supplied could not be found"
        )
        self.assertIsNone(client.get_artist_canonical_info("NoSuchArtistXYZ"))
        self.assertIsNone(client.get_artist_canonical_info("   "))


class TestCallbackProtocolSecurity(unittest.TestCase):
    def test_64_bit_owner_id_fits_under_64_bytes_and_roundtrips(self):
        max_64_bit = 9223372036854775807
        cb = Callback(
            action=Action.COLLAGE,
            owner_id=max_64_bit,
            entity=Entity.ARTIST,
            period=Period.WEEK,
            size="10x10",
            theme="glassmorphic",
            overlay="full_tint",
            preset="wallpaper",
            style="skip",
        )
        encoded = cb.encode()
        self.assertLessEqual(len(encoded.encode("utf-8")), 64)

        decoded = Callback.decode(encoded)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.owner_id, max_64_bit)
        self.assertEqual(decoded.theme, "glassmorphic")
        self.assertEqual(decoded.overlay, "full_tint")
        self.assertEqual(decoded.preset, "wallpaper")
        self.assertEqual(decoded.style, "skip")

    def test_overflow_raises_value_error_not_assertion(self):
        cb = Callback(
            action=Action.COLLAGE,
            owner_id=9223372036854775807,
            entity=Entity.ARTIST,
            period=Period.WEEK,
            size="10x10",
            theme="custom_very_long_theme_name",
            overlay="custom_very_long_overlay_name",
        )
        with self.assertRaises(ValueError):
            cb.encode()

    def test_legacy_full_string_payload_still_decodes(self):
        legacy = "1|cl|987654321|a|w|10x10|glassmorphic|full_tint|instagram-story|skip"
        decoded = Callback.decode(legacy)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.theme, "glassmorphic")
        self.assertEqual(decoded.overlay, "full_tint")
        self.assertEqual(decoded.preset, "instagram-story")
        self.assertEqual(decoded.to_collage_preset_str(), "instagram-story")
        self.assertEqual(decoded.style, "skip")


class TestCallbackHandlerOwnershipAndAnswering(unittest.IsolatedAsyncioTestCase):
    async def test_user_scoped_actions_reject_other_users_with_single_alert(self):
        scoped = [
            Callback(Action.PREF_UNLINK, owner_id=100),
            Callback(Action.PREF_OPT_OUT, owner_id=100),
            Callback(Action.COLLAGE, owner_id=100, entity=Entity.ALBUM),
            Callback(Action.TOPS, owner_id=100, entity=Entity.ARTIST),
            Callback(Action.NP_LESS, owner_id=100),
            Callback(Action.NP_LESS_COVER, owner_id=100),
            Callback(Action.NP_MORE, owner_id=100),
        ]
        for cb in scoped:
            mock_query = MagicMock()
            mock_query.data = cb.encode()
            mock_query.from_user = MagicMock(id=999)
            mock_query.answer = AsyncMock()
            mock_update = MagicMock(spec=Update, callback_query=mock_query)
            mock_context = MagicMock()

            fake_handler = AsyncMock()
            with patch.dict(commands.CALLBACK_ROUTES, {cb.action: fake_handler}):
                await commands.button_handler(mock_update, mock_context)

            mock_query.answer.assert_awaited_once_with(
                "This button belongs to another user.", show_alert=True
            )
            fake_handler.assert_not_awaited()

    async def test_owner_click_answers_once_and_dispatches(self):
        cb = Callback(Action.TOPS, owner_id=100, entity=Entity.ARTIST)
        mock_query = MagicMock()
        mock_query.data = cb.encode()
        mock_query.from_user = MagicMock(id=100)
        mock_query.answer = AsyncMock()
        mock_update = MagicMock(spec=Update, callback_query=mock_query)
        mock_context = MagicMock()

        fake_handler = AsyncMock()
        with patch.dict(commands.CALLBACK_ROUTES, {Action.TOPS: fake_handler}):
            await commands.button_handler(mock_update, mock_context)

        mock_query.answer.assert_awaited_once_with()
        fake_handler.assert_awaited_once_with(mock_update, mock_context, cb)

    async def test_whoknows_shared_button_answers_once_on_success_and_alert_on_missing(self):
        cb = Callback(Action.WHOKNOWS, owner_id=100)
        mock_query = MagicMock()
        mock_query.data = cb.encode()
        mock_query.from_user = MagicMock(id=200)  # different user allowed
        mock_query.answer = AsyncMock()

        mock_lfm_svc = MagicMock()
        mock_group_svc = MagicMock()
        mock_group_svc.get_whoknows = AsyncMock(return_value=("👑 Ranking", True))

        mock_update = MagicMock(spec=Update, callback_query=mock_query)
        mock_update.effective_chat = MagicMock(id=-1001, title="Music", username=None)
        mock_update.effective_message = MagicMock()
        mock_update.effective_message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.bot_data = {
            "lastfm_service": mock_lfm_svc,
            "group_service": mock_group_svc,
        }

        # Case 1: missing track -> single answer with show_alert=True
        mock_lfm_svc.get_now_playing = AsyncMock(return_value=(MagicMock(), None))
        await commands.button_handler(mock_update, mock_context)
        mock_query.answer.assert_awaited_once_with(
            "Could not determine current artist from Now Playing.", show_alert=True
        )
        mock_update.effective_message.reply_text.assert_not_awaited()

        # Case 2: valid track -> single answer() without alert + posts ranking
        mock_query.answer.reset_mock()
        track = MagicMock()
        track.artist = MagicMock()
        track.artist.name = "Radiohead"
        mock_lfm_svc.get_now_playing = AsyncMock(return_value=(MagicMock(), track))
        await commands.button_handler(mock_update, mock_context)
        mock_query.answer.assert_awaited_once_with()
        mock_update.effective_message.reply_text.assert_awaited_once_with("👑 Ranking")

    async def test_invalid_callback_data_answers_once(self):
        mock_query = MagicMock()
        mock_query.data = "garbage"
        mock_query.answer = AsyncMock()
        mock_update = MagicMock(spec=Update, callback_query=mock_query)
        await commands.button_handler(mock_update, MagicMock())
        mock_query.answer.assert_awaited_once_with("Invalid or expired button.")


class TestMediaTransitionsAndCommandSafety(unittest.IsolatedAsyncioTestCase):
    async def test_text_to_photo_transition_sends_photo_and_deletes_old_message(self):
        msg = MagicMock(spec=telegram.Message)
        msg.photo = ()
        msg.reply_photo = AsyncMock()
        msg.delete = AsyncMock()
        markup = MagicMock()

        await commands._update_or_replace_with_media(
            msg, "caption", markup, "https://img/cover.jpg"
        )
        msg.reply_photo.assert_awaited_once_with(
            photo="https://img/cover.jpg", caption="caption", reply_markup=markup
        )
        msg.delete.assert_awaited_once_with()

    async def test_photo_to_photo_and_missing_cover_transitions(self):
        markup = MagicMock()

        # Photo + cover -> edit_media
        photo_msg = MagicMock(spec=telegram.Message)
        photo_msg.photo = (MagicMock(),)
        photo_msg.edit_media = AsyncMock()
        await commands._update_or_replace_with_media(
            photo_msg, "cap", markup, "https://img/new.jpg"
        )
        photo_msg.edit_media.assert_awaited_once()

        # Photo + None cover -> edit_caption
        photo_msg.edit_caption = AsyncMock()
        await commands._update_or_replace_with_media(photo_msg, "cap", markup, None)
        photo_msg.edit_caption.assert_awaited_once_with(caption="cap", reply_markup=markup)

        # Text + None cover -> edit_text
        text_msg = MagicMock(spec=telegram.Message)
        text_msg.photo = ()
        text_msg.edit_text = AsyncMock()
        await commands._update_or_replace_with_media(text_msg, "cap", markup, None)
        text_msg.edit_text.assert_awaited_once_with("cap", reply_markup=markup)

    @patch("commands.db.log_command")
    async def test_status_button_uses_safe_media_transition_when_cover_none(self, _mock_log):
        mock_msg = MagicMock(spec=telegram.Message)
        mock_msg.photo = ()
        mock_msg.edit_text = AsyncMock()
        mock_msg.edit_media = AsyncMock()

        mock_query = MagicMock()
        mock_query.message = mock_msg

        mock_update = MagicMock(spec=Update)
        mock_update.callback_query = mock_query
        mock_update.effective_user = MagicMock(id=10, username="u")

        mock_view = MagicMock()
        mock_view.build_status_response = AsyncMock(return_value=("status html", None, None))
        mock_context = MagicMock()
        mock_context.bot_data = {"view_service": mock_view}

        await commands.status(mock_update, mock_context, show_cover=True, telegram_user_id=10)
        mock_msg.edit_media.assert_not_awaited()
        mock_msg.edit_text.assert_awaited_once_with("status html", reply_markup=None)

    @patch("commands.db.log_command")
    async def test_set_and_compare_no_args_escape_angle_brackets(self, _mock_log):
        mock_msg = MagicMock()
        mock_msg.text = "/set"
        mock_msg.reply_text = AsyncMock()
        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = MagicMock(id=1, username="u")
        mock_update.effective_message = mock_msg
        mock_update.effective_chat = MagicMock(id=1, type="private", title="", username="u")
        mock_context = MagicMock()
        mock_context.args = []

        await commands.lastfm_username_set(mock_update, mock_context)
        set_reply = mock_msg.reply_text.await_args.args[0]
        self.assertIn("&lt;username&gt;", set_reply)
        self.assertNotIn("<username>", set_reply)

        mock_msg.reply_text.reset_mock()
        mock_msg.text = "/compare"
        await commands.compare(mock_update, mock_context)
        cmp_reply = mock_msg.reply_text.await_args.args[0]
        self.assertIn("&lt;lastfm_username&gt;", cmp_reply)
        self.assertNotIn("<lastfm_username>", cmp_reply)

    @patch("commands.db.get_linked_user")
    @patch("commands.db.log_command")
    async def test_collage_error_and_value_error_are_html_escaped(
        self, _mock_log, mock_get_linked
    ):
        mock_get_linked.return_value = MagicMock(lastfm_username="alice")
        mock_msg = MagicMock()
        mock_msg.text = "/collage <script>"
        mock_msg.reply_text = AsyncMock()
        status_msg = MagicMock()
        status_msg.delete = AsyncMock()

        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = MagicMock(id=1, username="alice")
        mock_update.effective_message = mock_msg
        mock_update.effective_chat = None

        mock_context = MagicMock()
        mock_context.args = ["<script>"]
        mock_context.bot_data = {
            "view_service": MagicMock(),
            "collage_service": MagicMock(),
        }

        await commands.collage(mock_update, mock_context)
        err_msg = mock_msg.reply_text.await_args.args[0]
        self.assertIn("&lt;script&gt;", err_msg)
        self.assertNotIn("<script>", err_msg)

        # Now runtime error during generation
        mock_msg.reply_text.reset_mock()
        mock_msg.reply_text.side_effect = [status_msg, None]
        mock_context.args = ["3x3"]
        mock_context.bot_data["collage_service"].generate_collage_image = AsyncMock(
            side_effect=RuntimeError("Boom <bad> & error")
        )
        await commands.collage(mock_update, mock_context)
        runtime_err = mock_msg.reply_text.await_args_list[1].args[0]
        self.assertIn("Boom &lt;bad&gt; &amp; error", runtime_err)
        self.assertNotIn("<bad>", runtime_err)
        status_msg.delete.assert_awaited_once()


class TestHtmlEscapingAndUxServices(unittest.IsolatedAsyncioTestCase):
    async def test_start_missing_username_fallback_and_escaping(self):
        view_service = ViewService(MagicMock())
        with patch("services.db.get_linked_user", return_value=None):
            tg_user_with_first = MagicMock(
                spec=TgUser, id=1, username=None, first_name="A<b>C"
            )
            msg1 = await view_service.build_start_response(tg_user_with_first)
            self.assertIn("Hi A&lt;b&gt;C,", msg1)
            self.assertNotIn("@None", msg1)

            tg_user_no_name = MagicMock(
                spec=TgUser, id=2, username=None, first_name=None
            )
            msg2 = await view_service.build_start_response(tg_user_no_name)
            self.assertIn("Hi there,", msg2)

    async def test_status_empty_tracks_returns_empty_message_not_unlinked(self):
        mock_lfm_svc = MagicMock()
        mock_lfm_svc.get_recent_tracks = AsyncMock(return_value=[])
        view_service = ViewService(mock_lfm_svc)

        linked = MagicMock(lastfm_username="alice<1>")
        with patch("services.db.get_linked_user", return_value=linked):
            msg, kb, cover = await view_service.build_status_response(123)
        self.assertIn("No recent tracks found", msg)
        self.assertIn("alice&lt;1&gt;", msg)
        self.assertNotIn("/set [username]", msg)
        self.assertIsNone(kb)
        self.assertIsNone(cover)

    async def test_np_status_tops_compare_collage_html_escaping_and_english_copy(self):
        mock_lfm_svc = MagicMock()
        view_service = ViewService(mock_lfm_svc)

        # NP with special characters
        track = MagicMock()
        track.artist = SimpleNamespace(name="A & B <band>")
        track.title = "Song <1> & 2"
        track.get_url.return_value = "https://last.fm/music/A+B?x=1&y='2'"
        album = MagicMock()
        album.title = "Album <3>"
        album.get_cover_image.return_value = "https://img/cover.jpg"
        track.get_album.return_value = album
        user = MagicMock(lastfm_username="lfm<user>", telegram_username="tg<user>")
        mock_lfm_svc.get_now_playing = AsyncMock(return_value=(user, track))

        np_msg, np_kb, _ = await view_service.build_np_response(1)
        self.assertIn("lfm&lt;user&gt;", np_msg)
        self.assertIn("A &amp; B &lt;band&gt;", np_msg)
        self.assertIn("Song &lt;1&gt; &amp; 2", np_msg)
        self.assertIn("Album &lt;3&gt;", np_msg)
        self.assertIn("&#x27;2&#x27;", np_msg)
        button_texts = [btn.text for btn in np_kb.inline_keyboard[0]]
        self.assertIn("👑 Who knows?", button_texts)

        # Status with special characters
        played = MagicMock()
        played.timestamp = None
        played.track = track
        played.album = "Album & <More>"
        mock_lfm_svc.get_recent_tracks = AsyncMock(return_value=[played])
        with patch("services.db.get_linked_user", return_value=user):
            st_msg, _, _ = await view_service.build_status_response(1)
        self.assertIn("tg&lt;user&gt;", st_msg)
        self.assertIn("Album &amp; &lt;More&gt;", st_msg)

        # Tops with special characters
        top_item = MagicMock()
        top_item.item = MagicMock()
        top_item.item.name = "Artist <X> & Y"
        top_item.item.get_url.return_value = "https://last.fm/music/X&Y"
        top_item.weight = 42
        mock_lfm_svc.get_tops = AsyncMock(return_value=[top_item])
        with patch("services.db.get_linked_user", return_value=user):
            tops_msg, _ = await view_service.build_tops_response(
                1, EntityType.ARTIST, LfmPeriod.WEEK
            )
        self.assertIn("lfm%3Cuser%3E", tops_msg)
        self.assertIn("lfm&lt;user&gt;", tops_msg)
        self.assertIn("Artist &lt;X&gt; &amp; Y", tops_msg)

        # Compare with special characters
        mock_lfm_svc.get_user_stats = AsyncMock(
            side_effect=[
                {
                    "username": "u1<x>",
                    "playcount": 100,
                    "top_artists": [{"name": "Band <A>", "plays": 50}],
                },
                {
                    "username": "u2&y",
                    "playcount": 200,
                    "top_artists": [{"name": "Band & B", "plays": 60}],
                },
            ]
        )
        mock_lfm_svc.get_common_artists = AsyncMock(
            return_value=[{"name": "Common <Band>", "plays1": 10, "plays2": 20}]
        )
        with patch("services.db.get_linked_user", return_value=user):
            cmp_msg = await view_service.build_compare_response(1, "u2&y")
        self.assertIn("u1&lt;x&gt;", cmp_msg)
        self.assertIn("u2&amp;y", cmp_msg)
        self.assertIn("Common &lt;Band&gt;", cmp_msg)

        # Collage caption with special characters & English
        caption = ViewService.build_collage_caption(
            entity_type="album",
            size="3x3",
            period="7day",
            lastfm_username="u<name>",
            show_text=False,
            filter_name="duotone",
        )
        self.assertIn("no text, filter duotone", caption)
        self.assertIn("u%3Cname%3E", caption)
        self.assertIn("u&lt;name&gt;", caption)

    async def test_changelog_escapes_html_and_truncates_safely(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "CHANGELOG.md"
            p.write_text(("A < B & C > D\n" * 400), encoding="utf-8")
            with patch("services.config.CHANGELOG_PATH", p):
                out = await ViewService.build_changelog_response()
        self.assertLessEqual(len(out), 4096)
        self.assertTrue(out.startswith("<pre>"))
        self.assertTrue(out.endswith("</pre>"))
        inner = out[len("<pre>") : -len("</pre>")]
        self.assertIn("&lt;", inner)
        self.assertIn("&amp;", inner)
        # Ensure no unescaped '<' or '>' inside <pre>
        self.assertNotIn("<", inner)
        self.assertNotIn(">", inner)

    async def test_preferences_and_privacy_english_copy(self):
        view_service = ViewService(MagicMock())
        user = MagicMock(group_opt_out=False)
        with patch("services.db.get_user", return_value=user):
            _, kb = await view_service.build_preferences_response(1)
        self.assertEqual(
            kb.inline_keyboard[0][0].text, "🔒 Hide me from group rankings"
        )

        with patch("services.db.toggle_user_group_opt_out", return_value=True):
            msg = view_service.build_preferences_toggle_opt_out_response(1)
        self.assertIn("Hidden from group rankings 🔒", msg)

        with patch("services.db.toggle_user_group_opt_out", return_value=False):
            msg2 = view_service.build_preferences_toggle_opt_out_response(1)
        self.assertIn("Visible in group rankings 🔓", msg2)

        privacy_msg = await ViewService.build_privacy_response()
        self.assertIn("/preferences", privacy_msg)
        self.assertIn("Unlink your account", privacy_msg)
        self.assertIn("command usage logs", privacy_msg.lower())
        self.assertIn("crowns", privacy_msg.lower())

    async def test_interactive_collage_buttons_and_finally_cleanup(self):
        view_service = ViewService(MagicMock())
        # No theme/overlay -> Skip & Generate
        _, kb_skip = await view_service.build_collage_selection_response(
            1, entity=Entity.ALBUM, size="3x3", period=Period.WEEK
        )
        self.assertEqual(kb_skip.inline_keyboard[2][0].text, "✨ Skip & Generate")

        # Theme selected -> Generate
        _, kb_gen = await view_service.build_collage_selection_response(
            1, entity=Entity.ALBUM, size="3x3", period=Period.WEEK, theme="neon", style="set"
        )
        self.assertEqual(kb_gen.inline_keyboard[2][0].text, "✅ Generate")

        # _handle_collage deletes status message in finally even on error
        mock_query = MagicMock()
        mock_query.message = MagicMock()
        mock_query.message.reply_photo = AsyncMock()
        mock_query.message.reply_text = AsyncMock()
        mock_query.message.delete = AsyncMock()
        mock_query.edit_message_text = AsyncMock()

        mock_update = MagicMock(spec=Update, callback_query=mock_query)
        mock_update.effective_chat = MagicMock(id=-1)
        mock_collage_svc = MagicMock(spec=CollageService)
        mock_collage_svc.generate_collage_image = AsyncMock(
            side_effect=RuntimeError("bad <error>")
        )
        mock_context = MagicMock()
        mock_context.bot.send_chat_action = AsyncMock()
        mock_context.bot_data = {
            "view_service": view_service,
            "collage_service": mock_collage_svc,
        }
        cb = Callback(
            Action.COLLAGE,
            owner_id=1,
            entity=Entity.ALBUM,
            size="3x3",
            period=Period.WEEK,
            style="skip",
        )
        with patch("commands.db.get_linked_user", return_value=MagicMock(lastfm_username="u")):
            await commands._handle_collage(mock_update, mock_context, cb)

        mock_query.message.delete.assert_awaited_once()
        err_text = mock_query.message.reply_text.await_args.args[0]
        self.assertIn("bad &lt;error&gt;", err_text)

        # Success case also deletes in finally
        mock_query.message.delete.reset_mock()
        mock_collage_svc.generate_collage_image = AsyncMock(return_value=BytesIO(b"img"))
        with patch("commands.db.get_linked_user", return_value=MagicMock(lastfm_username="u")):
            await commands._handle_collage(mock_update, mock_context, cb)
        mock_query.message.reply_photo.assert_awaited_once()
        mock_query.message.delete.assert_awaited_once()

    async def test_crowns_showcase_truncates_under_4096_and_dethrone_is_english(self):
        mock_lfm = MagicMock()
        group_service = GroupService(mock_lfm)

        # Test 200 crowns truncation
        crowns = [
            SimpleNamespace(
                artist_name=f"Artist <{i}> & Band",
                artist_url=f"https://www.last.fm/music/Artist_{i}",
                playcount=1000 - i,
            )
            for i in range(200)
        ]
        target_user = SimpleNamespace(telegram_id=1, telegram_username="alice<1>")
        with patch("services.db.get_user_crowns", return_value=crowns):
            out = await group_service.get_user_crowns_showcase(-100, "Chat <X>", target_user)

        self.assertLessEqual(len(out), 4096)
        self.assertIn("more crowns</i>", out)
        self.assertIn("@alice&lt;1&gt;", out)
        self.assertIn("Chat &lt;X&gt;", out)

        # Test English dethroned banner & escaping
        mock_lfm.get_artist_canonical_info.return_value = (
            "Radiohead <HQ>",
            "https://www.last.fm/music/Radiohead",
        )
        mock_lfm.get_user_artist_playcount.side_effect = lambda u, a: 500
        u_new = SimpleNamespace(telegram_id=2, telegram_username="new<king>", lastfm_username="new_lfm")
        prev_crown = SimpleNamespace(
            user=SimpleNamespace(telegram_id=1, telegram_username="old<king>"),
            playcount=300,
        )
        with (
            patch("services.db.get_linked_chat_members", return_value=[u_new]),
            patch("services.db.upsert_crown", return_value=(MagicMock(), prev_crown)),
        ):
            wk_html, ok = await group_service.get_whoknows(-100, "Group <1>", "radiohead")

        self.assertTrue(ok)
        self.assertIn("NEW BAND KING!", wk_html)
        self.assertNotIn("NOU REI", wk_html)
        self.assertIn("@new&lt;king&gt;", wk_html)
        self.assertIn("@old&lt;king&gt;", wk_html)
        self.assertIn(html.escape("Radiohead <HQ>"), wk_html)


class TestPassiveGroupDiscoveryAndSentry(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.orig_db = db.db
        self.test_db = SqliteExtDatabase(":memory:")
        db.db = self.test_db
        db.db.bind(db.MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(db.MODELS)

    def tearDown(self):
        self.test_db.drop_tables(db.MODELS)
        self.test_db.close()
        db.db = self.orig_db
        self.orig_db.bind(db.MODELS, bind_refs=False, bind_backrefs=False)

    async def test_track_group_member_only_tracks_linked_non_bot_users(self):
        # Bot user -> ignored
        bot_update = MagicMock(spec=Update)
        bot_update.effective_user = MagicMock(id=10, is_bot=True, username="mybot")
        bot_update.effective_chat = MagicMock(id=-1001, title="Group", type="group")
        await commands.track_group_member(bot_update, MagicMock())
        self.assertIsNone(db.get_user(10))
        self.assertEqual(db.ChatMember.select().count(), 0)

        # Unlinked user -> ignored (no placeholder row created)
        unlinked_update = MagicMock(spec=Update)
        unlinked_update.effective_user = MagicMock(id=20, is_bot=False, username="unlinked")
        unlinked_update.effective_chat = MagicMock(id=-1001, title="Group", type="group")
        await commands.track_group_member(unlinked_update, MagicMock())
        self.assertIsNone(db.get_user(20))
        self.assertEqual(db.ChatMember.select().count(), 0)

        # Linked user -> ChatMember created/refreshed
        db.create_or_update_user(30, "linked", "linked_lfm")
        linked_update = MagicMock(spec=Update)
        linked_update.effective_user = MagicMock(id=30, is_bot=False, username="linked")
        linked_update.effective_chat = MagicMock(
            id=-1001, title="Music Group", type="supergroup", username=None
        )
        await commands.track_group_member(linked_update, MagicMock())
        members = db.get_linked_chat_members(-1001)
        self.assertEqual([m.telegram_id for m in members], [30])

    def test_bot_main_disables_sentry_pii_and_registers_passive_handler(self):
        mock_app = MagicMock()
        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.defaults.return_value = mock_builder
        mock_builder.concurrent_updates.return_value = mock_builder
        mock_builder.post_init.return_value = mock_builder
        mock_builder.build.return_value = mock_app

        with (
            patch("bot.sentry_sdk.init") as mock_sentry_init,
            patch("bot.ApplicationBuilder", return_value=mock_builder),
            patch("bot.LastfmClient"),
            patch("bot.CollageService"),
        ):
            bot.main()

        mock_sentry_init.assert_called_once()
        self.assertFalse(mock_sentry_init.call_args.kwargs["send_default_pii"])
        passive_handlers = [
            call
            for call in mock_app.add_handler.call_args_list
            if isinstance(call.args[0], MessageHandler)
            and call.args[0].callback is commands.track_group_member
        ]
        self.assertEqual(len(passive_handlers), 1)
        self.assertEqual(passive_handlers[0].kwargs.get("group"), 1)


if __name__ == "__main__":
    unittest.main()
