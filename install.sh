#!/bin/bash
# Content Workshop: one-time install (Mac). Paste this into Terminal once:
#
#   curl -fsSL https://raw.githubusercontent.com/Marketalse/Content_Workshop/main/install.sh | bash
#
# It creates ~/Content Workshop with the app to double-click, your Drafts and your Data.
# After this, updates come from the Update button in the dashboard. Running it again is safe:
# it repairs the program and never touches Drafts or Data.
set -euo pipefail

REPO="Marketalse/Content_Workshop"
BRANCH="${CW_BRANCH:-main}"   # for trying a version before it is merged
ROOT="$HOME/Content Workshop"
PROG="$ROOT/.program"
APP="$ROOT/Content Workshop.app"

say() { printf '\n\033[1m%s\033[0m\n' "$1"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$1" >&2; exit 1; }

say "Installing Content Workshop into: $ROOT"
mkdir -p "$PROG" "$ROOT/Drafts" "$ROOT/Data"

# 1. Python 3.10+ (uses one you already have, otherwise downloads a private copy).
PY=""
cands=(/opt/homebrew/bin/python3 /usr/local/bin/python3
       /Library/Frameworks/Python.framework/Versions/Current/bin/python3
       python3.13 python3.12 python3.11 python3.10)
# Apple's /usr/bin/python3 pops up an installer when the developer tools are missing, so only use it if they're there.
if xcode-select -p >/dev/null 2>&1 || [ "$(uname)" != "Darwin" ]; then cands+=(python3); fi
for c in "${cands[@]}"; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$(command -v "$c")"; break
  fi
done
if [ -z "$PY" ]; then
  say "Getting Python (one time, about a minute)..."
  curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$PROG/uv" INSTALLER_NO_MODIFY_PATH=1 sh >/dev/null
  "$PROG/uv/uv" python install 3.12 >/dev/null
  PY="$("$PROG/uv/uv" python find 3.12)"
fi
echo "Python: $PY"

# 2. The program: the latest version from GitHub.
say "Downloading the latest version..."
SHA="$(curl -fsSL -H 'Accept: application/vnd.github.sha' "https://api.github.com/repos/$REPO/commits/$BRANCH")" \
  || fail "Couldn't reach GitHub. Check the internet connection and try again."
DATE="$(curl -fsSL "https://api.github.com/repos/$REPO/commits/$SHA" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["commit"]["committer"]["date"][:10])' 2>/dev/null || true)"
rm -rf "$PROG/code.new"; mkdir -p "$PROG/code.new"
curl -fsSL "https://codeload.github.com/$REPO/tar.gz/$SHA" | tar -xz -C "$PROG/code.new" --strip-components 1 \
  || fail "The download failed. Try again."
rm -rf "$PROG/code"; mv "$PROG/code.new" "$PROG/code"
printf '{"sha": "%s", "date": "%s", "branch": "%s"}\n' "$SHA" "$DATE" "$BRANCH" > "$PROG/version.json"
chmod +x "$PROG/code/scripts/launch.sh"

# 3. A private Python environment with what the program needs.
say "Setting up (a minute or two the first time)..."
[ -x "$PROG/venv/bin/python" ] || "$PY" -m venv "$PROG/venv"
"$PROG/venv/bin/python" -m pip install --quiet --upgrade pip
"$PROG/venv/bin/python" -m pip install --quiet -e "$PROG/code" || fail "Setup failed. Try running the install command again."

# 4. The app you double-click (also in your Applications folder, so Spotlight and Launchpad find it).
if [ "$(uname)" = "Darwin" ]; then
  rm -rf "$APP"
  osacompile -o "$APP" -e "do shell script quoted form of \"$PROG/code/scripts/launch.sh\" & \" > /dev/null\""
  mkdir -p "$HOME/Applications"
  ln -sfn "$APP" "$HOME/Applications/Content Workshop.app"
fi

cat > "$ROOT/Read me.txt" <<'TXT'
Content Workshop
================

Content Workshop.app   Double-click to open the dashboard (or find "Content Workshop" in Spotlight).
Drafts/                Every run you create, as readable .md files (and .json with full detail).
Data/                  Your API key, your tracking log, your copy of the Iraqi word sheet, words waiting.

Updates: open the dashboard. When a new version is ready, "Update" appears at the bottom of the
sidebar. One click; your Drafts and Data are never touched.

To stop the dashboard: Settings > Stop dashboard. (It also stops when you restart the Mac.)
The hidden .program folder holds the program itself. Don't edit it; updates replace it.
TXT

say "Done. Opening the dashboard..."
"$PROG/code/scripts/launch.sh" || true
echo "Next time, double-click 'Content Workshop' in $ROOT (or search for it in Spotlight)."
