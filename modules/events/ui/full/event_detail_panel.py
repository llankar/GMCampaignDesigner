from datetime import date

import customtkinter as ctk

from modules.events.models.event_types import get_event_type


class EventDetailPanel(ctk.CTkFrame):
    """Selected-day details with compact mode and quick edit callback."""

    LINKED_TYPES = ("Places", "NPCs", "Villains", "Creatures", "Objects", "Factions", "Bases", "Maps", "Clues", "Scenarios", "Informations")

    def __init__(self, master, *, on_compact_toggle, on_quick_edit, on_open_entity=None, on_event_click=None):
        super().__init__(master)
        self._on_compact_toggle = on_compact_toggle
        self._on_quick_edit = on_quick_edit
        self._on_open_entity = on_open_entity
        self._on_event_click = on_event_click
        self._is_compact = False
        self._events = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.selection_label = ctk.CTkLabel(self, text="", anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        self.selection_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))

        self.compact_toggle = ctk.CTkSwitch(self, text="Mode compact", command=self._toggle_compact)
        self.compact_toggle.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))

        self.events_frame = ctk.CTkScrollableFrame(self)
        self.events_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))

        self.editor_frame = ctk.CTkFrame(self)
        self.editor_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.editor_frame.grid_columnconfigure(0, weight=1)

        self.quick_title_entry = ctk.CTkEntry(self.editor_frame, placeholder_text="Titre (édition rapide)")
        self.quick_title_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(self.editor_frame, text="Enregistrer", width=110, command=self._emit_quick_edit).grid(row=0, column=1, sticky="e")

    def set_compact_mode(self, compact):
        self._is_compact = bool(compact)
        if self._is_compact:
            self.events_frame.grid_remove()
            self.editor_frame.grid_remove()
            self.compact_toggle.select()
        else:
            self.events_frame.grid()
            self.editor_frame.grid()
            self.compact_toggle.deselect()

    def render(self, *, active_date, events, show_source=True):
        self._events = list(events)
        self.selection_label.configure(text=f"Jour sélectionné : {active_date.strftime('%A %d/%m/%Y').capitalize()}")
        self._render_events(show_source=show_source)

    def _render_events(self, *, show_source):
        for child in self.events_frame.winfo_children():
            child.destroy()

        if not self._events:
            ctk.CTkLabel(self.events_frame, text="Aucun évènement.").pack(anchor="w", padx=4, pady=4)
            return

        for event in self._events:
            title = event.get("title", "Sans titre")
            source = event.get("source")
            details = []
            if event.get("time"):
                details.append(str(event.get("time")))
            if event.get("type"):
                details.append(str(event.get("type")))
            if event.get("status"):
                details.append(str(event.get("status")))
            details.append(self._badge_text(event))

            suffix = f" — {' / '.join(details)}" if details else ""
            text = f"• {title}{suffix}"
            if source and show_source:
                text = f"{text} ({source})"

            event_block = ctk.CTkFrame(self.events_frame)
            event_block.pack(fill="x", pady=(0, 6), padx=2)
            event_type = get_event_type(event.get("type"))
            title_label = ctk.CTkLabel(
                event_block,
                text=text,
                anchor="w",
                justify="left",
                text_color=event.get("color") or event_type.color,
                cursor="hand2",
            )
            title_label.pack(anchor="w", padx=8, pady=(6, 2))
            title_label.bind("<Button-1>", lambda _e, current_event=event: self._emit_event_click(current_event))

            links_added = False
            for linked_type in self.LINKED_TYPES:
                linked_items = event.get(linked_type) or []
                for linked_name in linked_items:
                    links_added = True
                    label = ctk.CTkLabel(event_block, text=f"↳ {linked_type[:-1]}: {linked_name}", text_color="#4da3ff", cursor="hand2", anchor="w")
                    label.pack(anchor="w", padx=18, pady=(0, 2))
                    label.bind("<Button-1>", lambda _e, t=linked_type, n=linked_name: self._open_link(t, n))

            if not links_added:
                ctk.CTkLabel(event_block, text="↳ Aucun lien", anchor="w", text_color="gray").pack(anchor="w", padx=18, pady=(0, 4))

    @staticmethod
    def _badge_text(event):
        event_date = event.get("date")
        if event_date is None:
            return "à venir"
        today = date.today()
        if event_date < today:
            return "en retard"
        if event_date == today:
            return "aujourd'hui"
        return "à venir"

    def _open_link(self, entity_type, entity_name):
        if callable(self._on_open_entity):
            self._on_open_entity(entity_type, entity_name)

    def _emit_event_click(self, event):
        if callable(self._on_event_click):
            self._on_event_click(event)

    def _toggle_compact(self):
        self.set_compact_mode(bool(self.compact_toggle.get()))
        if callable(self._on_compact_toggle):
            self._on_compact_toggle(self._is_compact)

    def _emit_quick_edit(self):
        new_title = self.quick_title_entry.get().strip()
        if not new_title or not self._events:
            return

        first_event = self._events[0]
        if callable(self._on_quick_edit):
            self._on_quick_edit(first_event, new_title)
