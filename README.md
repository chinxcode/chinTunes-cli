# ChinTunes 🎵

> **The Ultimate High-Fidelity Music Downloader, Playlist Syncer & Terminal Mini-Player.**  
> Seamless, zero-configuration setup for **macOS, Linux, and Windows** running in a 100% isolated sandbox.

---

## 📑 Feature Highlights

### 1. 🎵 Studio 320kbps CD Masters
- Automatically matches song metadata against **JioSaavn CD masters** for authentic 320kbps audio.
- Direct high-speed CDN audio streaming with pure Python (`urllib`), resulting in near-0% CPU load and maximum download speed.

### 2. 🎤 Real-Time Synced Lyrics & Album Covers
- Fetches synchronized timestamped lyrics (`.lrc` / `SYLT`) from **LRCLIB** and **NetEase**.
- Auto-crops video thumbnails into clean **1:1 square album covers** using pure Python Pillow without needing external tools.
- Embeds complete ID3v2.3, MP4 (`mutagen.mp4`), and FLAC metadata directly into files.

### 3. 📂 Complete Playlist & Track Manager
- **✨ Custom Playlists**: Create new local playlists (e.g. *"Gym Hits"*, *"Roadtrip"*) without requiring a remote URL. Auto-generates matching standard `.m3u8` playlists for phone, car, and VLC compatibility.
- **🎵 Manage Songs**: Inspect all songs in a playlist with file sizes and lyrics status. Play individual tracks or delete tracks and their sync history with one click.
- **⚡ 1-Click Sync**: Keeps your offline library perfectly synchronized with remote YouTube / Spotify playlists, automatically skipping already-downloaded songs.

### 4. 🔍 Multi-Format Audio Library Matcher (MP3, M4A, FLAC, OGG, OPUS, WAV, AAC, ALAC, WEBM)
- **Multi-Format Support**: Works seamlessly across `.mp3`, `.m4a`, `.mp4`, `.flac`, `.aac`, `.ogg`, `.opus`, `.wav`, `.wave`, `.aiff`, `.alac`, and `.webm`.
- **Tri-Source Metadata Cascade**:
  1. **Apple iTunes CD Master API**: Queries CD-release masters and fetches up to **1400x1400** ultra-high-definition artwork.
  2. **JioSaavn Studio API**: Secondary resolver for Indian, Bollywood, and regional tracks with studio 500x500 covers.
  3. **YouTube & YouTube Music**: Tertiary fallback via `yt-dlp` to identify rare tracks, remixes, covers, and unreleased singles, retrieving `maxresdefault` thumbnail artwork.
- **Cleans & Sanitizes**: Automatically strips pirate site domains, bitrates (`320kbps`), web URLs, and platform junk tokens.
- **1:1 Square Hi-Res Artwork**: Center-crops artwork to square JPEG using Pillow (`PIL`) without requiring external binaries.
- **Synced Lyrics Backfill**: Automatically queries and embeds synced karaoke lyrics directly into audio containers and writes matching `.lrc` companion files.
- **Optional Clean Rename**: Automatically renames files into standardized `Title - Artist.ext` format upon confirmation.

### 5. 🛠️ Library Tag & Cover Repair
- Point ChinTunes to any existing folder of music to backfill missing synchronized lyrics and 1:1 album covers offline.

---

## 🎛️ Terminal Mini-Player & Live Karaoke

Play any downloaded song or playlist directly inside your terminal with real-time scrolling lyrics:

```text
╭──────────────────────── ChinTunes Terminal Player 🎵 ────────────────────────╮
│ AGAR TUM SAATH HO — Arijit Singh                                             │
│ Track 1 of 203 • M4A • 13.26 MB                                              │
│                                                                              │
│ PLAYING ▶  00:42 ━━━━━━━━━━━─────────────────── 05:41  |  🔊 80%              │
│                                                                              │
│ ── Karaoke Synced Lyrics ─────────────────────────────────────────────────── │
│   Pal bhar thahar jaao                                                       │
│   Dil ye sambhal jaaye                                                       │
│   ♫  Agar tum saath ho  ♪                                                    │
│   Har gham phisal jaaye                                                      │
│ ──────────────────────────────────────────────────────────────────────────── │
│ Controls: [Space] Pause/Play  [←/→] Peek ±5s  [↑/↓] Volume  [N/P] Next/Prev  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### Keyboard Shortcuts:
| Key | Action |
| :--- | :--- |
| **`[Space]`** | Pause / Resume playback |
| **`[→]` / `[Right Arrow]`** | Peek / Seek forward **+5 seconds** |
| **`[←]` / `[Left Arrow]`** | Peek / Seek backward **-5 seconds** |
| **`[↑]` / `[+ / =]`** | Volume Up (+5%) |
| **`[↓]` / `[- / _]`** | Volume Down (-5%) |
| **`[N]`** | Skip to **Next Track** |
| **`[P]`** | Jump to **Previous Track** (or replay from start) |
| **`[Q]` / `[Esc]`** | Stop playback and return cleanly to menu |

---

## ⚡ 1-Click Automated Install

ChinTunes sets up its own isolated environment with zero pollution to your global system Python.

### macOS & Linux:
```bash
./install.sh
```
*(or run `python3 install.py`)*

### Windows:
Double-click `install.bat`  
*(or run `python install.py` in PowerShell / Command Prompt)*

> **What the installer does automatically:**
> 1. **System Pre-Flight**: Checks Python version and optionally detects FFmpeg.
> 2. **Isolated Environment (`~/.chintunes/env`)**: Creates a private virtual environment and installs all dependencies with 0 global footprint.
> 3. **Global Command Registration**: Adds `chintunes` and `chintune` to your PATH so they can be launched anywhere.

---

## 🚀 How to Launch

Open **any terminal** and type:
```bash
chintunes
```
*(or simply `chintune`)*

Use your **arrow keys** to navigate the menu and press **Enter** to select.

---

## 🗑️ 1-Click Complete Uninstall

To completely purge ChinTunes, its isolated virtual environment, global launchers, PATH entries, and optionally FFmpeg:

- **macOS & Linux**: Run `./uninstall.sh` (or `python3 uninstall.py`)
- **Windows**: Double-click `uninstall.bat` (or `python uninstall.py`)

Leaves **zero residual files or broken packages** on your machine.

---

## 📄 License

MIT License. Free and open source for personal music enjoyment.
