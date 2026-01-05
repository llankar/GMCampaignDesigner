import customtkinter as ctk
from typing import Callable, Optional

from modules.helpers.logging_helper import log_module_import


class InspectorPanel(ctk.CTkFrame):
    def __init__(self, master, on_edit_current_entity: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_edit_current_entity = on_edit_current_entity

        header = ctk.CTkLabel(self, text="Inspector", font=("Helvetica", 16, "bold"))
        header.pack(side="top", anchor="w", padx=12, pady=(12, 6))

        self.focus_label = ctk.CTkLabel(self, text="No panel selected", font=("Helvetica", 13, "bold"))
        self.focus_label.pack(side="top", anchor="w", padx=12, pady=(4, 2))

        self.details_label = ctk.CTkLabel(self, text="", justify="left", anchor="w")
        self.details_label.pack(side="top", anchor="w", padx=12, pady=(2, 8))

        if self._on_edit_current_entity:
            self.edit_button = ctk.CTkButton(
                self,
                text="Edit Entity",
                command=self._on_edit_current_entity,
                state="disabled",
            )
            self.edit_button.pack(side="top", anchor="w", padx=12, pady=(4, 0))
        else:
            self.edit_button = None

    def set_focus(self, panel_name: Optional[str], meta: Optional[dict] = None):
        meta = meta or {}
        if panel_name:
            self.focus_label.configure(text=panel_name)
        else:
            self.focus_label.configure(text="No panel selected")

        detail_lines = []
        kind = meta.get("kind")
        if kind:
            detail_lines.append(f"Type: {kind}")
        entity_type = meta.get("entity_type")
        entity_name = meta.get("entity_name")
        if entity_type:
            detail_lines.append(f"Entity: {entity_type}")
        if entity_name:
            detail_lines.append(f"Name: {entity_name}")

        self.details_label.configure(text="\n".join(detail_lines) if detail_lines else "")

        if self.edit_button is not None:
            if kind == "entity":
                self.edit_button.configure(state="normal")
            else:
                self.edit_button.configure(state="disabled")


log_module_import(__name__)
