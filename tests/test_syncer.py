"""Comprehensive test suite verifying models, config, history, providers, lyrics, and tagger."""

import os
import json
import pytest

from syncer.core.models import TrackMetadata, LyricsData, CollectionResult, SyncProcessResult
from syncer.core.config import ConfigManager
from syncer.core.history import HistoryManager
from syncer.providers.registry import ProviderRegistry
from syncer.providers.jiosaavn import JioSaavnProvider
from syncer.providers.spotify import SpotifyProvider
from syncer.providers.youtube import YouTubeProvider
from syncer.tagging.lyrics import LyricsEngine
from syncer.tagging.tagger import MetadataTagger
from syncer.core.coordinator import SyncCoordinator


class TestCoreModels:
    def test_track_metadata_safe_filename(self):
        track = TrackMetadata(
            id="abc1234",
            title='Song: "Love / Life" *Special*',
            artist="Singer A, Singer B",
            album="Top Album"
        )
        safe = track.safe_filename_base
        assert "Love  Life Special" in safe
        assert '[abc1234]' in safe
        assert " - " in safe
        assert "===" not in safe
        for bad_char in '\\/*?:"<>|':
            assert bad_char not in safe

    def test_lyrics_data_properties(self):
        empty = LyricsData()
        assert empty.is_empty is True
        assert empty.has_synced is False

        synced = LyricsData(plain="La la", synced="[00:10.00] La la", source="LRCLIB")
        assert synced.is_empty is False
        assert synced.has_synced is True


class TestConfigAndHistory:
    def test_config_empty_targets_and_override(self, tmp_path):
        cfg_file = str(tmp_path / "test_cfg.json")
        cfg_mgr = ConfigManager(cfg_file)
        # Should start with no targets by default
        assert cfg_mgr.has_targets is False
        assert cfg_mgr.active_target_info is None

        # Add target
        cfg_mgr.targets["my_target"] = {
            "name": "Rock Classics",
            "url": "https://music.youtube.com/playlist?list=sample",
            "folder": "./Playlists/Rock"
        }
        cfg_mgr.set("active_target", "my_target")
        cfg_mgr.save()

        # Reload
        cfg_mgr_2 = ConfigManager(cfg_file)
        assert cfg_mgr_2.has_targets is True
        assert cfg_mgr_2.active_target_info["name"] == "Rock Classics"

    def test_history_manager_track_lifecycle(self, tmp_path):
        hist_dir = str(tmp_path / "sync_folder")
        os.makedirs(hist_dir, exist_ok=True)

        hm = HistoryManager(hist_dir)
        assert hm.has_track("track_01") is False

        hm.record_track("track_01", {"id": "track_01", "title": "My Song"})
        hm.save()
        assert hm.has_track("track_01") is True

        hm2 = HistoryManager(hist_dir)
        assert hm2.has_track("track_01") is True

        hm2.remove_track("track_01")
        hm2.save()
        assert hm2.has_track("track_01") is False


class TestProviders:
    def test_provider_url_routing(self):
        registry = ProviderRegistry()

        p_yt = registry.get_provider_for_url("https://music.youtube.com/playlist?list=PL123")
        assert isinstance(p_yt, YouTubeProvider)

        p_yt_video = registry.get_provider_for_url("https://www.youtube.com/watch?v=swcCuuQKGJ4")
        assert isinstance(p_yt_video, YouTubeProvider)

        p_saavn = registry.get_provider_for_url("https://www.jiosaavn.com/song/out-of-time/MgE7dT93XWU")
        assert isinstance(p_saavn, JioSaavnProvider)

        p_saavn_album = registry.get_provider_for_url("https://www.jiosaavn.com/album/dawn-fm/sFq24sTmy5E_")
        assert isinstance(p_saavn_album, JioSaavnProvider)

        p_spot = registry.get_provider_for_url("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT")
        assert isinstance(p_spot, SpotifyProvider)

    def test_jiosaavn_des_decryption_and_upgrade(self):
        enc_url = "ID2ieOjCrwfgWvL5sXl4B1ImC5QfbsDyjvOrZHJ3NJfS/Z3TGpniJjw8gwFDqbt0unByKKL6/Z/qCr2on7HQrRw7tS9a8Gtq"
        dec = JioSaavnProvider.decrypt_cdn_url(enc_url)
        assert dec is not None
        assert "saavncdn.com" in dec

        upgraded = JioSaavnProvider.upgrade_to_320k(dec)
        assert "_320.mp4" in upgraded

    def test_jiosaavn_live_song_fetch(self):
        provider = JioSaavnProvider()
        # Out of Time by The Weeknd on JioSaavn
        url = "https://www.jiosaavn.com/song/out-of-time/MgE7dT93XWU"
        res = provider.fetch_collection(url)
        assert res is not None
        assert res.is_single is True
        assert len(res.tracks) == 1
        track = res.tracks[0]
        assert "Out of Time" in track.title
        assert track.cdn_url is not None
        assert "_320.mp4" in track.cdn_url

    def test_jiosaavn_live_album_fetch(self):
        provider = JioSaavnProvider()
        url = "https://www.jiosaavn.com/album/dawn-fm/sFq24sTmy5E_"
        res = provider.fetch_collection(url)
        assert res is not None
        assert res.is_single is False
        assert len(res.tracks) > 5
        assert res.tracks[0].cdn_url is not None

    def test_spotify_live_track_fetch(self):
        provider = SpotifyProvider()
        url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
        res = provider.fetch_collection(url)
        assert res is not None
        assert res.is_single is True
        assert len(res.tracks) == 1
        track = res.tracks[0]
        assert "Never Gonna Give You Up" in track.title
        assert "Rick Astley" in track.artist

    def test_youtube_live_single_track_fetch(self):
        provider = YouTubeProvider()
        url = "https://www.youtube.com/watch?v=swcCuuQKGJ4"
        res = provider.fetch_collection(url)
        assert res is not None
        assert res.is_single is True
        assert len(res.tracks) == 1
        assert "Pehli Nazar Mein" in res.tracks[0].title


class TestLyricsEngine:
    def test_sanitize_query(self):
        raw = "Pehli Nazar Mein (Official Music Video) [Audio]"
        clean = LyricsEngine.sanitize(raw)
        assert clean == "Pehli Nazar Mein"

    def test_artist_variants(self):
        artist_str = "Jubin Nautiyal, Rocky-Shiv, Manoj Muntashir"
        variants = LyricsEngine.get_artist_variants(artist_str)
        assert variants[0] == "Jubin Nautiyal, Rocky-Shiv, Manoj Muntashir"
        assert "Jubin Nautiyal" in variants
        assert "Rocky-Shiv" in variants
        assert "Manoj Muntashir" in variants

    def test_parse_lrc_to_sylt(self):
        lrc = "[00:11.71] Line 1\n[00:17.29] Line 2"
        sylt = LyricsEngine.parse_lrc_to_sylt(lrc)
        assert len(sylt) == 2
        assert sylt[0] == ("Line 1", 11710)
        assert sylt[1] == ("Line 2", 17290)

    def test_live_lrclib_synced_lyrics(self):
        engine = LyricsEngine()
        lyrics = engine.find_lyrics("Pehli Nazar Mein", "Pritam, Atif Aslam")
        assert lyrics is not None
        assert lyrics.has_synced is True
        assert "00:" in (lyrics.synced or "")


class TestCoordinatorAndTagger:
    def test_m3u8_generation(self, tmp_path):
        cfg_mgr = ConfigManager(str(tmp_path / "cfg.json"))
        coordinator = SyncCoordinator(cfg_mgr)
        out_dir = str(tmp_path / "music")
        os.makedirs(out_dir, exist_ok=True)

        # Create dummy audio file
        dummy_file = os.path.join(out_dir, "Track One - Artist - [test123].mp3")
        with open(dummy_file, "wb") as f:
            f.write(b"ID3dummy")

        track = TrackMetadata(id="test123", title="Track One", artist="Artist", album="Album", duration=180)
        coordinator.generate_m3u8(out_dir, "TestPlaylist", [track])

        m3u8_file = os.path.join(out_dir, "TestPlaylist.m3u8")
        assert os.path.exists(m3u8_file)
        with open(m3u8_file, "r") as f:
            content = f.read()
            assert "#EXTM3U" in content
            assert "Track One" in content
            assert "Track One - Artist - [test123].mp3" in content
