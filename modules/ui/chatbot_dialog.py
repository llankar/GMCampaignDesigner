"""Campaign chatbot dialog with rich text rendering for entity notes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence
import bisect
import tkinter as tk

import customtkinter as ctk

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import (
    log_debug,
    log_exception,
    log_info,
    log_module_import,
    log_warning,
)
from modules.helpers.text_helpers import normalize_rtf_json

log_module_import(__name__)


# ---------------------------------------------------------------------------
# Rich text helpers
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class RichTextValue:
    """Simple container holding text and formatting spans."""

    text: str = ""
    formatting: dict[str, list[tuple[int, int]]] = field(default_factory=dict)

    def has_content(self) -> bool:
        return bool(self.text and self.text.strip())

    def cleaned(self) -> "RichTextValue":
        if not self.text:
            return self
        stripped = self.text.rstrip()
        if stripped == self.text:
            return self
        delta = len(self.text) - len(stripped)
        if delta <= 0:
            return self
        adjusted: dict[str, list[tuple[int, int]]] = {}
        end_limit = len(stripped)
        for tag, ranges in self.formatting.items():
            clipped: list[tuple[int, int]] = []
            for start, end in ranges:
                if end <= 0 or start >= end_limit:
                    continue
                clipped.append((max(0, start), min(end_limit, end)))
            if clipped:
                adjusted[tag] = clipped
        return RichTextValue(stripped, adjusted)

    def clone(self) -> "RichTextValue":
        return RichTextValue(self.text, {tag: ranges.copy() for tag, ranges in self.formatting.items()})


def _coerce_formatting(data: Mapping[str, Any]) -> dict[str, list[tuple[int, int]]]:
    coerced: dict[str, list[tuple[int, int]]] = {}
    for tag, ranges in data.items():
        result: list[tuple[int, int]] = []
        for start, end in ranges:
            try:
                s = int(start)
                e = int(end)
            except Exception:
                continue
            if e <= s:
                continue
            result.append((s, e))
        if result:
            coerced[tag] = result
    return coerced


def _from_rtf_json(value: Mapping[str, Any]) -> RichTextValue:
    normalized = normalize_rtf_json(value)
    text = normalized.get("text", "")
    fmt = normalized.get("formatting", {})
    return RichTextValue(str(text or ""), _coerce_formatting(fmt))


def _apply_line_prefix(value: RichTextValue, first_prefix: str, later_prefix: str | None = None) -> RichTextValue:
    if later_prefix is None:
        later_prefix = first_prefix
    base = value.text or ""
    if not base:
        return RichTextValue(first_prefix)

    lines = base.splitlines(True)
    new_parts: list[str] = []
    inserts: list[tuple[int, int]] = []
    cursor = 0
    total_added = 0

    for idx, line in enumerate(lines):
        prefix = first_prefix if idx == 0 else later_prefix
        if prefix:
            new_parts.append(prefix)
            total_added += len(prefix)
            inserts.append((cursor, total_added))
        new_parts.append(line)
        cursor += len(line)

    new_text = "".join(new_parts)

    if not value.formatting:
        return RichTextValue(new_text)

    adjusted: dict[str, list[tuple[int, int]]] = {}

    def _delta(pos: int) -> int:
        idx = bisect.bisect_right(inserts, (pos, float("inf")))
        if idx == 0:
            return 0
        return inserts[idx - 1][1]

    for tag, ranges in value.formatting.items():
        updates: list[tuple[int, int]] = []
        for start, end in ranges:
            delta_start = _delta(start)
            delta_end = _delta(end)
            updates.append((start + delta_start, end + delta_end))
        if updates:
            adjusted[tag] = updates
    return RichTextValue(new_text, adjusted)


# ---------------------------------------------------------------------------
# Section definitions
# ---------------------------------------------------------------------------
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

_DEFAULT_NAME_FIELD_OVERRIDES: Mapping[str, str] = {
    "Scenarios": "Title",
    "Informations": "Title",
}

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
    "Overview",
    "PlayerDisplay",
    "FlavorText",
)

_EMPTY_STRING_MARKERS = {"", "none", "null", "n/a", "na", "undefined", "unknown"}


_DEFAULT_SECTION_FIELDS: Mapping[str, Sequence[tuple[str, tuple[str, ...]]]] = {
    "default": (
        ("Overview", tuple(dict.fromkeys((*_NOTE_FIELD_CANDIDATES, "Synopsis", "History", "GMNotes")))),
        (
            "Role",
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
                "Rank",
                "Position",
                "Concept",
            ),
        ),
        (
            "Traits",
            (
                "Traits",
                "Personality",
                "Appearance",
                "Quirks",
                "Mannerisms",
                "Roleplay",
                "RoleplayHints",
                "RoleplayHint",
                "RoleplayingHints",
                "RoleplayingCues",
                "Behavior",
                "Voice",
                "Quote",
            ),
        ),
        (
            "Statistics",
            (
                "Stats",
                "StatBlock",
                "Attributes",
                "Abilities",
                "Skills",
                "Combat",
                "HP",
                "HitPoints",
                "HPMax",
                "Level",
                "ArmorClass",
                "AC",
                "Saves",
                "Speed",
                "Resources",
                "Equipment",
                "Inventory",
                "Powers",
                "Weakness",
            ),
        ),
        (
            "Secrets",
            (
                "Motivation",
                "Goals",
                "Agenda",
                "PlotHook",
                "PlotHooks",
                "Hooks",
                "Rumors",
                "Secret",
                "Secrets",
                "GMSecret",
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
                "Family",
                "Friends",
                "Factions",
                "NPCs",
                "Creatures",
            ),
        ),
    ),
    "NPCs": (
        ("Overview", tuple(dict.fromkeys((*_NOTE_FIELD_CANDIDATES, "Synopsis")))),
        (
            "Role",
            (
                "Role",
                "Title",
                "Type",
                "Occupation",
                "Alignment",
                "Organization",
                "Faction",
                "Rank",
            ),
        ),
        (
            "Traits",
            (
                "Traits",
                "Personality",
                "Appearance",
                "Quirks",
                "RoleplayHints",
                "RoleplayHint",
                "RoleplayingCues",
                "Behavior",
                "Quote",
            ),
        ),
        ("Statistics", ("Stats", "Attributes", "Abilities", "HP", "Level")),
        (
            "Secrets",
            (
                "Goals",
                "Motivation",
                "Secret",
                "Secrets",
                "PlotHooks",
            ),
        ),
        ("Connections", ("Allies", "Contacts", "Enemies", "Friends", "Factions")),
    ),
    "Creatures": (
        ("Overview", tuple(dict.fromkeys((*_NOTE_FIELD_CANDIDATES, "Ecology")))),
        (
            "Role",
            ("Type", "Role", "Environment", "Alignment", "Habitat"),
        ),
        (
            "Traits",
            ("Traits", "Abilities", "Powers", "Weakness", "SpecialAbilities", "Behavior"),
        ),
        ("Statistics", ("Stats", "Attributes", "Skills", "HP", "Level", "AC", "Speed")),
        ("Secrets", ("Goals", "Motivation", "Secret", "Secrets")),
    ),
    "Factions": (
        ("Overview", tuple(dict.fromkeys((*_NOTE_FIELD_CANDIDATES, "Background")))),
        (
            "Role",
            ("Type", "Alignment", "Scale", "Reach", "Resources"),
        ),
        ("Secrets", ("Goals", "Agenda", "Secret", "Secrets", "PlotHooks")),
        ("Connections", ("Allies", "Enemies", "Contacts", "Rivals")),
    ),
    "Places": (
        ("Overview", tuple(dict.fromkeys((*_NOTE_FIELD_CANDIDATES, "History", "Atmosphere")))),
        (
            "Role",
            ("Type", "Region", "Environment", "Tags", "Features", "SensoryDetails"),
        ),
        ("Secrets", ("Secrets", "Hooks", "PlotHooks", "Rumors")),
        (
            "Connections",
            ("NPCs", "Creatures", "Factions", "Allies", "Enemies", "Objects"),
        ),
    ),
    "Scenarios": (
        ("Overview", tuple(dict.fromkeys((*_NOTE_FIELD_CANDIDATES, "Synopsis", "Setup")))),
        ("Role", ("Type", "Theme", "Tone")),
        (
            "Traits",
            ("Tags", "Challenges", "Complications"),
        ),
        (
            "Statistics",
            ("Difficulty", "XP", "Rewards"),
        ),
        (
            "Secrets",
            ("Secrets", "Twists", "PlotHooks", "GMNotes"),
        ),
        (
            "Connections",
            ("Scenes", "Places", "NPCs", "Creatures", "Objects", "Factions", "Clues"),
        ),
    ),
}

_IGNORED_FIELDS = {
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


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def get_default_chatbot_wrappers() -> dict[str, GenericModelWrapper]:
    wrappers: dict[str, GenericModelWrapper] = {}
    for label, key in _DEFAULT_WRAPPER_FACTORIES:
        try:
            wrappers[label] = GenericModelWrapper(key)
        except Exception:
            continue
    return wrappers


def _normalize_value(value: Any) -> RichTextValue | None:
    preview = repr(value)
    if len(preview) > 200:
        preview = preview[:197] + "..."
    log_debug(
        f"ChatbotDialog._normalize_value - Processing value of type {type(value).__name__}: {preview}",
        func_name="ChatbotDialog._normalize_value",
    )
    if value is None:
        log_debug(
            "ChatbotDialog._normalize_value - Value was None; returning None",
            func_name="ChatbotDialog._normalize_value",
        )
        return None
    if isinstance(value, RichTextValue):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() in _EMPTY_STRING_MARKERS:
            log_debug(
                "ChatbotDialog._normalize_value - String matched empty marker; returning None",
                func_name="ChatbotDialog._normalize_value",
            )
            return None
        return RichTextValue(value.replace("\r\n", "\n").replace("\r", "\n"))
    if isinstance(value, Mapping):
        if "text" in value:
            normalized = _from_rtf_json(value)
            text = (normalized.text or "").strip()
            if text.lower() in _EMPTY_STRING_MARKERS:
                log_debug(
                    "ChatbotDialog._normalize_value - Mapping with text matched empty marker; returning None",
                    func_name="ChatbotDialog._normalize_value",
                )
                return None
            return normalized
        parts: list[str] = []
        for key, val in value.items():
            if val in (None, ""):
                continue
            parts.append(f"{key}: {val}")
        if not parts:
            log_debug(
                "ChatbotDialog._normalize_value - Mapping had no usable entries; returning None",
                func_name="ChatbotDialog._normalize_value",
            )
            return None
        return RichTextValue("\n".join(parts))
    if isinstance(value, (list, tuple, set)):
        bullets: list[RichTextValue] = []
        for item in value:
            normalized = _normalize_value(item)
            if not normalized or not normalized.has_content():
                continue
            bullets.append(_apply_line_prefix(normalized.cleaned(), "• ", "  "))
        if not bullets:
            log_debug(
                "ChatbotDialog._normalize_value - Iterable produced no bullet entries; returning None",
                func_name="ChatbotDialog._normalize_value",
            )
            return None
        joined_text = []
        joined_runs: dict[str, list[tuple[int, int]]] = {}
        cursor = 0
        for idx, bullet in enumerate(bullets):
            if idx > 0:
                joined_text.append("\n")
                cursor += 1
            joined_text.append(bullet.text)
            for tag, runs in bullet.formatting.items():
                joined_runs.setdefault(tag, []).extend((start + cursor, end + cursor) for start, end in runs)
            cursor += len(bullet.text)
        return RichTextValue("".join(joined_text), joined_runs)
    return RichTextValue(str(value))


# ---------------------------------------------------------------------------
# Dialog implementation
# ---------------------------------------------------------------------------
class ChatbotDialog(ctk.CTkToplevel):
    """Tk dialog that surfaces entity notes with styled text."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        wrappers: Mapping[str, GenericModelWrapper] | None = None,
        name_field_overrides: Mapping[str, str] | None = None,
        note_field_candidates: Iterable[str] | None = None,
        title: str = "Campaign Chatbot",
        geometry: str = "1500x800",
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.geometry(geometry)
        try:
            if master is not None and isinstance(master, (tk.Tk, tk.Toplevel, ctk.CTk)):
                self.transient(master)
        except Exception:
            pass
        self.resizable(True, True)

        self._wrappers = dict(wrappers or get_default_chatbot_wrappers())
        overrides = dict(_DEFAULT_NAME_FIELD_OVERRIDES)
        if name_field_overrides:
            overrides.update(name_field_overrides)
        self._name_field_overrides = overrides
        if note_field_candidates:
            self._note_fields = tuple(dict.fromkeys(note_field_candidates))
        else:
            self._note_fields = _NOTE_FIELD_CANDIDATES
        self._section_overrides = _DEFAULT_SECTION_FIELDS

        self._results: list[tuple[str, str, Mapping[str, Any]]] = []
        self._notes_widget: tk.Text | None = None

        self._build_ui()
        log_info(
            f"ChatbotDialog.__init__ - Initializing chatbot dialog with {len(self._wrappers)} wrappers",
            func_name="ChatbotDialog.__init__",
        )
        self._populate(initial=True)
        self.after(75, self._focus_query_entry)

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        header.grid_columnconfigure(1, weight=1)

        title_label = ctk.CTkLabel(header, text="Ask the Campaign", font=("Segoe UI", 18, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(4, 10))

        prompt_label = ctk.CTkLabel(header, text="Search by name or keyword to reveal matching notes.")
        prompt_label.grid(row=1, column=0, columnspan=2, sticky="w")

        ctk.CTkLabel(header, text="Query:").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.query_entry = ctk.CTkEntry(header, placeholder_text="e.g. cult, hidden door, plot hook")
        self.query_entry.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(12, 0))
        self.query_entry.bind("<KeyRelease>", self._on_query_changed)
        self.query_entry.bind("<Return>", self._on_submit)
        self.query_entry.bind("<KP_Enter>", self._on_submit)
        self.query_entry.bind("<Down>", self._focus_results)

        results_frame = ctk.CTkFrame(self)
        results_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        results_frame.rowconfigure(1, weight=1)
        results_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(results_frame, text="Matches", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(8, 4)
        )

        list_theme = self._derive_listbox_theme()
        self.result_list = tk.Listbox(
            results_frame,
            activestyle="none",
            bg=list_theme["bg"],
            fg=list_theme["fg"],
            highlightbackground=list_theme["bg"],
            selectbackground=list_theme["sel_bg"],
            selectforeground=list_theme["fg"],
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

        ctk.CTkLabel(notes_frame, text="Notes", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(8, 4)
        )

        self._body_font = ctk.CTkFont(size=13)
        self._section_font = ctk.CTkFont(size=18, weight="bold")
        self._field_font = ctk.CTkFont(size=15, weight="bold")
        family = self._body_font.cget("family")
        self._bold_font = ctk.CTkFont(family=family, size=13, weight="bold")
        self._italic_font = ctk.CTkFont(family=family, size=13, slant="italic")
        self._underline_font = ctk.CTkFont(family=family, size=13, underline=True)

        text_theme = self._derive_text_theme()
        self.notes_box = ctk.CTkTextbox(
            notes_frame,
            wrap="word",
            activate_scrollbars=False,
            fg_color=text_theme["bg"],
            text_color=text_theme["fg"],
        )
        self.notes_box.grid(row=1, column=0, sticky="nsew")
        widget = getattr(self.notes_box, "_textbox", self.notes_box)
        widget.configure(
            wrap="word",
            font=self._body_font,
            bg=text_theme["bg"],
            fg=text_theme["fg"],
            insertbackground=text_theme["fg"],
            selectbackground=text_theme["sel_bg"],
            selectforeground=text_theme["fg"],
            highlightthickness=0,
            borderwidth=0,
            padx=8,
            pady=8,
        )
        widget_config = widget.configure()
        disabled_config: dict[str, object] = {}
        if "disabledbackground" in widget_config:
            disabled_config["disabledbackground"] = text_theme["bg"]
        if "disabledforeground" in widget_config:
            disabled_config["disabledforeground"] = text_theme["fg"]
        if disabled_config:
            widget.configure(**disabled_config)
        self._notes_widget = widget
        self._set_notes_state("disabled")

        widget.tag_configure("section_title", font=self._section_font, spacing3=8)
        widget.tag_configure("field_label", font=self._field_font)
        widget.tag_configure("bold", font=self._bold_font)
        widget.tag_configure("italic", font=self._italic_font)
        widget.tag_configure("underline", font=self._underline_font)

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
        query = self.query_entry.get().strip().lower()
        self._populate(initial=(query == ""), query=query)

    def _on_submit(self, _event=None) -> None:
        self._display_selected_note()

    # ------------------------------------------------------------------
    # Data interaction
    # ------------------------------------------------------------------
    def _populate(self, *, initial: bool, query: str = "") -> None:
        log_info(
            f"ChatbotDialog._populate - Refreshing results (initial={initial}, query={query!r})",
            func_name="ChatbotDialog._populate",
        )
        self.result_list.delete(0, tk.END)
        self._results.clear()

        if not self._wrappers:
            log_warning(
                "ChatbotDialog._populate - No wrappers were provided; displaying empty state",
                func_name="ChatbotDialog._populate",
            )
            self._render_text(RichTextValue("No data sources are available for the chatbot."))
            return

        for entity_type, wrapper in self._wrappers.items():
            try:
                items = wrapper.load_items()
            except Exception:
                log_exception(
                    f"ChatbotDialog._populate - Failed to load items for {entity_type}",
                    func_name="ChatbotDialog._populate",
                )
                continue
            name_field = self._name_field_overrides.get(entity_type, "Name")
            try:
                count = len(items)  # type: ignore[arg-type]
                log_debug(
                    f"ChatbotDialog._populate - Loaded {count} records for {entity_type} (name field: {name_field})",
                    func_name="ChatbotDialog._populate",
                )
            except Exception:
                log_debug(
                    f"ChatbotDialog._populate - Loaded records for {entity_type} but total count is unknown",
                    func_name="ChatbotDialog._populate",
                )
            added_for_entity = 0
            for record in items:
                name = str(record.get(name_field, ""))
                if not name:
                    log_debug(
                        f"ChatbotDialog._populate - Skipping {entity_type} record without a name",
                        func_name="ChatbotDialog._populate",
                    )
                    continue
                if initial or (query and query in name.lower()):
                    display = f"{entity_type.rstrip('s')}: {name}"
                    self.result_list.insert(tk.END, display)
                    self._results.append((entity_type, name, record))
                    added_for_entity += 1
            log_debug(
                f"ChatbotDialog._populate - Added {added_for_entity} visible records for {entity_type}",
                func_name="ChatbotDialog._populate",
            )

        if self.result_list.size() > 0:
            self.result_list.selection_clear(0, tk.END)
            self.result_list.selection_set(0)
            self.result_list.activate(0)
            self._display_selected_note()
        else:
            log_info(
                f"ChatbotDialog._populate - No results matched query {query!r}",
                func_name="ChatbotDialog._populate",
            )
            self.selection_label.configure(text="")
            if query:
                self._render_text(RichTextValue("No results matched that query."))
            else:
                self._render_text(RichTextValue("No records available to display."))

    def _display_selected_note(self, _event=None) -> None:
        selection = self.result_list.curselection()
        if not selection:
            if self.result_list.size() == 0:
                self._render_text(RichTextValue("No matches yet. Try refining your query."))
            return
        idx = selection[0]
        if idx >= len(self._results):
            return
        entity_type, name, record = self._results[idx]
        log_debug(
            f"ChatbotDialog._display_selected_note - Selected index {idx} of {len(self._results)} results",
            func_name="ChatbotDialog._display_selected_note",
        )
        log_debug(
            f"ChatbotDialog._display_selected_note - Record keys: {sorted(record.keys())}",
            func_name="ChatbotDialog._display_selected_note",
        )
        log_info(
            f"ChatbotDialog._display_selected_note - Rendering notes for {entity_type} '{name}'",
            func_name="ChatbotDialog._display_selected_note",
        )
        self.selection_label.configure(text=f"{entity_type}: {name}")

        sections = self._collate_sections(entity_type, record)
        if not sections:
            log_warning(
                "ChatbotDialog._display_selected_note - No sections found after collation",
                func_name="ChatbotDialog._display_selected_note",
            )
            self._render_text(RichTextValue("No notes available for this record."))
            return
        log_debug(
            "ChatbotDialog._display_selected_note - Section summary: "
            + ", ".join(f"{title} ({len(entries)} fields)" for title, entries in sections),
            func_name="ChatbotDialog._display_selected_note",
        )
        self._render_sections(sections)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _section_layout(self, entity_type: str) -> Sequence[tuple[str, tuple[str, ...]]]:
        base = self._section_overrides.get(entity_type, self._section_overrides["default"])
        if self._note_fields == _NOTE_FIELD_CANDIDATES:
            return base
        merged: list[tuple[str, tuple[str, ...]]] = []
        first = True
        for title, fields in base:
            if first:
                merged.append((title, tuple(dict.fromkeys((*self._note_fields, *fields)))))
                first = False
            else:
                merged.append((title, fields))
        return tuple(merged)

    def _collate_sections(
        self, entity_type: str, record: Mapping[str, Any]
    ) -> list[tuple[str, list[tuple[str, RichTextValue]]]]:
        available_fields = sorted(str(key) for key in record.keys())
        log_debug(
            f"ChatbotDialog._collate_sections - Starting collation for {entity_type} with fields: {available_fields}",
            func_name="ChatbotDialog._collate_sections",
        )
        sections: list[tuple[str, list[tuple[str, RichTextValue]]]] = []
        used: set[str] = set()

        for title, field_names in self._section_layout(entity_type):
            entries: list[tuple[str, RichTextValue]] = []
            for field in field_names:
                if field in used:
                    log_debug(
                        f"ChatbotDialog._collate_sections - Skipping duplicate field {field}",
                        func_name="ChatbotDialog._collate_sections",
                    )
                    continue
                normalized = _normalize_value(record.get(field))
                if not normalized or not normalized.has_content():
                    log_debug(
                        f"ChatbotDialog._collate_sections - Field {field} had no usable content",
                        func_name="ChatbotDialog._collate_sections",
                    )
                    continue
                log_debug(
                    f"ChatbotDialog._collate_sections - Field {field} produced {len(normalized.text or '')} chars",
                    func_name="ChatbotDialog._collate_sections",
                )
                entries.append((field, normalized.cleaned()))
                used.add(field)
            if entries:
                sections.append((title, entries))
                log_debug(
                    f"ChatbotDialog._collate_sections - Added section '{title}' with fields {[label for label, _ in entries]}",
                    func_name="ChatbotDialog._collate_sections",
                )

        additional: list[tuple[str, RichTextValue]] = []
        for key, value in record.items():
            if key in used or key in _IGNORED_FIELDS:
                continue
            normalized = _normalize_value(value)
            if not normalized or not normalized.has_content():
                log_debug(
                    f"ChatbotDialog._collate_sections - Additional field {key} lacked content",
                    func_name="ChatbotDialog._collate_sections",
                )
                continue
            log_debug(
                f"ChatbotDialog._collate_sections - Additional field {key} produced {len(normalized.text or '')} chars",
                func_name="ChatbotDialog._collate_sections",
            )
            additional.append((key, normalized.cleaned()))
            used.add(key)
        if additional:
            sections.append(("Additional Details", additional))
            log_debug(
                f"ChatbotDialog._collate_sections - Added Additional Details section with fields {[label for label, _ in additional]}",
                func_name="ChatbotDialog._collate_sections",
            )
        if not sections:
            log_warning(
                "ChatbotDialog._collate_sections - No sections were generated for this record",
                func_name="ChatbotDialog._collate_sections",
            )
        return sections

    def _set_notes_state(self, state: str) -> None:
        try:
            self.notes_box.configure(state=state)
        except Exception:
            pass
        if self._notes_widget is not None:
            try:
                self._notes_widget.configure(state=state)
            except Exception:
                pass
        log_debug(
            f"ChatbotDialog._set_notes_state - Notes widget state changed to {state}",
            func_name="ChatbotDialog._set_notes_state",
        )

    def _render_text(self, value: RichTextValue) -> None:
        widget = self._notes_widget
        if widget is None:
            return
        self._set_notes_state("normal")
        widget.delete("1.0", tk.END)
        text = value.text
        if text and not text.endswith("\n"):
            text += "\n"
        widget.insert("1.0", text)
        for tag, ranges in value.formatting.items():
            if tag not in {"bold", "italic", "underline"}:
                continue
            for start, end in ranges:
                if end <= start:
                    continue
                start_index = f"1.0+{start}c"
                end_index = f"1.0+{end}c"
                widget.tag_add(tag, start_index, end_index)
        self._set_notes_state("disabled")
        log_debug(
            f"ChatbotDialog._render_text - Rendered plain text with {len(text or '')} characters",
            func_name="ChatbotDialog._render_text",
        )

    def _render_sections(self, sections: Sequence[tuple[str, list[tuple[str, RichTextValue]]]]) -> None:
        widget = self._notes_widget
        if widget is None:
            return
        self._set_notes_state("normal")
        widget.delete("1.0", tk.END)

        text_parts: list[str] = []
        tag_runs: dict[str, list[tuple[int, int]]] = {"bold": [], "italic": [], "underline": []}
        field_runs: list[tuple[int, int]] = []
        section_runs: list[tuple[int, int]] = []
        cursor = 0

        for section_index, (title, entries) in enumerate(sections):
            if section_index > 0:
                text_parts.append("\n")
                cursor += 1
            section_start = cursor
            section_line = f"{title}\n"
            text_parts.append(section_line)
            cursor += len(section_line)
            section_runs.append((section_start, section_start + len(title)))

            for entry_index, (label, value) in enumerate(entries):
                if entry_index > 0:
                    text_parts.append("\n")
                    cursor += 1
                value_text = value.text or ""
                multiline = "\n" in value_text
                if multiline:
                    line = f"{label}:\n"
                    text_parts.append(line)
                    field_runs.append((cursor, cursor + len(label) + 1))
                    cursor += len(line)
                    indented = _apply_line_prefix(value, "  ")
                    block = indented.text
                    block_offset = cursor
                    text_parts.append(block)
                    for tag, ranges in indented.formatting.items():
                        tag_runs.setdefault(tag, []).extend((start + block_offset, end + block_offset) for start, end in ranges)
                    cursor += len(block)
                    if not block.endswith("\n"):
                        text_parts.append("\n")
                        cursor += 1
                else:
                    prefix = f"{label}: "
                    line_start = cursor
                    text_parts.append(prefix)
                    cursor += len(prefix)
                    field_runs.append((line_start, line_start + len(prefix)))
                    text_parts.append(value_text)
                    value_offset = cursor
                    for tag, ranges in value.formatting.items():
                        tag_runs.setdefault(tag, []).extend((start + value_offset, end + value_offset) for start, end in ranges)
                    cursor += len(value_text)
                    text_parts.append("\n")
                    cursor += 1
                log_debug(
                    f"ChatbotDialog._render_sections - Added entry {label!r} with {len(value_text)} chars (multiline={multiline})",
                    func_name="ChatbotDialog._render_sections",
                )

        final_text = "".join(text_parts)
        widget.insert("1.0", final_text)
        log_debug(
            f"ChatbotDialog._render_sections - Rendered {len(sections)} sections with total length {len(final_text)}",
            func_name="ChatbotDialog._render_sections",
        )

        for start, end in section_runs:
            widget.tag_add("section_title", f"1.0+{start}c", f"1.0+{end}c")
        for start, end in field_runs:
            widget.tag_add("field_label", f"1.0+{start}c", f"1.0+{end}c")

        for tag, runs in tag_runs.items():
            if tag not in {"bold", "italic", "underline"}:
                continue
            for start, end in runs:
                if end <= start:
                    continue
                widget.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")

        self._set_notes_state("disabled")
        applied = {tag: len(runs) for tag, runs in tag_runs.items() if runs}
        log_debug(
            f"ChatbotDialog._render_sections - Applied formatting tags summary: {applied}",
            func_name="ChatbotDialog._render_sections",
        )

    def _derive_listbox_theme(self) -> dict[str, str]:
        entry = self.query_entry
        raw_bg = entry.cget("fg_color")
        raw_fg = entry.cget("text_color")
        appearance = ctk.get_appearance_mode()
        idx = 1 if appearance == "Dark" else 0

        def _resolve(value: str | Sequence[str], fallback: str) -> str:
            chosen: str | None = None
            if isinstance(value, (list, tuple)):
                if value:
                    chosen = value[idx if idx < len(value) else 0]
            elif isinstance(value, str):
                parts = value.split()
                if parts:
                    chosen = parts[idx if idx < len(parts) else 0]
                else:
                    chosen = value
            if not chosen:
                return fallback
            lowered = chosen.lower()
            if lowered in {"", "none", "null", "transparent"}:
                return fallback
            return chosen

        bg = _resolve(raw_bg, "#2b2b2b" if appearance == "Dark" else "#f6f6f6")
        fg = _resolve(raw_fg, "#f5f5f5" if appearance == "Dark" else "#121212")
        sel_bg = "#3a3a3a" if appearance == "Dark" else "#d9d9d9"
        if fg.lower() == bg.lower():
            fg = "#f5f5f5" if appearance == "Dark" else "#121212"
        return {"bg": bg, "fg": fg, "sel_bg": sel_bg}

    def _derive_text_theme(self) -> dict[str, str]:
        base = self._derive_listbox_theme()
        bg = base["bg"]
        fg = base["fg"]
        if fg.lower() == bg.lower():
            fg = "#f5f5f5" if ctk.get_appearance_mode() == "Dark" else "#121212"
        return {"bg": bg, "fg": fg, "sel_bg": base["sel_bg"]}


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------
def open_chatbot_dialog(
    master: tk.Misc | None,
    *,
    wrappers: Mapping[str, GenericModelWrapper] | None = None,
    name_field_overrides: Mapping[str, str] | None = None,
    note_field_candidates: Iterable[str] | None = None,
) -> ChatbotDialog:
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
