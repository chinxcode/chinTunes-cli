"""High-fidelity real-time terminal audio player with synchronized karaoke lyrics and smooth controls."""

import os
import sys
import time
import shutil
import threading
import subprocess
from typing import List, Optional, Tuple

import mutagen
from rich.console import Console
from rich.panel import Panel
from rich.live import Live

from syncer.core.playlist_manager import PlaylistTrackInfo
from syncer.tagging.lyrics import LyricsEngine


class TerminalPlayer:
    """Terminal Mini-Player with live karaoke lyrics, Left/Right seeking, and robust sound playback."""

    def __init__(self, tracks: List[PlaylistTrackInfo], initial_index: int = 0):
        self.tracks = tracks
        self.current_index = initial_index
        self.is_playing = False
        self.is_paused = False
        self.stop_requested = False
        self.volume = 0.8  # Default volume 80%
        self.console = Console()
        self.song_duration = 0.0
        self.playback_offset = 0.0      # Current position offset in seconds
        self.process_start_time = 0.0    # Time when active player process started
        self.synced_lines: List[Tuple[float, str]] = []
        self.plain_lyrics_lines: List[str] = []
        self.show_lyrics: bool = True  # Enabled by default; toggled via 'C' / 'c'
        self._lyrics_engine = LyricsEngine()
        self._proc: Optional[subprocess.Popen] = None
        self._player_cmd = "ffplay" if shutil.which("ffplay") else ("afplay" if shutil.which("afplay") else "mpv")

    def run(self):
        """Starts player loop with Live UI and interactive keyboard thread."""
        if not self.tracks:
            self.console.print("[yellow]No tracks available to play.[/yellow]")
            return

        # Start non-blocking keyboard listener thread
        kbd_thread = threading.Thread(target=self._keyboard_listener, daemon=True)
        kbd_thread.start()

        self._start_track(self.current_index)

        with Live(self._render_ui(), console=self.console, refresh_per_second=6, screen=True) as live:
            while not self.stop_requested:
                if self.is_playing and not self.is_paused: 
                    # Check if process exited naturally (song reached end)
                    if self._proc and self._proc.poll() is not None:
                        if self._proc.returncode == 0 or self._get_current_pos() >= (self.song_duration - 1.5):
                            self._next_track()

                live.update(self._render_ui())
                time.sleep(0.18)

        self._kill_process()
        self.console.print("\n[dim]Playback stopped. Returned to menu.[/dim]\n")

    def _start_track(self, index: int, start_offset: float = 0.0):
        """Launches audio playback from given offset using crystal-clear native engine."""
        if index < 0 or index >= len(self.tracks):
            return

        self._kill_process()
        self.current_index = index
        track = self.tracks[self.current_index]

        try:
            self.song_duration = self._read_duration(track.file_path)
            self._load_track_lyrics(track)
            self.playback_offset = max(0.0, min(start_offset, self.song_duration - 1.0 if self.song_duration > 0 else start_offset))
            self.process_start_time = time.time()
            self.is_paused = False

            # Spawn audio player process
            if self._player_cmd == "ffplay":
                vol = int(self.volume * 100)
                cmd = [
                    "ffplay",
                    "-nodisp",
                    "-autoexit",
                    "-ss", str(int(self.playback_offset)),
                    "-volume", str(vol),
                    "-loglevel", "quiet",
                    track.file_path
                ]
            elif self._player_cmd == "afplay":
                # afplay on macOS
                cmd = [
                    "afplay",
                    "-v", str(round(self.volume, 2)),
                    track.file_path
                ]
            else:
                vol = int(self.volume * 100)
                cmd = [
                    "mpv",
                    "--no-video",
                    f"--start={int(self.playback_offset)}",
                    f"--volume={vol}",
                    track.file_path
                ]

            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.is_playing = True

        except Exception as e:
            self.console.print(f"[red]Error starting playback for {track.filename}: {e}[/red]")
            self._next_track()

    def _kill_process(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=0.15)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def _get_current_pos(self) -> float:
        if not self.is_playing:
            return 0.0
        if self.is_paused:
            return self.playback_offset
        elapsed = time.time() - self.process_start_time
        pos = self.playback_offset + elapsed
        return max(0.0, min(pos, self.song_duration) if self.song_duration > 0 else pos)

    def _toggle_pause(self):
        if not self.is_playing:
            return
        if self.is_paused:
            # Resume: restart playback from paused offset
            self._start_track(self.current_index, start_offset=self.playback_offset)
            self.is_paused = False
        else:
            # Pause: save current offset and kill active process
            self.playback_offset = self._get_current_pos()
            self._kill_process()
            self.is_paused = True

    def _seek(self, delta: float):
        """Peek/Seek forward or backward by delta seconds."""
        current = self._get_current_pos()
        target = max(0.0, current + delta)
        if self.song_duration > 0:
            target = min(target, self.song_duration - 1.0)
        self.playback_offset = target
        if not self.is_paused:
            self._start_track(self.current_index, start_offset=target)

    def _next_track(self):
        next_idx = self.current_index + 1 if (self.current_index + 1 < len(self.tracks)) else 0
        self._start_track(next_idx, start_offset=0.0)

    def _prev_track(self):
        if self._get_current_pos() > 3.5:
            # Restart current track from beginning
            self._start_track(self.current_index, start_offset=0.0)
        elif self.current_index > 0:
            self._start_track(self.current_index - 1, start_offset=0.0)
        else:
            self._start_track(len(self.tracks) - 1, start_offset=0.0)

    def _change_volume(self, delta: float):
        self.volume = max(0.0, min(1.0, round(self.volume + delta, 2)))
        # Re-apply volume if using ffplay/mpv
        if not self.is_paused and self._proc:
            cur = self._get_current_pos()
            self._start_track(self.current_index, start_offset=cur)

    def _read_duration(self, file_path: str) -> float:
        try:
            mf = mutagen.File(file_path)
            if mf and mf.info and hasattr(mf.info, "length"):
                return float(mf.info.length)
        except Exception:
            pass
    def _toggle_lyrics(self):
        """Toggle lyrics display on/off."""
        self.show_lyrics = not self.show_lyrics

    def _read_duration(self, file_path: str) -> float:
        try:
            mf = mutagen.File(file_path)
            if mf and mf.info and hasattr(mf.info, "length"):
                return float(mf.info.length)
        except Exception:
            pass
        return 0.0

    def _load_track_lyrics(self, track: PlaylistTrackInfo):
        """
        Loads synced lyrics and plain lyrics for the track with hierarchical fallback:
        1. Local .lrc file next to track
        2. Embedded tags (©lyr in M4A, USLT/SYLT in MP3, LYRICS in FLAC)
        3. Online search via LyricsEngine (LRCLIB, SyncedLyrics, JioSaavn)
        """
        self.synced_lines = []
        self.plain_lyrics_lines = []

        raw_text = ""
        lrc_path = os.path.splitext(track.file_path)[0] + ".lrc"

        # 1. Check local .lrc file
        if os.path.exists(lrc_path):
            try:
                with open(lrc_path, "r", encoding="utf-8") as f:
                    raw_text = f.read()
            except Exception:
                pass

        # 2. Check embedded tags
        if not raw_text:
            try:
                mf = mutagen.File(track.file_path)
                if mf:
                    # M4A ©lyr or MP3 USLT or FLAC LYRICS
                    lyr = mf.get("©lyr") or mf.get("USLT::eng") or mf.get("LYRICS")
                    if lyr:
                        raw_text = lyr[0] if isinstance(lyr, list) else str(lyr)
                    elif hasattr(mf, "tags") and mf.tags:
                        for tag_k in ("USLT::eng", "USLT::XXX", "USLT", "LYRICS"):
                            if tag_k in mf.tags:
                                raw_text = str(mf.tags[tag_k])
                                break
            except Exception:
                pass

        # 3. If still empty, search online and auto-cache
        if not raw_text:
            try:
                ld = self._lyrics_engine.find_lyrics(
                    title=track.title,
                    artist=track.artist or "",
                    duration=int(self.song_duration) if self.song_duration > 0 else None
                )
                if ld:
                    if ld.synced:
                        raw_text = ld.synced
                        # Auto-save local .lrc file for immediate next load
                        try:
                            with open(lrc_path, "w", encoding="utf-8") as lf:
                                lf.write(ld.synced)
                        except Exception:
                            pass
                    elif ld.plain:
                        raw_text = ld.plain
            except Exception:
                pass

        if not raw_text:
            return

        # Parse raw_text into synced lines or plain lines
        import re
        synced = []
        for line in raw_text.splitlines():
            line_str = line.strip()
            match = re.match(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)", line_str)
            if match:
                mins = int(match.group(1))
                secs = float(match.group(2))
                text = match.group(3).strip()
                if text:
                    synced.append((mins * 60 + secs, text))

        if synced:
            synced.sort(key=lambda x: x[0])
            self.synced_lines = synced
        else:
            # Normal plain lyrics without timestamps
            plain_lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            self.plain_lyrics_lines = plain_lines

    def _render_ui(self) -> Panel:
        """Renders the Rich terminal player interface with live karaoke or plain lyrics."""
        track = self.tracks[self.current_index]
        cur_pos = self._get_current_pos()

        cur_str = time.strftime("%M:%S", time.gmtime(cur_pos))
        dur_str = time.strftime("%M:%S", time.gmtime(self.song_duration)) if self.song_duration > 0 else "--:--"

        ratio = (cur_pos / self.song_duration) if self.song_duration > 0 else 0.0
        bar_len = 32
        filled_len = int(bar_len * max(0.0, min(1.0, ratio)))
        bar = f"[cyan]{'━' * filled_len}[/cyan][dim]{'━' * (bar_len - filled_len)}[/dim]"

        state_badge = "[bold yellow]PAUSED ⏸[/bold yellow]" if self.is_paused else "[bold green]PLAYING ▶[/bold green]"
        vol_pct = int(self.volume * 100)
        vol_badge = f"🔊 {vol_pct}%"

        # Build lyrics section based on show_lyrics toggle
        if not self.show_lyrics:
            lyrics_header = "[dim]── Lyrics: Hidden (Press [bold white]C[/bold white] to show) ──────────────────────────[/dim]"
            lyrics_block = "  [dim](Lyrics display hidden - press [bold white]C[/bold white] to toggle back on)[/dim]"
            lyrics_footer = "[dim]────────────────────────────────────────────────────[/dim]"
        elif self.synced_lines:
            lyrics_header = "[bold bright_blue]── Karaoke Synced Lyrics ────────────────────────────[/bold bright_blue]"
            # Find active karaoke lyric line
            active_idx = -1
            for idx, (t_sec, txt) in enumerate(self.synced_lines):
                if cur_pos >= t_sec:
                    active_idx = idx
                else:
                    break

            # Build 5-line karaoke window: 2 previous, 1 active, 2 upcoming
            lyric_rows = []
            start_l = max(0, active_idx - 2)
            end_l = min(len(self.synced_lines), active_idx + 3)

            for i in range(start_l, end_l):
                t_sec, text = self.synced_lines[i]
                if i == active_idx:
                    lyric_rows.append(f"  [bold bright_yellow]♫  {text}  ♪[/bold bright_yellow]")
                elif i < active_idx:
                    lyric_rows.append(f"  [dim]{text}[/dim]")
                else:
                    lyric_rows.append(f"  [white]{text}[/white]")
            lyrics_block = "\n".join(lyric_rows) if lyric_rows else "  [dim]♫ Music playing... ♫[/dim]"
            lyrics_footer = "[bold bright_blue]────────────────────────────────────────────────────[/bold bright_blue]"
        elif self.plain_lyrics_lines:
            lyrics_header = "[bold bright_cyan]── Plain Lyrics (Synced unavailable) ───────────────[/bold bright_cyan]"
            # Scroll plain lyrics proportionally across song duration
            total_lines = len(self.plain_lyrics_lines)
            est_idx = int(ratio * total_lines) if total_lines > 0 else 0
            start_l = max(0, est_idx - 2)
            end_l = min(total_lines, start_l + 5)
            lyric_rows = []
            for i in range(start_l, end_l):
                txt = self.plain_lyrics_lines[i]
                if i == est_idx:
                    lyric_rows.append(f"  [bold bright_cyan]▸  {txt}[/bold bright_cyan]")
                else:
                    lyric_rows.append(f"  [white]{txt}[/white]")
            lyrics_block = "\n".join(lyric_rows)
            lyrics_footer = "[bold bright_cyan]────────────────────────────────────────────────────[/bold bright_cyan]"
        else:
            lyrics_header = "[dim]── Lyrics ──────────────────────────────────────────[/dim]"
            lyrics_block = (
                "  [dim](No synchronized or plain lyrics found for this track)[/dim]\n"
                "  [dim]Tip: Use 'Fix Missing Lyrics' in the main menu to automatically backfill lyrics.[/dim]"
            )
            lyrics_footer = "[dim]────────────────────────────────────────────────────[/dim]"

        track_pos = f"Track {self.current_index + 1} of {len(self.tracks)}"

        content = f"""
 [bold cyan]{track.title}[/bold cyan] [dim]—[/dim] [bold white]{track.artist or 'Unknown Artist'}[/bold white]
 [dim]{track_pos} • {track.extension.upper().lstrip('.')} • {track.size_mb} MB[/dim]

 {state_badge}  {cur_str} {bar} {dur_str}  [dim]|[/dim]  [cyan]{vol_badge}[/cyan]

{lyrics_header}
{lyrics_block}
{lyrics_footer}
 [bold cyan]Controls:[/bold cyan] [white][Space][/white] Play/Pause  [white][←/→][/white] Peek ±5s  [white][↑/↓][/white] Vol  [white][C][/white] Lyrics  [white][N/P][/white] Next/Prev  [white][Q][/white] Quit
"""
        return Panel(
            content.strip(),
            title="[bold magenta]ChinTunes Terminal Player 🎵[/bold magenta]",
            border_style="cyan"
        )

    def _keyboard_listener(self):
        """Robust key listener handling full ANSI arrow escape sequences and playback controls."""
        if os.name == "nt":
            import msvcrt
            while not self.stop_requested:
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch in (b'q', b'Q', b'\x1b'):
                        self.stop_requested = True
                        break
                    elif ch == b' ':
                        self._toggle_pause()
                    elif ch in (b'c', b'C'):
                        self._toggle_lyrics()
                    elif ch in (b'n', b'N'):
                        self._next_track()
                    elif ch in (b'p', b'P'):
                        self._prev_track()
                    elif ch in (b'+', b'='):
                        self._change_volume(0.05)
                    elif ch in (b'-', b'_'):
                        self._change_volume(-0.05)
                    elif ch in (b'\x00', b'\xe0'):
                        arrow = msvcrt.getch()
                        if arrow == b'H':    # Up arrow -> Volume Up
                            self._change_volume(0.05)
                        elif arrow == b'P':  # Down arrow -> Volume Down
                            self._change_volume(-0.05)
                        elif arrow == b'M':  # Right arrow -> Peek forward 5s
                            self._seek(5.0)
                        elif arrow == b'K':  # Left arrow -> Peek backward 5s
                            self._seek(-5.0)
                time.sleep(0.04)
        else:
            try:
                from prompt_toolkit.input import create_input
                from prompt_toolkit.keys import Keys

                inp = create_input()
                with inp.raw_mode():
                    while not self.stop_requested:
                        keys = inp.read_keys()
                        for key_press in keys:
                            k = key_press.key
                            if k in (Keys.Right, "right"):
                                self._seek(5.0)
                            elif k in (Keys.Left, "left"):
                                self._seek(-5.0)
                            elif k in (Keys.Up, "up"):
                                self._change_volume(0.05)
                            elif k in (Keys.Down, "down"):
                                self._change_volume(-0.05)
                            elif k in (Keys.Escape, "q", "Q"):
                                self.stop_requested = True
                                return
                            elif k == " ":
                                self._toggle_pause()
                            elif k in ("c", "C"):
                                self._toggle_lyrics()
                            elif k in ("n", "N"):
                                self._next_track()
                            elif k in ("p", "P"):
                                self._prev_track()
                            elif k in ("+", "="):
                                self._change_volume(0.05)
                            elif k in ("-", "_"):
                                self._change_volume(-0.05)
                        time.sleep(0.04)
            except Exception:
                pass
