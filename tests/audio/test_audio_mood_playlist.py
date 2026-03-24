from pathlib import Path

from modules.audio.audio_controller import AudioController
from modules.audio.library.service import AudioLibraryService


def _make_audio_file(base: Path, name: str) -> str:
    path = base / name
    path.write_bytes(b"fake-audio")
    return str(path)


def _new_service(tmp_path: Path) -> AudioLibraryService:
    return AudioLibraryService(path=str(tmp_path / "audio_library.json"))


def test_list_and_remove_track_are_strict_on_category_and_mood(tmp_path: Path) -> None:
    service = _new_service(tmp_path)
    service.add_category("music", "Ambience")
    service.add_mood("music", "Ambience", "calm")
    service.add_mood("music", "Ambience", "tense")

    calm_path = _make_audio_file(tmp_path, "calm.mp3")
    tense_path = _make_audio_file(tmp_path, "tense.mp3")

    added_calm = service.add_tracks("music", "Ambience", "calm", [calm_path])
    added_tense = service.add_tracks("music", "Ambience", "tense", [tense_path])

    assert [track["name"] for track in service.list_tracks("music", "Ambience", mood="calm")] == ["calm"]
    assert [track["name"] for track in service.list_tracks("music", "Ambience", mood="tense")] == ["tense"]

    removed_wrong_bucket = service.remove_track("music", "Ambience", "calm", added_tense[0]["id"])
    assert removed_wrong_bucket is None

    removed_right_bucket = service.remove_track("music", "Ambience", "tense", added_tense[0]["id"])
    assert removed_right_bucket is not None
    assert removed_right_bucket["id"] == added_tense[0]["id"]

    remaining_calm_ids = [track["id"] for track in service.list_tracks("music", "Ambience", mood="calm")]
    assert remaining_calm_ids == [added_calm[0]["id"]]


def test_playlist_stays_coherent_when_switching_mood(tmp_path: Path) -> None:
    service = _new_service(tmp_path)
    service.add_category("music", "Ambience")
    service.add_mood("music", "Ambience", "calm")
    service.add_mood("music", "Ambience", "tense")

    calm_paths = [_make_audio_file(tmp_path, "calm-1.mp3"), _make_audio_file(tmp_path, "calm-2.mp3")]
    tense_paths = [_make_audio_file(tmp_path, "tense-1.mp3")]

    calm_tracks = service.add_tracks("music", "Ambience", "calm", calm_paths)
    tense_tracks = service.add_tracks("music", "Ambience", "tense", tense_paths)

    controller = AudioController(library=service)

    controller.set_playlist("music", calm_tracks, category="Ambience", mood="calm")
    calm_state = controller.get_state("music")
    assert calm_state["category"] == "Ambience"
    assert calm_state["mood"] == "calm"
    assert [track["id"] for track in calm_state["playlist"]] == [track["id"] for track in calm_tracks]

    controller.set_playlist("music", tense_tracks, category="Ambience", mood="tense")
    tense_state = controller.get_state("music")
    assert tense_state["category"] == "Ambience"
    assert tense_state["mood"] == "tense"
    assert [track["id"] for track in tense_state["playlist"]] == [track["id"] for track in tense_tracks]
    assert [track["id"] for track in tense_state["playlist"]] != [track["id"] for track in calm_tracks]
