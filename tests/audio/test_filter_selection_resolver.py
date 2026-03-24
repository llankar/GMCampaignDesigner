from pathlib import Path

from modules.audio.library.service import AudioLibraryService
from modules.audio.ui.filter_selection_resolver import resolve_category_mood_selection


def _new_service(tmp_path: Path) -> AudioLibraryService:
    return AudioLibraryService(path=str(tmp_path / "audio_library.json"))


def test_resolver_recomputes_moods_for_selected_category(tmp_path: Path) -> None:
    service = _new_service(tmp_path)
    service.add_category("music", "Ambience")
    service.add_category("music", "Battle")
    service.add_mood("music", "Ambience", "calm")
    service.add_mood("music", "Battle", "epic")

    category, mood, moods = resolve_category_mood_selection(
        library=service,
        section="music",
        category="Battle",
        preferred_mood="epic",
    )

    assert category == "Battle"
    assert mood == "epic"
    assert moods == ["epic", "no mood"]
