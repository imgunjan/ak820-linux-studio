#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
for cmd in python3; do command -v "$cmd" >/dev/null || { echo 'Python 3 required'; exit 1; }; done
if ! python3 -c 'import tkinter' 2>/dev/null; then
  echo 'Please install tkinter first: sudo apt install python3-tk'
  exit 1
fi
if ! python3 -m venv .venv; then
  echo 'Please install venv first: sudo apt install python3-venv'
  exit 1
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
printf '\nInstalled. Launch with ./run.sh\n'
