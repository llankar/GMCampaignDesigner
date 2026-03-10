import customtkinter as ctk

from modules.generic.generic_model_wrapper import GenericModelWrapper


class RelatedEventsPanel(ctk.CTkFrame):
    """Reusable panel listing calendar events linked to an entity."""

    def __init__(self, master, *, entity_type, entity_name, on_open_entity=None):
        super().__init__(master)
        self._on_open_entity = on_open_entity

        ctk.CTkLabel(self, text="Évènements liés", font=("Arial", 16, "bold")).pack(anchor="w", padx=8, pady=(6, 2))

        self.body = ctk.CTkFrame(self)
        self.body.pack(fill="x", padx=8, pady=(0, 6))

        events = self._collect_related_events(entity_type, entity_name)
        if not events:
            ctk.CTkLabel(self.body, text="Aucun évènement lié.", text_color="gray").pack(anchor="w", pady=(2, 6))
            return

        for event in events:
            text = f"• {event.get('title')} — {event.get('date')}"
            ctk.CTkLabel(self.body, text=text, anchor="w").pack(anchor="w", pady=(1, 1))

    @staticmethod
    def _collect_related_events(entity_type, entity_name):
        key = str(entity_name or "").strip()
        if not key:
            return []

        field_map = {
            "Places": "Places",
            "NPCs": "NPCs",
            "Villains": "Villains",
            "Scenarios": "Scenarios",
            "Informations": "Informations",
            "Factions": "Factions",
            "Bases": "Bases",
            "Maps": "Maps",
            "Clues": "Clues",
        }
        linked_field = field_map.get(entity_type)
        if not linked_field:
            return []

        wrappers = [GenericModelWrapper("events"), GenericModelWrapper("scenarios")]
        found = []
        seen = set()

        for wrapper in wrappers:
            try:
                items = wrapper.load_items()
            except Exception:
                continue
            for item in items:
                links = item.get(linked_field) or []
                if key not in links:
                    continue
                title = item.get("Title") or item.get("Name") or "Sans titre"
                date_value = item.get("Date") or item.get("date") or "Date inconnue"
                identity = (title, str(date_value))
                if identity in seen:
                    continue
                seen.add(identity)
                found.append({"title": title, "date": str(date_value)})

        found.sort(key=lambda row: (row["date"], row["title"].lower()))
        return found
