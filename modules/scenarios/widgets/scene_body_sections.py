import customtkinter as ctk
from customtkinter import CTkLabel

from modules.generic.detail_ui import create_chip, get_detail_palette


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
    description_label = ctk.CTkLabel(
        description_block,
        text=body_text or "(No scene notes)",
        wraplength=0,
        justify="left",
        font=ctk.CTkFont(size=13),
        text_color=palette["muted_text"],
        anchor="w",
    )
    description_label.pack(fill="x", padx=14, pady=(0, 14))
    return description_block, description_label


def _create_entities_block(parent, npc_names, villain_names, creature_names, place_names, open_entity_callback=None):
    palette = get_detail_palette()
    has_entities = bool(npc_names or villain_names or creature_names or place_names)
    if not has_entities:
        return None

    entities_block = ctk.CTkFrame(parent, fg_color=palette["surface_elevated"], corner_radius=16, border_width=1, border_color=palette["muted_border"])
    entities_block.pack(fill="x", padx=12, pady=(0, 0))
    _create_section_title(entities_block, "Entities")

    for label_text, names in (("NPCs", npc_names), ("Villains", villain_names), ("Creatures", creature_names), ("Places", place_names)):
        if not names:
            continue
        row = ctk.CTkFrame(row_parent := entities_block, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(
            row,
            text=f"{label_text}:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=palette["text"],
        ).pack(anchor="w")
        chips = ctk.CTkFrame(row, fg_color="transparent")
        chips.pack(fill="x", padx=0, pady=(4, 0))

        for name in names:
            can_open = callable(open_entity_callback)
            chip = create_chip(chips, name)
            chip.pack(side="left", padx=(0, 6), pady=2)
            if can_open:
                chip.configure(cursor="hand2")
                for child in chip.winfo_children():
                    child.configure(cursor="hand2")
            if can_open:
                chip.bind(
                    "<Button-1>",
                    lambda _event=None, t=label_text, n=name: open_entity_callback(t, n),
                )
                for child in chip.winfo_children():
                    child.bind(
                        "<Button-1>",
                        lambda _event=None, t=label_text, n=name: open_entity_callback(t, n),
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


def _create_links_block(parent, links):
    palette = get_detail_palette()
    if not links:
        return None

    links_block = ctk.CTkFrame(parent, fg_color=palette["surface_elevated"], corner_radius=16, border_width=1, border_color=palette["muted_border"])
    links_block.pack(fill="x", padx=12, pady=(0, 0))
    _create_section_title(links_block, "Links")

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
            links_block,
            text=f"• {text_val} → {target_display}",
            font=ctk.CTkFont(size=12),
            justify="left",
            text_color=palette["muted_text"],
            anchor="w",
        ).pack(anchor="w", padx=14, pady=(0, 8))

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

    links_block = _create_links_block(shell, links)

    return {
        "description_block": description_block,
        "entities_block": entities_block,
        "maps_block": maps_block,
        "links_block": links_block,
        "description_label": description_label,
    }
