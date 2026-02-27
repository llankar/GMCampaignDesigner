"""Export facade for Savage Fate character sheets."""

from __future__ import annotations

from pathlib import Path

from .html_renderer import render_character_sheet_html

BACKENDS = ("html",)


def _target_for_backend(output_path: str, export_html_only: bool) -> Path:
    base = Path(output_path)
    if export_html_only:
        return base.with_suffix(".html")
    return base.with_suffix(".html")


def _export_with_html(payload: dict, rules_result, output_path: str, export_html_only: bool) -> str:
    html = render_character_sheet_html(payload, rules_result)
    target = _target_for_backend(output_path, export_html_only)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return str(target)


def export_character_sheet(
    payload: dict,
    rules_result,
    output_path: str,
    backend: str = "html",
    export_html_only: bool = True,
) -> tuple[str, str]:
    _ = backend
    out = _export_with_html(payload, rules_result, output_path, export_html_only)
    return out, "html"


__all__ = ["BACKENDS", "export_character_sheet", "render_character_sheet_html"]
