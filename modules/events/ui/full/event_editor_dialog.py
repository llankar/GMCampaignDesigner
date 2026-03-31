"""Dialog for event editor."""

from __future__ import annotations

from datetime import date
from tkinter import colorchooser

import customtkinter as ctk

from modules.events.models.event_types import get_event_type, event_type_labels
from modules.events.services.entity_link_service import EntityLinkService
from modules.events.ui.full.event_editor import (
    EVENT_EDITOR_PALETTE,
    EVENT_LINK_GROUPS,
    EventEditorHero,
    EventEditorSection,
)
from modules.events.ui.shared.color_utils import normalize_hex_color
from modules.events.ui.shared.multi_link_selector import MultiLinkSelector
from modules.events.ui.shared.schedule_widgets import EventDatePickerField, EventTimePickerField


class EventEditorDialog(ctk.CTkToplevel):
    """Full editor for calendar events with themed sections and a live preview."""

    STATUS_OPTIONS = ["Planned", "Confirmed", "Completed", "Canceled"]

    def __init__(self, master, *, initial_values=None, on_save=None, entity_link_service=None, save_label="Create"):
        """Initialize the EventEditorDialog instance."""
        super().__init__(master)
        self.title("Event editor")
        self.geometry("960x820")
        self.minsize(860, 720)
        self.resizable(True, True)
        self.configure(fg_color=EVENT_EDITOR_PALETTE.window_bg)

        self._on_save = on_save
        self._initial = dict(initial_values or {})
        self._entity_link_service = entity_link_service or EntityLinkService()
        self._save_label = str(save_label or "Create")
        self._selected_color = "#4F8EF7"
        self._color_locked = False
        self._status_buttons = {}
        self._link_selectors = {}

        self._build_ui()
        self._populate_fields()
        self._bind_live_updates()
        self._refresh_summary_preview()

        self.transient(master)
        self.grab_set()

    def _build_ui(self):
        """Build UI."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.grid(row=0, column=0, padx=18, pady=(18, 10), sticky="nsew")
        content.grid_columnconfigure(0, weight=1)

        self.hero = EventEditorHero(content)
        self.hero.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        self.identity_section = EventEditorSection(
            content,
            title="Identity",
            description="Give the event a clear title, category, and status so it stands out instantly in the calendar.",
        )
        self.identity_section.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self._build_identity_section(self.identity_section.content)

        self.schedule_section = EventEditorSection(
            content,
            title="Schedule",
            description="Set the campaign date and a time window. Empty time fields keep the event flexible.",
        )
        self.schedule_section.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        self._build_schedule_section(self.schedule_section.content)

        self.appearance_section = EventEditorSection(
            content,
            title="Appearance",
            description="Pick a color that fits the active app theme while still making this event easy to scan.",
        )
        self.appearance_section.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        self._build_appearance_section(self.appearance_section.content)

        self.links_section = EventEditorSection(
            content,
            title="Campaign links",
            description="Attach related entities so the event becomes a useful campaign hub instead of a simple reminder.",
        )
        self.links_section.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        self._build_links_section(self.links_section.content)

        self._build_footer()

    def _build_identity_section(self, container):
        """Build identity section."""
        for column in range(2):
            container.grid_columnconfigure(column, weight=1)

        title_block = self._create_field_block(container, "Title", "A strong title makes the event readable at a glance.")
        title_block.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        self.title_entry = ctk.CTkEntry(
            title_block,
            placeholder_text="Ex: The gala infiltration",
            height=40,
            fg_color=EVENT_EDITOR_PALETTE.input_bg,
            border_color=EVENT_EDITOR_PALETTE.input_border,
            text_color=EVENT_EDITOR_PALETTE.text_primary,
        )
        self.title_entry.grid(row=2, column=0, sticky="ew")

        type_block = self._create_field_block(container, "Type", "Choose the event family to help visual categorization.")
        type_block.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.type_menu = ctk.CTkOptionMenu(
            type_block,
            values=event_type_labels(),
            height=40,
            fg_color=EVENT_EDITOR_PALETTE.accent,
            button_color=EVENT_EDITOR_PALETTE.accent,
            button_hover_color=EVENT_EDITOR_PALETTE.accent_hover,
        )
        self.type_menu.grid(row=2, column=0, sticky="ew")

        status_block = self._create_field_block(container, "Status", "Use a quick status so the team understands progress instantly.")
        status_block.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        status_row = ctk.CTkFrame(status_block, fg_color="transparent")
        status_row.grid(row=2, column=0, sticky="ew")
        for index, status in enumerate(self.STATUS_OPTIONS):
            # Process each (index, status) from enumerate(STATUS_OPTIONS).
            button = ctk.CTkButton(
                status_row,
                text=status,
                width=0,
                height=34,
                corner_radius=999,
                fg_color=EVENT_EDITOR_PALETTE.muted_chip,
                hover_color=EVENT_EDITOR_PALETTE.panel_alt_bg,
                text_color=EVENT_EDITOR_PALETTE.text_primary,
                command=lambda value=status: self._set_status(value),
            )
            button.grid(row=0, column=index, padx=(0, 8 if index < len(self.STATUS_OPTIONS) - 1 else 0), sticky="ew")
            status_row.grid_columnconfigure(index, weight=1)
            self._status_buttons[status] = button

        self.status_entry = ctk.CTkEntry(
            status_block,
            placeholder_text="Or type a custom status",
            height=38,
            fg_color=EVENT_EDITOR_PALETTE.input_bg,
            border_color=EVENT_EDITOR_PALETTE.input_border,
            text_color=EVENT_EDITOR_PALETTE.text_primary,
        )
        self.status_entry.grid(row=3, column=0, sticky="ew", pady=(10, 0))

    def _build_schedule_section(self, container):
        """Build schedule section."""
        for column in range(3):
            container.grid_columnconfigure(column, weight=1)

        date_block = self._create_field_block(container, "Date", "Anchor the event to the campaign timeline.")
        date_block.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.date_entry = EventDatePickerField(
            date_block,
            picker_button_text="Calendar",
            today_button_text="Today",
            clear_button_text="Clear",
            empty_hint_text="No date selected",
        )
        self.date_entry.grid(row=2, column=0, sticky="ew")

        start_block = self._create_field_block(container, "Start time", "Optional. Leave empty for an all-day beat.")
        start_block.grid(row=0, column=1, sticky="ew", padx=8)
        self.start_entry = EventTimePickerField(
            start_block,
            picker_button_text="Pick",
            now_button_text="Now",
            clear_button_text="Clear",
            empty_hint_text="No time selected",
        )
        self.start_entry.grid(row=2, column=0, sticky="ew")

        end_block = self._create_field_block(container, "End time", "Optional. Helps communicate duration and overlap.")
        end_block.grid(row=0, column=2, sticky="ew", padx=(8, 0))
        self.end_entry = EventTimePickerField(
            end_block,
            picker_button_text="Pick",
            now_button_text="Now",
            clear_button_text="Clear",
            empty_hint_text="No time selected",
        )
        self.end_entry.grid(row=2, column=0, sticky="ew")

    def _build_appearance_section(self, container):
        """Build appearance section."""
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=0)

        description = ctk.CTkLabel(
            container,
            text="The color preview updates live and inherits the active app palette, so the editor feels native in every theme.",
            text_color=EVENT_EDITOR_PALETTE.text_secondary,
            justify="left",
            wraplength=520,
        )
        description.grid(row=0, column=0, sticky="w")

        self.color_button = ctk.CTkButton(
            container,
            text="",
            width=150,
            height=42,
            corner_radius=14,
            command=self._choose_color,
        )
        self.color_button.grid(row=0, column=1, rowspan=2, padx=(18, 0), sticky="e")

        chip_row = ctk.CTkFrame(container, fg_color="transparent")
        chip_row.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self._color_presets = []
        for index, label in enumerate(event_type_labels()):
            # Process each (index, label) from enumerate(event_type_labels()).
            event_type = get_event_type(label)
            chip = ctk.CTkButton(
                chip_row,
                text=label,
                width=0,
                height=34,
                corner_radius=999,
                fg_color=EVENT_EDITOR_PALETTE.muted_chip,
                hover_color=event_type.color,
                text_color=EVENT_EDITOR_PALETTE.text_primary,
                command=lambda value=event_type.color: self._apply_color(value, lock=True),
            )
            chip.grid(row=0, column=index, padx=(0, 8), pady=(0, 4), sticky="ew")
            chip_row.grid_columnconfigure(index, weight=1)
            self._color_presets.append(chip)

    def _build_links_section(self, container):
        """Build links section."""
        for column in range(2):
            container.grid_columnconfigure(column, weight=1)
        for index, (field_name, label) in enumerate(EVENT_LINK_GROUPS):
            # Process each (index, (field_name, label)) from enumerate(EVENT_LINK_GROUPS).
            selector = MultiLinkSelector(
                container,
                label=label,
                load_options=lambda query, group=field_name: self._entity_link_service.search_entities(group, query),
                helper_text=f"Search and attach {label.lower()} relevant to this event.",
            )
            selector.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=(0, 10) if index % 2 == 0 else (10, 0),
                pady=10,
            )
            self._link_selectors[field_name] = selector

    def _build_footer(self):
        """Build footer."""
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            footer,
            text="Tip: pick a type first, then adjust the color only if you need a stronger visual signal.",
            text_color=EVENT_EDITOR_PALETTE.text_secondary,
        ).grid(row=0, column=0, sticky="w")

        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            actions,
            text="Cancel",
            fg_color="transparent",
            hover_color=EVENT_EDITOR_PALETTE.panel_alt_bg,
            text_color=EVENT_EDITOR_PALETTE.text_secondary,
            border_width=1,
            border_color=EVENT_EDITOR_PALETTE.border,
            command=self.destroy,
        ).pack(side="right", padx=(10, 0))
        ctk.CTkButton(
            actions,
            text=self._save_label,
            fg_color=EVENT_EDITOR_PALETTE.accent,
            hover_color=EVENT_EDITOR_PALETTE.accent_hover,
            text_color="#FFFFFF",
            command=self._save,
        ).pack(side="right")

    def _create_field_block(self, master, title: str, helper: str):
        """Create field block."""
        block = ctk.CTkFrame(master, fg_color="transparent")
        block.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            block,
            text=title,
            text_color=EVENT_EDITOR_PALETTE.text_primary,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            block,
            text=helper,
            text_color=EVENT_EDITOR_PALETTE.text_secondary,
            justify="left",
            wraplength=260,
        ).grid(row=1, column=0, sticky="w", pady=(2, 8))
        return block

    def _bind_live_updates(self):
        """Bind live updates."""
        self.title_entry.bind("<KeyRelease>", lambda _event: self._refresh_summary_preview())
        self.status_entry.bind("<KeyRelease>", lambda _event: self._refresh_summary_preview())
        self.date_entry.entry.bind("<KeyRelease>", lambda _event: self._refresh_summary_preview(), add="+")
        self.date_entry.entry.bind("<FocusOut>", lambda _event: self._refresh_summary_preview(), add="+")
        self.start_entry.entry.bind("<KeyRelease>", lambda _event: self._refresh_summary_preview(), add="+")
        self.start_entry.entry.bind("<FocusOut>", lambda _event: self._refresh_summary_preview(), add="+")
        self.end_entry.entry.bind("<KeyRelease>", lambda _event: self._refresh_summary_preview(), add="+")
        self.end_entry.entry.bind("<FocusOut>", lambda _event: self._refresh_summary_preview(), add="+")
        self.type_menu.configure(command=lambda _value: self._on_type_changed())

    def _populate_fields(self):
        """Internal helper for populate fields."""
        self.title_entry.insert(0, self._initial.get("title", ""))

        current_date = self._initial.get("date") or date.today()
        self.date_entry.set(current_date)

        self.start_entry.set(self._initial.get("start_time", ""))
        self.end_entry.set(self._initial.get("end_time", ""))
        initial_type = self._initial.get("type", "Session") or "Session"
        self.type_menu.set(initial_type)

        initial_color = normalize_hex_color(self._initial.get("color"), fallback=get_event_type(initial_type).color)
        self._selected_color = initial_color
        self._color_locked = bool(self._initial.get("color"))
        self._update_color_button()

        status = self._initial.get("status", "")
        self.status_entry.insert(0, status)
        self._highlight_status(status)

        for field_name, _label in EVENT_LINK_GROUPS:
            selector = self._link_selectors[field_name]
            selector.set_values(self._initial.get(field_name) or [])

    def _set_status(self, value: str):
        """Set status."""
        self.status_entry.delete(0, "end")
        self.status_entry.insert(0, value)
        self._highlight_status(value)
        self._refresh_summary_preview()

    def _highlight_status(self, active_status: str):
        """Internal helper for highlight status."""
        normalized = str(active_status or "").strip().lower()
        for status, button in self._status_buttons.items():
            is_active = status.lower() == normalized
            button.configure(
                fg_color=EVENT_EDITOR_PALETTE.accent if is_active else EVENT_EDITOR_PALETTE.muted_chip,
                hover_color=EVENT_EDITOR_PALETTE.accent_hover if is_active else EVENT_EDITOR_PALETTE.panel_alt_bg,
                text_color="#FFFFFF" if is_active else EVENT_EDITOR_PALETTE.text_primary,
            )

    def _on_type_changed(self):
        """Handle type changed."""
        chosen_type = self.type_menu.get().strip()
        event_type = get_event_type(chosen_type)
        if not self._color_locked:
            self._apply_color(event_type.color, lock=False)
        self._refresh_summary_preview()

    def _apply_color(self, color: str, *, lock: bool):
        """Apply color."""
        self._selected_color = normalize_hex_color(color, fallback=self._selected_color)
        self._color_locked = lock
        self._update_color_button()
        self._refresh_summary_preview()

    def _save(self):
        """Save the operation."""
        payload = {
            "title": self.title_entry.get().strip(),
            "date": self.date_entry.get().strip(),
            "start_time": self.start_entry.get().strip(),
            "end_time": self.end_entry.get().strip(),
            "type": self.type_menu.get().strip(),
            "color": self._selected_color,
            "status": self.status_entry.get().strip(),
        }
        for field_name in self._link_selectors:
            payload[field_name] = self._link_selectors[field_name].get_values()
        if callable(self._on_save):
            self._on_save(payload)
        self.destroy()

    def _choose_color(self):
        """Internal helper for choose color."""
        current = normalize_hex_color(self._selected_color, fallback="#4F8EF7")
        selection = colorchooser.askcolor(color=current, parent=self)
        color = None
        if isinstance(selection, (tuple, list)) and len(selection) > 1:
            color = selection[1]
        self._apply_color(normalize_hex_color(color, fallback=current), lock=True)

    def _update_color_button(self):
        """Update color button."""
        self.color_button.configure(
            text=f"{self._selected_color}  {'• custom' if self._color_locked else '• auto'}",
            fg_color=self._selected_color,
            hover_color=self._selected_color,
            text_color="#FFFFFF",
        )

    def _refresh_summary_preview(self):
        """Refresh summary preview."""
        status = self.status_entry.get().strip()
        self._highlight_status(status)
        self.hero.update_preview(
            title=self.title_entry.get().strip(),
            event_type=self.type_menu.get().strip() or "Session",
            schedule=self._format_schedule_preview(),
            status=status or "Draft",
            color=self._selected_color,
        )

    def _format_schedule_preview(self):
        """Format schedule preview."""
        selected_date = self.date_entry.get().strip()
        start_time = self.start_entry.get().strip()
        end_time = self.end_entry.get().strip()

        if not selected_date:
            return "Date to define"
        if start_time and end_time:
            return f"{selected_date} · {start_time} → {end_time}"
        if start_time:
            return f"{selected_date} · starts at {start_time}"
        return selected_date
