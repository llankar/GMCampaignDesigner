from __future__ import annotations

import os
from pathlib import Path

from typing import TYPE_CHECKING

from modules.helpers.logging_helper import log_warning

if TYPE_CHECKING:
    from docx import Document


def _sanitize_filename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in value)
    safe = "_".join(safe.split())
    return safe or "session_brief"


def _build_markdown(
    *,
    campaign_name: str,
    summary: str,
    active_arcs: list[str],
    arc_details: list[str],
    dashboard_fields: list[str],
    gm_priority_notes: list[str],
) -> str:
    lines: list[str] = [
        f"# Session brief — {campaign_name}",
        "",
        "## Résumé",
        summary.strip() or "Aucun résumé disponible.",
        "",
        "## Arcs actifs",
    ]

    if active_arcs:
        lines.extend([f"- {arc}" for arc in active_arcs])
    else:
        lines.append("- Aucun arc actif.")

    lines.extend(["", "## Détails des arcs"])
    if arc_details:
        lines.extend([f"- {arc}" for arc in arc_details])
    else:
        lines.append("- Aucun détail d'arc.")

    lines.extend(["", "## Champs dashboard"])
    if dashboard_fields:
        lines.extend([f"- {field}" for field in dashboard_fields])
    else:
        lines.append("- Aucun champ dashboard.")

    lines.extend(["", "## Notes MJ prioritaires"])
    if gm_priority_notes:
        lines.extend([f"- {note}" for note in gm_priority_notes])
    else:
        lines.append("- Aucune note prioritaire.")

    lines.append("")
    return "\n".join(lines)


def _convert_docx_to_pdf(docx_path: str, pdf_path: str) -> bool:
    try:
        from docx2pdf import convert
    except Exception:
        return False

    try:
        convert(docx_path, pdf_path)
    except Exception as exc:
        log_warning(
            f"Session brief PDF conversion failed: {exc}",
            func_name="modules.exports.session_brief.exporter._convert_docx_to_pdf",
        )
        return False
    return os.path.exists(pdf_path)


def _build_docx_document(
    *,
    campaign_name: str,
    summary: str,
    active_arcs: list[str],
    arc_details: list[str],
    dashboard_fields: list[str],
    gm_priority_notes: list[str],
):
    from docx import Document

    document = Document()
    document.add_heading(f"Session brief — {campaign_name}", level=1)

    def add_section(title: str, values: list[str] | None = None, paragraph_text: str | None = None) -> None:
        document.add_heading(title, level=2)
        if paragraph_text is not None:
            document.add_paragraph(paragraph_text)
            return
        for value in values or []:
            document.add_paragraph(value, style="List Bullet")

    add_section("Résumé", paragraph_text=summary.strip() or "Aucun résumé disponible.")
    add_section("Arcs actifs", values=active_arcs or ["Aucun arc actif."])
    add_section("Détails des arcs", values=arc_details or ["Aucun détail d'arc."])
    add_section("Champs dashboard", values=dashboard_fields or ["Aucun champ dashboard."])
    add_section("Notes MJ prioritaires", values=gm_priority_notes or ["Aucune note prioritaire."])

    return document


def export_session_brief(
    *,
    campaign_name: str,
    summary: str,
    active_arcs: list[str],
    arc_details: list[str],
    dashboard_fields: list[str],
    gm_priority_notes: list[str],
    output_format: str,
    output_path: str,
) -> str:
    """Export a session brief to markdown, DOCX, or lightweight PDF.

    Returns the exported file path.
    """

    export_format = (output_format or "markdown").strip().lower()
    target_path = Path(output_path)

    if export_format == "markdown":
        if target_path.suffix.lower() != ".md":
            target_path = target_path.with_suffix(".md")
        payload = _build_markdown(
            campaign_name=campaign_name,
            summary=summary,
            active_arcs=active_arcs,
            arc_details=arc_details,
            dashboard_fields=dashboard_fields,
            gm_priority_notes=gm_priority_notes,
        )
        target_path.write_text(payload, encoding="utf-8")
        return str(target_path)

    if export_format in {"docx", "pdf"}:
        docx_path = target_path.with_suffix(".docx")
        try:
            document = _build_docx_document(
                campaign_name=campaign_name,
                summary=summary,
                active_arcs=active_arcs,
                arc_details=arc_details,
                dashboard_fields=dashboard_fields,
                gm_priority_notes=gm_priority_notes,
            )
            document.save(str(docx_path))
        except Exception as exc:
            log_warning(
                f"Session brief DOCX generation failed: {exc}",
                func_name="modules.exports.session_brief.exporter.export_session_brief",
            )
            markdown_fallback_path = target_path.with_suffix(".md")
            markdown_fallback_path.write_text(
                _build_markdown(
                    campaign_name=campaign_name,
                    summary=summary,
                    active_arcs=active_arcs,
                    arc_details=arc_details,
                    dashboard_fields=dashboard_fields,
                    gm_priority_notes=gm_priority_notes,
                ),
                encoding="utf-8",
            )
            return str(markdown_fallback_path)

        if export_format == "docx":
            return str(docx_path)

        pdf_path = target_path.with_suffix(".pdf")
        if _convert_docx_to_pdf(str(docx_path), str(pdf_path)):
            try:
                docx_path.unlink(missing_ok=True)
            except Exception:
                pass
            return str(pdf_path)

        return str(docx_path)

    suggested_name = _sanitize_filename(campaign_name)
    raise ValueError(f"Unsupported format '{output_format}' for {suggested_name}")
