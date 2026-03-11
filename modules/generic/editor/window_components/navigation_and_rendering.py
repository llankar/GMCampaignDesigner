from modules.generic.editor.window_context import *


class GenericEditorWindowNavigationAndRendering:
    def _mark_dirty(self, event=None):
        if self._dirty:
            return
        if event is not None and getattr(event, "keysym", "") in {"Control_L", "Control_R", "Shift_L", "Shift_R", "Escape"}:
            return
        self._dirty = True
        if getattr(self, "toolbar", None):
            self.toolbar.set_dirty(True)
    def _register_field_section(self, field_name: str):
        section = ctk.CTkFrame(self.scroll_frame)
        section.pack(fill="x", pady=2)
        self._field_sections[field_name] = section
        self._field_section_order.append(field_name)
        return section
    def _filter_visible_fields(self, query: str):
        query = (query or "").strip().lower()
        total = len(self._field_section_order)
        visible = 0
        for field_name in self._field_section_order:
            section = self._field_sections.get(field_name)
            if section is None:
                continue
            should_show = (not query) or (query in field_name.lower())
            if should_show:
                if not section.winfo_manager():
                    section.pack(fill="x", pady=2)
                visible += 1
            elif section.winfo_manager():
                section.pack_forget()
        self.toolbar.update_visible_count(visible, total)
    def _jump_to_field(self, field_name: str):
        section = self._field_sections.get(field_name)
        if section is None:
            return
        section.focus_set()
        self.after(10, lambda: self._scroll_to_widget(section))
    def _scroll_to_widget(self, widget):
        canvas = getattr(self.scroll_frame, "_parent_canvas", None)
        if canvas is None:
            return
        try:
            y = max(widget.winfo_y() - 10, 0)
            height = max(self.scroll_frame.winfo_height(), 1)
            canvas.yview_moveto(y / max(height * 3, 1))
        except Exception:
            return
    def _get_ai(self):
        if self._ai_client is None:
            self._ai_client = LocalAIClient()
        return self._ai_client
    def _field_parent(self):
        return getattr(self, "_active_field_parent", None) or self.scroll_frame
    def _render_standard_field(self, field):
        field_name = str(field.get("name", ""))
        field_type = str(field.get("type", "")).lower()

        if field_name in {"FogMaskPath", "Tokens", "token_size"}:
            return
        field_container = self._register_field_section(field_name)
        self._active_field_parent = field_container

        ctk.CTkLabel(field_container, text=field_name).pack(pady=(5, 0), anchor="w")

        if field_name == "Portrait":
            self.create_portrait_field(field)
        elif field_name == "Image":
            self.create_image_field(field)
        elif field_type == "links":
            self.create_character_links_field(field)
        elif field_type == "list_longtext":
            self.create_dynamic_longtext_list(field)
        elif field_type == "longtext":
            self.create_longtext_field(field)
        elif field_name in ["NPCs", "Places", "Factions", "Objects", "Creatures", "PCs", "Villains", "Events"] or \
             (field_type == "list" and field.get("linked_type")):
            self.create_dynamic_combobox_list(field)
        elif field_type == "boolean":
            self.create_boolean_field(field)
        elif field_type == "audio" or field_name.lower() == "audio":
            self.create_audio_field(field)
        elif field_type == "file":
            self.create_file_field(field)
        else:
            self.create_text_entry(field)
        self._active_field_parent = None
    def _make_richtext_editor(self, parent, initial_text, hide_toolbar=True, max_lines=None):
        """
        Shared initialization for any RichTextEditor-based field.
        Returns the editor instance.
        """
        line_limit = 100 if max_lines is None else max_lines
        editor = RichTextEditor(parent, max_lines=line_limit)
        editor.text_widget.configure(
            bg="#2B2B2B", fg="white", insertbackground="white"
        )
        # Load data (dict or raw string)

        data = initial_text
        if isinstance(data, str):
            parsed_data = None
            try:
                parsed_data = json.loads(data)
            except Exception:
                try:
                    parsed_data = ast.literal_eval(data)
                except Exception:
                    parsed_data = None

            if isinstance(parsed_data, dict):
                data = parsed_data
            else:
                data = {"text": data}
        elif not isinstance(data, dict):
            data = {"text": str(initial_text or "")}

        editor.load_text_data(data)
        # Toolbar toggle
        if hide_toolbar:
            editor.toolbar.pack_forget()
            editor.text_widget.bind(
                "<FocusIn>",
                lambda e: editor.toolbar.pack(fill="x", before=editor.text_widget, pady=2)
            )
            editor.text_widget.bind(
                "<FocusOut>",
                lambda e: editor.toolbar.pack_forget()
            )
        editor.pack(fill="x", pady=5)
        return editor
    def create_longtext_field(self, field):
        raw = self.item.get(field["name"], "")
        if field["name"] == "ExtractedText":
            preview = ReadOnlyLongTextPreview(
                self._field_parent(),
                field.get("label") or field["name"],
                raw,
            )
            preview.pack(fill="x", pady=5)
            self.field_widgets[field["name"]] = preview
            return
        editor = self._make_richtext_editor(self._field_parent(), raw)
        self.field_widgets[field["name"]] = editor

        # Place action buttons for this field on one row
        btn_row = ctk.CTkFrame(self._field_parent())
        btn_row.pack(fill="x", pady=5)

        # extra buttons for Summary/Secrets…
        if field["name"] == "Summary":
            ctk.CTkButton(
                btn_row, text="Random Summary",
                command=self.generate_scenario_description
            ).pack(side="left", padx=5, pady=5)
            ctk.CTkButton(
                btn_row, text="AI Draft Summary",
                command=lambda fn=field["name"]: self.ai_draft_field(fn)
            ).pack(side="left", padx=5, pady=5)
        if field["name"] == "Secrets":
            ctk.CTkButton(
                btn_row, text="Generate Secret",
                command=self.generate_secret_text
            ).pack(side="left", padx=5, pady=5)
            ctk.CTkButton(
                btn_row, text="AI Draft Secret",
                command=lambda fn=field["name"]: self.ai_draft_field(fn)
            ).pack(side="left", padx=5, pady=5)

        entity_slug = getattr(self.model_wrapper, "entity_type", "") if self.model_wrapper else ""

        # Add AI draft for NPC/Creature/Villain Description
        if (
            field["name"] == "Description"
            and entity_slug in ("npcs", "creatures", "villains")
        ):
            ctk.CTkButton(
                btn_row, text="AI Draft Description",
                command=lambda fn=field["name"]: self.ai_draft_field(fn)
            ).pack(side="left", padx=5, pady=5)
        if field["name"] == "Scheme" and entity_slug == "villains":
            ctk.CTkButton(
                btn_row, text="AI Draft Scheme",
                command=lambda fn=field["name"]: self.ai_draft_field(fn)
            ).pack(side="left", padx=5, pady=5)
        if field["name"] == "LieutenantNetwork" and entity_slug == "villains":
            ctk.CTkButton(
                btn_row, text="AI Draft Network",
                command=lambda fn=field["name"]: self.ai_draft_field(fn)
            ).pack(side="left", padx=5, pady=5)

        # Generic AI improvement button for any long text field
        ctk.CTkButton(
            btn_row, text=f"AI Improve {field['name']}",
            command=lambda fn=field["name"]: self.ai_improve_field(fn)
        ).pack(side="left", padx=5, pady=5)

        markup_supported_fields = {"Traits", "Stats"}
