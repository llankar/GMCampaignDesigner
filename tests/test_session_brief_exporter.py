from pathlib import Path

from modules.exports.session_brief import export_session_brief


def test_export_session_brief_markdown(tmp_path: Path):
    output = tmp_path / "brief.md"
    path = export_session_brief(
        campaign_name="Dragonfall",
        summary="Résumé rapide",
        active_arcs=["Arc One — Recover relic"],
        linked_scenarios=["Scene 1"],
        gm_priority_notes=["Protect the witness"],
        output_format="markdown",
        output_path=str(output),
    )

    exported = Path(path)
    assert exported.exists()
    text = exported.read_text(encoding="utf-8")
    assert "# Session brief — Dragonfall" in text
    assert "## Arcs actifs" in text
    assert "- Arc One — Recover relic" in text


def test_export_session_brief_pdf_fallback_returns_non_pdf_file_when_unavailable(tmp_path: Path):
    output = tmp_path / "brief.pdf"

    path = export_session_brief(
        campaign_name="Dragonfall",
        summary="Résumé rapide",
        active_arcs=[],
        linked_scenarios=[],
        gm_priority_notes=[],
        output_format="pdf",
        output_path=str(output),
    )

    exported = Path(path)
    assert exported.exists()
    assert exported.suffix in {".docx", ".md"}
