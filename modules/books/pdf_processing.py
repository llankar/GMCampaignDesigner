"""PDF helper functions for rendering and extracting content.

The helpers in this module centralise common PDF tasks such as rendering pages,
extracting ranges, and pulling embedded images for reuse inside campaigns.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

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


def _sanitize_filename(component: str) -> str:
    """Return a filesystem-safe fragment derived from ``component``."""

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", component).strip("._-")
    return cleaned or "image"


def _extract_section_heading(page: fitz.Page) -> Optional[str]:
    """Attempt to extract a representative heading from the top of the page."""

    # Prefer block-level text to avoid headers/footers being stitched together.
    try:
        blocks = page.get_text("blocks") or []
    except Exception:  # pragma: no cover - PyMuPDF can raise for malformed text
        blocks = []

    for block in sorted(blocks, key=lambda b: (b[1], b[0])):
        text = (block[4] or "").strip()
        if text:
            heading_line = text.splitlines()[0].strip()
            if heading_line:
                return heading_line

    # Fallback to raw text extraction if no block text is available.
    try:
        raw_text = page.get_text("text") or ""
    except Exception:  # pragma: no cover
        raw_text = ""

    heading_line = raw_text.strip().splitlines()[0] if raw_text.strip() else ""
    return heading_line or None


def _extract_paragraph_labels(page: fitz.Page) -> Dict[int, str]:
    """Map image xrefs to the nearest paragraph label on the page using geometry."""

    try:
        raw = page.get_text("rawdict") or {}
    except Exception:  # pragma: no cover - defensive fallback for malformed PDFs
        return {}

    blocks = raw.get("blocks", [])
    text_blocks = _collect_text_blocks(blocks)
    image_blocks = _collect_image_blocks(blocks)

    if not image_blocks:
        return {}

    labeled_blocks = _label_image_blocks(image_blocks, text_blocks)
    image_info = page.get_image_info(xrefs=True)

    labels: Dict[int, str] = {}
    for info in image_info:
        bbox = info.get("bbox") or ()
        xref = info.get("xref")
        if xref is None or len(bbox) != 4:
            continue

        match_index = _match_image_to_block(tuple(bbox), image_blocks)
        if match_index is None:
            continue

        paragraph_label = labeled_blocks.get(match_index)
        if paragraph_label:
            labels[int(xref)] = paragraph_label

    return labels


def _collect_text(block: dict) -> str:
    lines = block.get("lines") or []
    text_parts: list[str] = []
    for line in lines:
        spans = line.get("spans") or []
        for span in spans:
            text_parts.append(span.get("text", ""))
    return "".join(text_parts).strip()


def _collect_text_blocks(blocks: Sequence[dict]) -> List[Tuple[Tuple[float, float, float, float], str]]:
    collected: List[Tuple[Tuple[float, float, float, float], str]] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block.get("bbox") or ()
        if len(bbox) != 4:
            continue
        paragraph_text = _collect_text(block)
        if paragraph_text:
            collected.append((tuple(bbox), paragraph_text))
    return collected


def _collect_image_blocks(blocks: Sequence[dict]) -> List[Tuple[float, float, float, float]]:
    collected: List[Tuple[float, float, float, float]] = []
    for block in blocks:
        if block.get("type") != 1:
            continue
        bbox = block.get("bbox") or ()
        if len(bbox) != 4:
            continue
        collected.append(tuple(bbox))
    return collected


def _label_image_blocks(
    image_blocks: Sequence[Tuple[float, float, float, float]],
    text_blocks: Sequence[Tuple[Tuple[float, float, float, float], str]],
) -> Dict[int, str]:
    labels: Dict[int, str] = {}

    for index, image_bbox in enumerate(image_blocks):
        nearest_text = _find_nearest_text(image_bbox, text_blocks)
        if not nearest_text:
            continue

        _, paragraph_text = nearest_text
        paragraph_label = paragraph_text.splitlines()[0].strip()
        if paragraph_label:
            labels[index] = paragraph_label

    return labels


def _find_nearest_text(
    image_bbox: Tuple[float, float, float, float],
    text_blocks: Sequence[Tuple[Tuple[float, float, float, float], str]],
) -> Optional[Tuple[Tuple[float, float, float, float], str]]:
    """Return the closest text block to an image by bounding box proximity."""

    best_candidate: Optional[Tuple[Tuple[float, float, float, float], str]] = None
    best_score: Optional[float] = None

    for text_bbox, text in text_blocks:
        score = _bbox_distance(image_bbox, text_bbox)
        if best_score is None or score < best_score:
            best_score = score
            best_candidate = (text_bbox, text)

    return best_candidate


def _bbox_distance(
    box_a: Tuple[float, float, float, float], box_b: Tuple[float, float, float, float]
) -> float:
    """Calculate a simple distance metric between two bounding boxes."""

    ax0, ay0, ax1, ay1 = box_a
    bx0, by0, bx1, by1 = box_b

    horizontal_gap = max(bx0 - ax1, ax0 - bx1, 0)
    vertical_gap = max(by0 - ay1, ay0 - by1, 0)

    overlap_penalty = 0.0
    if horizontal_gap == 0 and vertical_gap == 0:
        ax_center, ay_center = _bbox_center(box_a)
        bx_center, by_center = _bbox_center(box_b)
        overlap_penalty = abs(ax_center - bx_center) + abs(ay_center - by_center)

    return horizontal_gap + vertical_gap + overlap_penalty


def _bbox_center(box: Tuple[float, float, float, float]) -> Tuple[float, float]:
    x0, y0, x1, y1 = box
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _match_image_to_block(
    bbox: Tuple[float, float, float, float],
    image_blocks: Sequence[Tuple[float, float, float, float]],
) -> Optional[int]:
    """Find the image block that best matches a given bbox from ``get_image_info``."""

    best_index: Optional[int] = None
    best_score: Optional[float] = None

    for index, block_bbox in enumerate(image_blocks):
        score = _bbox_distance(bbox, block_bbox)
        if best_score is None or score < best_score:
            best_score = score
            best_index = index

    return best_index


def extract_images_with_names(
    attachment_path: str, *, campaign_dir: str | None = None
) -> List[Dict[str, object]]:
    """
    Extract embedded images from a PDF and save them with descriptive filenames.

    Images are written to ``assets/books/images`` beneath the campaign directory
    using a filename derived from the nearest paragraph label when possible,
    otherwise from the XObject name or the current page's heading text. A
    page/sequence suffix is appended to keep names unique. The function returns
    metadata for each exported image.
    """

    pdf_path = _resolve_pdf_path(attachment_path, campaign_dir)
    campaign_root = _resolve_campaign_dir(campaign_dir)
    image_dir = campaign_root / "assets" / "books" / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    document = open_document(attachment_path, campaign_dir=campaign_dir)
    metadata: List[Dict[str, object]] = []
    log_info(
        f"Extracting images from '{pdf_path.name}' into '{image_dir.relative_to(campaign_root)}'.",
        func_name="pdf_processing.extract_images_with_names",
    )

    try:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            section_heading = _extract_section_heading(page)
            paragraph_labels = _extract_paragraph_labels(page)
            images = page.get_images(full=True)

            if not images:
                log_debug(
                    f"No images found on page {page_index + 1}.",
                    func_name="pdf_processing.extract_images_with_names",
                )
                continue

            for image_position, image_info in enumerate(images, start=1):
                xref = image_info[0]
                original_name = None
                if len(image_info) > 7 and image_info[7]:
                    original_name = image_info[7]
                    if isinstance(original_name, bytes):
                        original_name = original_name.decode(errors="ignore")

                paragraph_label = paragraph_labels.get(xref)
                base_name: Optional[str] = None
                if paragraph_label:
                    base_name = _sanitize_filename(paragraph_label)
                if not base_name and original_name:
                    base_name = _sanitize_filename(original_name)
                if not base_name and section_heading:
                    base_name = _sanitize_filename(section_heading)
                if not base_name:
                    base_name = f"page{page_index + 1:04d}_img{image_position:02d}"

                candidate = image_dir / f"{base_name}.png"
                counter = 1
                while candidate.exists():
                    candidate = image_dir / f"{base_name}_{counter}.png"
                    counter += 1

                pixmap = fitz.Pixmap(document, xref)
                if pixmap.n >= 5:  # Convert CMYK or other colorspaces to RGB
                    pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
                pixmap.save(candidate)

                relative_path = candidate.relative_to(campaign_root).as_posix()
                entry = {
                    "path": relative_path,
                    "page": page_index + 1,
                    "paragraph": paragraph_label,
                    "section": section_heading,
                    "original_name": original_name,
                    "sequence": image_position,
                }
                metadata.append(entry)
                log_info(
                    f"Saved image from page {page_index + 1} as '{relative_path}'.",
                    func_name="pdf_processing.extract_images_with_names",
                )

    finally:
        document.close()

    log_debug(
        f"Extracted {len(metadata)} image(s) from '{pdf_path.name}'.",
        func_name="pdf_processing.extract_images_with_names",
    )
    return metadata

