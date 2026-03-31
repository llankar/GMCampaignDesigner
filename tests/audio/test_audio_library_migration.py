"""Regression tests for audio library migration."""

import json
from pathlib import Path

from modules.audio.library.repository import AudioLibraryRepository


def test_repository_migrates_legacy_tracks_and_adds_last_mood_setting(tmp_path: Path) -> None:
    """Verify that repository migrates legacy tracks and adds last mood setting."""
    audio_a = tmp_path / "legacy-a.mp3"
    audio_b = tmp_path / "legacy-b.mp3"
    audio_a.write_bytes(b"a")
    audio_b.write_bytes(b"b")

    config_path = tmp_path / "audio_library.json"
    legacy_payload = {
        "music": {
            "categories": {
                "Ambience": {
                    "directories": [str(tmp_path)],
                    "tracks": [
                        {"id": "t1", "name": "Legacy A", "path": str(audio_a), "mood": "Calm"},
                        {"id": "t2", "name": "Legacy B", "path": str(audio_b)},
                    ],
                }
            },
            "settings": {"last_category": "Ambience", "last_track_id": "t1"},
        },
        "effects": {"categories": {}, "settings": {}},
    }
    config_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    repository = AudioLibraryRepository(str(config_path))
    data = repository.load()

    music_settings = data["music"]["settings"]
    assert "last_mood" in music_settings
    assert music_settings["last_mood"] == ""

    ambience = data["music"]["categories"]["Ambience"]
    assert "tracks" not in ambience
    assert set(ambience["moods"].keys()) == {"calm", "no mood"}

    calm_tracks = ambience["moods"]["calm"]["tracks"]
    no_mood_tracks = ambience["moods"]["no mood"]["tracks"]
    assert [track["name"] for track in calm_tracks] == ["Legacy A"]
    assert [track["name"] for track in no_mood_tracks] == ["Legacy B"]
