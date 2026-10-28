#!/usr/bin/env python3
"""
ChinTunes 1-Click Automated Installer & PATH Configurator.
Supports macOS, Linux, and Windows.
Installs dependencies and puts 'chintunes' into system PATH.
"""

import os
import sys
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
  ██████╗██╗  ██╗██╗███╗   ██╗████████╗██╗   ██╗███╗   ██╗███████╗███████╗
 ██╔════╝██║  ██║██║████╗  ██║╚══██╔══╝██║   ██║████╗  ██║██╔════╝██╔════╝
 ██║     ███████║██║██╔██╗ ██║   ██║   ██║   ██║██╔██╗ ██║█████╗  ███████╗
 ██║     ██╔══██║██║██║╚██╗██║   ██║   ██║   ██║██║╚██╗██║██╔══╝  ╚════██║
 ╚██████╗██║  ██║██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚████║███████╗███████║
  ╚═════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚══════╝{RESET}
               {BOLD}One-Click Automated Setup{RESET}
    """)


def get_install_bin_dir() -> Path:
    """Returns directory for placing command launchers."""
    if os.name == "nt":
        # Windows User AppData Local Programs or Python Scripts
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
    repo_dir = Path(__file__).resolve().parent

    print(f"[{BOLD}1/3{RESET}] Installing ChinTunes package & dependencies...")
    pip_cmd = [sys.executable, "-m", "pip", "install", "-e", str(repo_dir)]
    try:
        subprocess.check_call(pip_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f" {GREEN}✔{RESET} Dependencies installed.")
    except Exception:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "-e", str(repo_dir)])

    print(f"\n[{BOLD}2/3{RESET}] Setting up command launcher...")
    bin_dir = get_install_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    python_exec = sys.executable

    if os.name == "nt":
        # Windows .bat and .cmd launchers
        bat_content = f'@echo off\r\n"{python_exec}" -m syncer %*\r\n'
        for name in ["chintunes.bat", "chintune.bat", "chintunes.cmd"]:
            target_bat = bin_dir / name
            with open(target_bat, "w", encoding="utf-8") as f:
                f.write(bat_content)
        print(f" {GREEN}✔{RESET} Created Windows launchers in {CYAN}{bin_dir}{RESET}")
    else:
        # macOS / Linux shell script launchers
        sh_content = f'#!/bin/sh\nexec "{python_exec}" -m syncer "$@"\n'
        for name in ["chintunes", "chintune"]:
            target_sh = bin_dir / name
            with open(target_sh, "w", encoding="utf-8") as f:
                f.write(sh_content)
            target_sh.chmod(0o755)
        print(f" {GREEN}✔{RESET} Created executable launcher in {CYAN}{bin_dir}{RESET}")

    print(f"\n[{BOLD}3/3{RESET}] Checking system PATH environment...")
    if os.name == "nt":
        configure_path_windows(bin_dir)
    else:
        configure_path_unix(bin_dir)

    print(f"""
{GREEN}{BOLD}══════════════════════════════════════════════════════════════════{RESET}
 {GREEN}{BOLD}🎉 Installation Complete! ChinTunes is ready.{RESET}
{GREEN}{BOLD}══════════════════════════════════════════════════════════════════{RESET}

Open any terminal and type:
  {CYAN}{BOLD}chintunes{RESET}
""")


if __name__ == "__main__":
    install()
