# AK820 Linux Studio — preview release

A small native **Linux** Python/Tkinter utility for the stock **AJAZZ AK820 Pro** 128×128 TFT keyboard, based on publicly reverse-engineered USB HID packet formats. It does **not** install a Windows driver, flash firmware, or communicate with a remote server.

**Hardware testing status:** packet serialization and image encoding are unit-tested, but this build has **not** been tested against the requester's physical keyboard. Models with another VID/PID, usage page, or firmware may need modifications. Only use standard clock and image functions; a bad transfer may fail or alter stored screen content. Do not use the advanced firmware-modding projects to solve a display issue.

## Supported and unsupported

- Supported target: USB `0c45:8009` or `0c45:800a`, vendor HID usage pages `0xFF13` (control) and `0xFF68` (screen data).
- Implemented: read-only `probe`, select preview+upload PNG/JPEG/BMP/WebP, animated GIF (up to 60 frames by default, configurable in CLI), generate a simple text graphic, sync clock to Linux time.
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

## Terminal commands

```bash
./run.sh probe
./run.sh clock
./run.sh upload ~/Pictures/photo.png
./run.sh upload ~/Pictures/motion.gif --max-frames 40 --fit contain
./run.sh gui
```

`probe` is entirely read-only. Every other command writes only the known USB HID commands. No sudo is required after granting local-seat `udev` permission.

## Diagnostics

```bash
lsusb | grep -iE '0c45|ajazz|sonix|microdia'
./run.sh probe
ls -l /dev/hidraw*
```

If `lsusb` lists a different VID:PID or `probe` shows a missing usage page, **do not spoof the ID or force uploads**. Send the command output to the developer so the interface and framing can be checked against the device's variant.

If the protocol does not work, try an existing Chromium WebHID implementation first: <https://kabelklaus.github.io/ajazz-ak820-pro/>. The browser implementation includes alternate framing options and supports known board variations.

## Credits and protocol references

Original independent implementation, based on protocol details from:

- https://github.com/Beattrey/ajazz-ak820-config (MIT) — byte-level description for AK820 Pro.
- https://github.com/aar-rafi/aks075-linux (MIT) — 256-byte GIF header, `hidraw` zero-byte quirk, RGB565, ACK sequence for related hardware.
- https://github.com/gohv/EPOMAKER-Ajazz-AK820-Pro (MIT) — AK820 Pro control report and clock reference.
- https://github.com/kabelklaus/ajazz-ak820-pro (MIT) — browser-based alternative with two image framing variants.

The open-source notes disagree on some transfer details, so this tool uses the Windows-capture-based AKS075 image framing with the AK820-compatible VID/PID+usage-page selection. It may not support every AK820 Pro production revision.

MIT License; see `LICENSE`.

## Development and tests

From the repository root, create the environment with `./setup.sh`, then run:

```bash
.venv/bin/python -m unittest discover -s tests -v
./run.sh --help
for script in ./*.sh; do
  bash -n "$script"
done
```

For a headless development environment, Tkinter is not needed for the tests:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

The tests generate their image data in memory and do not require a keyboard or send USB commands. GitHub Actions runs the tests, CLI startup, and shell checks on Linux with Python 3.10, 3.12, and 3.14. Physical keyboard compatibility still requires manual testing.

The source lives in `ak820linux/`, automated tests in `tests/`, and setup helpers in the repository root. Local virtual environments, caches, editor settings, credentials, and personal test images are ignored by Git. Keep manual upload images in `local-media/`; shared automated image fixtures can go in `tests/fixtures/` and remain trackable. No sample photos or GIFs are required to run the app or tests.

## Permission fix in 0.1.1

The `uaccess` rule is now named `70-ak820-linux.rules` (previously `99-...`), so it is evaluated before the systemd `73-seat-late.rules` access-control pass. The installer removes the obsolete `99-...` rule. After installation unplug/replug the keyboard; verify using `ls -l /dev/hidraw*` and `python -m ak820linux probe`. Avoid running the GUI with sudo.
