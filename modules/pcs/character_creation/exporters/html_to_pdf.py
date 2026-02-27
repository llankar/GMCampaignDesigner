"""HTML to PDF conversion backend for character sheets."""

from __future__ import annotations

import importlib
import re
from pathlib import Path


def html_to_pdf(html_content: str, output_path: str) -> str:
    fitz_spec = importlib.util.find_spec("fitz")
    if fitz_spec is None:
        raise RuntimeError("Backend HTML indisponible: PyMuPDF (fitz) n'est pas installé.")

    fitz = importlib.import_module("fitz")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    plain_text = re.sub(r"<[^>]+>", "", html_content)
    plain_text = re.sub(r"\n\s*\n+", "\n\n", plain_text).strip()

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    rect = fitz.Rect(40, 40, 555, 802)
    page.insert_textbox(rect, plain_text, fontsize=10, fontname="helv")
    try:
        doc.save(str(output))
    finally:
        doc.close()
    return str(output)
