"""Multi-select widget for assigning scenarios inside campaign UI flows."""
from __future__ import annotations

import customtkinter as ctk

from modules.campaigns.ui.theme import ARC_EDITOR_PALETTE


class ScenarioMultiSelector(ctk.CTkFrame):
    """Searchable multi-select control with quick actions and visible selected chips."""

    def __init__(self, master, scenarios: list[str], *, label: str = "Scenarios"):
        """Initialize the ScenarioMultiSelector instance."""
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        self._all_scenarios = list(scenarios or [])
        self._selected_scenarios: set[str] = set()
        self._scenario_vars: dict[str, ctk.StringVar] = {}
        self._scenario_checks: list[tuple[str, ctk.CTkCheckBox]] = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=label,
            anchor="w",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=ARC_EDITOR_PALETTE.text_primary,
        ).grid(row=0, column=0, sticky="w")

        self.selection_count_label = ctk.CTkLabel(
            header,
            text="0 selected",
            anchor="e",
            text_color=ARC_EDITOR_PALETTE.text_secondary,
        )
        self.selection_count_label.grid(row=0, column=1, sticky="e")

        self.search_var = ctk.StringVar(value="")
        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        search_row.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            search_row,
            textvariable=self.search_var,
            placeholder_text="Search by scenario title, location, or hook...",
            height=38,
            corner_radius=14,
            fg_color=ARC_EDITOR_PALETTE.surface_alt,
            border_color=ARC_EDITOR_PALETTE.border,
            text_color=ARC_EDITOR_PALETTE.text_primary,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.search_entry.bind("<KeyRelease>", self._on_search)

        ctk.CTkButton(
            search_row,
            text="Select visible",
            width=118,
            fg_color=ARC_EDITOR_PALETTE.accent_soft,
            hover_color=ARC_EDITOR_PALETTE.chip_border,
            command=self._select_visible,
        ).grid(row=0, column=1, padx=(0, 6))

        ctk.CTkButton(
            search_row,
            text="Clear",
            width=86,
            fg_color=ARC_EDITOR_PALETTE.danger,
            hover_color=ARC_EDITOR_PALETTE.danger_hover,
            command=self._clear_selection,
        ).grid(row=0, column=2)

        self.selected_chips = ctk.CTkFrame(
            self,
            fg_color=ARC_EDITOR_PALETTE.surface_alt,
            corner_radius=16,
            border_width=1,
            border_color=ARC_EDITOR_PALETTE.border,
        )
        self.selected_chips.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.selected_chips.grid_columnconfigure(0, weight=1)

        self.selected_summary_label = ctk.CTkLabel(
            self.selected_chips,
            text="No scenarios linked yet. Pick the chapters that move this arc forward.",
            anchor="w",
            justify="left",
            wraplength=620,
            text_color=ARC_EDITOR_PALETTE.text_secondary,
        )
        self.selected_summary_label.grid(row=0, column=0, sticky="ew", padx=14, pady=12)

        self.results_scroll = ctk.CTkScrollableFrame(
            self,
            height=280,
            fg_color=ARC_EDITOR_PALETTE.surface_alt,
            corner_radius=16,
            border_width=1,
            border_color=ARC_EDITOR_PALETTE.border,
        )
        self.results_scroll.grid(row=3, column=0, sticky="ew")
        self.results_scroll.grid_columnconfigure(0, weight=1)

        self.empty_results_label = ctk.CTkLabel(
            self,
            text="No scenarios match this filter.",
            text_color=ARC_EDITOR_PALETTE.text_secondary,
            anchor="w",
        )

        self._build_scenario_list()
        self._filter_visible_scenarios()
        self._refresh_selected_summary()

    def set_values(self, values: list[str]):
        """Set values."""
        self._selected_scenarios = {str(value).strip() for value in (values or []) if str(value).strip()}
        self._sync_checkboxes()
        self._refresh_selected_summary()

    def get_values(self) -> list[str]:
        """Return values."""
        return [name for name in self._all_scenarios if name in self._selected_scenarios]

    def _build_scenario_list(self) -> None:
        """Build scenario list."""
        for widget in self.results_scroll.winfo_children():
            widget.destroy()
        self._scenario_checks.clear()

        for row, scenario in enumerate(self._all_scenarios):
            # Process each (row, scenario) from enumerate(_all_scenarios).
            var = ctk.StringVar(value="on" if scenario in self._selected_scenarios else "off")
            check = ctk.CTkCheckBox(
                self.results_scroll,
                text=scenario,
                variable=var,
                onvalue="on",
                offvalue="off",
                corner_radius=8,
                fg_color=ARC_EDITOR_PALETTE.accent,
                hover_color=ARC_EDITOR_PALETTE.accent,
                border_color=ARC_EDITOR_PALETTE.border,
                text_color=ARC_EDITOR_PALETTE.text_primary,
                command=lambda name=scenario: self._toggle_scenario(name),
            )
            check.grid(row=row, column=0, sticky="ew", padx=10, pady=6)
            self._scenario_vars[scenario] = var
            self._scenario_checks.append((scenario, check))

    def _on_search(self, _event=None) -> None:
        """Handle search."""
        self._filter_visible_scenarios()

    def _filter_visible_scenarios(self) -> None:
        """Internal helper for filter visible scenarios."""
        query = self.search_var.get().strip().lower()
        any_visible = False
        for row, (scenario, check) in enumerate(self._scenario_checks):
            # Process each (row, (scenario, check)) from enumerate(_scenario_checks).
            visible = not query or query in scenario.lower()
            if visible:
                check.grid(row=row, column=0, sticky="ew", padx=10, pady=6)
                any_visible = True
            else:
                check.grid_remove()

        if any_visible:
            self.empty_results_label.grid_remove()
        else:
            self.empty_results_label.grid(row=4, column=0, sticky="ew", pady=(8, 0))

    def _toggle_scenario(self, scenario: str) -> None:
        """Toggle scenario."""
        if self._scenario_vars[scenario].get() == "on":
            self._selected_scenarios.add(scenario)
        else:
            self._selected_scenarios.discard(scenario)
        self._refresh_selected_summary()

    def _select_visible(self) -> None:
        """Select visible."""
        query = self.search_var.get().strip().lower()
        for scenario, _check in self._scenario_checks:
            if not query or query in scenario.lower():
                self._selected_scenarios.add(scenario)
        self._sync_checkboxes()
        self._refresh_selected_summary()

    def _clear_selection(self) -> None:
        """Clear selection."""
        self._selected_scenarios.clear()
        self._sync_checkboxes()
        self._refresh_selected_summary()

    def _sync_checkboxes(self) -> None:
        """Synchronize checkboxes."""
        for scenario, var in self._scenario_vars.items():
            var.set("on" if scenario in self._selected_scenarios else "off")

    def _refresh_selected_summary(self) -> None:
        """Refresh selected summary."""
        selected = [name for name in self._all_scenarios if name in self._selected_scenarios]
        self.selection_count_label.configure(text=f"{len(selected)} selected")
        if not selected:
            self.selected_summary_label.configure(
                text="No scenarios linked yet. Pick the chapters that move this arc forward."
            )
            return

        preview = "  •  ".join(selected[:4])
        if len(selected) > 4:
            preview += f"  •  +{len(selected) - 4} more"
        self.selected_summary_label.configure(text=preview)
