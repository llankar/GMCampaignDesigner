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
    """Attachments come only from explicit attachment fields."""
    clue = tmp_path / "assets" / "clue.png"
    pdf = tmp_path / "docs" / "note.pdf"
    _file(clue)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4\n")

    record = {
        "Portrait": ["assets/portrait.png"],
        "Image": "assets/ignored-image.png",
        "Attachment": "docs/note.pdf, assets/clue.png",
    }

    attachments = collect_entity_attachments(record, campaign_dir=str(tmp_path))

    assert [attachment.label for attachment in attachments] == [
        "note.pdf",
        "clue.png",
    ]
    assert [attachment.is_image for attachment in attachments] == [False, True]
    assert entity_has_attachments(record, campaign_dir=str(tmp_path))


def test_collect_entity_attachments_ignores_media_without_attachment_field(
    tmp_path: Path,
) -> None:
    """Portrait and Image fields should not create GM Table attachments."""
    portrait = tmp_path / "assets" / "portrait.png"
    _file(portrait)

    attachments = collect_entity_attachments(
        {"Portrait": "assets/portrait.png", "Image": "assets/portrait.png"},
        campaign_dir=str(tmp_path),
    )

    assert attachments == []
    assert not entity_has_attachments(
        {"Portrait": "assets/portrait.png", "Image": "assets/portrait.png"},
        campaign_dir=str(tmp_path),
    )


def test_open_attachment_file_uses_platform_launcher(monkeypatch, tmp_path: Path) -> None:
    """Clicking an attachment card should open the linked file with the OS launcher."""
    import modules.scenarios.gm_table.pages as pages
    from modules.scenarios.gm_table.attachments import EntityAttachment

    attachment_path = tmp_path / "docs" / "note.pdf"
    _file(attachment_path)
    launched = []

    monkeypatch.setattr(pages.sys, "platform", "linux")
    monkeypatch.setattr(
        pages.subprocess,
        "Popen",
        lambda args: launched.append(args),
    )

    result = pages.open_attachment_file(
        EntityAttachment(
            field_name="Attachment",
            path=str(attachment_path),
            resolved_path=str(attachment_path),
            label="note.pdf",
            is_image=False,
        )
    )

    assert result is True
    assert launched == [["xdg-open", str(attachment_path.resolve())]]
