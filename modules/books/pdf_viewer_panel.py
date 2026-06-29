"""Reusable frame-based PDF viewer for embedded panels and book windows."""
from __future__ import annotations
import threading
import tkinter as tk
from typing import Any
import customtkinter as ctk
from PIL import ImageTk
from modules.books.pdf_processing import get_pdf_page_count, open_document, render_pdf_page_to_image
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_warning


class PDFViewerFrame(ctk.CTkFrame):
    """Non-blocking PDF viewer frame with JSON-safe state."""
    MIN_ZOOM = 0.5
    MAX_ZOOM = 4.0

    def __init__(self, master, *, pdf_path: str = "", attachment_path: str = "", title: str = "PDF Viewer", initial_state: dict[str, Any] | None = None, on_state_changed=None, campaign_dir: str | None = None):
        super().__init__(master)
        state = initial_state or {}
        self.pdf_path = str(pdf_path or attachment_path or state.get("pdf_path") or state.get("attachment_path") or "")
        self.attachment_path = str(attachment_path or self.pdf_path)
        self.title = title or str(state.get("book_title") or "PDF Viewer")
        self.campaign_dir = campaign_dir or ConfigHelper.get_campaign_dir()
        self.current_page = int(state.get("current_page") or 1)
        self.zoom = float(state.get("zoom") or 1.25)
        self.search_query = str(state.get("search_query") or "")
        self._on_state_changed = on_state_changed
        self._render_token = 0
        self._page_image = None
        self._document = None
        self.page_count = 0
        self._build_ui()
        self.open_pdf(self.pdf_path, initial_page=self.current_page, zoom=self.zoom)

    def _build_ui(self) -> None:
        self.grid_rowconfigure(1, weight=1); self.grid_columnconfigure(0, weight=1)
        controls = ctk.CTkFrame(self); controls.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        ctk.CTkButton(controls, text="◀", width=36, command=self.previous_page).pack(side="left", padx=(0,4))
        ctk.CTkButton(controls, text="▶", width=36, command=self.next_page).pack(side="left", padx=(0,8))
        self.page_var = tk.StringVar(value=str(self.current_page))
        entry = ctk.CTkEntry(controls, width=58, textvariable=self.page_var); entry.pack(side="left")
        entry.bind("<Return>", lambda _e: self.go_to_page_from_entry())
        self.page_label = ctk.CTkLabel(controls, text="Page 1"); self.page_label.pack(side="left", padx=8)
        ctk.CTkButton(controls, text="−", width=36, command=lambda: self.adjust_zoom(-0.25)).pack(side="left")
        ctk.CTkButton(controls, text="+", width=36, command=lambda: self.adjust_zoom(0.25)).pack(side="left", padx=(4,0))
        ctk.CTkButton(controls, text="Reset Zoom", width=96, command=self.reset_zoom).pack(side="left", padx=8)
        self.zoom_label = ctk.CTkLabel(controls, text="Zoom: 125%"); self.zoom_label.pack(side="left")
        body = ctk.CTkFrame(self); body.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0,6)); body.grid_rowconfigure(0, weight=1); body.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(body, bg="#0B1020", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ybar = ctk.CTkScrollbar(body, orientation="vertical", command=self.canvas.yview); ybar.grid(row=0, column=1, sticky="ns")
        xbar = ctk.CTkScrollbar(body, orientation="horizontal", command=self.canvas.xview); xbar.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel, add="+")
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel, add="+")
        self.canvas.bind("<Button-4>", lambda _event: self.canvas.yview_scroll(-3, "units"), add="+")
        self.canvas.bind("<Button-5>", lambda _event: self.canvas.yview_scroll(3, "units"), add="+")
        self.loading_label = ctk.CTkLabel(body, text="Loading page...")

    def open_pdf(self, pdf_path: str, *, initial_page: int = 1, zoom: float | None = None) -> None:
        self.pdf_path = str(pdf_path or ""); self.attachment_path = self.pdf_path
        if zoom is not None: self.zoom = self._clamp_zoom(zoom)
        try:
            self._document = open_document(self.pdf_path, campaign_dir=self.campaign_dir) if self.pdf_path else None
            self.page_count = get_pdf_page_count(self.pdf_path, campaign_dir=self.campaign_dir) if self.pdf_path else 0
        except Exception as exc:
            log_warning(f"Unable to open PDF '{self.pdf_path}': {exc}", func_name="PDFViewerFrame.open_pdf")
            self._document = None; self.page_count = 0
        self.go_to_page(initial_page, render=True)

    def _clamp_page(self, page: int) -> int:
        page = max(1, int(page or 1))
        return min(page, self.page_count) if self.page_count else page
    def _clamp_zoom(self, zoom: float) -> float:
        return max(self.MIN_ZOOM, min(self.MAX_ZOOM, float(zoom or 1.25)))
    def _format_page_label(self) -> str:
        return f"Page {self.current_page} / {self.page_count}" if self.page_count else f"Page {self.current_page}"
    def _refresh_labels(self) -> None:
        self.page_var.set(str(self.current_page)); self.page_label.configure(text=self._format_page_label()); self.zoom_label.configure(text=f"Zoom: {int(self.zoom*100)}%")
    def go_to_page_from_entry(self) -> None:
        try: page = int(self.page_var.get())
        except Exception: page = self.current_page
        self.go_to_page(page)
    def go_to_page(self, page: int, *, render: bool = True) -> None:
        self.current_page = self._clamp_page(page); self._refresh_labels()
        if render: self._schedule_render(); self._changed()
    def previous_page(self) -> None: self.go_to_page(self.current_page - 1)
    def next_page(self) -> None: self.go_to_page(self.current_page + 1)
    def adjust_zoom(self, delta: float) -> None:
        self.zoom = self._clamp_zoom(self.zoom + delta); self._refresh_labels(); self._schedule_render(); self._changed()
    def reset_zoom(self) -> None:
        self.zoom = 1.25; self._refresh_labels(); self._schedule_render(); self._changed()
    def _schedule_render(self) -> None:
        self._render_token += 1; token = self._render_token
        self.loading_label.place(relx=0.5, rely=0.5, anchor="center")
        path, page, zoom, doc = self.pdf_path, self.current_page, self.zoom, self._document
        def worker():
            image = None; error = None
            try:
                if path: image = render_pdf_page_to_image(path, page, zoom=zoom, campaign_dir=self.campaign_dir, document=doc)
            except Exception as exc: error = exc
            self.after(0, lambda: self._apply_render(token, image, error))
        threading.Thread(target=worker, daemon=True).start()
    def _apply_render(self, token: int, image, error) -> None:
        if token != self._render_token: return
        self.loading_label.place_forget()
        if error is not None or image is None: return
        self._page_image = ImageTk.PhotoImage(image)
        self.canvas.delete("page"); self.canvas.create_image(0, 0, image=self._page_image, anchor="nw", tags="page")
        self.canvas.configure(scrollregion=(0, 0, image.width, image.height))
    def _on_mousewheel(self, event) -> str:
        direction = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(direction * 3, "units")
        return "break"

    def _on_shift_mousewheel(self, event) -> str:
        direction = -1 if event.delta > 0 else 1
        self.canvas.xview_scroll(direction * 3, "units")
        return "break"

    def _on_ctrl_mousewheel(self, event) -> str:
        self.adjust_zoom(0.1 if event.delta > 0 else -0.1)
        return "break"

    def discard_stale_render_for_test(self, token: int) -> bool:
        return token != self._render_token
    def get_state(self) -> dict[str, Any]:
        return {"pdf_path": self.pdf_path, "attachment_path": self.attachment_path, "book_title": self.title, "current_page": int(self.current_page), "zoom": float(self.zoom), "search_query": self.search_query}
    def _changed(self) -> None:
        if callable(self._on_state_changed): self.after(250, self._on_state_changed)
