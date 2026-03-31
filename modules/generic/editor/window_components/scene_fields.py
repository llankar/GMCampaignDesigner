"""Field helpers for window components scene."""

from modules.generic.editor.window_context import *


class GenericEditorWindowSceneFields:
    def create_dynamic_longtext_list(self, field):
        """Create dynamic longtext list."""
        container = ctk.CTkFrame(self._field_parent())
        container.pack(fill="x", pady=4)

        editors = []
        entity_type_map = {
            "NPCs": "npcs",
            "Villains": "villains",
            "Creatures": "creatures",
            "Bases": "bases",
            "Places": "places",
            "Maps": "maps",
        }
        entity_wrappers = {}
        entity_templates = {}

        def _get_wrapper(label):
            """Return wrapper."""
            if label not in entity_wrappers:
                key = entity_type_map[label]
                entity_wrappers[label] = GenericModelWrapper(key)
                entity_templates[label] = load_template(key)
            return entity_wrappers[label], entity_templates[label]

        def renumber_scenes():
            """Handle renumber scenes."""
            for idx, state in enumerate(editors, start=1):
                # Process each (idx, state) from enumerate(editors, start=1).
                label = state.get("index_label")
                if label:
                    label.configure(text=f"Scene {idx}")

        def remove_scene(state):
            """Remove scene."""
            if state in editors:
                # Handle the branch where state is in editors.
                editors.remove(state)
                try:
                    state["frame"].destroy()
                except Exception:
                    pass
                renumber_scenes()

        def _coerce_names(value):
            """Coerce names."""
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
            """Coerce links."""
            result = []
            if value is None:
                return result
            if isinstance(value, list):
                # Handle the branch where isinstance(value, list).
                for item in value:
                    result.extend(_coerce_links(item))
                return result
            if isinstance(value, dict):
                # Handle the branch where isinstance(value, dict).
                target = None
                text = None
                for key in ("Target", "target", "Scene", "scene", "Next", "next", "Id", "id"):
                    if key in value:
                        target = value[key]
                        break
                for key in ("Text", "text", "Label", "label", "Description", "description", "Choice", "choice"):
                    if key in value:
                        text = value[key]
                        break
                result.append({"target": target, "text": text})
                return result
            if isinstance(value, (int, float)):
                result.append({"target": int(value), "text": ""})
                return result
            text = str(value).strip()
            if text:
                result.append({"target": text, "text": text})
            return result

        def refresh_entity_chips(state, label):
            """Refresh entity chips."""
            frame = state["entity_chip_frames"].get(label)
            if not frame:
                return
            for child in frame.winfo_children():
                child.destroy()

            entries = state["entities"].get(label, [])
            if not entries:
                # Handle the branch where entries is unavailable.
                if frame.winfo_manager():
                    frame.pack_forget()
                return

            if not frame.winfo_manager():
                frame.pack(fill="x", padx=20, pady=(1, 0))

            for name in entries:
                chip = ctk.CTkFrame(frame, fg_color="#3A3A3A")
                chip.pack(side="left", padx=4, pady=2)
                ctk.CTkLabel(chip, text=name).pack(side="left", padx=(6, 2))

                def _remove(n=name, lbl=label, st=state, widget=chip):
                    """Remove the operation."""
                    st["entities"][lbl] = [x for x in st["entities"].get(lbl, []) if x != n]
                    widget.destroy()
                    if not st["entities"].get(lbl):
                        frame.pack_forget()

                ctk.CTkButton(chip, text="×", width=24, command=_remove).pack(side="left", padx=(0, 6))

        def add_entity(state, label, name):
            """Handle add entity."""
            cleaned = str(name).strip()
            if not cleaned:
                return
            entries = state["entities"].setdefault(label, [])
            if cleaned in entries:
                return
            entries.append(cleaned)
            refresh_entity_chips(state, label)

        def open_entity_picker(state, label):
            """Open entity picker."""
            wrapper, template = _get_wrapper(label)
            dialog = ctk.CTkToplevel(self)
            dialog.title(f"Select {label[:-1] if label.endswith('s') else label}")
            dialog.geometry("1200x700")
            dialog.transient(self)
            dialog.grab_set()

            def _on_select(entity_type, name):
                """Handle select."""
                add_entity(state, label, name)
                if dialog.winfo_exists():
                    dialog.destroy()

            view = GenericListSelectionView(
                dialog,
                label,
                wrapper,
                template,
                on_select_callback=_on_select,
            )
            view.pack(fill="both", expand=True)
            dialog.wait_window()

        def remove_link(state, link_state):
            """Remove link."""
            if link_state in state.get("link_rows", []):
                # Handle the branch where link state is in state.get('link_rows', []).
                state["link_rows"].remove(link_state)
                try:
                    link_state["frame"].destroy()
                except Exception:
                    pass

            container = state.get("links_container")
            if container is not None and not container.winfo_children():
                container.pack_forget()

        def add_link_row(state, link=None):
            """Handle add link row."""
            container = state["links_container"]
            if not container.winfo_manager():
                container.pack(fill="x", padx=16, pady=(2, 2))

            link_row = ctk.CTkFrame(container, fg_color="transparent")
            link_row.pack(fill="x", pady=1)
            target_entry = ctk.CTkEntry(link_row, placeholder_text="Target scene (name or number)")
            target_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
            text_entry = ctk.CTkEntry(link_row, placeholder_text="Displayed link text")
            text_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
            link_state = {
                "frame": link_row,
                "target_entry": target_entry,
                "text_entry": text_entry,
            }
            ctk.CTkButton(
                link_row,
                text="–",
                width=40,
                command=lambda st=state, ls=link_state: remove_link(st, ls),
            ).pack(side="left")

            if isinstance(link, dict):
                # Handle the branch where isinstance(link, dict).
                target_val = link.get("target")
                text_val = link.get("text")
                if target_val is not None:
                    target_entry.insert(0, str(target_val))
                if text_val:
                    text_entry.insert(0, str(text_val))

            state.setdefault("link_rows", []).append(link_state)

        def add_scene(initial_data=None):
            """Handle add scene."""
            data = initial_data
            if data is None:
                data = {}
            elif isinstance(data, (str, list)):
                data = {"Text": data}
            elif not isinstance(data, dict):
                data = {"Text": data}

            row = ctk.CTkFrame(container)
            row.pack(fill="x", pady=(0, 8))

            header = ctk.CTkFrame(row, fg_color="transparent")
            header.pack(fill="x", pady=(0, 2))

            scene_state = {"frame": row}

            index_label = ctk.CTkLabel(header, text="")
            index_label.pack(side="left")
            scene_state["index_label"] = index_label

            title_entry = ctk.CTkEntry(header, placeholder_text="Scene title")
            title_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
            title_value = data.get("Title") or data.get("Scene") or ""
            if isinstance(title_value, str) and title_value.strip():
                title_entry.insert(0, title_value.strip())
            scene_state["title_entry"] = title_entry

            ctk.CTkButton(
                header,
                text="– Remove",
                width=100,
                command=lambda st=scene_state: remove_scene(st),
            ).pack(side="right")

            text_data = data.get("Text") or data.get("text") or ""
            rte = self._make_richtext_editor(row, text_data, hide_toolbar=True, max_lines=12)
            rte.pack_configure(pady=4)
            scene_state["editor"] = rte

            entity_section = ctk.CTkFrame(row, fg_color="transparent")
            entity_section.pack(fill="x", padx=4, pady=(2, 2))
            scene_state["entities"] = {}
            scene_state["entity_chip_frames"] = {}

            for label in entity_type_map:
                # Process each label from entity_type_map.
                block = ctk.CTkFrame(entity_section, fg_color="transparent")
                block.pack(fill="x", pady=(1, 0))

                header_frame = ctk.CTkFrame(block, fg_color="transparent")
                header_frame.pack(fill="x")
                ctk.CTkLabel(header_frame, text=f"{label}:").pack(side="left")
                ctk.CTkButton(
                    header_frame,
                    text=f"+ Add {label[:-1] if label.endswith('s') else label}",
                    width=160,
                    command=lambda st=scene_state, lbl=label: open_entity_picker(st, lbl),
                ).pack(side="left", padx=(8, 0))

                chip_frame = ctk.CTkFrame(block, fg_color="transparent")
                scene_state["entity_chip_frames"][label] = chip_frame
                scene_state["entities"][label] = _coerce_names(data.get(label))
                refresh_entity_chips(scene_state, label)

            links_outer = ctk.CTkFrame(row, fg_color="transparent")
            links_outer.pack(fill="x", padx=4, pady=(4, 0))
            ctk.CTkLabel(links_outer, text="Scene Links:").pack(anchor="w")

            links_container = ctk.CTkFrame(links_outer, fg_color="transparent")
            scene_state["links_container"] = links_container
            scene_state["link_rows"] = []

            for link in _coerce_links(data.get("Links")):
                add_link_row(scene_state, link)

            ctk.CTkButton(
                links_outer,
                text="+ Add Link",
                width=110,
                command=lambda st=scene_state: add_link_row(st),
            ).pack(anchor="w", padx=16, pady=(0, 2))

            editors.append(scene_state)
            renumber_scenes()
            return scene_state

        scenes_data = self.item.get(field["name"])
        if isinstance(scenes_data, dict) and isinstance(scenes_data.get("Scenes"), list):
            scenes_iterable = scenes_data.get("Scenes", [])
        elif isinstance(scenes_data, list):
            scenes_iterable = scenes_data
        elif scenes_data is None:
            scenes_iterable = []
        else:
            scenes_iterable = [scenes_data]

        for scene in scenes_iterable:
            add_scene(scene)

        ctk.CTkButton(
            container,
            text="+ Add Scene",
            command=lambda: add_scene({}),
        ).pack(anchor="w", pady=(4, 0))

        self.field_widgets[field["name"]] = editors
        self.field_widgets[f"{field['name']}_container"] = container
        self.field_widgets[f"{field['name']}_add_scene"] = add_scene
        self.field_widgets[f"{field['name']}_renumber"] = renumber_scenes
    def create_character_links_field(self, field):
        """Create character links field."""
        container = ctk.CTkFrame(self._field_parent())
        container.pack(fill="x", pady=4)

        description = ctk.CTkLabel(
            container,
            text="Managed by the Character Graph editor.",
            text_color="#A0A0A0",
        )
        description.pack(anchor="w", padx=4, pady=(0, 4))

        links = self.item.get(field["name"], [])
        if not isinstance(links, list):
            links = []

        if not links:
            ctk.CTkLabel(container, text="No links yet.").pack(anchor="w", padx=4)
        else:
            for link in links:
                # Process each link from links.
                if isinstance(link, dict):
                    # Handle the branch where isinstance(link, dict).
                    target_type = link.get("target_type") or "unknown"
                    target_name = link.get("target_name") or "unknown"
                    label = link.get("label") or ""
                    arrow_mode = link.get("arrow_mode") or "both"
                    parts = [f"{target_type.upper()}: {target_name}"]
                    if label:
                        parts.append(f"label: {label}")
                    if arrow_mode:
                        parts.append(f"arrow: {arrow_mode}")
                    text = " | ".join(parts)
                else:
                    text = str(link)
                ctk.CTkLabel(container, text=text, wraplength=900, justify="left").pack(
                    anchor="w",
                    padx=4,
                    pady=2,
                )

        self.field_widgets[field["name"]] = links
