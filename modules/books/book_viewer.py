"""Interactive PDF book viewer for campaign assets."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
import fitz
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
        self._search_query_display = ""
        self._search_index = -1
        self._signets: list[dict[str, int | str]] = []
        self._suppress_signet_events = False
        self._highlight_boxes: list[tuple[float, float, float, float]] = []

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
        self._signets = self._collect_signets()

        self._build_ui()
        self._render_current_page()

        self.bind("<MouseWheel>", self._on_mouse_wheel)
        self.bind("<Button-4>", self._on_mouse_wheel)
        self.bind("<Button-5>", self._on_mouse_wheel)
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
        viewer_frame.grid_columnconfigure(0, weight=0)
        viewer_frame.grid_columnconfigure(1, weight=1)

        if self._signets:
            self.signet_panel = ctk.CTkFrame(viewer_frame)
            self.signet_panel.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
            self.signet_panel.grid_rowconfigure(1, weight=1)

            signet_title = ctk.CTkLabel(self.signet_panel, text="Signets", anchor="w")
            signet_title.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))

            self._signet_list_var = tk.StringVar(value=[self._format_signet_label(item) for item in self._signets])
            signet_listbox = tk.Listbox(
                self.signet_panel,
                listvariable=self._signet_list_var,
                exportselection=False,
                activestyle="none",
                background="#1E1E1E",
                foreground="#E0E0E0",
                highlightthickness=0,
                selectbackground="#3A7EBF",
            )
            signet_listbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

            signet_scrollbar = tk.Scrollbar(self.signet_panel, orient="vertical", command=signet_listbox.yview)
            signet_scrollbar.grid(row=1, column=1, sticky="ns", pady=5)
            signet_listbox.configure(yscrollcommand=signet_scrollbar.set)

            signet_listbox.bind("<<ListboxSelect>>", self._on_signet_select)
            signet_listbox.bind("<Double-Button-1>", self._on_signet_activate)
            signet_listbox.bind("<Return>", self._on_signet_activate)
            self._signet_listbox = signet_listbox
        else:
            self.signet_panel = None
            self._signet_list_var = None
            self._signet_listbox = None

        self.canvas = tk.Canvas(viewer_frame, background="#1E1E1E", highlightthickness=0)
        self.canvas.grid(row=0, column=1, sticky="nsew")

        self.v_scroll = ctk.CTkScrollbar(viewer_frame, orientation="vertical", command=self.canvas.yview)
        self.v_scroll.grid(row=0, column=2, sticky="ns")
        self.h_scroll = ctk.CTkScrollbar(viewer_frame, orientation="horizontal", command=self.canvas.xview)
        self.h_scroll.grid(row=1, column=1, sticky="ew")

        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        self.canvas.bind("<Configure>", lambda _e: self._center_image())

        self._highlight_current_signet()

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

    def _collect_signets(self) -> list[dict[str, int | str]]:
        signets: list[dict[str, int | str]] = []
        if not self._document:
            return signets

        try:
            toc = self._document.get_toc(simple=True) or []
        except Exception as exc:  # pragma: no cover - defensive catch
            log_warning(
                f"Failed to collect signets: {exc}",
                func_name="BookViewer._collect_signets",
            )
            return signets

        for entry in toc:
            if not isinstance(entry, (list, tuple)) or len(entry) < 3:
                continue
            level, title, page = entry[:3]
            try:
                page_number = int(page)
            except (TypeError, ValueError):
                continue
            if page_number < 1:
                continue
            try:
                level_value = int(level)
            except (TypeError, ValueError):
                level_value = 1

            label = str(title or "").strip() or f"Page {page_number}"
            signets.append({"title": label, "page": page_number, "level": max(level_value, 1)})

        if signets:
            log_debug(
                f"Collected {len(signets)} signet(s) from PDF.",
                func_name="BookViewer._collect_signets",
            )
        return signets

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
        self._refresh_search_highlight()
        self._highlight_current_signet()
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
        self._draw_highlight_overlays()

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
        stripped = query.strip()
        lowered = stripped.lower()
        if not lowered:
            self._search_cache = []
            self._search_query = ""
            self._search_query_display = ""
            self._search_index = -1
            self.search_status.configure(text="")
            self._refresh_search_highlight()
            return

        if lowered == self._search_query and stripped == self._search_query_display:
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
        self._search_query_display = stripped
        self._search_index = -1
        total = len(matches)
        status = f"{total} match(es)" if total else "No matches"
        self.search_status.configure(text=status)
        self._refresh_search_highlight()
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
        previous_page = self.current_page
        self.go_to_page(target_page)
        if target_page == previous_page:
            self._refresh_search_highlight()

    def search_forward(self):
        self._advance_search(True)

    def search_backward(self):
        self._advance_search(False)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _format_signet_label(self, signet: dict[str, int | str]) -> str:
        indent = "    " * (max(int(signet.get("level", 1)) - 1, 0))
        title = str(signet.get("title", "")).strip()
        page = signet.get("page", "")
        page_display = f" (p. {page})" if page else ""
        return f"{indent}{title}{page_display}".rstrip()

    def _highlight_current_signet(self):
        if not self._signets or not self._signet_listbox:
            return

        target_index = None
        for idx, signet in enumerate(self._signets):
            if signet.get("page") == self.current_page:
                target_index = idx
                break

        if not self._signet_listbox or not int(self._signet_listbox.winfo_exists()):
            return

        self._suppress_signet_events = True
        try:
            self._signet_listbox.selection_clear(0, "end")
            if target_index is not None:
                self._signet_listbox.selection_set(target_index)
                self._signet_listbox.see(target_index)
        finally:
            self._suppress_signet_events = False

    def _activate_selected_signet(self):
        if (
            not self._signets
            or not self._signet_listbox
            or not int(self._signet_listbox.winfo_exists())
        ):
            return

        selection = self._signet_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        try:
            signet = self._signets[index]
        except IndexError:
            return
        page = signet.get("page")
        if isinstance(page, int):
            self.go_to_page(page)

    def _on_signet_select(self, _event):
        if self._suppress_signet_events:
            return
        self._activate_selected_signet()

    def _on_signet_activate(self, _event=None):
        if self._suppress_signet_events:
            return
        self._activate_selected_signet()

    def _on_mouse_wheel(self, event):
        ctrl_mask = 0x0004
        num = getattr(event, "num", 0)
        delta = event.delta

        if event.state & ctrl_mask:
            if delta > 0 or num == 4:
                self.adjust_zoom(0.25)
            elif delta < 0 or num == 5:
                self.adjust_zoom(-0.25)
            return

        if delta > 0 or num == 4:
            self.go_to_page(self.current_page - 1)
        elif delta < 0 or num == 5:
            self.go_to_page(self.current_page + 1)

    def _on_shift_mouse_wheel(self, event):
        self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")

    def _on_close(self):
        if self._document is not None:
            try:
                self._document.close()
            except Exception:
                pass

    def _refresh_search_highlight(self):
        self._prepare_highlight_boxes_for_current_page()
        self._draw_highlight_overlays()

    def _prepare_highlight_boxes_for_current_page(self):
        self._highlight_boxes = []
        if not self._document:
            return

        if not self._search_query_display:
            return

        if self._search_cache and self.current_page not in self._search_cache:
            return

        try:
            page = self._document.load_page(self.current_page - 1)
        except Exception as exc:  # pragma: no cover - defensive catch
            log_warning(
                f"Failed to prepare highlights for page {self.current_page}: {exc}",
                func_name="BookViewer._prepare_highlight_boxes_for_current_page",
            )
            return

        flags = 0
        for attr in ("TEXT_DEHYPHENATE", "TEXT_IGNORECASE"):
            flags |= getattr(fitz, attr, 0)

        try:
            results = page.search_for(self._search_query_display, flags=flags)
        except TypeError:
            results = page.search_for(self._search_query_display)
        except Exception as exc:  # pragma: no cover - defensive catch
            log_warning(
                f"Failed to locate search results on page {self.current_page}: {exc}",
                func_name="BookViewer._prepare_highlight_boxes_for_current_page",
            )
            return

        zoom = self.zoom
        self._highlight_boxes = [
            (rect.x0 * zoom, rect.y0 * zoom, rect.x1 * zoom, rect.y1 * zoom)
            for rect in results
        ]

    def _draw_highlight_overlays(self):
        self.canvas.delete("highlight")
        if not self._highlight_boxes:
            return

        coords = self.canvas.coords("page")
        if not coords:
            return

        x_offset, y_offset = coords[0], coords[1]
        for left, top, right, bottom in self._highlight_boxes:
            self.canvas.create_rectangle(
                x_offset + left,
                y_offset + top,
                x_offset + right,
                y_offset + bottom,
                outline="#FFD54F",
                width=2,
                fill="#FFD54F",
                stipple="gray50",
                tags=("highlight",),
            )
        self.canvas.tag_raise("highlight", "page")


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

