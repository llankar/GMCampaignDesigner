"""Graph-inspired scenario planner with node list and property panel."""
from __future__ import annotations

import customtkinter as ctk


class GraphScenarioPlanner(ctk.CTkFrame):
    """Lightweight node flow planner that maps to scenario scenes."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="Flow Graph (Wizard + Node Editor)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(2, 8), pady=(0, 8))

        ctk.CTkLabel(
            self,
            text="Select a node on the left, edit its properties on the right.",
            text_color="#8ca2bf",
        ).grid(row=0, column=1, sticky="e", padx=(8, 2), pady=(0, 8))

        self.nodes_list = ctk.CTkTextbox(self, corner_radius=12)
        self.nodes_list.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        self.properties = ctk.CTkFrame(self, fg_color="#101827", corner_radius=12)
        self.properties.grid(row=1, column=1, sticky="nsew")
        self.properties.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.properties, text="Properties", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 6)
        )
        self.title_var = ctk.StringVar()
        self.objective_var = ctk.StringVar()
        self.success_condition_var = ctk.StringVar()

        self._entry(self.properties, "Node title", self.title_var, 1)
        self._entry(self.properties, "Objective", self.objective_var, 2)
        self._entry(self.properties, "Success condition", self.success_condition_var, 3)

        self.notes_box = ctk.CTkTextbox(self.properties, height=180)
        ctk.CTkLabel(self.properties, text="Notes").grid(row=4, column=0, sticky="w", padx=12, pady=(10, 2))
        self.notes_box.grid(row=5, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.properties.grid_rowconfigure(5, weight=1)

        self._scenes = []

    @staticmethod
    def _entry(parent, label, variable, row):
        ctk.CTkLabel(parent, text=label).grid(row=row * 2 - 1, column=0, sticky="w", padx=12, pady=(4, 2))
        ctk.CTkEntry(parent, textvariable=variable).grid(row=row * 2, column=0, sticky="ew", padx=12)

    def load_scenes(self, scenes):
        """Load scenario scenes into graph-like planner."""
        self._scenes = list(scenes or [])
        self.nodes_list.delete("1.0", "end")
        if not self._scenes:
            self.nodes_list.insert("1.0", "• Objective principal\n  → Scène 1 (à définir)")
            self.title_var.set("Objective principal")
            self.objective_var.set("")
            self.success_condition_var.set("")
            self.notes_box.delete("1.0", "end")
            return

        lines = []
        for index, scene in enumerate(self._scenes, start=1):
            title = str(scene.get("title") or f"Scene {index}").strip()
            objective = str(scene.get("objective") or "").strip()
            marker = "🎯" if index == 1 else "💬"
            lines.append(f"{marker} {index}. {title}")
            if objective:
                lines.append(f"   └─ objectif: {objective}")
            if index < len(self._scenes):
                lines.append(f"   └─ ensuite → {index + 1}")

        self.nodes_list.insert("1.0", "\n".join(lines))
        first = self._scenes[0]
        self.title_var.set(str(first.get("title") or ""))
        self.objective_var.set(str(first.get("objective") or ""))
        self.success_condition_var.set(str(first.get("success_condition") or ""))
        self.notes_box.delete("1.0", "end")
        self.notes_box.insert("1.0", str(first.get("notes") or ""))

    def export_scenes(self):
        """Export edited data preserving scene list."""
        if not self._scenes:
            return []
        first = dict(self._scenes[0])
        first["title"] = self.title_var.get().strip() or first.get("title") or "Objective principal"
        first["objective"] = self.objective_var.get().strip()
        first["success_condition"] = self.success_condition_var.get().strip()
        first["notes"] = self.notes_box.get("1.0", "end").strip()
        exported = [first]
        exported.extend(self._scenes[1:])
        return exported
