from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageChops, UnidentifiedImageError

from ak820linux.images import convert_size, from_path, prepare_image, rgb565, text_card
from ak820linux.protocol import FRAME_BYTES, image_header


class ImageTest(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.photo = Path(self.directory.name) / "photo.png"
        Image.new("RGB", (80, 40), (100, 60, 20)).save(self.photo)
        self.gif = Path(self.directory.name) / "motion.gif"
        frames = [
            Image.new("RGB", (16, 16), color) for color in ("red", "green", "blue")
        ]
        frames[0].save(
            self.gif,
            save_all=True,
            append_images=frames[1:],
            duration=[100, 200, 300],
            loop=0,
        )

    def test_contain_preserves_shape_with_black_bars(self):
        result = convert_size(Image.new("RGB", (80, 40), "red"), "contain")
        self.assertEqual(result.size, (128, 128))
        self.assertEqual(result.getpixel((64, 0)), (0, 0, 0))
        self.assertEqual(result.getpixel((64, 64)), (255, 0, 0))

    def test_rotation_is_clockwise(self):
        source = Image.new("RGB", (128, 128), "blue")
        source.paste("red", (0, 0, 64, 128))
        result = convert_size(source, rotation=90)
        self.assertEqual(result.getpixel((64, 20)), (255, 0, 0))
        self.assertEqual(result.getpixel((64, 100)), (0, 0, 255))

    def test_exif_orientation_is_applied(self):
        source = Image.new("RGB", (128, 128), "blue")
        source.paste("red", (0, 0, 64, 128))
        source.getexif()[274] = 6
        result = convert_size(source)
        self.assertEqual(result.getpixel((64, 20)), (255, 0, 0))
        self.assertEqual(result.getpixel((64, 100)), (0, 0, 255))

    def test_brightness_and_transparency(self):
        source = Image.new("RGBA", (128, 128), (100, 60, 20, 255))
        self.assertEqual(
            convert_size(source, brightness=0.5).getpixel((0, 0)), (50, 30, 10)
        )
        self.assertEqual(convert_size(source, brightness=0).getbbox(), None)
        source.putalpha(0)
        self.assertEqual(convert_size(source).getbbox(), None)

    def test_static_image_and_compatibility_wrapper(self):
        prepared = prepare_image(self.photo)
        self.assertEqual(len(prepared.frames), 1)
        self.assertEqual(len(prepared.frames[0]), FRAME_BYTES)
        self.assertIsNone(prepared.delays)
        self.assertFalse(prepared.truncated)
        frames, delays, preview = from_path(self.photo)
        self.assertEqual(frames, prepared.frames)
        self.assertIsNone(delays)
        self.assertEqual(preview.tobytes(), prepared.previews[0].tobytes())

    def test_gif_previews_match_uploaded_frames(self):
        prepared = prepare_image(self.gif, speed=2)
        self.assertEqual(prepared.delays, [50, 100, 150])
        self.assertEqual(len(prepared.previews), 3)
        self.assertEqual(
            prepared.frames, [rgb565(frame) for frame in prepared.previews]
        )
        self.assertEqual(prepared.previews[0].getpixel((0, 0)), (255, 0, 0))
        self.assertEqual(prepared.previews[2].getpixel((0, 0)), (0, 0, 255))
        self.assertEqual(list(image_header(prepared.delays)[1:4]), [25, 50, 75])

    def test_settings_apply_to_every_gif_frame(self):
        prepared = prepare_image(self.gif, brightness=0, rotation=180)
        self.assertEqual(prepared.frames, [bytes(FRAME_BYTES)] * 3)
        self.assertTrue(all(frame.getbbox() is None for frame in prepared.previews))

    def test_frame_limit_reports_truncation(self):
        prepared = prepare_image(self.gif, max_frames=2)
        self.assertEqual(len(prepared.frames), 2)
        self.assertEqual(prepared.delays, [100, 200])
        self.assertTrue(prepared.truncated)
        self.assertFalse(prepare_image(self.gif, max_frames=3).truncated)

    def test_one_frame_limit_produces_static_content(self):
        prepared = prepare_image(self.gif, max_frames=1)
        self.assertEqual(len(prepared.previews), 1)
        self.assertIsNone(prepared.delays)
        self.assertTrue(prepared.truncated)

    def test_preview_timing_matches_keyboard_limits(self):
        prepared = prepare_image(self.gif, speed=0.25)
        self.assertEqual(prepared.delays, [400, 510, 510])
        self.assertTrue(prepared.timing_limited)
        header = image_header(prepared.delays)
        self.assertEqual([value * 2 for value in header[1:4]], prepared.delays)

    def test_invalid_options(self):
        for options in [
            {"max_frames": 0},
            {"max_frames": 256},
            {"max_frames": 1.5},
            {"rotation": 45},
            {"fit": "bad"},
            {"brightness": -1},
            {"brightness": 3},
            {"brightness": float("nan")},
            {"speed": 0},
            {"speed": 5},
            {"speed": float("inf")},
        ]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                prepare_image(self.photo, **options)

    def test_corrupt_image_is_rejected(self):
        self.photo.write_bytes(b"not an image")
        with self.assertRaises(UnidentifiedImageError):
            prepare_image(self.photo)

    def test_text_colors_and_alignment(self):
        boxes = []
        for alignment in ("left", "center", "right"):
            image = text_card(
                "Hi", fg="#ff0000", bg="#123456", font_size=24, alignment=alignment
            )
            self.assertEqual(image.getpixel((0, 0)), (18, 52, 86))
            boxes.append(
                ImageChops.difference(
                    image, Image.new("RGB", image.size, "#123456")
                ).getbbox()
            )
        self.assertLess(boxes[0][0], boxes[1][0])
        self.assertLess(boxes[1][0], boxes[2][0])

    def test_long_words_stay_inside_screen_at_every_font_size(self):
        for size in (8, 16, 24, 32):
            with self.subTest(size=size):
                image = text_card(
                    "Supercalifragilisticexpialidocious " * 10,
                    bg="black",
                    font_size=size,
                )
                left, top, right, bottom = image.getbbox()
                self.assertGreaterEqual(left, 5)
                self.assertGreaterEqual(top, 5)
                self.assertLessEqual(right, 123)
                self.assertLessEqual(bottom, 123)

    def test_explicit_line_breaks_are_preserved(self):
        multiline = text_card("Hello\nLinux")
        single_line = text_card("Hello Linux")
        self.assertNotEqual(multiline.tobytes(), single_line.tobytes())

    def test_text_validation(self):
        for options in [
            {"font_size": 0},
            {"font_size": 33},
            {"alignment": "bad"},
            {"fg": "not-a-color"},
        ]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                text_card("Hello", **options)


if __name__ == "__main__":
    unittest.main()
