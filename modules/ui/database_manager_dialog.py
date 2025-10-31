"""Modal dialog for selecting or creating campaign database files."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable, Iterable

import customtkinter as ctk

from modules.helpers.logging_helper import log_exception, log_module_import

log_module_import(__name__)

DatabaseSelectedCallback = Callable[[str, bool], None]


class DatabaseManagerDialog(ctk.CTkToplevel):
    """Allow the user to select, create, or browse for a campaign database."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        current_path: str | None = None,
        on_selected: DatabaseSelectedCallback | None = None,
        on_cancelled: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Manage Campaign Database")
        self.geometry("560x520")
        self.resizable(False, False)

        self._on_selected = on_selected
        self._on_cancelled = on_cancelled
        self._current_path = (Path(current_path).expanduser().resolve() if current_path else None)
        self._selection_var = tk.StringVar()
        self._selection_var.trace_add("write", lambda *_: self._update_confirm_state())
        self._error_var = tk.StringVar(value="")
        self._new_name_var = tk.StringVar()
        self._option_flags: dict[str, bool] = {}

        self._campaigns_dir = self._determine_campaigns_directory()
        self._campaigns_dir.mkdir(parents=True, exist_ok=True)

        self._list_container: ctk.CTkScrollableFrame | None = None
        self._confirm_button: ctk.CTkButton | None = None
        self._error_label: ctk.CTkLabel | None = None

        self._build_ui()
        self._load_existing_databases()

        if self._current_path is not None and str(self._current_path) in self._option_flags:
            self._selection_var.set(str(self._current_path))
        else:
            self._update_confirm_state()

        self.transient(master)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = ctk.CTkFrame(self)
        root.pack(fill="both", expand=True, padx=18, pady=18)
        root.grid_columnconfigure(0, weight=1)

        current = ctk.CTkFrame(root, fg_color="transparent")
        current.grid(row=0, column=0, sticky="ew")
        current.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(current, text="Current database:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ctk.CTkLabel(
            current,
            text=str(self._current_path) if self._current_path else "(not configured)",
            wraplength=360,
            justify="left",
        ).grid(row=0, column=1, sticky="w")

        list_frame = ctk.CTkFrame(root)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(16, 12))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            list_frame,
            text="Campaign databases detected in the Campaigns directory:",
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        container = ctk.CTkScrollableFrame(list_frame, height=220)
        container.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        container.grid_columnconfigure(0, weight=1)
        self._list_container = container

        create_frame = ctk.CTkFrame(root, fg_color="transparent")
        create_frame.grid(row=2, column=0, sticky="ew")
        create_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(create_frame, text="New campaign name:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        entry = ctk.CTkEntry(create_frame, textvariable=self._new_name_var)
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind("<Return>", lambda _event: self._create_new_campaign())

        create_btn = ctk.CTkButton(create_frame, text="Create", width=100, command=self._create_new_campaign)
        create_btn.grid(row=0, column=2, padx=(8, 0))

        browse_frame = ctk.CTkFrame(root, fg_color="transparent")
        browse_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ctk.CTkButton(
            browse_frame,
            text="Browse for External Database…",
            command=self._browse_for_database,
        ).pack(anchor="w")

        error_label = ctk.CTkLabel(root, textvariable=self._error_var, text_color="#ff6666", justify="left")
        error_label.grid(row=4, column=0, sticky="w", pady=(12, 0))
        self._error_label = error_label

        buttons = ctk.CTkFrame(root, fg_color="transparent")
        buttons.grid(row=5, column=0, sticky="e", pady=(18, 0))

        cancel = ctk.CTkButton(buttons, text="Cancel", width=110, command=self._cancel)
        cancel.pack(side="right", padx=(8, 0))

        confirm = ctk.CTkButton(buttons, text="Use Selected", width=150, command=self._confirm_selection)
        confirm.pack(side="right")
        self._confirm_button = confirm

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _determine_campaigns_directory() -> Path:
        try:
            if getattr(sys, "frozen", False):
                base = Path(sys.executable).resolve().parent
            else:
                base = Path(__file__).resolve().parent.parent.parent
        except Exception:
            base = Path.cwd()
        return base / "Campaigns"

    @staticmethod
    def _sanitize_name(name: str) -> str:
        safe = "".join(ch for ch in name.strip() if ch.isalnum() or ch in {"_", "-", " "})
        safe = safe.strip().replace(" ", "_")
        return safe

    def _load_existing_databases(self) -> None:
        self._option_flags.clear()
        for path in self._discover_databases():
            self._option_flags[str(path)] = False
        self._render_database_options()

    def _discover_databases(self) -> Iterable[Path]:
        candidates: list[Path] = []
        try:
            for root, _dirs, files in os.walk(self._campaigns_dir):
                for filename in files:
                    if filename.lower().endswith(".db"):
                        candidates.append(Path(root) / filename)
        except Exception as exc:
            log_exception(
                f"Failed to scan Campaigns directory for databases: {exc}",
                func_name="DatabaseManagerDialog._discover_databases",
            )
        return sorted({path.resolve() for path in candidates})

    def _render_database_options(self) -> None:
        container = self._list_container
        if container is None:
            return
        for child in container.winfo_children():
            child.destroy()

        if not self._option_flags:
            ctk.CTkLabel(
                container,
                text="No campaign databases were found. Create a new campaign to get started.",
                wraplength=360,
                justify="left",
            ).grid(row=0, column=0, sticky="w")
            return

        for index, path in enumerate(sorted(self._option_flags.keys(), key=lambda p: p.lower())):
            row = ctk.CTkFrame(container, fg_color="transparent")
            row.grid(row=index, column=0, sticky="ew", pady=4)
            row.grid_columnconfigure(0, weight=1)

            display = self._format_display_text(Path(path))
            radio = ctk.CTkRadioButton(row, text=display, value=path, variable=self._selection_var)
            radio.grid(row=0, column=0, sticky="w")

    def _format_display_text(self, path: Path) -> str:
        try:
            relative = path.resolve().relative_to(self._campaigns_dir.resolve())
            return str(relative)
        except ValueError:
            return str(path)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _create_new_campaign(self) -> None:
        name = self._new_name_var.get().strip()
        safe = self._sanitize_name(name)
        if not safe:
            self._set_error("Enter a campaign name using letters, numbers, spaces, '_' or '-'.")
            return

        target_dir = self._campaigns_dir / safe
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self._set_error(f"Unable to create campaign folder: {exc}")
            return

        new_db_path = target_dir / f"{safe}.db"
        if new_db_path.exists():
            self._set_error("A database with this name already exists.")
            return

        self._option_flags[str(new_db_path.resolve())] = True
        self._render_database_options()
        self._selection_var.set(str(new_db_path.resolve()))
        self._new_name_var.set("")
        self._set_error("")

    def _browse_for_database(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Campaign Database",
            initialdir=str(self._campaigns_dir),
            filetypes=[("SQLite Databases", "*.db"), ("All Files", "*.*")],
        )
        if not path:
            return
        resolved = str(Path(path).expanduser().resolve())
        self._option_flags[resolved] = not Path(resolved).exists()
        self._render_database_options()
        self._selection_var.set(resolved)
        self._set_error("")

    def _confirm_selection(self) -> None:
        value = self._selection_var.get().strip()
        if not value:
            self._set_error("Select or create a campaign database before continuing.")
            return
        is_new = self._option_flags.get(value, False) or not Path(value).exists()
        if self._on_selected is not None:
            self._on_selected(value, is_new)
        self.destroy()

    def _cancel(self) -> None:
        if self._on_cancelled is not None:
            self._on_cancelled()
        self.destroy()

    def _set_error(self, message: str) -> None:
        self._error_var.set(message)
        if self._error_label is not None:
            self._error_label.configure(text_color="#ff6666" if message else "#a0a0a0")
        self._update_confirm_state()

    def _update_confirm_state(self) -> None:
        if self._confirm_button is None:
            return
        state = "normal" if self._selection_var.get().strip() else "disabled"
        self._confirm_button.configure(state=state)
