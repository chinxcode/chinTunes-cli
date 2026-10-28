#!/usr/bin/env python3
"""
ChinTunes - High-Fidelity Music Downloader & Syncer.
Production-ready, persistent interactive CLI loop with graceful signal handling and clean worker termination.
"""

import os
import sys

# Auto-use the isolated ~/.chintunes/env virtual environment if available
_ISOLATED_PYTHON = os.path.expanduser("~/.chintunes/env/bin/python")
if os.path.exists(_ISOLATED_PYTHON) and os.path.abspath(sys.executable) != os.path.abspath(_ISOLATED_PYTHON):
    os.execv(_ISOLATED_PYTHON, [_ISOLATED_PYTHON] + sys.argv)

from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from syncer.core.config import ConfigManager
from syncer.core.history import HistoryManager
from syncer.core.coordinator import SyncCoordinator
from syncer.core.models import TrackMetadata
from syncer.core.playlist_manager import PlaylistManager
from syncer.player.terminal_player import TerminalPlayer
from syncer.providers.registry import ProviderRegistry
from syncer.ui.cli import InteractiveCLI

console = Console()


def run_library_repair(coordinator: SyncCoordinator, download_dir: str):
    if not os.path.exists(download_dir):
        console.print(f"[red]❌ Directory {download_dir} does not exist.[/red]")
        return

    console.print(
        Panel.fit(
            "[bold cyan]🛠️ Library Tag & Lyrics Backfiller Mode[/bold cyan]\n"
            f"[dim]Scanning {download_dir} to backfill missing lyrics and 1:1 square album covers.[/dim]",
            border_style="cyan"
        )
    )

    audio_files = [f for f in os.listdir(download_dir) if f.endswith((".mp3", ".m4a", ".mp4", ".flac"))]
    if not audio_files:
        console.print("[yellow]No audio files found in directory to repair.[/yellow]")
        return

    console.print(f"Found [cyan]{len(audio_files)}[/cyan] local tracks to inspect.\n")
    history = HistoryManager(download_dir)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        repair_task = progress.add_task("[cyan]Inspecting & backfilling...", total=len(audio_files))

        for fname in audio_files:
            file_path = os.path.join(download_dir, fname)
            vid = fname.split("[")[-1].split("]")[0] if "[" in fname and "]" in fname else fname

            # Standard ' - [' separator
            if " - [" in fname:
                parts = fname.rsplit(" - [", 1)
                meta_parts = parts[0].split(" - ")
            else:
                meta_parts = [fname.rsplit(".", 1)[0]]

            title = meta_parts[0].strip()
            artist = meta_parts[1].strip() if len(meta_parts) > 1 else ""

            track = TrackMetadata(id=vid, title=title, artist=artist, album=title)
            lyrics_res = coordinator.lyrics_engine.find_lyrics(title, artist)
            candidates = [
                f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            ]
            from syncer.tagging.tagger import MetadataTagger
            cover_bytes = MetadataTagger.process_cover_art(candidates, crop_square=True)

            detected_ext = fname.rsplit(".", 1)[-1].lower()
            MetadataTagger.embed(
                file_path=file_path,
                audio_format=detected_ext,
                track=track,
                lyrics=lyrics_res,
                cover_bytes=cover_bytes
            )

            history.record_track(vid, {
                "id": vid,
                "title": title,
                "artist": artist,
                "file_path": file_path,
                "lyrics_source": lyrics_res.source if lyrics_res else None,
                "has_synced_lyrics": bool(lyrics_res and lyrics_res.has_synced),
                "has_thumbnail": bool(cover_bytes)
            })
            progress.advance(repair_task)

    history.save()
    console.print("\n[bold green]✔ Library Backfill complete![/bold green]\n")


def execute_sync_pipeline(coordinator: SyncCoordinator, collection, download_dir: str, config_mgr: ConfigManager) -> bool:
    """
    Executes concurrent synchronization.
    Returns True if completed successfully, False if paused/interrupted.
    """
    coordinator.reset_stop()
    os.makedirs(download_dir, exist_ok=True)
    history = HistoryManager(download_dir)
    remote_tracks = collection.tracks
    remote_ids = {str(t.id) for t in remote_tracks}

    pending_tracks = []
    for t in remote_tracks:
        file_exists = False
        if history.has_track(t.id) and "file_path" in history.tracks[str(t.id)]:
            file_exists = os.path.exists(history.tracks[str(t.id)]["file_path"])
        else:
            for fname in os.listdir(download_dir):
                if f"[{t.id}]." in fname:
                    file_exists = True
                    break
        if not file_exists or not history.has_track(t.id):
            pending_tracks.append(t)

    console.print(f"[bold]📊 Status Summary:[/bold]")
    console.print(f" • Platform: [magenta]{collection.provider.upper()}[/magenta]")
    console.print(f" • Remote tracks: [cyan]{len(remote_tracks)}[/cyan]")
    console.print(f" • Already up to date: [green]{len(remote_tracks) - len(pending_tracks)}[/green]")
    console.print(f" • Pending to download: [yellow]{len(pending_tracks)}[/yellow]\n")

    interrupted = False
    if pending_tracks:
        max_workers = 1 if collection.is_single else (config_mgr.get("max_workers") or 3)
        pacing = 0.0 if collection.is_single else (config_mgr.get("rate_limit_delay") or 1.5)

        console.print(
            f"[bold cyan]🚀 Syncing {len(pending_tracks)} track(s) "
            f"(Concurrency: {max_workers} threads, Pacing: {pacing}s)...[/bold cyan]\n"
            f"[dim]Tip: Press Ctrl+C anytime to pause gracefully without losing downloaded files.[/dim]\n"
        )

        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                sync_task = progress.add_task("[cyan]Syncing media...", total=len(pending_tracks))

                futures = {}
                for idx, track in enumerate(pending_tracks):
                    stagger = (idx % max_workers) * pacing
                    f = executor.submit(coordinator.process_track, track, download_dir, stagger)
                    futures[f] = track

                for future in as_completed(futures):
                    if coordinator.is_stopped:
                        interrupted = True
                        break
                    track = futures[future]
                    try:
                        res = future.result()
                        if res.success:
                            history.record_track(res.track_id, {
                                "id": res.track_id,
                                "title": res.title,
                                "artist": res.artist,
                                "album": res.album,
                                "file_path": res.file_path,
                                "source": res.source,
                                "lyrics_source": res.lyrics_source,
                                "has_synced_lyrics": res.has_synced_lyrics,
                                "has_thumbnail": res.has_thumbnail,
                                "synced_at": res.synced_at
                            })
                            src_badge = f"[cyan]{res.source}[/cyan]"
                            lyr_badge = f"Lyrics: {res.lyrics_source}" if res.lyrics_source else "No lyrics"
                            progress.console.print(
                                f"  [green]✔[/green] {res.title} [dim]({res.artist}) [{src_badge}] - {lyr_badge}[/dim]"
                            )
                        else:
                            if not coordinator.is_stopped:
                                progress.console.print(f"  [red]✖ Failed:[/red] {track.title} -> {res.error}")
                    except Exception as exc:
                        if not coordinator.is_stopped:
                            progress.console.print(f"  [red]✖ Exception on {track.title}: {exc}[/red]")
                    finally:
                        progress.advance(sync_task)
                        history.save()

        except KeyboardInterrupt:
            interrupted = True
        finally:
            if coordinator.is_stopped:
                interrupted = True
            executor.shutdown(wait=False, cancel_futures=True)

        if interrupted or coordinator.is_stopped:
            console.print("\n[bold yellow]🛑 Sync paused! Active workers safely halted.[/bold yellow]")
            coordinator.request_stop()
            history.save()
            console.print("[green]✔ Progress preserved in sync history! Select 'Sync Active Target' anytime to resume.[/green]\n")
            return False

        console.print("\n[bold green]✔ Download phase complete![/bold green]\n")
    else:
        console.print("[green]✔ Everything is already in sync! No new tracks to download.[/green]\n")

    # Clean removed tracks
    if not collection.is_single and config_mgr.get("clean_removed_tracks", True):
        removed_count = 0
        for fname in os.listdir(download_dir):
            if fname in ("sync_history.json", "downloaded_history.txt", "sync_config.json") or fname.endswith(".m3u8"):
                continue
            if "[" in fname and "]" in fname:
                vid = fname.split("[")[-1].split("]")[0]
                if vid not in remote_ids:
                    file_path = os.path.join(download_dir, fname)
                    console.print(f"  [red]🗑️ Purging removed track:[/red] {fname}")
                    try:
                        os.remove(file_path)
                        lrc_path = os.path.splitext(file_path)[0] + ".lrc"
                        if os.path.exists(lrc_path):
                            os.remove(lrc_path)
                        history.remove_track(vid)
                        removed_count += 1
                    except Exception as e:
                        console.print(f"    [yellow]⚠️ Error deleting file: {e}[/yellow]")

        history.save()
        if removed_count > 0:
            console.print(f"[green]✔ Removed {removed_count} stale track(s).[/green]\n")

    # M3U8 Playlist Generation
    if not collection.is_single and config_mgr.get("generate_m3u8", True):
        clean_name = "".join(c for c in collection.title if c not in '\\/*?:"<>|').strip() or "Playlist"
        coordinator.generate_m3u8(download_dir, clean_name, remote_tracks)

    console.print(
        Panel.fit(
            f"[bold green]✨ All Done! Library is fully synchronized.[/bold green]\n"
            f"[dim]Total in collection: {len(remote_tracks)} • Folder: {os.path.abspath(download_dir)}[/dim]",
            border_style="green"
        )
    )
    return True


def sanitize_filename_token(text: str) -> str:
    clean = "".join(c for c in text if c not in '\\/*?:"<>|').strip()
    return clean or "Track"


def main():
    config_mgr = ConfigManager()
    ui = InteractiveCLI(config_mgr)
    registry = ProviderRegistry()
    coordinator = SyncCoordinator(config_mgr, registry)

    while True:
        try:
            ui.show_banner()
            action = ui.select_action()

            if action == "exit":
                console.print("[dim]Goodbye! Thanks for using ChinTunes.[/dim]")
                sys.exit(0)

            targets = config_mgr.targets
            active_key = config_mgr.get("active_target")

            # 1. Quick Download Any Link
            if action == "quick_download":
                link_url = ui.ask_url()
                if not link_url:
                    continue

                provider = registry.get_provider_for_url(link_url)
                collection = provider.fetch_collection(link_url) if provider else None

                if not collection or not collection.tracks:
                    console.print("[bold red]❌ Could not retrieve entries from this link.[/bold red]")
                else:
                    detected_title = collection.title or "New Playlist"
                    target_name = ui.ask_target_name(detected_title)
                    clean_title = sanitize_filename_token(target_name)

                    folder_category = "Single_Tracks" if collection.is_single else f"{collection.provider.capitalize()}_Playlists"
                    suggested_folder = f"./Playlists/{folder_category}/{clean_title}"
                    custom_folder = ui.ask_folder_destination(suggested_folder)
                    save_target = ui.ask_save_to_library()

                    target_key = clean_title.replace(" ", "_")
                    if save_target:
                        targets[target_key] = {
                            "name": target_name,
                            "url": link_url,
                            "folder": custom_folder,
                            "is_single": collection.is_single
                        }
                        config_mgr.set("active_target", target_key)
                        config_mgr.save()

                    execute_sync_pipeline(coordinator, collection, custom_folder, config_mgr)

            # 2. Terminal Mini-Player & Live Karaoke
            elif action == "play_music":
                pl_mgr = PlaylistManager(config_mgr)
                all_pls = pl_mgr.list_playlists()
                if not all_pls:
                    console.print("[yellow]⚠️ No playlists found in your library yet. Download or create one first![/yellow]")
                    continue

                # Select which playlist to play
                choices = [
                    f"{p['name']} ({p['track_count']} tracks)"
                    for p in all_pls
                ]
                import questionary
                from syncer.ui.cli import custom_style
                chosen = questionary.select(
                    "Select playlist to play:",
                    choices=choices + ["🔙 Back to Menu"],
                    style=custom_style
                ).ask()

                if not chosen or chosen == "🔙 Back to Menu":
                    continue

                chosen_idx = choices.index(chosen)
                selected_pl = all_pls[chosen_idx]
                tracks = pl_mgr.get_tracks(selected_pl["folder"])
                if not tracks:
                    console.print(f"[yellow]⚠️ No audio files found in '{selected_pl['name']}'.[/yellow]")
                    continue

                # Launch Terminal Mini-Player
                player = TerminalPlayer(tracks)
                player.run()

            # 3. Manage Playlists & Library
            elif action == "manage_playlists":
                pl_mgr = PlaylistManager(config_mgr)
                selected_key = ui.select_saved_playlist(targets, active_key)
                if not selected_key or selected_key == "__back__":
                    continue

                if selected_key == "__create_custom__":
                    custom_name = ui.ask_custom_playlist_name()
                    pl_info = pl_mgr.create_custom_playlist(custom_name)
                    console.print(f"[bold green]✔ Created custom playlist '{custom_name}' in {pl_info['folder']}[/bold green]\n")

                elif selected_key == "__add_new__":
                    new_url = ui.ask_url()
                    if not new_url:
                        continue
                    provider = registry.get_provider_for_url(new_url)
                    collection = provider.fetch_collection(new_url) if provider else None
                    detected_title = collection.title if collection else "New Playlist"
                    target_name = ui.ask_target_name(detected_title)
                    clean_name = sanitize_filename_token(target_name)
                    is_single = collection.is_single if collection else False

                    folder_category = "Single_Tracks" if is_single else f"{provider.name.capitalize()}_Playlists"
                    suggested_folder = f"./Playlists/{folder_category}/{clean_name}"
                    folder_path = ui.ask_folder_destination(suggested_folder)

                    key = clean_name.replace(" ", "_")
                    targets[key] = {
                        "name": target_name,
                        "url": new_url,
                        "folder": folder_path,
                        "is_single": is_single
                    }
                    config_mgr.set("active_target", key)
                    config_mgr.save()
                    console.print(f"[green]✔ Added & set active: {target_name}[/green]\n")

                elif selected_key == "__manage_songs__":
                    all_pls = pl_mgr.list_playlists()
                    pl_choices = [p["name"] for p in all_pls]
                    import questionary
                    from syncer.ui.cli import custom_style
                    pick_pl = questionary.select(
                        "Which playlist would you like to inspect?",
                        choices=pl_choices + ["🔙 Back"],
                        style=custom_style
                    ).ask()

                    if not pick_pl or pick_pl == "🔙 Back":
                        continue

                    pl_obj = next(p for p in all_pls if p["name"] == pick_pl)
                    tracks = pl_mgr.get_tracks(pl_obj["folder"])
                    t_idx = ui.select_track_from_playlist(tracks, pl_obj["name"])
                    if t_idx is None or t_idx == "__back__":
                        continue

                    chosen_track = tracks[t_idx]
                    t_action = ui.ask_track_action(chosen_track.display_name)
                    if t_action == "play":
                        player = TerminalPlayer(tracks, initial_index=t_idx)
                        player.run()
                    elif t_action == "delete":
                        confirm_del = questionary.confirm(
                            f"Are you sure you want to permanently delete '{chosen_track.filename}'?",
                            default=False,
                            style=custom_style
                        ).ask()
                        if confirm_del:
                            pl_mgr.remove_track(pl_obj["folder"], chosen_track)
                            console.print(f"[bold green]✔ Successfully deleted '{chosen_track.filename}'[/bold green]\n")

                elif selected_key == "__delete__":
                    del_key = ui.select_target_to_delete(targets)
                    if del_key and del_key != "__cancel__":
                        del_name = targets[del_key].get("name", del_key)
                        del targets[del_key]
                        if config_mgr.get("active_target") == del_key:
                            config_mgr.set("active_target", list(targets.keys())[0] if targets else None)
                        config_mgr.save()
                        console.print(f"[green]✔ Removed target '{del_name}' from library.[/green]\n")

                else:
                    config_mgr.set("active_target", selected_key)
                    config_mgr.save()
                    console.print(f"[green]✔ Active target switched to: {targets[selected_key]['name']}[/green]\n")

            # 3. Repair Existing Library
            elif action == "repair_library":
                active_info = config_mgr.active_target_info
                default_path = active_info.get("folder", "./Playlists") if active_info else "./Playlists"
                folder = ui.ask_folder_destination(default_path)
                run_library_repair(coordinator, folder)

            # 4. Settings
            elif action == "settings":
                ui.configure_settings()

            # 5. Sync Active Target
            elif action == "sync_active":
                active_info = config_mgr.active_target_info
                if not active_info:
                    console.print("[yellow]⚠️ No active target selected. Please choose 'Download Any Link' or add a playlist first.[/yellow]")
                    continue

                ui.display_active_target(active_info)
                if not ui.confirm_sync():
                    continue

                download_dir = active_info.get("folder", "./Playlists/Synced")
                target_url = active_info.get("url")

                provider = registry.get_provider_for_url(target_url)
                collection = provider.fetch_collection(target_url) if provider else None
                if not collection or not collection.tracks:
                    console.print("[bold red]🛑 Failed to retrieve collection tracks from remote source.[/bold red]")
                    continue

                execute_sync_pipeline(coordinator, collection, download_dir, config_mgr)

            should_continue = ui.ask_continue_or_exit()
            if not should_continue:
                console.print("[dim]Goodbye! Thanks for using ChinTunes.[/dim]")
                sys.exit(0)

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️ Interrupted. Returning to main menu...[/yellow]")
            continue


if __name__ == "__main__":
    main()
