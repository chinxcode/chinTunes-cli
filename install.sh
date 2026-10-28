#!/usr/bin/env bash
# ChinTunes 1-Click Setup for Linux & macOS
# Checks Python & FFmpeg, offers auto-installation with user confirmation.

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
GREEN="\033[92m"
YELLOW="\033[93m"
CYAN="\033[96m"
BOLD="\033[1m"
RESET="\033[0m"

echo ""
echo -e "${CYAN}${BOLD}── ChinTunes Pre-Flight System Check ──${RESET}"

# 1. Check Python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${YELLOW}⚠️ Python 3 was not found on your system.${RESET}"
    read -p "$(echo -e "${YELLOW}?${RESET} Would you like to install Python 3 now? [${GREEN}${BOLD}Y${RESET}/n]: ")" install_py
    install_py=${install_py:-Y}
    if [[ "$install_py" =~ ^[Yy]$ ]]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &> /dev/null; then
                brew install python
            else
                echo -e "${YELLOW}Homebrew not detected. Please install Python from https://www.python.org/downloads/${RESET}"
                exit 1
            fi
        elif command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y python3 python3-pip
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm python python-pip
        else
            echo "Please install Python 3 using your system package manager."
            exit 1
        fi
        PYTHON_CMD="python3"
    else
        echo "Python 3 is required to run ChinTunes. Exiting."
        exit 1
    fi
fi

echo -e " ${GREEN}✔${RESET} Python detected: $($PYTHON_CMD --version)"

# 2. Run Python installer (which also checks and installs FFmpeg if missing)
"$PYTHON_CMD" "$DIR/install.py"
