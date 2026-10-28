"""Local MP3 & Audio Library Matcher and Tagger.

Scans local audio collections, cleans up filenames and messy ID3 metadata,
intelligently matches against high-authority music databases (iTunes & JioSaavn),
fetches 1:1 high-resolution square artwork, and embeds missing synchronized lyrics (.lrc).
"""

import os
import re
import io
import json
import html
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

import mutagen
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from PIL import Image

from syncer.core.models import TrackMetadata
from syncer.tagging.lyrics import LyricsEngine, LyricsData
from syncer.tagging.tagger import MetadataTagger

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


@dataclass
class MatchResult:
    original_path: str
    filename: str
    detected_title: str
    detected_artist: str
    matched_title: str
    matched_artist: str
    matched_album: str
    matched_year: Optional[int]
    artwork_url: Optional[str]
    has_synced_lyrics: bool
    confidence: float  # 0.0 to 1.0


class LibraryMatcher:
    """Matches messy local music files with clean metadata, covers, and synced lyrics."""

    SUPPORTED_EXTENSIONS = (
        ".mp3", ".m4a", ".mp4", ".flac", ".aac", ".ogg", ".opus",
        ".wav", ".wave", ".aif", ".aiff", ".alac", ".wma", ".webm"
    )

    def __init__(self):
        self.lyrics_engine = LyricsEngine()

    @staticmethod
    def sanitize_search_query(text: str) -> str:
        """Strips junk tokens from filenames (e.g. 320kbps, PagalWorld, official video, [id])."""
        # Remove bracketed/parenthesized video or platform tags
        cleaned = re.sub(r"\[.*?\]", "", text)
        cleaned = re.sub(r"\(.*?(?:official|video|audio|lyrics|hd|remix|feat|ft\.).*?\)", "", cleaned, flags=re.IGNORECASE)

        # Remove domain names e.g. pagalworld.com, mp3song.cc, etc.
        cleaned = re.sub(r"(?:https?://)?(?:www\.)?[a-zA-Z0-9_\-]+\.(?:com|in|co|org|net|cc|pk|me|link|site|info)", "", cleaned, flags=re.IGNORECASE)

        # Remove common web scraper / pirate site names and bitrates
        junk_patterns = [
            r"\b320kbps\b", r"\b128kbps\b", r"\b192kbps\b", r"\b256kbps\b", r"\bkbps\b",
            r"\bpagalworld\b", r"\bdjpunjab\b", r"\bmp3mad\b", r"\bsongspk\b", r"\bwapking\b",
            r"\bdownloadming\b", r"\bpendujatt\b", r"\bnaasongs\b", r"\bgaana\b", r"\bjiosaavn\b",
            r"\bfull song\b", r"\bofficial music video\b", r"\bofficial video\b", r"\baudio song\b",
            r"\blyric video\b", r"\bofficial audio\b", r"\blyrics\b"
        ]
        for pat in junk_patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

        # Remove track numbers like 01., 02 -, etc. at the start
        cleaned = re.sub(r"^\s*\d+[\s\.\-_]+", "", cleaned)

        # Replace underscores, multiple dashes with clean single space
        cleaned = cleaned.replace("_", " ")
        cleaned = re.sub(r"\s*-\s*", " - ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip(" -_")
        return cleaned

    def inspect_file(self, file_path: str) -> Tuple[str, str, str, float]:
        """
        Reads existing audio tags and duration.
        Returns (title, artist, album, duration_seconds).
        """
        title = ""
        artist = ""
        album = ""
        duration = 0.0

        filename = os.path.basename(file_path)
        base_name, _ = os.path.splitext(filename)

        try:
            mf = mutagen.File(file_path)
            if mf and mf.info and hasattr(mf.info, "length"):
                duration = float(mf.info.length)

            if mf:
                # 1. MP3 ID3 Tags
                if hasattr(mf, "tags") and mf.tags:
                    for k in ("TIT2", "title"):
                        if k in mf.tags:
                            title = str(mf.tags[k])
                            break
                    for k in ("TPE1", "artist"):
                        if k in mf.tags:
                            artist = str(mf.tags[k])
                            break
                    for k in ("TALB", "album"):
                        if k in mf.tags:
                            album = str(mf.tags[k])
                            break

                # 2. MP4 / M4A Atoms
                if not title and "©nam" in mf:
                    v = mf["©nam"]
                    title = v[0] if isinstance(v, list) else str(v)
                if not artist and "©ART" in mf:
                    v = mf["©ART"]
                    artist = v[0] if isinstance(v, list) else str(v)
                if not album and "©alb" in mf:
                    v = mf["©alb"]
                    album = v[0] if isinstance(v, list) else str(v)

                # 3. Vorbis Comments (FLAC, Ogg, Opus)
                if not title and "title" in mf:
                    v = mf["title"]
                    title = v[0] if isinstance(v, list) else str(v)
                if not artist and "artist" in mf:
                    v = mf["artist"]
                    artist = v[0] if isinstance(v, list) else str(v)
                if not album and "album" in mf:
                    v = mf["album"]
                    album = v[0] if isinstance(v, list) else str(v)
        except Exception:
            pass

        # If tags are missing or generic junk, derive from filename
        if not title:
            clean_base = self.sanitize_search_query(base_name)
            if " - " in clean_base:
                parts = clean_base.split(" - ", 1)
                title = parts[0].strip()
                artist = artist or parts[1].strip()
            else:
                title = clean_base

        title = self.sanitize_search_query(title)
        artist = self.sanitize_search_query(artist)
        return title, artist, album, duration

    def query_itunes(self, title: str, artist: str = "") -> Optional[Dict[str, Any]]:
        """Queries Apple iTunes Music Search API for CD-master metadata and hi-res artwork."""
        query = f"{artist} {title}".strip() if artist else title
        encoded_q = urllib.parse.quote(query)
        url = f"https://itunes.apple.com/search?term={encoded_q}&media=music&entity=song&limit=5"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                results = data.get("results", [])
                if not results:
                    return None

                best = results[0]
                art_100 = best.get("artworkUrl100", "")
                hires_art = art_100.replace("100x100bb.jpg", "1400x1400bb.jpg") if art_100 else None

                year = None
                release_date = best.get("releaseDate")
                if release_date and len(release_date) >= 4:
                    try:
                        year = int(release_date[:4])
                    except ValueError:
                        pass

                return {
                    "title": best.get("trackName"),
                    "artist": best.get("artistName"),
                    "album": best.get("collectionName"),
                    "year": year,
                    "artwork_url": hires_art,
                    "preview_url": best.get("previewUrl")
                }
        except Exception:
            return None

    def query_jiosaavn(self, title: str, artist: str = "") -> Optional[Dict[str, Any]]:
        """Queries JioSaavn search autocomplete for studio masters and covers."""
        query = f"{artist} {title}".strip() if artist else title
        encoded_q = urllib.parse.quote(query)
        url = f"https://www.jiosaavn.com/api.php?__call=autocomplete.get&_format=json&_marker=0&cc=in&includeMetaTags=1&query={encoded_q}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                songs = data.get("songs", {}).get("data", [])
                if not songs:
                    return None

                best = songs[0]
                raw_img = best.get("image", "")
                hires_art = raw_img.replace("50x50.jpg", "500x500.jpg").replace("150x150.jpg", "500x500.jpg") if raw_img else None

                raw_title = html.unescape(best.get("title", ""))
                more_info = best.get("more_info", {})
                raw_artist = html.unescape(
                    more_info.get("primary_artists") or
                    more_info.get("singers") or
                    more_info.get("music") or
                    (best.get("description", "").split("·")[-1].strip() if "·" in best.get("description", "") else "") or
                    ""
                )
                raw_album = html.unescape(best.get("album") or more_info.get("album") or raw_title)

                year = None
                if more_info.get("year"):
                    try:
                        year = int(more_info["year"])
                    except ValueError:
                        pass

                return {
                    "title": raw_title,
                    "artist": raw_artist,
                    "album": raw_album,
                    "year": year,
                    "artwork_url": hires_art,
                }
        except Exception:
            return None

    def query_youtube(self, title: str, artist: str = "") -> Optional[Dict[str, Any]]:
        """Queries YouTube via yt-dlp search for track title, artist, and maxres thumbnail."""
        query = f"{artist} {title} audio".strip() if artist else f"{title} audio"
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
            "no_warnings": True,
        }
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                res = ydl.extract_info(f"ytsearch1:{query}", download=False)
                entries = res.get("entries", [])
                if not entries or not entries[0]:
                    return None

                best = entries[0]
                raw_title = best.get("title", "")
                clean_title = self.sanitize_search_query(raw_title)

                uploader = best.get("uploader") or best.get("channel") or ""
                clean_uploader = re.sub(r"(?:VEVO|Topic|Official)$", "", uploader, flags=re.IGNORECASE).strip()

                if " - " in clean_title:
                    parts = clean_title.split(" - ", 1)
                    parsed_artist = parts[0].strip()
                    parsed_title = parts[1].strip()
                else:
                    parsed_title = clean_title
                    parsed_artist = clean_uploader or artist

                # Thumbnail resolution
                thumb = best.get("thumbnail")
                if not thumb and best.get("thumbnails"):
                    thumb = best["thumbnails"][-1].get("url")

                # If youtube ID present, build maxres default candidate
                vid_id = best.get("id")
                if vid_id and ("i.ytimg.com" in (thumb or "") or not thumb):
                    thumb = f"https://i.ytimg.com/vi/{vid_id}/maxresdefault.jpg"

                year = None
                upload_date = best.get("upload_date")
                if upload_date and len(upload_date) >= 4:
                    try:
                        year = int(upload_date[:4])
                    except ValueError:
                        pass

                return {
                    "title": parsed_title or title,
                    "artist": parsed_artist or artist,
                    "album": parsed_title or title,
                    "year": year,
                    "artwork_url": thumb,
                }
        except Exception:
            return None

    def match_track(self, file_path: str) -> MatchResult:
        """Performs full acoustic/textual match for a single local audio track."""
        filename = os.path.basename(file_path)
        d_title, d_artist, d_album, duration = self.inspect_file(file_path)

        match_data = self.query_itunes(d_title, d_artist)
        if not match_data:
            match_data = self.query_jiosaavn(d_title, d_artist)
        if not match_data:
            match_data = self.query_youtube(d_title, d_artist)

        if match_data:
            m_title = match_data["title"] or d_title
            m_artist = match_data["artist"] or d_artist
            m_album = match_data["album"] or d_album
            m_year = match_data["year"]
            m_art = match_data["artwork_url"]
            confidence = 0.95 if match_data.get("year") else 0.85
        else:
            m_title = d_title
            m_artist = d_artist
            m_album = d_album or d_title
            m_year = None
            m_art = None
            confidence = 0.50

        # Check lyrics availability
        has_synced = False
        lrc_path = os.path.splitext(file_path)[0] + ".lrc"
        if os.path.exists(lrc_path):
            has_synced = True

        return MatchResult(
            original_path=file_path,
            filename=filename,
            detected_title=d_title,
            detected_artist=d_artist,
            matched_title=m_title,
            matched_artist=m_artist,
            matched_album=m_album,
            matched_year=m_year,
            artwork_url=m_art,
            has_synced_lyrics=has_synced,
            confidence=confidence
        )

    def process_and_repair_track(
        self,
        match: MatchResult,
        save_lrc: bool = True,
        rename_file: bool = False
    ) -> bool:
        """
        Embeds cleaned tags, square artwork, and synced lyrics into the target audio file.
        Optionally renames the file into 'Title - Artist.ext'.
        """
        file_path = match.original_path
        ext = os.path.splitext(file_path)[-1].lower().lstrip(".")

        track_meta = TrackMetadata(
            id=re.sub(r"[^a-zA-Z0-9_\-]", "", match.matched_title)[:32],
            title=match.matched_title,
            artist=match.matched_artist,
            album=match.matched_album,
            year=match.matched_year
        )

        # 1. Fetch & Crop Cover Artwork
        cover_bytes = None
        if match.artwork_url:
            cover_bytes = MetadataTagger.process_cover_art([match.artwork_url], crop_square=True)

        # 2. Fetch Synced Lyrics
        lyrics_data = self.lyrics_engine.find_lyrics(
            title=match.matched_title,
            artist=match.matched_artist,
        )

        # Write .lrc file if synced lyrics obtained
        if save_lrc and lyrics_data and lyrics_data.synced:
            lrc_file = os.path.splitext(file_path)[0] + ".lrc"
            try:
                with open(lrc_file, "w", encoding="utf-8") as lf:
                    lf.write(lyrics_data.synced)
            except Exception:
                pass

        # 3. Embed tags into audio container
        MetadataTagger.embed(
            file_path=file_path,
            audio_format=ext,
            track=track_meta,
            lyrics=lyrics_data,
            cover_bytes=cover_bytes
        )

        # 4. Optional Clean Rename
        if rename_file:
            safe_title = re.sub(r'[\/\\:\*\?"<>\|]', "", match.matched_title).strip()
            safe_artist = re.sub(r'[\/\\:\*\?"<>\|]', "", match.matched_artist).strip()
            if safe_artist:
                new_filename = f"{safe_title} - {safe_artist}.{ext}"
            else:
                new_filename = f"{safe_title}.{ext}"

            dir_path = os.path.dirname(file_path)
            new_path = os.path.join(dir_path, new_filename)
            if new_path != file_path and not os.path.exists(new_path):
                try:
                    os.rename(file_path, new_path)
                    # Also rename .lrc if exists
                    old_lrc = os.path.splitext(file_path)[0] + ".lrc"
                    new_lrc = os.path.splitext(new_path)[0] + ".lrc"
                    if os.path.exists(old_lrc):
                        os.rename(old_lrc, new_lrc)
                except Exception:
                    pass

        return True
