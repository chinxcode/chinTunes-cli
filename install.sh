#!/usr/bin/env bash
# ChinTunes 1-Click Setup for Linux & macOS
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PYTHON_CMD="python3"

if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "❌ Python 3 is required. Please install python3 first."
        exit 1
    fi
fi

"$PYTHON_CMD" "$DIR/install.py"
