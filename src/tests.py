import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure src is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image
from telegram import Chat as TgChat, Update, User as TgUser
import telegram

import bot
import commands
from callbacks import Action, Callback, Entity, Period
from services import CollageOptions, CollageService, ViewService, parse_collage_args


class TestCollageArgParser(unittest.TestCase):
    def test_default_args(self):
        opts = parse_collage_args([])
        self.assertEqual(opts.entity, "album")
        self.assertEqual(opts.cols, 3)
        self.assertEqual(opts.rows, 3)
        self.assertEqual(opts.period, "7day")
        self.assertIsNone(opts.tile_size)
        self.assertIsNone(opts.theme)
        self.assertIsNone(opts.overlay_style)
        self.assertTrue(opts.show_text)
        self.assertIsNone(opts.preset)

    def test_custom_dimensions(self):
        self.assertEqual(parse_collage_args(["5x5"]).cols, 5)
        self.assertEqual(parse_collage_args(["5x5"]).rows, 5)
        self.assertEqual(parse_collage_args(["3x5"]).cols, 3)
        self.assertEqual(parse_collage_args(["3x5"]).rows, 5)
        self.assertEqual(parse_collage_args(["4"]).cols, 4)
        self.assertEqual(parse_collage_args(["4"]).rows, 4)
        self.assertEqual(parse_collage_args(["10x10"]).cols, 10)
        self.assertEqual(parse_collage_args(["10x10"]).rows, 10)
        self.assertEqual(parse_collage_args(["10x5"]).cols, 10)
        self.assertEqual(parse_collage_args(["10x5"]).rows, 5)
        self.assertEqual(parse_collage_args(["20x20"]).cols, 20)
        self.assertEqual(parse_collage_args(["20x20"]).rows, 20)

    def test_tile_size_parsing(self):
        self.assertEqual(parse_collage_args(["150px"]).tile_size, 150)
        self.assertEqual(parse_collage_args(["ts:200"]).tile_size, 200)
        self.assertEqual(parse_collage_args(["size=100"]).tile_size, 100)
        self.assertEqual(parse_collage_args(["tile_size:300"]).tile_size, 300)

    def test_invalid_tile_size_raises(self):
        with self.assertRaises(ValueError):
            parse_collage_args(["40px"])
        with self.assertRaises(ValueError):
            parse_collage_args(["700px"])
        with self.assertRaises(ValueError):
            parse_collage_args(["ts:10"])

    def test_custom_entities(self):
        self.assertEqual(parse_collage_args(["artists"]).entity, "artist")
        self.assertEqual(parse_collage_args(["album"]).entity, "album")
        self.assertEqual(parse_collage_args(["tracks"]).entity, "track")
        self.assertEqual(parse_collage_args(["songs"]).entity, "track")

    def test_custom_periods(self):
        self.assertEqual(parse_collage_args(["week"]).period, "7day")
        self.assertEqual(parse_collage_args(["1month"]).period, "1month")
        self.assertEqual(parse_collage_args(["3m"]).period, "3month")
        self.assertEqual(parse_collage_args(["6m"]).period, "6month")
        self.assertEqual(parse_collage_args(["year"]).period, "12month")
        self.assertEqual(parse_collage_args(["overall"]).period, "overall")

    def test_theme_parsing(self):
        self.assertEqual(parse_collage_args(["theme:neon"]).theme, "neon")
        self.assertEqual(parse_collage_args(["theme=glass"]).theme, "glassmorphic")
        self.assertEqual(parse_collage_args(["tema:sunset"]).theme, "sunset")
        self.assertEqual(parse_collage_args(["theme:dark"]).theme, "dark")
        with self.assertRaises(ValueError):
            parse_collage_args(["theme:unknown"])

    def test_overlay_parsing(self):
        self.assertEqual(parse_collage_args(["overlay:pill"]).overlay_style, "pill")
        self.assertEqual(parse_collage_args(["ov:clean"]).overlay_style, "clean")
        self.assertEqual(parse_collage_args(["style:tint"]).overlay_style, "full_tint")
        self.assertEqual(
            parse_collage_args(["overlay:gradient"]).overlay_style, "gradient"
        )
        with self.assertRaises(ValueError):
            parse_collage_args(["overlay:bogus"])

    def test_preset_parsing(self):
        self.assertEqual(
            parse_collage_args(["preset:instagram-story"]).preset, "instagram-story"
        )
        self.assertEqual(parse_collage_args(["preset:story"]).preset, "instagram-story")
        self.assertEqual(parse_collage_args(["story"]).preset, "instagram-story")
        self.assertEqual(parse_collage_args(["post"]).preset, "instagram-post")
        self.assertEqual(parse_collage_args(["header"]).preset, "twitter-header")
        self.assertEqual(parse_collage_args(["wallpaper"]).preset, "desktop-wallpaper")
        self.assertEqual(parse_collage_args(["4k"]).preset, "desktop-wallpaper-4k")
        with self.assertRaises(ValueError):
            parse_collage_args(["preset:bogus"])

    def test_geometry_parsing(self):
        opts = parse_collage_args(
            ["corner:12", "border:3", "border_color:#FF5A5F", "spacing:8"]
        )
        self.assertEqual(opts.corner_radius, 12)
        self.assertEqual(opts.border_width, 3)
        self.assertEqual(opts.border_color, "#FF5A5F")
        self.assertEqual(opts.spacing, 8)
        opts2 = parse_collage_args(["radius:5", "bc:abcdef", "gap:2"])
        self.assertEqual(opts2.corner_radius, 5)
        self.assertEqual(opts2.border_color, "#abcdef")
        self.assertEqual(opts2.spacing, 2)
        with self.assertRaises(ValueError):
            parse_collage_args(["border_color:#ZZZZZZ"])

    def test_notext_and_fallback(self):
        self.assertFalse(parse_collage_args(["notext"]).show_text)
        self.assertTrue(parse_collage_args([]).show_playcount)
        self.assertFalse(parse_collage_args(["noplaycount"]).show_playcount)
        self.assertFalse(parse_collage_args(["nocount"]).show_playcount)
        self.assertFalse(parse_collage_args(["noplaycounts"]).show_playcount)
        self.assertEqual(parse_collage_args(["fallback:black"]).fallback_style, "black")
        self.assertEqual(
            parse_collage_args(["fallback:gradient"]).fallback_style, "gradient"
        )
        with self.assertRaises(ValueError):
            parse_collage_args(["fallback:bogus"])

    def test_filter_and_bold_parsing(self):
        opts = parse_collage_args(["bold", "filter:duotone"])
        self.assertTrue(opts.font_bold)
        self.assertEqual(opts.filter, "duotone")

        opts2 = parse_collage_args(["fx:sepia"])
        self.assertEqual(opts2.filter, "sepia")

        opts3 = parse_collage_args(["filter:duotone:#123456,#abcdef"])
        self.assertEqual(opts3.filter, "duotone:#123456,#abcdef")

        with self.assertRaises(ValueError):
            parse_collage_args(["filter:unknown_filter"])

    def test_mixed_order_arguments(self):
        opts = parse_collage_args(
            ["overall", "artist", "10x10", "150px", "theme:neon", "overlay:pill", "bold", "filter:matrix"]
        )
        self.assertEqual(opts.entity, "artist")
        self.assertEqual(opts.cols, 10)
        self.assertEqual(opts.rows, 10)
        self.assertEqual(opts.period, "overall")
        self.assertEqual(opts.tile_size, 150)
        self.assertEqual(opts.theme, "neon")
        self.assertEqual(opts.overlay_style, "pill")
        self.assertTrue(opts.font_bold)
        self.assertEqual(opts.filter, "matrix")

    def test_invalid_dimension_raises(self):
        with self.assertRaises(ValueError):
            parse_collage_args(["21x21"])
        with self.assertRaises(ValueError):
            parse_collage_args(["0x0"])
        with self.assertRaises(ValueError):
            parse_collage_args(["25"])
        with self.assertRaises(ValueError):
            parse_collage_args(["20x21"])  # > 400 tiles

    def test_unrecognized_argument_raises(self):
        with self.assertRaises(ValueError):
            parse_collage_args(["invalid_arg_xyz"])


class TestCallbackProtocol(unittest.TestCase):
    def test_collage_callback_roundtrip(self):
        cb = Callback(
            action=Action.COLLAGE,
            owner_id=987654321,
            entity=Entity.ARTIST,
            period=Period.WEEK,
            size="10x10",
        )
        encoded = cb.encode()
        self.assertLessEqual(len(encoded.encode("utf-8")), 64)

        decoded = Callback.decode(encoded)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.action, Action.COLLAGE)
        self.assertEqual(decoded.owner_id, 987654321)
        self.assertEqual(decoded.entity, Entity.ARTIST)
        self.assertEqual(decoded.period, Period.WEEK)
        self.assertEqual(decoded.size, "10x10")

    def test_collage_callback_roundtrip_with_style(self):
        cb = Callback(
            action=Action.COLLAGE,
            owner_id=987654321,
            entity=Entity.ARTIST,
            period=Period.WEEK,
            size="10x10",
            theme="neon",
            overlay="pill",
            preset="story",
            style="set",
        )
        encoded = cb.encode()
        self.assertLessEqual(len(encoded.encode("utf-8")), 64)

        decoded = Callback.decode(encoded)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.theme, "neon")
        self.assertEqual(decoded.overlay, "pill")
        self.assertEqual(decoded.preset, "story")
        self.assertEqual(decoded.style, "set")

    def test_legacy_callback_decode(self):
        decoded = Callback.decode("1|cl|987654321|a|w|10x10")
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.entity, Entity.ARTIST)
        self.assertEqual(decoded.period, Period.WEEK)
        self.assertEqual(decoded.size, "10x10")
        self.assertIsNone(decoded.theme)
        self.assertIsNone(decoded.overlay)
        self.assertIsNone(decoded.preset)
        self.assertIsNone(decoded.style)

    def test_collage_conversion_helpers(self):
        cb = Callback(
            action=Action.COLLAGE, owner_id=123, entity=Entity.TRACK, period=Period.YEAR
        )
        self.assertEqual(cb.to_collage_entity_str(), "track")
        self.assertEqual(cb.to_collage_period_str(), "12month")

    def test_preset_conversion_helper(self):
        cb = Callback(action=Action.COLLAGE, owner_id=123, preset="story")
        self.assertEqual(cb.to_collage_preset_str(), "instagram-story")
        cb_none = Callback(action=Action.COLLAGE, owner_id=123)
        self.assertIsNone(cb_none.to_collage_preset_str())


class TestCollageService(unittest.IsolatedAsyncioTestCase):
    @patch("services.CollageGenerator")
    async def test_generate_collage_image(self, mock_generator_cls):
        mock_gen_instance = MagicMock()
        mock_generator_cls.return_value = mock_gen_instance

        # Mock generate_async() returning a real in-memory PIL image
        test_image = Image.new("RGB", (300, 300), color=(255, 0, 0))
        mock_gen_instance.generate_async = AsyncMock(return_value=test_image)

        service = CollageService(api_key="dummy_key", api_secret="dummy_secret")
        options = CollageOptions(
            entity="album",
            cols=10,
            rows=10,
            period="7day",
            tile_size=150,
            theme="neon",
            overlay_style="pill",
            show_playcount=False,
            font_bold=True,
            filter="duotone",
            preset="instagram-post",
            corner_radius=12,
            border_width=3,
            border_color="#FF5A5F",
            spacing=8,
            fallback_style="black",
        )
        bio = await service.generate_collage_image(username="testuser", options=options)

        self.assertIsInstance(bio, BytesIO)
        mock_gen_instance.generate_async.assert_awaited_once()
        call_kwargs = mock_gen_instance.generate_async.await_args.kwargs
        self.assertEqual(call_kwargs["entity"], "album")
        self.assertEqual(call_kwargs["username"], "testuser")
        self.assertEqual(call_kwargs["cols"], 10)
        self.assertEqual(call_kwargs["rows"], 10)
        self.assertEqual(call_kwargs["period"], "7day")
        self.assertEqual(call_kwargs["tile_size"], 150)
        self.assertEqual(call_kwargs["theme"], "neon")
        self.assertEqual(call_kwargs["overlay_style"], "pill")
        self.assertFalse(call_kwargs["show_playcount"])
        self.assertTrue(call_kwargs["font_bold"])
        self.assertIn("filters", call_kwargs)
        self.assertEqual(call_kwargs["preset"], "instagram-post")
        self.assertEqual(call_kwargs["corner_radius"], 12)
        self.assertEqual(call_kwargs["border_width"], 3)
        self.assertEqual(call_kwargs["border_color"], "#FF5A5F")
        self.assertEqual(call_kwargs["spacing"], 8)
        self.assertEqual(call_kwargs["fallback_style"], "black")

        # Verify it's a valid exported image stream (WebP by default)
        loaded_img = Image.open(bio)
        self.assertEqual(loaded_img.size, (300, 300))

    @patch("services.CollageGenerator")
    async def test_generate_collage_image_defaults_omit_style_kwargs(
        self, mock_generator_cls
    ):
        mock_gen_instance = MagicMock()
        mock_generator_cls.return_value = mock_gen_instance
        test_image = Image.new("RGB", (300, 300), color=(255, 0, 0))
        mock_gen_instance.generate_async = AsyncMock(return_value=test_image)

        service = CollageService(api_key="dummy_key", api_secret="dummy_secret")
        options = CollageOptions(entity="album", cols=3, rows=3, period="7day")
        await service.generate_collage_image(username="testuser", options=options)

        mock_gen_instance.generate_async.assert_awaited_once_with(
            entity="album",
            username="testuser",
            cols=3,
            rows=3,
            period="7day",
            tile_size=None,
            cache_dir=service._cache_dir,
        )

    @patch("services.CollageGenerator")
    @patch("services.export_image")
    async def test_generate_collage_image_fallback_on_unsupported_format(
        self, mock_export_image, mock_generator_cls
    ):
        mock_gen_instance = MagicMock()
        mock_generator_cls.return_value = mock_gen_instance
        test_image = Image.new("RGB", (300, 300), color=(255, 0, 0))
        mock_gen_instance.generate_async = AsyncMock(return_value=test_image)

        # First call to export_image raises KeyError('WEBP'), second call succeeds
        def side_effect(img, path, format=None, **kwargs):
            if format == "WEBP":
                raise KeyError("WEBP")
            img.save(path, format=format)

        mock_export_image.side_effect = side_effect

        service = CollageService(api_key="dummy_key", api_secret="dummy_secret")
        options = CollageOptions(entity="album", cols=3, rows=3, period="7day")
        bio = await service.generate_collage_image(
            username="testuser", options=options, export_format="WEBP"
        )
        self.assertEqual(bio.name, "collage.png")
        self.assertEqual(mock_export_image.call_count, 2)


class TestViewServiceCollage(unittest.IsolatedAsyncioTestCase):
    def test_collage_caption(self):
        caption = ViewService.build_collage_caption(
            entity_type="album", size="10x10", period="7day", lastfm_username="testuser"
        )
        self.assertIn("(10x10, 1 week)", caption)
        self.assertNotIn("px tiles", caption)

        caption_with_tile = ViewService.build_collage_caption(
            entity_type="artist",
            size="3x3",
            period="overall",
            lastfm_username="testuser",
            tile_size=150,
        )
        self.assertIn("(3x3, all time, 150px tiles)", caption_with_tile)

    def test_collage_caption_with_style(self):
        caption = ViewService.build_collage_caption(
            entity_type="album",
            size="3x3",
            period="7day",
            lastfm_username="testuser",
            theme="neon",
            overlay_style="pill",
            show_text=False,
            font_bold=True,
            filter_name="duotone",
        )
        self.assertIn("neon, pill, sense text, bold, filtre duotone", caption)

    def test_collage_caption_with_preset(self):
        caption = ViewService.build_collage_caption(
            entity_type="album",
            size="3x3",
            period="overall",
            lastfm_username="testuser",
            preset="instagram-post",
        )
        self.assertIn("instagram-post 3x3", caption)

    async def test_interactive_selection_steps(self):
        mock_lastfm_service = MagicMock()
        view_service = ViewService(mock_lastfm_service)

        # Step 1: No entity
        msg, kb = await view_service.build_collage_selection_response(
            telegram_user_id=123
        )
        self.assertIn("entity", msg.lower())
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard), 1)
        self.assertEqual(len(kb.inline_keyboard[0]), 3)

        # Step 2: Entity chosen, no size/preset -> size step with presets row
        msg, kb = await view_service.build_collage_selection_response(
            telegram_user_id=123, entity=Entity.ALBUM
        )
        self.assertIn("size", msg.lower())
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard), 3)
        self.assertEqual(len(kb.inline_keyboard[0]), 3)
        self.assertEqual(len(kb.inline_keyboard[1]), 3)
        self.assertEqual(len(kb.inline_keyboard[2]), 5)

        # Step 3: Entity and size chosen, no period
        msg, kb = await view_service.build_collage_selection_response(
            telegram_user_id=123, entity=Entity.ALBUM, size="10x10"
        )
        self.assertIn("period", msg.lower())
        self.assertIsNotNone(kb)

        # Step 3b: Entity and preset chosen, no period
        msg, kb = await view_service.build_collage_selection_response(
            telegram_user_id=123, entity=Entity.ALBUM, preset="story"
        )
        self.assertIn("instagram-story", msg.lower())
        self.assertIsNotNone(kb)

        # Step 4: Entity, size and period chosen, no style -> style step
        msg, kb = await view_service.build_collage_selection_response(
            telegram_user_id=123, entity=Entity.ALBUM, size="10x10", period=Period.WEEK
        )
        self.assertIn("style", msg.lower())
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard), 3)
        self.assertEqual(len(kb.inline_keyboard[0]), 5)
        self.assertEqual(len(kb.inline_keyboard[1]), 5)
        self.assertEqual(len(kb.inline_keyboard[2]), 1)

        # Style selected -> style step re-rendered with selection
        msg, kb = await view_service.build_collage_selection_response(
            telegram_user_id=123,
            entity=Entity.ALBUM,
            size="10x10",
            period=Period.WEEK,
            theme="neon",
            overlay="pill",
            style="set",
        )
        self.assertIn("neon / pill", msg.lower())
        self.assertIsNotNone(kb)


class TestBotCoreAndLifecycle(unittest.IsolatedAsyncioTestCase):
    def test_bot_commands_definition(self):
        self.assertGreater(len(commands.BOT_COMMANDS), 5)
        command_names = [cmd.command for cmd in commands.BOT_COMMANDS]
        self.assertIn("np", command_names)
        self.assertIn("status", command_names)
        self.assertIn("tops", command_names)
        self.assertIn("collage", command_names)
        self.assertIn("vibe", command_names)
        self.assertIn("roast", command_names)
        self.assertIn("recommend", command_names)

    async def test_post_init_registers_commands(self):
        mock_app = MagicMock()
        mock_app.bot.set_my_commands = AsyncMock()

        await bot.post_init(mock_app)
        mock_app.bot.set_my_commands.assert_awaited_once_with(commands.BOT_COMMANDS)

    async def test_global_error_handler_sends_notification(self):
        mock_context = MagicMock()
        mock_context.error = ValueError("Test error message")
        mock_context.bot.send_message = AsyncMock()

        mock_update = MagicMock(spec=Update)
        mock_chat = MagicMock(spec=TgChat)
        mock_chat.id = 12345
        mock_update.effective_chat = mock_chat

        with (
            patch("bot.config.SENTRY_DSN", "https://key@sentry.io/123"),
            patch("bot.sentry_sdk.capture_exception") as mock_sentry,
        ):
            await bot.error_handler(mock_update, mock_context)
            mock_sentry.assert_called_once_with(mock_context.error)
            mock_context.bot.send_message.assert_awaited_once_with(
                chat_id=12345,
                text="⚠️ An unexpected error occurred while processing your request. Please try again later.",
            )


class TestCommandDecoratorsAndHandlers(unittest.IsolatedAsyncioTestCase):
    @patch("db.log_command")
    async def test_log_command_decorator_with_effective_user(self, mock_db_log):
        @commands.log_command("test_cmd")
        async def dummy_handler(update, context):
            return "ok"

        mock_update = MagicMock(spec=Update)
        mock_user = MagicMock(spec=TgUser)
        mock_user.id = 999
        mock_user.username = "test_user"
        mock_chat = MagicMock(spec=TgChat)
        mock_chat.id = 888
        mock_chat.type = "private"
        mock_chat.title = ""
        mock_chat.username = "test_user"

        mock_update.effective_user = mock_user
        mock_update.effective_chat = mock_chat

        mock_context = MagicMock()
        mock_context.args = ["arg1", "arg2"]

        result = await dummy_handler(mock_update, mock_context)
        self.assertEqual(result, "ok")
        mock_db_log.assert_called_once_with(
            user_id=999,
            username="test_user",
            command="test_cmd",
            args="arg1 arg2",
            chat_id=888,
            chat_type="private",
            chat_name="test_user",
        )

    def test_tops_arg_parser_edge_cases(self):
        entity, period = commands._parse_tops_args(["artists", "1month"])
        self.assertEqual(entity, commands.lastfm.EntityType.ARTIST)
        self.assertEqual(period, commands.lastfm.Period.ONE_MONTH)

        entity, period = commands._parse_tops_args(["tracks", "overall"])
        self.assertEqual(entity, commands.lastfm.EntityType.TRACK)
        self.assertEqual(period, commands.lastfm.Period.OVERALL)


class TestEditMessageText(unittest.IsolatedAsyncioTestCase):
    async def test_tolerates_message_not_modified(self):
        mock_query = MagicMock()
        mock_query.edit_message_text = AsyncMock(
            side_effect=telegram.error.BadRequest("Message is not modified")
        )
        await commands._edit_message_text(mock_query, "hello", None)
        mock_query.edit_message_text.assert_awaited_once_with(text="hello")

    async def test_passes_reply_markup(self):
        mock_query = MagicMock()
        mock_query.edit_message_text = AsyncMock()
        markup = MagicMock()
        await commands._edit_message_text(mock_query, "hello", markup)
        mock_query.edit_message_text.assert_awaited_once_with(
            text="hello", reply_markup=markup
        )

    async def test_rethrows_other_errors(self):
        mock_query = MagicMock()
        mock_query.edit_message_text = AsyncMock(
            side_effect=telegram.error.BadRequest("Another error")
        )
        with self.assertRaises(telegram.error.BadRequest):
            await commands._edit_message_text(mock_query, "hello", None)


class TestDatabaseGroupAndCrowns(unittest.TestCase):
    def setUp(self):
        import db

        self.db = db
        self.orig_db = db.db
        from playhouse.sqlite_ext import SqliteExtDatabase

        self.test_db = SqliteExtDatabase(":memory:")
        self.db.db = self.test_db
        self.db.db.bind(self.db.MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(self.db.MODELS)

    def tearDown(self):
        self.test_db.drop_tables(self.db.MODELS)
        self.test_db.close()
        self.db.db = self.orig_db
        self.orig_db.bind(self.db.MODELS, bind_refs=False, bind_backrefs=False)

    def test_track_and_get_chat_members(self):
        self.db.create_or_update_user(101, "alice", "alice_lfm")
        self.db.create_or_update_user(102, "bob", "bob_lfm")
        self.db.create_or_update_user(103, "charlie", "")  # unlinked

        self.db.track_chat_member(-1001, 101, "alice", "Music Club", "supergroup")
        self.db.track_chat_member(-1001, 102, "bob", "Music Club", "supergroup")
        self.db.track_chat_member(-1001, 103, "charlie", "Music Club", "supergroup")

        linked = self.db.get_linked_chat_members(-1001)
        self.assertEqual(len(linked), 2)
        linked_ids = [u.telegram_id for u in linked]
        self.assertIn(101, linked_ids)
        self.assertIn(102, linked_ids)
        self.assertNotIn(103, linked_ids)

    def test_opt_out_toggle(self):
        self.db.create_or_update_user(201, "david", "david_lfm")
        self.db.track_chat_member(-1002, 201, "david", "Test Chat", "group")

        linked = self.db.get_linked_chat_members(-1002)
        self.assertEqual(len(linked), 1)

        # Toggle opt-out -> True
        new_status = self.db.toggle_user_group_opt_out(201)
        self.assertTrue(new_status)
        linked_after = self.db.get_linked_chat_members(-1002)
        self.assertEqual(len(linked_after), 0)

        # Toggle opt-out -> False
        new_status2 = self.db.toggle_user_group_opt_out(201)
        self.assertFalse(new_status2)
        linked_again = self.db.get_linked_chat_members(-1002)
        self.assertEqual(len(linked_again), 1)

    def test_upsert_crown_and_dethrone(self):
        u1 = self.db.create_or_update_user(301, "eva", "eva_lfm")
        u2 = self.db.create_or_update_user(302, "frank", "frank_lfm")

        # Initial crown
        crown1, prev1 = self.db.upsert_crown(
            -1003, "Radiohead", "https://last.fm/music/Radiohead", u1, 500
        )
        self.assertIsNone(prev1)
        self.assertEqual(crown1.playcount, 500)
        self.assertEqual(crown1.user.telegram_id, 301)

        # Dethrone by Frank
        crown2, prev2 = self.db.upsert_crown(
            -1003, "Radiohead", "https://last.fm/music/Radiohead", u2, 800
        )
        self.assertIsNotNone(prev2)
        self.assertEqual(prev2.user.telegram_id, 301)
        self.assertEqual(prev2.playcount, 500)
        self.assertEqual(crown2.user.telegram_id, 302)
        self.assertEqual(crown2.playcount, 800)

    def test_crowns_leaderboard_and_user_crowns(self):
        u1 = self.db.create_or_update_user(401, "grace", "grace_lfm")
        u2 = self.db.create_or_update_user(402, "hector", "hector_lfm")

        self.db.upsert_crown(-1004, "Artist A", "urlA", u1, 100)
        self.db.upsert_crown(-1004, "Artist B", "urlB", u1, 200)
        self.db.upsert_crown(-1004, "Artist C", "urlC", u2, 300)

        leaderboard = self.db.get_chat_crowns_leaderboard(-1004)
        self.assertEqual(len(leaderboard), 2)
        self.assertEqual(leaderboard[0]["user"].telegram_id, 401)
        self.assertEqual(leaderboard[0]["crown_count"], 2)
        self.assertEqual(leaderboard[1]["user"].telegram_id, 402)
        self.assertEqual(leaderboard[1]["crown_count"], 1)

        grace_crowns = self.db.get_user_crowns(-1004, 401)
        self.assertEqual(len(grace_crowns), 2)
        self.assertEqual(
            grace_crowns[0].artist_name, "Artist B"
        )  # higher playcount first

    def test_run_migrations_adds_missing_group_opt_out(self):
        # Simulate an old legacy database where 'user' table lacks group_opt_out column
        from playhouse.sqlite_ext import SqliteExtDatabase

        legacy_db = SqliteExtDatabase(":memory:")
        legacy_db.connect()
        legacy_db.execute_sql(
            "CREATE TABLE user ("
            "id INTEGER NOT NULL PRIMARY KEY,"
            "telegram_id BIGINT NOT NULL UNIQUE,"
            "telegram_username VARCHAR(255) NOT NULL,"
            "lastfm_username VARCHAR(255) NOT NULL"
            ")"
        )
        legacy_db.execute_sql(
            "INSERT INTO user (telegram_id, telegram_username, lastfm_username) "
            "VALUES (999, 'legacy_user', 'legacy_lfm')"
        )

        # Check column is initially absent
        cursor = legacy_db.execute_sql("PRAGMA table_info('user')")
        cols_before = {row[1] for row in cursor.fetchall()}
        self.assertNotIn("group_opt_out", cols_before)

        # Run migration on legacy_db
        self.db.run_migrations(legacy_db)

        # Check column is now added
        cursor = legacy_db.execute_sql("PRAGMA table_info('user')")
        cols_after = {row[1] for row in cursor.fetchall()}
        self.assertIn("group_opt_out", cols_after)

        # Verify Peewee query on migrated DB works without OperationalError
        self.db.User._meta.database = legacy_db
        try:
            users = list(self.db.User.select().where(self.db.User.telegram_id == 999))
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0].telegram_username, "legacy_user")
            self.assertFalse(users[0].group_opt_out)
        finally:
            self.db.User._meta.database = self.test_db
            legacy_db.close()


class TestGroupService(unittest.IsolatedAsyncioTestCase):
    async def test_get_whoknows_success(self):
        mock_lfm = MagicMock()
        mock_lfm.get_artist_canonical_info.return_value = (
            "Radiohead",
            "https://www.last.fm/music/Radiohead",
        )

        def mock_playcount(username, artist):
            if username == "alice_lfm":
                return 1500
            elif username == "bob_lfm":
                return 400
            return 0

        mock_lfm.get_user_artist_playcount.side_effect = mock_playcount

        from services import GroupService

        with (
            patch("services.db.get_linked_chat_members") as mock_members,
            patch("services.db.upsert_crown") as mock_upsert,
        ):
            u1 = MagicMock(
                telegram_id=1, telegram_username="alice", lastfm_username="alice_lfm"
            )
            u2 = MagicMock(
                telegram_id=2, telegram_username="bob", lastfm_username="bob_lfm"
            )
            mock_members.return_value = [u1, u2]
            mock_upsert.return_value = (MagicMock(), None)

            service = GroupService(mock_lfm)
            html_msg, success = await service.get_whoknows(
                -999, "Indie Chat", "radiohead"
            )

            self.assertTrue(success)
            self.assertIn("Radiohead", html_msg)
            self.assertIn("@alice", html_msg)
            self.assertIn("1,500", html_msg)
            self.assertIn("👑", html_msg)

    async def test_get_whoknows_artist_not_found(self):
        mock_lfm = MagicMock()
        mock_lfm.get_artist_canonical_info.return_value = None

        from services import GroupService

        service = GroupService(mock_lfm)
        html_msg, success = await service.get_whoknows(
            -999, "Chat", "NonExistentBand123"
        )

        self.assertFalse(success)
        self.assertIn("Could not find artist", html_msg)

    async def test_get_whoknows_no_listeners(self):
        mock_lfm = MagicMock()
        mock_lfm.get_artist_canonical_info.return_value = (
            "Obscure Band",
            "https://url",
        )
        mock_lfm.get_user_artist_playcount.return_value = 0

        from services import GroupService

        with patch("services.db.get_linked_chat_members") as mock_members:
            u1 = MagicMock(
                telegram_id=1, telegram_username="alice", lastfm_username="alice_lfm"
            )
            mock_members.return_value = [u1]

            service = GroupService(mock_lfm)
            html_msg, success = await service.get_whoknows(-999, "Chat", "Obscure Band")

            self.assertTrue(success)
            self.assertIn("Nobody in", html_msg)
            self.assertIn("Obscure Band", html_msg)


class TestWhoknowsAndCrownsCommands(unittest.IsolatedAsyncioTestCase):
    @patch("commands.db.log_command")
    async def test_whoknows_command_with_explicit_arg(self, mock_log_cmd):
        mock_update = MagicMock(spec=Update)
        mock_msg = MagicMock()
        mock_msg.reply_text = AsyncMock()
        mock_update.effective_message = mock_msg
        mock_update.effective_chat = MagicMock(id=-555, title="Cool Group")
        mock_update.effective_user = MagicMock(id=10, username="tester")

        mock_context = MagicMock()
        mock_context.args = ["Fontaines", "D.C."]
        mock_group_svc = MagicMock()
        mock_group_svc.get_whoknows = AsyncMock(return_value=("👑 Ranking HTML", True))
        mock_context.bot_data = {
            "group_service": mock_group_svc,
            "lastfm_service": MagicMock(),
        }
        mock_context.bot.send_chat_action = AsyncMock()

        await commands.whoknows(mock_update, mock_context)
        mock_group_svc.get_whoknows.assert_awaited_once_with(
            -555, "Cool Group", "Fontaines D.C."
        )
        mock_msg.reply_text.assert_awaited_once_with("👑 Ranking HTML")

    @patch("commands.db.log_command")
    async def test_crowns_command_hall_of_fame(self, mock_log_cmd):
        mock_update = MagicMock(spec=Update)
        mock_msg = MagicMock()
        mock_msg.text = "/crowns"
        mock_msg.reply_text = AsyncMock()
        mock_update.effective_message = mock_msg
        mock_update.effective_chat = MagicMock(id=-555, title="Cool Group")
        mock_update.effective_user = MagicMock(id=10, username="tester")

        mock_context = MagicMock()
        mock_context.args = []
        mock_group_svc = MagicMock()
        mock_group_svc.get_crowns_hall_of_fame = AsyncMock(
            return_value="🏆 Hall of Fame HTML"
        )
        mock_context.bot_data = {"group_service": mock_group_svc}

        await commands.crowns(mock_update, mock_context)
        mock_group_svc.get_crowns_hall_of_fame.assert_awaited_once_with(
            -555, "Cool Group"
        )
        mock_msg.reply_text.assert_awaited_once_with("🏆 Hall of Fame HTML")


if __name__ == "__main__":
    unittest.main()
