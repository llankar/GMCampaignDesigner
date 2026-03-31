"""Regression tests for session brief exporter."""

from pathlib import Path

from modules.exports.session_brief import export_session_brief
from modules.exports.session_brief import exporter as session_brief_exporter


def test_export_session_brief_markdown(tmp_path: Path):
    """Verify that export session brief markdown."""
    output = tmp_path / "brief.md"
    path = export_session_brief(
        campaign_name="Dragonfall",
        summary="Résumé rapide",
        active_arcs=["Arc One — Recover relic"],
        arc_details=["Arc 1: Arc One | objective: Recover relic | status: In Progress"],
        dashboard_fields=["Summary: Résumé rapide", "CriticalNPCs: Witness X"],
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
    assert "## Détails des arcs" in text
    assert "Arc 1: Arc One | objective: Recover relic | status: In Progress" in text
    assert "## Champs dashboard" in text
    assert "Summary: Résumé rapide" in text



def test_export_session_brief_docx(tmp_path: Path, monkeypatch):
    """Verify that export session brief docx."""
    class _FakeDocument:
        def save(self, path: str) -> None:
            """Save the operation."""
            Path(path).write_bytes(b"fake-docx")

    monkeypatch.setattr(session_brief_exporter, "_build_docx_document", lambda **_: _FakeDocument())

    output = tmp_path / "brief.docx"
    path = export_session_brief(
        campaign_name="Dragonfall",
        summary="Résumé rapide",
        active_arcs=["Arc One — Recover relic"],
        arc_details=["Arc 1: Arc One | objective: Recover relic | status: In Progress"],
        dashboard_fields=["Summary: Résumé rapide", "CriticalNPCs: Witness X"],
        gm_priority_notes=["Protect the witness"],
        output_format="docx",
        output_path=str(output),
    )

    exported = Path(path)
    assert exported.exists()
    assert exported.suffix == ".docx"


def test_export_session_brief_pdf_fallback_returns_non_pdf_file_when_unavailable(tmp_path: Path):
    """Verify that export session brief PDF fallback returns non PDF file when unavailable."""
    output = tmp_path / "brief.pdf"

    path = export_session_brief(
        campaign_name="Dragonfall",
        summary="Résumé rapide",
        active_arcs=[],
        arc_details=[],
        dashboard_fields=[],
        gm_priority_notes=[],
        output_format="pdf",
        output_path=str(output),
    )

    exported = Path(path)
    assert exported.exists()
    assert exported.suffix in {".docx", ".md"}
