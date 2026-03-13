from __future__ import annotations

import ast
import json
from typing import Any, Callable

import customtkinter as ctk


class CampaignArcField(ctk.CTkFrame):
    """Read-only campaign arc renderer with scenario quick-open actions."""

    def __init__(
        self,
        parent,
        *,
        raw_value: Any,
        open_scenario_callback: Callable[[str], None],
    ):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self._open_scenario_callback = open_scenario_callback

        arcs = coerce_arc_list(raw_value)
        if not arcs:
            ctk.CTkLabel(self, text="No arcs configured.", text_color="gray70", anchor="w").grid(
                row=0,
                column=0,
                sticky="ew",
                padx=4,
                pady=4,
            )
            return

        for row, arc in enumerate(arcs):
            arc_name = str(arc.get("name") or f"Arc {row + 1}").strip() or f"Arc {row + 1}"
            block = ctk.CTkFrame(self, corner_radius=10)
            block.grid(row=row, column=0, sticky="ew", padx=2, pady=4)
            block.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                block,
                text=arc_name,
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))

            detail_row = 1
            for label, key in (("Status", "status"), ("Summary", "summary"), ("Objective", "objective")):
                value = str(arc.get(key) or "").strip()
                if not value:
                    continue
                ctk.CTkLabel(
                    block,
                    text=f"{label}: {value}",
                    anchor="w",
                    justify="left",
                    wraplength=580,
                    text_color="gray85",
                ).grid(row=detail_row, column=0, sticky="ew", padx=12, pady=(0, 2))
                detail_row += 1

            scenarios = [str(name).strip() for name in arc.get("scenarios") or [] if str(name).strip()]
            if scenarios:
                ctk.CTkLabel(block, text="Scenarios", anchor="w", text_color="gray80").grid(
                    row=detail_row,
                    column=0,
                    sticky="ew",
                    padx=12,
                    pady=(2, 2),
                )
                detail_row += 1
                scenario_wrap = ctk.CTkFrame(block, fg_color="transparent")
                scenario_wrap.grid(row=detail_row, column=0, sticky="ew", padx=10, pady=(0, 8))
                for idx, scenario_name in enumerate(scenarios):
                    ctk.CTkButton(
                        scenario_wrap,
                        text=f"Open {scenario_name}",
                        anchor="w",
                        command=lambda n=scenario_name: self._open_scenario_callback(n),
                    ).grid(row=idx, column=0, sticky="ew", pady=2)


def coerce_arc_list(raw_value: Any) -> list[dict[str, Any]]:
    def _from_dict(payload: dict[str, Any]) -> list[dict[str, Any]]:
        arcs_value = payload.get("arcs")
        if isinstance(arcs_value, list):
            return [arc for arc in arcs_value if isinstance(arc, dict)]

        text_value = payload.get("text")
        if text_value is not None:
            return coerce_arc_list(text_value)

        arc_keys = {"name", "summary", "objective", "status", "scenarios"}
        if any(key in payload for key in arc_keys):
            return [payload]

        return []

    if isinstance(raw_value, list):
        return [arc for arc in raw_value if isinstance(arc, dict)]

    if isinstance(raw_value, dict):
        return _from_dict(raw_value)

    if isinstance(raw_value, str):
        parsed: Any = None
        try:
            parsed = json.loads(raw_value)
        except Exception:
            try:
                parsed = ast.literal_eval(raw_value)
            except Exception:
                parsed = None

        if isinstance(parsed, list):
            return [arc for arc in parsed if isinstance(arc, dict)]
        if isinstance(parsed, dict):
            return _from_dict(parsed)

    return []
