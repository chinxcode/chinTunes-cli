"""Core data models representing tracks, lyrics, targets, and results."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


def clean_artist_name(raw_artist: Optional[str], description: str = "") -> str:
    """
    Cleans automated YouTube channel artifacts such as '- Topic', 'VEVO', 'Official',
    and resolves generic 'Release - Topic' channels into the true performer.
    """
    if not raw_artist:
        return "Unknown"

    cleaned = raw_artist.strip()
    noise_suffixes = [
        r"\s*-\s*Topic$",
        r"\s+Topic$",
        r"\s+Official Channel$",
        r"\s+Official$",
        r"\s+VEVO$",
        r"\s+Records$",
        r"\s+Music$",
        r"\s+Series$",
    ]
    for pattern in noise_suffixes:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # If channel was literally "Release" or "Release - Topic", extract from description bullet line: "Title · Real Artist"
    if cleaned.lower() in ("release", "various artists", "auto-generated", "unknown", ""):
        if description:
            for line in description.splitlines():
                if "·" in line:
                    parts = [p.strip() for p in line.split("·")]
                    if len(parts) >= 2 and parts[1]:
                        return parts[1]

    return cleaned or "Unknown"


@dataclass
class LyricsData:
    plain: Optional[str] = None
    synced: Optional[str] = None
    source: str = "UNKNOWN"

    @property
    def has_synced(self) -> bool:
        return bool(self.synced)

    @property
    def is_empty(self) -> bool:
        return not bool(self.plain or self.synced)


@dataclass
class TrackMetadata:
    id: str
    title: str
    artist: str
    album: str
    duration: Optional[int] = None
    year: Optional[str] = None
    image_url: Optional[str] = None
    cdn_url: Optional[str] = None
    web_url: Optional[str] = None
    playlist_index: int = 1
    provider: str = "general"
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        desc = self.extra_data.get("description", "")
        self.artist = clean_artist_name(self.artist, description=desc)

    @property
    def safe_filename_base(self) -> str:
        clean_title = "".join(c for c in self.title if c not in '\\/*?:"<>|').strip() or "Track"
        clean_artist = "".join(c for c in self.artist if c not in '\\/*?:"<>|').strip() or "Unknown"
        return f"{clean_title} - {clean_artist} - [{self.id}]"


@dataclass
class CollectionResult:
    provider: str
    title: str
    tracks: List[TrackMetadata]
    is_single: bool = False
    header_desc: Optional[str] = None
    image_url: Optional[str] = None


@dataclass
class SyncProcessResult:
    track_id: str
    title: str
    artist: str
    album: str
    file_path: Optional[str] = None
    duration: Optional[int] = None
    source: str = "unknown"
    lyrics_source: Optional[str] = None
    has_synced_lyrics: bool = False
    has_thumbnail: bool = False
    synced_at: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
