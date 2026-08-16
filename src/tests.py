import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image

from callbacks import Action, Callback, Entity, Period
from services import CollageService, ViewService, parse_collage_args


class TestCollageArgParser(unittest.TestCase):
    def test_default_args(self):
        entity, cols, rows, period = parse_collage_args([])
        self.assertEqual(entity, "album")
        self.assertEqual(cols, 3)
        self.assertEqual(rows, 3)
        self.assertEqual(period, "7day")

    def test_custom_dimensions(self):
        entity, cols, rows, period = parse_collage_args(["5x5"])
        self.assertEqual(cols, 5)
        self.assertEqual(rows, 5)

        entity, cols, rows, period = parse_collage_args(["3x5"])
        self.assertEqual(cols, 3)
        self.assertEqual(rows, 5)

        entity, cols, rows, period = parse_collage_args(["4"])
        self.assertEqual(cols, 4)
        self.assertEqual(rows, 4)

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
        entity, cols, rows, period = parse_collage_args(["overall", "artist", "5x5"])
        self.assertEqual(entity, "artist")
        self.assertEqual(cols, 5)
        self.assertEqual(rows, 5)
        self.assertEqual(period, "overall")

    def test_invalid_dimension_raises(self):
        with self.assertRaises(ValueError):
            parse_collage_args(["6x6"])
        with self.assertRaises(ValueError):
            parse_collage_args(["0x0"])
        with self.assertRaises(ValueError):
            parse_collage_args(["10"])

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
            size="3x3",
        )
        encoded = cb.encode()
        self.assertLessEqual(len(encoded.encode("utf-8")), 64)

        decoded = Callback.decode(encoded)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.action, Action.COLLAGE)
        self.assertEqual(decoded.owner_id, 987654321)
        self.assertEqual(decoded.entity, Entity.ARTIST)
        self.assertEqual(decoded.period, Period.WEEK)
        self.assertEqual(decoded.size, "3x3")

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
            username="testuser", entity="album", cols=1, rows=1, period="7day"
        )

        self.assertIsInstance(bio, BytesIO)
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

        # Step 3: Entity and size chosen, no period
        msg, kb = await view_service.build_collage_selection_response(
            telegram_user_id=123, entity=Entity.ALBUM, size="3x3"
        )
        self.assertIn("period", msg.lower())
        self.assertIsNotNone(kb)


if __name__ == "__main__":
    unittest.main()
