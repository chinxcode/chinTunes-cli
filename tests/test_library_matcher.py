"""Tests for Local MP3 Library Matcher & Tagger."""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from syncer.core.library_matcher import LibraryMatcher, MatchResult


def test_sanitize_search_query():
    matcher = LibraryMatcher()

    # Domain, bitrate, and junk tags removal
    raw = "PagalWorld.com - Badshah - Genda Phool 320kbps [Official Video]"
    cleaned = matcher.sanitize_search_query(raw)
    assert "Badshah" in cleaned
    assert "Genda Phool" in cleaned
    assert "PagalWorld" not in cleaned
    assert "320kbps" not in cleaned
    assert "Official Video" not in cleaned

    # Web URL and leading numbers
    raw2 = "01. https://www.djpunjab.in/ Sidhu Moose Wala - 295 (Official Audio).mp3"
    cleaned2 = matcher.sanitize_search_query(raw2)
    assert "Sidhu Moose Wala" in cleaned2
    assert "295" in cleaned2
    assert "djpunjab" not in cleaned2
    assert not cleaned2.startswith("01.")


def test_inspect_file_without_tags():
    matcher = LibraryMatcher()
    with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
        # File has no tags, should parse from clean basename
        title, artist, album, duration = matcher.inspect_file(tmp.name)
        assert title != ""
        assert duration == 0.0


@patch("urllib.request.urlopen")
def test_query_itunes_success(mock_urlopen):
    matcher = LibraryMatcher()

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'''{
        "resultCount": 1,
        "results": [
            {
                "trackName": "Starboy",
                "artistName": "The Weeknd",
                "collectionName": "Starboy",
                "releaseDate": "2016-11-25T08:00:00Z",
                "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/100x100bb.jpg"
            }
        ]
    }'''
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    res = matcher.query_itunes("Starboy", "The Weeknd")
    assert res is not None
    assert res["title"] == "Starboy"
    assert res["artist"] == "The Weeknd"
    assert res["year"] == 2016
    assert "1400x1400bb.jpg" in res["artwork_url"]


@patch("urllib.request.urlopen")
def test_query_jiosaavn_success(mock_urlopen):
    matcher = LibraryMatcher()

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'''{
        "songs": {
            "data": [
                {
                    "id": "12345",
                    "title": "Kesariya",
                    "image": "https://c.saavncdn.com/123/50x50.jpg",
                    "album": "Brahmastra",
                    "more_info": {
                        "primary_artists": "Pritam, Arijit Singh",
                        "year": "2022"
                    }
                }
            ]
        }
    }'''
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    res = matcher.query_jiosaavn("Kesariya", "Arijit Singh")
    assert res is not None
    assert res["title"] == "Kesariya"
    assert "Arijit Singh" in res["artist"]
    assert res["album"] == "Brahmastra"
    assert res["year"] == 2022
    assert "500x500.jpg" in res["artwork_url"]


@patch("yt_dlp.YoutubeDL")
def test_query_youtube_success(mock_ydl_cls):
    matcher = LibraryMatcher()
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = {
        "entries": [
            {
                "id": "abc123xyz",
                "title": "Arijit Singh - Kesariya (Audio)",
                "uploader": "SonyMusicIndiaVEVO",
                "upload_date": "20220715",
                "thumbnails": [{"url": "https://i.ytimg.com/vi/abc123xyz/hqdefault.jpg"}]
            }
        ]
    }
    mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

    res = matcher.query_youtube("Kesariya", "Arijit Singh")
    assert res is not None
    assert "Kesariya" in res["title"] or "Arijit Singh" in res["artist"]
    assert res["year"] == 2022
    assert "abc123xyz" in res["artwork_url"]


def test_variety_of_audio_formats_supported():
    matcher = LibraryMatcher()
    for ext in (".mp3", ".m4a", ".mp4", ".flac", ".aac", ".ogg", ".opus", ".wav", ".wave", ".aiff", ".alac", ".webm"):
        assert ext in matcher.SUPPORTED_EXTENSIONS

