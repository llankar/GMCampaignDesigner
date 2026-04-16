"""Handouts page for the GM Table workspace."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from modules.helpers.config_helper import ConfigHelper


class GMTableHandoutsPage(ctk.CTkFrame):
    """Browse and open campaign handout files."""

    def __init__(
        self,
        master,
        *,
        scenario_name: str = "",
        initial_state: dict | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        state = dict(initial_state or {})
        self._scenario_name = str(scenario_name or state.get("scenario_name") or "").strip()
        self._query_var = tk.StringVar(value=str(state.get("query") or ""))
        self._selected_path = str(state.get("selected_path") or "")
        self._handout_paths: list[str] = []
        self._row_buttons: dict[str, ctk.CTkButton] = {}

        title_text = "Handouts"
        if self._scenario_name:
            title_text = f"Handouts · {self._scenario_name}"
        ctk.CTkLabel(
            self,
            text=title_text,
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)

        search = ctk.CTkEntry(controls, textvariable=self._query_var, placeholder_text="Filter handouts…")
        search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        search.bind("<KeyRelease>", lambda _event: self._render_rows())

        ctk.CTkButton(
            controls,
            text="Refresh",
            width=96,
            command=self._refresh_handouts,
        ).grid(row=0, column=1)

        self._list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._list_frame.grid(row=2, column=0, sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

        self._refresh_handouts()

    def _refresh_handouts(self) -> None:
        """Reload files from campaign handout directories."""
        self._handout_paths = self._collect_handout_files()
        self._render_rows()

    def _collect_handout_files(self) -> list[str]:
        """Return available handout files relative to the campaign directory."""
        campaign_dir = Path(ConfigHelper.get_campaign_dir())
        candidate_dirs = (
            campaign_dir / "Handouts",
            campaign_dir / "handouts",
            campaign_dir / "assets" / "handouts",
        )
        discovered: set[str] = set()
        for folder in candidate_dirs:
            if not folder.exists() or not folder.is_dir():
                continue
            for file_path in folder.rglob("*"):
                if file_path.is_file():
                    discovered.add(str(file_path.relative_to(campaign_dir)))
        return sorted(discovered, key=str.lower)

    def _render_rows(self) -> None:
        """Render row buttons based on the active query filter."""
        for child in self._list_frame.winfo_children():
            child.destroy()
        self._row_buttons.clear()

        query = self._query_var.get().strip().lower()
        visible_paths = [
            relative_path
            for relative_path in self._handout_paths
            if not query or query in relative_path.lower()
        ]
        if not visible_paths:
            ctk.CTkLabel(
                self._list_frame,
                text="No handout files found. Add files to Handouts/ or assets/handouts.",
                anchor="w",
                justify="left",
            ).grid(row=0, column=0, sticky="ew", padx=4, pady=4)
            return

        for row_index, relative_path in enumerate(visible_paths):
            button = ctk.CTkButton(
                self._list_frame,
                text=relative_path,
                anchor="w",
                fg_color="transparent",
                hover_color="#283146",
                command=lambda path=relative_path: self._open_handout(path),
            )
            button.grid(row=row_index, column=0, sticky="ew", padx=2, pady=2)
            self._row_buttons[relative_path] = button
        self._highlight_selection()

    def _highlight_selection(self) -> None:
        """Apply a distinct color to the selected row."""
        for relative_path, button in self._row_buttons.items():
            is_selected = relative_path == self._selected_path
            button.configure(
                fg_color="#374151" if is_selected else "transparent",
                text_color="#F4F7FB",
            )

    def _open_handout(self, relative_path: str) -> None:
        """Open a handout in the system default app."""
        resolved = Path(ConfigHelper.get_campaign_dir()) / relative_path
        if not resolved.exists():
            messagebox.showerror("Handouts", f"File not found:\n{relative_path}")
            return
        self._selected_path = relative_path
        self._highlight_selection()
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(resolved))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(resolved)])
            else:
                subprocess.Popen(["xdg-open", str(resolved)])
        except Exception as exc:
            messagebox.showerror("Handouts", f"Unable to open file:\n{exc}")

    def get_state(self) -> dict:
        """Return serializable page state for workspace persistence."""
        return {
            "query": self._query_var.get().strip(),
            "selected_path": self._selected_path,
            "scenario_name": self._scenario_name,
        }
