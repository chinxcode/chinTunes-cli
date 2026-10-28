#!/usr/bin/env bash
# ChinTunes 1-Click Complete Uninstaller for macOS & Linux

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Python 3 is required to run the uninstaller."
    exit 1
fi

"$PYTHON_CMD" "$DIR/uninstall.py"
