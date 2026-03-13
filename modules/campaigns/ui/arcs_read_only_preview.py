from __future__ import annotations

import ast
import json
from typing import Any

import customtkinter as ctk


class ReadOnlyArcsPreview(ctk.CTkFrame):
    """Read-only, human-friendly rendering of campaign arc data."""

    def __init__(self, parent, raw_value: Any):
        super().__init__(parent)
        self._raw_value = raw_value
        self._formatted_text = self._format_arcs(raw_value)

        info = ctk.CTkLabel(
            self,
            text="Campaign arcs (read-only)",
            anchor="w",
        )
        info.pack(fill="x", padx=5, pady=(5, 0))

        textbox = ctk.CTkTextbox(self, height=200, wrap="word")
        textbox.insert("1.0", self._formatted_text)
        textbox.configure(state="disabled")
        textbox.pack(fill="x", expand=False, padx=5, pady=5)

        self.textbox = textbox

    def get_text_data(self):
        """Keep the original payload untouched during save."""

        return self._raw_value

    def _format_arcs(self, raw_value: Any) -> str:
        arcs = self._coerce_to_arc_list(raw_value)
        if not arcs:
            return "No arcs configured."

        lines: list[str] = []
        for index, arc in enumerate(arcs, start=1):
            if not isinstance(arc, dict):
                continue

            name = str(arc.get("name") or f"Arc {index}").strip() or f"Arc {index}"
            status = str(arc.get("status") or "").strip()
            summary = str(arc.get("summary") or "").strip()
            objective = str(arc.get("objective") or "").strip()

            lines.append(f"{index}. {name}")
            if status:
                lines.append(f"   Status: {status}")
            if summary:
                lines.append(f"   Summary: {summary}")
            if objective:
                lines.append(f"   Objective: {objective}")

            scenarios = arc.get("scenarios")
            if isinstance(scenarios, list) and scenarios:
                lines.append("   Scenarios:")
                for scenario in scenarios:
                    scenario_name = str(scenario).strip()
                    if scenario_name:
                        lines.append(f"     - {scenario_name}")

            lines.append("")

        rendered = "\n".join(lines).strip()
        return rendered or "No arcs configured."

    @staticmethod
    def _coerce_to_arc_list(raw_value: Any) -> list[dict[str, Any]]:
        if isinstance(raw_value, list):
            return [arc for arc in raw_value if isinstance(arc, dict)]

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

        return []
