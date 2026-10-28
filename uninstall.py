#!/usr/bin/env python3
"""
ChinTunes Complete Uninstaller.
Completely cleans and removes all ChinTunes installations, commands, PATH configurations,
and optionally all dependencies and FFmpeg.
Supports macOS, Linux, and Windows.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# ANSI Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    print(f"""{RED}{BOLD}
 ▄▄▄▄▄▄▄ ▄▄             ▄▄▄▄▄▄▄▄▄                      
███▀▀▀▀▀ ██    ▀▀       ▀▀▀███▀▀▀                      
███      ████▄ ██  ████▄   ███ ██ ██ ████▄ ▄█▀█▄ ▄█▀▀▀ 
███      ██ ██ ██  ██ ██   ███ ██ ██ ██ ██ ██▄█▀ ▀███▄ 
▀███████ ██ ██ ██▄ ██ ██   ███ ▀██▀█ ██ ██ ▀█▄▄▄ ▄▄▄█▀{RESET}
{BOLD}ChinTunes Complete System Uninstaller & Cleaner{RESET}
    """)


def ask_permission(prompt_text: str, default: bool = True) -> bool:
    """Prompt with default highlighted choice."""
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
        print("\nUninstallation cancelled by user.")
        sys.exit(0)


def get_chintunes_env_dir() -> Path:
    """Returns dedicated isolated environment directory for ChinTunes."""
    if os.name == "nt":
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "ChinTunes" / "env"
        return Path.home() / ".chintunes" / "env"
    return Path.home() / ".chintunes" / "env"


def get_bin_dir() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Programs" / "ChinTunes"
        return Path.home() / "ChinTunes"
    return Path.home() / ".local" / "bin"


def remove_launchers():
    """Removes chintunes and chintune command scripts."""
    print(f"\n[{BOLD}1/4{RESET}] Removing global command launchers...")
    bin_dir = get_bin_dir()
    removed_count = 0

    if os.name == "nt":
        for name in ["chintunes.bat", "chintune.bat", "chintunes.cmd", "chintune.cmd"]:
            target = bin_dir / name
            if target.exists():
                try:
                    target.unlink()
                    removed_count += 1
                except Exception as e:
                    print(f" {YELLOW}⚠️ Could not remove {target}: {e}{RESET}")
        if bin_dir.exists() and not any(bin_dir.iterdir()):
            try:
                shutil.rmtree(bin_dir)
            except Exception:
                pass
    else:
        for name in ["chintunes", "chintune"]:
            target = bin_dir / name
            if target.exists():
                try:
                    target.unlink()
                    removed_count += 1
                except Exception as e:
                    print(f" {YELLOW}⚠️ Could not remove {target}: {e}{RESET}")

    if removed_count > 0:
        print(f" {GREEN}✔{RESET} Removed command launchers from {CYAN}{bin_dir}{RESET}")
    else:
        print(f" {dim_text('No stray launchers found.')}")


def clean_path_config():
    """Removes ChinTunes PATH entries from shell rc files on Unix."""
    print(f"\n[{BOLD}2/4{RESET}] Cleaning system PATH configuration...")
    if os.name == "nt":
        print(f" {GREEN}✔{RESET} Windows launcher entries cleaned.")
        return

    home = Path.home()
    shell_files = [home / ".zshrc", home / ".bashrc", home / ".bash_profile", home / ".profile"]
    cleaned_any = False

    for rc in shell_files:
        if rc.exists():
            try:
                lines = rc.read_text(encoding="utf-8").splitlines(keepends=True)
                new_lines = []
                skip_next = False
                for l in lines:
                    if "# Added by ChinTunes Installer" in l:
                        cleaned_any = True
                        continue
                    if ".local/bin" in l and "chintunes" in l.lower():
                        cleaned_any = True
                        continue
                    new_lines.append(l)

                if cleaned_any:
                    rc.write_text("".join(new_lines), encoding="utf-8")
                    print(f" {GREEN}✔{RESET} Cleaned PATH entries from {BOLD}{rc.name}{RESET}")
            except Exception:
                pass

    if not cleaned_any:
        print(f" {dim_text('Shell configurations were already clean.')}")


def uninstall_python_package():
    """Removes ChinTunes isolated virtual environment and all packages within it."""
    print(f"\n[{BOLD}3/4{RESET}] Removing isolated environment & dependencies...")
    env_dir = get_chintunes_env_dir()
    chintunes_root = env_dir.parent

    if chintunes_root.exists():
        try:
            shutil.rmtree(chintunes_root)
            print(f" {GREEN}✔{RESET} Completely purged isolated environment at {CYAN}{chintunes_root}{RESET}")
        except Exception as e:
            print(f" {YELLOW}⚠️ Failed to delete environment folder: {e}{RESET}")
    else:
        print(f" {dim_text('Isolated environment was already removed.')}")

    # Also check if package was installed in current python environment
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "uninstall", "-y", "chintunes"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def check_and_remove_ffmpeg():
    """Optionally asks to remove FFmpeg if user wants complete cleanup."""
    print(f"\n[{BOLD}4/4{RESET}] Checking for external FFmpeg...")
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        print(f" {dim_text('FFmpeg is not installed on system.')}")
        return

    print(f" Found FFmpeg at: {CYAN}{ffmpeg_bin}{RESET}")
    remove_ff = ask_permission("Would you like to uninstall FFmpeg as well?", default=False)
    if not remove_ff:
        print(" Keeping FFmpeg on your system.")
        return

    print(f"   {CYAN}Removing FFmpeg...{RESET}")
    if sys.platform == "darwin":
        if shutil.which("brew"):
            try:
                subprocess.check_call(["brew", "uninstall", "ffmpeg"])
                print(f" {GREEN}✔{RESET} FFmpeg removed via Homebrew!")
            except Exception as e:
                print(f" {YELLOW}⚠️ Failed to uninstall FFmpeg via brew: {e}{RESET}")
    elif os.name == "nt":
        if shutil.which("winget"):
            try:
                subprocess.check_call(["winget", "uninstall", "-e", "--id", "Gyan.FFmpeg"])
                print(f" {GREEN}✔{RESET} FFmpeg removed via Winget!")
            except Exception as e:
                print(f" {YELLOW}⚠️ Winget uninstall failed: {e}{RESET}")
    else:
        for mgr in ["apt-get", "dnf", "pacman", "zypper"]:
            if shutil.which(mgr):
                try:
                    sudo = [] if (hasattr(os, "geteuid") and os.geteuid() == 0) else ["sudo"]
                    if mgr == "apt-get":
                        subprocess.check_call(sudo + ["apt-get", "remove", "-y", "ffmpeg"])
                    elif mgr == "dnf":
                        subprocess.check_call(sudo + ["dnf", "remove", "-y", "ffmpeg"])
                    elif mgr == "pacman":
                        subprocess.check_call(sudo + ["pacman", "-R", "--noconfirm", "ffmpeg"])
                    print(f" {GREEN}✔{RESET} FFmpeg removed via {mgr}!")
                    break
                except Exception as e:
                    print(f" {YELLOW}⚠️ Failed to remove via {mgr}: {e}{RESET}")


def dim_text(t: str) -> str:
    return f"\033[2m{t}\033[0m"


def uninstall():
    print_banner()
    confirm = ask_permission(f"{RED}{BOLD}Are you sure you want to completely uninstall ChinTunes?{RESET}", default=False)
    if not confirm:
        print("Uninstallation aborted.")
        return

    remove_launchers()
    clean_path_config()
    uninstall_python_package()
    check_and_remove_ffmpeg()

    print(f"""
{RED}{BOLD}══════════════════════════════════════════════════════════════════{RESET}
 {GREEN}{BOLD}✔ ChinTunes has been completely uninstalled from your system.{RESET}
{RED}{BOLD}══════════════════════════════════════════════════════════════════{RESET}
""")


if __name__ == "__main__":
    uninstall()
