"""Shared chatbot dialog for querying campaign notes across entity wrappers."""
from __future__ import annotations

import tkinter as tk
from typing import Any, Iterable, Mapping, Sequence

import customtkinter as ctk

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_module_import
from modules.helpers.text_helpers import format_multiline_text

log_module_import(__name__)

# Wrappers exposed by the GM screen that we want to make available everywhere.
_DEFAULT_WRAPPER_FACTORIES: Sequence[tuple[str, str]] = (
    ("Scenarios", "scenarios"),
    ("Places", "places"),
    ("NPCs", "npcs"),
    ("PCs", "pcs"),
    ("Factions", "factions"),
    ("Creatures", "creatures"),
    ("Clues", "clues"),
    ("Informations", "informations"),
    ("Objects", "Objects"),
)

# Some models use "Title" instead of "Name" for their display key.
_DEFAULT_NAME_FIELD_OVERRIDES: Mapping[str, str] = {
    "Scenarios": "Title",
    "Informations": "Title",
}

# A list of potential fields that could contain note-style content.
_NOTE_FIELD_CANDIDATES: Sequence[str] = (
    "Notes",
    "Summary",
    "Description",
    "Information",
    "Details",
    "Body",
    "Text",
    "Gist",
    "Content",
    "Background",
)

_DEFAULT_SECTION_FIELDS: Sequence[tuple[str, tuple[str, ...]]] = (
    (
        "Overview",
        tuple(
            dict.fromkeys(
                (*_NOTE_FIELD_CANDIDATES, "Synopsis", "Background", "History", "Flavor")
            )
        ),
    ),
    (
        "Identity & Role",
        (
            "Role",
            "Title",
            "Type",
            "Profession",
            "Occupation",
            "Alignment",
            "Ancestry",
            "Heritage",
            "Species",
            "Organization",
            "Affiliation",
            "Faction",
            "Factions",
            "Rank",
            "Position",
        ),
    ),
    (
        "Traits & Personality",
        (
            "Traits",
            "Personality",
            "Appearance",
            "Quirks",
            "Mannerisms",
            "Roleplay",
            "RoleplayHint",
            "RoleplayHints",
            "Roleplay Hints",
            "RoleplayingCues",
            "Roleplaying Cues",
            "Behavior",
            "Voice",
        ),
    ),
    (
        "Statistics",
        (
            "Stats",
            "Attributes",
            "Abilities",
            "Skills",
            "Combat",
            "HP",
            "HitPoints",
            "Level",
            "Rank",
            "Resources",
            "Equipment",
            "Inventory",
            "Powers",
            "Weakness",
        ),
    ),
    (
        "Motivations & Secrets",
        (
            "Motivation",
            "Motivations",
            "Goals",
            "Agenda",
            "PlotHook",
            "PlotHooks",
            "Hooks",
            "Rumors",
            "Secret",
            "Secrets",
        ),
    ),
    (
        "Connections",
        (
            "Allies",
            "Contacts",
            "Relationships",
            "Connections",
            "Associates",
            "Enemies",
            "SupportingNPCs",
            "Family",
            "Friends",
        ),
    ),
)

_ENTITY_SECTION_OVERRIDES: Mapping[str, Sequence[tuple[str, tuple[str, ...]]]] = {
    "NPCs": (
        _DEFAULT_SECTION_FIELDS[0],
        _DEFAULT_SECTION_FIELDS[1],
        (
            "Traits & Personality",
            (
                "Traits",
                "Personality",
                "Appearance",
                "Quirks",
                "RoleplayingCues",
                "RoleplayHint",
                "RoleplayHints",
                "Behavior",
            ),
        ),
        _DEFAULT_SECTION_FIELDS[3],
        (
            "Motivations & Secrets",
            (
                "Motivation",
                "Goals",
                "Agenda",
                "Secret",
                "Secrets",
                "PlotHook",
                "PlotHooks",
            ),
        ),
        _DEFAULT_SECTION_FIELDS[5],
    ),
    "Creatures": (
        _DEFAULT_SECTION_FIELDS[0],
        (
            "Identity & Role",
            (
                "Type",
                "Role",
                "Environment",
                "Alignment",
            ),
        ),
        (
            "Traits & Abilities",
            (
                "Traits",
                "Abilities",
                "Powers",
                "Weakness",
                "SpecialAbilities",
            ),
        ),
        (
            "Statistics",
            (
                "Stats",
                "Attributes",
                "Skills",
                "Combat",
                "HP",
                "HitPoints",
                "Level",
            ),
        ),
        _DEFAULT_SECTION_FIELDS[4],
    ),
    "Factions": (
        _DEFAULT_SECTION_FIELDS[0],
        (
            "Identity & Role",
            (
                "Type",
                "Alignment",
                "Scale",
                "Reach",
                "Resources",
            ),
        ),
        (
            "Goals & Secrets",
            (
                "Goals",
                "Agenda",
                "Motivation",
                "Secret",
                "Secrets",
                "PlotHooks",
            ),
        ),
        _DEFAULT_SECTION_FIELDS[5],
    ),
    "Places": (
        _DEFAULT_SECTION_FIELDS[0],
        (
            "Location Details",
            (
                "Type",
                "Region",
                "Environment",
                "Tags",
                "Features",
                "SensoryDetails",
            ),
        ),
        (
            "Secrets & Hooks",
            (
                "Secrets",
                "Hooks",
                "PlotHooks",
                "Rumors",
            ),
        ),
        (
            "Occupants & Connections",
            (
                "NPCs",
                "Creatures",
                "Factions",
                "Allies",
                "Enemies",
            ),
        ),
    ),
}

_IGNORED_FIELDS: set[str] = {
    "Name",
    "Title",
    "ID",
    "Id",
    "Uuid",
    "UUID",
    "Portrait",
    "Image",
    "Token",
}


def get_default_chatbot_wrappers() -> dict[str, GenericModelWrapper]:
    """Return a dictionary of wrappers matching the GM screen defaults."""

    wrappers: dict[str, GenericModelWrapper] = {}
    for label, model_key in _DEFAULT_WRAPPER_FACTORIES:
        try:
            wrappers[label] = GenericModelWrapper(model_key)
        except Exception:
            # If a wrapper fails to initialise we silently skip it to avoid
            # breaking the dialog for the remaining models.
            continue
    return wrappers


class ChatbotDialog(ctk.CTkToplevel):
    """Simple dialog that surfaces entity notes filtered by a text query."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        wrappers: Mapping[str, GenericModelWrapper] | None = None,
        name_field_overrides: Mapping[str, str] | None = None,
        note_field_candidates: Iterable[str] | None = None,
        title: str = "Campaign Chatbot",
        geometry: str = "840x720",
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.geometry(geometry)
        try:
            if master is not None and isinstance(master, (tk.Tk, tk.Toplevel, ctk.CTk)):
                self.transient(master)
        except Exception:
            # Transient relationships are best-effort.
            pass
        self.resizable(True, True)

        self._wrappers = dict(wrappers or get_default_chatbot_wrappers())
        merged_overrides: dict[str, str] = dict(_DEFAULT_NAME_FIELD_OVERRIDES)
        if name_field_overrides:
            merged_overrides.update(name_field_overrides)
        self._name_field_overrides = merged_overrides
        self._note_fields = tuple(note_field_candidates or _NOTE_FIELD_CANDIDATES)

        self._results: list[tuple[str, str, dict]] = []

        self._build_ui()
        self._populate(initial=True)
        self.after(50, self._focus_query_entry)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        header.grid_columnconfigure(1, weight=1)

        title_label = ctk.CTkLabel(header, text="Ask the Campaign", font=("Segoe UI", 18, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(6, 8))

        prompt_label = ctk.CTkLabel(header, text="Type a question or keyword to surface matching notes.")
        prompt_label.grid(row=1, column=0, columnspan=2, sticky="w")

        query_label = ctk.CTkLabel(header, text="Query:")
        query_label.grid(row=2, column=0, sticky="w", pady=(12, 0))

        self.query_entry = ctk.CTkEntry(header, placeholder_text="e.g. mysterious cult, hidden door, plot hook")
        self.query_entry.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(12, 0))
        self.query_entry.bind("<KeyRelease>", self._on_query_changed)
        self.query_entry.bind("<Return>", self._on_submit)
        self.query_entry.bind("<KP_Enter>", self._on_submit)
        self.query_entry.bind("<Down>", self._focus_results)

        results_frame = ctk.CTkFrame(self)
        results_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 6))
        results_frame.rowconfigure(1, weight=1)
        results_frame.columnconfigure(0, weight=1)

        results_label = ctk.CTkLabel(results_frame, text="Matches", font=("Segoe UI", 14, "bold"))
        results_label.grid(row=0, column=0, sticky="w", pady=(8, 4))

        listbox_theme = self._derive_listbox_theme()
        self.result_list = tk.Listbox(
            results_frame,
            activestyle="none",
            bg=listbox_theme["bg"],
            fg=listbox_theme["fg"],
            highlightbackground=listbox_theme["bg"],
            selectbackground=listbox_theme["sel_bg"],
            selectforeground=listbox_theme["fg"],
        )
        self.result_list.grid(row=1, column=0, sticky="nsew")
        self.result_list.bind("<<ListboxSelect>>", self._display_selected_note)
        self.result_list.bind("<Return>", self._on_submit)
        self.result_list.bind("<KP_Enter>", self._on_submit)
        self.result_list.bind("<Double-Button-1>", self._on_submit)
        self.result_list.bind("<Up>", self._maybe_focus_query)

        self.selection_label = ctk.CTkLabel(
            results_frame,
            text="",
            anchor="w",
            wraplength=760,
            font=("Segoe UI", 13, "bold"),
        )
        self.selection_label.grid(row=2, column=0, sticky="ew", pady=(10, 4))

        notes_frame = ctk.CTkFrame(self)
        notes_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        notes_frame.rowconfigure(1, weight=1)
        notes_frame.columnconfigure(0, weight=1)

        notes_label = ctk.CTkLabel(notes_frame, text="Notes", font=("Segoe UI", 14, "bold"))
        notes_label.grid(row=0, column=0, sticky="w", pady=(8, 4))

        self._body_font = ctk.CTkFont(size=13)
        self._section_font = ctk.CTkFont(size=18, weight="bold")
        self._field_font = ctk.CTkFont(size=15, weight="bold")

        self.notes_box = ctk.CTkTextbox(notes_frame, wrap="word", font=self._body_font)
        self.notes_box.grid(row=1, column=0, sticky="nsew")
        self.notes_box.configure(state=tk.DISABLED)
        self.notes_box.tag_configure("section_title", font=self._section_font, spacing3=8)
        self.notes_box.tag_configure("field_label", font=self._field_font)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _focus_query_entry(self) -> None:
        try:
            self.query_entry.focus_set()
        except Exception:
            pass

    def _focus_results(self, _event=None):
        if self.result_list.size() == 0:
            return "break"
        self.result_list.focus_set()
        if not self.result_list.curselection():
            self.result_list.selection_clear(0, tk.END)
            self.result_list.selection_set(0)
            self.result_list.activate(0)
            self._display_selected_note()
        return "break"

    def _maybe_focus_query(self, _event=None):
        if self.result_list.curselection() == (0,):
            self.query_entry.focus_set()
            return "break"
        return None

    def _on_query_changed(self, _event=None) -> None:
        query = self.query_entry.get().strip()
        self._populate(initial=(query == ""), query=query.lower())

    def _on_submit(self, _event=None) -> None:
        self._display_selected_note()

    def _display_selected_note(self, _event=None) -> None:
        selection = self.result_list.curselection()
        if not selection:
            if self.result_list.size() == 0:
                self._render_note_text("No matches yet. Try refining your query.")
            return
        idx = selection[0]
        if idx >= len(self._results):
            return
        entity_type, name, record = self._results[idx]
        self.selection_label.configure(text=f"{entity_type}: {name}")
        note_text = self._extract_note(entity_type, record)
        if note_text:
            formatted = format_multiline_text(note_text)
        else:
            formatted = "No notes available for this record."
        self._render_note_text(formatted)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _populate(self, *, initial: bool, query: str = "") -> None:
        self.result_list.delete(0, tk.END)
        self._results.clear()

        if not self._wrappers:
            self._render_note_text("No data sources are available for the chatbot.")
            return

        for entity_type, wrapper in self._wrappers.items():
            try:
                items = wrapper.load_items()
            except Exception:
                continue
            key = self._name_field_overrides.get(entity_type, "Name")
            for item in items:
                name = item.get(key, "") or ""
                if not name:
                    continue
                if initial or (query and query in name.lower()):
                    display = f"{entity_type.rstrip('s')}: {name}"
                    self.result_list.insert(tk.END, display)
                    self._results.append((entity_type, name, item))

        if self.result_list.size() > 0:
            self.result_list.selection_clear(0, tk.END)
            self.result_list.selection_set(0)
            self.result_list.activate(0)
            self._display_selected_note()
        else:
            self.selection_label.configure(text="")
            if query:
                self._render_note_text("No results matched that query.")
            else:
                self._render_note_text("No records available to display.")

    def _extract_note(self, entity_type: str, record: Mapping[str, Any]) -> str:
        sections: list[str] = []
        used_fields: set[str] = set()

        for title, field_names in self._resolve_section_fields(entity_type):
            entries: list[str] = []
            for field in field_names:
                if field in used_fields:
                    continue
                value = record.get(field)
                formatted = self._format_field_value(field, value)
                if formatted:
                    entries.append(formatted)
                    used_fields.add(field)
            if entries:
                sections.append(self._format_section(title, entries))

        additional_entries: list[str] = []
        for key, value in record.items():
            if key in used_fields or key in _IGNORED_FIELDS:
                continue
            formatted = self._format_field_value(key, value)
            if formatted:
                additional_entries.append(formatted)
                used_fields.add(key)
        if additional_entries:
            sections.append(self._format_section("Additional Details", additional_entries))

        return "\n\n".join(section for section in sections if section).strip()

    def _resolve_section_fields(self, entity_type: str) -> Sequence[tuple[str, tuple[str, ...]]]:
        return _ENTITY_SECTION_OVERRIDES.get(entity_type, _DEFAULT_SECTION_FIELDS)

    def _format_section(self, title: str, entries: Sequence[str]) -> str:
        if not entries:
            return ""
        lines = [f"{title}:"]
        for entry in entries:
            entry_lines = [part.rstrip() for part in str(entry).splitlines()]
            if not entry_lines:
                continue
            lines.append("  " + "\n  ".join(entry_lines))
        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    def _format_field_value(self, label: str, value: Any) -> str | None:
        text = self._normalize_field_value(value)
        if not text:
            return None
        text = text.replace("\r\n", "\n").strip()
        if not text:
            return None
        if "\n" in text:
            indented = "\n  ".join(line.rstrip() for line in text.splitlines())
            return f"{label}:\n  {indented}"
        return f"{label}: {text}"

    def _normalize_field_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, Mapping):
            text_value = value.get("text")
            if isinstance(text_value, str) and text_value.strip():
                return text_value.strip()
            parts: list[str] = []
            for key, sub_value in value.items():
                if key in {"text", "formatting"}:
                    continue
                formatted = self._format_field_value(str(key), sub_value)
                if formatted:
                    parts.append(formatted)
            return "\n".join(parts)
        if isinstance(value, (list, tuple, set)):
            items: list[str] = []
            for item in value:
                normalized = self._normalize_field_value(item)
                if not normalized:
                    continue
                normalized = normalized.replace("\r\n", "\n").strip()
                if not normalized:
                    continue
                normalized = normalized.replace("\n", "\n    ")
                bullet = normalized if normalized.startswith("• ") else f"• {normalized}"
                items.append(bullet)
            return "\n".join(items)
        return str(value).strip()

    def _render_note_text(self, text: str) -> None:
        self.notes_box.configure(state=tk.NORMAL)
        self.notes_box.delete("1.0", tk.END)

        if text and not text.endswith("\n"):
            text += "\n"

        self.notes_box.insert(tk.END, text)

        lines = text.splitlines()
        for lineno, raw_line in enumerate(lines, start=1):
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                continue
            if not line.startswith(" ") and stripped.endswith(":"):
                self.notes_box.tag_add("section_title", f"{lineno}.0", f"{lineno}.end")
                continue
            colon_idx = line.find(":")
            if colon_idx == -1:
                continue
            leading_spaces = len(line) - len(line.lstrip(" "))
            start_index = f"{lineno}.0+{leading_spaces}c"
            end_index = f"{lineno}.0+{colon_idx + 1}c"
            try:
                self.notes_box.tag_add("field_label", start_index, end_index)
            except Exception:
                continue

        self.notes_box.configure(state=tk.DISABLED)

    def _derive_listbox_theme(self) -> dict[str, str]:
        entry = self.query_entry
        raw_bg = entry.cget("fg_color")
        raw_txt = entry.cget("text_color")
        appearance = ctk.get_appearance_mode()
        idx = 1 if appearance == "Dark" else 0

        def _resolve(value: str | Sequence[str]) -> str:
            if isinstance(value, (list, tuple)):
                return value[idx]
            if isinstance(value, str):
                parts = value.split()
                if len(parts) > idx:
                    return parts[idx]
                return parts[0]
            return "#1f1f1f"

        bg_color = _resolve(raw_bg)
        fg_color = _resolve(raw_txt)
        sel_bg = "#3a3a3a" if appearance == "Dark" else "#d9d9d9"
        return {"bg": bg_color, "fg": fg_color, "sel_bg": sel_bg}


def open_chatbot_dialog(
    master: tk.Misc | None,
    *,
    wrappers: Mapping[str, GenericModelWrapper] | None = None,
    name_field_overrides: Mapping[str, str] | None = None,
    note_field_candidates: Iterable[str] | None = None,
) -> ChatbotDialog:
    """Convenience helper to spawn the chatbot dialog."""

    dialog = ChatbotDialog(
        master,
        wrappers=wrappers,
        name_field_overrides=name_field_overrides,
        note_field_candidates=note_field_candidates,
    )
    return dialog


__all__ = [
    "ChatbotDialog",
    "get_default_chatbot_wrappers",
    "open_chatbot_dialog",
    "_DEFAULT_NAME_FIELD_OVERRIDES",
    "_NOTE_FIELD_CANDIDATES",
]
