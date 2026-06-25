"""Regression tests for GM Table entity attachment discovery."""

from pathlib import Path

from modules.scenarios.gm_table.attachments import (
    collect_entity_attachments,
    entity_has_attachments,
)


def _file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")


def test_collect_entity_attachments_handles_multiple_attachment_formats(
    tmp_path: Path,
) -> None:
    """Attachments can come from images, portrait lists, and delimited attachment fields."""
    portrait = tmp_path / "assets" / "portrait.png"
    clue = tmp_path / "assets" / "clue.png"
    pdf = tmp_path / "docs" / "note.pdf"
    _file(portrait)
    _file(clue)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4\n")

    record = {
        "Portrait": ["assets/portrait.png"],
        "Attachment": "docs/note.pdf, assets/clue.png",
    }

    attachments = collect_entity_attachments(record, campaign_dir=str(tmp_path))

    assert [attachment.label for attachment in attachments] == [
        "portrait.png",
        "note.pdf",
        "clue.png",
    ]
    assert [attachment.is_image for attachment in attachments] == [True, False, True]
    assert entity_has_attachments(record, campaign_dir=str(tmp_path))


def test_collect_entity_attachments_deduplicates_media_paths(tmp_path: Path) -> None:
    """The same file listed in Portrait and Image should render once."""
    portrait = tmp_path / "assets" / "portrait.png"
    _file(portrait)

    attachments = collect_entity_attachments(
        {"Portrait": "assets/portrait.png", "Image": "assets/portrait.png"},
        campaign_dir=str(tmp_path),
    )

    assert len(attachments) == 1
    assert attachments[0].label == "portrait.png"
