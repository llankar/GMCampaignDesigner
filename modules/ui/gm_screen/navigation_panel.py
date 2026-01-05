import customtkinter as ctk
import tkinter as tk
from typing import Callable, Iterable, Optional

from modules.helpers.logging_helper import log_module_import


ENTITY_TYPES = (
    "Scenarios",
    "Places",
    "NPCs",
    "PCs",
    "Factions",
    "Creatures",
    "Clues",
    "Informations",
    "Puzzles",
    "Objects",
    "Books",
)


class NavigationPanel(ctk.CTkFrame):
    def __init__(
        self,
        master,
        scenario_item: dict,
        entity_wrappers: dict,
        open_entity_callback: Callable[[str, str], None],
        open_entity_list_callback: Optional[Callable[[str], None]] = None,
        on_scene_selected: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self._scenario_item = scenario_item or {}
        self._entity_wrappers = entity_wrappers or {}
        self._open_entity_callback = open_entity_callback
        self._open_entity_list_callback = open_entity_list_callback
        self._on_scene_selected = on_scene_selected

        header = ctk.CTkLabel(self, text="Navigation", font=("Helvetica", 16, "bold"))
        header.pack(side="top", anchor="w", padx=12, pady=(12, 6))

        self.body = ctk.CTkScrollableFrame(self)
        self.body.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        self._build_scene_outline()
        self._build_entity_sections()

    def _build_scene_outline(self):
        scenes = self._normalize_list(self._scenario_item.get("Scenes"))

        section = ctk.CTkFrame(self.body)
        section.pack(fill="x", pady=(0, 12))

        title_row = ctk.CTkFrame(section)
        title_row.pack(fill="x")
        label = ctk.CTkLabel(title_row, text="Scenario Outline", font=("Helvetica", 13, "bold"))
        label.pack(side="left", padx=4, pady=(4, 2))

        if not scenes:
            empty_label = ctk.CTkLabel(section, text="No scenes added.")
            empty_label.pack(side="top", anchor="w", padx=8, pady=(4, 0))
            return

        listbox = tk.Listbox(section, height=min(6, max(2, len(scenes))))
        for scene in scenes:
            listbox.insert(tk.END, scene)
        listbox.pack(fill="x", padx=6, pady=(4, 0))
        listbox.bind("<Double-Button-1>", lambda _event: self._handle_scene_select(listbox))
        listbox.bind("<<ListboxSelect>>", lambda _event: self._handle_scene_select(listbox))

    def _build_entity_sections(self):
        for entity_type in ENTITY_TYPES:
            items = self._normalize_list(self._scenario_item.get(entity_type))
            if not items:
                continue
            if entity_type not in self._entity_wrappers:
                continue
            section = ctk.CTkFrame(self.body)
            section.pack(fill="x", pady=(0, 12))

            header_row = ctk.CTkFrame(section)
            header_row.pack(fill="x")
            label = ctk.CTkLabel(header_row, text=entity_type, font=("Helvetica", 13, "bold"))
            label.pack(side="left", padx=4, pady=(4, 2))

            if self._open_entity_list_callback:
                browse_button = ctk.CTkButton(
                    header_row,
                    text="Browse",
                    width=80,
                    command=lambda et=entity_type: self._open_entity_list_callback(et),
                )
                browse_button.pack(side="right", padx=4, pady=(4, 2))

            listbox = tk.Listbox(section, height=min(6, max(2, len(items))))
            for item in items:
                listbox.insert(tk.END, item)
            listbox.pack(fill="x", padx=6, pady=(4, 0))
            listbox.bind(
                "<Double-Button-1>",
                lambda _event, et=entity_type, lb=listbox: self._handle_entity_select(et, lb),
            )

    def _normalize_list(self, value: Optional[Iterable[str]]) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            split_items = [item.strip() for item in value.split(",")]
            return [item for item in split_items if item]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _handle_scene_select(self, listbox: tk.Listbox):
        if not self._on_scene_selected:
            return
        selection = listbox.curselection()
        if not selection:
            return
        scene_name = listbox.get(selection[0])
        if scene_name:
            self._on_scene_selected(scene_name)

    def _handle_entity_select(self, entity_type: str, listbox: tk.Listbox):
        selection = listbox.curselection()
        if not selection:
            return
        name = listbox.get(selection[0])
        if name:
            self._open_entity_callback(entity_type, name)


log_module_import(__name__)
