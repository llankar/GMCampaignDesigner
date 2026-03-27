import customtkinter as ctk
from customtkinter import CTkLabel

from modules.generic.detail_ui import get_detail_palette
from modules.scenarios.widgets.scene_body import create_entities_groups_grid, prepare_entities_for_group
from modules.scenarios.widgets.scene_density import get_scene_density_style
from modules.scenarios.widgets.scene_sections_parser import parse_scene_body_sections


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


def _create_description_block_fallback(parent, body_text, *, description_font_size=13):
    palette = get_detail_palette()
    description_block = ctk.CTkFrame(parent, fg_color=palette["surface_overlay"], corner_radius=16, border_width=1, border_color=palette["pill_border"])
    description_block.pack(fill="x", padx=12, pady=(12, 0))

    _create_section_title(description_block, "Description")
    clean_text = str(body_text or "").strip()
    has_description = bool(clean_text)
    fallback_text = "Aucune note de mise en scène"
    full_text = clean_text if has_description else fallback_text

    description_font = ctk.CTkFont(size=description_font_size)
    fallback_font = ctk.CTkFont(size=description_font_size, slant="italic")
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

    def _refresh_description_wrap(_event=None):
        wrap_px = max(200, description_block.winfo_width() - 32)
        description_label.configure(wraplength=wrap_px, text=full_text)

    description_block.bind("<Configure>", _refresh_description_wrap, add="+")
    _refresh_description_wrap()
    return description_block, description_label


def _build_hero_text(raw_intro, sections):
    intro = str(raw_intro or "").strip()
    if intro:
        return intro
    else:
        candidates = []
        for section in sections:
            if section.get("items"):
                candidates.extend(section["items"][:2])
            if len(candidates) >= 3:
                break

    hero_lines = []
    for line in candidates:
        compact = " ".join(str(line).split())
        if not compact:
            continue
        hero_lines.append(compact)
        if len(hero_lines) == 3:
            break

    return "\n".join(hero_lines).strip()


def _render_card_bullets(container, items, *, expanded, font_size):
    for child in container.winfo_children():
        child.destroy()

    shown_items = items if expanded else items[:4]
    labels = []
    for item in shown_items:
        text = " ".join(str(item).split())
        if not expanded and len(text) > 170:
            text = text[:167].rstrip() + "…"
        label = ctk.CTkLabel(
            container,
            text=f"• {text}",
            justify="left",
            anchor="w",
            text_color=get_detail_palette()["muted_text"],
            wraplength=0,
            font=ctk.CTkFont(size=max(11, font_size - 1)),
        )
        label.pack(fill="x", padx=10, pady=(0, 4))
        labels.append(label)

    if not labels:
        empty = ctk.CTkLabel(
            container,
            text="• —",
            justify="left",
            anchor="w",
            text_color=get_detail_palette()["muted_text"],
            font=ctk.CTkFont(size=max(11, font_size - 1), slant="italic"),
        )
        empty.pack(fill="x", padx=10, pady=(0, 4))
        labels.append(empty)

    def _refresh_wrap(_event=None):
        wrap_px = max(180, container.winfo_width() - 20)
        for current in labels:
            current.configure(wraplength=wrap_px)

    container.bind("<Configure>", _refresh_wrap, add="+")
    _refresh_wrap()


def _create_description_block(parent, body_text, *, description_font_size=13):
    palette = get_detail_palette()
    parsed = parse_scene_body_sections(body_text)
    if not parsed.get("has_sections"):
        return _create_description_block_fallback(parent, body_text, description_font_size=description_font_size)

    description_block = ctk.CTkFrame(parent, fg_color=palette["surface_overlay"], corner_radius=16, border_width=1, border_color=palette["pill_border"])
    description_block.pack(fill="x", padx=12, pady=(12, 0))
    _create_section_title(description_block, "Description")

    hero_strip = ctk.CTkFrame(
        description_block,
        fg_color=palette["hero_band"],
        corner_radius=12,
        border_width=1,
        border_color=palette["muted_border"],
    )
    hero_strip.pack(fill="x", padx=12, pady=(0, 10))

    hero_text = _build_hero_text(parsed.get("intro_text"), parsed.get("sections") or []) or "Aucune note de mise en scène"
    description_label = ctk.CTkLabel(
        hero_strip,
        text=hero_text,
        justify="left",
        anchor="w",
        wraplength=0,
        text_color=palette["text"],
        font=ctk.CTkFont(size=description_font_size, weight="bold"),
    )
    description_label.pack(fill="x", padx=12, pady=(10, 10))

    cards_grid = ctk.CTkFrame(description_block, fg_color="transparent")
    cards_grid.pack(fill="x", padx=12, pady=(0, 10))
    cards_grid.grid_columnconfigure(0, weight=1)
    cards_grid.grid_columnconfigure(1, weight=1)

    for index, section in enumerate(parsed.get("sections") or []):
        row = index // 2
        col = index % 2
        card = ctk.CTkFrame(
            cards_grid,
            fg_color=palette["surface_card"],
            corner_radius=12,
            border_width=1,
            border_color=palette["muted_border"],
        )
        card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

        title = ctk.CTkLabel(
            card,
            text=f"{section.get('emoji', '•')} {section.get('title', '')}",
            justify="left",
            anchor="w",
            text_color=palette["text"],
            font=ctk.CTkFont(size=max(12, description_font_size - 1), weight="bold"),
        )
        title.pack(fill="x", padx=10, pady=(8, 6))

        bullet_container = ctk.CTkFrame(card, fg_color="transparent")
        bullet_container.pack(fill="x", padx=0, pady=(0, 2))

        items = section.get("items") or [section.get("raw_text")]
        is_expanded = ctk.BooleanVar(master=card, value=False)

        def _refresh_card(*, container=bullet_container, values=items, state=is_expanded):
            _render_card_bullets(
                container,
                values,
                expanded=state.get(),
                font_size=description_font_size,
            )

        _refresh_card()

        if len(items) > 4:
            toggle = ctk.CTkButton(
                card,
                text="Voir plus",
                height=24,
                corner_radius=8,
                fg_color="transparent",
                hover_color=palette["surface_overlay"],
                text_color=palette["accent"],
                border_width=1,
                border_color=palette["pill_border"],
            )
            toggle.pack(anchor="w", padx=10, pady=(0, 8))

            def _toggle_section(
                *,
                state=is_expanded,
                button=toggle,
                refresh=_refresh_card,
            ):
                state.set(not state.get())
                button.configure(text="Voir moins" if state.get() else "Voir plus")
                refresh()

            toggle.configure(command=_toggle_section)

    def _refresh_hero_wrap(_event=None):
        wrap_px = max(220, hero_strip.winfo_width() - 24)
        description_label.configure(wraplength=wrap_px)

    hero_strip.bind("<Configure>", _refresh_hero_wrap, add="+")
    _refresh_hero_wrap()

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
            ("NPCs", prepare_entities_for_group(npc_names or [])),
            ("Villains", prepare_entities_for_group(villain_names or [])),
            ("Creatures", prepare_entities_for_group(creature_names or [])),
            ("Places", prepare_entities_for_group(place_names or [])),
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
    scene_density="Normal",
):
    density_style = get_scene_density_style(scene_density)
    has_entities = bool(npc_names or villain_names or creature_names or place_names)
    has_maps = bool(map_names)
    has_links = bool(links)

    shell = _create_section_shell(parent)

    description_block, description_label = _create_description_block(
        shell,
        body_text,
        description_font_size=density_style["description_font_size"],
    )
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

    secondary_toggles = {}
    if density_style["collapse_secondary_by_default"]:
        for block_name, block_widget in (("Maps", maps_block), ("Links", links_block)):
            if block_widget is None:
                continue
            toggle_holder = ctk.CTkFrame(shell, fg_color="transparent")
            toggle_holder.pack(fill="x", padx=12, pady=(0, 8), before=block_widget)

            collapsed = ctk.BooleanVar(master=toggle_holder, value=True)
            toggle_button = ctk.CTkButton(
                toggle_holder,
                text=f"▶ {block_name}",
                anchor="w",
                height=24,
                corner_radius=10,
                fg_color="transparent",
                hover_color=get_detail_palette()["surface_card"],
                text_color=get_detail_palette()["muted_text"],
                border_width=1,
                border_color=get_detail_palette()["muted_border"],
            )
            toggle_button.pack(fill="x")
            block_widget.pack_forget()

            def _toggle_section(
                *,
                section=block_name,
                button=toggle_button,
                block=block_widget,
                state=collapsed,
                holder=toggle_holder,
            ):
                now_collapsed = not state.get()
                state.set(now_collapsed)
                if now_collapsed:
                    block.pack_forget()
                    button.configure(text=f"▶ {section}")
                else:
                    block.pack(fill="x", padx=12, pady=(0, 0), after=holder)
                    button.configure(text=f"▼ {section}")

            toggle_button.configure(command=_toggle_section)
            secondary_toggles[block_name.lower()] = {
                "button": toggle_button,
                "collapsed": collapsed,
                "block": block_widget,
            }

    return {
        "description_block": description_block,
        "entities_block": entities_block,
        "maps_block": maps_block,
        "links_block": links_block,
        "description_label": description_label,
        "secondary_toggles": secondary_toggles,
    }
