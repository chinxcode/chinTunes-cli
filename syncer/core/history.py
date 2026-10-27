"""JSON State & sync history management."""

import json
import os
import time
from typing import Dict, Any

HISTORY_FILE = "sync_history.json"


class HistoryManager:
    def __init__(self, directory: str):
        self.directory = directory
        self.history_path = os.path.join(directory, HISTORY_FILE)
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Check for legacy downloaded_history.txt migration
        legacy_txt = os.path.join(self.directory, "downloaded_history.txt")
        tracks = {}
        if os.path.exists(legacy_txt):
            try:
                with open(legacy_txt, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("youtube "):
                            vid = line.split(" ", 1)[1].strip()
                            tracks[vid] = {
                                "id": vid,
                                "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "status": "migrated_from_legacy_txt",
                            }
            except Exception:
                pass

        return {"version": 3, "last_sync": None, "tracks": tracks}

    def save(self):
        try:
            self.data["last_sync"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving history: {e}")

    @property
    def tracks(self) -> Dict[str, Any]:
        return self.data.setdefault("tracks", {})

    def record_track(self, track_id: str, record_dict: Dict[str, Any]):
        self.tracks[str(track_id)] = record_dict

    def remove_track(self, track_id: str):
        if str(track_id) in self.tracks:
            del self.tracks[str(track_id)]

    def has_track(self, track_id: str) -> bool:
        return str(track_id) in self.tracks
