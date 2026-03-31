"""Dialog for campaign arc editor."""

from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from modules.campaigns.shared.arc_status import CANONICAL_ARC_STATUSES, canonicalize_arc_status
from modules.campaigns.ui.theme import ARC_EDITOR_PALETTE, ARC_EDITOR_STATUS_HINTS
from modules.campaigns.ui.widgets import FormSection, ScenarioMultiSelector
from modules.helpers.window_helper import position_window_at_top


class ArcEditorDialog(ctk.CTkToplevel):
    """Modal dialog used by campaign wizard to create/update one campaign arc."""

    def __init__(self, master, scenarios: list[str], initial_data: dict | None = None):
        """Initialize the ArcEditorDialog instance."""
        super().__init__(master)
        self.title("Campaign Arc")
        self.geometry("860x940")
        self.minsize(820, 860)
        self.configure(fg_color=ARC_EDITOR_PALETTE.window_bg)
        self.result = None

        initial = initial_data or {}

        self.name_var = ctk.StringVar(value=initial.get("name", ""))
        self.status_var = ctk.StringVar(value=canonicalize_arc_status(initial.get("status")))
        self.thread_var = ctk.StringVar(value=initial.get("thread", ""))
        self.status_hint_var = ctk.StringVar(
            value=ARC_EDITOR_STATUS_HINTS.get(self.status_var.get(), ARC_EDITOR_STATUS_HINTS["Planned"])
        )

        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=18, pady=18)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        self._build_hero(shell, scenario_count=len(scenarios), initial=initial)

        scroll = ctk.CTkScrollableFrame(shell, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        scroll.grid_columnconfigure(0, weight=1)
        self.content_scroll = scroll

        self._build_identity_section(scroll)
        self._build_story_section(scroll, initial)
        self._build_scenarios_section(scroll, scenarios, initial)
        self._build_footer(shell)

        self.status_var.trace_add("write", self._update_status_hint)

        self.transient(master)
        self.grab_set()
        self.focus_force()
        position_window_at_top(self)

    def _build_hero(self, parent: ctk.CTkFrame, *, scenario_count: int, initial: dict) -> None:
        """Build hero."""
        hero = ctk.CTkFrame(
            parent,
            fg_color=ARC_EDITOR_PALETTE.hero_gradient_start,
            corner_radius=22,
            border_width=1,
            border_color=ARC_EDITOR_PALETTE.border,
        )
        hero.grid(row=0, column=0, sticky="ew")
        hero.grid_columnconfigure(0, weight=1)
        hero.grid_columnconfigure(1, weight=0)

        title = "Refine campaign arc" if initial else "Design a new campaign arc"
        subtitle = (
            "Give the arc a clear promise, define the win condition, and connect the scenarios that deliver the payoff."
        )

        ctk.CTkLabel(
            hero,
            text=title,
            anchor="w",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=ARC_EDITOR_PALETTE.text_primary,
        ).grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 4))

        ctk.CTkLabel(
            hero,
            text=subtitle,
            anchor="w",
            justify="left",
            wraplength=560,
            text_color=ARC_EDITOR_PALETTE.text_secondary,
        ).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 18))

        stat_card = ctk.CTkFrame(
            hero,
            fg_color=ARC_EDITOR_PALETTE.hero_gradient_end,
            corner_radius=18,
            border_width=1,
            border_color=ARC_EDITOR_PALETTE.chip_border,
        )
        stat_card.grid(row=0, column=1, rowspan=2, sticky="ns", padx=18, pady=18)

        ctk.CTkLabel(
            stat_card,
            text=str(scenario_count),
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=ARC_EDITOR_PALETTE.text_primary,
        ).pack(padx=20, pady=(14, 0))
        ctk.CTkLabel(
            stat_card,
            text="scenarios ready to link",
            text_color=ARC_EDITOR_PALETTE.text_secondary,
        ).pack(padx=20, pady=(0, 14))

    def _build_identity_section(self, parent: ctk.CTkScrollableFrame) -> None:
        """Build identity section."""
        section = FormSection(
            parent,
            title="Arc identity",
            description="Start with a strong title and a narrative thread so the arc is easy to scan in the campaign overview.",
        )
        section.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        body = section.body
        body.grid_columnconfigure((0, 1), weight=1)

        self._create_field_label(body, 0, 0, "Arc name")
        self.name_entry = ctk.CTkEntry(
            body,
            textvariable=self.name_var,
            height=40,
            corner_radius=14,
            fg_color=ARC_EDITOR_PALETTE.surface_alt,
            border_color=ARC_EDITOR_PALETTE.border,
            text_color=ARC_EDITOR_PALETTE.text_primary,
            placeholder_text="Example: Fall of the Glass City",
        )
        self.name_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))

        self._create_field_label(body, 0, 1, "Narrative thread")
        self.thread_entry = ctk.CTkEntry(
            body,
            textvariable=self.thread_var,
            height=40,
            corner_radius=14,
            fg_color=ARC_EDITOR_PALETTE.surface_alt,
            border_color=ARC_EDITOR_PALETTE.border,
            text_color=ARC_EDITOR_PALETTE.text_primary,
            placeholder_text="Political thriller, revenge quest, corporate sabotage...",
        )
        self.thread_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        self._create_field_label(body, 2, 0, "Status")
        self.status_menu = ctk.CTkOptionMenu(
            body,
            variable=self.status_var,
            values=list(CANONICAL_ARC_STATUSES),
            height=40,
            corner_radius=14,
            fg_color=ARC_EDITOR_PALETTE.success,
            button_color=ARC_EDITOR_PALETTE.success,
            button_hover_color=ARC_EDITOR_PALETTE.success_hover,
            dropdown_fg_color=ARC_EDITOR_PALETTE.surface_alt,
        )
        self.status_menu.grid(row=3, column=0, sticky="ew", padx=(0, 8))

        self.status_hint = ctk.CTkLabel(
            body,
            textvariable=self.status_hint_var,
            anchor="w",
            justify="left",
            wraplength=300,
            text_color=ARC_EDITOR_PALETTE.text_secondary,
        )
        self.status_hint.grid(row=3, column=1, sticky="ew", padx=(8, 0))

    def _build_story_section(self, parent: ctk.CTkScrollableFrame, initial: dict) -> None:
        """Build story section."""
        section = FormSection(
            parent,
            title="Story brief",
            description="Keep these two blocks short and punchy. They should tell you what the arc is about and how you know it is resolved.",
        )
        section.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        body = section.body
        body.grid_columnconfigure(0, weight=1)

        self._create_field_label(body, 0, 0, "Summary")
        self.summary_box = self._create_textbox(body, height=120)
        self.summary_box.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.summary_box.insert("1.0", initial.get("summary", ""))

        self._create_field_label(body, 2, 0, "Objective")
        self.objective_box = self._create_textbox(body, height=120)
        self.objective_box.grid(row=3, column=0, sticky="ew")
        self.objective_box.insert("1.0", initial.get("objective", ""))

    def _build_scenarios_section(self, parent: ctk.CTkScrollableFrame, scenarios: list[str], initial: dict) -> None:
        """Build scenarios section."""
        section = FormSection(
            parent,
            title="Scenario links",
            description="Choose the scenarios that actively advance this arc. Search and batch-select to build a tighter story path.",
        )
        section.grid(row=2, column=0, sticky="ew", pady=(0, 14))

        self.scenario_selector = ScenarioMultiSelector(section.body, scenarios, label="Linked scenarios")
        self.scenario_selector.grid(row=0, column=0, sticky="ew")

        initial_scenarios = initial.get("scenarios") or []
        if not initial_scenarios and scenarios:
            initial_scenarios = scenarios[:2]
        self.scenario_selector.set_values(initial_scenarios)

        if scenarios:
            helper = f"Tip: arcs usually read best when 2–5 scenarios are linked. You currently have {len(scenarios)} scenarios available."
        else:
            helper = "No scenarios exist yet. Save the arc now and link scenarios later from the campaign builder."

        ctk.CTkLabel(
            section.body,
            text=helper,
            anchor="w",
            justify="left",
            wraplength=620,
            text_color=ARC_EDITOR_PALETTE.text_secondary,
        ).grid(row=1, column=0, sticky="ew", pady=(12, 0))

    def _build_footer(self, parent: ctk.CTkFrame) -> None:
        """Build footer."""
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            footer,
            text="Aim for clarity over completeness—this editor should help you spot the arc at a glance during prep.",
            anchor="w",
            text_color=ARC_EDITOR_PALETTE.text_secondary,
        ).grid(row=0, column=0, sticky="w")

        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            actions,
            text="Cancel",
            width=120,
            fg_color=ARC_EDITOR_PALETTE.danger,
            hover_color=ARC_EDITOR_PALETTE.danger_hover,
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            actions,
            text="Save arc",
            width=140,
            fg_color=ARC_EDITOR_PALETTE.success,
            hover_color=ARC_EDITOR_PALETTE.success_hover,
            command=self._save,
        ).pack(side="right")

    def _create_field_label(self, parent: ctk.CTkFrame, row: int, column: int, text: str) -> None:
        """Create field label."""
        padx = (0, 8) if column == 0 else (8, 0)
        ctk.CTkLabel(
            parent,
            text=text,
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=ARC_EDITOR_PALETTE.text_primary,
        ).grid(row=row, column=column, sticky="w", padx=padx, pady=(0, 6))

    def _create_textbox(self, parent: ctk.CTkFrame, *, height: int) -> ctk.CTkTextbox:
        """Create textbox."""
        return ctk.CTkTextbox(
            parent,
            height=height,
            corner_radius=16,
            fg_color=ARC_EDITOR_PALETTE.surface_alt,
            border_width=1,
            border_color=ARC_EDITOR_PALETTE.border,
            text_color=ARC_EDITOR_PALETTE.text_primary,
            wrap="word",
        )

    def _update_status_hint(self, *_args) -> None:
        """Update status hint."""
        self.status_hint_var.set(
            ARC_EDITOR_STATUS_HINTS.get(self.status_var.get(), ARC_EDITOR_STATUS_HINTS["Planned"])
        )

    def _save(self):
        """Save the operation."""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Arc name is required.", parent=self)
            self.name_entry.focus_set()
            return

        scenarios = self.scenario_selector.get_values()

        self.result = {
            "name": name,
            "summary": self.summary_box.get("1.0", "end").strip(),
            "objective": self.objective_box.get("1.0", "end").strip(),
            "status": canonicalize_arc_status(self.status_var.get()),
            "thread": self.thread_var.get().strip(),
            "scenarios": scenarios,
        }
        self.destroy()

    @staticmethod
    def validate_generation_requirements(arc: dict) -> str | None:
        """Validate generation requirements."""
        name = str((arc or {}).get("name") or "").strip() or "Unnamed arc"
        linked_scenarios = [str(title).strip() for title in ((arc or {}).get("scenarios") or []) if str(title).strip()]
        if not linked_scenarios:
            return f"Arc '{name}' must include at least one linked scenario before generating new scenarios."
        return None
