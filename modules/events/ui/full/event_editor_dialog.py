from datetime import date

import customtkinter as ctk

from modules.events.services.entity_link_service import EntityLinkService
from modules.events.models.event_types import event_type_labels
from modules.events.ui.shared.multi_link_selector import MultiLinkSelector


class EventEditorDialog(ctk.CTkToplevel):
    """Full editor for calendar events."""

    def __init__(self, master, *, initial_values=None, on_save=None, entity_link_service=None):
        super().__init__(master)
        self.title("Éditeur d'évènement")
        self.geometry("560x700")
        self.resizable(True, True)

        self._on_save = on_save
        self._initial = dict(initial_values or {})
        self._entity_link_service = entity_link_service or EntityLinkService()

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
        ctk.CTkLabel(content, text="Titre").grid(row=row, column=0, padx=12, pady=(16, 8), sticky="w")
        self.title_entry = ctk.CTkEntry(content, placeholder_text="Titre de l'évènement")
        self.title_entry.grid(row=row, column=1, padx=12, pady=(16, 8), sticky="ew")

        row += 1
        ctk.CTkLabel(content, text="Date").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.date_entry = ctk.CTkEntry(content, placeholder_text="YYYY-MM-DD")
        self.date_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(content, text="Heure début").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.start_entry = ctk.CTkEntry(content, placeholder_text="HH:MM")
        self.start_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(content, text="Heure fin").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.end_entry = ctk.CTkEntry(content, placeholder_text="HH:MM")
        self.end_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(content, text="Type").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.type_entry = ctk.CTkEntry(content, placeholder_text="Session / Rencontre / Quête...")
        self.type_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(content, text="Statut").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.status_entry = ctk.CTkEntry(content, placeholder_text="Planifié / Confirmé / Terminé...")
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
        self.scenario_selector = MultiLinkSelector(
            content,
            label="Scenarios",
            load_options=lambda query: self._entity_link_service.search_entities("Scenarios", query),
        )
        self.scenario_selector.grid(row=row, column=0, columnspan=2, padx=12, pady=4, sticky="ew")

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
        ctk.CTkButton(buttons, text="Annuler", fg_color="transparent", command=self.destroy).pack(side="right", padx=(6, 0))
        ctk.CTkButton(buttons, text="Créer", command=self._save).pack(side="right")

    def _populate_fields(self):
        self.title_entry.insert(0, self._initial.get("title", ""))

        current_date = self._initial.get("date") or date.today()
        if isinstance(current_date, date):
            self.date_entry.insert(0, current_date.isoformat())
        elif current_date:
            self.date_entry.insert(0, str(current_date))

        self.start_entry.insert(0, self._initial.get("start_time", ""))
        self.end_entry.insert(0, self._initial.get("end_time", ""))
        initial_type = self._initial.get("type", "Session") or "Session"
        self.type_menu.set(initial_type)
        self.status_entry.insert(0, self._initial.get("status", ""))
        self.place_selector.set_values(self._initial.get("Places") or [])
        self.npc_selector.set_values(self._initial.get("NPCs") or [])
        self.scenario_selector.set_values(self._initial.get("Scenarios") or [])
        self.information_selector.set_values(self._initial.get("Informations") or [])

    def _save(self):
        payload = {
            "title": self.title_entry.get().strip(),
            "date": self.date_entry.get().strip(),
            "start_time": self.start_entry.get().strip(),
            "end_time": self.end_entry.get().strip(),
            "type": self.type_menu.get().strip(),
            "status": self.status_entry.get().strip(),
            "Places": self.place_selector.get_values(),
            "NPCs": self.npc_selector.get_values(),
            "Scenarios": self.scenario_selector.get_values(),
            "Informations": self.information_selector.get_values(),
        }
        if callable(self._on_save):
            self._on_save(payload)
        self.destroy()
