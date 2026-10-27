"""JioSaavn provider implementation."""

import base64
import html
import json
import urllib.parse
import urllib.request
from typing import Optional, List, Dict, Any
from Cryptodome.Cipher import DES

from syncer.core.models import TrackMetadata, CollectionResult
from syncer.providers.base import BaseProvider

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
DES_KEY = b"38346591"


class JioSaavnProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "jiosaavn"

    def can_handle(self, url: str) -> bool:
        url_lower = url.lower()
        return "jiosaavn.com" in url_lower or "saavn.com" in url_lower

    @staticmethod
    def decrypt_cdn_url(encrypted_media_url: str) -> Optional[str]:
        if not encrypted_media_url:
            return None
        try:
            des = DES.new(DES_KEY, DES.MODE_ECB)
            enc_bytes = base64.b64decode(encrypted_media_url)
            dec_bytes = des.decrypt(enc_bytes)
            pad_len = dec_bytes[-1]
            return dec_bytes[:-pad_len].decode("utf-8")
        except Exception:
            return None

    @staticmethod
    def upgrade_to_320k(raw_cdn_url: str) -> str:
        if not raw_cdn_url:
            return ""
        for token in ["_96.mp4", "_160.mp4"]:
            if token in raw_cdn_url:
                return raw_cdn_url.replace(token, "_320.mp4")
        if raw_cdn_url.endswith(".mp4") and "_320" not in raw_cdn_url:
            return raw_cdn_url.replace(".mp4", "_320.mp4")
        return raw_cdn_url

    def _normalize_track(self, item: Dict[str, Any], idx: int = 1) -> TrackMetadata:
        title = html.unescape(item.get("title", "")).strip()
        more_info = item.get("more_info", {})
        artist = html.unescape(item.get("subtitle") or more_info.get("music") or "").strip()
        album = html.unescape(more_info.get("album") or title).strip()

        enc_url = more_info.get("encrypted_media_url")
        raw_cdn = self.decrypt_cdn_url(enc_url)
        cdn_320 = self.upgrade_to_320k(raw_cdn)

        image_url = item.get("image", "")
        if image_url:
            image_url = image_url.replace("150x150", "500x500").replace("50x50", "500x500")

        duration_val = more_info.get("duration")
        duration = int(duration_val) if duration_val and str(duration_val).isdigit() else None

        return TrackMetadata(
            id=str(item.get("id")),
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            year=str(item.get("year") or ""),
            image_url=image_url,
            cdn_url=cdn_320,
            web_url=item.get("perma_url"),
            playlist_index=idx,
            provider=self.name,
            extra_data={"has_lyrics": str(more_info.get("has_lyrics", "")).lower() == "true"}
        )

    def search_songs(self, query: str, limit: int = 5) -> List[TrackMetadata]:
        endpoint = (
            f"https://www.jiosaavn.com/api.php?p=1&q={urllib.parse.quote(query)}"
            f"&_format=json&_marker=0&api_version=4&ctx=wap6dot0&n={limit}&__call=search.getResults"
        )
        req = urllib.request.Request(endpoint, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                results = data.get("results", [])
                return [self._normalize_track(item, idx + 1) for idx, item in enumerate(results)]
        except Exception:
            return []

    def fetch_lyrics(self, song_id: str) -> Optional[str]:
        endpoint = f"https://www.jiosaavn.com/api.php?__call=lyrics.getLyrics&lyrics_id={song_id}&ctx=web6dot0&api_version=4&_format=json"
        req = urllib.request.Request(endpoint, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                raw_lyr = data.get("lyrics")
                if raw_lyr:
                    clean = raw_lyr.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
                    return html.unescape(clean).strip()
        except Exception:
            pass
        return None

    def fetch_collection(self, url: str) -> Optional[CollectionResult]:
        token = url.strip().rstrip("/").split("/")[-1]
        url_lower = url.lower()

        # 1. Single Song
        if "/song/" in url_lower:
            endpoint = (
                f"https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}&type=song"
                f"&includeMetaTags=0&ctx=web6dot0&api_version=4&_format=json&_marker=0"
            )
            req = urllib.request.Request(endpoint, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    songs = data.get("songs", [])
                    if songs:
                        track = self._normalize_track(songs[0], 1)
                        return CollectionResult(
                            provider=self.name,
                            title=track.title,
                            tracks=[track],
                            is_single=True,
                            image_url=track.image_url
                        )
            except Exception:
                pass
            return None

        # 2. Album or Playlist
        col_type = "album" if "/album/" in url_lower else "playlist"
        endpoint = (
            f"https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}&type={col_type}"
            f"&p=1&n=250&includeMetaTags=0&ctx=wap6dot0&api_version=4&_format=json&_marker=0"
        )
        req = urllib.request.Request(endpoint, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                if not data or not data.get("title"):
                    return None

                title = html.unescape(data.get("title", "")).strip()
                raw_list = data.get("list", [])
                tracks = [self._normalize_track(item, idx + 1) for idx, item in enumerate(raw_list)]
                return CollectionResult(
                    provider=self.name,
                    title=title,
                    tracks=tracks,
                    is_single=False,
                    header_desc=html.unescape(data.get("header_desc") or "").strip(),
                    image_url=data.get("image")
                )
        except Exception:
            return None
