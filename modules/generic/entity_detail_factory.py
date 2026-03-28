import os
import re
import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk
from customtkinter import CTkImage, CTkLabel, CTkTextbox
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
from modules.helpers.layout_scheduler import LayoutSettleScheduler
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
from modules.scenarios.widgets.scene_body_sections import build_scene_body_sections
from modules.scenarios.widgets.scene_density import (
    DEFAULT_SCENE_DENSITY,
    SCENE_DENSITY_MODES,
    get_scene_density_style,
    normalize_scene_density,
)
from modules.ui.vertical_section_tabs import VerticalSectionTabs
from modules.events.ui.shared.related_events_panel import RelatedEventsPanel
from modules.generic.detail_ui import (
    build_scroll_host,
    create_chip,
    create_detail_split_layout,
    create_hero_header,
    create_highlight_card,
    create_section_card,
    create_spotlight_panel,
    estimate_field_height,
    get_detail_palette,
    get_link_color,
    get_textbox_style,
)
from modules.generic.detail_ui.window_geometry import apply_fullscreen_top_left
from modules.generic.entities.linking import resolve_entity_label, resolve_entity_slug
from modules.generic.scene_indicator_payload import build_scene_indicator_payload

log_module_import(__name__)

# Configure portrait size.
PORTRAIT_SIZE = (320, 420)
HERO_PORTRAIT_SIZE = (280, 240)
DEFAULT_PORTRAIT_PLACEMENT = "spotlight"
_open_entity_windows = {}


def _portrait_debug(entity_type, entity, message):
    entity_name = ""
    if isinstance(entity, dict):
        entity_name = str(entity.get("Name") or entity.get("Title") or "").strip()
    label = entity_name or "<unnamed>"
  

def _bring_window_to_front(window, parent=None):
    try:
        if parent is not None:
            window.transient(parent)
    except Exception:
        pass
    try:
        window.deiconify()
    except Exception:
        pass
    try:
        window.lift()
    except Exception:
        pass
    try:
        window.focus_force()
    except Exception:
        pass
    try:
        window.attributes("-topmost", True)
        window.after_idle(lambda: window.attributes("-topmost", False))
    except Exception:
        pass


def _compute_wraplength_from_widths(*candidate_widths, minimum=200, safety_margin=32):
    """Return a conservative wrap length from the narrowest usable container width."""

    usable_widths = []
    for width in candidate_widths:
        try:
            width_value = int(width or 0)
        except Exception:
            continue
        if width_value > 1:
            usable_widths.append(width_value)
    if not usable_widths:
        return minimum
    return max(minimum, min(usable_widths) - max(0, int(safety_margin)))


def _configure_wraplength_if_changed(label, *candidate_widths, minimum=200, safety_margin=32):
    wrap_px = _compute_wraplength_from_widths(
        *candidate_widths,
        minimum=minimum,
        safety_margin=safety_margin,
    )
    if getattr(label, "_last_wraplength", None) == wrap_px:
        return wrap_px
    label._last_wraplength = wrap_px
    label.configure(wraplength=wrap_px)
    return wrap_px


TOOLTIP_FIELDS = {
    "NPCs": ("Role", "Secret", "Traits", "Motivation"),
    "Villains": ("Archetype", "ThreatLevel", "Scheme", "CurrentObjective"),
    "Creatures": ("Type", "Stats", "Powers", "Weakness", "Background"),
    "PCs": ("Role", "Traits", "Secret", "Background"),
    "Places": ("Description", "Secrets"),
    "Bases": ("Location", "Upgrades", "Threats", "DowntimeHooks"),
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

def _wrapper_for(entity_type: str):
    slug = resolve_entity_slug(entity_type)
    if not slug:
        return None
    try:
        return GenericModelWrapper(slug)
    except Exception:
        return None

@log_function
def _open_book_link(parent, book_title: str) -> None:
    title = str(book_title or "").strip()
    if not title:
        return
    wrapper = _wrapper_for("Books")
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

def _adaptive_wraplength(widget, min_width=320, padding=40):
    try:
        return max(min_width, widget.winfo_width() - padding)
    except Exception:
        return min_width


def _spotlight_fallback(entity_type: str) -> str:
    label = entity_type[:-1] if entity_type.endswith("s") else entity_type
    return f"No {label.lower()} portrait is linked yet."


def _collect_highlight_lines(entity_type, entity):
    preferred_fields = TOOLTIP_FIELDS.get(entity_type, ())
    lines = []
    for field in preferred_fields:
        if field in {"Portrait", "Name", "Title"}:
            continue
        raw_value = entity.get(field)
        text = _format_tooltip_value(raw_value, max_length=140)
        if text:
            lines.append(f"{field}: {text}")
        if len(lines) >= 4:
            break
    return lines


def _build_portrait_widget(parent, entity_type, entity, *, size):
    portrait_sources = (
        ("Portrait", entity.get("Portrait")),
        ("Image", entity.get("Image")),
    )
    portrait_path = ""
    resolved_portrait = None
    campaign_dir = ConfigHelper.get_campaign_dir()

    _portrait_debug(
        entity_type,
        entity,
        f"starting widget build with size={size}, campaign_dir='{campaign_dir}'",
    )

    for field_name, portrait_value in portrait_sources:
        portrait_path = primary_portrait(portrait_value)
        resolved_portrait = resolve_portrait_path(portrait_value, campaign_dir)
        resolved_exists = bool(resolved_portrait and os.path.exists(resolved_portrait))
        _portrait_debug(
            entity_type,
            entity,
            (
                f"field={field_name}, raw={portrait_value!r}, primary={portrait_path!r}, "
                f"resolved={resolved_portrait!r}, exists={resolved_exists}"
            ),
        )
        if resolved_exists:
            break
    else:
        _portrait_debug(entity_type, entity, "no usable portrait path found; returning without widget")
        return None, portrait_path

    try:
        _portrait_debug(entity_type, entity, f"loading portrait image from '{resolved_portrait}'")
        img = Image.open(resolved_portrait).convert("RGBA")
        framed_image = ImageOps.fit(
            img,
            size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

        portrait_shell = ctk.CTkFrame(parent, fg_color="transparent")
        portrait_shell.pack_propagate(False)
        portrait_shell.configure(width=size[0], height=size[1])

        photo_image = ImageTk.PhotoImage(framed_image)
        portrait_widget = tk.Label(
            portrait_shell,
            image=photo_image,
            text="",
            bg=portrait_shell._apply_appearance_mode(["#DBDBDB", "#2B2B2B"]),
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
        )
        portrait_widget.pack(fill="both", expand=True)
        portrait_widget.image = photo_image
        portrait_shell.image = photo_image
        portrait_shell.entity_name = entity.get("Name") or entity.get("Title") or ""
        portrait_shell.is_portrait = True
        _attach_portrait_tooltip(portrait_widget, entity_type, entity)
        portrait_widget.bind(
            "<Button-1>",
            lambda _event=None, p=portrait_path, n=portrait_shell.entity_name: show_portrait(p, n)
        )
        _portrait_debug(
            entity_type,
            entity,
            (
                f"portrait widget ready using source={portrait_path!r}, resolved={resolved_portrait!r}, "
                f"cover_image={framed_image.width}x{framed_image.height}, fitted_to={size}"
            ),
        )
        return portrait_shell, portrait_path
    except Exception as exc:
        _portrait_debug(entity_type, entity, f"error loading portrait: {exc}")
        return None, portrait_path


def _populate_generic_columns(columns, fields, entity, open_entity_callback):
    column_heights = [0 for _ in columns]
    for field in fields:
        field_name = field["name"]
        field_type = field["type"]
        linked_type = field.get("linked_type")
        value = entity.get(field_name, "")

        target_index = min(range(len(columns)), key=lambda idx: column_heights[idx])
        parent = columns[target_index]

        if field_type == "longtext":
            insert_longtext(parent, field_name, value)
        elif field_type == "text":
            insert_text(parent, field_name, value)
        elif field_type == "list":
            items = value or []
            if linked_type:
                insert_links(parent, field_name, items, linked_type, open_entity_callback)

        column_heights[target_index] += estimate_field_height(field_type, value)


@log_function
def insert_text(parent, header, content):
    card, body = create_section_card(parent, header, compact=True)
    card.pack(fill="x", padx=10, pady=(0, 12))
    box = ctk.CTkTextbox(body, wrap="word", height=58, **get_textbox_style())
    render_rtf_to_text_widget(box, content)
    box.configure(state="disabled")
    box.pack(fill="x")


@log_function
def insert_longtext(parent, header, content):
    card, body = create_section_card(parent, header)
    card.pack(fill="x", padx=10, pady=(0, 12))
    box = CTkTextbox(body, wrap="word", **get_textbox_style())
    render_rtf_to_text_widget(box, content)
    box.pack(fill="x")

    def update_height():
        lines = int(box._textbox.count("1.0", "end", "lines")[0])
        font = tkfont.Font(font=box._textbox.cget("font"))
        line_px = font.metrics("linespace")
        box.configure(height=max(4, lines + 2) * line_px)
        box.configure(state="disabled")

    box.after_idle(update_height)


@log_function
def insert_links(parent, header, items, linked_type, open_entity_callback):
    card, body = create_section_card(parent, header, compact=True)
    card.pack(fill="x", padx=10, pady=(0, 12))
    links_row = ctk.CTkFrame(body, fg_color="transparent")
    links_row.pack(fill="x")
    has_items = False
    for item in items:
        display_text = str(item).strip()
        if not display_text:
            continue
        has_items = True
        chip = create_chip(links_row, display_text)
        chip.pack(side="left", padx=(0, 8), pady=(0, 8))
        label = ctk.CTkLabel(
            chip,
            text=display_text,
            text_color=get_link_color(),
            cursor="hand2",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        label.place(relx=0.5, rely=0.5, anchor="center")
        if linked_type == "Books":
            label.bind("<Button-1>", lambda _event, title=display_text: _open_book_link(parent, title))
        elif open_entity_callback is not None:
            label.bind("<Button-1>", lambda event, l=linked_type, i=display_text: open_entity_callback(l, i))
    if not has_items:
        ctk.CTkLabel(
            body,
            text="No linked items.",
            text_color=get_detail_palette()["muted_text"],
        ).pack(anchor="w")


@log_function
def insert_relationship_table(parent, header, relationships, open_entity_callback):
    if not relationships:
        return

    card, table = create_section_card(parent, header, "Character ties surfaced from linked records.")
    card.pack(fill="x", padx=10, pady=(0, 12))

    palette = get_detail_palette()
    for idx in range(3):
        table.grid_columnconfigure(idx, weight=1)

    headers = ["Source", "Relationship", "Target"]
    for col, title in enumerate(headers):
        CTkLabel(
            table,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=palette["muted_text"],
        ).grid(row=0, column=col, padx=8, pady=(0, 10), sticky="w")

    for row_idx, relationship in enumerate(relationships, start=1):
        source_name = relationship.get("source_name", "")
        relation_text = relationship.get("relation_text", "")
        target_name = relationship.get("target_name", "")

        source_label = CTkLabel(
            table,
            text=source_name,
            text_color=get_link_color(),
            cursor="hand2",
            font=ctk.CTkFont(size=12, underline=True),
        )
        source_label.grid(row=row_idx, column=0, padx=8, pady=4, sticky="w")
        if open_entity_callback:
            source_type = relationship.get("source_type", "NPCs")
            source_label.bind(
                "<Button-1>",
                lambda _event=None, t=source_type, n=source_name: open_entity_callback(t, n),
            )

        CTkLabel(
            table,
            text=relation_text,
            font=ctk.CTkFont(size=12),
            text_color=palette["text"],
        ).grid(row=row_idx, column=1, padx=8, pady=4, sticky="w")

        target_label = CTkLabel(
            table,
            text=target_name,
            text_color=get_link_color(),
            cursor="hand2",
            font=ctk.CTkFont(size=12, underline=True),
        )
        target_label.grid(row=row_idx, column=2, padx=8, pady=4, sticky="w")
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
            parent_window = master.winfo_toplevel() if master is not None else None
            _bring_window_to_front(existing, parent=parent_window)
            return
        else:
            _open_entity_windows.pop(window_key, None)

    # 2) Load the data item
    wrapper = _wrapper_for(entity_type)
    if not wrapper:
        messagebox.showerror("Error", f"Unknown type '{entity_type}'")
        return

    resolved_label = resolve_entity_label(entity_type)
    key_field = "Title" if resolve_entity_slug(entity_type) in {"scenarios", "books"} else "Name"
    item = wrapper.load_item_by_key(name, key_field=key_field)
    if not item:
        messagebox.showerror("Error", f"{resolved_label} '{name}' not found.")
        return

    # 3) Create a new Toplevel window
    parent_window = master.winfo_toplevel() if master is not None else None
    new_window = ctk.CTkToplevel(parent_window) if parent_window is not None else ctk.CTkToplevel()
    new_window.title(f"{resolved_label}: {name}")
    apply_fullscreen_top_left(new_window)
    new_window.configure(padx=10, pady=10)

    # 4) Build the scrollable detail frame inside it
    scrollable_container = build_scroll_host(new_window)
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
    _bring_window_to_front(new_window, parent=parent_window)
    
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


def _create_entity_dashboard_card(list_wrap, *, title, portrait_builder=None, portrait_click=None, tooltip_type=None, tooltip_data=None, title_click=None, chips=None, sections=None):
    palette = get_detail_palette()
    row_card = ctk.CTkFrame(
        list_wrap,
        fg_color=palette["surface_elevated"],
        border_width=1,
        border_color=palette["muted_border"],
        corner_radius=18,
    )
    row_card.grid_columnconfigure(1, weight=1)
    row_card.grid_columnconfigure(2, weight=1)

    portrait_shell = ctk.CTkFrame(
        row_card,
        fg_color=palette["surface_overlay"],
        border_width=1,
        border_color=palette["pill_border"],
        corner_radius=16,
        width=74,
        height=74,
    )
    portrait_shell.grid(row=0, column=0, rowspan=2, sticky="nw", padx=14, pady=14)
    portrait_shell.grid_propagate(False)

    portrait_widget = portrait_builder(portrait_shell) if callable(portrait_builder) else CTkLabel(
        portrait_shell,
        text="",
        text_color=palette["muted_text"],
    )
    if tooltip_type and isinstance(tooltip_data, dict):
        _attach_portrait_tooltip(portrait_widget, tooltip_type, tooltip_data)
    if callable(portrait_click):
        portrait_widget.bind("<Button-1>", portrait_click)
    portrait_widget.place(relx=0.5, rely=0.5, anchor="center")

    title_row = ctk.CTkFrame(row_card, fg_color="transparent")
    title_row.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(0, 14), pady=(14, 8))
    title_row.grid_columnconfigure(0, weight=1)

    name_label = CTkLabel(
        title_row,
        text=title,
        text_color=get_link_color() if callable(title_click) else palette["text"],
        font=ctk.CTkFont(size=16, weight="bold", underline=bool(callable(title_click))),
        cursor="hand2" if callable(title_click) else "",
        anchor="w",
    )
    name_label.grid(row=0, column=0, sticky="w")
    if callable(title_click):
        name_label.bind("<Button-1>", title_click)

    rendered_chips = [str(chip).strip() for chip in (chips or []) if str(chip).strip()]
    if rendered_chips:
        chips_row = ctk.CTkFrame(title_row, fg_color="transparent")
        chips_row.grid(row=1, column=0, sticky="w", pady=(6, 0))
        for idx, chip_text in enumerate(rendered_chips[:6]):
            create_chip(chips_row, chip_text).pack(side="left", padx=(0 if idx == 0 else 6, 0), pady=(0, 4))

    details_grid = ctk.CTkFrame(row_card, fg_color="transparent")
    details_grid.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 14), pady=(0, 14))
    details_grid.grid_columnconfigure((0, 1), weight=1)

    normalized_sections = [(label, value) for label, value in (sections or []) if label]
    for idx, (label, value) in enumerate(normalized_sections):
        block = ctk.CTkFrame(
            details_grid,
            fg_color=palette["surface_card"],
            border_width=1,
            border_color=palette["muted_border"],
            corner_radius=14,
        )
        block.grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=5, pady=5)
        block.grid_columnconfigure(0, weight=1)
        CTkLabel(
            block,
            text=str(label).upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=palette["muted_text"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        text_box = CTkTextbox(block, wrap="word", height=76, **get_textbox_style())
        text_box.insert = text_box._textbox.insert
        text_box.insert("1.0", value or "—")
        text_box.configure(state="disabled")
        text_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

    return row_card

@log_function
def insert_npc_table(parent, header, npc_names, open_entity_callback):
    card, body = create_section_card(parent, header, compact=True)
    card.pack(fill="both", expand=True, padx=10, pady=(0, 12))

    palette = get_detail_palette()
    wrapper = GenericModelWrapper("npcs")
    all_npcs = wrapper.load_items()
    npc_map = {npc["Name"]: npc for npc in all_npcs}

    list_wrap = ctk.CTkFrame(body, fg_color="transparent")
    list_wrap.pack(fill="both", expand=True)
    list_wrap.grid_columnconfigure(0, weight=1)

    for r, name in enumerate(npc_names):
        data = npc_map.get(name, {}) or {}
        portrait_value = data.get("Portrait")
        portrait_path = primary_portrait(portrait_value)
        resolved_portrait = resolve_portrait_path(portrait_value, ConfigHelper.get_campaign_dir())
        if resolved_portrait and os.path.exists(resolved_portrait):
            img = Image.open(resolved_portrait).resize((56, 56), Image.Resampling.LANCZOS)
            photo = CTkImage(light_image=img, size=(56, 56))
            def _portrait_builder(parent, image=photo):
                label = CTkLabel(parent, image=image, text="")
                label.image = image
                return label
        else:
            def _portrait_builder(parent, text="NPC", color=palette["muted_text"]):
                return CTkLabel(parent, text=text, text_color=color)

        row_card = _create_entity_dashboard_card(
            list_wrap,
            title=name,
            portrait_builder=_portrait_builder,
            portrait_click=(lambda _event=None, p=portrait_path, n=name: show_portrait(p, n)) if portrait_path else None,
            tooltip_type="NPCs",
            tooltip_data=data,
            title_click=(lambda _event=None, nm=name: open_entity_callback("NPCs", nm)) if open_entity_callback else None,
            chips=[str(f).strip() for f in (data.get("Factions") or []) if str(f).strip()][:4],
            sections=[
                ("Secret", format_longtext(data.get("Secret", ""))),
                ("Background", format_longtext(data.get("Background", ""))),
                ("Traits", format_longtext(data.get("Traits"))),
            ],
        )
        row_card.grid(row=r, column=0, sticky="ew", pady=(0, 10))

@log_function
def insert_creature_table(parent, header, creature_names, open_entity_callback):
    card, body = create_section_card(parent, header, compact=True)
    card.pack(fill="both", expand=True, padx=10, pady=(0, 12))

    palette = get_detail_palette()
    wrapper = GenericModelWrapper("creatures")
    all_creatures = wrapper.load_items()
    creature_map = {cr["Name"]: cr for cr in all_creatures}

    list_wrap = ctk.CTkFrame(body, fg_color="transparent")
    list_wrap.pack(fill="both", expand=True)
    list_wrap.grid_columnconfigure(0, weight=1)

    for r, name in enumerate(creature_names):
        data = creature_map.get(name, {}) or {}
        portrait_value = data.get("Portrait")
        portrait_path = primary_portrait(portrait_value)
        resolved_portrait = resolve_portrait_path(portrait_value, ConfigHelper.get_campaign_dir())
        if resolved_portrait and os.path.exists(resolved_portrait):
            img = Image.open(resolved_portrait).resize((56, 56), Image.Resampling.LANCZOS)
            photo = CTkImage(light_image=img, size=(56, 56))
            def _portrait_builder(parent, image=photo):
                label = CTkLabel(parent, image=image, text="")
                label.image = image
                return label
        else:
            def _portrait_builder(parent, text="Creature", color=palette["muted_text"]):
                return CTkLabel(parent, text=text, text_color=color)

        row_card = _create_entity_dashboard_card(
            list_wrap,
            title=name,
            portrait_builder=_portrait_builder,
            portrait_click=(lambda _event=None, p=portrait_path, n=name: show_portrait(p, n)) if portrait_path else None,
            tooltip_type="Creatures",
            tooltip_data=data,
            title_click=(lambda _event=None, nm=name: open_entity_callback("Creatures", nm)) if open_entity_callback else None,
            chips=[str(data.get("Type") or "").strip()] if str(data.get("Type") or "").strip() else [],
            sections=[
                ("Weakness", format_longtext(data.get("Weakness", ""), max_length=2000)),
                ("Powers", format_longtext(data.get("Powers", ""), max_length=2000)),
                ("Stats", format_longtext(data.get("Stats", ""), max_length=2000)),
                ("Background", format_longtext(data.get("Background", ""), max_length=2000)),
            ],
        )
        row_card.grid(row=r, column=0, sticky="ew", pady=(0, 10))

@log_function
def insert_villain_table(parent, header, villain_names, open_entity_callback):
    card, body = create_section_card(parent, header, compact=True)
    card.pack(fill="both", expand=True, padx=10, pady=(0, 12))

    palette = get_detail_palette()
    wrapper = GenericModelWrapper("villains")
    all_villains = wrapper.load_items()
    villain_map = {villain["Name"]: villain for villain in all_villains}

    list_wrap = ctk.CTkFrame(body, fg_color="transparent")
    list_wrap.pack(fill="both", expand=True)
    list_wrap.grid_columnconfigure(0, weight=1)

    for r, name in enumerate(villain_names):
        data = villain_map.get(name, {}) or {}
        portrait_value = data.get("Portrait")
        portrait_path = primary_portrait(portrait_value)
        resolved_portrait = resolve_portrait_path(portrait_value, ConfigHelper.get_campaign_dir())
        if resolved_portrait and os.path.exists(resolved_portrait):
            img = Image.open(resolved_portrait).resize((56, 56), Image.Resampling.LANCZOS)
            photo = CTkImage(light_image=img, size=(56, 56))
            def _portrait_builder(parent, image=photo):
                label = CTkLabel(parent, image=image, text="")
                label.image = image
                return label
        else:
            def _portrait_builder(parent, text="Villain", color=palette["muted_text"]):
                return CTkLabel(parent, text=text, text_color=color)

        chips = []
        for key in ("Archetype", "ThreatLevel"):
            value = str(data.get(key) or "").strip()
            if value:
                chips.append(value)

        row_card = _create_entity_dashboard_card(
            list_wrap,
            title=name,
            portrait_builder=_portrait_builder,
            portrait_click=(lambda _event=None, p=portrait_path, n=name: show_portrait(p, n)) if portrait_path else None,
            tooltip_type="Villains",
            tooltip_data=data,
            title_click=(lambda _event=None, nm=name: open_entity_callback("Villains", nm)) if open_entity_callback else None,
            chips=chips,
            sections=[
                ("Scheme", format_longtext(data.get("Scheme", ""), max_length=2000)),
                ("Objective", format_longtext(data.get("CurrentObjective", ""), max_length=2000)),
                ("Secret", format_longtext(data.get("Secret", ""), max_length=2000)),
                ("Traits", format_longtext(data.get("Traits", ""), max_length=2000)),
            ],
        )
        row_card.grid(row=r, column=0, sticky="ew", pady=(0, 10))

@log_function
def insert_places_table(parent, header, place_names, open_entity_callback):
    """
    Render places as dashboard cards instead of a raw grid.
    """
    card, body = create_section_card(parent, header, compact=True)
    card.pack(fill="both", expand=True, padx=10, pady=(0, 12))

    palette = get_detail_palette()
    place_map = {pl["Name"]: pl for pl in GenericModelWrapper("places").load_items()}

    list_wrap = ctk.CTkFrame(body, fg_color="transparent")
    list_wrap.pack(fill="both", expand=True)
    list_wrap.grid_columnconfigure(0, weight=1)

    for r, name in enumerate(place_names):
        data = place_map.get(name, {}) or {}
        portrait = primary_portrait(data.get("Portrait", ""))
        desc = format_longtext(data.get("Description", ""))
        secrets = format_longtext(data.get("Secrets", ""))
        npcs = [str(n).strip() for n in (data.get("NPCs") or []) if str(n).strip()]

        row_card = ctk.CTkFrame(
            list_wrap,
            fg_color=palette["surface_elevated"],
            border_width=1,
            border_color=palette["muted_border"],
            corner_radius=18,
        )
        row_card.grid(row=r, column=0, sticky="ew", pady=(0, 10))
        row_card.grid_columnconfigure(1, weight=1)
        row_card.grid_columnconfigure(2, weight=1)

        portrait_shell = ctk.CTkFrame(
            row_card,
            fg_color=palette["surface_overlay"],
            border_width=1,
            border_color=palette["pill_border"],
            corner_radius=16,
            width=74,
            height=74,
        )
        portrait_shell.grid(row=0, column=0, rowspan=2, sticky="nw", padx=14, pady=14)
        portrait_shell.grid_propagate(False)

        resolved_portrait = resolve_portrait_path(portrait, ConfigHelper.get_campaign_dir())
        if resolved_portrait and os.path.exists(resolved_portrait):
            img = Image.open(resolved_portrait).resize((56, 56), Image.Resampling.LANCZOS)
            photo = CTkImage(light_image=img, size=(56, 56))
            cell = CTkLabel(portrait_shell, image=photo, text="")
            cell.image = photo
            _attach_portrait_tooltip(cell, "Places", data)
            cell.bind("<Button-1>", lambda _event=None, p=portrait, n=name: show_portrait(p, n))
        else:
            cell = CTkLabel(portrait_shell, text="Place", text_color=palette["muted_text"])
        cell.place(relx=0.5, rely=0.5, anchor="center")

        title_row = ctk.CTkFrame(row_card, fg_color="transparent")
        title_row.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(0, 14), pady=(14, 8))
        title_row.grid_columnconfigure(0, weight=1)

        name_label = CTkLabel(
            title_row,
            text=name,
            text_color=get_link_color(),
            font=ctk.CTkFont(size=16, weight="bold", underline=True),
            cursor="hand2",
            anchor="w",
        )
        name_label.grid(row=0, column=0, sticky="w")
        if open_entity_callback:
            name_label.bind("<Button-1>", lambda _event=None, nm=name: open_entity_callback("Places", nm))

        if npcs:
            npc_row = ctk.CTkFrame(title_row, fg_color="transparent")
            npc_row.grid(row=1, column=0, sticky="w", pady=(6, 0))
            for idx, npc_name in enumerate(npcs[:6]):
                chip = create_chip(npc_row, npc_name)
                chip.pack(side="left", padx=(0 if idx == 0 else 6, 0), pady=(0, 4))
                if open_entity_callback:
                    for child in chip.winfo_children():
                        child.configure(cursor="hand2")
                        child.bind("<Button-1>", lambda _event=None, nm=npc_name: open_entity_callback("NPCs", nm))
                    chip.bind("<Button-1>", lambda _event=None, nm=npc_name: open_entity_callback("NPCs", nm))

        details_grid = ctk.CTkFrame(row_card, fg_color="transparent")
        details_grid.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 14), pady=(0, 14))
        details_grid.grid_columnconfigure((0, 1), weight=1)

        sections = [
            ("Description", desc),
            ("Secrets", secrets),
        ]

        for idx, (label, value) in enumerate(sections):
            block = ctk.CTkFrame(
                details_grid,
                fg_color=palette["surface_card"],
                border_width=1,
                border_color=palette["muted_border"],
                corner_radius=14,
            )
            block.grid(row=0, column=idx, sticky="nsew", padx=5, pady=5)
            block.grid_columnconfigure(0, weight=1)
            CTkLabel(
                block,
                text=label.upper(),
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=palette["muted_text"],
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
            text_box = CTkTextbox(block, wrap="word", height=88, **get_textbox_style())
            text_box.insert = text_box._textbox.insert
            text_box.insert("1.0", value or "—")
            text_box.configure(state="disabled")
            text_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        
@log_function
def insert_list_longtext(
    parent,
    header,
    items,
    open_entity_callback=None,
    entity_collector=None,
    gm_view=None,
    show_header=True,
    scene_density=DEFAULT_SCENE_DENSITY,
):
    """Insert collapsible sections for long text lists such as scenario scenes."""
    palette = get_detail_palette()
    active_border_color = palette.get("accent", palette["muted_border"])
    completed_border_color = palette.get("success", palette["muted_border"])

    if show_header:
        ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 16, "bold")) \
            .pack(anchor="w", padx=10, pady=(10, 2))

    def _truncate_label(text, max_len=34):
        cleaned = str(text or "").strip()
        if len(cleaned) <= max_len:
            return cleaned
        return f"{cleaned[:max(0, max_len - 1)].rstrip()}…"

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

    def _normalize_scene_entry(entry):
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

        indicator_payload = build_scene_indicator_payload(scene_dict, body_text)

        return {
            "scene_dict": scene_dict,
            "body_text": body_text,
            "title_clean": title_clean,
            "npc_names": indicator_payload["npc_names"],
            "villain_names": indicator_payload["villain_names"],
            "creature_names": indicator_payload["creature_names"],
            "place_names": indicator_payload["place_names"],
            "map_names": indicator_payload["map_names"],
            "links": indicator_payload["links"],
        }

    scene_entries = [_normalize_scene_entry(entry) for entry in items]
    scene_key_by_reference = {}
    scene_open_handlers = {}

    def _add_scene_reference(reference, scene_key):
        if reference is None:
            return
        text = str(reference).strip()
        if not text:
            return
        lowered = text.lower()
        scene_key_by_reference.setdefault(lowered, scene_key)
        digits_only = re.match(r"^\s*scene\s+(\d+)\s*$", lowered)
        if digits_only:
            scene_key_by_reference.setdefault(digits_only.group(1), scene_key)

    normalized_density = normalize_scene_density(scene_density)
    density_style = get_scene_density_style(normalized_density)

    for idx, scene_data in enumerate(scene_entries, start=1):
        scene_dict = scene_data["scene_dict"]
        scene_key = _build_scene_key(idx, scene_dict)
        _add_scene_reference(idx, scene_key)
        _add_scene_reference(scene_key, scene_key)
        for key_name in ("Id", "ID", "Scene", "scene", "Title", "title"):
            _add_scene_reference(scene_dict.get(key_name), scene_key)

    def _resolve_scene_target(target):
        if target is None:
            return None
        if isinstance(target, (int, float)):
            return scene_key_by_reference.get(str(int(target)))
        raw_text = str(target).strip()
        if not raw_text:
            return None
        lowered = raw_text.lower()
        resolved = scene_key_by_reference.get(lowered)
        if resolved:
            return resolved
        scene_match = re.match(r"^scene\s+(\d+)$", lowered)
        if scene_match:
            return scene_key_by_reference.get(scene_match.group(1))
        if lowered.isdigit():
            return scene_key_by_reference.get(str(int(lowered)))
        return None

    def _open_scene_target(scene_key):
        handler = scene_open_handlers.get(scene_key)
        if not callable(handler):
            return False
        try:
            handler()
            return True
        except Exception:
            return False

    for idx, scene_data in enumerate(scene_entries, start=1):
        scene_dict = scene_data["scene_dict"]
        body_text = scene_data["body_text"]
        title_clean = scene_data["title_clean"]
        npc_names = scene_data["npc_names"]
        villain_names = scene_data["villain_names"]
        creature_names = scene_data["creature_names"]
        place_names = scene_data["place_names"]
        map_names = scene_data["map_names"]
        scene_key = _build_scene_key(idx, scene_dict)
        links = [
            {
                **link,
                "resolved_target_key": _resolve_scene_target(link.get("target")),
            }
            for link in scene_data["links"]
        ]

        if entity_collector is not None:
            entity_collector.setdefault("NPCs", set()).update(npc_names)
            entity_collector.setdefault("Villains", set()).update(villain_names)
            entity_collector.setdefault("Creatures", set()).update(creature_names)
            entity_collector.setdefault("Places", set()).update(place_names)
            entity_collector.setdefault("Maps", set()).update(map_names)

        outer = ctk.CTkFrame(parent, fg_color=palette["surface_card"], corner_radius=20, border_width=1, border_color=palette["muted_border"])
        outer.pack(
            fill="x",
            expand=True,
            padx=density_style["outer_padx"],
            pady=density_style["outer_pady"],
        )
        body = ctk.CTkFrame(outer, fg_color="transparent")

        scene_sections = build_scene_body_sections(
            body,
            body_text=body_text,
            npc_names=npc_names,
            villain_names=villain_names,
            creature_names=creature_names,
            place_names=place_names,
            map_names=map_names,
            links=links,
            open_entity_callback=open_entity_callback,
            open_scene_callback=_open_scene_target,
            gm_view_ref=gm_view_ref,
            scene_density=normalized_density,
        )
        body_label = scene_sections["description_label"]

        expanded = ctk.BooleanVar(value=False)
        short_title = _truncate_label(title_clean, max_len=32)
        scene_label = f"{idx}"
        if short_title:
            scene_label += f" · {short_title}"
        button_text = f"▶ {scene_label}"
        note_title = f"Scene {idx}"
        if title_clean:
            note_title += f" – {title_clean}"

        initial_state = False
        if gm_view_ref and hasattr(gm_view_ref, "get_scene_completion"):
            initial_state = bool(gm_view_ref.get_scene_completion(scene_key))
        check_var = ctk.BooleanVar(master=outer, value=initial_state) if gm_view_ref else None
        checkbox = None

        header_row = ctk.CTkFrame(outer, fg_color="transparent")
        header_row.pack(
            fill="x",
            expand=True,
            padx=density_style["header_padx"],
            pady=density_style["header_pady"],
        )

        left_actions = ctk.CTkFrame(header_row, fg_color="transparent")
        left_actions.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn = ctk.CTkButton(
            left_actions,
            text=button_text,
            fg_color=palette["surface_overlay"],
            hover_color=palette["hero_band"],
            text_color=palette["text"],
            corner_radius=14,
            anchor="w",
            height=density_style["header_height"],
        )
        btn.pack(side="left", fill="x", expand=True)

        tags_row = ctk.CTkFrame(header_row, fg_color="transparent")
        tags_row.pack(side="left", padx=(0, 8))
        create_chip(tags_row, f"NPC {len(npc_names)}").pack(side="left", padx=(0, 6))
        create_chip(tags_row, f"Lieux {len(place_names)}").pack(side="left", padx=(0, 6))
        create_chip(tags_row, f"Liens {len(links)}").pack(side="left", padx=(0, 6))
        create_chip(tags_row, f"Map {'✓' if bool(map_names) else '—'}").pack(side="left")

        quick_actions = ctk.CTkFrame(header_row, fg_color="transparent")
        quick_actions.pack(side="right")

        def _set_scene_active(*, key=scene_key, gm_view=gm_view_ref):
            if gm_view and hasattr(gm_view, "set_active_scene"):
                gm_view.set_active_scene(key)
                refreshers = getattr(gm_view, "_scene_state_refreshers", {})
                for refresher in list(refreshers.values()):
                    try:
                        refresher()
                    except Exception:
                        continue

        def _mark_scene_done(*, check=check_var):
            if check is None:
                return
            check.set(True)
            _set_scene_active()

        def _add_scene_note(*, gm_view=gm_view_ref, key=scene_key):
            if gm_view and hasattr(gm_view, "_append_scene_to_notes"):
                gm_view._append_scene_to_notes(key)
            elif gm_view and hasattr(gm_view, "add_timestamped_note"):
                gm_view.add_timestamped_note()

        active_btn = ctk.CTkButton(
            quick_actions,
            text="◎",
            width=30,
            height=30,
            corner_radius=999,
            fg_color=palette["surface_overlay"],
            hover_color=palette["hero_band"],
            command=_set_scene_active,
        )
        active_btn.pack(side="left", padx=(0, 4))
        done_btn = ctk.CTkButton(
            quick_actions,
            text="✓",
            width=30,
            height=30,
            corner_radius=999,
            fg_color=palette["surface_overlay"],
            hover_color=palette["hero_band"],
            command=_mark_scene_done,
        )
        done_btn.pack(side="left", padx=(0, 4))
        note_btn = ctk.CTkButton(
            quick_actions,
            text="✎",
            width=30,
            height=30,
            corner_radius=999,
            fg_color=palette["surface_overlay"],
            hover_color=palette["hero_band"],
            command=_add_scene_note,
        )
        note_btn.pack(side="left")

        def _refresh_scene_state(
            *,
            check=check_var,
            gm_view=gm_view_ref,
            key=scene_key,
            card_outer=outer,
            complete_btn=done_btn,
        ):
            is_completed = bool(check.get()) if check is not None else False
            is_active = bool(gm_view and getattr(gm_view, "_active_scene_key", None) == key)
            border_color = palette["muted_border"]
            border_width = 1
            if is_active and not is_completed:
                border_color = active_border_color
                border_width = 2
            if is_completed:
                border_color = completed_border_color
                border_width = 2
            card_outer.configure(border_color=border_color, border_width=border_width)
            complete_btn.configure(text="✓✓" if is_completed else "✓")

        if gm_view_ref:
            refreshers = getattr(gm_view_ref, "_scene_state_refreshers", None)
            if not isinstance(refreshers, dict):
                refreshers = {}
                setattr(gm_view_ref, "_scene_state_refreshers", refreshers)
            refreshers[scene_key] = _refresh_scene_state

        def _toggle(btn=btn, body=body, lbl=body_label, expanded=expanded, idx=idx, title=title_clean, key=scene_key):
            if expanded.get():
                body.pack_forget()
                label = f"▶ {idx}"
                if title:
                    label += f" · {_truncate_label(title, max_len=32)}"
                btn.configure(text=label)
            else:
                body.pack(
                    fill="x",
                    padx=density_style["body_padx"],
                    pady=density_style["body_pady"],
                )
                label = f"▼ {idx}"
                if title:
                    label += f" · {_truncate_label(title, max_len=32)}"
                btn.configure(text=label)
                outer.update_idletasks()

                def _refresh_body_wrap(_event=None, *, target_label=lbl, target_body=body, target_outer=outer):
                    try:
                        parent_width = target_body.master.winfo_width() if target_body.master is not None else 0
                    except Exception:
                        parent_width = 0
                    _configure_wraplength_if_changed(
                        target_label,
                        target_body.winfo_width(),
                        target_outer.winfo_width(),
                        parent_width,
                        minimum=200,
                        safety_margin=32,
                    )

                if not getattr(lbl, "_wraplength_bound", False):
                    body.bind("<Configure>", _refresh_body_wrap, add="+")
                    outer.bind("<Configure>", _refresh_body_wrap, add="+")
                    lbl._wraplength_bound = True
                _refresh_body_wrap()
                if gm_view_ref and hasattr(gm_view_ref, "set_active_scene"):
                    gm_view_ref.set_active_scene(key)
                _refresh_scene_state()
            expanded.set(not expanded.get())

        def _open_scene_from_link(*, expanded_state=expanded, key=scene_key):
            if not expanded_state.get():
                _toggle()
                return
            if gm_view_ref and hasattr(gm_view_ref, "set_active_scene"):
                gm_view_ref.set_active_scene(key)
            _refresh_scene_state()

        scene_open_handlers[scene_key] = _open_scene_from_link
        btn.configure(command=_toggle)
        if gm_view_ref:
            checkbox = ctk.CTkCheckBox(
                quick_actions,
                text="",
                variable=check_var,
                width=18,
                fg_color=palette["accent"],
                hover_color=palette["accent_hover"],
                border_color=palette["pill_border"],
            )
            checkbox.pack(side="left", padx=(8, 0), pady=(2, 2))
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
                _refresh_scene_state()

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
        _refresh_scene_state()

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


def _replace_detail_frame(current_frame, updated_item, entity_type, open_entity_callback, builder):
    parent = current_frame.master
    current_frame.destroy()

    replacement_frame = builder(updated_item, parent)
    replacement_frame.pack(fill="both", expand=True)

    gm_view = getattr(open_entity_callback, "__self__", None)
    if gm_view is not None:
        key_field = "Title" if entity_type == "Scenarios" else "Name"
        tab_name = updated_item.get(key_field)
        if tab_name in gm_view.tabs:
            gm_view.tabs[tab_name]["content_frame"] = replacement_frame

    return replacement_frame

@log_function
def create_scenario_detail_frame(entity_type, scenario_item, master, open_entity_callback=None):
    """
    Build a scrollable detail view for a scenario with:
    1) A header zone (Title, Summary, Secrets)
    2) Then the rest of the fields, but NPCs always before Places.
    """
    palette = get_detail_palette()
    frame = ctk.CTkFrame(master, fg_color="transparent")
    gm_view_instance = getattr(open_entity_callback, "__self__", None)
    sections = {}
    pinned_sections = set()
    active_section = None
    section_order = ["Summary", "Scenes", "NPCs", "Villains", "Creatures", "Places", "Secrets", "Notes"]
    section_names = []
    def rebuild_frame(updated_item):
        _replace_detail_frame(
            frame,
            updated_item,
            entity_type,
            open_entity_callback,
            lambda item, parent: create_scenario_detail_frame(
                entity_type,
                item,
                parent,
                open_entity_callback,
            ),
        )

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

    nav_frame = ctk.CTkFrame(layout, width=240, fg_color="transparent")
    nav_frame.grid(row=0, column=0, sticky="ns", padx=(0, 12))

    content_frame = ctk.CTkFrame(layout, fg_color="transparent")
    content_frame.grid(row=0, column=1, sticky="nsew")
    content_frame.grid_rowconfigure(0, weight=1)
    content_frame.grid_columnconfigure(0, weight=1)

    scrollable_frame = ctk.CTkScrollableFrame(content_frame, fg_color="transparent")
    scrollable_frame.grid(row=0, column=0, sticky="nsew")
    frame._scrollable_frame = scrollable_frame
    for attr in ("_parent_canvas", "_scroll_canvas", "_scrollbar"):
        try:
            setattr(frame, attr, getattr(scrollable_frame, attr, None))
        except Exception:
            pass

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
                sections[name].pack(fill="both", expand=True, padx=10, pady=(0, 12))

    def _reset_scroll_position():
        try:
            scrollable_frame.update_idletasks()
            parent_canvas = getattr(scrollable_frame, "_parent_canvas", None)
            if parent_canvas is not None:
                try:
                    bbox = parent_canvas.bbox("all")
                    if bbox is not None:
                        parent_canvas.configure(scrollregion=bbox)
                except Exception:
                    pass
                if hasattr(parent_canvas, "yview_moveto"):
                    parent_canvas.yview_moveto(0.0)
        except Exception:
            pass

    def show_section(section_name):
        nonlocal active_section
        active_section = section_name
        _apply_section_visibility()
        scrollable_frame.after_idle(_reset_scroll_position)
        scrollable_frame.after(25, _reset_scroll_position)

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
    scenario_title = str(scenario_item.get("Title") or scenario_item.get("Name") or "Scenario").strip()
    scenario_meta = []
    for label, key in (("Scenes", "Scenes"), ("NPCs", "NPCs"), ("Places", "Places"), ("Villains", "Villains")):
        value = scenario_item.get(key)
        if isinstance(value, list) and value:
            scenario_meta.append(f"{len(value)} {label}")
    hero = create_hero_header(
        summary_section,
        title=scenario_title,
        category=entity_type[:-1] if entity_type.endswith("s") else entity_type,
        summary=format_multiline_text(scenario_item.get("Summary", "")),
        meta_items=scenario_meta,
    )
    hero.pack(fill="x", padx=10, pady=(0, 12))
    # ——— BODY — prepare fields in the custom order ———
    tpl = load_template(entity_type.lower())
    scene_entity_tracker = {"NPCs": set(), "Villains": set(), "Creatures": set(), "Places": set(), "Maps": set()}
    # remove header fields
    body_fields = [
        f for f in tpl["fields"]
        if f["name"] not in ("Title", "Summary", "Secrets")
    ]

    
    # group them
    scenes_fields = [f for f in body_fields if f["name"] == "Scenes"]
    npc_fields   = [f for f in body_fields if f.get("linked_type") == "NPCs"]
    villain_fields = [f for f in body_fields if f.get("linked_type") == "Villains"]
    creature_fields = [f for f in body_fields if f.get("linked_type") == "Creatures"]
    place_fields = [f for f in body_fields if f.get("linked_type") == "Places"]
    other_fields = [f for f in body_fields if f not in scenes_fields + npc_fields + villain_fields + place_fields + creature_fields]
    ordered_fields = scenes_fields + npc_fields + villain_fields + creature_fields + place_fields + other_fields

    if gm_view_instance and hasattr(gm_view_instance, "reset_scene_widgets"):
        gm_view_instance.reset_scene_widgets()

    section_map = {
        "Summary": "Summary",
        "Scenes": "Scenes",
        "NPCs": "NPCs",
        "Villains": "Villains",
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
                scenes_field_name = name
                scenes_items = value if isinstance(value, list) else []
                scenes_card, scenes_body = create_section_card(
                    section_frame,
                    "Scenes",
                    "Run the scenario as a scene list or switch to scene flow.",
                )
                scenes_card.pack(fill="both", expand=True, padx=10, pady=(0, 12))

                scenes_container = ctk.CTkFrame(scenes_body, fg_color="transparent")
                scenes_container.pack(fill="both", expand=True)

                header_row = ctk.CTkFrame(scenes_container, fg_color="transparent")
                header_row.pack(fill="x", pady=(0, 4))

                scenario_title = str(
                    scenario_item.get("Title") or scenario_item.get("Name") or ""
                ).strip()

                def _extract_scene_text_length(entry):
                    parsed_entry = deserialize_possible_json(entry)
                    if isinstance(parsed_entry, dict):
                        scene_dict = {key: deserialize_possible_json(val) for key, val in parsed_entry.items()}
                        text_payload = scene_dict.get("Text") or scene_dict.get("text") or ""
                    elif isinstance(parsed_entry, list):
                        text_payload = parsed_entry
                    else:
                        text_payload = parsed_entry

                    if isinstance(text_payload, list):
                        text_payload = "\n".join(str(part) for part in text_payload if str(part).strip())
                    return len(str(text_payload or "").strip())

                long_text_threshold = 450
                scene_entries = scenes_items
                scene_lengths = [_extract_scene_text_length(entry) for entry in scene_entries]
                average_scene_length = (
                    sum(scene_lengths) / len(scene_lengths)
                    if scene_lengths
                    else 0
                )
                default_scene_view = "List" if average_scene_length > long_text_threshold else "Scene Flow"

                persisted_scene_view = default_scene_view
                if gm_view_instance is not None and hasattr(gm_view_instance, "layout_manager"):
                    try:
                        persisted_scene_view = (
                            gm_view_instance.layout_manager.get_scene_view_mode(scenario_title)
                            or default_scene_view
                        )
                    except Exception:
                        persisted_scene_view = default_scene_view

                view_var = tk.StringVar(value=persisted_scene_view)
                view_toggle = ctk.CTkSegmentedButton(
                    header_row,
                    values=["List", "Scene Flow"],
                    variable=view_var,
                )
                view_toggle.pack(side="right")

                persisted_scene_density = DEFAULT_SCENE_DENSITY
                if gm_view_instance is not None and hasattr(gm_view_instance, "layout_manager"):
                    try:
                        persisted_scene_density = (
                            gm_view_instance.layout_manager.get_scene_list_density(scenario_title)
                            or DEFAULT_SCENE_DENSITY
                        )
                    except Exception:
                        persisted_scene_density = DEFAULT_SCENE_DENSITY
                persisted_scene_density = normalize_scene_density(persisted_scene_density)

                density_var = tk.StringVar(value=persisted_scene_density)
                density_toggle = ctk.CTkSegmentedButton(
                    header_row,
                    values=list(SCENE_DENSITY_MODES),
                    variable=density_var,
                )
                density_toggle.pack(side="right", padx=(0, 8))

                list_container = ctk.CTkFrame(scenes_container, fg_color="transparent")
                list_container.pack(fill="x", expand=True)

                def _render_scene_list(selected_density):
                    normalized_density = normalize_scene_density(selected_density)
                    for child in list_container.winfo_children():
                        child.destroy()
                    insert_list_longtext(
                        list_container,
                        scenes_field_name,
                        scenes_items,
                        open_entity_callback,
                        entity_collector=scene_entity_tracker,
                        gm_view=gm_view_instance,
                        show_header=False,
                        scene_density=normalized_density,
                    )

                _render_scene_list(persisted_scene_density)

                flow_container = ctk.CTkFrame(scenes_container, fg_color="transparent")
                flow_container.pack_propagate(False)
                scene_flow_frame = create_scene_flow_frame(
                    flow_container,
                    scenario_title=scenario_title,
                )
                scene_flow_frame.pack(fill="both", expand=True)

                def _sync_scene_flow_height(_event=None):
                    target_height = 520
                    try:
                        viewport = getattr(gm_view_instance, "content_area", None)
                        if viewport is not None and viewport.winfo_exists():
                            viewport.update_idletasks()
                            scenes_container.update_idletasks()
                            header_row.update_idletasks()

                            viewport_h = int(viewport.winfo_height())
                            viewport_top = int(viewport.winfo_rooty())
                            viewport_bottom = viewport_top + max(1, viewport_h)
                            section_top = int(scenes_container.winfo_rooty())
                            header_h = int(header_row.winfo_height())

                            # Visible vertical space from under the local header to
                            # the bottom of the GM viewport, with a safety margin.
                            visible_space = viewport_bottom - section_top - header_h - 36
                            if visible_space > 1:
                                target_height = max(320, min(900, visible_space))
                        else:
                            top = frame.winfo_toplevel()
                            top.update_idletasks()
                            top_h = int(top.winfo_height())
                            if top_h > 1:
                                target_height = max(320, min(900, top_h - 360))
                    except Exception:
                        pass

                    try:
                        flow_container.configure(height=target_height)
                    except Exception:
                        return

                scene_flow_layout_scheduler = LayoutSettleScheduler(scene_flow_frame)

                def _scene_flow_layout_ready():
                    try:
                        if view_var.get() != "Scene Flow":
                            return False
                        if not flow_container.winfo_exists() or not flow_container.winfo_ismapped():
                            return False
                        return int(scenes_container.winfo_width()) > 1 and int(flow_container.winfo_width()) > 1
                    except Exception:
                        return False

                def _settle_scene_flow_layout():
                    _sync_scene_flow_height()
                    try:
                        scene_flow_frame._on_layout_resize()
                    except Exception:
                        pass

                def _toggle_scene_view(selected_view=None):
                    selection = selected_view or view_var.get()
                    if selection not in {"List", "Scene Flow"}:
                        selection = default_scene_view
                    view_var.set(selection)

                    if selection == "Scene Flow":
                        list_container.pack_forget()
                        flow_container.pack(fill="x", expand=False, padx=10, pady=(6, 0))
                        scene_flow_layout_scheduler.schedule(
                            "scene-flow-layout",
                            _settle_scene_flow_layout,
                            when=_scene_flow_layout_ready,
                        )
                    else:
                        flow_container.pack_forget()
                        _render_scene_list(density_var.get())
                        list_container.pack(fill="x", expand=True)

                    if gm_view_instance and hasattr(gm_view_instance, "layout_manager"):
                        try:
                            gm_view_instance.layout_manager.update_scenario_state(
                                scenario_title,
                                scene_view_mode=selection,
                            )
                        except Exception:
                            pass

                def _toggle_scene_density(selected_density=None):
                    density_selection = normalize_scene_density(selected_density or density_var.get())
                    density_var.set(density_selection)
                    if view_var.get() == "List":
                        _render_scene_list(density_selection)
                    if gm_view_instance and hasattr(gm_view_instance, "layout_manager"):
                        try:
                            gm_view_instance.layout_manager.update_scenario_state(
                                scenario_title,
                                scene_list_density=density_selection,
                            )
                        except Exception:
                            pass

                try:
                    if hasattr(gm_view_instance, "content_area") and gm_view_instance.content_area.winfo_exists():
                        scene_flow_layout_scheduler.bind_configure(
                            gm_view_instance.content_area,
                            "scene-flow-layout",
                            _settle_scene_flow_layout,
                            when=_scene_flow_layout_ready,
                        )
                except Exception:
                    pass
                try:
                    scene_flow_layout_scheduler.bind_configure(
                        scenes_container,
                        "scene-flow-layout",
                        _settle_scene_flow_layout,
                        when=_scene_flow_layout_ready,
                    )
                except Exception:
                    pass

                view_toggle.configure(command=_toggle_scene_view)
                density_toggle.configure(command=_toggle_scene_density)
                _toggle_scene_view(persisted_scene_view)
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
            elif linked == "Villains":
                insert_villain_table(section_frame, "Villains", items, open_entity_callback)
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
    secrets_card, secrets_body = create_section_card(
        secrets_section,
        "Secrets",
        "Hidden truths, leverage, and reveals to hold in reserve.",
    )
    secrets_card.pack(fill="x", padx=10, pady=(0, 12))
    secrets_text_label = CTkLabel(
        secrets_body,
        text=format_multiline_text(scenario_item.get("Secrets", "")),
        font=ctk.CTkFont(size=14),
        text_color=palette["text"],
        wraplength=400,
        justify="left"
    )
    secrets_text_label.pack(fill="x", anchor="w")

    def _update_text_wraplength(_event=None):
        try:
            available_width = max(260, scrollable_frame.winfo_width() - 80)
            summary_text_label.configure(wraplength=available_width)
            secrets_text_label.configure(wraplength=available_width)
        except Exception:
            pass

    text_wrap_scheduler = LayoutSettleScheduler(scrollable_frame)
    text_wrap_scheduler.bind_configure(
        scrollable_frame,
        "scenario-wraplength",
        _update_text_wraplength,
        when=lambda: scrollable_frame.winfo_width() > 1,
    )
    text_wrap_scheduler.schedule(
        "scenario-wraplength",
        _update_text_wraplength,
        when=lambda: scrollable_frame.winfo_width() > 1,
    )

    if entity_type in {"Scenarios", "Places", "Bases", "NPCs", "Villains", "Informations"}:
        related_events_panel = RelatedEventsPanel(
            _get_section_frame("Notes"),
            entity_type=entity_type,
            entity_name=scenario_item.get("Title") or scenario_item.get("Name"),
            on_open_entity=open_entity_callback,
        )
        related_events_panel.pack(fill="x", padx=10, pady=(0, 10))

    if gm_view_instance and hasattr(gm_view_instance, "register_note_widget"):
        notes_section = _get_section_frame("Notes")
        notes_card, notes_body = create_section_card(notes_section, "GM Notes", "Scratchpad for timestamps, callbacks, and table reactions.")
        notes_card.pack(fill="both", expand=True, padx=10, pady=(0, 12))
        toolbar = ctk.CTkFrame(notes_body, fg_color="transparent")
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

        note_box = CTkTextbox(notes_body, wrap="word", height=160, **get_textbox_style())
        note_box.pack(fill="both", expand=True)
        gm_view_instance.register_note_widget(note_box)

    section_names = [name for name in section_order if name in sections]
    for name in sections:
        if name not in section_names:
            section_names.append(name)

    menu_handler = getattr(gm_view_instance, "_show_context_menu", None)
    tabs = VerticalSectionTabs(
        nav_frame,
        section_names,
        show_section,
        on_pin_toggle=_toggle_pin,
        on_right_click=menu_handler if callable(menu_handler) else None,
    )
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

    palette = get_detail_palette()
    content_frame = ctk.CTkFrame(master, fg_color="transparent")
    gm_view_instance = getattr(open_entity_callback, "__self__", None)

    def rebuild_frame(updated_item):
        _replace_detail_frame(
            content_frame,
            updated_item,
            entity_type,
            open_entity_callback,
            lambda item, parent: create_entity_detail_frame(
                entity_type,
                item,
                parent,
                open_entity_callback,
            ),
        )

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

    entity_label = entity.get("Name") or entity.get("Title") or entity_type[:-1]
    audio_value = get_entity_audio_value(entity)

    def _audio_display_name(value: str) -> str:
        if not value:
            return "Audio"
        base = os.path.basename(str(value)) or "Audio"
        resolved = resolve_audio_path(value)
        return base if resolved and os.path.exists(resolved) else f"{base} (missing)"

    def _play_audio_from_menu() -> None:
        if not audio_value:
            messagebox.showinfo("Audio", "No audio file configured for this entry.")
            return
        if not play_entity_audio(audio_value, entity_label=str(entity_label)):
            messagebox.showwarning("Audio", "Unable to play the associated audio track.")

    content_frame.portrait_images = {}
    def _make_spotlight_portrait(parent):
        portrait_widget, portrait_path = _build_portrait_widget(
            parent,
            entity_type,
            entity,
            size=PORTRAIT_SIZE,
        )
        _portrait_debug(
            entity_type,
            entity,
            f"spotlight result widget_created={portrait_widget is not None}, source={portrait_path!r}",
        )
        if portrait_widget is not None:
            content_frame.portrait_images[str(entity_label)] = portrait_widget.image
        return portrait_widget

    def _make_hero_portrait(parent):
        portrait_widget, portrait_path = _build_portrait_widget(
            parent,
            entity_type,
            entity,
            size=HERO_PORTRAIT_SIZE,
        )
        _portrait_debug(
            entity_type,
            entity,
            f"hero result widget_created={portrait_widget is not None}, source={portrait_path!r}",
        )
        if portrait_widget is not None:
            content_frame.portrait_images[f"{entity_label}-hero"] = portrait_widget.image
            content_frame.portrait_label = portrait_widget
        return portrait_widget

    _portrait_debug(
        entity_type,
        entity,
        f"opening detail view with placement='{DEFAULT_PORTRAIT_PLACEMENT}'",
    )

    template = load_template(entity_type.lower())
    meta_items = []
    for field in template.get("fields", []):
        field_name = field.get("name")
        value = entity.get(field_name)
        if isinstance(value, list) and value:
            meta_items.append(f"{len(value)} {field_name}")
        elif field_name in {"Role", "Type", "Location", "Archetype"} and value:
            meta_items.append(str(value))
        if len(meta_items) >= 4:
            break
    if audio_value:
        meta_items.append(f"🎵 {_audio_display_name(audio_value)}")

    summary_candidates = [entity.get(key) for key in ("Description", "Summary", "Role", "Secret", "Subject", "Location")]
    summary = next((format_multiline_text(value, max_length=260) for value in summary_candidates if str(value or "").strip()), "")
    highlight_lines = _collect_highlight_lines(entity_type, entity)

    hero = create_hero_header(
        content_frame,
        title=str(entity_label),
        category=entity_type[:-1] if entity_type.endswith("s") else entity_type,
        summary=summary,
        meta_items=meta_items,
        portrait_builder=_make_hero_portrait if DEFAULT_PORTRAIT_PLACEMENT in {"hero", "both"} else None,
    )
    hero.pack(fill="x", padx=10, pady=(0, 16))

    shell, main_column, side_column = create_detail_split_layout(content_frame)
    shell.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    create_spotlight_panel(
        side_column,
        title=str(entity_label),
        subtitle="Click the portrait to open it full size." if DEFAULT_PORTRAIT_PLACEMENT in {"spotlight", "both"} else "Give this entry a signature visual to own the right rail.",
        portrait_builder=_make_spotlight_portrait if DEFAULT_PORTRAIT_PLACEMENT in {"spotlight", "both"} else None,
        fallback_text=_spotlight_fallback(entity_type),
        accent_lines=highlight_lines[:3],
    )

    create_highlight_card(
        side_column,
        "Highlights",
        highlight_lines,
        empty_state="Add signature fields like Role, Secret, Powers, or Motivation to surface a punchier overview.",
    )

    if audio_value:
        audio_card, audio_body = create_section_card(
            side_column,
            "Audio ambiance",
            "Right-click the track badge to play or stop the linked audio cue.",
            compact=True,
        )
        audio_card.pack(fill="x", pady=(0, 14))
        audio_label = ctk.CTkLabel(
            audio_body,
            text=f"🎵 {_audio_display_name(audio_value)}",
            text_color=get_link_color(),
            cursor="hand2",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        audio_label.pack(anchor="w")

        def _show_audio_menu(event) -> None:
            menu = tk.Menu(audio_body, tearoff=0)
            menu.add_command(label="Play Audio", command=_play_audio_from_menu)
            menu.add_command(label="Stop Audio", command=stop_entity_audio)
            menu.tk_popup(event.x_root, event.y_root)

        audio_label.bind("<Button-3>", _show_audio_menu)

    grid = ctk.CTkFrame(main_column, fg_color="transparent")
    grid.pack(fill="both", expand=True)
    grid.grid_columnconfigure(0, weight=1)
    grid.grid_columnconfigure(1, weight=1)

    column_left = ctk.CTkFrame(grid, fg_color="transparent")
    column_left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    column_right = ctk.CTkFrame(grid, fg_color="transparent")
    column_right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    render_fields = []
    for field in template["fields"]:
        field_name = field["name"]
        field_type = field["type"]
        if field_name == "Portrait":
            continue
        if field_type == "list" and not field.get("linked_type"):
            continue
        render_fields.append(field)

    if summary:
        summary_card, summary_body = create_section_card(
            column_left,
            "Overview",
            "A quick read built for widescreen GM screens and pop-out windows.",
        )
        summary_card.pack(fill="x", padx=10, pady=(0, 12))
        summary_label = CTkLabel(
            summary_body,
            text=summary,
            font=ctk.CTkFont(size=14),
            text_color=palette["text"],
            wraplength=540,
            justify="left",
        )
        summary_label.pack(fill="x", anchor="w")
        render_fields = [field for field in render_fields if field["name"] not in {"Description", "Summary"}]

        def _update_summary_wrap(_event=None):
            try:
                summary_label.configure(wraplength=max(280, column_left.winfo_width() - 70))
            except Exception:
                pass

        summary_wrap_scheduler = LayoutSettleScheduler(column_left)
        summary_wrap_scheduler.bind_configure(
            column_left,
            "summary-wraplength",
            _update_summary_wrap,
            when=lambda: column_left.winfo_width() > 1,
        )
        summary_wrap_scheduler.schedule(
            "summary-wraplength",
            _update_summary_wrap,
            when=lambda: column_left.winfo_width() > 1,
        )

    _populate_generic_columns([column_left, column_right], render_fields, entity, open_entity_callback)

    if entity_type in {"Scenarios", "Places", "Bases", "NPCs", "Villains", "Informations"}:
        related_card, related_body = create_section_card(
            side_column,
            "Related events",
            "Timeline connections and linked moments across the campaign.",
        )
        related_card.pack(fill="x", pady=(0, 14))
        related_events_panel = RelatedEventsPanel(
            related_body,
            entity_type=entity_type,
            entity_name=entity.get("Title") or entity.get("Name"),
            on_open_entity=open_entity_callback,
        )
        related_events_panel.pack(fill="x")
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
    apply_fullscreen_top_left(new_window)
    new_window.configure(padx=10, pady=10)

    scrollable_container = build_scroll_host(new_window)

    detail_frame = create_entity_detail_frame(
        entity_type, entity, master=scrollable_container,
        open_entity_callback=open_entity_window
    )
    detail_frame.pack(fill="both", expand=True)
