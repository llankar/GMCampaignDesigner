"""Utilities for importing and indexing book records."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from pypdf import PdfReader

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_info, log_module_import, log_warning

log_module_import(__name__)

try:  # Optional OCR dependencies
    from pdf2image import convert_from_path  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    convert_from_path = None

try:  # Optional OCR dependencies
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pytesseract = None

_OCR_AVAILABLE = convert_from_path is not None and pytesseract is not None

ASSET_SUBDIR = "books"


def prepare_books_from_files(
    file_paths: Sequence[str], *, campaign_dir: str | None = None
) -> List[dict]:
    """Prepare book records from arbitrary PDF file selections."""

    normalized_paths = [Path(path) for path in file_paths or []]
    return _prepare_books(normalized_paths, base_dir=None, campaign_dir=campaign_dir)


def prepare_books_from_directory(
    directory_path: str, *, campaign_dir: str | None = None
) -> List[dict]:
    """Prepare book records for every PDF within ``directory_path`` (recursively)."""

    base_dir = Path(directory_path)
    if not base_dir.exists() or not base_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    pdf_files = sorted(base_dir.rglob("*.pdf"))
    return _prepare_books(pdf_files, base_dir=base_dir, campaign_dir=campaign_dir)


def extract_text_from_book(
    attachment_path: str, *, campaign_dir: str | None = None
) -> Tuple[int, str, List[str]]:
    """Extract page count and text for a persisted book attachment."""

    campaign_dir = _resolve_campaign_dir(campaign_dir)
    pdf_path = Path(attachment_path or "")
    if not pdf_path.is_absolute():
        pdf_path = Path(campaign_dir) / pdf_path
    pdf_path = pdf_path.resolve()

    if not pdf_path.exists():
        raise FileNotFoundError(f"Attachment not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    page_texts: List[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - defensive catch
            log_warning(
                f"Failed to extract text from page {index} of {pdf_path.name}: {exc}",
                func_name="book_importer.extract_text_from_book",
            )
            text = ""
        if not text and _OCR_AVAILABLE:
            text = _run_ocr_on_page(pdf_path, index)
        page_texts.append(text.strip())

    full_text = "\n\n".join(filter(None, page_texts)).strip()
    return len(reader.pages), full_text, page_texts


# ---------------------------------------------------------------------------
# Internal helpers


def _prepare_books(
    paths: Iterable[Path], *, base_dir: Path | None, campaign_dir: str | None
) -> List[dict]:
    campaign_dir = _resolve_campaign_dir(campaign_dir)
    records: List[dict] = []
    seen_sources = set()

    for source in paths:
        if not isinstance(source, Path):
            continue
        if not source.exists() or not source.is_file():
            continue
        if source.suffix.lower() != ".pdf":
            continue

        resolved_source = source.resolve()
        if resolved_source in seen_sources:
            continue
        seen_sources.add(resolved_source)

        dest_path, rel_path = _copy_pdf_to_assets(resolved_source, campaign_dir)
        title = _title_from_filename(resolved_source)
        folder, tags = _folder_and_tags_for(resolved_source, base_dir)
        page_count = _count_pdf_pages(dest_path)

        record = {
            "Title": title,
            "Subject": "",
            "Game": "",
            "Folder": folder,
            "Tags": tags,
            "PageCount": page_count,
            "Notes": "",
            "Attachment": rel_path,
            "ExtractedText": "",
            "ExtractedPages": [],
            "IndexStatus": "queued",
        }
        records.append(record)

    return records


def _resolve_campaign_dir(campaign_dir: str | None) -> str:
    return campaign_dir or ConfigHelper.get_campaign_dir()


def _copy_pdf_to_assets(source: Path, campaign_dir: str) -> Tuple[Path, str]:
    dest_dir = Path(campaign_dir) / "assets" / ASSET_SUBDIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / source.name
    source_resolved = source.resolve()

    counter = 1
    while dest_path.exists() and dest_path.resolve() != source_resolved:
        dest_path = dest_dir / f"{source.stem}_{counter}{source.suffix}"
        counter += 1

    if dest_path.resolve() != source_resolved:
        shutil.copy2(source_resolved, dest_path)

    rel_path = dest_path.resolve().relative_to(Path(campaign_dir).resolve()).as_posix()
    log_info(
        f"Copied PDF '{source_resolved.name}' to '{rel_path}'",
        func_name="book_importer._copy_pdf_to_assets",
    )
    return dest_path.resolve(), rel_path


def _title_from_filename(path: Path) -> str:
    stem = path.stem
    cleaned = re.sub(r"[_-]+", " ", stem).strip()
    return cleaned.title() if cleaned else path.name


def _folder_and_tags_for(path: Path, base_dir: Path | None) -> Tuple[str, List[str]]:
    if base_dir and base_dir.exists():
        try:
            rel_parent = path.parent.resolve().relative_to(base_dir.resolve())
            parts = [part for part in rel_parent.parts if part and part != "."]
        except ValueError:
            parts = [path.parent.name] if path.parent.name else []
    else:
        parts = [path.parent.name] if path.parent.name else []

    folder = "/".join(parts)
    tags: List[str] = []
    seen = set()
    for part in parts:
        label = re.sub(r"[_-]+", " ", part).strip()
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        tags.append(label.title())

    return folder, tags


def _count_pdf_pages(path: Path) -> int:
    try:
        reader = PdfReader(str(path))
        return len(reader.pages)
    except Exception as exc:  # pragma: no cover - defensive catch
        log_warning(
            f"Unable to count pages for '{path}': {exc}",
            func_name="book_importer._count_pdf_pages",
        )
        return 0


def _run_ocr_on_page(pdf_path: Path, page_number: int) -> str:
    if not _OCR_AVAILABLE:
        return ""

    try:
        images = convert_from_path(
            str(pdf_path),
            first_page=page_number,
            last_page=page_number,
        )
    except Exception as exc:  # pragma: no cover - optional dependency failure
        log_warning(
            f"Failed to render page {page_number} of {pdf_path.name} for OCR: {exc}",
            func_name="book_importer._run_ocr_on_page",
        )
        return ""

    texts: List[str] = []
    for image in images:
        try:
            text = pytesseract.image_to_string(image)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive catch
            log_warning(
                f"OCR failed on page {page_number} of {pdf_path.name}: {exc}",
                func_name="book_importer._run_ocr_on_page",
            )
            continue
        texts.append(text.strip())

    return "\n".join(filter(None, texts)).strip()

