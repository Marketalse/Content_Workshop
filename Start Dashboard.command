#!/bin/bash
# Double-click this file in Finder to open the Content Workshop dashboard.
# The first run sets everything up (a minute or two). Keep the window open while you work.

cd "$(dirname "$0")" || exit 1

echo "Content Workshop"
echo "----------------"

# Pick up the latest version if this folder came from GitHub (skipped quietly if it can't).
if [ -d .git ] && command -v git >/dev/null 2>&1; then
  git pull --ff-only --quiet 2>/dev/null && echo "Up to date." || echo "(Couldn't check for updates; carrying on.)"
fi

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo ""
  echo "Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/macos/"
  echo "then double-click this file again."
  open "https://www.python.org/downloads/macos/" 2>/dev/null
  read -r -p "Press Enter to close." _
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "First-time setup..."
  "$PY" -m venv .venv || { read -r -p "Setup failed. Press Enter to close." _; exit 1; }
fi

# Install or refresh the project when pyproject.toml changes.
if [ ! -f .venv/.installed ] || [ pyproject.toml -nt .venv/.installed ]; then
  echo "Installing (this happens once)..."
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -e ".[dev]" || { read -r -p "Install failed. Press Enter to close." _; exit 1; }
  touch .venv/.installed
fi

echo ""
.venv/bin/python -m content_workshop dashboard
