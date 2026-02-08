import os
import customtkinter as ctk
from PIL import Image
from customtkinter import CTkLabel, CTkImage, CTkTextbox
from modules.helpers.text_helpers import (
    deserialize_possible_json,
    format_longtext,
    format_multiline_text,
)
from modules.helpers.rtf_rendering import render_rtf_to_text_widget
from modules.helpers.template_loader import load_template
from modules.generic.generic_model_wrapper import GenericModelWrapper
from tkinter import Toplevel, messagebox
from tkinter import ttk
import tkinter.font as tkfont
import tkinter as tk
from modules.helpers.portrait_helper import primary_portrait, resolve_portrait_path
from modules.ui.image_viewer import show_portrait
from modules.ui.tooltip import ToolTip
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.helpers.config_helper import ConfigHelper
from modules.audio.entity_audio import (
    get_entity_audio_value,
    play_entity_audio,
    resolve_audio_path,
    stop_entity_audio,
)
from modules.books.book_viewer import open_book_viewer
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_module_import,
)
from modules.scenarios.scene_flow_viewer import create_scene_flow_frame
from modules.ui.vertical_section_tabs import VerticalSectionTabs

log_module_import(__name__)

# Configure portrait size.
PORTRAIT_SIZE = (200, 200)
_open_entity_windows = {}

TOOLTIP_FIELDS = {
    "NPCs": ("Role", "Secret", "Traits", "Motivation"),
    "Creatures": ("Type", "Stats", "Powers", "Weakness", "Background"),
    "PCs": ("Role", "Traits", "Secret", "Background"),
    "Places": ("Description", "Secrets"),
    "Objects": ("Description", "Powers"),
    "Factions": ("Description", "Secrets"),
    "Books": ("Subject", "Game", "Tags", "Notes"),
}


def _format_tooltip_value(value, max_length=200):
    if value is None:
        return ""
    if isinstance(value, list):
        joined = ", ".join(str(v).strip() for v in value if str(v).strip())
        if not joined:
            return ""
        return format_longtext(joined, max_length=max_length)
    return format_longtext(value, max_length=max_length)


def build_entity_tooltip(entity_type, data):
    """Build a compact tooltip string for an entity portrait."""
    if not isinstance(data, dict):
        return ""

    name_field = "Title" if entity_type in {"Scenarios", "Books"} else "Name"
    name_value = str(data.get(name_field, "")).strip()
    lines = []
    if name_value:
        lines.append(name_value)

    for field in TOOLTIP_FIELDS.get(entity_type, ()):  # type: ignore[arg-type]
        if field == name_field:
            continue
        raw_value = data.get(field)
        text = _format_tooltip_value(raw_value)
        if text:
            lines.append(f"{field}: {text}")

    return "\n".join(lines)


def _attach_portrait_tooltip(widget, entity_type, data):
    tooltip_text = build_entity_tooltip(entity_type, data)
    if tooltip_text:
        widget.tooltip = ToolTip(widget, tooltip_text)

wrappers = {
    "Scenarios": GenericModelWrapper("scenarios"),
    "Places": GenericModelWrapper("places"),
    "NPCs": GenericModelWrapper("npcs"),
    "Factions": GenericModelWrapper("factions"),
    "Objects": GenericModelWrapper("objects"),
    "Creatures": GenericModelWrapper("creatures"),
    "PCs": GenericModelWrapper("pcs"),
    "Clues": GenericModelWrapper("clues"),
    "Informations": GenericModelWrapper("informations"),
    "Puzzles": GenericModelWrapper("puzzles"),
    "Books": GenericModelWrapper("books"),
}

@log_function
def _open_book_link(parent, book_title: str) -> None:
    title = str(book_title or "").strip()
    if not title:
        return
    wrapper = wrappers.get("Books")
    if wrapper is None:
        messagebox.showerror("Books", "Book library is not available.")
        return
    try:
        record = wrapper.load_item_by_key(title, key_field="Title")
    except Exception as exc:
        messagebox.showerror("Books", f"Unable to load books: {exc}")
        return
    if not record:
        messagebox.showerror("Books", f"Book '{title}' not found.")
        return
    master = parent.winfo_toplevel() if parent is not None else None
    open_book_viewer(master, record)

@log_function
def insert_text(parent, header, content):
    label = ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 16, "bold"))
    label.pack(anchor="w", padx=10)
    box = ctk.CTkTextbox(parent, wrap="word", height=40)
    render_rtf_to_text_widget(box, content)
    box.pack(fill="x", padx=10, pady=5)

@log_function
def insert_longtext(parent, header, content):
    ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 16, "bold")).pack(anchor="w", padx=10)

    box = CTkTextbox(parent, wrap="word")
    render_rtf_to_text_widget(box, content)
    box.pack(fill="x", padx=10, pady=5)

    # Resize after layout
    def update_height():
        lines = int(box._textbox.count("1.0", "end", "lines")[0])
        font = tkfont.Font(font=box._textbox.cget("font"))
        line_px = font.metrics("linespace")
        box.configure(height=max(2, lines+2) * line_px)
        box.configure(state="disabled")

    box.after_idle(update_height)

@log_function
def insert_links(parent, header, items, linked_type, open_entity_callback):
    ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold")).pack(anchor="w", padx=10)
    for item in items:
        display_text = str(item)
        if not display_text:
            continue
        label = CTkLabel(parent, text=display_text, text_color="#00BFFF", cursor="hand2")
        label.pack(anchor="w", padx=10)
        if linked_type == "Books":
            label.bind("<Button-1>", lambda _event, title=display_text: _open_book_link(parent, title))
        elif open_entity_callback is not None:
            # Capture the current values with lambda defaults.
            label.bind("<Button-1>", lambda event, l=linked_type, i=display_text: open_entity_callback(l, i))


@log_function
def insert_relationship_table(parent, header, relationships, open_entity_callback):
    if not relationships:
        return

    ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(6, 2))

    table = ctk.CTkFrame(parent)
    table.pack(fill="x", padx=10, pady=(0, 6))

    for idx in range(3):
        table.grid_columnconfigure(idx, weight=1)

    headers = ["Source", "Relationship", "Target"]
    for col, title in enumerate(headers):
        CTkLabel(table, text=title, font=("Arial", 12, "bold"))\
            .grid(row=0, column=col, padx=6, pady=2, sticky="w")

    for row_idx, relationship in enumerate(relationships, start=1):
        source_name = relationship.get("source_name", "")
        relation_text = relationship.get("relation_text", "")
        target_name = relationship.get("target_name", "")

        source_label = CTkLabel(
            table,
            text=source_name,
            text_color="#00BFFF",
            cursor="hand2",
            font=("Arial", 12, "underline"),
        )
        source_label.grid(row=row_idx, column=0, padx=6, pady=2, sticky="w")
        if open_entity_callback:
            source_type = relationship.get("source_type", "NPCs")
            source_label.bind(
                "<Button-1>",
                lambda _event=None, t=source_type, n=source_name: open_entity_callback(t, n),
            )

        CTkLabel(
            table,
            text=relation_text,
            font=("Arial", 12),
        ).grid(row=row_idx, column=1, padx=6, pady=2, sticky="w")

        target_label = CTkLabel(
            table,
            text=target_name,
            text_color="#00BFFF",
            cursor="hand2",
            font=("Arial", 12, "underline"),
        )
        target_label.grid(row=row_idx, column=2, padx=6, pady=2, sticky="w")
        if open_entity_callback:
            target_type = relationship.get("target_type", "NPCs")
            target_label.bind(
                "<Button-1>",
                lambda _event=None, t=target_type, n=target_name: open_entity_callback(t, n),
            )


@log_function
def open_entity_tab(entity_type, name, master):
    log_info(f"Opening entity tab for {entity_type}: {name}", func_name="open_entity_tab")
    """
    Opens (or focuses) a detail window for the given entity_type/name.
    Debug prints added to trace why/when new windows are created.
    """
    # 1) Build a unique key and look for an existing window
    window_key = f"{entity_type}:{name}"
    existing = _open_entity_windows.get(window_key)
    if existing:
        alive = existing.winfo_exists()
        if alive:
            existing.deiconify()
            existing.lift()
            return
        else:
            _open_entity_windows.pop(window_key, None)

    # 2) Load the data item
    wrapper = wrappers.get(entity_type)
    if not wrapper:
        messagebox.showerror("Error", f"Unknown type '{entity_type}'")
        return

    key_field = "Title" if entity_type in {"Scenarios", "Books"} else "Name"
    item = wrapper.load_item_by_key(name, key_field=key_field)
    if not item:
        messagebox.showerror("Error", f"{entity_type[:-1]} '{name}' not found.")
        return

    # 3) Create a new Toplevel window
    new_window = ctk.CTkToplevel()
    new_window.title(f"{entity_type[:-1]}: {name}")
    new_window.geometry("1000x600")
    new_window.minsize(1000, 600)
    new_window.configure(padx=10, pady=10)

    # 4) Build the scrollable detail frame inside it
    scrollable_container = ctk.CTkScrollableFrame(new_window)
    scrollable_container.pack(fill="both", expand=True)
    frame = create_entity_detail_frame(
        entity_type,
        item,
        master=scrollable_container,
        open_entity_callback=open_entity_tab
    )
    frame.pack(fill="both", expand=True)

    # 5) Register it and hook the close event
    _open_entity_windows[window_key] = new_window

    def _on_close():
        _open_entity_windows.pop(window_key, None)
        new_window.destroy()

    new_window.protocol("WM_DELETE_WINDOW", _on_close)
    
@log_function
def unwrap_value(val):
    """
    If val is a dict with a 'text' key, return that.
    Otherwise, return str(val) (or '' if None).
    """
    if isinstance(val, dict):
        return val.get("text", "")
    if val is None:
        return ""
    return str(val)

@log_function
def insert_npc_table(parent, header, npc_names, open_entity_callback):
    CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold"))\
        .pack(anchor="w", padx=10, pady=(1, 2))

    table = ctk.CTkFrame(parent)
    table.pack(fill="both", expand=True, padx=10, pady=(0,0))

    cols         = ["Portrait", "Name", "Secret", "Background",  "Traits", "Factions"]
    weights      = [0,         1,       2,        2,            4,          1     ]
    wrap_lengths = [0,       120,     250,      250,          500,        100   ]
    text_heights = {2: 60, 3: 60, 4: 60}

    # configure columns
    for idx, w in enumerate(weights):
        table.grid_columnconfigure(idx, weight=w)

    # configure all rows to expand equally (after we place them)
    # we'll do that after row creation below

    # header row
    for c, col_name in enumerate(cols):
        CTkLabel(table, text=col_name, font=("Arial", 12, "bold"))\
            .grid(row=0, column=c, padx=5, pady=1, sticky="nsew")

    # load data
    wrapper = GenericModelWrapper("npcs")
    all_npcs = wrapper.load_items()
    npc_map   = {npc["Name"]: npc for npc in all_npcs}

    for r, name in enumerate(npc_names, start=1):
        data = npc_map.get(name, {}) or {}

        # portrait
        portrait_path = primary_portrait(data.get("Portrait"))
        resolved_portrait = resolve_portrait_path(portrait_path, ConfigHelper.get_campaign_dir())
        if resolved_portrait and os.path.exists(resolved_portrait):
            img = Image.open(resolved_portrait).resize((40,40), Image.Resampling.LANCZOS)
            photo = CTkImage(light_image=img, size=(40,40))
            widget = CTkLabel(table, image=photo, text="", anchor="center")
            widget.image = photo
            _attach_portrait_tooltip(widget, "NPCs", data)
            # clicking the thumbnail pops up the full‑screen viewer
            widget.bind(
                "<Button-1>",
                lambda _event=None, p=portrait_path, n=name: show_portrait(p, n)
            )
        else:
            widget = CTkLabel(table, text="", anchor="center")
        widget.grid(row=r, column=0, padx=5, pady=5, sticky="nsew")

        # other columns
        secret     = format_longtext(data.get("Secret",""))
        background = format_longtext(data.get("Background",""))
        factions   = ", ".join(data.get("Factions") or [])
        traits     = format_longtext(data.get("Traits"))

        values = [name, secret, background, traits, factions]
        for c, txt in enumerate(values, start=1):
            if c in text_heights:
                cell = CTkTextbox(table, wrap="word", height=text_heights[c])
                cell.insert = cell._textbox.insert
                cell.insert("1.0", txt)
                cell.configure(state="disabled")
            else:
                if c == 1:
                    cell = CTkLabel(
                        table,
                        text=txt,
                        text_color="#00BFFF",
                        font=("Arial", 12, "underline"),
                        cursor="hand2",
                        anchor="center",
                        justify="center"

                    )
                    if open_entity_callback:
                        cell.bind(
                            "<Button-1>",
                            lambda _event=None, nm=name: open_entity_callback("NPCs", nm)
                        )
                else:
                    cell = CTkLabel(
                        table,
                        text=txt,
                        font=("Arial", 12),
                        wraplength=wrap_lengths[c],
                        justify="left",
                        anchor="w"
                    )
            cell.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")

        # make this row expandable so portrait centers vertically
        table.grid_rowconfigure(r, weight=1)

@log_function
def insert_creature_table(parent, header, creature_names, open_entity_callback):
    CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold")) \
        .pack(anchor="w", padx=10, pady=(1, 2))

    table = ctk.CTkFrame(parent)
    table.pack(fill="both", expand=True, padx=10, pady=(0,0))

    cols         = ["Portrait", "Name", "Weakness", "Powers", "Stats"]
    weights      = [0,         1,       3,          3,        2     ]
    wrap_lengths = [0,       150,     400,        400,      300   ]
    text_heights = {2: 60, 3: 60,    4: 60}

    for idx, w in enumerate(weights):
        table.grid_columnconfigure(idx, weight=w)

    for c, col in enumerate(cols):
        CTkLabel(table, text=col, font=("Arial", 12, "bold")) \
            .grid(row=0, column=c, padx=5, pady=1, sticky="nsew")

    wrapper       = GenericModelWrapper("creatures")
    all_creatures = wrapper.load_items()
    creature_map  = {cr["Name"]: cr for cr in all_creatures}

    for r, name in enumerate(creature_names, start=1):
        data = creature_map.get(name, {}) or {}

        # portrait
        portrait_path = primary_portrait(data.get("Portrait"))
        resolved_portrait = resolve_portrait_path(portrait_path, ConfigHelper.get_campaign_dir())
        if resolved_portrait and os.path.exists(resolved_portrait):
            img = Image.open(resolved_portrait).resize((40,40), Image.Resampling.LANCZOS)
            photo = CTkImage(light_image=img, size=(40,40))
            widget = CTkLabel(table, image=photo, text="", anchor="center")
            widget.image = photo
            _attach_portrait_tooltip(widget, "Creatures", data)
            widget.bind(
                "<Button-1>",
                lambda e, p=portrait_path, n=name: show_portrait(p, n)
            )
        else:
            widget = CTkLabel(table, text="", anchor="center")
        widget.grid(row=r, column=0, padx=5, pady=5, sticky="nsew")

        # other columns
        weakness = format_longtext(data.get("Weakness",""), max_length=2000)
        powers   = format_longtext(data.get("Powers",""),   max_length=2000)
        stats    = format_longtext(data.get("Stats",""),    max_length=2000)

        values = [name, weakness, powers, stats]
        for c, txt in enumerate(values, start=1):
            if c in text_heights:
                cell = CTkTextbox(table, wrap="word", height=text_heights[c])
                cell.insert = cell._textbox.insert
                cell.insert("1.0", txt)
                cell.configure(state="disabled")
            else:
                if c == 1:
                    cell = CTkLabel(
                        table,
                        text=txt,
                        text_color="#00BFFF",
                        font=("Arial", 12, "underline"),
                        cursor="hand2",
                        anchor="center",
                        justify="center"
                    )
                    if open_entity_callback:
                        cell.bind(
                            "<Button-1>",
                            lambda e, nm=name: open_entity_callback("Creatures", nm)
                        )
                else:
                    cell = CTkLabel(
                        table,
                        text=txt,
                        font=("Arial", 12),
                        wraplength=wrap_lengths[c],
                        justify="left",
                        anchor="w"
                    )
            cell.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")

        table.grid_rowconfigure(r, weight=1)

@log_function
def insert_places_table(parent, header, place_names, open_entity_callback):
    """
    Render a table of Places (excluding PlayerDisplay) with columns:
    Portrait, Name, Description, NPCs, Secrets
    """
    # Section header
    CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold")) \
        .pack(anchor="w", padx=10, pady=(1, 2))

    # Table container
    table = ctk.CTkFrame(parent)
    table.pack(fill="both", expand=True, padx=10, pady=(0, 0))

    # Column defs
    cols         = ["Portrait", "Name", "Description", "NPCs", "Secrets"]
    weights      = [0,          1,      2,             1,      1    ]
    wrap_lengths = [0,        150,    400,           200,    200  ]
    # only Description (2) and Secrets (4) get scrollboxes
    text_heights = {2: 60,  4: 60}

    # configure columns
    for idx, w in enumerate(weights):
        table.grid_columnconfigure(idx, weight=w)

    # header row
    for c, col_name in enumerate(cols):
        CTkLabel(table, text=col_name, font=("Arial", 12, "bold")) \
            .grid(row=0, column=c, padx=5, pady=1, sticky="nsew")

    # load place data once
    place_map = {
        pl["Name"]: pl
        for pl in GenericModelWrapper("places").load_items()
    }

    # populate rows
    for r, name in enumerate(place_names, start=1):
        data     = place_map.get(name, {}) or {}
        portrait = primary_portrait(data.get("Portrait", ""))
        desc     = format_longtext(data.get("Description", ""))
        secrets  = format_longtext(data.get("Secrets", ""))
        npcs     = data.get("NPCs") or []
        values   = [portrait, name, desc, npcs, secrets]

        for c, val in enumerate(values):
            # scrollable for Description & Secrets
            if c in text_heights:
                cell = CTkTextbox(table, wrap="word", height=text_heights[c])
                cell.insert = cell._textbox.insert
                cell.insert("1.0", val)
                cell.configure(state="disabled")

            # Portrait thumbnail
            elif c == 0:
                resolved_portrait = resolve_portrait_path(portrait, ConfigHelper.get_campaign_dir())
                if resolved_portrait and os.path.exists(resolved_portrait):
                    img   = Image.open(resolved_portrait).resize((40, 40), Image.Resampling.LANCZOS)
                    photo = CTkImage(light_image=img, size=(40, 40))
                    cell  = CTkLabel(table, image=photo, text="", anchor="center")
                    cell.image = photo
                    _attach_portrait_tooltip(cell, "Places", data)
                    cell.bind(
                        "<Button-1>",
                        lambda e, p=portrait, n=name: show_portrait(p, n)
                    )
                else:
                    cell = CTkLabel(table, text="–", font=("Arial", 12), anchor="center")

            # clickable Name
            elif c == 1:
                cell = CTkLabel(
                    table, text=val,
                    text_color="#00BFFF", font=("Arial", 12, "underline"),
                    cursor="hand2", anchor="center",
                    height=60
                )
                if open_entity_callback:
                    cell.bind(
                        "<Button-1>",
                        lambda e, nm=val: open_entity_callback("Places", nm)
                    )

            # NPCs list as individual links
            elif c == 3:
                cell = ctk.CTkFrame(table, height=60)
                for i, npc_name in enumerate(val):
                    link = CTkLabel(
                        cell, text=npc_name,
                        text_color="#00BFFF", font=("Arial", 12, "underline"),
                        cursor="hand2",
                        height=60
                    )
                    if open_entity_callback:
                        link.bind(
                            "<Button-1>",
                            lambda e, nm=npc_name: open_entity_callback("NPCs", nm)
                        )
                    link.grid(row=0, column=i, padx=(0, 5))

            # default simple label
            else:
                cell = CTkLabel(
                    table, text=val,
                    font=("Arial", 12),
                    wraplength=wrap_lengths[c],
                    justify="left", anchor="w",
                    height=60
                )

            cell.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")

        # match NPC row heights
        table.grid_rowconfigure(r, weight=1)
        
@log_function
def insert_list_longtext(
    parent,
    header,
    items,
    open_entity_callback=None,
    entity_collector=None,
    gm_view=None,
    show_header=True,
):
    """Insert collapsible sections for long text lists such as scenario scenes."""
    if show_header:
        ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 16, "bold")) \
            .pack(anchor="w", padx=10, pady=(10, 2))

    def _flatten_strings(value):
        parsed = deserialize_possible_json(value)
        if isinstance(parsed, dict):
            for key in ("text", "Text", "value", "Value", "name", "Name"):
                if key in parsed:
                    return _flatten_strings(parsed[key])
            results = []
            for item in parsed.values():
                results.extend(_flatten_strings(item))
            return results
        if isinstance(parsed, (list, tuple, set)):
            results = []
            for item in parsed:
                results.extend(_flatten_strings(item))
            return results
        if parsed is None:
            return []
        text = str(parsed).strip()
        return [text] if text else []

    def _coerce_names(value):
        names = []
        for entry in _flatten_strings(value):
            parts = [part.strip() for part in entry.split(",") if part.strip()]
            names.extend(parts or [entry])
        return names

    def _coerce_links(value):
        links = []
        if value is None:
            return links
        parsed = deserialize_possible_json(value)
        if isinstance(parsed, list):
            for item in parsed:
                links.extend(_coerce_links(item))
            return links
        if isinstance(parsed, dict):
            payload = {k: deserialize_possible_json(v) for k, v in parsed.items()}
            target = None
            text_val = None
            for key in ("Target", "target", "Scene", "scene", "Next", "next", "Id", "id", "Reference", "reference"):
                if key in payload:
                    target = payload[key]
                    break
            for key in ("Text", "text", "Label", "label", "Description", "description", "Choice", "choice"):
                if key in payload:
                    text_val = payload[key]
                    break

            if isinstance(target, (int, float)):
                target_display = int(target)
            else:
                target_options = _flatten_strings(target)
                if target_options:
                    target_display = target_options[0]
                elif target is not None:
                    target_display = str(target)
                else:
                    target_display = None

            text_options = _flatten_strings(text_val)
            if text_options:
                text_display = text_options[0]
            elif isinstance(text_val, (int, float)):
                text_display = str(text_val)
            else:
                text_display = str(text_val or "")

            links.append({"target": target_display, "text": text_display})
            return links
        if isinstance(parsed, (int, float)):
            links.append({"target": int(parsed), "text": ""})
            return links
        text_val = str(parsed).strip()
        if text_val:
            links.append({"target": text_val, "text": text_val})
        return links

    if items is None:
        items = []
    elif not isinstance(items, (list, tuple)):
        items = [items]

    is_scenes_field = str(header or "").strip().lower() == "scenes"
    gm_view_ref = gm_view if is_scenes_field else None

    def _build_scene_key(index, data):
        if not isinstance(data, dict):
            return str(index)
        for key in ("Id", "ID", "Scene", "scene", "Title", "title"):
            value = data.get(key)
            if value:
                return f"{index}:{value}"
        return str(index)

    for idx, entry in enumerate(items, start=1):
        parsed_entry = deserialize_possible_json(entry)
        if isinstance(parsed_entry, dict):
            scene_dict = {key: deserialize_possible_json(val) for key, val in parsed_entry.items()}
        elif isinstance(parsed_entry, (list, tuple, set)):
            scene_dict = {"Text": list(parsed_entry)}
        else:
            scene_dict = {"Text": parsed_entry}

        text_payload = scene_dict.get("Text") or scene_dict.get("text") or ""
        text_payload = deserialize_possible_json(text_payload)
        if isinstance(text_payload, dict):
            nested_text = deserialize_possible_json(text_payload.get("text") or text_payload.get("Text") or "")
            if isinstance(nested_text, (list, tuple, set)):
                body_text = "\n".join(str(v).strip() for v in nested_text if str(v).strip())
            else:
                body_text = str(nested_text or "")
        elif isinstance(text_payload, (list, tuple, set)):
            body_text = "\n".join(str(v).strip() for v in text_payload if str(v).strip())
        else:
            body_text = str(text_payload or "")
        body_text = format_multiline_text(body_text, max_length=2000)

        title_value = scene_dict.get("Title") or scene_dict.get("Scene") or ""
        title_candidates = _flatten_strings(title_value)
        title_clean = title_candidates[0] if title_candidates else ""
        if title_clean:
            scene_dict["Title"] = title_clean

        npc_names = _coerce_names(scene_dict.get("NPCs"))
        creature_names = _coerce_names(scene_dict.get("Creatures"))
        place_names = _coerce_names(scene_dict.get("Places"))
        map_names = _coerce_names(scene_dict.get("Maps"))
        if entity_collector is not None:
            entity_collector.setdefault("NPCs", set()).update(npc_names)
            entity_collector.setdefault("Creatures", set()).update(creature_names)
            entity_collector.setdefault("Places", set()).update(place_names)
            entity_collector.setdefault("Maps", set()).update(map_names)
        links = _coerce_links(scene_dict.get("Links"))

        outer = ctk.CTkFrame(parent, fg_color="transparent")
        outer.pack(fill="x", expand=True, padx=20, pady=4)
        body = ctk.CTkFrame(outer, fg_color="transparent")

        body_label = ctk.CTkLabel(
            body,
            text=body_text or "(No scene notes)",
            wraplength=0,
            justify="left",
            font=("Arial", 14),
        )
        body_label.pack(fill="x", padx=12, pady=(6, 6))

        def _make_entity_section(names, label_text):
            if not names:
                return
            section = ctk.CTkFrame(body, fg_color="transparent")
            section.pack(fill="x", padx=12, pady=(0, 4))
            ctk.CTkLabel(section, text=f"{label_text}:", font=("Arial", 13, "bold"))\
                .pack(anchor="w")
            chips = ctk.CTkFrame(section, fg_color="transparent")
            chips.pack(fill="x", padx=10, pady=(2, 0))
            allow_entity_open = callable(open_entity_callback) and label_text != "Maps"
            for name in names:
                chip = ctk.CTkLabel(
                    chips,
                    text=name,
                    text_color="#00BFFF" if allow_entity_open else "white",
                    cursor="hand2" if allow_entity_open else "",
                )
                chip.pack(side="left", padx=4, pady=2)
                if allow_entity_open:
                    chip.bind(
                        "<Button-1>",
                        lambda _event=None, t=label_text, n=name: open_entity_callback(t, n)
                    )

        _make_entity_section(npc_names, "NPCs")
        _make_entity_section(creature_names, "Creatures")
        _make_entity_section(place_names, "Places")
        
        def _make_map_section(names):
            if not names:
                return
            interactive = bool(gm_view_ref and hasattr(gm_view_ref, "open_map_tool"))
            if not interactive:
                _make_entity_section(names, "Maps")
                return

            section = ctk.CTkFrame(body, fg_color="transparent")
            section.pack(fill="x", padx=12, pady=(0, 4))
            ctk.CTkLabel(section, text="Maps:", font=("Arial", 13, "bold"))\
                .pack(anchor="w")

            gallery = ctk.CTkFrame(section, fg_color="transparent")
            gallery.pack(fill="x", padx=10, pady=(2, 0))

            has_thumbnail_provider = hasattr(gm_view_ref, "get_map_thumbnail")

            for name in names:
                display_name = name or "(Unnamed Map)"
                tile = ctk.CTkFrame(gallery, fg_color="#2F2F2F", corner_radius=6)
                tile.pack(side="left", padx=4, pady=4)
                tile.configure(cursor="hand2")

                thumbnail = None
                if has_thumbnail_provider:
                    try:
                        thumbnail = gm_view_ref.get_map_thumbnail(name)
                    except Exception:
                        thumbnail = None

                if thumbnail:
                    img_label = CTkLabel(tile, image=thumbnail, text="")
                    img_label.image = thumbnail
                else:
                    img_label = CTkLabel(
                        tile,
                        text="No Image",
                        width=140,
                        height=90,
                        justify="center",
                    )
                img_label.pack(padx=6, pady=(6, 2))
                img_label.configure(cursor="hand2")

                name_label = CTkLabel(
                    tile,
                    text=display_name,
                    wraplength=140,
                    justify="center",
                )
                name_label.pack(padx=6, pady=(0, 6))
                name_label.configure(cursor="hand2")

                def _open_map(event, map_name=name):
                    try:
                        gm_view_ref.open_map_tool(map_name)
                    except Exception:
                        pass

                tile.bind("<Button-1>", _open_map)
                img_label.bind("<Button-1>", _open_map)
                name_label.bind("<Button-1>", _open_map)

        _make_map_section(map_names)

        if links:
            link_section = ctk.CTkFrame(body, fg_color="transparent")
            link_section.pack(fill="x", padx=12, pady=(4, 6))
            ctk.CTkLabel(link_section, text="Links:", font=("Arial", 13, "bold"))\
                .pack(anchor="w")
            for link in links:
                text_val = str(link.get("text") or "").strip()
                target_val = link.get("target")
                if isinstance(target_val, (int, float)):
                    target_display = f"Scene {int(target_val)}"
                elif target_val:
                    target_display = str(target_val)
                else:
                    target_display = "(unspecified)"
                if not text_val:
                    text_val = "(no link text)"
                CTkLabel(
                    link_section,
                    text=f"• {text_val} → {target_display}",
                    font=("Arial", 12),
                    justify="left",
                ).pack(anchor="w", padx=12, pady=1)

        expanded = ctk.BooleanVar(value=False)
        button_text = f"▶ Scene {idx}"
        if title_clean:
            button_text += f" – {title_clean}"
        note_title = f"Scene {idx}"
        if title_clean:
            note_title += f" – {title_clean}"

        scene_key = _build_scene_key(idx, scene_dict)

        if gm_view_ref:
            initial_state = False
            if hasattr(gm_view_ref, "get_scene_completion"):
                initial_state = bool(gm_view_ref.get_scene_completion(scene_key))
            check_var = ctk.BooleanVar(master=outer, value=initial_state)
            header_row = ctk.CTkFrame(outer, fg_color="transparent")
            header_row.pack(fill="x", expand=True)
            btn = ctk.CTkButton(
                header_row,
                text=button_text,
                fg_color="transparent",
                anchor="w",
            )
            checkbox = ctk.CTkCheckBox(
                header_row,
                text="",
                variable=check_var,
            )
            checkbox.pack(side="right", padx=(8, 0), pady=(2, 2))
        else:
            check_var = None
            checkbox = None
            btn = ctk.CTkButton(
                outer,
                text=button_text,
                fg_color="transparent",
                anchor="w",
            )

        def _toggle(btn=btn, body=body, lbl=body_label, expanded=expanded, idx=idx, title=title_clean, key=scene_key):
            if expanded.get():
                body.pack_forget()
                label = f"▶ Scene {idx}"
                if title:
                    label += f" – {title}"
                btn.configure(text=label)
            else:
                body.pack(fill="x", padx=8, pady=6)
                label = f"▼ Scene {idx}"
                if title:
                    label += f" – {title}"
                btn.configure(text=label)
                outer.update_idletasks()
                wrap_px = max(200, lbl.winfo_width())
                lbl.configure(wraplength=wrap_px)
                if gm_view_ref and hasattr(gm_view_ref, "set_active_scene"):
                    gm_view_ref.set_active_scene(key)
            expanded.set(not expanded.get())

        btn.configure(command=_toggle)
        if gm_view_ref:
            btn.pack(fill="x", expand=True, padx=(0, 4))
            if hasattr(gm_view_ref, "register_scene_widget") and check_var is not None:
                gm_view_ref.register_scene_widget(
                    scene_key,
                    check_var,
                    checkbox,
                    display_label=button_text,
                    description=body_text,
                    note_title=note_title,
                )

            def _on_check(key=scene_key):
                if gm_view_ref and hasattr(gm_view_ref, "set_active_scene"):
                    gm_view_ref.set_active_scene(key)

            checkbox.configure(command=_on_check)
            if hasattr(gm_view_ref, "set_active_scene"):
                btn.bind(
                    "<Button-1>",
                    lambda event, key=scene_key: gm_view_ref.set_active_scene(key),
                )
            menu_handler = getattr(gm_view_ref, "_show_context_menu", None)
            if callable(menu_handler):
                btn.bind("<Button-3>", menu_handler)
                btn.bind("<Control-Button-1>", menu_handler)
        else:
            btn.pack(fill="x", expand=True)

@log_function
def _collect_character_relationships(scenario_npcs=None):
    relationships = []
    seen = set()
    scenario_npc_set = None
    if scenario_npcs:
        scenario_npc_set = {str(name).strip().lower() for name in scenario_npcs if str(name).strip()}
    for entity_label, table_key in (("NPCs", "npcs"), ("PCs", "pcs")):
        if scenario_npc_set is not None and entity_label != "NPCs":
            continue
        wrapper = GenericModelWrapper(table_key)
        records = wrapper.load_items()
        for record in records:
            source_name = str(record.get("Name") or "").strip()
            if not source_name:
                continue
            if scenario_npc_set is not None and source_name.lower() not in scenario_npc_set:
                continue
            links = record.get("Links")
            if not isinstance(links, list):
                continue
            for link in links:
                if not isinstance(link, dict):
                    continue
                target_type_raw = str(
                    link.get("target_type")
                    or link.get("TargetType")
                    or link.get("targetType")
                    or ""
                ).lower()
                if target_type_raw not in {"npc", "pc"}:
                    continue
                target_name = str(
                    link.get("target_name")
                    or link.get("TargetName")
                    or link.get("target")
                    or ""
                ).strip()
                if not target_name:
                    continue
                if (
                    scenario_npc_set is not None
                    and target_type_raw == "npc"
                    and target_name.lower() not in scenario_npc_set
                ):
                    continue
                relation_text = str(
                    link.get("label")
                    or link.get("Label")
                    or link.get("text")
                    or ""
                ).strip()
                relation_text = relation_text or "(unspecified)"
                target_type = "NPCs" if target_type_raw == "npc" else "PCs"
                key = (entity_label, source_name, relation_text, target_type, target_name)
                if key in seen:
                    continue
                seen.add(key)
                relationships.append({
                    "source_type": entity_label,
                    "source_name": source_name,
                    "relation_text": relation_text,
                    "target_type": target_type,
                    "target_name": target_name,
                })

    relationships.sort(
        key=lambda entry: (
            entry.get("source_name", "").lower(),
            entry.get("target_name", "").lower(),
            entry.get("relation_text", "").lower(),
        )
    )
    return relationships

@log_function
def create_scenario_detail_frame(entity_type, scenario_item, master, open_entity_callback=None):
    """
    Build a scrollable detail view for a scenario with:
    1) A header zone (Title, Summary, Secrets)
    2) Then the rest of the fields, but NPCs always before Places.
    """
    frame = ctk.CTkFrame(master)
    frame.pack(fill="both", expand=True, padx=20, pady=10)
    gm_view_instance = getattr(open_entity_callback, "__self__", None)
    sections = {}
    pinned_sections = set()
    active_section = None
    section_order = ["Summary", "Scenes", "NPCs", "Creatures", "Places", "Secrets", "Notes"]
    section_names = []
    def rebuild_frame(updated_item):
        # 1) Destroy the old frame
        frame.destroy()

        # 2) Build a fresh one and pack it
        new_frame = create_scenario_detail_frame(
            entity_type,
            updated_item,
            master,
            open_entity_callback
        )
        new_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 3) Update the GM-view’s tabs dict so show_tab() refers to the new widget
        #    open_entity_callback is bound to the GMScreenView instance
        gm_view = getattr(open_entity_callback, "__self__", None)
        if gm_view is not None:
            # pick the right key—"Title" for scenarios, else "Name"
            key_field = "Title" if entity_type == "Scenarios" else "Name"
            tab_name = updated_item.get(key_field)
            if tab_name in gm_view.tabs:
                gm_view.tabs[tab_name]["content_frame"] = new_frame

    def _edit_entity():
        EditWindow(
            frame,
            scenario_item,
            load_template(entity_type.lower()),
            wrappers[entity_type],
            creation_mode=False,
            on_save=rebuild_frame,
        )

    frame.edit_entity = _edit_entity
    if gm_view_instance is not None:
        frame.bind("<Button-3>", gm_view_instance._show_context_menu)
        frame.bind("<Control-Button-1>", gm_view_instance._show_context_menu)

    layout = ctk.CTkFrame(frame, fg_color="transparent")
    layout.pack(fill="both", expand=True)
    layout.grid_columnconfigure(0, weight=0)
    layout.grid_columnconfigure(1, weight=1)
    layout.grid_rowconfigure(0, weight=1)

    nav_frame = ctk.CTkFrame(layout, width=220)
    nav_frame.grid(row=0, column=0, sticky="ns", padx=(0, 12))

    content_frame = ctk.CTkFrame(layout, fg_color="transparent")
    content_frame.grid(row=0, column=1, sticky="nsew")
    content_frame.grid_rowconfigure(0, weight=1)
    content_frame.grid_columnconfigure(0, weight=1)

    scrollable_frame = ctk.CTkScrollableFrame(content_frame)
    scrollable_frame.grid(row=0, column=0, sticky="nsew")

    def _get_section_frame(section_name):
        section_frame = sections.get(section_name)
        if section_frame is None:
            section_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
            sections[section_name] = section_frame
        return section_frame

    def _apply_section_visibility():
        visible_sections = set(pinned_sections)
        if active_section:
            visible_sections.add(active_section)

        for name in section_names:
            section_frame = sections.get(name)
            if section_frame is not None:
                section_frame.pack_forget()

        for name in section_names:
            if name in visible_sections:
                sections[name].pack(fill="x", expand=True, padx=10, pady=(0, 12))

    def show_section(section_name):
        nonlocal active_section
        active_section = section_name
        _apply_section_visibility()

    tabs = None

    def _toggle_pin(section_name):
        if section_name in pinned_sections:
            pinned_sections.discard(section_name)
        else:
            pinned_sections.add(section_name)
        _apply_section_visibility()
        if tabs is not None:
            tabs.set_pinned(pinned_sections)

    summary_section = _get_section_frame("Summary")
    ttk.Separator(summary_section, orient="horizontal").pack(fill="x", pady=1)
    CTkLabel(summary_section, text="Summary", font=("Arial", 18, "bold"))\
        .pack(anchor="w", pady=(0, 6))
    CTkLabel(
        summary_section,
        text=format_multiline_text(scenario_item.get("Summary", "")),
        font=("Arial", 16),
        wraplength=1620,
        justify="left"
    ).pack(fill="x", pady=(0, 15))

    # ——— BODY — prepare fields in the custom order ———
    tpl = load_template(entity_type.lower())
    scene_entity_tracker = {"NPCs": set(), "Creatures": set(), "Places": set(), "Maps": set()}
    # remove header fields
    body_fields = [
        f for f in tpl["fields"]
        if f["name"] not in ("Title", "Summary", "Secrets")
    ]

    
    # group them
    scenes_fields = [f for f in body_fields if f["name"] == "Scenes"]
    npc_fields   = [f for f in body_fields if f.get("linked_type") == "NPCs"]
    creature_fields = [f for f in body_fields if f.get("linked_type") == "Creatures"]
    place_fields = [f for f in body_fields if f.get("linked_type") == "Places"]
    other_fields = [f for f in body_fields if f not in scenes_fields +  npc_fields + place_fields + creature_fields]
    ordered_fields = scenes_fields + npc_fields + creature_fields + place_fields + other_fields

    if gm_view_instance and hasattr(gm_view_instance, "reset_scene_widgets"):
        gm_view_instance.reset_scene_widgets()

    section_map = {
        "Summary": "Summary",
        "Scenes": "Scenes",
        "NPCs": "NPCs",
        "Creatures": "Creatures",
        "Places": "Places",
        "Secrets": "Secrets",
        "Notes": "Notes",
    }

    # render in that order
    for field in ordered_fields:
        name  = field["name"]
        ftype = field["type"]
        value = scenario_item.get(name) or ""
        section_name = section_map.get(name, "Notes")
        section_frame = _get_section_frame(section_name)

        if ftype == "text":
            insert_text(section_frame, name, value)
        elif ftype == "list_longtext":
            if name == "Scenes" and gm_view_instance is not None:
                scenes_container = ctk.CTkFrame(section_frame, fg_color="transparent")
                scenes_container.pack(fill="both", expand=True, padx=10, pady=(10, 2))

                header_row = ctk.CTkFrame(scenes_container, fg_color="transparent")
                header_row.pack(fill="x", padx=10, pady=(0, 4))
                ctk.CTkLabel(
                    header_row,
                    text="Scenes:",
                    font=("Arial", 16, "bold"),
                ).pack(side="left")

                view_var = tk.StringVar(value="Scene Flow")
                view_toggle = ctk.CTkSegmentedButton(
                    header_row,
                    values=["List", "Scene Flow"],
                    variable=view_var,
                )
                view_toggle.pack(side="right")

                list_container = ctk.CTkFrame(scenes_container, fg_color="transparent")
                list_container.pack(fill="x", expand=True)

                insert_list_longtext(
                    list_container,
                    name,
                    value,
                    open_entity_callback,
                    entity_collector=scene_entity_tracker,
                    gm_view=gm_view_instance,
                    show_header=False,
                )

                flow_container = ctk.CTkFrame(scenes_container, fg_color="transparent", height=520)
                flow_container.pack_propagate(False)
                scenario_title = str(
                    scenario_item.get("Title") or scenario_item.get("Name") or ""
                ).strip()
                scene_flow_frame = create_scene_flow_frame(
                    flow_container,
                    scenario_title=scenario_title,
                )
                scene_flow_frame.pack(fill="both", expand=True)

                def _toggle_scene_view(selected_view=None):
                    selection = selected_view or view_var.get()
                    if selection == "Scene Flow":
                        list_container.pack_forget()
                        flow_container.pack(fill="both", expand=True, padx=10, pady=(6, 0))
                        scene_flow_frame.after_idle(scene_flow_frame._on_layout_resize)
                    else:
                        flow_container.pack_forget()
                        list_container.pack(fill="x", expand=True)

                view_toggle.configure(command=_toggle_scene_view)
                _toggle_scene_view("Scene Flow")
            else:
                insert_list_longtext(
                    section_frame,
                    name,
                    value,
                    open_entity_callback,
                    entity_collector=scene_entity_tracker,
                    gm_view=gm_view_instance,
                )
        elif ftype == "longtext":
            insert_longtext(section_frame, name, value)
        elif ftype == "list":
            linked = field.get("linked_type")
            items  = value if isinstance(value, list) else []
            if linked == "NPCs":
                insert_npc_table(section_frame, "NPCs", items, open_entity_callback)
            elif linked == "Creatures":
                filtered_creatures = [
                    creature for creature in items
                    if creature not in scene_entity_tracker.get("Creatures", set())
                ]
                if not filtered_creatures:
                    continue
                insert_creature_table(section_frame, "Creatures", filtered_creatures, open_entity_callback)
            elif linked == "Places":
                insert_places_table(section_frame, "Places", items, open_entity_callback)
            else:
                insert_links(section_frame, name, items, linked, open_entity_callback)

    insert_relationship_table(
        _get_section_frame("NPCs"),
        "Relationship Table",
        _collect_character_relationships(scenario_item.get("NPCs")),
        open_entity_callback,
    )

    secrets_section = _get_section_frame("Secrets")
    ttk.Separator(secrets_section, orient="horizontal").pack(fill="x", pady=1)
    CTkLabel(secrets_section, text="Secrets", font=("Arial", 18, "bold"))\
        .pack(anchor="w", pady=(0, 5))
    CTkLabel(
        secrets_section,
        text=format_multiline_text(scenario_item.get("Secrets", "")),
        font=("Arial", 16),
        wraplength=1620,
        justify="left"
    ).pack(fill="x", pady=(0, 15))

    if gm_view_instance and hasattr(gm_view_instance, "register_note_widget"):
        notes_section = _get_section_frame("Notes")
        ctk.CTkLabel(
            notes_section,
            text="GM Notes",
            font=("Arial", 16, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        toolbar = ctk.CTkFrame(notes_section, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 6))
        add_timestamp = getattr(gm_view_instance, "add_timestamped_note", None)
        if callable(add_timestamp):
            ctk.CTkButton(
                toolbar,
                text="Add Timestamp",
                command=add_timestamp,
                width=140,
            ).pack(side="left", padx=(0, 6))
        open_editor = getattr(gm_view_instance, "open_note_editor", None)
        if callable(open_editor):
            ctk.CTkButton(
                toolbar,
                text="Edit Notes",
                command=open_editor,
                width=140,
            ).pack(side="left", padx=(0, 6))

        note_box = CTkTextbox(notes_section, wrap="word", height=160)
        note_box.pack(fill="both", expand=True)
        gm_view_instance.register_note_widget(note_box)

    section_names = [name for name in section_order if name in sections]
    for name in sections:
        if name not in section_names:
            section_names.append(name)

    tabs = VerticalSectionTabs(nav_frame, section_names, show_section, on_pin_toggle=_toggle_pin)
    tabs.pack(fill="x", padx=8, pady=8)
    tabs.set_pinned(pinned_sections)

    if section_names:
        tabs.set_active(section_names[0])
        show_section(section_names[0])
    return frame

@log_function
def EditWindow(self, item, template, model_wrapper, creation_mode=False, on_save=None):
    key_field = "Title" if model_wrapper.entity_type in {"scenarios", "books"} else "Name"
    key_value = item.get(key_field)
    target = None
    if key_value:
        target = model_wrapper.load_item_by_key(key_value, key_field=key_field)
    if target is None:
        target = dict(item)
    editor = GenericEditorWindow(
        self, target, template,
        model_wrapper, creation_mode
    )
    self.master.wait_window(editor)
    if getattr(editor, "saved", False):
        model_wrapper.save_item(
            target,
            key_field=key_field,
            original_key_value=key_value,
        )
        # let the detail frame know it should refresh itself
        if callable(on_save):
            on_save(target)


@log_function
def create_entity_detail_frame(entity_type, entity, master, open_entity_callback=None):
    """
    Routes Scenarios through our custom header/body and
    everything else through the generic detail path.
    """
    if entity_type == "Scenarios":
        return create_scenario_detail_frame(
            entity_type,
            entity,
            master,
            open_entity_callback
        )

    # Create the actual content frame inside the scrollable container.
    content_frame = ctk.CTkFrame(master)
    content_frame.pack(fill="both", expand=True, padx=10, pady=10)
    gm_view_instance = getattr(open_entity_callback, "__self__", None)

    # rebuild_frame will clear & re-populate this same content_frame
    def rebuild_frame(updated_item):
        # 1) Destroy the old frame
        content_frame.destroy()

        # 2) Build a fresh one and pack it
        new_frame = create_entity_detail_frame(
            entity_type,
            updated_item,
            master,
            open_entity_callback
        )
        new_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 3) Update the GM-view’s tabs dict so show_tab() refers to the new widget
        #    open_entity_callback is bound to the GMScreenView instance
        gm_view = getattr(open_entity_callback, "__self__", None)
        if gm_view is not None:
            # pick the right key—"Title" for scenarios, else "Name"
            key_field = "Title" if entity_type == "Scenarios" else "Name"
            tab_name = updated_item.get(key_field)
            if tab_name in gm_view.tabs:
                gm_view.tabs[tab_name]["content_frame"] = new_frame

    def _edit_entity():
        EditWindow(
            content_frame,
            entity,
            load_template(entity_type.lower()),
            wrappers[entity_type],
            creation_mode=False,
            on_save=rebuild_frame,
        )

    content_frame.edit_entity = _edit_entity
    if gm_view_instance is not None:
        content_frame.bind("<Button-3>", gm_view_instance._show_context_menu)
        content_frame.bind("<Control-Button-1>", gm_view_instance._show_context_menu)
        

    audio_value = get_entity_audio_value(entity)
    entity_label = entity.get("Name") or entity.get("Title") or entity_type[:-1]

    def _audio_display_name(value: str) -> str:
        if not value:
            return "🎵 Audio"
        base = os.path.basename(str(value)) or "Audio"
        resolved = resolve_audio_path(value)
        if resolved and os.path.exists(resolved):
            return f"🎵 {base}"
        return f"🎵 {base} (missing)"

    def _play_audio_from_menu() -> None:
        if not audio_value:
            messagebox.showinfo("Audio", "No audio file configured for this entry.")
            return
        if not play_entity_audio(audio_value, entity_label=str(entity_label)):
            messagebox.showwarning("Audio", "Unable to play the associated audio track.")

    if audio_value:
        button_bar = ctk.CTkFrame(content_frame)
        button_bar.pack(fill="x", pady=(0, 10))

        audio_label = ctk.CTkLabel(
            button_bar,
            text=_audio_display_name(audio_value),
            cursor="hand2",
        )

        def _show_audio_menu(event) -> None:
            menu = tk.Menu(button_bar, tearoff=0)
            menu.add_command(label="Play Audio", command=_play_audio_from_menu)
            menu.add_command(label="Stop Audio", command=stop_entity_audio)
            menu.tk_popup(event.x_root, event.y_root)

        audio_label.bind("<Button-3>", _show_audio_menu)
        audio_label.pack(side="right", padx=(0, 6), pady=6)

    # This local cache is used for portrait images (if any).
    content_frame.portrait_images = {}

    # If the entity has a valid Portrait, load and show it for portrait-capable types.
    portrait_path = primary_portrait(entity.get("Portrait"))
    if (entity_type in {"NPCs", "PCs", "Creatures", "Factions"}):
        resolved_portrait = resolve_portrait_path(portrait_path, ConfigHelper.get_campaign_dir())
        if resolved_portrait and os.path.exists(resolved_portrait):
            try:
                img = Image.open(resolved_portrait)
                img = img.resize(PORTRAIT_SIZE, Image.Resampling.LANCZOS)
                ctk_image = CTkImage(light_image=img, size=PORTRAIT_SIZE)
                portrait_label = CTkLabel(content_frame, image=ctk_image, text="")
                portrait_label.image = ctk_image  # persist reference
                portrait_label.entity_name = entity.get("Name", "")
                portrait_label.is_portrait = True
                content_frame.portrait_images[entity.get("Name", "")] = ctk_image
                _attach_portrait_tooltip(portrait_label, entity_type, entity)
                portrait_label.bind(
                    "<Button-1>",
                    lambda e, p=portrait_path, n=portrait_label.entity_name: show_portrait(p, n)
                )
                portrait_label.pack(pady=10)
                content_frame.portrait_label = portrait_label
            except Exception as e:
                print(f"[DEBUG] Error loading portrait for {entity.get('Name','')}: {e}")

    # Create fields from the template.
    template = load_template(entity_type.lower())
    for field in template["fields"]:
        field_name = field["name"]
        field_type = field["type"]
        # Skip the Portrait field if already handled.
        if (entity_type in {"NPCs", "PCs", "Creatures", "Factions"}) and field_name == "Portrait":
            continue
        if field_type == "longtext":
            insert_longtext(content_frame, field_name, entity.get(field_name, ""))
        elif field_type == "text":
            insert_text(content_frame, field_name, entity.get(field_name, ""))
        elif field_type == "list":
            linked_type = field.get("linked_type", None)
            if linked_type:
                insert_links(content_frame, field_name, entity.get(field_name) or [], linked_type, open_entity_callback)
    # Return the scrollable container so that whoever creates the window or tab gets a frame with scrollbars.
    return content_frame

@log_function
def open_entity_window(entity_type, name):
    log_info(f"Opening entity window for {entity_type}: {name}", func_name="open_entity_window")
    wrapper = wrappers[entity_type]
    items = wrapper.load_items()
    key = "Title" if entity_type == "Scenarios" else "Name"
    entity = next((i for i in items if i.get(key) == name), None)
    if not entity:
        messagebox.showerror("Error", f"{entity_type[:-1]} '{name}' not found.")
        return

    new_window = ctk.CTkToplevel()
    new_window.title(f"{entity_type[:-1]}: {name}")
    new_window.geometry("1000x600")
    new_window.minsize(1000, 600)
    new_window.configure(padx=10, pady=10)

    scrollable_container = ctk.CTkScrollableFrame(new_window)
    scrollable_container.pack(fill="both", expand=True)

    detail_frame = create_entity_detail_frame(
        entity_type, entity, master=scrollable_container,
        open_entity_callback=open_entity_window
    )
    detail_frame.pack(fill="both", expand=True)
