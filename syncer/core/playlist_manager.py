"""Advanced playlist management: track addition, removal, custom creation, and local scanning."""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from syncer.core.config import ConfigManager
from syncer.core.history import HistoryManager


class PlaylistTrackInfo:
    def __init__(
        self,
        file_path: str,
        title: str,
        artist: str = "",
        track_id: str = "",
        extension: str = "",
        size_bytes: int = 0,
        has_lrc: bool = False
    ):
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self.title = title
        self.artist = artist
        self.track_id = track_id
        self.extension = extension
        self.size_bytes = size_bytes
        self.has_lrc = has_lrc

    @property
    def display_name(self) -> str:
        if self.artist:
            return f"{self.title} - {self.artist}"
        return self.title

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)


class PlaylistManager:
    """Manages custom playlists, track lists, and library modifications."""

    SUPPORTED_AUDIO_EXTS = {".mp3", ".m4a", ".mp4", ".flac", ".ogg", ".wav", ".opus"}

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def list_playlists(self) -> List[Dict[str, Any]]:
        """Returns all configured playlists and custom playlists."""
        targets = self.config_manager.targets
        result = []
        for key, pinfo in targets.items():
            result.append({
                "key": key,
                "name": pinfo.get("name", key),
                "folder": pinfo.get("folder", "./Playlists"),
                "url": pinfo.get("url", ""),
                "is_custom": not bool(pinfo.get("url")),
                "is_single": pinfo.get("is_single", False),
                "track_count": self.count_tracks_in_folder(pinfo.get("folder", ""))
            })
        return result

    def count_tracks_in_folder(self, folder: str) -> int:
        if not folder or not os.path.isdir(folder):
            return 0
        try:
            return sum(
                1 for f in os.listdir(folder)
                if Path(f).suffix.lower() in self.SUPPORTED_AUDIO_EXTS
            )
        except Exception:
            return 0

    def create_custom_playlist(self, name: str, folder_path: Optional[str] = None) -> Dict[str, Any]:
        """Creates a new custom local playlist target."""
        clean_name = re.sub(r'[\\/*?:"<>|]', "", name).strip() or "Custom Playlist"
        if not folder_path:
            folder_path = str(Path("./Playlists/Custom") / clean_name)

        os.makedirs(folder_path, exist_ok=True)
        key = clean_name.lower().replace(" ", "_")

        playlist_info = {
            "name": clean_name,
            "folder": folder_path,
            "url": "",  # Empty URL means local custom playlist
            "is_single": False,
            "is_custom": True
        }

        targets = self.config_manager.targets
        targets[key] = playlist_info
        self.config_manager.set("active_target", key)
        self.config_manager.save()
        self.update_m3u8(folder_path, clean_name)
        return playlist_info

    def get_tracks(self, folder: str) -> List[PlaylistTrackInfo]:
        """Scans folder and returns parsed track information."""
        if not folder or not os.path.isdir(folder):
            return []

        tracks = []
        try:
            files = sorted(os.listdir(folder))
        except Exception:
            return []

        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext not in self.SUPPORTED_AUDIO_EXTS:
                continue

            full_path = os.path.join(folder, fname)
            size = os.path.getsize(full_path) if os.path.exists(full_path) else 0

            # Check matching .lrc file
            lrc_file = os.path.splitext(full_path)[0] + ".lrc"
            has_lrc = os.path.exists(lrc_file)

            # Parse "Title - Artist - [ID].ext" format
            base = os.path.splitext(fname)[0]
            track_id = ""
            if "[" in base and "]" in base:
                parts = base.split("[")
                track_id = parts[-1].split("]")[0]
                base_clean = parts[0].rstrip(" -")
            else:
                base_clean = base

            if " - " in base_clean:
                title, artist = base_clean.split(" - ", 1)
            else:
                title, artist = base_clean, ""

            tracks.append(PlaylistTrackInfo(
                file_path=full_path,
                title=title.strip(),
                artist=artist.strip(),
                track_id=track_id.strip(),
                extension=ext,
                size_bytes=size,
                has_lrc=has_lrc
            ))

        return tracks

    def remove_track(self, folder: str, track: PlaylistTrackInfo) -> bool:
        """Deletes a song, its .lrc file, and removes it from sync history and m3u8."""
        success = True
        try:
            if os.path.exists(track.file_path):
                os.remove(track.file_path)
            lrc_path = os.path.splitext(track.file_path)[0] + ".lrc"
            if os.path.exists(lrc_path):
                os.remove(lrc_path)

            # Remove from history manager if history exists
            if track.track_id:
                history = HistoryManager(folder)
                history.remove_track(track.track_id)
                history.save()

            # Refresh M3U8
            playlist_name = Path(folder).name
            self.update_m3u8(folder, playlist_name)
        except Exception as e:
            print(f"Error removing track {track.filename}: {e}")
            success = False

        return success

    def update_m3u8(self, folder: str, playlist_name: str):
        """Generates or updates the M3U8 playlist file in the folder."""
        if not os.path.isdir(folder):
            return
        clean_name = re.sub(r'[\\/*?:"<>|]', "", playlist_name).strip() or "Playlist"
        m3u8_path = os.path.join(folder, f"{clean_name}.m3u8")

        tracks = self.get_tracks(folder)
        try:
            with open(m3u8_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"#PLAYLIST:{clean_name}\n\n")
                for t in tracks:
                    f.write(f"#EXTINF:-1,{t.artist} - {t.title}\n")
                    f.write(f"{t.filename}\n")
        except Exception:
            pass
