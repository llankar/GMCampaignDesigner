"""PDF helper functions for rendering and extracting content."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import fitz  # PyMuPDF
from PIL import Image
from pypdf import PdfReader, PdfWriter

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import (
    log_debug,
    log_info,
    log_module_import,
)

log_module_import(__name__)


def _resolve_campaign_dir(campaign_dir: str | None) -> Path:
    base = Path(campaign_dir or ConfigHelper.get_campaign_dir()).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def _resolve_pdf_path(attachment_path: str, campaign_dir: str | None) -> Path:
    campaign_root = _resolve_campaign_dir(campaign_dir)
    pdf_path = Path(attachment_path or "")
    if not pdf_path.is_absolute():
        pdf_path = campaign_root / pdf_path
    resolved = pdf_path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"PDF not found: {resolved}")
    return resolved


def open_document(attachment_path: str, *, campaign_dir: str | None = None) -> fitz.Document:
    """Open a PDF attachment and return a PyMuPDF document instance."""

    pdf_path = _resolve_pdf_path(attachment_path, campaign_dir)
    log_debug(f"Opening PDF document: {pdf_path}", func_name="pdf_processing.open_document")
    return fitz.open(pdf_path)


def render_pdf_page_to_image(
    attachment_path: str,
    page_number: int,
    *,
    zoom: float = 1.0,
    campaign_dir: str | None = None,
    document: fitz.Document | None = None,
) -> Image.Image:
    """Rasterize a PDF page and return it as a ``PIL.Image`` instance."""

    if page_number < 1:
        raise ValueError("page_number must be >= 1")

    close_document = False
    if document is None:
        document = open_document(attachment_path, campaign_dir=campaign_dir)
        close_document = True

    try:
        index = page_number - 1
        if index >= document.page_count:
            raise IndexError(f"Page {page_number} is out of range (1-{document.page_count}).")
        matrix = fitz.Matrix(zoom, zoom)
        pix = document.load_page(index).get_pixmap(matrix=matrix, alpha=False)
        mode = "RGBA" if pix.alpha else "RGB"
        image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        log_debug(
            f"Rendered page {page_number} at zoom {zoom:.2f} ({pix.width}x{pix.height}).",
            func_name="pdf_processing.render_pdf_page_to_image",
        )
        return image
    finally:
        if close_document:
            document.close()


def get_pdf_page_count(attachment_path: str, *, campaign_dir: str | None = None) -> int:
    """Return the total number of pages for the PDF attachment."""

    pdf_path = _resolve_pdf_path(attachment_path, campaign_dir)
    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    log_debug(
        f"PDF '{pdf_path.name}' has {page_count} page(s).",
        func_name="pdf_processing.get_pdf_page_count",
    )
    return page_count


def export_pdf_page_range(
    attachment_path: str,
    start_page: int,
    end_page: int,
    *,
    campaign_dir: str | None = None,
) -> Dict[str, object]:
    """Export a selection of pages to ``assets/books/excerpts`` and return metadata."""

    if start_page < 1 or end_page < 1:
        raise ValueError("Page numbers must be greater than zero.")
    if end_page < start_page:
        raise ValueError("end_page must be greater than or equal to start_page.")

    pdf_path = _resolve_pdf_path(attachment_path, campaign_dir)
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    if start_page > total_pages or end_page > total_pages:
        raise ValueError(
            f"Page range {start_page}-{end_page} exceeds document page count ({total_pages})."
        )

    writer = PdfWriter()
    for index in range(start_page - 1, end_page):
        writer.add_page(reader.pages[index])

    campaign_root = _resolve_campaign_dir(campaign_dir)
    excerpt_dir = campaign_root / "assets" / "books" / "excerpts"
    excerpt_dir.mkdir(parents=True, exist_ok=True)

    base_name = pdf_path.stem
    range_label = f"pp{start_page:04d}-{end_page:04d}" if start_page != end_page else f"p{start_page:04d}"
    candidate = excerpt_dir / f"{base_name}_{range_label}.pdf"
    counter = 1
    while candidate.exists():
        candidate = excerpt_dir / f"{base_name}_{range_label}_{counter}.pdf"
        counter += 1

    with candidate.open("wb") as handle:
        writer.write(handle)

    relative_path = candidate.relative_to(campaign_root).as_posix()
    log_info(
        f"Exported pages {start_page}-{end_page} from '{pdf_path.name}' to '{relative_path}'.",
        func_name="pdf_processing.export_pdf_page_range",
    )

    return {
        "page_range": (start_page, end_page),
        "path": relative_path,
        "filename": candidate.name,
        "total_pages": total_pages,
    }

