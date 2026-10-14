#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/ajazz-ak820-linux.desktop" <<EOL
[Desktop Entry]
Type=Application
Name=AK820 Linux Studio
Comment=Custom AJAZZ AK820 Pro screen and clock
Exec=$root/run.sh
Icon=input-keyboard
Terminal=false
Categories=Utility;Settings;
EOL
echo 'Desktop launcher installed for this directory. Keep the extracted folder in this location.'
