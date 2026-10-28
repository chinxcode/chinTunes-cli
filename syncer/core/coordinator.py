"""Sync pipeline coordinator and track processor with graceful shutdown and clean metadata resolution."""

import os
import time
import subprocess
import urllib.request
import threading
from typing import List, Optional

import yt_dlp

from syncer.core.models import TrackMetadata, LyricsData, SyncProcessResult, clean_artist_name
from syncer.core.config import ConfigManager
from syncer.providers.registry import ProviderRegistry
from syncer.tagging.lyrics import LyricsEngine
from syncer.tagging.tagger import MetadataTagger


class SyncCoordinator:
    def __init__(self, config_manager: ConfigManager, registry: Optional[ProviderRegistry] = None):
        self.config_manager = config_manager
        self.registry = registry or ProviderRegistry()
        self.lyrics_engine = LyricsEngine()
        self._stop_event = threading.Event()

    def request_stop(self):
        """Signals worker threads to stop processing new items immediately."""
        self._stop_event.set()

    def reset_stop(self):
        self._stop_event.clear()

    @property
    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    def process_track(
        self,
        track: TrackMetadata,
        download_dir: str,
        pacing_delay: float = 0.0
    ) -> SyncProcessResult:
        if self._stop_event.is_set():
            return SyncProcessResult(
                track_id=track.id,
                title=track.title,
                artist=track.artist,
                album=track.album,
                success=False,
                error="Cancelled by user"
            )

        cfg = self.config_manager.data
        audio_format = cfg.get("audio_format", "mp3")
        audio_quality = cfg.get("audio_quality", "0")

        if pacing_delay > 0:
            sleep_step = 0.1
            slept = 0.0
            while slept < pacing_delay:
                if self._stop_event.is_set():
                    return SyncProcessResult(
                        track_id=track.id,
                        title=track.title,
                        artist=track.artist,
                        album=track.album,
                        success=False,
                        error="Cancelled by user"
                    )
                time.sleep(sleep_step)
                slept += sleep_step

        audio_downloaded = False
        source_used = track.provider
        jio_matched_id = None
        matched_artist = track.artist

        # 1. High-Fidelity JioSaavn 320k Direct Stream (Near-0% CPU, direct HTTP stream)
        if cfg.get("prefer_jiosaavn_320k", True) and not self._stop_event.is_set():
            cdn_url = track.cdn_url
            if not cdn_url and source_used in ("youtube", "spotify"):
                matches = self.registry.jiosaavn.search_songs(f"{track.title} {track.artist}".strip(), limit=3)
                if matches and matches[0].cdn_url:
                    cdn_url = matches[0].cdn_url
                    jio_matched_id = matches[0].id
                    if matches[0].artist and matches[0].artist != "Unknown":
                        matched_artist = matches[0].artist
                    if not track.album or track.album == track.title:
                        track.album = matches[0].album
                    track.year = track.year or matches[0].year
                    track.duration = track.duration or matches[0].duration

            if cdn_url and not self._stop_event.is_set():
                track.artist = clean_artist_name(matched_artist)
                normalize_needed = cfg.get("normalize_loudness", False)
                fast_copy = cfg.get("fast_stream_copy", True)

                # If user selected m4a/aac or if fast_stream_copy without loudnorm is enabled
                if (audio_format in ("m4a", "mp4", "aac") or (fast_copy and not normalize_needed and audio_format == "m4a")) and not normalize_needed:
                    target_ext = "m4a"
                    final_filename = f"{track.safe_filename_base}.{target_ext}"
                    final_file = os.path.join(download_dir, final_filename)
                    try:
                        req = urllib.request.Request(cdn_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=30) as resp, open(final_file, "wb") as out_f:
                            while True:
                                if self._stop_event.is_set():
                                    break
                                chunk = resp.read(65536)
                                if not chunk:
                                    break
                                out_f.write(chunk)
                        if os.path.exists(final_file) and os.path.getsize(final_file) > 10000:
                            audio_downloaded = True
                            source_used = "jiosaavn_320k"
                            audio_format = target_ext
                    except Exception:
                        audio_downloaded = False
                else:
                    # FFmpeg stream transcode (MP3 or FLAC, or when loudnorm requested)
                    final_filename = f"{track.safe_filename_base}.{audio_format}"
                    final_file = os.path.join(download_dir, final_filename)
                    ffmpeg_args = [
                        "ffmpeg", "-y", "-hide_banner", "-loglevel", "quiet",
                        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                        "-i", cdn_url
                    ]
                    if normalize_needed:
                        ffmpeg_args.extend(["-af", "loudnorm=I=-16:LRA=11:TP=-1.5"])

                    if audio_format == "mp3":
                        bitrate = "320k" if audio_quality in ("320k", "0") else "256k"
                        ffmpeg_args.extend(["-c:a", "libmp3lame", "-b:a", bitrate, final_file])
                    elif audio_format in ("m4a", "mp4"):
                        ffmpeg_args.extend(["-c:a", "copy", final_file])
                    else:
                        ffmpeg_args.extend(["-c:a", "flac", final_file])

                    try:
                        proc = subprocess.run(ffmpeg_args, timeout=60)
                        if proc.returncode == 0 and os.path.exists(final_file) and os.path.getsize(final_file) > 10000:
                            audio_downloaded = True
                            source_used = "jiosaavn_320k"
                    except Exception:
                        audio_downloaded = False

        # 2. Fallback to yt-dlp (Fast stream copy when m4a or zero-transcode enabled)
        if not audio_downloaded and not self._stop_event.is_set():
            normalize_needed = cfg.get("normalize_loudness", False)
            fast_copy = cfg.get("fast_stream_copy", True)

            out_template = os.path.join(download_dir, f"%(title)s - %(artist,creator,uploader)s - [{track.id}].%(ext)s")
            postprocessor_args = {}
            if normalize_needed:
                postprocessor_args["ffmpeg"] = ["-af", "loudnorm=I=-16:LRA=11:TP=-1.5"]

            # When m4a is selected and loudness normalization is not requested, use zero-transcoding copy!
            if audio_format == "m4a" and not normalize_needed:
                postprocessors = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }]
                fmt_selector = "bestaudio[ext=m4a]/bestaudio/best"
            else:
                postprocessors = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                    "preferredquality": audio_quality,
                }]
                fmt_selector = "bestaudio/best"

            ydl_opts = {
                "format": fmt_selector,
                "postprocessors": postprocessors,
                "postprocessor_args": postprocessor_args,
                "outtmpl": out_template,
                "quiet": True,
                "no_warnings": True,
                "extractor_args": {
                    "youtube": {"player_client": ["ios", "mweb", "web_embedded"]}
                },
                "remote_components": ["ejs:github"],
                "retries": 3,
            }

            target_url = track.web_url or f"ytsearch1:{track.title} {track.artist} audio"
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(target_url, download=True)
                    if "entries" in info:
                        info = info["entries"][0]
                    raw_title = info.get("title") or track.title
                    raw_artist = info.get("artist") or info.get("creator") or info.get("uploader") or track.artist
                    desc = info.get("description", "")
                    track.title = raw_title
                    track.artist = clean_artist_name(raw_artist, description=desc)
                    track.album = info.get("album") or track.album
                    track.duration = info.get("duration") or track.duration
                    source_used = "youtube"

                expected_suffix = f"[{track.id}].{audio_format}"
                for fname in os.listdir(download_dir):
                    if fname.endswith(expected_suffix):
                        actual_found = os.path.join(download_dir, fname)
                        desired_name = f"{track.safe_filename_base}.{audio_format}"
                        desired_path = os.path.join(download_dir, desired_name)
                        if actual_found != desired_path:
                            try:
                                os.rename(actual_found, desired_path)
                                final_file = desired_path
                            except Exception:
                                final_file = actual_found
                        else:
                            final_file = desired_path
                        audio_downloaded = True
                        break
            except Exception as e:
                return SyncProcessResult(
                    track_id=track.id,
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    success=False,
                    error=str(e)
                )

        if self._stop_event.is_set():
            if 'final_file' in locals() and final_file and os.path.exists(final_file):
                try:
                    os.remove(final_file)
                except Exception:
                    pass
            return SyncProcessResult(
                track_id=track.id,
                title=track.title,
                artist=track.artist,
                album=track.album,
                success=False,
                error="Cancelled by user"
            )

        if not audio_downloaded or not os.path.exists(final_file):
            return SyncProcessResult(
                track_id=track.id,
                title=track.title,
                artist=track.artist,
                album=track.album,
                success=False,
                error="Audio extraction failed"
            )

        # 3. Lyrics
        lyrics_res: Optional[LyricsData] = None
        if cfg.get("embed_lyrics", True) and not self._stop_event.is_set():
            lyrics_id = jio_matched_id or (track.id if track.provider == "jiosaavn" else None)
            cb = (lambda: self.registry.jiosaavn.fetch_lyrics(lyrics_id)) if lyrics_id else None
            lyrics_res = self.lyrics_engine.find_lyrics(
                title=track.title,
                artist=track.artist,
                duration=track.duration,
                jiosaavn_lyrics_cb=cb
            )

            if cfg.get("save_lrc_file", False) and lyrics_res and lyrics_res.synced:
                lrc_path = os.path.splitext(final_file)[0] + ".lrc"
                try:
                    with open(lrc_path, "w", encoding="utf-8") as lf:
                        lf.write(lyrics_res.synced)
                except Exception:
                    pass

        # 4. Artwork
        candidates = []
        if track.image_url:
            candidates.append(track.image_url)
        candidates.extend([
            f"https://i.ytimg.com/vi/{track.id}/maxresdefault.jpg",
            f"https://i.ytimg.com/vi/{track.id}/hqdefault.jpg"
        ])
        cover_bytes = MetadataTagger.process_cover_art(
            candidates,
            crop_square=cfg.get("crop_square_thumbnail", True)
        )

        # 5. Embed Tags
        MetadataTagger.embed(
            file_path=final_file,
            audio_format=audio_format,
            track=track,
            lyrics=lyrics_res,
            cover_bytes=cover_bytes
        )

        return SyncProcessResult(
            track_id=track.id,
            title=track.title,
            artist=track.artist,
            album=track.album,
            file_path=final_file,
            duration=track.duration,
            source=source_used,
            lyrics_source=lyrics_res.source if lyrics_res else None,
            has_synced_lyrics=bool(lyrics_res and lyrics_res.has_synced),
            has_thumbnail=bool(cover_bytes),
            synced_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            success=True
        )

    def generate_m3u8(self, download_dir: str, playlist_name: str, ordered_tracks: List[TrackMetadata]):
        m3u8_path = os.path.join(download_dir, f"{playlist_name}.m3u8")
        lines = ["#EXTM3U", f"#PLAYLIST:{playlist_name}"]

        for t in ordered_tracks:
            for fname in sorted(os.listdir(download_dir)):
                if f"[{t.id}]." in fname and not fname.endswith(".lrc") and not fname.endswith(".json") and not fname.endswith(".m3u8"):
                    duration = t.duration or -1
                    lines.append(f"#EXTINF:{duration},{t.title}")
                    lines.append(fname)
                    break

        try:
            with open(m3u8_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass
