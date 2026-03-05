import customtkinter as ctk


class EventDetailPanel(ctk.CTkFrame):
    """Selected-day details with compact mode and quick edit callback."""

    def __init__(self, master, *, on_compact_toggle, on_quick_edit):
        super().__init__(master)
        self._on_compact_toggle = on_compact_toggle
        self._on_quick_edit = on_quick_edit
        self._is_compact = False
        self._events = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.selection_label = ctk.CTkLabel(self, text="", anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        self.selection_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))

        self.compact_toggle = ctk.CTkSwitch(self, text="Mode compact", command=self._toggle_compact)
        self.compact_toggle.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))

        self.events_text = ctk.CTkTextbox(self)
        self.events_text.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.events_text.configure(state="disabled")

        self.editor_frame = ctk.CTkFrame(self)
        self.editor_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.editor_frame.grid_columnconfigure(0, weight=1)

        self.quick_title_entry = ctk.CTkEntry(self.editor_frame, placeholder_text="Titre (édition rapide)")
        self.quick_title_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(self.editor_frame, text="Enregistrer", width=110, command=self._emit_quick_edit).grid(
            row=0,
            column=1,
            sticky="e",
        )

    def set_compact_mode(self, compact):
        self._is_compact = bool(compact)
        if self._is_compact:
            self.events_text.grid_remove()
            self.editor_frame.grid_remove()
            self.compact_toggle.select()
        else:
            self.events_text.grid()
            self.editor_frame.grid()
            self.compact_toggle.deselect()

    def render(self, *, active_date, events, show_source=True):
        self._events = list(events)
        self.selection_label.configure(text=f"Jour sélectionné : {active_date.strftime('%A %d/%m/%Y').capitalize()}")
        lines = self._format_event_lines(self._events, show_source=show_source)
        self._set_textbox_lines(lines)

    @staticmethod
    def _format_event_lines(events, *, show_source):
        if not events:
            return ["Aucun évènement."]

        lines = []
        for event in events:
            title = event.get("title", "Sans titre")
            source = event.get("source")
            if source and show_source:
                lines.append(f"• {title} ({source})")
            else:
                lines.append(f"• {title}")
        return lines

    def _set_textbox_lines(self, lines):
        self.events_text.configure(state="normal")
        self.events_text.delete("1.0", "end")
        self.events_text.insert("1.0", "\n".join(lines))
        self.events_text.configure(state="disabled")

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
