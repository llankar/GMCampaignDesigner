from tkinter import font as tkfont

import customtkinter as ctk

from modules.generic.detail_ui import get_detail_palette


class VerticalSectionTabs(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        sections,
        show_section,
        on_pin_toggle=None,
        on_right_click=None,
        **kwargs,
    ):
        palette = get_detail_palette()
        kwargs.setdefault("fg_color", palette["surface_card"])
        kwargs.setdefault("corner_radius", 18)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", palette["muted_border"])
        super().__init__(parent, **kwargs)
        self._palette = palette
        self._show_section = show_section
        self._on_pin_toggle_callback = on_pin_toggle
        self._on_right_click_callback = on_right_click
        self._buttons = {}
        self._button_labels = {}
        self._active_section = None
        self._font_normal = ctk.CTkFont(size=13, weight="normal")
        self._font_bold = ctk.CTkFont(size=13, weight="bold")

        header = ctk.CTkFrame(
            self,
            fg_color=palette["surface_overlay"],
            corner_radius=16,
            border_width=1,
            border_color=palette["pill_border"],
        )
        header.pack(fill="x", padx=12, pady=(12, 10))

        eyebrow = ctk.CTkFrame(header, fg_color="transparent")
        eyebrow.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            eyebrow,
            text="GM NAVIGATION",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=palette["muted_text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Sections",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=palette["text"],
        ).pack(anchor="w", padx=14)
        right_click_hint = (
            "Click to focus · right-click for actions · Shift+right-click to pin"
            if callable(on_right_click)
            else "Click to focus · right-click to pin"
        )
        ctk.CTkLabel(
            header,
            text=right_click_hint,
            font=ctk.CTkFont(size=11),
            text_color=palette["muted_text"],
        ).pack(anchor="w", padx=14, pady=(4, 12))

        self._button_container = ctk.CTkFrame(self, fg_color="transparent")
        self._button_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._inactive_border_color = palette["surface_card"]

        for section in sections:
            button = ctk.CTkButton(
                self._button_container,
                text=section,
                anchor="w",
                font=self._font_normal,
                fg_color=palette["surface_elevated"],
                hover_color=palette["surface_overlay"],
                text_color=palette["muted_text"],
                corner_radius=16,
                height=42,
                border_width=1,
                border_color=self._inactive_border_color,
                command=lambda name=section: self._on_select(name),
            )
            button.bind("<Button-3>", lambda event, name=section: self._on_right_click(event, name))
            button.bind("<Control-Button-1>", lambda event, name=section: self._on_right_click(event, name))
            button.pack(fill="x", padx=6, pady=4)
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
        button.configure(width=max(156, text_width + 44))

    def _on_pin_toggle(self, section_name):
        if self._on_pin_toggle_callback is not None:
            self._on_pin_toggle_callback(section_name)

    def _on_right_click(self, event, section_name):
        try:
            if int(getattr(event, "state", 0)) & 0x0001:
                self._on_pin_toggle(section_name)
                return
        except Exception:
            pass
        if callable(self._on_right_click_callback):
            self._on_right_click_callback(event)
            return
        self._on_pin_toggle(section_name)

    def _on_select(self, section_name):
        self.set_active(section_name)
        if self._show_section is not None:
            self._show_section(section_name)

    def set_active(self, section_name):
        self._active_section = section_name
        for name, button in self._buttons.items():
            is_active = name == section_name
            button.configure(
                font=self._font_bold if is_active else self._font_normal,
                fg_color=self._palette["surface_overlay"] if is_active else self._palette["surface_elevated"],
                border_color=self._palette["pill_border"] if is_active else self._inactive_border_color,
                text_color=self._palette["text"] if is_active else self._palette["muted_text"],
            )
            self._resize_button(name)

    def set_pinned(self, pinned_sections):
        for name in self._buttons:
            label = name
            if name in pinned_sections:
                label = f"📌 {label}"
            self._button_labels[name] = label
            self._buttons[name].configure(text=label)
            self._resize_button(name)
