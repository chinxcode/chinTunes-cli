"""Spotify Provider implementation using Spotify oEmbed and embed API."""

import json
import re
import urllib.parse
import urllib.request
from typing import Optional

from syncer.core.models import TrackMetadata, CollectionResult
from syncer.providers.base import BaseProvider

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


class SpotifyProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "spotify"

    def can_handle(self, url: str) -> bool:
        return "spotify.com" in url.lower()

    def fetch_collection(self, url: str) -> Optional[CollectionResult]:
        url_lower = url.lower()
        if "/track/" in url_lower:
            track_id = url.split("/track/")[1].split("?")[0]
            clean_track_url = f"https://open.spotify.com/track/{track_id}"

            title = "Spotify Track"
            artist = "Unknown Artist"
            image_url = None

            # 1. Use official Spotify oEmbed endpoint for reliable title & artwork
            oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_track_url)}"
            req = urllib.request.Request(oembed_url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    if data.get("title"):
                        title = data["title"]
                    if data.get("thumbnail_url"):
                        image_url = data["thumbnail_url"]
            except Exception:
                pass

            # 2. Extract Artist from Spotify embed page
            embed_url = f"https://open.spotify.com/embed/track/{track_id}"
            ereq = urllib.request.Request(embed_url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(ereq, timeout=8) as eresp:
                    ehtml = eresp.read().decode("utf-8", errors="ignore")
                    artist_match = re.search(r'\"artists\":\[\{\"name\":\"([^\"]+)\"', ehtml)
                    if artist_match:
                        artist = artist_match.group(1)
            except Exception:
                pass

            track = TrackMetadata(
                id=track_id,
                title=title.strip(),
                artist=artist.strip(),
                album=title.strip(),
                image_url=image_url,
                web_url=clean_track_url,
                provider=self.name
            )
            return CollectionResult(
                provider=self.name,
                title=title,
                tracks=[track],
                is_single=True,
                image_url=image_url
            )

        return None
