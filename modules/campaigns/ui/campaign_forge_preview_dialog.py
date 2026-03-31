"""Dialog for campaign forge preview."""

from __future__ import annotations

from copy import deepcopy
from tkinter import messagebox

import customtkinter as ctk

from modules.campaigns.ui.campaign_forge_preview.models import CampaignForgeArcPreview, CampaignForgeScenarioPreview
from modules.campaigns.ui.campaign_forge_preview.validation import evaluate_forge_warnings
from modules.helpers.window_helper import position_window_at_top


class CampaignForgePreviewDialog(ctk.CTkToplevel):
    """Preview generated campaign arcs and allow include/exclude pruning before save."""

    def __init__(
        self,
        master,
        *,
        campaign_summary: str,
        generated_payload: dict,
        arc_metadata_by_name: dict[str, dict] | None = None,
    ):
        """Initialize the CampaignForgePreviewDialog instance."""
        super().__init__(master)
        self.title("Campaign Forge Preview")
        self.geometry("980x900")
        self.minsize(920, 760)

        self.result: dict | None = None
        self._generated_payload = generated_payload
        self._validation = evaluate_forge_warnings(generated_payload)
        self._arc_rows: list[dict] = []
        self._arc_previews = self._build_arc_previews(generated_payload, arc_metadata_by_name or {})

        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=16, pady=16)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        self._build_summary_block(shell, campaign_summary)
        self._build_content_block(shell)
        self._build_footer(shell)

        self.transient(master)
        self.grab_set()
        self.focus_force()
        position_window_at_top(self)

    def _build_summary_block(self, parent: ctk.CTkFrame, campaign_summary: str) -> None:
        """Build summary block."""
        card = ctk.CTkFrame(parent)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Campaign summary",
            anchor="w",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        summary_box = ctk.CTkTextbox(card, height=84, wrap="word")
        summary_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        summary_box.insert("1.0", campaign_summary.strip() or "No campaign summary available.")
        summary_box.configure(state="disabled")

        ctk.CTkLabel(
            card,
            text="Validation warnings",
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 4))

        warning_box = ctk.CTkTextbox(card, height=84, wrap="word")
        warning_box.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        warning_box.insert("1.0", "\n".join(f"• {line}" for line in self._validation.global_warnings))
        warning_box.configure(state="disabled")

    def _build_content_block(self, parent: ctk.CTkFrame) -> None:
        """Build content block."""
        self.scroll = ctk.CTkScrollableFrame(parent)
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        for arc_index, arc in enumerate(self._arc_previews):
            self._build_arc_card(arc_index, arc)

    def _build_arc_card(self, row_index: int, arc: CampaignForgeArcPreview) -> None:
        """Build arc card."""
        arc_frame = ctk.CTkFrame(self.scroll)
        arc_frame.grid(row=row_index, column=0, sticky="ew", padx=4, pady=(0, 10))
        arc_frame.grid_columnconfigure(0, weight=1)

        arc_var = ctk.BooleanVar(value=True)
        arc_toggle = ctk.CTkCheckBox(
            arc_frame,
            text=f"Arc: {arc.name}",
            variable=arc_var,
            command=lambda idx=row_index: self._on_arc_toggle(idx),
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        arc_toggle.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))

        metadata = f"Objective: {arc.objective or '—'}\nThread: {arc.thread or '—'}\nStatus: {arc.status or '—'}"
        ctk.CTkLabel(arc_frame, text=metadata, anchor="w", justify="left").grid(
            row=1, column=0, sticky="ew", padx=32, pady=(0, 8)
        )

        scenario_rows = []
        for scn_idx, scenario in enumerate(arc.scenarios):
            scenario_rows.append(self._build_scenario_row(arc_frame, scn_idx, scenario))

        self._arc_rows.append({"arc_var": arc_var, "arc_toggle": arc_toggle, "scenario_rows": scenario_rows, "arc": arc})

    def _build_scenario_row(self, parent: ctk.CTkFrame, scenario_index: int, scenario: CampaignForgeScenarioPreview) -> dict:
        """Build scenario row."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=scenario_index + 2, column=0, sticky="ew", padx=22, pady=(0, 6))
        row.grid_columnconfigure(1, weight=1)

        scenario_var = ctk.BooleanVar(value=True)
        toggle = ctk.CTkCheckBox(row, text="", width=20, variable=scenario_var)
        toggle.grid(row=0, column=0, sticky="nw", pady=(4, 0))

        summary = scenario.summary.strip()
        if len(summary) > 180:
            summary = summary[:177].rstrip() + "..."

        detail = f"{scenario.title}\n{summary or 'No summary provided.'}"
        if scenario.warnings:
            detail = f"{detail}\nWarnings: {', '.join(scenario.warnings)}"

        label = ctk.CTkLabel(row, text=detail, anchor="w", justify="left", wraplength=800)
        label.grid(row=0, column=1, sticky="ew")
        return {"scenario_var": scenario_var, "toggle": toggle, "label": label, "scenario": scenario}

    def _build_footer(self, parent: ctk.CTkFrame) -> None:
        """Build footer."""
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))

        ctk.CTkButton(footer, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Accept selection", command=self._accept).pack(side="right")

    def _on_arc_toggle(self, row_index: int) -> None:
        """Handle arc toggle."""
        arc_row = self._arc_rows[row_index]
        enabled = bool(arc_row["arc_var"].get())
        state = "normal" if enabled else "disabled"
        for scenario_row in arc_row["scenario_rows"]:
            scenario_row["toggle"].configure(state=state)
            scenario_row["label"].configure(text_color=("gray35" if enabled else "gray58"))

    def _accept(self) -> None:
        """Internal helper for accept."""
        accepted_arcs: list[dict] = []

        for arc_row in self._arc_rows:
            # Process each arc_row from _arc_rows.
            if not arc_row["arc_var"].get():
                continue

            arc = arc_row["arc"]
            accepted_scenarios: list[dict] = []
            source_arc_group = self._find_source_arc_group(arc.name)
            source_scenarios = source_arc_group.get("scenarios") or []

            for scenario_row in arc_row["scenario_rows"]:
                # Process each scenario_row from arc_row['scenario_rows'].
                if not scenario_row["scenario_var"].get():
                    continue
                title = scenario_row["scenario"].title.casefold()
                for payload in source_scenarios:
                    if str(payload.get("Title") or "").strip().casefold() == title:
                        accepted_scenarios.append(deepcopy(payload))
                        break

            if accepted_scenarios:
                accepted_arcs.append({"arc_name": arc.name, "scenarios": accepted_scenarios})

        if not accepted_arcs:
            messagebox.showwarning("Nothing selected", "Select at least one scenario to continue.", parent=self)
            return

        self.result = {
            **self._generated_payload,
            "arcs": accepted_arcs,
        }
        self.destroy()

    def _find_source_arc_group(self, arc_name: str) -> dict:
        """Find source arc group."""
        for group in self._generated_payload.get("arcs") or []:
            if str(group.get("arc_name") or "").strip().casefold() == arc_name.casefold():
                return group
        return {}

    def _build_arc_previews(self, generated_payload: dict, arc_metadata_by_name: dict[str, dict]) -> list[CampaignForgeArcPreview]:
        """Build arc previews."""
        previews: list[CampaignForgeArcPreview] = []
        for group in generated_payload.get("arcs") or []:
            # Process each group from generated_payload.get('arcs') or [].
            arc_name = str(group.get("arc_name") or "Unnamed arc").strip() or "Unnamed arc"
            arc_meta = arc_metadata_by_name.get(arc_name.casefold(), {})
            scenario_previews: list[CampaignForgeScenarioPreview] = []

            for scenario in group.get("scenarios") or []:
                title = str(scenario.get("Title") or "Untitled scenario").strip() or "Untitled scenario"
                summary = str(scenario.get("Summary") or "").strip()
                warnings = self._validation.scenario_warnings.get((arc_name.casefold(), title.casefold()), [])
                scenario_previews.append(
                    CampaignForgeScenarioPreview(
                        arc_name=arc_name,
                        title=title,
                        summary=summary,
                        warnings=warnings,
                    )
                )

            previews.append(
                CampaignForgeArcPreview(
                    name=arc_name,
                    objective=str(arc_meta.get("objective") or "").strip(),
                    thread=str(arc_meta.get("thread") or "").strip(),
                    status=str(arc_meta.get("status") or "").strip(),
                    scenarios=scenario_previews,
                )
            )

        return previews


def preview_campaign_forge_payload(
    master,
    *,
    campaign_summary: str,
    generated_payload: dict,
    arc_metadata_by_name: dict[str, dict] | None = None,
) -> dict | None:
    """Handle preview campaign forge payload."""
    dialog = CampaignForgePreviewDialog(
        master,
        campaign_summary=campaign_summary,
        generated_payload=generated_payload,
        arc_metadata_by_name=arc_metadata_by_name,
    )
    master.wait_window(dialog)
    return dialog.result
