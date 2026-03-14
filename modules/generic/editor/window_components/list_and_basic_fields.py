from modules.generic.editor.window_context import *
from modules.generic.editor.styles import EDITOR_PALETTE, option_menu_style, primary_button_style, toolbar_entry_style
from modules.generic.editor.window_components.dynamic_linked_entities import resolve_linked_entity_source
from modules.generic.editor.shared.campaign_status_field import (
    campaign_status_choices,
    canonical_campaign_status,
    is_campaign_status_field,
)


class GenericEditorWindowListAndBasicFields:
    def create_audio_field(self, field):
        frame = ctk.CTkFrame(self._field_parent(), fg_color="transparent")
        frame.pack(fill="x", pady=5)

        raw_value = self.item.get(field["name"], "") or ""
        normalized_value = self._campaign_relative_path(raw_value)
        audio_var = tk.StringVar(value=normalized_value)

        display_label = ctk.CTkLabel(
            frame,
            text=self._format_audio_label(audio_var.get()),
            anchor="w",
            text_color=EDITOR_PALETTE["muted_text"],
        )
        display_label.pack(fill="x", padx=5, pady=(5, 0))

        button_row = ctk.CTkFrame(frame, fg_color="transparent")
        button_row.pack(fill="x", pady=(5, 0))

        def update_value(new_value: str) -> None:
            audio_var.set(new_value)
            display_label.configure(text=self._format_audio_label(new_value))

        def on_select() -> None:
            file_path = filedialog.askopenfilename(
                title="Select Audio File",
                filetypes=[
                    (
                        "Audio Files",
                        "*.mp3 *.wav *.ogg *.oga *.flac *.aac *.m4a *.opus *.webm",
                    ),
                    ("All Files", "*.*"),
                ],
            )
            if not file_path:
                return
            try:
                relative = self.copy_audio_asset(file_path)
            except Exception as exc:
                messagebox.showerror("Select Audio", f"Could not copy audio file:\n{exc}")
                return
            update_value(relative)

        def on_clear() -> None:
            update_value("")

        def on_play() -> None:
            value = audio_var.get()
            if not value:
                messagebox.showinfo("Audio", "No audio file selected.")
                return
            name_hint = self.item.get("Name") or self.item.get("Title") or "Entity"
            if not play_entity_audio(value, entity_label=str(name_hint)):
                messagebox.showwarning("Audio", "Unable to play the selected audio file.")

        def on_stop() -> None:
            stop_entity_audio()

        ctk.CTkButton(button_row, text="Select Audio", **primary_button_style(), command=on_select).pack(side="left", padx=5)
        ctk.CTkButton(button_row, text="Clear", **primary_button_style(), command=on_clear).pack(side="left", padx=5)
        ctk.CTkButton(button_row, text="Play", **primary_button_style(), command=on_play).pack(side="left", padx=5)
        ctk.CTkButton(button_row, text="Stop", **primary_button_style(), command=on_stop).pack(side="left", padx=5)

        self.field_widgets[field["name"]] = audio_var
    def create_file_field(self, field):
        frame = ctk.CTkFrame(self._field_parent(), fg_color="transparent")
        frame.pack(fill="x", pady=5)

        field_name = field.get("name")
        storage_subdir = (field.get("storage_subdir") or "").strip()

        raw_value = self.item.get(field_name, "") or ""
        normalized = self._campaign_relative_path(raw_value)
        if normalized and not normalized.startswith(".."):
            label_text = os.path.basename(normalized)
            abs_candidate = Path(ConfigHelper.get_campaign_dir()) / Path(normalized)
            if not abs_candidate.exists():
                label_text = f"{label_text} (missing)"
        elif raw_value:
            label_text = os.path.basename(str(raw_value))
        else:
            label_text = "[No Attachment]"

        label_widget = ctk.CTkLabel(frame, text=label_text, text_color=EDITOR_PALETTE["muted_text"])
        label_widget.pack(side="left", padx=5)

        ctk.CTkButton(
            frame,
            text="Browse Attachment",
            command=lambda: self.select_attachment(field_name, label_widget, storage_subdir),
            **primary_button_style(),
        ).pack(side="left", padx=5)

        self._file_field_info[field_name] = {
            "path": normalized,
            "label": label_widget,
            "storage_subdir": storage_subdir,
        }

        # placeholder so save() sees the key
        self.field_widgets[field_name] = label_widget
    def select_attachment(self, field_name, label_widget, storage_subdir):
        file_path = filedialog.askopenfilename(
            title="Select Attachment",
            filetypes=[("All Files", "*.*")]
        )
        if not file_path:
            return

        # ensure upload folder
        campaign_dir = ConfigHelper.get_campaign_dir()
        subdir = storage_subdir or "uploads"
        upload_folder = os.path.join(campaign_dir, "assets", subdir)
        os.makedirs(upload_folder, exist_ok=True)

        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        dest = os.path.join(upload_folder, filename)
        counter = 1
        while os.path.exists(dest):
            filename = f"{name}_{counter}{ext}"
            dest = os.path.join(upload_folder, filename)
            counter += 1
        try:
            shutil.copy2(file_path, dest)
            rel_path = os.path.relpath(dest, campaign_dir).replace("\\", "/")
            info = self._file_field_info.setdefault(field_name, {})
            info["path"] = rel_path
            info["storage_subdir"] = storage_subdir
            label_widget.configure(text=os.path.basename(filename))
        except Exception as e:
            messagebox.showerror("Error", f"Could not copy file:\n{e}")
    def create_boolean_field(self, field):
        # Define the two possible dropdown options.
        options = ["True", "False"]
        # Retrieve the stored value (default to "False" if not found).
        stored_value = self.item.get(field["name"], "False")
        # Convert stored_value to a string "True" or "False":
        if isinstance(stored_value, bool):
            initial_value = "True" if stored_value else "False"
        else:
            initial_value = "True" if (str(stored_value).lower() == "true" or stored_value ==1) else "False"
        # Create a StringVar with the initial value.
        var = ctk.StringVar(value=initial_value)
        # Create the OptionMenu (dropdown) using customtkinter.
        option_menu = ctk.CTkOptionMenu(self._field_parent(), variable=var, values=options, **option_menu_style())
        option_menu.pack(fill="x", pady=5)
        # Save the widget and its StringVar for later retrieval.
        self.field_widgets[field["name"]] = (option_menu, var)
    def create_dynamic_combobox_list(self, field):
        container = ctk.CTkFrame(self._field_parent(), fg_color="transparent")
        container.pack(fill="x", pady=5)

        combobox_list = []
        combobox_vars = []
        options_list, label_text = resolve_linked_entity_source(field)

        initial_values = self.item.get(field["name"]) or []
        if isinstance(initial_values, str):
            initial_values = [val.strip() for val in initial_values.split(",") if val.strip()]

        def remove_this(row, entry_widget):
            row.destroy()
            try:
                idx = combobox_list.index(entry_widget)
                combobox_list.pop(idx)
                if idx < len(combobox_vars):
                    combobox_vars.pop(idx)
            except ValueError:
                pass

        def open_dropdown(widget, var):
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height()
            dropdown = CustomDropdown(
                widget.winfo_toplevel(),
                options=options_list,
                command=lambda v: var.set(v),
                width=widget.winfo_width(),
                max_height=200
            )
            dropdown.geometry(f"{widget.winfo_width()}x{dropdown.winfo_reqheight()}+{x}+{y}")
            dropdown.lift()
            dropdown.grab_set()

            # move keyboard focus into the search box immediately
            dropdown.entry.focus_set()

        def add_combobox(initial_value=None):
            row = ctk.CTkFrame(container, fg_color="transparent")
            row.pack(fill="x", pady=2)

            var = ctk.StringVar()
            state = "normal" if not options_list else "readonly"
            entry = ctk.CTkEntry(row, textvariable=var, state=state, **toolbar_entry_style())
            entry.pack(side="left", expand=True, fill="x")

            if options_list:
                entry.bind("<Button-1>",  lambda e, w=entry, v=var: open_dropdown(w, v))

            if initial_value:
                var.set(initial_value)
            elif options_list:
                var.set(options_list[0])

            if options_list:
                btn = ctk.CTkButton(row, text="▼", width=30, command=lambda: open_dropdown(entry, var), **primary_button_style())
                btn.pack(side="left", padx=5)

            remove_btn = ctk.CTkButton(row, text="−", width=30, command=lambda: remove_this(row, entry), **primary_button_style())
            remove_btn.pack(side="left", padx=5)

            combobox_list.append(entry)
            combobox_vars.append(var)

        for value in initial_values:
            add_combobox(value)

        add_button = ctk.CTkButton(container, text=label_text, command=add_combobox, **primary_button_style())
        add_button.pack(anchor="w", pady=2)

        # Save widgets clearly
        self.field_widgets[field["name"]] = combobox_list
        self.field_widgets[f"{field['name']}_vars"] = combobox_vars
        self.field_widgets[f"{field['name']}_container"] = container
        self.field_widgets[f"{field['name']}_add_combobox"] = add_combobox
    def create_text_entry(self, field):
        value = self.item.get(field["name"], "")
        field_name = str(field.get("name", ""))
        field_type = str(field.get("type", "")).strip().lower()
        entity_type = str(getattr(self.model_wrapper, "entity_type", "") or "")

        if is_campaign_status_field(entity_type=entity_type, field_name=field_name):
            canonical_status = canonical_campaign_status(value)
            status_var = ctk.StringVar(value=canonical_status)
            option_menu = ctk.CTkOptionMenu(
                self._field_parent(),
                variable=status_var,
                values=campaign_status_choices(),
                **option_menu_style(),
            )
            option_menu.pack(fill="x", pady=5)
            self.field_widgets[field["name"]] = option_menu
            return

        is_date_field = field_type == "date" or field_name.lower().endswith("date")

        if is_date_field:
            widget = EventDatePickerField(self._field_parent(), initial_value=value)
            widget.pack(fill="x", pady=5)
            self.field_widgets[field["name"]] = widget
            return

        if getattr(self.model_wrapper, "entity_type", "") == "events":
            if field_name == "Date":
                widget = EventDatePickerField(self._field_parent(), initial_value=value)
                widget.pack(fill="x", pady=5)
                self.field_widgets[field["name"]] = widget
                return
            if field_name in {"StartTime", "EndTime"}:
                widget = EventTimePickerField(self._field_parent(), initial_value=value)
                widget.pack(fill="x", pady=5)
                self.field_widgets[field["name"]] = widget
                return

        entry = ctk.CTkEntry(self._field_parent(), **toolbar_entry_style())
        if value:
            entry.insert(0, self.item.get(field["name"], ""))
        entry.pack(fill="x", pady=5)
        self.field_widgets[field["name"]] = entry
    def on_combo_mousewheel(self, event, combobox):
        # Get the current selection and available options.
        options = combobox.cget("values")
        if not options:
            return
        current_val = combobox.get()
        try:
            idx = options.index(current_val)
        except ValueError:
            idx = 0

        # Determine scroll direction.
        if event.num == 4 or event.delta > 0:
            # Scroll up: go to previous option.
            new_idx = max(0, idx - 1)
        elif event.num == 5 or event.delta < 0:
            # Scroll down: go to next option.
            new_idx = min(len(options) - 1, idx + 1)
        else:
            new_idx = idx

        combobox.set(options[new_idx])
