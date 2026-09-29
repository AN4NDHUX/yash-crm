#!/usr/bin/env bash
# Double-click to start Yash CRM on macOS (or run ./start.command on Linux).
cd "$(dirname "$0")" || exit 1

# Prefer a tested Python (3.12 first). Very new releases can break the dependencies.
PY=""
for candidate in python3.12 python3.13 python3.11 python3.10 python3.14 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done

if [ -n "$PY" ]; then
  "$PY" launch.py "$@"
else
  echo "Python 3.10 to 3.14 is required. Install Python 3.12 from https://www.python.org/downloads/ and run this again."
fi
echo
read -r -p "Press Enter to close..."
