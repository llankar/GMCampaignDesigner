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
        texts: list[str] = []
        pages = self.book_record.get("ExtractedPages")
        if isinstance(pages, list):
            for entry in pages:
                if isinstance(entry, str):
                    texts.append(entry)
                elif isinstance(entry, dict):
                    if "Text" in entry:
                        texts.append(str(entry.get("Text", "")))
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

