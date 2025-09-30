import re

from modules.helpers.list_utils import (
    dedupe_preserve_case,
    format_multi_field_duplicate_summary,
)


def test_dedupe_preserve_case_collapses_mixed_case_duplicates():
    values = ["Test", "Alpha", "test", "ALPHA", "Beta"]

    deduped, duplicates = dedupe_preserve_case(values)

    assert deduped == ["Test", "Alpha", "Beta"]
    assert duplicates == {"Test": ["test"], "Alpha": ["ALPHA"]}


def test_format_multi_field_duplicate_summary_mentions_collapsed_entries():
    duplicates = {
        "Places": {"Test": ["test", "TEST"]},
        "NPCs": {"Rin": ["rin"]},
    }

    message = format_multi_field_duplicate_summary(
        duplicates,
        intro="Note: Duplicate entries were merged because they only differed by letter case.",
    )

    assert message.startswith("Note: Duplicate entries were merged because they only differed by letter case.")
    assert "Places" in message
    assert re.search(r"test, TEST", message)
    assert "→ Test" in message
    assert "NPCs" in message
    assert "rin" in message
    assert "→ Rin" in message
