#!/bin/bash
# Run by "Content Workshop.app": open the dashboard, starting it in the background if it isn't running.
CODE="$(cd "$(dirname "$0")/.." && pwd)"
PROG="$(dirname "$CODE")"
ROOT="$(dirname "$PROG")"
PORT=8765
URL="http://127.0.0.1:$PORT/"
export CW_PROGRAM_DIR="$PROG" CW_DATA_DIR="$ROOT/Data" CW_OUTPUT_DIR="$ROOT/Drafts"

show() { if command -v open >/dev/null 2>&1; then open "$URL"; else xdg-open "$URL" >/dev/null 2>&1 || echo "$URL"; fi; }
up() { curl -fsS -m 1 "${URL}healthz" >/dev/null 2>&1; }

if up; then show; exit 0; fi
PY="$PROG/venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "Content Workshop isn't fully installed. Run the install command from the Read me again." >&2
  exit 1
fi
cd "$ROOT" || exit 1
nohup "$PY" -m content_workshop dashboard --no-browser --port "$PORT" >> "$PROG/dashboard.log" 2>&1 &
for _ in $(seq 1 60); do
  if up; then show; exit 0; fi
  sleep 0.25
done
echo "The dashboard didn't start. Details: $PROG/dashboard.log" >&2
exit 1
