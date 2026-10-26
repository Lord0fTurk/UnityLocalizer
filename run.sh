#!/bin/sh
# Start UnityLocalizer on Linux / Steam Deck (desktop mode); extra arguments are passed on.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
    exec python3 run.py "$@"
fi
exec python run.py "$@"
