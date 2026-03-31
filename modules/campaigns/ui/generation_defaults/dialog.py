"""Dialog for campaign."""

from __future__ import annotations

import customtkinter as ctk

from modules.campaigns.ui.generation_defaults.mapper import generation_defaults_payload_to_state, generation_defaults_state_to_payload
from modules.generic.editor.styles import EDITOR_PALETTE, primary_button_style


class CampaignGenerationDefaultsDialog(ctk.CTkToplevel):
    """Editor dialog for campaign AI generation defaults."""

    def __init__(self, master, *, initial_state: dict | None = None):
        """Initialize the CampaignGenerationDefaultsDialog instance."""
        super().__init__(master)
        self.title("AI Generation Defaults")
        self.geometry("760x680")
        self.configure(fg_color=EDITOR_PALETTE["surface"])

        self.result_state: dict | None = None
        state = generation_defaults_payload_to_state(initial_state)

        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(root, text="Campaign AI Generation Defaults", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(
            root,
            text=(
                "These defaults steer arc/scenario generation. Main PC and protected factions are favored, "
                "while forbidden antagonist factions are blocked from antagonist roles."
            ),
            justify="left",
            text_color=EDITOR_PALETTE["muted_text"],
            wraplength=700,
        ).pack(anchor="w", pady=(0, 12))

        self.main_pc_factions_box = self._build_list_field(
            root,
            "Main PC factions",
            "One faction per line. AI treats these as player-aligned anchors.",
            "\n".join(state["main_pc_factions"]),
        )
        self.protected_factions_box = self._build_list_field(
            root,
            "Protected factions",
            "One faction per line. AI avoids depicting these as villains or direct targets.",
            "\n".join(state["protected_factions"]),
        )
        self.forbidden_antagonist_factions_box = self._build_list_field(
            root,
            "Forbidden antagonist factions",
            "One faction per line. AI must not cast these factions as antagonists.",
            "\n".join(state["forbidden_antagonist_factions"]),
        )

        self.optional_conflict_var = ctk.BooleanVar(value=bool(state.get("allow_optional_conflicts", True)))
        self.optional_conflict_checkbox = ctk.CTkCheckBox(
            root,
            text="Allow optional conflict between protected factions and campaign pressure",
            variable=self.optional_conflict_var,
        )
        self.optional_conflict_checkbox.pack(anchor="w", pady=(6, 4))
        ctk.CTkLabel(
            root,
            text=(
                "Enabled: AI may introduce nuanced tension around protected factions when needed for drama. "
                "Disabled: AI should avoid conflict framing involving protected factions."
            ),
            justify="left",
            text_color=EDITOR_PALETTE["muted_text"],
            wraplength=700,
        ).pack(anchor="w", pady=(0, 12))

        actions = ctk.CTkFrame(root, fg_color="transparent")
        actions.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(actions, text="Cancel", command=self.destroy, fg_color="transparent", border_width=1).pack(side="right", padx=(8, 0))
        ctk.CTkButton(actions, text="Save Defaults", command=self._on_save, **primary_button_style()).pack(side="right")

        self.transient(master)
        self.grab_set()
        self.focus_force()

    def _build_list_field(self, parent, label: str, helper: str, value: str) -> ctk.CTkTextbox:
        """Build list field."""
        ctk.CTkLabel(parent, text=label, font=("Arial", 13, "bold")).pack(anchor="w")
        ctk.CTkLabel(parent, text=helper, justify="left", text_color=EDITOR_PALETTE["muted_text"], wraplength=700).pack(anchor="w", pady=(0, 4))
        box = ctk.CTkTextbox(parent, height=94, fg_color=EDITOR_PALETTE["surface_soft"], border_width=1, border_color=EDITOR_PALETTE["border"])
        box.pack(fill="x", pady=(0, 10))
        if value:
            box.insert("1.0", value)
        return box

    def _on_save(self):
        """Handle save."""
        self.result_state = generation_defaults_state_to_payload(
            {
                "main_pc_factions": self._textbox_lines(self.main_pc_factions_box),
                "protected_factions": self._textbox_lines(self.protected_factions_box),
                "forbidden_antagonist_factions": self._textbox_lines(self.forbidden_antagonist_factions_box),
                "allow_optional_conflicts": bool(self.optional_conflict_var.get()),
            }
        )
        self.destroy()

    @staticmethod
    def _textbox_lines(widget: ctk.CTkTextbox) -> list[str]:
        """Internal helper for textbox lines."""
        return [line.strip() for line in widget.get("1.0", "end").splitlines() if line.strip()]
