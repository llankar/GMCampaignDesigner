from datetime import date

import customtkinter as ctk


class EventEditorDialog(ctk.CTkToplevel):
    """Full editor for calendar events."""

    def __init__(self, master, *, initial_values=None, on_save=None):
        super().__init__(master)
        self.title("Éditeur d'évènement")
        self.geometry("520x420")
        self.resizable(False, False)

        self._on_save = on_save
        self._initial = dict(initial_values or {})

        self._build_ui()
        self._populate_fields()

        self.transient(master)
        self.grab_set()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)

        row = 0
        ctk.CTkLabel(self, text="Titre").grid(row=row, column=0, padx=12, pady=(16, 8), sticky="w")
        self.title_entry = ctk.CTkEntry(self, placeholder_text="Titre de l'évènement")
        self.title_entry.grid(row=row, column=1, padx=12, pady=(16, 8), sticky="ew")

        row += 1
        ctk.CTkLabel(self, text="Date").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.date_entry = ctk.CTkEntry(self, placeholder_text="YYYY-MM-DD")
        self.date_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(self, text="Heure début").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.start_entry = ctk.CTkEntry(self, placeholder_text="HH:MM")
        self.start_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(self, text="Heure fin").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.end_entry = ctk.CTkEntry(self, placeholder_text="HH:MM")
        self.end_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(self, text="Type").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.type_entry = ctk.CTkEntry(self, placeholder_text="Session / Rencontre / Quête...")
        self.type_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(self, text="Statut").grid(row=row, column=0, padx=12, pady=8, sticky="w")
        self.status_entry = ctk.CTkEntry(self, placeholder_text="Planifié / Confirmé / Terminé...")
        self.status_entry.grid(row=row, column=1, padx=12, pady=8, sticky="ew")

        row += 1
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=row, column=0, columnspan=2, padx=12, pady=(18, 12), sticky="e")
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
        self.type_entry.insert(0, self._initial.get("type", ""))
        self.status_entry.insert(0, self._initial.get("status", ""))

    def _save(self):
        payload = {
            "title": self.title_entry.get().strip(),
            "date": self.date_entry.get().strip(),
            "start_time": self.start_entry.get().strip(),
            "end_time": self.end_entry.get().strip(),
            "type": self.type_entry.get().strip(),
            "status": self.status_entry.get().strip(),
        }
        if callable(self._on_save):
            self._on_save(payload)
        self.destroy()
