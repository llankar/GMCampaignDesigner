import os
import customtkinter as ctk
from PIL import Image
from customtkinter import CTkLabel, CTkImage, CTkTextbox
from modules.helpers.text_helpers import format_longtext, format_multiline_text
from modules.helpers.template_loader import load_template
from modules.generic.generic_model_wrapper import GenericModelWrapper
from tkinter import Toplevel, messagebox
from tkinter import ttk
import tkinter.font as tkfont
import tkinter as tk
from modules.ui.image_viewer import show_portrait
from modules.ui.tooltip import ToolTip
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.helpers.config_helper import ConfigHelper
from modules.audio.entity_audio import play_entity_audio, resolve_audio_path, stop_entity_audio
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_module_import,
)

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

    name_field = "Title" if entity_type == "Scenarios" else "Name"
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
        }

@log_function
def insert_text(parent, header, content):
    label = ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 16, "bold"))
    label.pack(anchor="w", padx=10)
    box = ctk.CTkTextbox(parent, wrap="word", height=40)
    # Ensure content is a plain string.
    if isinstance(content, dict):
        content = content.get("text", "")
    elif isinstance(content, list):
        content = " ".join(map(str, content))
    else:
        content = str(content)
    # For debugging, you can verify:
    # print("DEBUG: content =", repr(content))

    # Override the insert method to bypass the CTkTextbox wrapper.
    box.insert = box._textbox.insert
    # Now use box.insert normally.
    box.insert("1.0", content)

    box.configure(state="disabled")
    box.pack(fill="x", padx=10, pady=5)

@log_function
def insert_longtext(parent, header, content):
    ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 16, "bold")).pack(anchor="w", padx=10)

    # Convert to string and format
    if isinstance(content, dict):
        text = content.get("text", "")
    else:
        text = str(content)
    formatted_text = format_multiline_text(text, max_length=2000)

    box = CTkTextbox(parent, wrap="word")
    box.insert = box._textbox.insert
    box.insert("1.0", formatted_text)
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
        label = CTkLabel(parent, text=item, text_color="#00BFFF", cursor="hand2")
        label.pack(anchor="w", padx=10)
        if open_entity_callback is not None:
            # Capture the current values with lambda defaults.
            label.bind("<Button-1>", lambda event, l=linked_type, i=item: open_entity_callback(l, i))


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

    items = wrapper.load_items()
    key_field = "Title" if entity_type == "Scenarios" else "Name"
    item = next((i for i in items if i.get(key_field) == name), None)
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
        portrait_path = data.get("Portrait")
        if portrait_path and not os.path.isabs(portrait_path):
            candidate = os.path.join(ConfigHelper.get_campaign_dir(), portrait_path)
            if os.path.exists(candidate):
                portrait_path = candidate
        if portrait_path and os.path.exists(portrait_path):
            img = Image.open(portrait_path).resize((40,40), Image.Resampling.LANCZOS)
            photo = CTkImage(light_image=img, size=(40,40))
            widget = CTkLabel(table, image=photo, text="", anchor="center")
            widget.image = photo
            _attach_portrait_tooltip(widget, "NPCs", data)
            # clicking the thumbnail pops up the full‑screen viewer
            widget.bind(
                "<Button-1>",
                lambda e, p=portrait_path, n=name: show_portrait(p, n)
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
                            lambda e, nm=name: open_entity_callback("NPCs", nm)
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
        portrait_path = data.get("Portrait")
        if portrait_path and not os.path.isabs(portrait_path):
            candidate = os.path.join(ConfigHelper.get_campaign_dir(), portrait_path)
            if os.path.exists(candidate):
                portrait_path = candidate
        if portrait_path and os.path.exists(portrait_path):
            img = Image.open(portrait_path).resize((40,40), Image.Resampling.LANCZOS)
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
        portrait = data.get("Portrait", "")
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
                if portrait and os.path.exists(portrait):
                    img   = Image.open(portrait).resize((40, 40), Image.Resampling.LANCZOS)
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
def insert_list_longtext(parent, header, items, open_entity_callback=None, entity_collector=None, gm_view=None):
    """Insert collapsible sections for long text lists such as scenario scenes."""
    ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 16, "bold")) \
        .pack(anchor="w", padx=10, pady=(10, 2))

    def _coerce_names(value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, (set, tuple)):
            return [str(v).strip() for v in value if str(v).strip()]
        text = str(value).strip()
        if not text:
            return []
        parts = [part.strip() for part in text.split(",") if part.strip()]
        return parts or [text]

    def _coerce_links(value):
        links = []
        if value is None:
            return links
        if isinstance(value, list):
            for item in value:
                links.extend(_coerce_links(item))
            return links
        if isinstance(value, dict):
            target = None
            text = None
            for key in ("Target", "target", "Scene", "scene", "Next", "next", "Id", "id", "Reference", "reference"):
                if key in value:
                    target = value[key]
                    break
            for key in ("Text", "text", "Label", "label", "Description", "description", "Choice", "choice"):
                if key in value:
                    text = value[key]
                    break
            links.append({"target": target, "text": text})
            return links
        if isinstance(value, (int, float)):
            links.append({"target": int(value), "text": ""})
            return links
        text_val = str(value).strip()
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
        scene_dict = entry if isinstance(entry, dict) else {"Text": entry}
        text_payload = scene_dict.get("Text") or scene_dict.get("text") or ""
        if isinstance(text_payload, dict):
            body_text = text_payload.get("text", "")
        elif isinstance(text_payload, list):
            body_text = "\n".join(str(v) for v in text_payload if v)
        else:
            body_text = str(text_payload or "")
        body_text = format_multiline_text(body_text, max_length=2000)

        title_value = scene_dict.get("Title") or scene_dict.get("Scene") or ""
        title_clean = str(title_value).strip()

        npc_names = _coerce_names(scene_dict.get("NPCs"))
        creature_names = _coerce_names(scene_dict.get("Creatures"))
        place_names = _coerce_names(scene_dict.get("Places"))
        if entity_collector is not None:
            entity_collector.setdefault("NPCs", set()).update(npc_names)
            entity_collector.setdefault("Creatures", set()).update(creature_names)
            entity_collector.setdefault("Places", set()).update(place_names)
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
            for name in names:
                chip = ctk.CTkLabel(
                    chips,
                    text=name,
                    text_color="#00BFFF" if callable(open_entity_callback) else "white",
                    cursor="hand2" if callable(open_entity_callback) else "",
                )
                chip.pack(side="left", padx=4, pady=2)
                if callable(open_entity_callback):
                    chip.bind("<Button-1>", lambda e, t=label_text, n=name: open_entity_callback(t, n))

        _make_entity_section(npc_names, "NPCs")
        _make_entity_section(creature_names, "Creatures")
        _make_entity_section(place_names, "Places")

        if links:
            link_section = ctk.CTkFrame(body, fg_color="transparent")
            link_section.pack(fill="x", padx=12, pady=(4, 6))
            ctk.CTkLabel(link_section, text="Links:", font=("Arial", 13, "bold"))\
                .pack(anchor="w")
            for link in links:
                text_val = str(link.get("text") or "Continue").strip()
                target_val = link.get("target")
                if isinstance(target_val, (int, float)):
                    target_display = f"Scene {int(target_val)}"
                elif target_val:
                    target_display = str(target_val)
                else:
                    target_display = "(unspecified)"
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
                gm_view_ref.register_scene_widget(scene_key, check_var, checkbox, display_label=button_text)

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
def create_scenario_detail_frame(entity_type, scenario_item, master, open_entity_callback=None):
    """
    Build a scrollable detail view for a scenario with:
    1) A header zone (Title, Summary, Secrets)
    2) Then the rest of the fields, but NPCs always before Places.
    """
    frame = ctk.CTkFrame(master)
    frame.pack(fill="both", expand=True, padx=20, pady=10)
    gm_view_instance = getattr(open_entity_callback, "__self__", None)
    edit_btn = ctk.CTkButton(
        frame,
        text="Edit",
        command=lambda et=entity_type, en=scenario_item: EditWindow(
            frame,
            en,
            load_template(et.lower()),
            wrappers[et],
            creation_mode=False,
            on_save=rebuild_frame
        )
    )
    edit_btn.pack(anchor="ne", padx=10, pady=(0, 10))
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
        
    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=1)
    # ——— HEADER ———
    CTkLabel(
        frame,
        text=format_longtext(scenario_item.get("Summary", "")),
        font=("Arial", 16),
        wraplength=1620,
        justify="left"
    ).pack(fill="x", pady=(0, 15))
    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # ——— BODY — prepare fields in the custom order ———
    tpl = load_template(entity_type.lower())
    scene_entity_tracker = {"NPCs": set(), "Creatures": set(), "Places": set()}
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

    # render in that order
    for field in ordered_fields:
        name  = field["name"]
        ftype = field["type"]
        value = scenario_item.get(name) or ""

        if ftype == "text":
            insert_text(frame, name, value)
        elif ftype == "list_longtext":
            insert_list_longtext(
                frame,
                name,
                value,
                open_entity_callback,
                entity_collector=scene_entity_tracker,
                gm_view=gm_view_instance,
            )
        elif ftype == "longtext":
            insert_longtext(frame, name, value)
        elif ftype == "list":
            linked = field.get("linked_type")
            items  = value if isinstance(value, list) else []
            if linked == "NPCs":
                insert_npc_table(frame, "NPCs", items, open_entity_callback)
            elif linked == "Creatures":
                filtered_creatures = [
                    creature for creature in items
                    if creature not in scene_entity_tracker.get("Creatures", set())
                ]
                if not filtered_creatures:
                    continue
                insert_creature_table(frame, "Creatures", filtered_creatures, open_entity_callback)
            elif linked == "Places":
                insert_places_table(frame, "Places", items, open_entity_callback)
            else:
                insert_links(frame, name, items, linked, open_entity_callback)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=1)
    CTkLabel(frame, text="Secrets", font=("Arial", 18))\
    .pack(anchor="w", pady=(0, 5))
    CTkLabel(
        frame,
        text=format_longtext(scenario_item.get("Secrets", "")),
        font=("Arial", 16),
        wraplength=1620,
        justify="left"
    ).pack(fill="x", pady=(0, 15))
    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    if gm_view_instance and hasattr(gm_view_instance, "register_note_widget"):
        notes_section = ctk.CTkFrame(frame, fg_color="transparent")
        notes_section.pack(fill="both", expand=True, padx=10, pady=(0, 10))
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

        note_box = CTkTextbox(notes_section, wrap="word", height=160)
        note_box.pack(fill="both", expand=True)
        gm_view_instance.register_note_widget(note_box)
    return frame

@log_function
def EditWindow(self, item, template, model_wrapper, creation_mode=False, on_save=None):
    # load the full list so saves actually persist
    items = model_wrapper.load_items()
    key_field = "Title" if model_wrapper.entity_type == "scenarios" else "Name"
    # 3) Find the same dict in our list and edit *that*
    target = next((it for it in items if it.get(key_field) == item.get(key_field)), None)
    if target is None:
        # Fallback: fall back to editing the passed-in dict, and append if new
        target = item
        items.append(target)
    editor = GenericEditorWindow(
        self, target, template,
        model_wrapper, creation_mode
    )
    self.master.wait_window(editor)
    if getattr(editor, "saved", False):
        model_wrapper.save_items(items)
        # let the detail frame know it should refresh itself
        if callable(on_save):
            on_save(target)
   # 2) Identify the unique key field ("Title" for scenarios, else "Name")
  
        
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

    # Create a scrollable container instead of a plain frame.
    
    # Create the actual content frame inside the scrollable container.
    content_frame = ctk.CTkFrame(master)
    content_frame.pack(fill="both", expand=True, padx=10, pady=10)
    # — Add an “Edit” button so GMs can open the generic editor for this entity —

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
        gm_view = open_entity_callback.__self__
        # pick the right key—"Title" for scenarios, else "Name"
        key_field = "Title" if entity_type == "Scenarios" else "Name"
        tab_name = updated_item.get(key_field)
        gm_view.tabs[tab_name]["content_frame"] = new_frame
        

    button_bar = ctk.CTkFrame(content_frame)
    button_bar.pack(fill="x", pady=(0, 10))

    audio_value = entity.get("Audio") or ""
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

    edit_btn = ctk.CTkButton(
        button_bar,
        text="Edit",
        command=lambda et=entity_type, en=entity: EditWindow(
            content_frame,
            en,
            load_template(et.lower()),
            wrappers[et],
            creation_mode=False,
            on_save=rebuild_frame
        )
    )

    edit_btn.pack(side="right", padx=10, pady=6)

    # This local cache is used for portrait images (if any).
    content_frame.portrait_images = {}

    # If entity_type is "NPCs" and the entity has a valid Portrait, load and show it.
    portrait_path = entity.get("Portrait")
    if (entity_type in {"NPCs", "PCs", "Creatures"}) :
        if portrait_path and not os.path.isabs(portrait_path):
            candidate = os.path.join(ConfigHelper.get_campaign_dir(), portrait_path)
            if os.path.exists(candidate):
                portrait_path = candidate
        if portrait_path and os.path.exists(portrait_path):
            try:
                img = Image.open(portrait_path)
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
        if (entity_type == "NPCs" or entity_type == "PCs" or entity_type == "Creatures") and field_name == "Portrait":
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
