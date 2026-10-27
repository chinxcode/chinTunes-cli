"""YouTube and Generic yt-dlp provider implementation."""

from typing import Optional, List
import yt_dlp

from syncer.core.models import TrackMetadata, CollectionResult, clean_artist_name
from syncer.providers.base import BaseProvider


class YouTubeProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "youtube"

    def can_handle(self, url: str) -> bool:
        url_lower = url.lower()
        return (
            "youtube.com" in url_lower
            or "youtu.be" in url_lower
            or "music.youtube.com" in url_lower
            or "soundcloud.com" in url_lower
            or "gaana.com" in url_lower
        )

    def fetch_collection(self, url: str) -> Optional[CollectionResult]:
        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception:
                return None

        # Check if single track
        entries = info.get("entries")
        if not entries:
            raw_artist = info.get("artist") or info.get("creator") or info.get("uploader") or info.get("channel", "Unknown")
            desc = info.get("description", "")
            resolved_artist = clean_artist_name(raw_artist, description=desc)

            track = TrackMetadata(
                id=str(info.get("id")),
                title=info.get("title") or "Track",
                artist=resolved_artist,
                album=info.get("album") or info.get("title") or "Single",
                duration=info.get("duration"),
                year=info.get("release_year") or (info.get("upload_date")[:4] if info.get("upload_date") else None),
                image_url=info.get("thumbnail"),
                web_url=f"https://www.youtube.com/watch?v={info.get('id')}",
                provider=self.name,
                extra_data={
                    "thumbnails": info.get("thumbnails", []),
                    "description": desc,
                }
            )
            return CollectionResult(
                provider=self.name,
                title=track.title,
                tracks=[track],
                is_single=True,
                image_url=track.image_url
            )

        # Playlist / Album collection
        playlist_title = info.get("title") or "Playlist"
        tracks: List[TrackMetadata] = []
        for idx, entry in enumerate(entries):
            if entry and entry.get("id"):
                raw_artist = entry.get("artist") or entry.get("uploader") or entry.get("channel", "Unknown")
                resolved_artist = clean_artist_name(raw_artist)

                tracks.append(
                    TrackMetadata(
                        id=str(entry["id"]),
                        title=entry.get("title") or f"Track {idx + 1}",
                        artist=resolved_artist,
                        album=entry.get("album") or playlist_title,
                        duration=entry.get("duration"),
                        playlist_index=idx + 1,
                        web_url=f"https://www.youtube.com/watch?v={entry['id']}",
                        provider=self.name,
                        extra_data={"thumbnails": entry.get("thumbnails", [])}
                    )
                )

        return CollectionResult(
            provider=self.name,
            title=playlist_title,
            tracks=tracks,
            is_single=False,
            image_url=info.get("thumbnails", [{}])[0].get("url") if info.get("thumbnails") else None
        )
