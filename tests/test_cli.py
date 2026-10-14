from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

from ak820linux.__main__ import do_upload, main
from ak820linux.images import prepare_image


class CliTest(unittest.TestCase):
    def test_new_upload_options_reach_conversion(self):
        with (
            patch(
                "sys.argv",
                [
                    "ak820linux",
                    "upload",
                    "photo.png",
                    "--rotate",
                    "90",
                    "--brightness",
                    "0.5",
                    "--speed",
                    "2",
                ],
            ),
            patch("ak820linux.__main__.do_upload") as upload,
        ):
            self.assertEqual(main(), 0)
            upload.assert_called_once_with(
                "photo.png", "cover", 60, rotation=90, brightness=0.5, speed=2.0
            )

    def test_invalid_settings_never_open_device(self):
        with (
            patch("sys.argv", ["ak820linux", "upload", "photo.png", "--speed", "0"]),
            patch("ak820linux.__main__.find_device") as find_device,
            redirect_stderr(StringIO()),
        ):
            self.assertEqual(main(), 1)
            find_device.assert_not_called()

    def test_upload_receives_transformed_content(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "photo.png"
            Image.new("RGB", (40, 20), "red").save(path)
            expected = prepare_image(path, rotation=90, brightness=0.5)
            with (
                patch("ak820linux.__main__.find_device"),
                patch("ak820linux.__main__.Keyboard") as keyboard,
                redirect_stdout(StringIO()),
            ):
                do_upload(path, rotation=90, brightness=0.5)
                args = (
                    keyboard.return_value.__enter__.return_value.upload.call_args.args
                )
                self.assertEqual(args[0], expected.frames)
                self.assertIsNone(args[1])


if __name__ == "__main__":
    unittest.main()
