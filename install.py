#!/usr/bin/env python3
"""
ChinTunes 1-Click Automated Installer & System Analyzer.
Analyzes Python version and FFmpeg availability.
Offers automated 1-click installation of missing tools with user permission.
Supports macOS, Linux, and Windows.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    print(f"""{CYAN}{BOLD}
 ▄▄▄▄▄▄▄ ▄▄             ▄▄▄▄▄▄▄▄▄                      
███▀▀▀▀▀ ██    ▀▀       ▀▀▀███▀▀▀                      
███      ████▄ ██  ████▄   ███ ██ ██ ████▄ ▄█▀█▄ ▄█▀▀▀ 
███      ██ ██ ██  ██ ██   ███ ██ ██ ██ ██ ██▄█▀ ▀███▄ 
▀███████ ██ ██ ██▄ ██ ██   ███ ▀██▀█ ██ ██ ▀█▄▄▄ ▄▄▄█▀{RESET}
{BOLD}One-Click System Setup & Environment Configurator{RESET}
    """)


def ask_permission(prompt_text: str, default: bool = True) -> bool:
    """Prompt with highlighted default choice."""
    if default:
        suffix = f" [{GREEN}{BOLD}Y{RESET}/n]: "
    else:
        suffix = f" [y/{GREEN}{BOLD}N{RESET}]: "

    try:
        reply = input(f"{YELLOW}{BOLD}?{RESET} {prompt_text}{suffix}").strip().lower()
        if not reply:
            return default
        return reply.startswith("y") if not default else not reply.startswith("n")
    except (KeyboardInterrupt, EOFError):
        print("\nInstallation cancelled by user.")
        sys.exit(0)


def check_and_install_ffmpeg():
    """Analyzes system for FFmpeg. If missing, explains why it's optional and prompts with default N."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        print(f" {GREEN}✔{RESET} FFmpeg detected: {CYAN}{ffmpeg_bin}{RESET}")
        return True

    print(f"\n {YELLOW}ℹ FFmpeg is not installed (Optional){RESET}")
    print("   ChinTunes works completely out-of-the-box in high quality without it.")
    print("   FFmpeg is only needed if you want automatic MP3 conversion or volume leveling.")

    want_install = ask_permission("Would you like to install FFmpeg anyway?", default=False)
    if not want_install:
        print(f" {GREEN}✔{RESET} Continuing in pure Python mode (fast & lightweight)")
        return False

    print(f"   {CYAN}Attempting to install FFmpeg...{RESET}")

    # 1. macOS
    if sys.platform == "darwin":
        if shutil.which("brew"):
            try:
                subprocess.check_call(["brew", "install", "ffmpeg"])
                print(f" {GREEN}✔{RESET} FFmpeg successfully installed via Homebrew!")
                return True
            except Exception as e:
                print(f" {YELLOW}⚠️ Failed to install FFmpeg via Homebrew: {e}{RESET}")
        else:
            print(f" {YELLOW}⚠️ Homebrew not detected. Please install Homebrew (https://brew.sh) or download FFmpeg manually.{RESET}")

    # 2. Windows
    elif os.name == "nt":
        if shutil.which("winget"):
            try:
                subprocess.check_call(["winget", "install", "-e", "--id", "Gyan.FFmpeg", "--accept-package-agreements", "--accept-source-agreements"])
                print(f" {GREEN}✔{RESET} FFmpeg installed via Windows Package Manager (winget)!")
                return True
            except Exception as e:
                print(f" {YELLOW}⚠️ Winget installation failed: {e}{RESET}")
        elif shutil.which("choco"):
            try:
                subprocess.check_call(["choco", "install", "ffmpeg", "-y"])
                print(f" {GREEN}✔{RESET} FFmpeg installed via Chocolatey!")
                return True
            except Exception as e:
                print(f" {YELLOW}⚠️ Chocolatey install failed: {e}{RESET}")
        else:
            print("   Please install FFmpeg using winget or from https://ffmpeg.org/download.html")

    # 3. Linux
    else:
        pkg_managers = [
            (["apt-get", "update"], ["apt-get", "install", "-y", "ffmpeg"]),
            (None, ["dnf", "install", "-y", "ffmpeg"]),
            (None, ["pacman", "-S", "--noconfirm", "ffmpeg"]),
            (None, ["zypper", "install", "-y", "ffmpeg"]),
        ]
        for prep, cmd in pkg_managers:
            mgr = cmd[0]
            if shutil.which(mgr):
                try:
                    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
                    sudo = [] if is_root else ["sudo"]
                    if prep:
                        subprocess.run(sudo + prep, check=True)
                    subprocess.check_call(sudo + cmd)
                    print(f" {GREEN}✔{RESET} FFmpeg successfully installed via {mgr}!")
                    return True
                except Exception as e:
                    print(f" {YELLOW}⚠️ Failed to install FFmpeg via {mgr}: {e}{RESET}")
                    break

    return False


def get_install_bin_dir() -> Path:
    """Returns directory for placing command launchers."""
    if os.name == "nt":
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Programs" / "ChinTunes"
        return Path.home() / "ChinTunes"
    return Path.home() / ".local" / "bin"


def configure_path_windows(bin_dir: Path):
    """Adds bin_dir to user PATH on Windows permanently via setx or PowerShell."""
    bin_dir_str = str(bin_dir)
    current_path = os.environ.get("PATH", "")
    if bin_dir_str.lower() in current_path.lower():
        return

    try:
        cmd = f'[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User) + ";{bin_dir_str}", [EnvironmentVariableTarget]::User)'
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f" {GREEN}✔{RESET} Added {CYAN}{bin_dir_str}{RESET} to Windows User PATH")
    except Exception:
        try:
            subprocess.run(f'setx PATH "%PATH%;{bin_dir_str}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f" {GREEN}✔{RESET} Added {CYAN}{bin_dir_str}{RESET} to Windows PATH via setx")
        except Exception as e:
            print(f" {YELLOW}⚠️ Notice: Please add {bin_dir_str} to your Windows PATH: {e}{RESET}")


def configure_path_unix(bin_dir: Path):
    """Ensures bin_dir is in PATH across ~/.zshrc, ~/.bashrc, ~/.bash_profile."""
    bin_dir_str = str(bin_dir)
    current_path = os.environ.get("PATH", "")
    if bin_dir_str in current_path:
        return

    export_line = f'export PATH="{bin_dir_str}:$PATH"\n'
    home = Path.home()
    shell_files = [home / ".zshrc", home / ".bashrc", home / ".bash_profile", home / ".profile"]

    configured_any = False
    for rc_file in shell_files:
        if rc_file.exists():
            try:
                content = rc_file.read_text(encoding="utf-8")
                if bin_dir_str not in content:
                    with open(rc_file, "a", encoding="utf-8") as f:
                        f.write(f"\n# Added by ChinTunes Installer\n{export_line}")
                    print(f" {GREEN}✔{RESET} Added {CYAN}{bin_dir_str}{RESET} to {BOLD}{rc_file.name}{RESET}")
                    configured_any = True
            except Exception:
                pass

    if not configured_any:
        target_rc = home / (".zshrc" if sys.platform == "darwin" else ".bashrc")
        try:
            with open(target_rc, "a", encoding="utf-8") as f:
                f.write(f"\n# Added by ChinTunes Installer\n{export_line}")
            print(f" {GREEN}✔{RESET} Created PATH entry in {BOLD}{target_rc.name}{RESET}")
        except Exception:
            pass


def install():
    print_banner()

    # 1. System Pre-flight Analysis
    print(f"[{BOLD}1/4{RESET}] Analyzing system requirements...")
    v = sys.version_info
    print(f" {GREEN}✔{RESET} Python version: {CYAN}{v.major}.{v.minor}.{v.micro}{RESET}")
    if v.major < 3 or (v.major == 3 and v.minor < 8):
        print(f" {YELLOW}⚠️ ChinTunes requires Python 3.8 or higher.{RESET}")

    check_and_install_ffmpeg()

    # 2. Package Installation
    repo_dir = Path(__file__).resolve().parent
    print(f"\n[{BOLD}2/4{RESET}] Installing ChinTunes package & dependencies...")
    pip_cmd = [sys.executable, "-m", "pip", "install", "-e", str(repo_dir)]
    try:
        subprocess.check_call(pip_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f" {GREEN}✔{RESET} Dependencies successfully installed.")
    except Exception:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "-e", str(repo_dir)])

    # 3. Setup Global Command Launcher
    print(f"\n[{BOLD}3/4{RESET}] Setting up global command launcher...")
    bin_dir = get_install_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    python_exec = sys.executable

    if os.name == "nt":
        bat_content = f'@echo off\r\n"{python_exec}" -m syncer %*\r\n'
        for name in ["chintunes.bat", "chintune.bat", "chintunes.cmd"]:
            target_bat = bin_dir / name
            with open(target_bat, "w", encoding="utf-8") as f:
                f.write(bat_content)
        print(f" {GREEN}✔{RESET} Created Windows launchers in {CYAN}{bin_dir}{RESET}")
    else:
        sh_content = f'#!/bin/sh\nexec "{python_exec}" -m syncer "$@"\n'
        for name in ["chintunes", "chintune"]:
            target_sh = bin_dir / name
            with open(target_sh, "w", encoding="utf-8") as f:
                f.write(sh_content)
            target_sh.chmod(0o755)
        print(f" {GREEN}✔{RESET} Created executable launcher in {CYAN}{bin_dir}{RESET}")

    # 4. PATH Environment Setup
    print(f"\n[{BOLD}4/4{RESET}] Checking system PATH environment...")
    if os.name == "nt":
        configure_path_windows(bin_dir)
    else:
        configure_path_unix(bin_dir)

    print(f"""
{GREEN}{BOLD}══════════════════════════════════════════════════════════════════{RESET}
 {GREEN}{BOLD}🎉 Installation Complete! ChinTunes is ready to use.{RESET}
{GREEN}{BOLD}══════════════════════════════════════════════════════════════════{RESET}

Open any terminal and type:
  {CYAN}{BOLD}chintunes{RESET} or {CYAN}{BOLD}chintune{RESET}
""")


if __name__ == "__main__":
    install()
