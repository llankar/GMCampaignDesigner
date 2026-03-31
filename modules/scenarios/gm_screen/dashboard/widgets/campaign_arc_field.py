"""Field helpers for dashboard campaign arc."""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from modules.campaigns.shared.arc_status import canonicalize_arc_status
from modules.campaigns.shared.arc_parser import coerce_arc_list
from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from modules.scenarios.gm_screen.dashboard.widgets.arc_display import ArcMomentumMeter


class CampaignArcField(ctk.CTkFrame):
    """Stylized read-only campaign arc renderer with momentum visuals."""

    _STATUS_COLOR = {
        "Planned": DASHBOARD_THEME.arc_planned,
        "In Progress": DASHBOARD_THEME.arc_active,
        "Paused": DASHBOARD_THEME.accent_soft,
        "Completed": DASHBOARD_THEME.arc_complete,
    }

    def __init__(
        self,
        parent,
        *,
        raw_value: Any,
        open_scenario_callback: Callable[[str], None],
    ):
        """Initialize the CampaignArcField instance."""
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self._open_scenario_callback = open_scenario_callback

        arcs = coerce_arc_list(raw_value)
        if not arcs:
            ctk.CTkLabel(self, text="No arcs configured.", text_color=DASHBOARD_THEME.text_secondary, anchor="w").grid(
                row=0,
                column=0,
                sticky="ew",
                padx=4,
                pady=4,
            )
            return

        for row, arc in enumerate(arcs):
            self._render_arc_card(arc, row)

    def _render_arc_card(self, arc: dict[str, Any], row: int) -> None:
        """Render arc card."""
        arc_name = str(arc.get("name") or f"Arc {row + 1}").strip() or f"Arc {row + 1}"
        status_text = canonicalize_arc_status(arc.get("status"))
        status_color = self._STATUS_COLOR.get(status_text, DASHBOARD_THEME.accent_soft)

        scenarios = [str(name).strip() for name in arc.get("scenarios") or [] if str(name).strip()]
        total_steps = max(len(scenarios), 1)
        completed_steps = self._estimate_completion(status_text, scenarios)

        block = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color=DASHBOARD_THEME.card_bg,
            border_width=1,
            border_color=DASHBOARD_THEME.card_border,
        )
        block.grid(row=row, column=0, sticky="ew", padx=2, pady=5)
        block.grid_columnconfigure(1, weight=1)

        ArcMomentumMeter(
            block,
            completed_steps=completed_steps,
            total_steps=total_steps,
            label="Arc momentum",
        ).grid(row=0, column=0, rowspan=4, sticky="ns", padx=(10, 2), pady=8)

        header = ctk.CTkFrame(block, fg_color="transparent")
        header.grid(row=0, column=1, sticky="ew", padx=(8, 10), pady=(10, 2))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=arc_name,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
            text_color=DASHBOARD_THEME.text_primary,
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            header,
            text=status_text,
            fg_color=status_color,
            text_color="#0f172a",
            corner_radius=999,
            padx=12,
            pady=4,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=1, sticky="e")

        self._render_arc_meta(block, arc, start_row=1)
        self._render_scenario_actions(block, scenarios, start_row=3)

    def _render_arc_meta(self, block: ctk.CTkFrame, arc: dict[str, Any], *, start_row: int) -> None:
        """Render arc meta."""
        row = start_row
        for label, key in (("Summary", "summary"), ("Objective", "objective")):
            # Process each (label, key) while updating arc meta.
            value = str(arc.get(key) or "").strip()
            if not value:
                continue
            ctk.CTkLabel(
                block,
                text=f"{label}: {value}",
                anchor="w",
                justify="left",
                wraplength=540,
                text_color=DASHBOARD_THEME.text_secondary,
            ).grid(row=row, column=1, sticky="ew", padx=(10, 10), pady=(0, 4))
            row += 1

    def _render_scenario_actions(self, block: ctk.CTkFrame, scenarios: list[str], *, start_row: int) -> None:
        """Render scenario actions."""
        if not scenarios:
            return
        ctk.CTkLabel(
            block,
            text="Scenario links",
            anchor="w",
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=start_row, column=1, sticky="ew", padx=(10, 10), pady=(2, 4))

        scenario_wrap = ctk.CTkFrame(block, fg_color="transparent")
        scenario_wrap.grid(row=start_row + 1, column=1, sticky="ew", padx=(8, 10), pady=(0, 10))

        for idx, scenario_name in enumerate(scenarios):
            ctk.CTkButton(
                scenario_wrap,
                text=f"↗ Open {scenario_name}",
                anchor="w",
                fg_color=DASHBOARD_THEME.button_fg,
                hover_color=DASHBOARD_THEME.button_hover,
                text_color=DASHBOARD_THEME.text_primary,
                command=lambda n=scenario_name: self._open_scenario_callback(n),
            ).grid(row=idx // 2, column=idx % 2, sticky="ew", padx=3, pady=3)

        scenario_wrap.grid_columnconfigure(0, weight=1)
        scenario_wrap.grid_columnconfigure(1, weight=1)

    def _estimate_completion(self, status_text: str, scenarios: list[str]) -> int:
        """Internal helper for estimate completion."""
        status = canonicalize_arc_status(status_text)
        total = max(len(scenarios), 1)
        if status == "Completed":
            return total
        if status == "In Progress":
            return max(1, total // 2)
        return 0


