import customtkinter as ctk
import textwrap
from customtkinter import CTkLabel

from modules.generic.detail_ui import get_detail_palette
from modules.scenarios.widgets.scene_body import create_entities_groups_grid


def _create_section_shell(parent):
    palette = get_detail_palette()
    shell = ctk.CTkFrame(parent, fg_color=palette["surface_card"], corner_radius=18, border_width=1, border_color=palette["muted_border"])
    shell.pack(fill="x", padx=0, pady=(0, 0))
    shell.grid_columnconfigure(0, weight=1)
    return shell


def _create_section_title(parent, label_text):
    palette = get_detail_palette()
    title = ctk.CTkLabel(
        parent,
        text=label_text.upper(),
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color=palette["muted_text"],
        anchor="w",
    )
    title.pack(anchor="w", padx=14, pady=(12, 4))
    return title


def _add_subtle_separator(parent):
    palette = get_detail_palette()
    separator = ctk.CTkFrame(parent, height=1, fg_color=palette["muted_border"])
    separator.pack(fill="x", padx=14, pady=(6, 10))
    return separator


def _create_description_block(parent, body_text):
    palette = get_detail_palette()
    description_block = ctk.CTkFrame(parent, fg_color=palette["surface_overlay"], corner_radius=16, border_width=1, border_color=palette["pill_border"])
    description_block.pack(fill="x", padx=12, pady=(12, 0))

    _create_section_title(description_block, "Description")
    max_preview_lines = 5
    clean_text = str(body_text or "").strip()
    has_description = bool(clean_text)
    fallback_text = "Aucune note de mise en scène"
    full_text = clean_text if has_description else fallback_text

    description_font = ctk.CTkFont(size=13)
    fallback_font = ctk.CTkFont(size=13, slant="italic")
    description_label = ctk.CTkLabel(
        description_block,
        text=full_text,
        wraplength=0,
        justify="left",
        font=description_font if has_description else fallback_font,
        text_color=palette["muted_text"],
        anchor="w",
    )
    description_label.pack(fill="x", padx=14, pady=(0, 8 if has_description else 14))

    if not has_description:
        return description_block, description_label

    is_expanded = ctk.BooleanVar(master=description_block, value=False)
    description_toggle_button = ctk.CTkButton(
        description_block,
        text="Lire plus",
        width=0,
        height=24,
        corner_radius=10,
        fg_color="transparent",
        hover_color=palette["surface_card"],
        text_color=palette["muted_text"],
        border_width=1,
        border_color=palette["muted_border"],
    )
    description_toggle_button.pack(anchor="w", padx=14, pady=(0, 12))

    def _build_collapsed_preview(text_value, wrap_px):
        effective_wrap = max(160, int(wrap_px or 0))
        estimated_chars_per_line = max(22, effective_wrap // 7)
        lines = []
        for paragraph in text_value.splitlines() or [""]:
            paragraph_lines = textwrap.wrap(
                paragraph,
                width=estimated_chars_per_line,
                break_long_words=False,
                replace_whitespace=False,
                drop_whitespace=False,
            )
            lines.extend(paragraph_lines or [""])
        if len(lines) <= max_preview_lines:
            return text_value, False
        preview_lines = lines[:max_preview_lines]
        preview_lines[-1] = preview_lines[-1].rstrip() + "…"
        return "\n".join(preview_lines), True

    def _refresh_description_text():
        if is_expanded.get():
            description_label.configure(text=full_text)
            description_toggle_button.configure(text="Réduire", state="normal")
            return
        preview_text, is_truncated = _build_collapsed_preview(full_text, description_label.cget("wraplength"))
        description_label.configure(text=preview_text)
        description_toggle_button.configure(text="Lire plus", state="normal" if is_truncated else "disabled")

    def _toggle_description():
        is_expanded.set(not is_expanded.get())
        _refresh_description_text()

    description_toggle_button.configure(command=_toggle_description)
    description_label.bind("<Configure>", lambda _event=None: _refresh_description_text(), add="+")
    _refresh_description_text()
    return description_block, description_label


def _create_entities_block(parent, npc_names, villain_names, creature_names, place_names, open_entity_callback=None):
    palette = get_detail_palette()
    has_entities = bool(npc_names or villain_names or creature_names or place_names)
    if not has_entities:
        return None

    entities_block = ctk.CTkFrame(parent, fg_color=palette["surface_elevated"], corner_radius=16, border_width=1, border_color=palette["muted_border"])
    entities_block.pack(fill="x", padx=12, pady=(0, 0))
    _create_section_title(entities_block, "Entities")

    create_entities_groups_grid(
        entities_block,
        groups=(
            ("NPCs", npc_names or []),
            ("Villains", villain_names or []),
            ("Creatures", creature_names or []),
            ("Places", place_names or []),
        ),
        palette=palette,
        open_entity_callback=open_entity_callback,
        visible_limit=6,
    )

    return entities_block


def _create_maps_block(parent, map_names, gm_view_ref):
    palette = get_detail_palette()
    if not map_names:
        return None

    maps_block = ctk.CTkFrame(parent, fg_color=palette["surface_elevated"], corner_radius=16, border_width=1, border_color=palette["muted_border"])
    maps_block.pack(fill="x", padx=12, pady=(0, 0))
    _create_section_title(maps_block, "Maps")

    interactive = bool(gm_view_ref and hasattr(gm_view_ref, "open_map_tool"))
    if not interactive:
        names_row = ctk.CTkFrame(maps_block, fg_color="transparent")
        names_row.pack(fill="x", padx=12, pady=(0, 2))
        for name in map_names:
            CTkLabel(names_row, text=name).pack(side="left", padx=4, pady=2)
        return maps_block

    gallery = ctk.CTkFrame(maps_block, fg_color="transparent")
    gallery.pack(fill="x", padx=12, pady=(0, 2))
    has_thumbnail_provider = hasattr(gm_view_ref, "get_map_thumbnail")

    for name in map_names:
        display_name = name or "(Unnamed Map)"
        tile = ctk.CTkFrame(gallery, fg_color=palette["surface_overlay"], corner_radius=12, border_width=1, border_color=palette["muted_border"])
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

        def _open_map(_event=None, map_name=name):
            try:
                gm_view_ref.open_map_tool(map_name)
            except Exception:
                pass

        tile.bind("<Button-1>", _open_map)
        img_label.bind("<Button-1>", _open_map)
        name_label.bind("<Button-1>", _open_map)

    return maps_block


def _create_links_block(parent, links, open_scene_callback=None):
    palette = get_detail_palette()
    if not links:
        return None

    links_block = ctk.CTkFrame(parent, fg_color=palette["surface_elevated"], corner_radius=16, border_width=1, border_color=palette["muted_border"])
    links_block.pack(fill="x", padx=12, pady=(0, 0))
    _create_section_title(links_block, "Links")

    selected_link = {"button": None}

    for link in links:
        text_val = str(link.get("text") or "").strip()
        target_val = link.get("target")
        resolved_target = link.get("resolved_target_key")
        if isinstance(target_val, (int, float)):
            target_display = f"Scene {int(target_val)}"
        elif target_val:
            target_display = str(target_val)
        else:
            target_display = "(unspecified)"
        if not text_val:
            text_val = "(no link text)"
        is_clickable = bool(open_scene_callback and resolved_target)

        link_button = ctk.CTkButton(
            links_block,
            text=f"➤ {text_val} → {target_display}",
            anchor="w",
            height=30,
            corner_radius=10,
            border_width=1,
            border_color=palette["muted_border"],
            fg_color=palette["surface_overlay"],
            hover_color=palette["hero_band"],
            text_color=palette["text"],
            state="normal" if is_clickable else "disabled",
        )
        link_button.pack(fill="x", padx=14, pady=(0, 8))

        if not is_clickable:
            continue

        def _on_link_click(target=resolved_target, button=link_button):
            opened = bool(open_scene_callback(target))
            if not opened:
                return
            previous_button = selected_link.get("button")
            if previous_button is not None and previous_button.winfo_exists():
                previous_button.configure(
                    fg_color=palette["surface_overlay"],
                    border_color=palette["muted_border"],
                    text_color=palette["text"],
                )
            button.configure(
                fg_color=palette["accent"],
                border_color=palette["accent_hover"],
                text_color=palette["text"],
            )
            selected_link["button"] = button

        link_button.configure(command=_on_link_click)

    return links_block


def build_scene_body_sections(
    parent,
    body_text,
    npc_names,
    villain_names,
    creature_names,
    place_names,
    map_names,
    links,
    open_entity_callback=None,
    open_scene_callback=None,
    gm_view_ref=None,
):
    has_entities = bool(npc_names or villain_names or creature_names or place_names)
    has_maps = bool(map_names)
    has_links = bool(links)

    shell = _create_section_shell(parent)

    description_block, description_label = _create_description_block(shell, body_text)
    if has_entities or has_maps or has_links:
        _add_subtle_separator(shell)

    entities_block = _create_entities_block(
        shell,
        npc_names,
        villain_names,
        creature_names,
        place_names,
        open_entity_callback=open_entity_callback,
    )
    if entities_block is not None and (has_maps or has_links):
        _add_subtle_separator(shell)

    maps_block = _create_maps_block(shell, map_names, gm_view_ref)
    if maps_block is not None and has_links:
        _add_subtle_separator(shell)

    links_block = _create_links_block(shell, links, open_scene_callback=open_scene_callback)

    return {
        "description_block": description_block,
        "entities_block": entities_block,
        "maps_block": maps_block,
        "links_block": links_block,
        "description_label": description_label,
    }
