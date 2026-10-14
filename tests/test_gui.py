from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from PIL import Image

try:
    import tkinter as tk
except ImportError:
    tk = None


class GuiTest(unittest.TestCase):
    def setUp(self):
        if tk is None:
            self.skipTest("Tkinter is not installed")
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("No graphical display available")
        self.root.withdraw()
        from ak820linux.gui import StudioApp

        self.app = StudioApp(self.root)
        self.addCleanup(self.close)
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.gif = Path(self.directory.name) / "preview.gif"
        frames = [Image.new("RGB", (16, 16), color) for color in ("red", "blue")]
        frames[0].save(
            self.gif,
            save_all=True,
            append_images=frames[1:],
            duration=[100, 200],
            loop=0,
        )

    def close(self):
        self.app.busy = False
        self.app.close()

    def wait_for_task(self):
        deadline = time.monotonic() + 5
        while self.app.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)
        self.assertFalse(self.app.busy, "Background task did not finish")
        self.root.update()
        self.assertEqual(self.errors, [])

    def test_upload_requires_prepared_content(self):
        self.assertTrue(self.app.upload_button.instate(["disabled"]))
        self.app.use_text()
        self.assertFalse(self.app.upload_button.instate(["disabled"]))
        self.assertIsNone(self.app.content.delays)

    def test_image_settings_must_be_applied_before_upload(self):
        self.app._load_image(self.gif)
        self.wait_for_task()
        self.assertTrue(self.app.player.playing)
        self.app.brightness.set("0")
        self.assertTrue(self.app.dirty)
        self.assertTrue(self.app.upload_button.instate(["disabled"]))
        self.app.apply_image()
        self.wait_for_task()
        self.assertFalse(self.app.dirty)
        self.assertTrue(
            all(frame.getbbox() is None for frame in self.app.content.previews)
        )
        self.assertFalse(self.app.upload_button.instate(["disabled"]))

    def test_text_edits_invalidate_upload_and_stop_animation(self):
        self.app._load_image(self.gif)
        self.wait_for_task()
        self.app.use_text()
        self.assertFalse(self.app.player.playing)
        self.assertIsNone(self.app.player.timer)
        self.app.message.insert("end", "!")
        self.root.update()
        self.assertTrue(self.app.dirty)
        self.assertTrue(self.app.upload_button.instate(["disabled"]))
        self.app.use_text()
        self.assertFalse(self.app.dirty)

    def test_failed_load_preserves_current_content(self):
        self.app.use_text()
        previous = self.app.content
        with patch("ak820linux.gui.messagebox.showerror") as error:
            self.app._load_image(Path(self.directory.name) / "missing.png")
            self.wait_for_task()
            error.assert_called_once()
        self.assertIs(self.app.content, previous)
        self.assertFalse(self.app.upload_button.instate(["disabled"]))

    def test_applying_text_consumes_pending_edit_events(self):
        self.app.use_text()
        self.app.message.insert("end", " updated")
        self.app.use_text()
        self.root.update()
        self.assertFalse(self.app.dirty)
        self.assertFalse(self.app.upload_button.instate(["disabled"]))

    def test_preview_details_and_actions_fit_small_window(self):
        self.app.use_text()
        self.root.geometry("840x660")
        self.root.deiconify()
        self.root.update()
        for widget in (
            self.app.upload_button,
            self.app.detail_label,
            self.app.apply_button,
        ):
            with self.subTest(widget=widget):
                self.assertTrue(widget.winfo_ismapped())
                self.assertLessEqual(
                    widget.winfo_rooty() + widget.winfo_height(),
                    self.root.winfo_rooty() + self.root.winfo_height(),
                )
        self.assertGreater(self.app.preview.winfo_height(), 64)

    def test_upload_uses_prepared_frames_and_restores_controls(self):
        self.app._load_image(self.gif)
        self.wait_for_task()
        with (
            patch("ak820linux.gui.find_device"),
            patch("ak820linux.gui.Keyboard") as keyboard,
        ):
            device = keyboard.return_value.__enter__.return_value
            device.upload.side_effect = lambda frames, delays, progress: progress(1, 1)
            self.app.upload()
            self.assertTrue(self.app.busy)
            self.assertTrue(self.app.upload_button.instate(["disabled"]))
            self.wait_for_task()
            self.assertEqual(
                device.upload.call_args.args[:2],
                (self.app.content.frames, self.app.content.delays),
            )
        self.assertEqual(self.app.progress.get(), 100)
        self.assertFalse(self.app.upload_button.instate(["disabled"]))
        for control, state in self.app.controls:
            if state == "readonly":
                self.assertTrue(control.instate(["readonly"]))


if __name__ == "__main__":
    unittest.main()
