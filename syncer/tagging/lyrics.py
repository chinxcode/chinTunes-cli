"""Multi-Tiered Lyrics Fetching and Parsing Engine."""

import re
import urllib.parse
import requests
from typing import Optional, List, Tuple
import syncedlyrics

from syncer.core.models import LyricsData

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def strip_lrc_timestamps(synced_text: Optional[str]) -> Optional[str]:
    """Extracts plain text lines from synchronized [mm:ss.xx] LRC formatted lyrics."""
    if not synced_text:
        return None
    lines = []
    for line in synced_text.splitlines():
        cleaned = re.sub(r"\[\d{2}:\d{2}(?:\.\d{2,3})?\]", "", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines) if lines else None


class LyricsEngine:
    @staticmethod
    def sanitize(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"\(official[^\)]*\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[official[^\]]*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\(audio[^\)]*\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[audio[^\]]*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\(music\s+video\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\(lyric[^\)]*\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[lyric[^\]]*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\(video\)", "", text, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def get_artist_variants(artist_str: str) -> List[str]:
        if not artist_str:
            return []
        variants = [artist_str.strip()]
        tokens = re.split(r"[,/&]|(?:\s+feat\.?\s+)|\s+ft\.?\s+|\s+with\s+", artist_str, flags=re.IGNORECASE)
        for token in [t.strip() for t in tokens if t.strip()]:
            if token not in variants:
                variants.append(token)
        return variants

    @staticmethod
    def parse_lrc_to_sylt(lrc_text: str) -> List[Tuple[str, int]]:
        sylt_entries = []
        line_regex = re.compile(r"\[(\d{2}):(\d{2})(?:\.(\d{2,3}))?\](.*)")
        for line in lrc_text.splitlines():
            match = line_regex.match(line.strip())
            if match:
                mins = int(match.group(1))
                secs = int(match.group(2))
                millis_str = match.group(3) or "0"
                millis = int(millis_str) if len(millis_str) == 3 else int(millis_str) * 10
                total_ms = (mins * 60 + secs) * 1000 + millis
                text = match.group(4).strip()
                if text:
                    sylt_entries.append((text, total_ms))
        return sylt_entries

    def query_lrclib(self, title: str, artist: Optional[str] = None, duration: Optional[int] = None) -> Optional[LyricsData]:
        headers = {"User-Agent": USER_AGENT}
        if duration and artist:
            try:
                params = {"track_name": title, "artist_name": artist, "duration": round(duration)}
                resp = requests.get("https://lrclib.net/api/get", params=params, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    synced = data.get("syncedLyrics")
                    plain = data.get("plainLyrics") or strip_lrc_timestamps(synced)
                    if synced or plain:
                        return LyricsData(
                            plain=plain,
                            synced=synced,
                            source="LRCLIB (Exact Match)"
                        )
            except Exception:
                pass

        try:
            params = {"track_name": title}
            if artist:
                params["artist_name"] = artist
            resp = requests.get("https://lrclib.net/api/search", params=params, headers=headers, timeout=6)
            if resp.status_code == 200 and resp.json():
                # 1st preference in results: item with synced lyrics
                for item in resp.json():
                    synced = item.get("syncedLyrics")
                    if synced:
                        plain = item.get("plainLyrics") or strip_lrc_timestamps(synced)
                        return LyricsData(
                            plain=plain,
                            synced=synced,
                            source="LRCLIB (Synced)"
                        )
                # 2nd preference in results: item with plain lyrics
                for item in resp.json():
                    if item.get("plainLyrics"):
                        return LyricsData(
                            plain=item["plainLyrics"],
                            synced=None,
                            source="LRCLIB (Plain)"
                        )
        except Exception:
            pass
        return None

    def query_cascade(self, query: str) -> Optional[LyricsData]:
        clean_q = self.sanitize(query)
        for provider in ["musixmatch", "netease", "genius"]:
            try:
                lrc = syncedlyrics.search(clean_q, providers=[provider])
                if lrc:
                    is_synced = bool(re.search(r"\[\d{2}:\d{2}", lrc))
                    if is_synced:
                        plain = strip_lrc_timestamps(lrc)
                        return LyricsData(
                            plain=plain,
                            synced=lrc,
                            source=provider.upper()
                        )
                    else:
                        return LyricsData(
                            plain=lrc,
                            synced=None,
                            source=provider.upper()
                        )
            except Exception:
                continue
        return None

    def find_lyrics(
        self,
        title: str,
        artist: str,
        duration: Optional[int] = None,
        jiosaavn_lyrics_cb=None
    ) -> Optional[LyricsData]:
        """
        Hierarchical Priority Strategy:
        1. Both Synced & Normal Lyrics (High-Fidelity full package)
        2. Synced Lyrics only (auto-deriving clean normal lyrics from timed lines)
        3. Normal plain lyrics only (JioSaavn official / LRCLIB plain / Musixmatch / Genius)
        4. None (No lyrics found)
        """
        clean_title = self.sanitize(title)
        variants = self.get_artist_variants(artist)

        # -------------------------------------------------------------
        # TIER 1 & 2: Search for Synced Lyrics (LRCLIB -> SyncedLyrics cascade)
        # Guarantees both SYLT (timed) and USLT (plain) tags are generated
        # -------------------------------------------------------------
        for art in variants:
            res = self.query_lrclib(clean_title, art, duration)
            if res and res.has_synced:
                # Ensure plain lyrics exist
                if not res.plain:
                    res.plain = strip_lrc_timestamps(res.synced)
                return res

        # Check cascade providers (Musixmatch / NetEase) for synced lyrics
        for art in variants:
            res = self.query_cascade(f"{clean_title} {art}".strip())
            if res and res.has_synced:
                if not res.plain:
                    res.plain = strip_lrc_timestamps(res.synced)
                return res

        # Try title alone for synced cascade
        res = self.query_cascade(clean_title)
        if res and res.has_synced:
            if not res.plain:
                res.plain = strip_lrc_timestamps(res.synced)
            return res

        # -------------------------------------------------------------
        # TIER 3: Fallback to Normal / Plain Lyrics
        # (JioSaavn Official Studio Lyrics -> LRCLIB Plain -> Scraper Plain)
        # -------------------------------------------------------------
        if jiosaavn_lyrics_cb:
            try:
                native_lyr = jiosaavn_lyrics_cb()
                if native_lyr and len(native_lyr.strip()) > 10:
                    return LyricsData(plain=native_lyr.strip(), synced=None, source="JIOSAAVN")
            except Exception:
                pass

        for art in variants:
            res = self.query_lrclib(clean_title, art, duration)
            if res and res.plain:
                return res

        # -------------------------------------------------------------
        # TIER 4: None
        # -------------------------------------------------------------
        return None
