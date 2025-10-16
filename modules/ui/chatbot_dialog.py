"""Shared chatbot dialog for querying campaign notes across entity wrappers."""
from __future__ import annotations

import tkinter as tk
from typing import Iterable, Mapping, Sequence

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
        geometry: str = "520x560",
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
            wraplength=460,
            font=("Segoe UI", 13, "bold"),
        )
        self.selection_label.grid(row=2, column=0, sticky="ew", pady=(10, 4))

        notes_frame = ctk.CTkFrame(self)
        notes_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        notes_frame.rowconfigure(1, weight=1)
        notes_frame.columnconfigure(0, weight=1)

        notes_label = ctk.CTkLabel(notes_frame, text="Notes", font=("Segoe UI", 14, "bold"))
        notes_label.grid(row=0, column=0, sticky="w", pady=(8, 4))

        self.notes_box = ctk.CTkTextbox(notes_frame, wrap="word")
        self.notes_box.grid(row=1, column=0, sticky="nsew")
        self.notes_box.configure(state=tk.DISABLED)

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
        note_text = self._extract_note(record)
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

    def _extract_note(self, record: Mapping) -> str:
        for field in self._note_fields:
            value = record.get(field)
            if isinstance(value, str) and value.strip():
                return value
        return ""

    def _render_note_text(self, text: str) -> None:
        self.notes_box.configure(state=tk.NORMAL)
        self.notes_box.delete("1.0", tk.END)
        self.notes_box.insert(tk.END, text)
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
