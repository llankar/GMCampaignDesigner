import customtkinter as ctk


class VerticalSectionTabs(ctk.CTkFrame):
    def __init__(self, parent, sections, show_section, **kwargs):
        super().__init__(parent, **kwargs)
        self._show_section = show_section
        self._buttons = {}
        self._active_section = None

        for section in sections:
            button = ctk.CTkButton(
                self,
                text=section,
                anchor="w",
                command=lambda name=section: self._on_select(name),
            )
            button.pack(fill="x", padx=6, pady=4)
            self._buttons[section] = button

    def _on_select(self, section_name):
        self.set_active(section_name)
        if self._show_section is not None:
            self._show_section(section_name)

    def set_active(self, section_name):
        self._active_section = section_name
        for name, button in self._buttons.items():
            font_weight = "bold" if name == section_name else "normal"
            button.configure(font=("Arial", 13, font_weight))
