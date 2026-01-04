from tkinter import font as tkfont

import customtkinter as ctk


class VerticalSectionTabs(ctk.CTkFrame):
    def __init__(self, parent, sections, show_section, on_pin_toggle=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._show_section = show_section
        self._on_pin_toggle_callback = on_pin_toggle
        self._buttons = {}
        self._button_labels = {}
        self._active_section = None
        self._font_normal = ctk.CTkFont(size=13, weight="normal")
        self._font_bold = ctk.CTkFont(size=13, weight="bold")

        for section in sections:
            button = ctk.CTkButton(
                self,
                text=section,
                anchor="w",
                font=self._font_normal,
                command=lambda name=section: self._on_select(name),
            )
            button.bind("<Button-3>", lambda event, name=section: self._on_pin_toggle(name))
            button.pack(anchor="w", padx=6, pady=4)
            self._buttons[section] = button
            self._button_labels[section] = section
            self._resize_button(section)

    def _measure_text(self, text, font):
        return tkfont.Font(font=font).measure(text)

    def _resize_button(self, section_name):
        button = self._buttons.get(section_name)
        if button is None:
            return
        label = self._button_labels.get(section_name, section_name)
        font = self._font_bold if section_name == self._active_section else self._font_normal
        text_width = self._measure_text(label, font)
        button.configure(width=text_width + 24)

    def _on_pin_toggle(self, section_name):
        if self._on_pin_toggle_callback is not None:
            self._on_pin_toggle_callback(section_name)

    def _on_select(self, section_name):
        self.set_active(section_name)
        if self._show_section is not None:
            self._show_section(section_name)

    def set_active(self, section_name):
        self._active_section = section_name
        for name, button in self._buttons.items():
            is_active = name == section_name
            button.configure(font=self._font_bold if is_active else self._font_normal)
            self._resize_button(name)

    def set_pinned(self, pinned_sections):
        for name in self._buttons:
            label = name
            if name in pinned_sections:
                label = f"📌 {label}"
            self._button_labels[name] = label
            self._buttons[name].configure(text=label)
            self._resize_button(name)
