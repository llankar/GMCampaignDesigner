from modules.generic.editor.window_context import *


class GenericEditorWindowFormActionsAndPersistence:
    def create_action_bar(self):
        action_bar = ctk.CTkFrame(self.main_frame)
        action_bar.pack(fill="x", pady=5)

        ctk.CTkButton(action_bar, text="Cancel", command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(action_bar, text="Save", command=self.save).pack(side="right", padx=5)
        if self.model_wrapper.entity_type== 'scenarios':
            ctk.CTkButton(action_bar, text='Generate Scenario', command=self.generate_scenario).pack(side='left', padx=5)
            ctk.CTkButton(action_bar, text='AI Generate Scenario', command=self.ai_generate_full_scenario).pack(side='left', padx=5)

        if self.model_wrapper.entity_type== 'npcs':
            ctk.CTkButton(action_bar, text='Generate NPC', command=self.generate_npc).pack(side='left', padx=5)
            ctk.CTkButton(action_bar, text='AI Generate NPC', command=self.ai_generate_full_npc).pack(side='left', padx=5)

        if self.model_wrapper.entity_type== 'creatures':
            ctk.CTkButton(action_bar, text='AI Generate Creature', command=self.ai_generate_full_creature).pack(side='left', padx=5)
    def _serialize_scene_states(self, states):
        serialized = []
        for state in states:
            if not isinstance(state, dict):
                continue
            editor = state.get("editor")
            if editor is None:
                continue
            text_data = editor.get_text_data() if hasattr(editor, "get_text_data") else editor.text_widget.get("1.0", "end-1c")
            scene_payload = {}

            title_entry = state.get("title_entry")
            if title_entry:
                title = title_entry.get().strip()
                if title:
                    scene_payload["Title"] = title

            if isinstance(text_data, dict):
                scene_payload["Text"] = text_data
            else:
                scene_payload["Text"] = {"text": str(text_data)}

            for label, names in (state.get("entities") or {}).items():
                if names:
                    scene_payload[label] = list(names)

            links_payload = []
            for link_state in state.get("link_rows", []):
                target_entry = link_state.get("target_entry")
                text_entry = link_state.get("text_entry")
                target_val = target_entry.get().strip() if target_entry else ""
                text_val = text_entry.get().strip() if text_entry else ""
                if not target_val and not text_val:
                    continue
                link_record = {}
                if target_val:
                    link_record["Target"] = target_val
                if text_val:
                    link_record["Text"] = text_val
                links_payload.append(link_record)
            if links_payload:
                scene_payload["Links"] = links_payload

            serialized.append(scene_payload)
        return serialized
    def save(self):
        if self.creation_mode and not self._has_required_name():
            messagebox.showerror(
                "Missing Name",
                "Please enter a name before saving this new item.",
            )
            return
        for field in self.template["fields"]:
            field_name = str(field.get("name", ""))
            field_type = str(field.get("type", "")).lower()

            if field_name in ["FogMaskPath", "Tokens", "token_size"]:
                continue
            if field_type == "links":
                if field_name not in self.item:
                    self.item[field_name] = []
                continue
            widget = self.field_widgets[field_name]
            if field_type == "list_longtext":
                if field_name == "Scenes":
                    self.item[field_name] = self._serialize_scene_states(widget)
                else:
                    self.item[field_name] = [
                        rte.get_text_data() if hasattr(rte, "get_text_data")
                                            else rte.text_widget.get("1.0", "end-1c")
                        for rte in widget
                    ]
            elif field_type == "longtext":
                # Read-only previews (e.g. ExtractedText) do not expose ``get_text_data``.
                # Keep their existing payload so the save routine doesn't crash and block
                # persistence of the other fields.
                if hasattr(widget, "get_text_data"):
                    data = widget.get_text_data()
                else:
                    data = self.item.get(field_name, "")
                if isinstance(data, dict) and not data.get("text", "").strip():
                    self.item[field_name] = ""
                else:
                    self.item[field_name] = data
            elif field_type == "list":
                values = []
                if isinstance(widget, list):
                    for entry in widget:
                        if hasattr(entry, "get"):
                            raw = entry.get()
                        else:
                            raw = entry
                        if raw:
                            values.append(raw)
                elif hasattr(widget, "get"):
                    raw = widget.get()
                    if raw:
                        values.append(raw)

                if field_name == "Tags":
                    tags = []
                    for value in values:
                        tags.extend(
                            [tag.strip() for tag in str(value).split(",") if tag.strip()]
                        )
                    self.item[field_name] = tags
                else:
                    self.item[field_name] = values
            elif field_type == "file":
                file_info = self._file_field_info.get(field_name, {})
                stored_path = file_info.get("path", "")
                self.item[field_name] = self._campaign_relative_path(stored_path)
            elif field_type == "audio" or field_name.lower() == "audio":
                value = widget.get() if hasattr(widget, "get") else str(widget)
                self.item[field_name] = self._campaign_relative_path(value)
            elif field_name == "Portrait":
                portrait_paths = getattr(self, "portrait_paths", [])
                normalized = [
                    self._campaign_relative_path(path)
                    for path in portrait_paths
                    if path
                ]
                self.item[field_name] = serialize_portrait_value(normalized)
            elif field_name == "Image":
                self.item[field_name] = self._campaign_relative_path(self.image_path)
            elif field_type == "boolean":
                # widget is stored as (option_menu, StringVar); convert to Boolean.
                self.item[field_name] = True if widget[1].get() == "True" else False
            else:
                self.item[field_name] = widget.get()

        # Re-apply hidden values that are not exposed in the editor UI.  Without
        # this the dictionary we hand to ``GenericModelWrapper`` is missing those
        # keys, so SQLite writes NULL into the columns and the fog-of-war mask is
        # lost the next time the map loads.
        for field_name, value in getattr(self, "_preserved_hidden_fields", {}).items():
            if field_name not in self.item:
                self.item[field_name] = value
            elif value not in (None, "") and self.item[field_name] in (None, ""):
                self.item[field_name] = value
        self._dirty = False
        if getattr(self, "toolbar", None):
            self.toolbar.set_dirty(False)
        self.saved = True
        self.destroy()
    def _has_required_name(self):
        key_field = None
        template_fields = None
        if isinstance(self.template, dict):
            template_fields = self.template.get("fields")
        if isinstance(template_fields, list) and template_fields:
            for field in template_fields:
                if not isinstance(field, dict):
                    continue
                field_name = field.get("name")
                if not field_name:
                    continue
                if field_name in {"Portrait", "Image", "Audio"}:
                    continue
                key_field = field_name
                break
        if not key_field:
            key_field = self.model_wrapper._infer_key_field()
        widget = self.field_widgets.get(key_field)
        if widget is None:
            return bool(str(self.item.get(key_field, "")).strip())
        if hasattr(widget, "get"):
            return bool(str(widget.get()).strip())
        return bool(str(self.item.get(key_field, "")).strip())
