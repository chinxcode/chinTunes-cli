"""Tagging, Cover Art cropping, and Metadata injection."""

import os
import subprocess
import urllib.request
from typing import Optional, List

from mutagen.mp3 import MP3
from mutagen.flac import FLAC, Picture
from mutagen.id3 import (
    ID3,
    TIT2,
    TPE1,
    TALB,
    TYER,
    TDRC,
    TRCK,
    USLT,
    SYLT,
    APIC,
    Encoding,
)

from mutagen.mp4 import MP4, MP4Cover

from syncer.core.models import TrackMetadata, LyricsData
from syncer.tagging.lyrics import LyricsEngine

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


class MetadataTagger:
    @staticmethod
    def process_cover_art(
        candidate_urls: List[str],
        crop_square: bool = True
    ) -> Optional[bytes]:
        for url in candidate_urls:
            if not url:
                continue
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = resp.read()
                    if len(data) > 1000:
                        if not crop_square:
                            return data

                        # Pure Python 1:1 square center-crop using Pillow (No FFmpeg needed)
                        try:
                            from PIL import Image
                            import io
                            img = Image.open(io.BytesIO(data))
                            width, height = img.size
                            min_dim = min(width, height)
                            left = (width - min_dim) // 2
                            top = (height - min_dim) // 2
                            right = left + min_dim
                            bottom = top + min_dim
                            cropped = img.crop((left, top, right, bottom))
                            if cropped.mode in ("RGBA", "P"):
                                cropped = cropped.convert("RGB")
                            buf = io.BytesIO()
                            cropped.save(buf, format="JPEG", quality=90)
                            return buf.getvalue()
                        except Exception:
                            return data
            except Exception:
                continue
        return None

    @classmethod
    def embed(
        cls,
        file_path: str,
        audio_format: str,
        track: TrackMetadata,
        lyrics: Optional[LyricsData] = None,
        cover_bytes: Optional[bytes] = None
    ):
        ext = audio_format.lower()
        if ext == "mp3":
            cls._embed_mp3(file_path, track, lyrics, cover_bytes)
        elif ext in ("m4a", "mp4", "aac"):
            cls._embed_m4a(file_path, track, lyrics, cover_bytes)
        elif ext == "flac":
            cls._embed_flac(file_path, track, lyrics, cover_bytes)

    @classmethod
    def _embed_m4a(
        cls,
        file_path: str,
        track: TrackMetadata,
        lyrics: Optional[LyricsData],
        cover_bytes: Optional[bytes]
    ):
        try:
            audio = MP4(file_path)
            audio["\xa9nam"] = [track.title]
            audio["\xa9ART"] = [track.artist]
            audio["\xa9alb"] = [track.album]
            if track.year:
                audio["\xa9day"] = [str(track.year)]
            if track.playlist_index:
                audio["trkn"] = [(int(track.playlist_index), 0)]
            if lyrics and (lyrics.plain or lyrics.synced):
                audio["\xa9lyr"] = [lyrics.plain or lyrics.synced]
            if cover_bytes:
                audio["covr"] = [MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
        except Exception as e:
            print(f"Warning: could not write M4A tags to {file_path}: {e}")

    @classmethod
    def _embed_mp3(
        cls,
        file_path: str,
        track: TrackMetadata,
        lyrics: Optional[LyricsData],
        cover_bytes: Optional[bytes]
    ):
        try:
            audio = MP3(file_path, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
            else:
                audio.tags.delall("TIT2")
                audio.tags.delall("TPE1")
                audio.tags.delall("TALB")
                audio.tags.delall("USLT")
                audio.tags.delall("SYLT")

            audio.tags.add(TIT2(encoding=Encoding.UTF8, text=track.title))
            audio.tags.add(TPE1(encoding=Encoding.UTF8, text=track.artist))
            audio.tags.add(TALB(encoding=Encoding.UTF8, text=track.album))

            if track.year:
                audio.tags.add(TYER(encoding=Encoding.UTF8, text=str(track.year)))
                audio.tags.add(TDRC(encoding=Encoding.UTF8, text=str(track.year)))
            if track.playlist_index:
                audio.tags.add(TRCK(encoding=Encoding.UTF8, text=str(track.playlist_index)))

            if lyrics:
                # Plain lyrics (USLT)
                text = lyrics.plain or lyrics.synced or ""
                if text:
                    audio.tags.add(USLT(encoding=Encoding.UTF8, lang="eng", desc="Lyrics", text=text))

                # Synced lyrics (SYLT)
                if lyrics.synced:
                    sylt_entries = LyricsEngine.parse_lrc_to_sylt(lyrics.synced)
                    if sylt_entries:
                        audio.tags.add(SYLT(
                            encoding=Encoding.UTF8,
                            lang="eng",
                            format=2,
                            type=1,
                            desc="Synced Lyrics",
                            text=sylt_entries
                        ))

            if cover_bytes:
                audio.tags.delall("APIC")
                audio.tags.add(APIC(
                    encoding=Encoding.LATIN1,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=cover_bytes
                ))

            audio.save(v2_version=3)
        except Exception as e:
            print(f"Warning: could not write ID3 tags to {file_path}: {e}")

    @classmethod
    def _embed_flac(
        cls,
        file_path: str,
        track: TrackMetadata,
        lyrics: Optional[LyricsData],
        cover_bytes: Optional[bytes]
    ):
        try:
            audio = FLAC(file_path)
            audio["title"] = track.title
            audio["artist"] = track.artist
            audio["album"] = track.album
            if track.year:
                audio["date"] = str(track.year)
            if track.playlist_index:
                audio["tracknumber"] = str(track.playlist_index)
            if lyrics and (lyrics.plain or lyrics.synced):
                audio["lyrics"] = lyrics.plain or lyrics.synced

            if cover_bytes:
                audio.clear_pictures()
                pic = Picture()
                pic.type = 3
                pic.mime = "image/jpeg"
                pic.desc = "Cover"
                pic.data = cover_bytes
                audio.add_picture(pic)

            audio.save()
        except Exception as e:
            print(f"Warning: could not write FLAC tags to {file_path}: {e}")
