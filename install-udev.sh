#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
echo 'Installing seat-aware permission rules for AJAZZ 0c45:8009 and 0c45:800a.'
# uaccess must be tagged before systemd's 73-seat-late.rules runs.
sudo install -m 0644 70-ak820-linux.rules /etc/udev/rules.d/70-ak820-linux.rules
# Remove the previous incorrectly ordered rule if it was installed.
sudo rm -f /etc/udev/rules.d/99-ak820-linux.rules
sudo udevadm control --reload-rules
printf 'Installed. Unplug/reconnect the keyboard, then run python -m ak820linux probe.\n'
