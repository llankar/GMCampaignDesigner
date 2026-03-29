from __future__ import annotations

import customtkinter as ctk

from modules.generic.editor.styles import EDITOR_PALETTE, primary_button_style, toolbar_entry_style
from modules.helpers.window_helper import position_window_at_top


class ScenarioPickerDialog(ctk.CTkToplevel):
    """Simple searchable picker used to choose one scenario title."""

    def __init__(self, master, scenarios: list[str]):
        super().__init__(master)
        self.title("Choose Scenario")
        self.geometry("520x460")
        self.configure(fg_color=EDITOR_PALETTE["surface"])
        self.resizable(True, True)

        self._all_scenarios = [str(item).strip() for item in (scenarios or []) if str(item).strip()]
        self._filtered_scenarios: list[str] = []
        self.selected_scenario: str | None = None

        self.search_var = ctk.StringVar(value="")
        self._build_ui()
        self._refresh_list()

        self.transient(master)
        self.grab_set()
        self.focus_force()
        position_window_at_top(self)

    def _build_ui(self) -> None:
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=12, pady=12)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            root,
            text="Select a scenario to link",
            font=("Arial", 16, "bold"),
            text_color=EDITOR_PALETTE["text"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.search_entry = ctk.CTkEntry(
            root,
            textvariable=self.search_var,
            placeholder_text="Search scenarios…",
            **toolbar_entry_style(),
        )
        self.search_entry.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.search_entry.bind("<KeyRelease>", lambda _event: self._refresh_list())
        self.search_entry.bind("<Return>", lambda _event: self._confirm_selection())

        list_frame = ctk.CTkFrame(
            root,
            fg_color=EDITOR_PALETTE["surface_soft"],
            corner_radius=10,
            border_width=1,
            border_color=EDITOR_PALETTE["border"],
        )
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        self.list_widget = ctk.CTkScrollableFrame(list_frame, fg_color="transparent")
        self.list_widget.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.list_widget.grid_columnconfigure(0, weight=1)

        button_row = ctk.CTkFrame(root, fg_color="transparent")
        button_row.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        button_row.grid_columnconfigure(0, weight=1)

        self.info_label = ctk.CTkLabel(button_row, text="", text_color=EDITOR_PALETTE["muted_text"], anchor="w")
        self.info_label.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            button_row,
            text="Cancel",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
            border_color=EDITOR_PALETTE["border"],
        ).grid(row=0, column=1, padx=(8, 0))
        self.add_button = ctk.CTkButton(button_row, text="Add", command=self._confirm_selection, **primary_button_style())
        self.add_button.grid(row=0, column=2, padx=(8, 0))

    def _refresh_list(self) -> None:
        for child in self.list_widget.winfo_children():
            child.destroy()

        query = self.search_var.get().strip().lower()
        self._filtered_scenarios = [name for name in self._all_scenarios if not query or query in name.lower()]
        if not self._filtered_scenarios:
            ctk.CTkLabel(
                self.list_widget,
                text="No scenario matches your search.",
                text_color=EDITOR_PALETTE["muted_text"],
            ).grid(row=0, column=0, sticky="w", padx=6, pady=8)
            self.info_label.configure(text="0 scenario")
            self.add_button.configure(state="disabled")
            return

        self.info_label.configure(text=f"{len(self._filtered_scenarios)} scenario(s)")
        self.add_button.configure(state="disabled")
        for row_index, scenario in enumerate(self._filtered_scenarios):
            button = ctk.CTkButton(
                self.list_widget,
                text=scenario,
                anchor="w",
                fg_color=EDITOR_PALETTE["surface"],
                hover_color=EDITOR_PALETTE["surface_soft"],
                text_color=EDITOR_PALETTE["text"],
                command=lambda title=scenario: self._select(title),
            )
            button.grid(row=row_index, column=0, sticky="ew", padx=4, pady=3)

    def _select(self, scenario: str) -> None:
        self.selected_scenario = scenario
        self.add_button.configure(state="normal")

    def _confirm_selection(self) -> None:
        if not self.selected_scenario:
            return
        self.destroy()


def choose_scenario(master, scenarios: list[str]) -> str | None:
    dialog = ScenarioPickerDialog(master, scenarios)
    dialog.wait_window()
    return dialog.selected_scenario
