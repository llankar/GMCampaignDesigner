import customtkinter as ctk
from tkinter import messagebox
from typing import Iterable, List


class PDFReviewDialog(ctk.CTkToplevel):
    """Modal dialog that previews extracted PDF text and allows range trimming."""

    def __init__(self, master, pages: List[str], title: str = "Review PDF Text"):
        super().__init__(master)
        self.title(title)
        self.geometry("720x640")
        self.transient(master)
        self.grab_set()

        self._pages = pages
        self.selected_pages: list[str] | None = None

        info_text = (
            f"{len(pages)} page(s) extracted. Use ranges to keep only the pages with content "
            "(e.g., 3-10 or 2-4,7-12). This is handy for removing front/back matter like credits or ads."
        )

        ctk.CTkLabel(self, text=info_text, wraplength=680, justify="left").pack(
            fill="x", padx=14, pady=(12, 6)
        )

        range_row = ctk.CTkFrame(self)
        range_row.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(range_row, text="Page ranges to import:").pack(side="left", padx=(0, 8))
        self.range_entry = ctk.CTkEntry(range_row)
        self.range_entry.insert(0, f"1-{len(pages)}")
        self.range_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(range_row, text="Apply", command=self._apply_ranges).pack(side="left", padx=(8, 0))

        self.preview = ctk.CTkTextbox(self, wrap="word")
        self.preview.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        button_row = ctk.CTkFrame(self)
        button_row.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkButton(button_row, text="Cancel", command=self._cancel).pack(side="right", padx=(6, 0))
        ctk.CTkButton(button_row, text="Import Selection", command=self._confirm).pack(side="right")

        self._apply_ranges()

    def _cancel(self):
        self.selected_pages = None
        self.destroy()

    def _confirm(self):
        if self.selected_pages is None:
            messagebox.showwarning("No Pages", "Please apply a valid page range before importing.")
            return
        self.destroy()

    def _apply_ranges(self):
        raw = self.range_entry.get().strip()
        try:
            indices = _parse_page_ranges(raw, len(self._pages))
        except ValueError as exc:
            messagebox.showerror("Invalid Range", str(exc))
            return
        if not indices:
            messagebox.showwarning("No Pages", "No pages selected; please adjust the range.")
            return
        self.selected_pages = [self._pages[i] for i in indices]
        self._refresh_preview(indices)

    def _refresh_preview(self, indices: Iterable[int]):
        self.preview.delete("1.0", "end")
        parts = []
        for idx in indices:
            page_num = idx + 1
            parts.append(f"--- Page {page_num} ---\n")
            parts.append(self._pages[idx].strip() + "\n\n")
        self.preview.insert("1.0", "".join(parts))
        self.preview.yview_moveto(0)


def _parse_page_ranges(value: str, total_pages: int) -> list[int]:
    if not value:
        return list(range(total_pages))
    indices = set()
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_str, end_str = chunk.split("-", 1)
            try:
                start = int(start_str)
                end = int(end_str)
            except ValueError:
                raise ValueError(f"Invalid page range: '{chunk}'")
            if start < 1 or end < 1 or start > total_pages or end > total_pages:
                raise ValueError("Page ranges must be within the document length.")
            if start > end:
                start, end = end, start
            indices.update(range(start - 1, end))
        else:
            try:
                page = int(chunk)
            except ValueError:
                raise ValueError(f"Invalid page number: '{chunk}'")
            if page < 1 or page > total_pages:
                raise ValueError("Page numbers must be within the document length.")
            indices.add(page - 1)
    return sorted(indices)
