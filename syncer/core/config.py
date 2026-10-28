"""Configuration management with auto-migration and persistence."""

import json
import os
from typing import Dict, Any, Optional

CONFIG_FILE = "sync_config.json"


class ConfigManager:
    DEFAULT_CONFIG: Dict[str, Any] = {
        "active_target": None,
        "targets": {},
        "audio_format": "mp3",           # mp3, m4a (fastest/lossless container), or flac
        "audio_quality": "0",             # 0 = VBR best, 320k CBR
        "fast_stream_copy": True,        # When audio matches or m4a requested, copy directly without FFmpeg re-encoding
        "prefer_jiosaavn_320k": True,    # Studio 320kbps master preference (direct CDN HTTP stream)
        "normalize_loudness": False,     # Disabled by default for maximum download speed and 0% CPU; enable if loudness matching needed
        "crop_square_thumbnail": True,    # 1:1 center-cropped artwork
        "max_workers": 3,
        "rate_limit_delay": 0.5,         # Fast pacing delay
        "embed_lyrics": True,
        "save_lrc_file": False,
        "generate_m3u8": True,
        "clean_removed_tracks": False,
    }

    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self._config: Dict[str, Any] = self.load()

    def load(self) -> Dict[str, Any]:
        cfg = dict(self.DEFAULT_CONFIG)
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        if k not in ("targets", "playlists", "playlist_url", "download_dir", "embed_synced_lyrics"):
                            cfg[k] = v

                    targets = saved.get("targets") or saved.get("playlists") or {}
                    # Filter out old hardcoded "Default_Playlist" if empty or matching old hardcoded placeholder
                    cleaned_targets = {}
                    for t_key, t_val in targets.items():
                        if t_key != "Default_Playlist" and isinstance(t_val, dict) and t_val.get("url"):
                            cleaned_targets[t_key] = t_val

                    cfg["targets"] = cleaned_targets

                    active = saved.get("active_target") or saved.get("active_playlist")
                    if active and active in cleaned_targets:
                        cfg["active_target"] = active
                    elif cleaned_targets:
                        cfg["active_target"] = list(cleaned_targets.keys())[0]
                    else:
                        cfg["active_target"] = None
            except Exception:
                pass
        return cfg

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value

    @property
    def data(self) -> Dict[str, Any]:
        return self._config

    @property
    def targets(self) -> Dict[str, Any]:
        return self._config.setdefault("targets", {})

    @property
    def has_targets(self) -> bool:
        return bool(self._config.get("targets"))

    @property
    def active_target_info(self) -> Optional[Dict[str, Any]]:
        targets = self._config.setdefault("targets", {})
        active_key = self._config.get("active_target")
        if active_key and active_key in targets:
            return targets[active_key]
        if targets:
            first_key = list(targets.keys())[0]
            self._config["active_target"] = first_key
            return targets[first_key]
        return None
