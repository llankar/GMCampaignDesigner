"""Ambiance wallpaper importer modal dialog."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from modules.ui.ambiance.importer.models import DuplicateStrategy, ImportCandidate
from modules.ui.ambiance.importer.service import WallpaperImportService
from modules.ui.ambiance.importer.thumbnailer import WallpaperThumbnailer


class AmbianceWallpaperImporterDialog(ctk.CTkToplevel):
    """Modal for importing wallpapers into campaign-local library."""

    def __init__(self, master, *, on_complete=None) -> None:
        super().__init__(master)
        self.title("Import Ambiance Wallpapers")
        self.geometry("980x700")
        self.minsize(860, 580)
        self.transient(master)
        self.grab_set()

        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._service = WallpaperImportService()
        self._thumbnailer = WallpaperThumbnailer(size=(120, 74))
        self._on_complete = on_complete
        self._status_var = tk.StringVar(value="Drop files or click Add files.")
        self._strategy_var = tk.StringVar(value="skip")
        self._entries: list[ImportCandidate] = []

        self._build_header()
        self._build_drop_zone()
        self._build_controls()
        self._build_results_list()

        self.lift()
        self.focus_force()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Import Ambiance Wallpapers",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

    def _build_drop_zone(self) -> None:
        zone = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color="#374151", fg_color="#111827")
        zone.grid(row=1, column=0, sticky="ew", padx=16)
        zone.grid_columnconfigure(0, weight=1)
        self._drop_zone = zone

        ctk.CTkLabel(
            zone,
            text="Drag and drop files here",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, pady=(14, 4), padx=10)
        ctk.CTkLabel(
            zone,
            text="or use Add files to multi-select images/videos",
            text_color="#9CA3AF",
        ).grid(row=1, column=0, pady=(0, 14), padx=10)

        zone.bind("<Button-1>", lambda _event: self._choose_files())
        self._bind_drop_target(zone)

    def _build_controls(self) -> None:
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        controls.grid_columnconfigure(5, weight=1)

        ctk.CTkButton(controls, text="Add files", width=120, command=self._choose_files).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkLabel(controls, text="Duplicates").grid(row=0, column=1, padx=(4, 6))
        ctk.CTkOptionMenu(
            controls,
            variable=self._strategy_var,
            values=["skip", "replace", "keep_both"],
            width=130,
        ).grid(row=0, column=2, padx=(0, 12))

        ctk.CTkButton(controls, text="Import", fg_color="#16A34A", hover_color="#15803D", width=120, command=self._import).grid(
            row=0,
            column=3,
            padx=(0, 8),
        )
        ctk.CTkButton(controls, text="Close", width=90, command=self.destroy).grid(row=0, column=4)

        ctk.CTkLabel(controls, textvariable=self._status_var, anchor="w", text_color="#F59E0B").grid(
            row=1,
            column=0,
            columnspan=6,
            sticky="ew",
            pady=(8, 0),
        )

    def _build_results_list(self) -> None:
        self._list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._list.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 16))

    def _choose_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select ambiance media",
            filetypes=[
                ("Supported media", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.mp4 *.mov *.mkv *.avi *.webm *.m4v"),
                ("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                ("Videos", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"),
                ("All files", "*.*"),
            ],
            parent=self,
        )
        if not paths:
            return
        self._set_candidates(list(paths))

    def _set_candidates(self, paths: list[str]) -> None:
        self._entries = self._service.inspect_candidates(paths)
        self._render_entries()
        self._status_var.set(f"{len(self._entries)} file(s) queued for import.")

    def _import(self) -> None:
        if not self._entries:
            self._status_var.set("No files selected.")
            return

        strategy: DuplicateStrategy = self._strategy_var.get().strip().lower() or "skip"  # type: ignore[assignment]
        result = self._service.import_files([entry.source_path for entry in self._entries], strategy=strategy)
        self._entries = result.entries
        self._render_entries()
        self._show_summary(result.imported_count, result.skipped_count, result.failed_count)
        callback = self._on_complete
        if callable(callback):
            callback(result)

    def _show_summary(self, imported: int, skipped: int, failed: int) -> None:
        self._status_var.set(
            f"Import complete · imported: {imported} · skipped: {skipped} · failed: {failed}"
        )
        self.after(4000, lambda: self._status_var.set(""))

    def _render_entries(self) -> None:
        for child in self._list.winfo_children():
            child.destroy()

        if not self._entries:
            ctk.CTkLabel(self._list, text="No files selected yet.", anchor="w", text_color="#9CA3AF").grid(
                row=0,
                column=0,
                sticky="w",
                padx=4,
                pady=6,
            )
            return

        for idx, entry in enumerate(self._entries):
            row = ctk.CTkFrame(self._list)
            row.grid(row=idx, column=0, sticky="ew", padx=2, pady=4)
            row.grid_columnconfigure(1, weight=1)

            thumb = self._thumbnailer.get(entry.source_path, media_type=entry.media_type)
            ctk.CTkLabel(row, text="", image=thumb, width=128).grid(row=0, column=0, rowspan=2, padx=(6, 8), pady=6)

            dims = f"{entry.width}x{entry.height}" if entry.width and entry.height else "—"
            size_text = _format_size(entry.filesize)
            title = f"{entry.filename} · {dims} · {size_text}"
            ctk.CTkLabel(row, text=title, anchor="w").grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 2))

            status_color = {
                "pending": "#9CA3AF",
                "imported": "#22C55E",
                "skipped": "#EAB308",
                "failed": "#EF4444",
            }.get(entry.status, "#9CA3AF")
            status_text = entry.message or entry.status.title()
            ctk.CTkLabel(row, text=status_text, anchor="w", text_color=status_color).grid(
                row=1,
                column=1,
                sticky="ew",
                padx=(0, 8),
                pady=(0, 8),
            )

    def _bind_drop_target(self, widget) -> None:
        try:
            widget.drop_target_register("DND_Files")
            widget.dnd_bind("<<Drop>>", self._on_drop_event)
        except Exception:
            return

    def _on_drop_event(self, event) -> None:
        data = str(getattr(event, "data", "") or "").strip()
        if not data:
            return
        files = self.tk.splitlist(data)
        self._set_candidates([str(path) for path in files])


def _format_size(size: int) -> str:
    value = float(max(0, int(size)))
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
