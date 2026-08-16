import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure src is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image
from telegram import Chat as TgChat, Update, User as TgUser

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
        self.assertEqual(parse_collage_args(["fallback:black"]).fallback_style, "black")
        self.assertEqual(
            parse_collage_args(["fallback:gradient"]).fallback_style, "gradient"
        )
        with self.assertRaises(ValueError):
            parse_collage_args(["fallback:bogus"])

    def test_mixed_order_arguments(self):
        opts = parse_collage_args(
            ["overall", "artist", "10x10", "150px", "theme:neon", "overlay:pill"]
        )
        self.assertEqual(opts.entity, "artist")
        self.assertEqual(opts.cols, 10)
        self.assertEqual(opts.rows, 10)
        self.assertEqual(opts.period, "overall")
        self.assertEqual(opts.tile_size, 150)
        self.assertEqual(opts.theme, "neon")
        self.assertEqual(opts.overlay_style, "pill")

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

        # Mock generate() returning a real in-memory PIL image
        test_image = Image.new("RGB", (300, 300), color=(255, 0, 0))
        mock_gen_instance.generate.return_value = test_image

        service = CollageService(api_key="dummy_key", api_secret="dummy_secret")
        options = CollageOptions(
            entity="album",
            cols=10,
            rows=10,
            period="7day",
            tile_size=150,
            theme="neon",
            overlay_style="pill",
            preset="instagram-post",
            corner_radius=12,
            border_width=3,
            border_color="#FF5A5F",
            spacing=8,
            fallback_style="black",
        )
        bio = await service.generate_collage_image(username="testuser", options=options)

        self.assertIsInstance(bio, BytesIO)
        mock_gen_instance.generate.assert_called_once_with(
            entity="album",
            username="testuser",
            cols=10,
            rows=10,
            period="7day",
            tile_size=150,
            cache_dir=service._cache_dir,
            theme="neon",
            overlay_style="pill",
            preset="instagram-post",
            corner_radius=12,
            border_width=3,
            border_color="#FF5A5F",
            spacing=8,
            fallback_style="black",
        )
        # Verify it's a valid PNG image stream
        loaded_img = Image.open(bio)
        self.assertEqual(loaded_img.size, (300, 300))

    @patch("services.CollageGenerator")
    async def test_generate_collage_image_defaults_omit_style_kwargs(
        self, mock_generator_cls
    ):
        mock_gen_instance = MagicMock()
        mock_generator_cls.return_value = mock_gen_instance
        test_image = Image.new("RGB", (300, 300), color=(255, 0, 0))
        mock_gen_instance.generate.return_value = test_image

        service = CollageService(api_key="dummy_key", api_secret="dummy_secret")
        options = CollageOptions(entity="album", cols=3, rows=3, period="7day")
        await service.generate_collage_image(username="testuser", options=options)

        mock_gen_instance.generate.assert_called_once_with(
            entity="album",
            username="testuser",
            cols=3,
            rows=3,
            period="7day",
            tile_size=None,
            cache_dir=service._cache_dir,
        )


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
        )
        self.assertIn("neon, pill, sense text", caption)

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


if __name__ == "__main__":
    unittest.main()
