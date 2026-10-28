"""
Advanced Interactive CLI Experience.
Uses Questionary (keyboard arrow-keys navigation) & Rich formatting.
Zero confusing default brackets, clean options, persistent loop navigation.
"""

from typing import Dict, Any, List, Optional
import questionary
from questionary import Choice, Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from syncer.core.config import ConfigManager

console = Console()

custom_style = Style([
    ("qmark", "fg:#00d7d7 bold"),
    ("question", "bold fg:#ffffff"),
    ("answer", "fg:#00ff87 bold"),
    ("pointer", "fg:#00ffff bold"),
    ("highlighted", "fg:#00ffff bold"),
    ("selected", "fg:#00ff87"),
    ("separator", "fg:#6c6c6c"),
    ("instruction", "fg:#8a8a8a italic"),
    ("text", "fg:#ffffff"),
])


class InteractiveCLI:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def show_banner(self):
        console.clear()
        ascii_art = """[bold cyan]
 ▄▄▄▄▄▄▄ ▄▄             ▄▄▄▄▄▄▄▄▄                      
███▀▀▀▀▀ ██    ▀▀       ▀▀▀███▀▀▀                      
███      ████▄ ██  ████▄   ███ ██ ██ ████▄ ▄█▀█▄ ▄█▀▀▀ 
███      ██ ██ ██  ██ ██   ███ ██ ██ ██ ██ ██▄█▀ ▀███▄ 
▀███████ ██ ██ ██▄ ██ ██   ███ ▀██▀█ ██ ██ ▀█▄▄▄ ▄▄▄█▀[/bold cyan]
[magenta]♪ ♫ ♩ ♬  High-Fidelity Music Downloader & Syncer  ♬ ♩ ♫ ♪[/magenta]"""
        console.print(
            Panel(
                ascii_art + "\n\n"
                "[dim]YouTube • YouTube Music • JioSaavn 320k • Spotify • Synced Lyrics[/dim]",
                border_style="bright_blue",
                padding=(0, 2)
            )
        )

    def select_action(self) -> str:
        has_targets = self.config_manager.has_targets
        active_info = self.config_manager.active_target_info

        choices = []
        if has_targets and active_info:
            active_name = active_info.get("name", "Active Playlist")
            choices.append(
                Choice(
                    title=f"⚡ Sync '{active_name}'",
                    value="sync_active"
                )
            )

        choices.extend([
            Choice(
                title="▶️ Play Music (Terminal Mini-Player & Live Karaoke)",
                value="play_music"
            ),
            Choice(
                title="📥 Download Song or Playlist",
                value="quick_download"
            ),
            Choice(
                title="📑 Playlist Manager (View, Add/Remove Songs, Custom Playlists)",
                value="manage_playlists"
            ),
            Choice(
                title="🛠️ Fix Missing Lyrics & Artwork",
                value="repair_library"
            ),
            Choice(
                title="⚙️ Settings",
                value="settings"
            ),
            Choice(
                title="🚪 Exit",
                value="exit"
            )
        ])

        action = questionary.select(
            "What would you like to do?",
            choices=choices,
            style=custom_style
        ).ask()

        return action or "exit"

    def display_active_target(self, target: Dict[str, Any]):
        cfg = self.config_manager.data
        console.print("\n[bold]Current Active Target Information:[/bold]")
        table = Table(show_header=True, header_style="bold magenta", border_style="dim")
        table.add_column("Property", style="dim", width=25)
        table.add_column("Value", style="cyan")

        table.add_row("Name", target.get("name", "Untitled"))
        url = target.get("url", "")
        table.add_row("Source URL", url[:60] + "..." if len(url) > 60 else url)
        table.add_row("Destination Folder", target.get("folder", ""))
        table.add_row("Audio Format", f"{cfg.get('audio_format', 'mp3').upper()} ({cfg.get('audio_quality')})")
        table.add_row("Studio 320k Matching", "Enabled (Prioritize JioSaavn Master)" if cfg.get("prefer_jiosaavn_320k") else "Disabled")
        table.add_row("Loudness Normalization", "EBU R128 (-16 LUFS)" if cfg.get("normalize_loudness") else "Disabled")
        table.add_row("Album Artwork", "1:1 Square Auto-Cropped" if cfg.get("crop_square_thumbnail") else "Original")
        table.add_row("Lyrics Search", "LRCLIB Multi-Artist Cascade" if cfg.get("embed_lyrics") else "Disabled")
        table.add_row("Auto-Generate M3U8", "Enabled" if cfg.get("generate_m3u8") else "Disabled")

        console.print(table)
        console.print()

    def confirm_sync(self) -> bool:
        return questionary.confirm(
            "Start synchronization now?",
            default=True,
            style=custom_style
        ).ask()

    def ask_url(self) -> str:
        url = questionary.text(
            "Paste media URL (YouTube, YT Music, JioSaavn song/album/playlist, Spotify track):",
            style=custom_style,
            validate=lambda text: True if text.strip().startswith("http") else "Please enter a valid link starting with http/https"
        ).ask()
        return (url or "").strip()

    def ask_target_name(self, detected_name: str) -> str:
        name = questionary.text(
            "Enter playlist or track display name:",
            default=detected_name,
            style=custom_style,
            instruction="(Auto-detected from online source. Press Enter to keep or edit)"
        ).ask()
        return (name or detected_name).strip()

    def ask_folder_destination(self, suggested_folder: str) -> str:
        folder = questionary.text(
            "Destination folder path:",
            default=suggested_folder,
            style=custom_style,
            instruction="(Auto-named after target. Press Enter to keep or edit)"
        ).ask()
        return (folder or suggested_folder).strip()

    def ask_save_to_library(self) -> bool:
        return questionary.confirm(
            "Save this target to your library for future auto-syncing?",
            default=True,
            style=custom_style
        ).ask()

    def select_saved_playlist(self, targets: Dict[str, Any], active_key: Optional[str]) -> Optional[str]:
        choices = []
        if not targets:
            console.print("[yellow]Your saved playlist library is currently empty.[/yellow]")
        else:
            for key, pinfo in targets.items():
                is_active = (key == active_key)
                prefix = "[ACTIVE] " if is_active else ""
                t_type = "Single Track" if pinfo.get("is_single") else "Playlist"
                title = f"{prefix}{pinfo.get('name', key)} ({t_type}) -> {pinfo.get('folder')}"
                choices.append(Choice(title=title, value=key))

        choices.append(Choice(title="✨ Create New Custom Playlist", value="__create_custom__"))
        choices.append(Choice(title="➕ Add Remote Playlist / Link", value="__add_new__"))
        if targets:
            choices.append(Choice(title="🎵 View & Manage Songs in Playlist", value="__manage_songs__"))
            choices.append(Choice(title="🗑️ Delete an Entire Playlist", value="__delete__"))
        choices.append(Choice(title="🔙 Back to Main Menu", value="__back__"))

        return questionary.select(
            "Select action or target from library:",
            choices=choices,
            style=custom_style,
            instruction="(Use arrow keys, Enter to pick)"
        ).ask()

    def select_target_to_delete(self, targets: Dict[str, Any]) -> Optional[str]:
        choices = [
            Choice(title=f"{pinfo.get('name', key)} ({pinfo.get('folder')})", value=key)
            for key, pinfo in targets.items()
        ]
        choices.append(Choice(title="🔙 Cancel", value="__cancel__"))
        return questionary.select(
            "Choose a target to remove from saved library:",
            choices=choices,
            style=custom_style
        ).ask()

    def ask_custom_playlist_name(self) -> str:
        name = questionary.text(
            "Enter a name for your new Custom Playlist:",
            default="My Favorites",
            style=custom_style
        ).ask()
        return (name or "Custom Playlist").strip()

    def select_track_from_playlist(self, tracks: List[Any], playlist_name: str) -> Optional[int]:
        if not tracks:
            console.print(f"[yellow]No songs currently found in '{playlist_name}'.[/yellow]")
            return None

        choices = []
        for idx, t in enumerate(tracks):
            lrc_badge = "[LRC] " if getattr(t, "has_lrc", False) else ""
            title = f"{idx + 1}. {lrc_badge}{t.title} - {t.artist} ({t.extension.upper()} • {t.size_mb}MB)"
            choices.append(Choice(title=title, value=idx))

        choices.append(Choice(title="🔙 Back to Playlist Menu", value="__back__"))
        return questionary.select(
            f"Select a song from '{playlist_name}':",
            choices=choices,
            style=custom_style,
            instruction="(Use arrow keys, Enter to pick)"
        ).ask()

    def ask_track_action(self, track_display: str) -> str:
        return questionary.select(
            f"What would you like to do with '{track_display}'?",
            choices=[
                Choice("▶️ Play Now (Terminal Mini-Player)", value="play"),
                Choice("🗑️ Remove Track (Delete File & Sync History)", value="delete"),
                Choice("🔙 Cancel", value="cancel")
            ],
            style=custom_style
        ).ask()

    def configure_settings(self):
        cfg = self.config_manager.data
        console.print("\n[bold yellow]── Audio & Engine Configuration ──[/bold yellow]")

        fmt = questionary.select(
            "Audio Format:",
            choices=[
                Choice("MP3 (Universal - works on everything)", value="mp3"),
                Choice("M4A (Fastest & best quality)", value="m4a"),
                Choice("FLAC (Lossless)", value="flac")
            ],
            default=cfg.get("audio_format", "mp3"),
            style=custom_style
        ).ask()

        quality = cfg.get("audio_quality", "0")
        if fmt == "mp3":
            quality = questionary.select(
                "Audio Quality:",
                choices=[
                    Choice("Best (320k / VBR 0) - Highest Quality", value="0"),
                    Choice("High (256k)", value="256k"),
                    Choice("Standard (192k)", value="192k")
                ],
                default=cfg.get("audio_quality", "0"),
                style=custom_style
            ).ask()

        fast_copy = questionary.confirm(
            "Enable High-Speed Mode (Fast download with near-0% CPU)?",
            default=cfg.get("fast_stream_copy", True),
            style=custom_style
        ).ask()

        jio_master = questionary.confirm(
            "Prefer 320kbps Studio Masters (from JioSaavn when available)?",
            default=cfg.get("prefer_jiosaavn_320k", True),
            style=custom_style
        ).ask()

        concurrency = questionary.select(
            "Download Speed / Concurrency:",
            choices=[
                Choice("1 track at a time (Sequential)", value=1),
                Choice("2 tracks at a time (Balanced)", value=2),
                Choice("3 tracks at a time (Fast)", value=3),
                Choice("4 tracks at a time (Maximum Speed)", value=4),
            ],
            default=cfg.get("max_workers", 3),
            style=custom_style
        ).ask()

        loudnorm = questionary.confirm(
            "Equalize volume between songs (Loudness Normalization)?",
            default=cfg.get("normalize_loudness", False),
            style=custom_style
        ).ask()

        square_crop = questionary.confirm(
            "Crop cover artwork into square shape?",
            default=cfg.get("crop_square_thumbnail", True),
            style=custom_style
        ).ask()

        lyrics = questionary.confirm(
            "Download and embed lyrics into songs?",
            default=cfg.get("embed_lyrics", True),
            style=custom_style
        ).ask()

        save_lrc = False
        if lyrics:
            save_lrc = questionary.confirm(
                "Also save .lrc lyrics file next to the song?",
                default=cfg.get("save_lrc_file", False),
                style=custom_style
            ).ask()

        m3u8 = questionary.confirm(
            "Create .m3u8 playlist file?",
            default=cfg.get("generate_m3u8", True),
            style=custom_style
        ).ask()

        clean = questionary.confirm(
            "Delete local songs if they get removed from online playlist?",
            default=cfg.get("clean_removed_tracks", False),
            style=custom_style
        ).ask()

        cfg.update({
            "audio_format": fmt,
            "audio_quality": quality,
            "fast_stream_copy": fast_copy,
            "prefer_jiosaavn_320k": jio_master,
            "max_workers": concurrency,
            "normalize_loudness": loudnorm,
            "crop_square_thumbnail": square_crop,
            "embed_lyrics": lyrics,
            "save_lrc_file": save_lrc,
            "generate_m3u8": m3u8,
            "clean_removed_tracks": clean,
        })
        self.config_manager.save()
        console.print("\n[bold green]✔ Audio & Engine preferences successfully saved![/bold green]\n")

    def ask_continue_or_exit(self) -> bool:
        """Prompts whether the user wants to perform another action or exit."""
        console.print()
        choices = [
            Choice("🔄 Return to Main Menu", value=True),
            Choice("🚪 Exit Application", value=False)
        ]
        return questionary.select(
            "What would you like to do next?",
            choices=choices,
            style=custom_style
        ).ask()
