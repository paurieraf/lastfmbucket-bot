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
from services import CollageService, ViewService, parse_collage_args


class TestCollageArgParser(unittest.TestCase):
    def test_default_args(self):
        entity, cols, rows, period, tile_size = parse_collage_args([])
        self.assertEqual(entity, "album")
        self.assertEqual(cols, 3)
        self.assertEqual(rows, 3)
        self.assertEqual(period, "7day")
        self.assertIsNone(tile_size)

    def test_custom_dimensions(self):
        entity, cols, rows, period, tile_size = parse_collage_args(["5x5"])
        self.assertEqual(cols, 5)
        self.assertEqual(rows, 5)

        entity, cols, rows, period, tile_size = parse_collage_args(["3x5"])
        self.assertEqual(cols, 3)
        self.assertEqual(rows, 5)

        entity, cols, rows, period, tile_size = parse_collage_args(["4"])
        self.assertEqual(cols, 4)
        self.assertEqual(rows, 4)

        entity, cols, rows, period, tile_size = parse_collage_args(["10x10"])
        self.assertEqual(cols, 10)
        self.assertEqual(rows, 10)

        entity, cols, rows, period, tile_size = parse_collage_args(["10x5"])
        self.assertEqual(cols, 10)
        self.assertEqual(rows, 5)

        entity, cols, rows, period, tile_size = parse_collage_args(["20x20"])
        self.assertEqual(cols, 20)
        self.assertEqual(rows, 20)

    def test_tile_size_parsing(self):
        entity, cols, rows, period, tile_size = parse_collage_args(["150px"])
        self.assertEqual(tile_size, 150)

        entity, cols, rows, period, tile_size = parse_collage_args(["ts:200"])
        self.assertEqual(tile_size, 200)

        entity, cols, rows, period, tile_size = parse_collage_args(["size=100"])
        self.assertEqual(tile_size, 100)

        entity, cols, rows, period, tile_size = parse_collage_args(["tile_size:300"])
        self.assertEqual(tile_size, 300)

    def test_invalid_tile_size_raises(self):
        with self.assertRaises(ValueError):
            parse_collage_args(["40px"])
        with self.assertRaises(ValueError):
            parse_collage_args(["700px"])
        with self.assertRaises(ValueError):
            parse_collage_args(["ts:10"])

    def test_custom_entities(self):
        self.assertEqual(parse_collage_args(["artists"])[0], "artist")
        self.assertEqual(parse_collage_args(["album"])[0], "album")
        self.assertEqual(parse_collage_args(["tracks"])[0], "track")
        self.assertEqual(parse_collage_args(["songs"])[0], "track")

    def test_custom_periods(self):
        self.assertEqual(parse_collage_args(["week"])[3], "7day")
        self.assertEqual(parse_collage_args(["1month"])[3], "1month")
        self.assertEqual(parse_collage_args(["3m"])[3], "3month")
        self.assertEqual(parse_collage_args(["6m"])[3], "6month")
        self.assertEqual(parse_collage_args(["year"])[3], "12month")
        self.assertEqual(parse_collage_args(["overall"])[3], "overall")

    def test_mixed_order_arguments(self):
        entity, cols, rows, period, tile_size = parse_collage_args(
            ["overall", "artist", "10x10", "150px"]
        )
        self.assertEqual(entity, "artist")
        self.assertEqual(cols, 10)
        self.assertEqual(rows, 10)
        self.assertEqual(period, "overall")
        self.assertEqual(tile_size, 150)

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

    def test_collage_conversion_helpers(self):
        cb = Callback(
            action=Action.COLLAGE, owner_id=123, entity=Entity.TRACK, period=Period.YEAR
        )
        self.assertEqual(cb.to_collage_entity_str(), "track")
        self.assertEqual(cb.to_collage_period_str(), "12month")


class TestCollageService(unittest.IsolatedAsyncioTestCase):
    @patch("services.CollageGenerator")
    async def test_generate_collage_image(self, mock_generator_cls):
        mock_gen_instance = MagicMock()
        mock_generator_cls.return_value = mock_gen_instance

        # Mock generate() returning a real in-memory PIL image
        test_image = Image.new("RGB", (300, 300), color=(255, 0, 0))
        mock_gen_instance.generate.return_value = test_image

        service = CollageService(api_key="dummy_key", api_secret="dummy_secret")
        bio = await service.generate_collage_image(
            username="testuser",
            entity="album",
            cols=10,
            rows=10,
            period="7day",
            tile_size=150,
        )

        self.assertIsInstance(bio, BytesIO)
        mock_gen_instance.generate.assert_called_once_with(
            entity="album",
            username="testuser",
            cols=10,
            rows=10,
            period="7day",
            tile_size=150,
        )
        # Verify it's a valid PNG image stream
        loaded_img = Image.open(bio)
        self.assertEqual(loaded_img.size, (300, 300))


class TestViewServiceCollage(unittest.IsolatedAsyncioTestCase):
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

        # Step 2: Entity chosen, no size
        msg, kb = await view_service.build_collage_selection_response(
            telegram_user_id=123, entity=Entity.ALBUM
        )
        self.assertIn("size", msg.lower())
        self.assertIsNotNone(kb)
        # Verify 2 rows of sizes
        self.assertEqual(len(kb.inline_keyboard), 2)
        self.assertEqual(len(kb.inline_keyboard[0]), 3)
        self.assertEqual(len(kb.inline_keyboard[1]), 3)

        # Step 3: Entity and size chosen, no period
        msg, kb = await view_service.build_collage_selection_response(
            telegram_user_id=123, entity=Entity.ALBUM, size="10x10"
        )
        self.assertIn("period", msg.lower())
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

        with patch("bot.config.SENTRY_DSN", "https://key@sentry.io/123"), patch(
            "bot.sentry_sdk.capture_exception"
        ) as mock_sentry:
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
