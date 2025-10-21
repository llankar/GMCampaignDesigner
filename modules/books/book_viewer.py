"""Interactive PDF book viewer for campaign assets."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import ImageTk

from modules.books.pdf_processing import open_document, render_pdf_page_to_image
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import (
    log_debug,
    log_info,
    log_warning,
    log_module_import,
)

log_module_import(__name__)


class BookViewer(ctk.CTkToplevel):
    """A window capable of displaying PDF books with navigation and search."""

    def __init__(self, master, book_record: dict):
        super().__init__(master)
        self.book_record = dict(book_record or {})
        self.campaign_dir = ConfigHelper.get_campaign_dir()
        self.attachment = self.book_record.get("Attachment", "")
        self._document = None
        self._page_image = None
        self._search_cache: list[int] = []
        self._search_query = ""
        self._search_index = -1

        self.title(self.book_record.get("Title") or "Book Viewer")
        self.geometry("1024x768")
        self.minsize(720, 480)

        self.current_page = 1
        self.zoom = 1.25

        try:
            self._document = open_document(self.attachment, campaign_dir=self.campaign_dir)
        except Exception as exc:
            log_warning(
                f"Failed to open book attachment '{self.attachment}': {exc}",
                func_name="BookViewer.__init__",
            )
            messagebox.showerror("Book Viewer", f"Unable to open the book:\n{exc}")
            self.destroy()
            return

        self.page_count = getattr(self._document, "page_count", 0) or 0
        if not self.page_count:
            self.page_count = self.book_record.get("PageCount") or 0

        self._page_texts = self._collect_page_texts()

        self._build_ui()
        self._render_current_page()

        self.bind("<MouseWheel>", self._on_mouse_wheel)
        self.bind("<Shift-MouseWheel>", self._on_shift_mouse_wheel)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        controls = ctk.CTkFrame(self)
        controls.pack(fill="x", padx=10, pady=(10, 5))

        prev_btn = ctk.CTkButton(controls, text="◀", width=40, command=self.previous_page)
        prev_btn.pack(side="left", padx=(0, 5))

        next_btn = ctk.CTkButton(controls, text="▶", width=40, command=self.next_page)
        next_btn.pack(side="left", padx=(0, 10))

        self.page_var = tk.StringVar(value=str(self.current_page))
        self.page_entry = ctk.CTkEntry(controls, width=60, textvariable=self.page_var)
        self.page_entry.pack(side="left")
        self.page_entry.bind("<Return>", lambda _e: self.go_to_page_from_entry())

        self.page_label = ctk.CTkLabel(
            controls,
            text=self._format_page_label(),
        )
        self.page_label.pack(side="left", padx=10)

        zoom_out_btn = ctk.CTkButton(controls, text="−", width=40, command=lambda: self.adjust_zoom(-0.25))
        zoom_out_btn.pack(side="left")
        zoom_in_btn = ctk.CTkButton(controls, text="+", width=40, command=lambda: self.adjust_zoom(0.25))
        zoom_in_btn.pack(side="left", padx=(5, 0))

        self.zoom_label = ctk.CTkLabel(controls, text=self._format_zoom_label())
        self.zoom_label.pack(side="left", padx=10)

        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(search_frame, text="Search:").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda _e: self.search_forward())

        find_prev = ctk.CTkButton(search_frame, text="Prev", width=70, command=self.search_backward)
        find_prev.pack(side="left", padx=(5, 0))
        find_next = ctk.CTkButton(search_frame, text="Next", width=70, command=self.search_forward)
        find_next.pack(side="left", padx=(5, 0))

        self.search_status = ctk.CTkLabel(search_frame, text="")
        self.search_status.pack(side="left", padx=10)

        viewer_frame = ctk.CTkFrame(self)
        viewer_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        viewer_frame.grid_rowconfigure(0, weight=1)
        viewer_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(viewer_frame, background="#1E1E1E", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.v_scroll = ctk.CTkScrollbar(viewer_frame, orientation="vertical", command=self.canvas.yview)
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll = ctk.CTkScrollbar(viewer_frame, orientation="horizontal", command=self.canvas.xview)
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        self.canvas.bind("<Configure>", lambda _e: self._center_image())

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _collect_page_texts(self) -> list[str]:
        def normalize_page_number(value) -> int | None:
            try:
                if isinstance(value, str) and not value.strip():
                    return None
                if isinstance(value, (int, float)):
                    return int(value)
                if isinstance(value, str):
                    return int(float(value))
            except (TypeError, ValueError):
                return None
            return None

        pages_raw = self.book_record.get("ExtractedPages")
        sequential_texts: list[str] = []
        numbered_pages: dict[int, str] = {}
        pages_marked_as_excerpt = False

        if isinstance(pages_raw, list):
            for entry in pages_raw:
                text_value: str | None = None
                page_number: int | None = None

                if isinstance(entry, str):
                    text_value = entry
                elif isinstance(entry, dict):
                    lowered_keys = {str(key).lower(): key for key in entry.keys()}
                    entry_type_key = lowered_keys.get("type")
                    if entry_type_key:
                        entry_type = entry.get(entry_type_key)
                        if isinstance(entry_type, str) and entry_type.strip().lower() == "excerpt":
                            pages_marked_as_excerpt = True
                    if "path" in lowered_keys and "page" not in lowered_keys and "pagenumber" not in lowered_keys:
                        pages_marked_as_excerpt = True

                    for key in ("Text", "text", "Content", "content"):
                        if key in entry and isinstance(entry[key], str):
                            text_value = entry[key]
                            break

                    for key in ("Page", "page", "PageNumber", "pagenumber", "Index", "index"):
                        if key in entry:
                            page_number = normalize_page_number(entry[key])
                            if page_number is not None:
                                break

                if text_value is None:
                    text_value = ""

                text_value = str(text_value).strip()

                if page_number is not None:
                    numbered_pages[page_number] = text_value
                else:
                    sequential_texts.append(text_value)

        highest_numbered_page = max(numbered_pages) if numbered_pages else 0
        record_texts: list[str] = []
        if numbered_pages:
            target_count = self.page_count or highest_numbered_page
            for index in range(1, target_count + 1):
                record_texts.append(numbered_pages.get(index, "").strip())
        elif sequential_texts:
            record_texts = [text.strip() for text in sequential_texts]

        def normalize_to_page_count(texts: list[str]) -> list[str]:
            normalized = list(texts)
            if self.page_count:
                if len(normalized) < self.page_count:
                    normalized.extend([""] * (self.page_count - len(normalized)))
                elif len(normalized) > self.page_count:
                    normalized = normalized[: self.page_count]
            return normalized

        def covers_full_book(texts: list[str]) -> bool:
            if not texts or pages_marked_as_excerpt:
                return False

            if numbered_pages:
                required_pages = max(self.page_count or 0, highest_numbered_page)
                if required_pages <= 0:
                    required_pages = len(numbered_pages)

                distinct_pages = {page for page in numbered_pages.keys() if page is not None}
                if len(distinct_pages) < required_pages:
                    return False

                non_empty_pages = {
                    page
                    for page, text in numbered_pages.items()
                    if str(text or "").strip()
                }
                if len(non_empty_pages) < required_pages:
                    return False

                if len(texts) < required_pages:
                    return False

                return True

            non_empty_entries = sum(1 for text in texts if str(text or "").strip())
            if self.page_count:
                return len(texts) >= self.page_count and non_empty_entries >= self.page_count
            return len(texts) > 1 and non_empty_entries == len(texts)

        if covers_full_book(record_texts):
            return normalize_to_page_count(record_texts)

        extracted = self._extract_page_texts_from_pdf()
        has_pdf_content = any(text.strip() for text in extracted)
        if has_pdf_content:
            if record_texts and self.book_record.get("IndexStatus") == "indexed" and not pages_marked_as_excerpt:
                limit = min(len(record_texts), len(extracted))
                for index in range(limit):
                    if record_texts[index]:
                        extracted[index] = record_texts[index]
            return extracted

        transcript_pages = self._split_transcript_into_pages(self.book_record.get("ExtractedText"))
        if transcript_pages:
            if self.page_count:
                if len(transcript_pages) < self.page_count:
                    transcript_pages.extend([""] * (self.page_count - len(transcript_pages)))
                elif len(transcript_pages) > self.page_count:
                    transcript_pages = transcript_pages[: self.page_count]
            return transcript_pages

        if covers_full_book(record_texts):
            return normalize_to_page_count(record_texts)

        return extracted

    def _split_transcript_into_pages(self, transcript) -> list[str]:
        if not isinstance(transcript, str):
            return []

        cleaned = transcript.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not cleaned:
            return []

        for separator in ("\f", "\u000c"):
            if separator in cleaned:
                return [part.strip() for part in cleaned.split(separator)]

        if self.page_count and self.page_count > 0:
            approx_length = max(1, len(cleaned) // self.page_count)
            pages: list[str] = []
            start = 0
            for _ in range(self.page_count - 1):
                end = start + approx_length
                pages.append(cleaned[start:end].strip())
                start = end
            pages.append(cleaned[start:].strip())
            return pages

        return [cleaned]

    def _extract_page_texts_from_pdf(self) -> list[str]:
        texts: list[str] = []
        if not self._document:
            return texts

        total_pages = getattr(self._document, "page_count", 0) or 0
        if not total_pages:
            return texts

        for index in range(total_pages):
            try:
                page = self._document.load_page(index)
                text = page.get_text("text") or ""
            except Exception as exc:  # pragma: no cover - defensive catch
                log_warning(
                    f"Failed to extract text for page {index + 1}: {exc}",
                    func_name="BookViewer._extract_page_texts_from_pdf",
                )
                text = ""
            texts.append(text.strip())

        return texts

    def _render_current_page(self):
        if not self._document:
            return
        try:
            image = render_pdf_page_to_image(
                self.attachment,
                self.current_page,
                zoom=self.zoom,
                campaign_dir=self.campaign_dir,
                document=self._document,
            )
        except Exception as exc:
            log_warning(
                f"Unable to render page {self.current_page}: {exc}",
                func_name="BookViewer._render_current_page",
            )
            messagebox.showerror("Book Viewer", f"Failed to render page {self.current_page}:\n{exc}")
            return

        self._page_image = ImageTk.PhotoImage(image)
        self.canvas.delete("page")
        self.canvas.create_image(0, 0, image=self._page_image, anchor="nw", tags="page")
        self.canvas.configure(scrollregion=(0, 0, image.width, image.height))
        self.page_label.configure(text=self._format_page_label())
        self.page_var.set(str(self.current_page))
        self.zoom_label.configure(text=self._format_zoom_label())
        self._center_image()
        log_debug(
            f"Displayed page {self.current_page} at zoom {self.zoom:.2f}.",
            func_name="BookViewer._render_current_page",
        )

    def _center_image(self):
        bbox = self.canvas.bbox("page")
        if not bbox:
            return
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        image_width = bbox[2] - bbox[0]
        image_height = bbox[3] - bbox[1]
        x = max((canvas_width - image_width) // 2, 0)
        y = max((canvas_height - image_height) // 2, 0)
        self.canvas.coords("page", x, y)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _format_page_label(self) -> str:
        if self.page_count:
            return f"Page {self.current_page} / {self.page_count}"
        return f"Page {self.current_page}"

    def _format_zoom_label(self) -> str:
        return f"Zoom: {int(self.zoom * 100)}%"

    def go_to_page_from_entry(self):
        try:
            page = int(self.page_var.get())
        except (TypeError, ValueError):
            messagebox.showwarning("Book Viewer", "Enter a valid page number.")
            return
        self.go_to_page(page)

    def go_to_page(self, page: int):
        if page < 1:
            page = 1
        if self.page_count:
            page = min(page, self.page_count)
        if page == self.current_page:
            return
        self.current_page = page
        log_info(f"Navigating to page {page}", func_name="BookViewer.go_to_page")
        self._render_current_page()

    def previous_page(self):
        self.go_to_page(self.current_page - 1)

    def next_page(self):
        self.go_to_page(self.current_page + 1)

    def adjust_zoom(self, delta: float):
        new_zoom = max(0.5, min(4.0, self.zoom + delta))
        if abs(new_zoom - self.zoom) < 1e-3:
            return
        self.zoom = new_zoom
        log_info(f"Adjusting zoom to {self.zoom:.2f}", func_name="BookViewer.adjust_zoom")
        self._render_current_page()

    # ------------------------------------------------------------------
    # Search helpers
    # ------------------------------------------------------------------

    def _prepare_search_results(self, query: str):
        lowered = query.strip().lower()
        if not lowered:
            self._search_cache = []
            self._search_query = ""
            self._search_index = -1
            self.search_status.configure(text="")
            return

        if lowered == self._search_query:
            return

        matches: list[int] = []
        for idx, text in enumerate(self._page_texts):
            try:
                content = text.lower()
            except AttributeError:
                content = str(text).lower()
            if lowered in content:
                matches.append(idx + 1)

        self._search_cache = matches
        self._search_query = lowered
        self._search_index = -1
        total = len(matches)
        status = f"{total} match(es)" if total else "No matches"
        self.search_status.configure(text=status)
        log_debug(
            f"Search '{lowered}' found {total} page(s).",
            func_name="BookViewer._prepare_search_results",
        )

    def _advance_search(self, forward: bool):
        query = self.search_var.get().strip()
        if not query:
            messagebox.showinfo("Book Viewer", "Enter text to search for.")
            return

        self._prepare_search_results(query)
        if not self._search_cache:
            return

        if forward:
            self._search_index = (self._search_index + 1) % len(self._search_cache)
        else:
            self._search_index = (self._search_index - 1) % len(self._search_cache)

        target_page = self._search_cache[self._search_index]
        self.search_status.configure(
            text=f"Match {self._search_index + 1}/{len(self._search_cache)}"
        )
        self.go_to_page(target_page)

    def search_forward(self):
        self._advance_search(True)

    def search_backward(self):
        self._advance_search(False)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_mouse_wheel(self, event):
        if event.state & 0x0004:  # Control key pressed
            delta = 0.25 if event.delta > 0 else -0.25
            self.adjust_zoom(delta)
        else:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _on_shift_mouse_wheel(self, event):
        self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")

    def _on_close(self):
        if self._document is not None:
            try:
                self._document.close()
            except Exception:
                pass
        self.destroy()


def open_book_viewer(master, book_record: dict):
    """Open a new :class:`BookViewer` window for ``book_record``."""

    log_info(
        f"Opening book viewer for '{book_record.get('Title', 'Unknown')}'.",
        func_name="book_viewer.open_book_viewer",
    )
    viewer = BookViewer(master, book_record)
    if viewer.winfo_exists():
        viewer.focus_set()
    return viewer

