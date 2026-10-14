# AK820 Linux Studio — preview release

A small native **Linux** Python/Tkinter utility for the stock **AJAZZ AK820 Pro** 128×128 TFT keyboard, based on publicly reverse-engineered USB HID packet formats. It does **not** install a Windows driver, flash firmware, or communicate with a remote server.

**Hardware testing status:** packet serialization and image encoding are unit-tested, but this build has **not** been tested against the requester's physical keyboard. Models with another VID/PID, usage page, or firmware may need modifications. Only use standard clock and image functions; a bad transfer may fail or alter stored screen content. Do not use the advanced firmware-modding projects to solve a display issue.

## Supported and unsupported

- Supported target: USB `0c45:8009` or `0c45:800a`, vendor HID usage pages `0xFF13` (control) and `0xFF68` (screen data).
- Implemented: read-only `probe`, preview and upload PNG/JPEG/BMP/WebP, animated GIF playback, image rotation and brightness, configurable text cards, and clock sync to Linux time.
- Not implemented: keyboard key-remapping, firmware flashing, RGB configuration, wireless transfer, `0xFF67` / newer variant protocol, live system-monitor screen, autosync service.
- Requires keyboard in **wired USB mode** and a **USB data cable**. 2.4 GHz and Bluetooth do not expose the required vendor endpoints.

## Installation (Pop!_OS 24.04 / Ubuntu)

Requires Linux, Python 3.10 or newer, Tkinter for the GUI, and Pillow (installed by `setup.sh`).

1. Clone the repository or extract the ZIP into a permanent folder, such as `~/Applications/ajazz-ak820-linux`.
2. Open a terminal in that directory. Install the Ubuntu packages:

   ```bash
   sudo apt update
   sudo apt install python3 python3-venv python3-tk
   ```
3. Install Python Pillow in a private venv and launch:

   ```bash
   ./setup.sh
   ./run.sh
   ```
4. Select *Detect USB* first. Then choose your image or GIF, preview it, and click *Upload screen*.
5. If the app reports `Permission denied`, install the optional udev rule and reconnect the keyboard:

   ```bash
   ./install-udev.sh
   ```

If you want a menu launcher, run `./install-desktop.sh` **after** moving the folder into its permanent location. This uses the system's standard keyboard icon.

## Screen editor

- **Image / GIF:** choose a file, select cover/contain/stretch, rotate clockwise, and adjust image brightness from 0–200%. Photo EXIF orientation is applied automatically.
- **Animated preview:** GIFs play in the preview with pause/resume, a frame counter, and the loop duration. Choose a speed from 0.25× to 4× and a frame limit from 1 to 255 (default 60). A one-frame limit creates a static screen.
- **Text:** write multiple lines, select font size and alignment, and choose text and background colors. Long words wrap; messages too tall for the screen end with an ellipsis.

Click **Apply changes** for image settings or **Use this text** for text settings. Upload is enabled only after the preview reflects the current settings. Preparing content and previewing animations do not send anything to the keyboard; click **Upload screen** when ready.

The preview reports when a GIF exceeds the selected frame limit. Its playback uses the same frame delays as the upload, including the keyboard protocol's 2–510 ms range. Slow animations may have long pauses shortened; the editor reports this when it happens. Brightness adjusts the image pixels, not the keyboard's backlight.

## Terminal commands

```bash
./run.sh probe
./run.sh clock
./run.sh upload ~/Pictures/photo.png
./run.sh upload ~/Pictures/photo.png --rotate 90 --brightness 1.2
./run.sh upload ~/Pictures/motion.gif --max-frames 40 --fit contain
./run.sh upload ~/Pictures/motion.gif --speed 2
./run.sh gui
```

`--rotate` accepts 0, 90, 180, or 270 degrees clockwise. CLI brightness uses a multiplier from 0 to 2 (1 is unchanged); `--speed` accepts 0.25 to 4. These settings use the same image preparation as the GUI.

`probe` is entirely read-only. `clock` and `upload` send the known USB HID commands; `gui` opens the editor and waits for an explicit action. No sudo is required after granting local-seat `udev` permission.

## Diagnostics

```bash
lsusb | grep -iE '0c45|ajazz|sonix|microdia'
./run.sh probe
ls -l /dev/hidraw*
```

If `lsusb` lists a different VID:PID or `probe` shows a missing usage page, **do not spoof the ID or force uploads**. Send the command output to the developer so the interface and framing can be checked against the device's variant.

## Development and tests

From the repository root, create the environment with `./setup.sh`, then run:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m black --check .
.venv/bin/python -m unittest discover -s tests -v
./run.sh --help
for script in ./*.sh; do
  bash -n "$script"
done
```

For a headless development environment, Tkinter is not needed for the tests:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m black --check .
.venv/bin/python -m unittest discover -s tests -v
```

Format Python files with `.venv/bin/python -m black .` before committing. Black is pinned in `requirements-dev.txt`, with shared formatting settings in `pyproject.toml`.

The tests generate their own images and temporary GIFs. They cover image transformations, GIF timing and truncation, text layout, preview playback, CLI options, and packet serialization. No keyboard is required; device access in CLI and GUI tests is mocked. GUI tests run when Tkinter and a graphical display are available and otherwise skip. GitHub Actions checks Black formatting and runs the tests, CLI startup, and shell checks on Linux with Python 3.10, 3.12, and 3.14. Physical keyboard compatibility still requires manual testing.

The source lives in `ak820linux/`, automated tests in `tests/`, and setup helpers in the repository root. Local virtual environments, caches, editor settings, credentials, and personal test images are ignored by Git. Keep manual upload images in `local-media/`; shared automated image fixtures can go in `tests/fixtures/` and remain trackable. No sample photos or GIFs are required to run the app or tests.

## Permission fix in 0.1.1

The `uaccess` rule is now named `70-ak820-linux.rules` (previously `99-...`), so it is evaluated before the systemd `73-seat-late.rules` access-control pass. The installer removes the obsolete `99-...` rule. After installation unplug/replug the keyboard; verify using `ls -l /dev/hidraw*` and `python -m ak820linux probe`. Avoid running the GUI with sudo.

## License

[MIT License](LICENSE).
