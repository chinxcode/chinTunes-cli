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
  ██████╗██╗  ██╗██╗███╗   ██╗████████╗██╗   ██╗███╗   ██╗███████╗███████╗
 ██╔════╝██║  ██║██║████╗  ██║╚══██╔══╝██║   ██║████╗  ██║██╔════╝██╔════╝
 ██║     ███████║██║██╔██╗ ██║   ██║   ██║   ██║██╔██╗ ██║█████╗  ███████╗
 ██║     ██╔══██║██║██║╚██╗██║   ██║   ██║   ██║██║╚██╗██║██╔══╝  ╚════██║
 ╚██████╗██║  ██║██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚████║███████╗███████║
  ╚═════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚══════╝[/bold cyan]
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
                    title=f"⚡ Sync Active Target: '{active_name}'",
                    value="sync_active"
                )
            )

        choices.extend([
            Choice(
                title="📥 Download Any Link (Song, Album, or Playlist URL)",
                value="quick_download"
            ),
            Choice(
                title="📑 Manage Saved Library (Switch, Add, or Remove Targets)",
                value="manage_playlists"
            ),
            Choice(
                title="🛠️ Library Repair Mode (Backfill Lyrics & Square Covers offline)",
                value="repair_library"
            ),
            Choice(
                title="⚙️ Audio & Engine Settings (Quality, Concurrency, Normalization)",
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
            style=custom_style,
            instruction="(Use arrow keys to navigate, Enter to select)"
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

        choices.append(Choice(title="➕ Add New Playlist / Link", value="__add_new__"))
        if targets:
            choices.append(Choice(title="🗑️ Delete a Saved Target", value="__delete__"))
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

    def configure_settings(self):
        cfg = self.config_manager.data
        console.print("\n[bold yellow]── Audio & Engine Configuration ──[/bold yellow]")

        fmt = questionary.select(
            "Select Audio Format:",
            choices=[
                Choice("MP3 (Universal compatibility, ID3v2.3 tags, embedded lyrics)", value="mp3"),
                Choice("M4A (AAC Zero-Transcode Stream-Copy - Ultra Fast & Near-0% CPU)", value="m4a"),
                Choice("FLAC (Lossless compression, Vorbis comments)", value="flac")
            ],
            default=cfg.get("audio_format", "mp3"),
            style=custom_style
        ).ask()

        quality = cfg.get("audio_quality", "0")
        if fmt == "mp3":
            quality = questionary.select(
                "Select MP3 Quality / Bitrate:",
                choices=[
                    Choice("VBR 0 (~250-320 kbps) - Best Variable Bitrate", value="0"),
                    Choice("CBR 320k - Maximum Constant Bitrate", value="320k"),
                    Choice("CBR 256k - High Quality Constant Bitrate", value="256k"),
                    Choice("CBR 192k - Standard Quality", value="192k")
                ],
                default=cfg.get("audio_quality", "0"),
                style=custom_style
            ).ask()

        fast_copy = questionary.confirm(
            "Enable High-Speed Stream Copy (Bypasses heavy CPU re-encoding when formats match)?",
            default=cfg.get("fast_stream_copy", True),
            style=custom_style
        ).ask()

        jio_master = questionary.confirm(
            "Prioritize JioSaavn 320kbps CD master (direct HTTP CDN download)?",
            default=cfg.get("prefer_jiosaavn_320k", True),
            style=custom_style
        ).ask()

        concurrency = questionary.select(
            "Concurrent download threads:",
            choices=[
                Choice("1 thread (Sequential, safest against IP rate limits)", value=1),
                Choice("2 threads (Recommended safe balance)", value=2),
                Choice("3 threads (Fast download speed)", value=3),
                Choice("4 threads (Maximum aggressive concurrency)", value=4),
            ],
            default=cfg.get("max_workers", 3),
            style=custom_style
        ).ask()

        loudnorm = questionary.confirm(
            "Apply EBU R128 Loudness Normalization? (Note: disable for maximum speed & lowest CPU)",
            default=cfg.get("normalize_loudness", False),
            style=custom_style
        ).ask()

        square_crop = questionary.confirm(
            "Auto-crop video thumbnails into clean 1:1 square album covers?",
            default=cfg.get("crop_square_thumbnail", True),
            style=custom_style
        ).ask()

        lyrics = questionary.confirm(
            "Search and embed timed synchronized (SYLT) and plain (USLT) lyrics?",
            default=cfg.get("embed_lyrics", True),
            style=custom_style
        ).ask()

        save_lrc = False
        if lyrics:
            save_lrc = questionary.confirm(
                "Also save companion external .lrc file in folder for mobile/car players?",
                default=cfg.get("save_lrc_file", False),
                style=custom_style
            ).ask()

        m3u8 = questionary.confirm(
            "Maintain .m3u8 playlist file in directory preserving online track order?",
            default=cfg.get("generate_m3u8", True),
            style=custom_style
        ).ask()

        clean = questionary.confirm(
            "Auto-delete local tracks if they get removed from the remote playlist?",
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
