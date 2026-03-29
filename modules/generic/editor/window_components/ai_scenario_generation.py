from modules.generic.editor.window_context import *


class GenericEditorWindowAIScenarioGeneration:
    def ai_generate_full_scenario(self):
        try:
            theme = self._infer_theme("scenarios")

            # 1) Pick and apply linked entities first (so the AI can use them)
            npcs_list = load_npcs_list()
            creatures_list = load_creatures_list()
            places_list = load_places_list()
            factions_list = load_factions_list()
            objects_list = load_objects_list()

            selected_npcs = random.sample(npcs_list, 3) if len(npcs_list) >= 3 else npcs_list
            selected_places = random.sample(places_list, 3) if len(places_list) >= 3 else places_list
            selected_creatures = random.sample(creatures_list, 3) if len(creatures_list) >= 3 else creatures_list
            selected_factions = random.sample(factions_list, 2) if len(factions_list) >= 2 else factions_list
            selected_objects = random.sample(objects_list, 2) if len(objects_list) >= 2 else objects_list

            # Initial random picks are applied to UI lists

            # Save to self.item
            if selected_npcs is not None:
                self.item["NPCs"] = selected_npcs
            if selected_places is not None:
                self.item["Places"] = selected_places
            if selected_creatures is not None:
                self.item["Creatures"] = selected_creatures
            if selected_factions is not None:
                self.item["Factions"] = selected_factions
            if selected_objects is not None:
                self.item["Objects"] = selected_objects

            # Helper to shrink extra rows for a list of CTkEntry widgets
            def _shrink_widget_list(key, new_size):
                try:
                    lst = self.field_widgets.get(key, []) or []
                    if len(lst) > new_size:
                        for w in lst[new_size:]:
                            try:
                                w.master.destroy()
                            except Exception:
                                pass
                        lst = lst[:new_size]
                        self.field_widgets[key] = lst
                        # keep vars list in sync
                        vkey = f"{key}_vars"
                        vars_list = self.field_widgets.get(vkey, [])
                        if vars_list and len(vars_list) > new_size:
                            self.field_widgets[vkey] = vars_list[:new_size]
                except Exception:
                    pass

            # Update widgets for each list type
            # NPCs
            try:
                npc_widgets = self.field_widgets.get("NPCs", [])
                npc_vars = self.field_widgets.get("NPCs_vars", [])
                add_npc_combobox = self.field_widgets.get("NPCs_add_combobox")
                while len(npc_widgets) < len(selected_npcs) and callable(add_npc_combobox):
                    add_npc_combobox()
                    npc_widgets = self.field_widgets.get("NPCs", [])
                    npc_vars = self.field_widgets.get("NPCs_vars", [])
                _shrink_widget_list("NPCs", len(selected_npcs))
                npc_widgets = self.field_widgets.get("NPCs", [])
                npc_vars = self.field_widgets.get("NPCs_vars", [])
                for i in range(min(len(npc_widgets), len(selected_npcs))):
                    try:
                        npc_vars[i].set(selected_npcs[i])
                    except Exception:
                        widget = npc_widgets[i]
                        widget.configure(state="normal")
                        widget.delete(0, "end")
                        widget.insert(0, selected_npcs[i])
                        widget.configure(state="readonly")
            except Exception:
                pass
            # Creatures
            try:
                creature_widgets = self.field_widgets.get("Creatures", [])
                creature_vars = self.field_widgets.get("Creatures_vars", [])
                add_creatures_combobox = self.field_widgets.get("Creatures_add_combobox")
                while len(creature_widgets) < len(selected_creatures) and callable(add_creatures_combobox):
                    add_creatures_combobox()
                    creature_widgets = self.field_widgets.get("Creatures", [])
                    creature_vars = self.field_widgets.get("Creatures_vars", [])
                _shrink_widget_list("Creatures", len(selected_creatures))
                creature_widgets = self.field_widgets.get("Creatures", [])
                creature_vars = self.field_widgets.get("Creatures_vars", [])
                for i in range(min(len(creature_widgets), len(selected_creatures))):
                    try:
                        creature_vars[i].set(selected_creatures[i])
                    except Exception:
                        widget = creature_widgets[i]
                        widget.configure(state="normal")
                        widget.delete(0, "end")
                        widget.insert(0, selected_creatures[i])
                        widget.configure(state="readonly")
            except Exception:
                pass
            # Places
            try:
                place_widgets = self.field_widgets.get("Places", [])
                place_vars = self.field_widgets.get("Places_vars", [])
                add_place_combobox = self.field_widgets.get("Places_add_combobox")
                while len(place_widgets) < len(selected_places) and callable(add_place_combobox):
                    add_place_combobox()
                    place_widgets = self.field_widgets.get("Places", [])
                    place_vars = self.field_widgets.get("Places_vars", [])
                _shrink_widget_list("Places", len(selected_places))
                place_widgets = self.field_widgets.get("Places", [])
                place_vars = self.field_widgets.get("Places_vars", [])
                for i in range(min(len(place_widgets), len(selected_places))):
                    try:
                        place_vars[i].set(selected_places[i])
                    except Exception:
                        widget = place_widgets[i]
                        widget.configure(state="normal")
                        widget.delete(0, "end")
                        widget.insert(0, selected_places[i])
                        widget.configure(state="readonly")
            except Exception:
                pass
            # Factions
            try:
                faction_widgets = self.field_widgets.get("Factions", [])
                faction_vars = self.field_widgets.get("Factions_vars", [])
                add_faction_combobox = self.field_widgets.get("Factions_add_combobox")
                while len(faction_widgets) < len(selected_factions) and callable(add_faction_combobox):
                    add_faction_combobox()
                    faction_widgets = self.field_widgets.get("Factions", [])
                    faction_vars = self.field_widgets.get("Factions_vars", [])
                _shrink_widget_list("Factions", len(selected_factions))
                faction_widgets = self.field_widgets.get("Factions", [])
                faction_vars = self.field_widgets.get("Factions_vars", [])
                for i in range(min(len(faction_widgets), len(selected_factions))):
                    try:
                        faction_vars[i].set(selected_factions[i])
                    except Exception:
                        widget = faction_widgets[i]
                        widget.configure(state="normal")
                        widget.delete(0, "end")
                        widget.insert(0, selected_factions[i])
                        widget.configure(state="readonly")
            except Exception:
                pass
            # Objects
            try:
                object_widgets = self.field_widgets.get("Objects", [])
                object_vars = self.field_widgets.get("Objects_vars", [])
                add_object_combobox = self.field_widgets.get("Objects_add_combobox")
                while len(object_widgets) < len(selected_objects) and callable(add_object_combobox):
                    add_object_combobox()
                    object_widgets = self.field_widgets.get("Objects", [])
                    object_vars = self.field_widgets.get("Objects_vars", [])
                _shrink_widget_list("Objects", len(selected_objects))
                object_widgets = self.field_widgets.get("Objects", [])
                object_vars = self.field_widgets.get("Objects_vars", [])
                for i in range(min(len(object_widgets), len(selected_objects))):
                    try:
                        object_vars[i].set(selected_objects[i])
                    except Exception:
                        widget = object_widgets[i]
                        widget.configure(state="normal")
                        widget.delete(0, "end")
                        widget.insert(0, selected_objects[i])
                        widget.configure(state="readonly")
            except Exception:
                pass

            # 2) Read back values actually present in the UI, to ensure prompt matches what user sees
            def _read_list_from_widgets(name):
                try:
                    widgets = self.field_widgets.get(name, [])
                    vals = []
                    for w in widgets:
                        try:
                            v = w.get()
                        except Exception:
                            v = None
                        if v:
                            vals.append(v)
                    return vals
                except Exception:
                    return []

            # Ensure UI has applied changes, then read exact values from widgets
            try:
                self.update_idletasks()
            except Exception:
                pass
            selected_npcs = _read_list_from_widgets("NPCs")
            selected_places = _read_list_from_widgets("Places")
            selected_creatures = _read_list_from_widgets("Creatures")
            selected_factions = _read_list_from_widgets("Factions")
            selected_objects = _read_list_from_widgets("Objects")
            # At this point, values reflect the on-screen selections

            # 3) Build a context block describing these selected entities for coherence
            def _plain_text(val):
                try:
                    if isinstance(val, dict):
                        return str(val.get("text", ""))
                    return str(val)
                except Exception:
                    return ""

            def _summarize(record, wanted_fields):
                parts = []
                for f in wanted_fields:
                    v = record.get(f)
                    if not v:
                        continue
                    s = _plain_text(v).strip()
                    if not s:
                        continue
                    parts.append(f"{f}: {s[:220]}")
                return ", ".join(parts) or "(no details)"

            def _index_items(entity_type):
                try:
                    items = GenericModelWrapper(entity_type).load_items()
                except Exception:
                    items = []
                by_name = {}
                for it in items:
                    nm = it.get("Name") or it.get("Title")
                    if nm:
                        by_name[str(nm)] = it
                return by_name

            ctx_lines = []
            # Index maps for lookups
            idx_npcs = _index_items("npcs")
            idx_places = _index_items("places")
            idx_creatures = _index_items("creatures")
            idx_factions = _index_items("factions")
            idx_objects = _index_items("objects")

            if selected_npcs:
                ctx_lines.append("NPCs:")
                for n in selected_npcs:
                    rec = idx_npcs.get(n, {})
                    ctx_lines.append(f"- {n}: " + _summarize(rec, ["Role","Description","Background","Traits","Motivation","Personality","RoleplayingCues"]))
            if selected_places:
                ctx_lines.append("Places:")
                for n in selected_places:
                    rec = idx_places.get(n, {})
                    ctx_lines.append(f"- {n}: " + _summarize(rec, ["Description","Secrets"]))
            if selected_creatures:
                ctx_lines.append("Creatures:")
                for n in selected_creatures:
                    rec = idx_creatures.get(n, {})
                    ctx_lines.append(f"- {n}: " + _summarize(rec, ["Type","Description","Powers","Weakness","Background"]))
            if selected_factions:
                ctx_lines.append("Factions:")
                for n in selected_factions:
                    rec = idx_factions.get(n, {})
                    ctx_lines.append(f"- {n}: " + _summarize(rec, ["Description","Secrets"]))
            if selected_objects:
                ctx_lines.append("Objects:")
                for n in selected_objects:
                    rec = idx_objects.get(n, {})
                    ctx_lines.append(f"- {n}: " + _summarize(rec, ["Description","Secrets"]))
            entities_context = "\n".join(ctx_lines)

            # 4) Gather sample titles/summaries (optional flavor only)
            try:
                samples = GenericModelWrapper("scenarios").load_items()
            except Exception:
                samples = []
            examples = []
            for it in samples[:5]:
                t = it.get("Title") or it.get("Name")
                s = it.get("Summary") or it.get("Description")
                if t:
                    examples.append(f"- {t}: {str(s)[:140] if s else ''}")
            examples_text = "\n".join(examples)

            system = (
                "You are an RPG scenario generator. Produce concise, game-ready content. "
                "Write evocative but brief prose. Return ONLY compact JSON without code fences."
            )
            user = (
                f"Theme: {theme}\n"
                f"Use EXACTLY these selected entities (names must match; do not rename or invent new proper nouns):\n{', '.join(selected_npcs or [])} | {', '.join(selected_places or [])} | {', '.join(selected_creatures or [])} | {', '.join(selected_factions or [])} | {', '.join(selected_objects or [])}\n\n"
                f"Entity details for coherence:\n{entities_context}\n\n"
                f"Existing examples (optional):\n{examples_text}\n\n"
                "Task: Generate a scenario object with fields:\n"
                "{\n"
                "  \"Title\": string,\n"
                "  \"Summary\": string (1-3 short paragraphs, Markdown allowed),\n"
                "  \"Secrets\": string (a single compact secret),\n"
                "  \"Scenes\": [string, ...] (3-5 concise scene beats; reference the selected entities by NAME)\n"
                "}\n"
                "Constraints: Integrate the selected entities coherently. No extra keys. No code blocks. Keep within ~600 words."
            )
            # Build prompt and call AI
            content = execute_ai_chat(
                self._get_ai(),
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                pipeline_name="editor.scenario_generation.full",
                phase="scenario_generation",
                phase_message="Generating scenario content",
            )
            data = None
            try:
                data = LocalAIClient._parse_json_safe(content)
            except Exception:
                # If not JSON, fallback: put entire text into Summary
                data = {"Title": "Generated Scenario", "Summary": content, "Secrets": "", "Scenes": []}

            # Apply fields
            title = data.get("Title") or self.item.get("Title")
            if title:
                self._set_field_text("Title", str(title))

            summary = data.get("Summary")
            if summary:
                self._set_field_text("Summary", str(summary))

            secrets = data.get("Secrets")
            if secrets:
                self._set_field_text("Secrets", str(secrets))

            scenes = data.get("Scenes") or []
            if isinstance(scenes, (list, tuple)):
                editors = self.field_widgets.get("Scenes", [])
                add_scene = self.field_widgets.get("Scenes_add_scene")
                renumber = self.field_widgets.get("Scenes_renumber")
                # Grow to needed count
                while len(editors) < len(scenes) and callable(add_scene):
                    add_scene({})
                    editors = self.field_widgets.get("Scenes", [])
                # Shrink extra
                if len(editors) > len(scenes):
                    for state in editors[len(scenes):]:
                        try:
                            state["frame"].destroy()
                        except Exception:
                            pass
                    del editors[len(scenes):]
                    if callable(renumber):
                        renumber()
                # Populate content
                for state, sc in zip(editors, scenes):
                    editor = state.get("editor")
                    if not editor:
                        continue
                    title_entry = state.get("title_entry")
                    for existing in list(state.get("link_rows", [])):
                        try:
                            existing["frame"].destroy()
                        except Exception:
                            pass
                    state["link_rows"] = []
                    for label, frame in (state.get("entity_chip_frames") or {}).items():
                        state["entities"][label] = []
                        for widget in list(frame.winfo_children()):
                            try:
                                widget.destroy()
                            except Exception:
                                pass
                    raw_text = sc
                    title_value = None
                    if isinstance(sc, dict):
                        title_value = sc.get("Title") or sc.get("Scene")
                        raw_text = sc.get("Text") or sc.get("text") or sc.get("Summary") or sc
                    if title_entry is not None:
                        try:
                            title_entry.delete(0, "end")
                            if title_value:
                                title_entry.insert(0, str(title_value))
                        except Exception:
                            pass
                    try:
                        if isinstance(raw_text, dict) and "text" in raw_text:
                            editor.load_text_data(raw_text)
                        else:
                            editor.load_text_data(ai_text_to_rtf_json(str(raw_text)))
                    except Exception:
                        editor.text_widget.delete("1.0", "end")
                        editor.text_widget.insert("1.0", str(raw_text))

            # End-of-function: UI lists remain as displayed

        except Exception as e:
            messagebox.showerror("AI Error", f"Failed to generate scenario: {e}")
