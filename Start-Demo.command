#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
for candidate in python3.12 python3.13 python3.14 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
        "$candidate" scripts/launch_demo.py
        result=$?
        if [ "$result" -ne 0 ]; then read -r -p "Launch failed. Press Enter to close."; fi
        exit "$result"
    fi
done
printf '%s\n' 'Python 3.12 or newer is required. Install it from https://www.python.org/downloads/ and try again.'
read -r -p 'Press Enter to close.'
exit 1
