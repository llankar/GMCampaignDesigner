"""Dialog to import one or more filesystem directories into image assets."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from modules.image_assets import ImageAssetsService
from modules.image_assets.services.import_service import ImageAssetsImportSummary


class ImageDirectoryImportDialog(ctk.CTkToplevel):
    """Collect import options and launch image directory import."""

    def __init__(self, master: tk.Misc | None = None, *, service: ImageAssetsService | None = None) -> None:
        super().__init__(master)
        self.title("Import Image Directories")
        self.geometry("680x440")
        self.minsize(580, 360)
        self.transient(master)

        self._service = service or ImageAssetsService()
        self._roots: list[str] = []

        self.recursive_var = ctk.BooleanVar(value=True)
        self.reindex_changed_var = ctk.BooleanVar(value=True)

        self._build_ui()
        self._refresh_roots()

        self.bind("<Escape>", lambda _event: self.destroy())
        self.lift()
        self.focus_force()

    def _build_ui(self) -> None:
        """Build UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="Source directories", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(
            top,
            text="Choose one or more folders to index images into the shared library.",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        list_frame = ctk.CTkFrame(self)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        self.roots_list = tk.Listbox(list_frame, selectmode=tk.MULTIPLE)
        self.roots_list.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)

        side = ctk.CTkFrame(list_frame)
        side.grid(row=0, column=1, sticky="ns", padx=8, pady=8)

        ctk.CTkButton(side, text="Add directory...", command=self._add_directory).pack(fill="x", pady=(0, 6))
        ctk.CTkButton(side, text="Remove selected", command=self._remove_selected).pack(fill="x", pady=6)
        ctk.CTkButton(side, text="Clear", command=self._clear).pack(fill="x", pady=6)

        options = ctk.CTkFrame(self)
        options.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        ctk.CTkCheckBox(options, text="Scan subdirectories recursively", variable=self.recursive_var).pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        ctk.CTkCheckBox(
            options,
            text="Skip unchanged files (faster incremental import)",
            variable=self.reindex_changed_var,
        ).pack(anchor="w", padx=8, pady=(0, 8))

        actions = ctk.CTkFrame(self)
        actions.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        actions.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(actions, text="Cancel", command=self.destroy).grid(row=0, column=1, padx=(8, 4), pady=8)
        ctk.CTkButton(actions, text="Import", command=self._run_import).grid(row=0, column=2, padx=(4, 8), pady=8)

    def _add_directory(self) -> None:
        """Prompt and append one directory."""
        selected = filedialog.askdirectory(parent=self, title="Select image directory")
        if not selected:
            return
        candidate = str(selected).strip()
        if not candidate or candidate in self._roots:
            return
        self._roots.append(candidate)
        self._refresh_roots()

    def _remove_selected(self) -> None:
        """Remove selected rows from source list."""
        selection = list(self.roots_list.curselection())
        if not selection:
            return
        selected_indexes = set(selection)
        self._roots = [value for idx, value in enumerate(self._roots) if idx not in selected_indexes]
        self._refresh_roots()

    def _clear(self) -> None:
        """Clear all selected roots."""
        self._roots.clear()
        self._refresh_roots()

    def _refresh_roots(self) -> None:
        """Refresh listbox from local roots list."""
        self.roots_list.delete(0, tk.END)
        for root in self._roots:
            self.roots_list.insert(tk.END, root)

    def _run_import(self) -> None:
        """Execute import and report concise result."""
        if not self._roots:
            messagebox.showwarning("No directory", "Add at least one directory to import.", parent=self)
            return

        summary = self._service.import_directories(
            paths=list(self._roots),
            recursive=bool(self.recursive_var.get()),
            reindex_changed_only=bool(self.reindex_changed_var.get()),
        )
        messagebox.showinfo("Import complete", self._format_summary(summary), parent=self)

    @staticmethod
    def _format_summary(summary: ImageAssetsImportSummary) -> str:
        """Format import summary for messagebox."""
        lines = [
            f"Roots: {summary.roots_total}",
            f"Scanned files: {summary.scanned_files}",
            f"Imported new: {summary.imported_new}",
            f"Updated: {summary.updated}",
            f"Skipped unchanged: {summary.skipped_unchanged}",
            f"Skipped duplicates: {summary.skipped_duplicate}",
        ]
        if summary.roots_missing:
            lines.append(f"Missing roots: {len(summary.roots_missing)}")
        if summary.errors:
            lines.append(f"Errors: {len(summary.errors)}")
        return "\n".join(lines)
