import customtkinter as ctk
from customtkinter import CTkLabel


def _create_section_title(parent, label_text):
    title = ctk.CTkLabel(parent, text=label_text, font=("Arial", 13, "bold"))
    title.pack(anchor="w", padx=12, pady=(0, 4))
    return title


def _add_subtle_separator(parent):
    separator = ctk.CTkFrame(parent, height=1, fg_color="#3A3A3A")
    separator.pack(fill="x", padx=12, pady=(4, 8))
    return separator


def _create_description_block(parent, body_text):
    description_block = ctk.CTkFrame(parent, fg_color="transparent")
    description_block.pack(fill="x", padx=4, pady=(0, 0))

    _create_section_title(description_block, "Description")
    description_label = ctk.CTkLabel(
        description_block,
        text=body_text or "(No scene notes)",
        wraplength=0,
        justify="left",
        font=("Arial", 14),
    )
    description_label.pack(fill="x", padx=12, pady=(0, 2))
    return description_block, description_label


def _create_entities_block(parent, npc_names, creature_names, place_names, open_entity_callback=None):
    has_entities = bool(npc_names or creature_names or place_names)
    if not has_entities:
        return None

    entities_block = ctk.CTkFrame(parent, fg_color="transparent")
    entities_block.pack(fill="x", padx=4, pady=(0, 0))
    _create_section_title(entities_block, "Entities")

    for label_text, names in (("NPCs", npc_names), ("Creatures", creature_names), ("Places", place_names)):
        if not names:
            continue
        row = ctk.CTkFrame(entities_block, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(row, text=f"{label_text}:", font=("Arial", 12, "bold")).pack(anchor="w")
        chips = ctk.CTkFrame(row, fg_color="transparent")
        chips.pack(fill="x", padx=10, pady=(1, 0))

        for name in names:
            can_open = callable(open_entity_callback)
            chip = ctk.CTkLabel(
                chips,
                text=name,
                text_color="#00BFFF" if can_open else "white",
                cursor="hand2" if can_open else "",
            )
            chip.pack(side="left", padx=4, pady=2)
            if can_open:
                chip.bind(
                    "<Button-1>",
                    lambda _event=None, t=label_text, n=name: open_entity_callback(t, n),
                )

    return entities_block


def _create_maps_block(parent, map_names, gm_view_ref):
    if not map_names:
        return None

    maps_block = ctk.CTkFrame(parent, fg_color="transparent")
    maps_block.pack(fill="x", padx=4, pady=(0, 0))
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
    if not links:
        return None

    links_block = ctk.CTkFrame(parent, fg_color="transparent")
    links_block.pack(fill="x", padx=4, pady=(0, 0))
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
            font=("Arial", 12),
            justify="left",
        ).pack(anchor="w", padx=24, pady=1)

    return links_block


def build_scene_body_sections(
    parent,
    body_text,
    npc_names,
    creature_names,
    place_names,
    map_names,
    links,
    open_entity_callback=None,
    gm_view_ref=None,
):
    has_entities = bool(npc_names or creature_names or place_names)
    has_maps = bool(map_names)
    has_links = bool(links)

    description_block, description_label = _create_description_block(parent, body_text)
    if has_entities or has_maps or has_links:
        _add_subtle_separator(parent)

    entities_block = _create_entities_block(
        parent,
        npc_names,
        creature_names,
        place_names,
        open_entity_callback=open_entity_callback,
    )
    if entities_block is not None and (has_maps or has_links):
        _add_subtle_separator(parent)

    maps_block = _create_maps_block(parent, map_names, gm_view_ref)
    if maps_block is not None and has_links:
        _add_subtle_separator(parent)

    links_block = _create_links_block(parent, links)

    return {
        "description_block": description_block,
        "entities_block": entities_block,
        "maps_block": maps_block,
        "links_block": links_block,
        "description_label": description_label,
    }
