from datetime import date
from tkinter import colorchooser

import customtkinter as ctk

from modules.events.services.entity_link_service import EntityLinkService
from modules.events.models.event_types import event_type_labels
from modules.events.ui.shared.color_utils import normalize_hex_color
from modules.events.ui.shared.multi_link_selector import MultiLinkSelector
from modules.events.ui.shared.schedule_widgets import EventDatePickerField, EventTimePickerField


class EventEditorDialog(ctk.CTkToplevel):
    """Full editor for calendar events."""

    def __init__(self, master, *, initial_values=None, on_save=None, entity_link_service=None, save_label="Create"):
        super().__init__(master)
        self.title("Event editor")
        self.geometry("560x700")
        self.resizable(True, True)

        self._on_save = on_save
        self._initial = dict(initial_values or {})
        self._entity_link_service = entity_link_service or EntityLinkService()
        self._save_label = str(save_label or "Create")

        self._build_ui()
        self._populate_fields()

        self.transient(master)
        self.grab_set()

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        content = ctk.CTkScrollableFrame(self)
        content.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        content.grid_columnconfigure(1, weight=1)

        row = 0
        ctk.CTkLabel(content, text="Title").grid(row=row, column=0, padx=12, pady=(16, 8), sticky="w")
        self.title_entry = ctk.CTkEntry(content, placeholder_text="Event title")
        self.title_entry.grid(row=row, column=1, padx=12, pady=(16, 8), sticky="ew")

        row += 1
        ctk.CTkLabel(content, text="Date").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.date_entry = EventDatePickerField(
            content,
            picker_button_text="Calendar",
            today_button_text="Today",
            clear_button_text="Clear",
            empty_hint_text="No date selected",
        )
        self.date_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(content, text="Start time").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.start_entry = EventTimePickerField(
            content,
            picker_button_text="Pick",
            now_button_text="Now",
            clear_button_text="Clear",
            empty_hint_text="No time selected",
        )
        self.start_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(content, text="End time").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.end_entry = EventTimePickerField(
            content,
            picker_button_text="Pick",
            now_button_text="Now",
            clear_button_text="Clear",
            empty_hint_text="No time selected",
        )
        self.end_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(content, text="Type").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.type_menu = ctk.CTkOptionMenu(content, values=event_type_labels())
        self.type_menu.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(content, text="Color").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.color_button = ctk.CTkButton(content, text="", width=120, command=self._choose_color)
        self.color_button.grid(row=row, column=1, padx=12, pady=8, sticky="w")
        self._selected_color = "#4F8EF7"

        row += 1
        ctk.CTkLabel(content, text="Status").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.status_entry = ctk.CTkEntry(content, placeholder_text="Planned / Confirmed / Completed...")
        self.status_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        self.place_selector = MultiLinkSelector(
            content,
            label="Places",
            load_options=lambda query: self._entity_link_service.search_entities("Places", query),
        )
        self.place_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=(8, 4), sticky="ew")

        row += 1
        self.npc_selector = MultiLinkSelector(
            content,
            label="NPCs",
            load_options=lambda query: self._entity_link_service.search_entities("NPCs", query),
        )
        self.npc_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        row += 1
        self.villain_selector = MultiLinkSelector(
            content,
            label="Villains",
            load_options=lambda query: self._entity_link_service.search_entities("Villains", query),
        )
        self.villain_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        row += 1
        self.scenario_selector = MultiLinkSelector(
            content,
            label="Scenarios",
            load_options=lambda query: self._entity_link_service.search_entities("Scenarios", query),
        )
        self.scenario_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        row += 1
        self.creature_selector = MultiLinkSelector(
            content,
            label="Creatures",
            load_options=lambda query: self._entity_link_service.search_entities("Creatures", query),
        )
        self.creature_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        row += 1
        self.object_selector = MultiLinkSelector(
            content,
            label="Objects",
            load_options=lambda query: self._entity_link_service.search_entities("Objects", query),
        )
        self.object_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        row += 1
        self.faction_selector = MultiLinkSelector(
            content,
            label="Factions",
            load_options=lambda query: self._entity_link_service.search_entities("Factions", query),
        )
        self.faction_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        row += 1
        self.base_selector = MultiLinkSelector(
            content,
            label="Bases",
            load_options=lambda query: self._entity_link_service.search_entities("Bases", query),
        )
        self.base_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        row += 1
        self.map_selector = MultiLinkSelector(
            content,
            label="Maps",
            load_options=lambda query: self._entity_link_service.search_entities("Maps", query),
        )
        self.map_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        row += 1
        self.clue_selector = MultiLinkSelector(
            content,
            label="Clues",
            load_options=lambda query: self._entity_link_service.search_entities("Clues", query),
        )
        self.clue_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        row += 1
        self.information_selector = MultiLinkSelector(
            content,
            label="Informations",
            load_options=lambda query: self._entity_link_service.search_entities("Informations", query),
        )
        self.information_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

        row += 1
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=1, column=0, padx=12, pady=(8, 12), sticky="ew")
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(buttons, text="Cancel", fg_color="transparent", command=self.destroy).pack(side="right", padx=(6, 0))
        ctk.CTkButton(buttons, text=self._save_label, command=self._save).pack(side="right")

    def _populate_fields(self):
        self.title_entry.insert(0, self._initial.get("title", ""))

        current_date = self._initial.get("date") or date.today()
        self.date_entry.set(current_date)

        self.start_entry.set(self._initial.get("start_time", ""))
        self.end_entry.set(self._initial.get("end_time", ""))
        initial_type = self._initial.get("type", "Session") or "Session"
        self.type_menu.set(initial_type)
        self._selected_color = normalize_hex_color(self._initial.get("color"), fallback="#4F8EF7")
        self._update_color_button()
        self.status_entry.insert(0, self._initial.get("status", ""))
        self.place_selector.set_values(self._initial.get("Places") or [])
        self.npc_selector.set_values(self._initial.get("NPCs") or [])
        self.villain_selector.set_values(self._initial.get("Villains") or [])
        self.scenario_selector.set_values(self._initial.get("Scenarios") or [])
        self.creature_selector.set_values(self._initial.get("Creatures") or [])
        self.object_selector.set_values(self._initial.get("Objects") or [])
        self.faction_selector.set_values(self._initial.get("Factions") or [])
        self.base_selector.set_values(self._initial.get("Bases") or [])
        self.map_selector.set_values(self._initial.get("Maps") or [])
        self.clue_selector.set_values(self._initial.get("Clues") or [])
        self.information_selector.set_values(self._initial.get("Informations") or [])

    def _save(self):
        payload = {
            "title": self.title_entry.get().strip(),
            "date": self.date_entry.get().strip(),
            "start_time": self.start_entry.get().strip(),
            "end_time": self.end_entry.get().strip(),
            "type": self.type_menu.get().strip(),
            "color": self._selected_color,
            "status": self.status_entry.get().strip(),
            "Places": self.place_selector.get_values(),
            "NPCs": self.npc_selector.get_values(),
            "Villains": self.villain_selector.get_values(),
            "Scenarios": self.scenario_selector.get_values(),
            "Creatures": self.creature_selector.get_values(),
            "Objects": self.object_selector.get_values(),
            "Factions": self.faction_selector.get_values(),
            "Bases": self.base_selector.get_values(),
            "Maps": self.map_selector.get_values(),
            "Clues": self.clue_selector.get_values(),
            "Informations": self.information_selector.get_values(),
        }
        if callable(self._on_save):
            self._on_save(payload)
        self.destroy()

    def _choose_color(self):
        current = normalize_hex_color(self._selected_color, fallback="#4F8EF7")
        selection = colorchooser.askcolor(color=current, parent=self)
        color = None
        if isinstance(selection, (tuple, list)) and len(selection) > 1:
            color = selection[1]
        self._selected_color = normalize_hex_color(color, fallback=current)
        self._update_color_button()

    def _update_color_button(self):
        self.color_button.configure(
            text=self._selected_color,
            fg_color=self._selected_color,
            hover_color=self._selected_color,
            text_color="#FFFFFF",
        )
