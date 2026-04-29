from __future__ import annotations

import customtkinter as ctk


class PropertiesPanel(ctk.CTkFrame):
    """Selection-aware property editor for nodes and edges."""

    def __init__(self, master):
        super().__init__(master, fg_color="#101827", corner_radius=12)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self.on_change = None
        self._loading = False

        ctk.CTkLabel(self, text="Properties", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 2)
        )
        self.dirty_label = ctk.CTkLabel(self, text="Saved", text_color="#86efac")
        self.dirty_label.grid(row=0, column=0, sticky="e", padx=12, pady=(10, 2))

        self.mode_label = ctk.CTkLabel(self, text="No selection")
        self.mode_label.grid(row=1, column=0, sticky="w", padx=12, pady=(2, 8))

        self.form = ctk.CTkScrollableFrame(self, fg_color="transparent", height=220)
        self.form.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self.form.grid_columnconfigure(0, weight=1)

        self.readonly_ids = ctk.CTkLabel(self, text="", justify="left", anchor="w")
        self.readonly_ids.grid(row=3, column=0, sticky="ew", padx=12, pady=(2, 4))

        ctk.CTkLabel(self, text="Notes").grid(row=4, column=0, sticky="w", padx=12, pady=(0, 2))
        self.notes_box = ctk.CTkTextbox(self, height=140)
        self.notes_box.grid(row=5, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.notes_box.bind("<KeyRelease>", lambda _e: self._emit_change("notes", self.notes_box.get("1.0", "end").strip()))

        self._build_vars()
        self._build_form()
        self.show_empty()

    def _build_vars(self):
        self.title_var = ctk.StringVar()
        self.node_type_var = ctk.StringVar()
        self.active_var = ctk.BooleanVar(value=True)
        self.objective_var = ctk.StringVar()
        self.success_condition_var = ctk.StringVar()
        self.reward_var = ctk.StringVar()
        self.label_var = ctk.StringVar()
        self.condition_type_var = ctk.StringVar()
        self.condition_value_var = ctk.StringVar()

        for key, var in {
            "title": self.title_var,
            "type": self.node_type_var,
            "objective": self.objective_var,
            "success_condition": self.success_condition_var,
            "reward": self.reward_var,
            "label": self.label_var,
            "condition_type": self.condition_type_var,
            "condition_value": self.condition_value_var,
        }.items():
            var.trace_add("write", lambda *_args, k=key, v=var: self._emit_change(k, v.get()))

    def _build_form(self):
        self._widgets = {}

        def add_entry(row, label, var):
            ctk.CTkLabel(self.form, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=(4, 2))
            w = ctk.CTkEntry(self.form, textvariable=var)
            w.grid(row=row + 1, column=0, sticky="ew", padx=8)
            return w

        self._widgets["title"] = add_entry(0, "Node title", self.title_var)
        self._widgets["type"] = add_entry(2, "Type", self.node_type_var)
        self._widgets["active"] = ctk.CTkSwitch(
            self.form,
            text="Active",
            variable=self.active_var,
            command=lambda: self._emit_change("active", bool(self.active_var.get())),
        )
        self._widgets["active"].grid(row=4, column=0, sticky="w", padx=8, pady=6)
        self._widgets["objective"] = add_entry(5, "Objective", self.objective_var)
        self._widgets["success_condition"] = add_entry(7, "Success condition", self.success_condition_var)
        self._widgets["reward"] = add_entry(9, "Reward", self.reward_var)
        self._widgets["label"] = add_entry(11, "Edge label", self.label_var)
        self._widgets["condition_type"] = add_entry(13, "Condition type", self.condition_type_var)
        self._widgets["condition_value"] = add_entry(15, "Condition metadata", self.condition_value_var)

    def _emit_change(self, field: str, value):
        if self._loading or not self.on_change:
            return
        self.on_change(field, value)

    def set_dirty(self, dirty: bool):
        self.dirty_label.configure(text="Unsaved changes" if dirty else "Saved", text_color="#fca5a5" if dirty else "#86efac")

    def show_empty(self):
        self._loading = True
        try:
            self.mode_label.configure(text="No selection")
            self.readonly_ids.configure(text="")
            self._set_visibility(node_mode=False, edge_mode=False)
            self.notes_box.delete("1.0", "end")
        finally:
            self._loading = False

    def load_node(self, node: dict):
        self._loading = True
        try:
            self.mode_label.configure(text="Node")
            self.readonly_ids.configure(text=f"ID: {node.get('id', '')}")
            self._set_visibility(node_mode=True, edge_mode=False)
            self.title_var.set(node.get("title", ""))
            self.node_type_var.set(node.get("type", "scene"))
            self.active_var.set(bool(node.get("active", True)))
            self.objective_var.set(node.get("objective", ""))
            self.success_condition_var.set(node.get("success_condition", ""))
            self.reward_var.set(node.get("reward", ""))
            self.notes_box.delete("1.0", "end")
            self.notes_box.insert("1.0", node.get("notes", ""))
        finally:
            self._loading = False

    def load_edge(self, edge: dict):
        self._loading = True
        try:
            self.mode_label.configure(text="Edge")
            self.readonly_ids.configure(text=f"ID: {edge.get('id','')}\nSource: {edge.get('source','')}\nTarget: {edge.get('target','')}")
            self._set_visibility(node_mode=False, edge_mode=True)
            self.label_var.set(edge.get("label", ""))
            self.condition_type_var.set(edge.get("condition_type", "always"))
            self.condition_value_var.set(edge.get("condition_value", ""))
            self.notes_box.delete("1.0", "end")
        finally:
            self._loading = False

    def _set_visibility(self, *, node_mode: bool, edge_mode: bool):
        node_keys = ["title", "type", "active", "objective", "success_condition", "reward"]
        edge_keys = ["label", "condition_type", "condition_value"]
        for key in node_keys + edge_keys:
            widget = self._widgets[key]
            if key in node_keys and node_mode:
                widget.grid()
            elif key in edge_keys and edge_mode:
                widget.grid()
            else:
                widget.grid_remove()
            if hasattr(widget, "master"):
                pass
