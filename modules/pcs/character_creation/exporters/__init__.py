"""Export facade for Savage Fate character sheets."""

from __future__ import annotations

import importlib
from pathlib import Path

from .html_renderer import render_character_sheet_html
from .html_to_pdf import html_to_pdf

BACKENDS = ("fitz", "html", "docx")


def _target_for_backend(output_path: str, backend: str, export_html_only: bool) -> Path:
    base = Path(output_path)
    if export_html_only:
        return base.with_suffix(".html")
    if backend in ("fitz", "html"):
        return base.with_suffix(".pdf")
    if backend == "docx":
        return base.with_suffix(".docx")
    return base


def _export_with_fitz(payload: dict, rules_result, output_path: str) -> str:
    from ..pdf_exporter import export_character_pdf

    return export_character_pdf(payload, rules_result, output_path)


def _export_with_html(payload: dict, rules_result, output_path: str, export_html_only: bool) -> str:
    html = render_character_sheet_html(payload, rules_result)
    target = _target_for_backend(output_path, "html", export_html_only)
    if export_html_only:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        return str(target)
    return html_to_pdf(html, str(target))


def _export_with_docx(payload: dict, rules_result, output_path: str) -> str:
    spec = importlib.util.find_spec("docx")
    if spec is None:
        raise RuntimeError("Backend DOCX indisponible: python-docx n'est pas installé.")
    docx = importlib.import_module("docx")

    document = docx.Document()
    document.add_heading("Savage Fate - Character Creation", level=1)
    document.add_paragraph(f"Nom: {payload.get('name', '')}")
    document.add_paragraph(f"Joueur: {payload.get('player', '')}")
    document.add_paragraph(f"Concept: {payload.get('concept', '')}")
    document.add_paragraph(f"Défaut: {payload.get('flaw', '')}")
    document.add_paragraph(f"Atout de groupe: {payload.get('group_asset', '')}")
    document.add_paragraph(f"Rang: {getattr(rules_result, 'rank_name', '')}")

    document.add_heading("Compétences", level=2)
    for skill, die in (getattr(rules_result, "skill_dice", {}) or {}).items():
        document.add_paragraph(f"- {skill}: {die}")

    target = _target_for_backend(output_path, "docx", False)
    target.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(target))
    return str(target)


def export_character_sheet(
    payload: dict,
    rules_result,
    output_path: str,
    backend: str = "fitz",
    export_html_only: bool = False,
) -> tuple[str, str]:
    selected = backend if backend in BACKENDS else "fitz"
    ordered = [selected] + [candidate for candidate in BACKENDS if candidate != selected]

    last_error = None
    for candidate in ordered:
        try:
            if candidate == "fitz":
                target = _target_for_backend(output_path, candidate, export_html_only)
                return _export_with_fitz(payload, rules_result, str(target)), candidate
            if candidate == "html":
                return _export_with_html(payload, rules_result, output_path, export_html_only), candidate
            if candidate == "docx":
                if export_html_only:
                    continue
                return _export_with_docx(payload, rules_result, output_path), candidate
        except Exception as exc:  # fallback behavior required by UI spec
            last_error = exc

    raise RuntimeError(f"Tous les backends d'export ont échoué: {last_error}")


__all__ = ["BACKENDS", "export_character_sheet", "render_character_sheet_html"]
