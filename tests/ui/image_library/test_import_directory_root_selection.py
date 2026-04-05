"""Tests for image directory import root selection helpers."""

from __future__ import annotations

from modules.ui.image_library.dialogs.import_directories import RecentImportRootsStore, merge_roots, validate_roots


def test_merge_roots_supports_multiple_additions_in_one_operation(tmp_path) -> None:
    """Bulk add should keep every unique normalized root in order."""
    root_a = tmp_path / "assets-a"
    root_b = tmp_path / "assets-b"
    root_a.mkdir()
    root_b.mkdir()

    merged = merge_roots([], [f"  {root_a}  ", str(root_b)])

    assert merged == [str(root_a.resolve()), str(root_b.resolve())]


def test_merge_roots_suppresses_duplicates_after_normalization(tmp_path) -> None:
    """Different textual variants of the same path should collapse to one root."""
    root = tmp_path / "same-root"
    root.mkdir()

    merged = merge_roots([str(root)], [str(root.resolve()), f"{root}/"])

    assert merged == [str(root.resolve())]


def test_validate_roots_handles_mixed_existing_and_missing_directories(tmp_path) -> None:
    """Validation should separate existing roots from missing ones."""
    existing = tmp_path / "existing"
    missing = tmp_path / "missing"
    existing.mkdir()

    result = validate_roots([str(existing), str(missing)])

    assert result.existing_roots == [str(existing.resolve())]
    assert result.missing_roots == [str(missing.resolve())]


def test_recent_roots_store_round_trip_normalizes_and_dedupes(tmp_path) -> None:
    """Persisted recent roots should remain normalized and deduplicated."""
    values: dict[str, str | None] = {}

    def get_setting(key: str, default: str | None = None) -> str | None:
        return values.get(key, default)

    def set_setting(key: str, value: str | None) -> None:
        values[key] = value

    store = RecentImportRootsStore(get_setting=get_setting, set_setting=set_setting)
    root = tmp_path / "recent-root"
    root.mkdir()

    store.save([str(root), str(root.resolve())])

    assert store.load() == [str(root.resolve())]
