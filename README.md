# ChinTunes 🎵

A fast, interactive music downloader and playlist syncer for **Windows, macOS, and Linux**.

Download songs and playlists with 320kbps CD masters, timed synchronized lyrics, and square album covers.

---

## ⚡ 1-Click Install

### On macOS & Linux:
```bash
./install.sh
```
*(or run `python3 install.py`)*

### On Windows:
Double-click `install.bat`  
*(or run `python install.py` in PowerShell / Command Prompt)*

> **What the installer does automatically:**  
> 1. **System Check**: Analyzes your Python version and checks for FFmpeg. If missing, it asks for permission and automatically installs them for you (via Homebrew on Mac, Winget/Chocolatey on Windows, or apt/dnf/pacman on Linux).  
> 2. **Installs Packages**: Installs all required software packages.  
> 3. **Configures PATH**: Adds the `chintunes` command to your system environment PATH permanently so you can run it from anywhere.

---

## 🚀 How to Use

Open **any terminal** and type:

```bash
chintunes
```

Navigate the interactive menu using your **arrow keys** and press **Enter** to choose.

---

## ✨ Features

- **Universal Links**: Paste any link from YouTube, YouTube Music, JioSaavn, Spotify, SoundCloud, or Gaana.
- **Studio 320kbps Audio**: Automatic high-quality master matching from JioSaavn.
- **Fast & Light**: Streams audio directly without burning CPU or slowing down your computer.
- **Embedded Lyrics**: Automatically finds and embeds timed lyrics (`SYLT` and `USLT` tags).
- **Square Artwork**: Auto-crops video thumbnails into clean 1:1 album covers.
- **Clean File Names**: Saved neatly as `Song Title - Artist - [ID].mp3` (no ugly tags or channel noise).
- **Offline Repair**: Backfill missing lyrics and covers on your existing music library anytime.

---

## 📄 License

MIT
