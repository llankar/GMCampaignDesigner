"""Dialog to import one or more filesystem directories into image assets."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from modules.image_assets import ImageAssetsService
from modules.image_assets.services.import_service import ImageAssetsImportSummary
from modules.ui.image_library.dialogs.import_directories import (
    RecentImportRootsStore,
    merge_roots,
    validate_roots,
)


class ImageDirectoryImportDialog(ctk.CTkToplevel):
    """Collect import options and launch image directory import."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        service: ImageAssetsService | None = None,
        recent_roots_store: RecentImportRootsStore | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Import Image Directories")
        self.geometry("680x440")
        self.minsize(580, 360)
        self.transient(master)

        self._service = service or ImageAssetsService()
        self._recent_roots_store = recent_roots_store or RecentImportRootsStore()
        self._roots: list[str] = self._recent_roots_store.load()

        self.recursive_var = ctk.BooleanVar(value=True)
        self.reindex_changed_var = ctk.BooleanVar(value=True)

        self._build_ui()
        self._refresh_roots()
        self._enable_drag_and_drop_if_available()

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
        ctk.CTkButton(side, text="Bulk add...", command=self._bulk_add_directories).pack(fill="x", pady=6)
        ctk.CTkButton(side, text="Import ZIP...", command=self._import_bundle_zip).pack(fill="x", pady=6)
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
        self._append_roots([selected])

    def _bulk_add_directories(self) -> None:
        """Repeatedly prompt the user to add multiple directories in one flow."""
        selected_roots: list[str] = []
        while True:
            selected = filedialog.askdirectory(parent=self, title="Select image directory")
            if not selected:
                break
            selected_roots.append(selected)
            continue_adding = messagebox.askyesno(
                "Bulk add directories",
                "Add another directory?",
                parent=self,
            )
            if not continue_adding:
                break

        self._append_roots(selected_roots)

    def _import_bundle_zip(self) -> None:
        """Import a GitHub-style image-library bundle zip into the shared library."""
        zip_path = filedialog.askopenfilename(
            parent=self,
            title="Import GitHub Image Library ZIP",
            filetypes=[("Zip Files", "*.zip"), ("All Files", "*.*")],
        )
        if not zip_path:
            return

        analysis = self._service.analyze_image_library_bundle(zip_path)
        if not analysis.has_image_assets:
            messagebox.showinfo(
                "No Image Library Assets",
                "This archive does not contain any image library assets.",
                parent=self,
            )
            return

        overwrite = True
        if analysis.duplicate_names:
            response = messagebox.askyesnocancel(
                "Overwrite Existing Image Library Entries?",
                "Some image assets already exist in the active campaign.\n\n"
                f"Image assets: {len(analysis.duplicate_names)}\n\n"
                "Yes = overwrite duplicates\n"
                "No = keep existing and skip duplicates\n"
                "Cancel = abort import",
                parent=self,
            )
            if response is None:
                return
            overwrite = bool(response)

        summary = self._service.import_image_library_bundle(zip_path, overwrite=overwrite)
        messagebox.showinfo(
            "ZIP Import Complete",
            (
                "Image library ZIP import completed.\n\n"
                f"Imported: {summary.imported}\n"
                f"Updated: {summary.updated}\n"
                f"Skipped: {summary.skipped}"
            ),
            parent=self,
        )

    def _append_roots(self, candidates: list[str]) -> None:
        """Append incoming root candidates after normalization and dedupe."""
        before_count = len(self._roots)
        merged = merge_roots(self._roots, candidates)
        self._roots = merged
        if len(self._roots) != before_count:
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
        validation = validate_roots(self._roots)
        existing_roots = validation.existing_roots
        if not existing_roots:
            messagebox.showwarning("No directory", "Add at least one valid directory to import.", parent=self)
            return

        if validation.missing_roots:
            should_continue = messagebox.askyesno(
                "Missing directories",
                "Some selected directories no longer exist and will be skipped. Continue import?",
                parent=self,
            )
            if not should_continue:
                return

        summary = self._service.import_directories(
            paths=existing_roots,
            recursive=bool(self.recursive_var.get()),
            reindex_changed_only=bool(self.reindex_changed_var.get()),
        )
        self._recent_roots_store.save(existing_roots)
        messagebox.showinfo("Import complete", self._format_summary(summary), parent=self)

    def _enable_drag_and_drop_if_available(self) -> None:
        """Enable folder drag-and-drop when supported by the current Tk stack."""
        target_register = getattr(self.roots_list, "drop_target_register", None)
        dnd_bind = getattr(self.roots_list, "dnd_bind", None)
        if not callable(target_register) or not callable(dnd_bind):
            return
        try:
            target_register("DND_Files")
            dnd_bind("<<Drop>>", self._on_drop_files)
        except Exception:
            return

    def _on_drop_files(self, event: object) -> str:
        """Handle dropped file paths and add only directory roots."""
        raw_data = str(getattr(event, "data", "") or "")
        if not raw_data:
            return "break"

        try:
            candidates = [str(value).strip("{}") for value in self.tk.splitlist(raw_data)]
        except tk.TclError:
            candidates = [raw_data.strip("{}")]

        valid_dirs: list[str] = []
        for candidate in candidates:
            if not candidate:
                continue
            normalized = candidate.strip()
            if not normalized:
                continue
            try:
                if os.path.isdir(normalized):
                    valid_dirs.append(normalized)
            except Exception:
                continue

        self._append_roots(valid_dirs)
        return "break"

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
