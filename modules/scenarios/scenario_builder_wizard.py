import copy
import json
import sqlite3
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from modules.generic.generic_editor_window import GenericEditorWindow
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_module_import, log_info, log_exception
from modules.helpers.template_loader import load_template


log_module_import(__name__)


class WizardStep(ctk.CTkFrame):
    """Base class for wizard steps with state synchronization hooks."""

    def load_state(self, state):  # pragma: no cover - UI synchronization
        """Populate widgets using the shared wizard ``state``."""

    def save_state(self, state):  # pragma: no cover - UI synchronization
        """Persist widget values into the shared wizard ``state``."""
        return True


class BasicInfoStep(WizardStep):
    def __init__(self, master):
        super().__init__(master)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        form = ctk.CTkFrame(self)
        form.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20, 10))

        ctk.CTkLabel(form, text="Scenario Title", anchor="w").pack(fill="x", pady=(0, 4))
        self.title_var = ctk.StringVar()
        self.title_entry = ctk.CTkEntry(form, textvariable=self.title_var)
        self.title_entry.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(form, text="Summary", anchor="w").pack(fill="x", pady=(0, 4))
        self.summary_text = ctk.CTkTextbox(form, height=160)
        self.summary_text.pack(fill="both", expand=True, pady=(0, 12))

        ctk.CTkLabel(form, text="Secrets", anchor="w").pack(fill="x", pady=(0, 4))
        self.secret_text = ctk.CTkTextbox(form, height=120)
        self.secret_text.pack(fill="both", expand=True, pady=(0, 12))

    def load_state(self, state):  # pragma: no cover - UI synchronization
        self.title_var.set(state.get("Title", ""))
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", state.get("Summary", ""))
        secret_val = state.get("Secrets") or state.get("Secret") or ""
        self.secret_text.delete("1.0", "end")
        self.secret_text.insert("1.0", secret_val)

    def save_state(self, state):  # pragma: no cover - UI synchronization
        state["Title"] = self.title_var.get().strip()
        state["Summary"] = self.summary_text.get("1.0", "end").strip()
        secrets = self.secret_text.get("1.0", "end").strip()
        state["Secrets"] = secrets
        state["Secret"] = secrets  # ScenarioGraphEditor expects the singular key
        if "Scenes" not in state or state["Scenes"] is None:
            state["Scenes"] = []
        return True


class ScenesPlanningStep(WizardStep):
    """Editable scene list tailored for the scenario builder wizard."""

    ENTITY_FIELDS = {
        "NPCs": ("npcs", "Key NPCs", "NPC"),
        "Creatures": ("creatures", "Creatures / Foes", "Creature"),
        "Places": ("places", "Locations / Places", "Place"),
    }

    def __init__(self, master, entity_wrappers):
        super().__init__(master)
        self.scenes = []
        self.selected_index = None
        self._suppress_list_event = False
        self._updating_fields = False
        self.entity_wrappers = entity_wrappers
        self.entity_listboxes = {}
        self.entity_buttons = []

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        container.grid_columnconfigure(0, weight=0, minsize=280)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(0, weight=1)

        # Scene list ---------------------------------------------------
        list_frame = ctk.CTkFrame(container)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        list_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            list_frame,
            text="Scenes",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 4))

        self.scene_listbox = tk.Listbox(list_frame, activestyle="none", exportselection=False)
        self.scene_listbox.grid(row=1, column=0, sticky="nsew", padx=(6, 0), pady=(0, 6))
        self.scene_listbox.bind("<<ListboxSelect>>", self._on_scene_selected)

        list_scroll = tk.Scrollbar(list_frame, orient="vertical", command=self.scene_listbox.yview)
        list_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 6), padx=(0, 6))
        self.scene_listbox.configure(yscrollcommand=list_scroll.set)

        actions_top = ctk.CTkFrame(list_frame)
        actions_top.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        actions_top.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions_top, text="Add Scene", command=self.add_scene).grid(row=0, column=0, padx=4, pady=2, sticky="ew")
        ctk.CTkButton(actions_top, text="Duplicate", command=self.duplicate_scene).grid(row=0, column=1, padx=4, pady=2, sticky="ew")

        actions_middle = ctk.CTkFrame(list_frame)
        actions_middle.grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        actions_middle.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions_middle, text="Remove", command=self.remove_scene).grid(row=0, column=0, padx=4, pady=2, sticky="ew")
        ctk.CTkButton(actions_middle, text="Move Up", command=lambda: self.move_scene(-1)).grid(row=0, column=1, padx=4, pady=2, sticky="ew")

        actions_bottom = ctk.CTkFrame(list_frame)
        actions_bottom.grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 8))
        actions_bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(actions_bottom, text="Move Down", command=lambda: self.move_scene(1)).grid(row=0, column=0, padx=4, pady=2, sticky="ew")

        # Scene editor -------------------------------------------------
        editor = ctk.CTkScrollableFrame(container)
        editor.grid(row=0, column=1, sticky="nsew")
        editor.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            editor,
            text="Scene Details",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(8, 4))

        ctk.CTkLabel(editor, text="Title", anchor="w").grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 2))
        self.title_var = ctk.StringVar()
        self.title_entry = ctk.CTkEntry(editor, textvariable=self.title_var)
        self.title_entry.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 10))
        self.title_var.trace_add("write", self._on_title_change)

        ctk.CTkLabel(editor, text="Scene Type", anchor="w").grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 2))
        self.type_options = [
            "Auto-detect",
            "Setup",
            "Choice",
            "Investigation",
            "Combat",
            "Outcome",
            "Social",
            "Travel",
            "Downtime",
        ]
        self.type_var = ctk.StringVar(value=self.type_options[0])
        self.type_menu = ctk.CTkOptionMenu(editor, values=self.type_options, variable=self.type_var, command=self._on_type_change)
        self.type_menu.grid(row=4, column=0, sticky="w", padx=6, pady=(0, 12))

        ctk.CTkLabel(editor, text="Summary", anchor="w").grid(row=5, column=0, sticky="ew", padx=6, pady=(0, 2))
        self.summary_text = ctk.CTkTextbox(editor, height=220)
        self.summary_text.grid(row=6, column=0, sticky="nsew", padx=6, pady=(0, 12))

        hint_font = ctk.CTkFont(size=12)

        current_row = 7
        for field, (entity_type, label_text, singular) in self.ENTITY_FIELDS.items():
            ctk.CTkLabel(editor, text=label_text, anchor="w", font=hint_font).grid(
                row=current_row, column=0, sticky="ew", padx=6, pady=(0, 2)
            )
            current_row += 1

            list_frame = ctk.CTkFrame(editor)
            list_frame.grid(row=current_row, column=0, sticky="nsew", padx=6, pady=(0, 6))
            list_frame.grid_rowconfigure(0, weight=1)
            list_frame.grid_columnconfigure(0, weight=1)

            listbox = tk.Listbox(list_frame, activestyle="none", exportselection=False, height=6)
            listbox.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=(6, 6))
            scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
            scrollbar.grid(row=0, column=1, sticky="ns", pady=(6, 6), padx=(0, 6))
            listbox.configure(yscrollcommand=scrollbar.set)
            self.entity_listboxes[field] = listbox

            current_row += 1

            btn_row = ctk.CTkFrame(editor)
            btn_row.grid(row=current_row, column=0, sticky="ew", padx=6, pady=(0, 12))
            btn_row.grid_columnconfigure((0, 1, 2), weight=1)

            add_btn = ctk.CTkButton(
                btn_row,
                text="Add",
                command=lambda f=field, et=entity_type, singular=singular: self.open_entity_selector(f, et, singular),
            )
            add_btn.grid(row=0, column=0, padx=4, pady=2, sticky="ew")
            remove_btn = ctk.CTkButton(
                btn_row,
                text="Remove",
                command=lambda f=field: self.remove_selected_entity(f),
            )
            remove_btn.grid(row=0, column=1, padx=4, pady=2, sticky="ew")
            new_btn = ctk.CTkButton(
                btn_row,
                text=f"New {singular}",
                command=lambda et=entity_type, f=field, lbl=singular: self.create_new_entity(et, f, lbl),
            )
            new_btn.grid(row=0, column=2, padx=4, pady=2, sticky="ew")
            self.entity_buttons.extend([add_btn, remove_btn, new_btn])

            current_row += 1

        ctk.CTkLabel(editor, text="Next Scenes (names or numbers)", anchor="w", font=hint_font).grid(
            row=current_row, column=0, sticky="ew", padx=6, pady=(0, 2)
        )
        current_row += 1
        self.next_text = ctk.CTkTextbox(editor, height=80)
        self.next_text.grid(row=current_row, column=0, sticky="ew", padx=6, pady=(0, 20))

        self._set_editor_enabled(False)

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _set_editor_enabled(self, enabled):  # pragma: no cover - UI state toggling
        state = "normal" if enabled else "disabled"
        self.title_entry.configure(state=state)
        try:
            self.type_menu.configure(state=state)
        except Exception:  # pragma: no cover - widget state differences
            pass
        for widget in (self.summary_text, self.next_text):
            widget.configure(state="normal")
            if not enabled:
                widget.configure(state="disabled")
        for listbox in self.entity_listboxes.values():
            try:
                listbox.configure(state=tk.NORMAL if enabled else tk.DISABLED)
            except Exception:  # pragma: no cover - widget differences
                pass
        for button in self.entity_buttons:
            try:
                button.configure(state="normal" if enabled else "disabled")
            except Exception:  # pragma: no cover - widget differences
                pass

    def _set_textbox_value(self, widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if value:
            widget.insert("1.0", value)

    def _set_listbox_items(self, field, values):
        listbox = self.entity_listboxes.get(field)
        if not listbox:
            return
        items = self._dedupe(values)
        listbox.delete(0, tk.END)
        for value in items:
            listbox.insert(tk.END, value)

    def _get_listbox_items(self, field):
        listbox = self.entity_listboxes.get(field)
        if not listbox:
            return []
        return [listbox.get(idx) for idx in range(listbox.size())]

    def open_entity_selector(self, field, entity_type, singular_label):  # pragma: no cover - UI interaction
        wrapper = self.entity_wrappers.get(entity_type)
        if not wrapper:
            messagebox.showerror("Unavailable", f"No {singular_label} data available for selection.")
            return
        template = load_template(entity_type)
        top = ctk.CTkToplevel(self)
        top.title(f"Select {singular_label}")
        top.geometry("1100x720")
        top.minsize(1100, 720)
        selection = GenericListSelectionView(
            top,
            entity_type,
            wrapper,
            template,
            on_select_callback=lambda et, name, f=field, win=top: self._on_entity_selected(f, name, win),
        )
        selection.pack(fill="both", expand=True)
        top.transient(self.winfo_toplevel())
        top.grab_set()

    def _on_entity_selected(self, field, name, window):  # pragma: no cover - UI callback
        if not name:
            return
        existing = self._get_listbox_items(field)
        if name not in existing:
            existing.append(name)
            self._set_listbox_items(field, existing)
            self._update_scene_field_from_listbox(field)
        try:
            window.destroy()
        except Exception:  # pragma: no cover - best effort cleanup
            pass

    def remove_selected_entity(self, field):  # pragma: no cover - UI interaction
        listbox = self.entity_listboxes.get(field)
        if not listbox:
            return
        selection = listbox.curselection()
        for index in reversed(selection):
            listbox.delete(index)
        self._update_scene_field_from_listbox(field)

    def create_new_entity(self, entity_type, field, label):  # pragma: no cover - UI interaction
        wrapper = self.entity_wrappers.get(entity_type)
        if not wrapper:
            messagebox.showerror("Unavailable", f"No {label} data source is available.")
            return

        try:
            template = load_template(entity_type)
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(f"Failed to load template for {entity_type}: {exc}")
            messagebox.showerror("Template Error", f"Unable to load the {label} template.")
            return

        try:
            items = wrapper.load_items()
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(f"Failed to load existing {entity_type}: {exc}")
            messagebox.showerror("Database Error", f"Unable to load existing {label}s.")
            return

        new_item = {}
        editor = GenericEditorWindow(
            self.winfo_toplevel(),
            new_item,
            template,
            wrapper,
            creation_mode=True,
        )
        self.wait_window(editor)

        if not getattr(editor, "saved", False):
            return

        preferred_keys = ("Name", "Title")
        unique_key = next((key for key in preferred_keys if new_item.get(key)), None)
        unique_value = new_item.get(unique_key, "") if unique_key else ""
        if unique_key:
            replaced = False
            for idx, existing in enumerate(items):
                if existing.get(unique_key) == new_item.get(unique_key):
                    items[idx] = new_item
                    replaced = True
                    break
            if not replaced:
                items.append(new_item)
        else:
            items.append(new_item)

        try:
            wrapper.save_items(items)
            wrapper.load_items()
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(f"Failed to persist new {entity_type}: {exc}")
            messagebox.showerror("Save Error", f"Unable to save the new {label}.")
            return

        if not unique_value:
            messagebox.showwarning(
                "Missing Name",
                f"The new {label.lower()} was saved without a name and cannot be linked automatically.",
            )
            return

        existing = self._get_listbox_items(field)
        if unique_value not in existing:
            existing.append(unique_value)
            self._set_listbox_items(field, existing)
            self._update_scene_field_from_listbox(field)

    def _update_scene_field_from_listbox(self, field):  # pragma: no cover - UI helper
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        self.scenes[self.selected_index][field] = self._get_listbox_items(field)

    def _on_scene_selected(self, _event=None):  # pragma: no cover - UI callback
        if self._suppress_list_event:
            return
        selection = self.scene_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index == self.selected_index:
            return
        self._save_current_scene()
        self._apply_selection(index)

    def _apply_selection(self, index):
        if index is None or index < 0 or index >= len(self.scenes):
            self.selected_index = None
            self._updating_fields = True
            self._set_editor_enabled(True)
            self.title_var.set("")
            self._set_textbox_value(self.summary_text, "")
            for field in self.ENTITY_FIELDS:
                self._set_listbox_items(field, [])
            self._set_textbox_value(self.next_text, "")
            self.type_var.set(self.type_options[0])
            self._updating_fields = False
            self._set_editor_enabled(False)
            return

        self.selected_index = index
        scene = self.scenes[index]
        self._updating_fields = True
        self._set_editor_enabled(True)
        self.title_var.set(scene.get("Title", ""))
        type_label = self._normalise_type_label(
            scene.get("SceneType")
            or scene.get("Type")
            or scene.get("Category")
            or scene.get("Mood")
            or scene.get("Role")
        )
        self.type_var.set(type_label or self.type_options[0])
        summary = scene.get("Summary") or scene.get("Text") or ""
        self._set_textbox_value(self.summary_text, summary)
        for field in self.ENTITY_FIELDS:
            self._set_listbox_items(field, scene.get(field, []))
        self._set_textbox_value(self.next_text, "\n".join(scene.get("NextScenes", [])))
        self._updating_fields = False

    def _set_listbox_selection(self, index):
        self._suppress_list_event = True
        self.scene_listbox.selection_clear(0, tk.END)
        if index is not None and 0 <= index < len(self.scenes):
            self.scene_listbox.selection_set(index)
            self.scene_listbox.activate(index)
            self.scene_listbox.see(index)
        self._suppress_list_event = False

    def _format_scene_label(self, scene, index):
        title = scene.get("Title") or f"Scene {index + 1}"
        title = title.strip() or f"Scene {index + 1}"
        if len(title) > 48:
            title = title[:45].rstrip() + "..."
        type_label = scene.get("SceneType") or ""
        if type_label:
            return f"{index + 1}. {title} [{type_label}]"
        return f"{index + 1}. {title}"

    def _refresh_scene_list(self):
        current = self.selected_index
        self._suppress_list_event = True
        self.scene_listbox.delete(0, tk.END)
        for idx, scene in enumerate(self.scenes):
            self.scene_listbox.insert(tk.END, self._format_scene_label(scene, idx))
        self._suppress_list_event = False
        if current is not None and 0 <= current < len(self.scenes):
            self._set_listbox_selection(current)
            self._apply_selection(current)
        elif self.scenes:
            self._set_listbox_selection(0)
            self._apply_selection(0)
        else:
            self._apply_selection(None)

    def _on_title_change(self, *_):  # pragma: no cover - simple binding
        if self._updating_fields or self.selected_index is None:
            return
        title = self.title_var.get()
        self.scenes[self.selected_index]["Title"] = title
        self._update_list_item(self.selected_index)

    def _on_type_change(self, _value):  # pragma: no cover - simple binding
        if self._updating_fields or self.selected_index is None:
            return
        selection = self.type_var.get()
        label = "" if selection == self.type_options[0] else selection
        self.scenes[self.selected_index]["SceneType"] = label
        if label:
            self.scenes[self.selected_index]["Type"] = label
        else:
            self.scenes[self.selected_index].pop("Type", None)
        self._update_list_item(self.selected_index)

    def _update_list_item(self, index):
        if index is None or index < 0 or index >= len(self.scenes):
            return
        self._suppress_list_event = True
        self.scene_listbox.delete(index)
        self.scene_listbox.insert(index, self._format_scene_label(self.scenes[index], index))
        self._set_listbox_selection(index)
        self._suppress_list_event = False

    # ------------------------------------------------------------------
    # Scene data helpers
    # ------------------------------------------------------------------
    def _create_scene_record(self, default_title):
        return {
            "Title": default_title,
            "SceneType": "",
            "Summary": "",
            "Text": "",
            "NPCs": [],
            "Creatures": [],
            "Places": [],
            "NextScenes": [],
        }

    def _split_to_list(self, value):
        if not value:
            return []
        if isinstance(value, str):
            tokens = []
            for segment in value.replace(";", "\n").replace(",", "\n").splitlines():
                cleaned = segment.strip()
                if cleaned:
                    tokens.append(cleaned)
            return tokens
        if isinstance(value, (list, tuple, set)):
            results = []
            for item in value:
                results.extend(self._split_to_list(item))
            return results
        if isinstance(value, dict):
            results = []
            for key in ("Name", "Title", "Label", "text", "Text"):
                if key in value:
                    results.extend(self._split_to_list(value[key]))
            if not results:
                for item in value.values():
                    results.extend(self._split_to_list(item))
            return results
        value_str = str(value).strip()
        return [value_str] if value_str else []

    def _dedupe(self, items):
        seen = set()
        result = []
        for item in items:
            cleaned = str(item).strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result

    def _extract_links(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            results = []
            for item in value:
                results.extend(self._extract_links(item))
            return results
        if isinstance(value, dict):
            for key in ("target", "Target", "Scene", "scene", "Next", "next", "To", "to", "Id", "ID", "Name", "name", "Title", "title", "Label", "label"):
                if key in value:
                    return self._extract_links(value.get(key))
            results = []
            for item in value.values():
                results.extend(self._extract_links(item))
            return results
        if isinstance(value, (int, float)):
            return [str(int(value))]
        text = str(value).strip()
        return [text] if text else []

    def _extract_text(self, entry):
        if not isinstance(entry, dict):
            return str(entry) if entry is not None else ""
        fragments = []
        for key in ("Text", "text", "Summary", "Description", "Body", "Details", "Notes", "Content"):
            value = entry.get(key)
            if isinstance(value, str):
                fragments.append(value)
            elif isinstance(value, (list, tuple)):
                fragments.extend(str(item) for item in value if item)
            elif isinstance(value, dict):
                fragments.extend(str(item) for item in value.values() if isinstance(item, str))
        if not fragments and isinstance(entry.get("text"), dict):
            inner = entry.get("text")
            fragments.extend(str(item) for item in inner.values() if isinstance(item, str))
        return "\n\n".join(fragment.strip() for fragment in fragments if str(fragment).strip())

    def _normalise_type_label(self, value):
        if not value:
            return self.type_options[0]
        lowered = str(value).strip().lower()
        if not lowered:
            return self.type_options[0]
        for option in self.type_options[1:]:
            if option.lower() == lowered:
                return option
        if "combat" in lowered or "fight" in lowered or "battle" in lowered:
            return "Combat"
        if "social" in lowered or "parley" in lowered or "diplom" in lowered:
            return "Social"
        if "invest" in lowered or "myster" in lowered or "clue" in lowered:
            return "Investigation"
        if "travel" in lowered or "journey" in lowered or "chase" in lowered:
            return "Travel"
        if "downtime" in lowered or "rest" in lowered or "interlude" in lowered:
            return "Downtime"
        if "setup" in lowered or "hook" in lowered or "opening" in lowered:
            return "Setup"
        if "choice" in lowered or "branch" in lowered or "decision" in lowered:
            return "Choice"
        if "outcome" in lowered or "resolution" in lowered or "result" in lowered:
            return "Outcome"
        display = value if isinstance(value, str) else str(value)
        display = display.strip() or self.type_options[0]
        title_display = display.title()
        if title_display not in self.type_options:
            self.type_options.append(title_display)
            try:
                self.type_menu.configure(values=self.type_options)
            except Exception:  # pragma: no cover - widget differences
                pass
        return title_display

    def _normalise_scene_entry(self, entry, index):
        scene = self._create_scene_record(f"Scene {index + 1}")
        if isinstance(entry, dict):
            title = ""
            for key in ("Title", "Scene", "Name", "Heading", "Label"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    title = value.strip()
                    break
            if title:
                scene["Title"] = title

            summary = self._extract_text(entry)
            if summary:
                scene["Summary"] = summary.strip()
                scene["Text"] = scene["Summary"]

            type_label = self._normalise_type_label(
                entry.get("SceneType")
                or entry.get("Type")
                or entry.get("Category")
                or entry.get("Mood")
                or entry.get("Role")
            )
            scene["SceneType"] = "" if type_label == self.type_options[0] else type_label
            if scene["SceneType"]:
                scene["Type"] = scene["SceneType"]

            npc_names = []
            for key in ("NPCs", "InvolvedNPCs", "Participants", "Characters", "Allies"):
                npc_names.extend(self._split_to_list(entry.get(key)))
            creature_names = []
            for key in ("Creatures", "Monsters", "Enemies", "Foes", "Threats"):
                creature_names.extend(self._split_to_list(entry.get(key)))
            place_names = []
            for key in ("Places", "Locations", "Site", "Setting", "Where", "Venue"):
                place_names.extend(self._split_to_list(entry.get(key)))

            scene["NPCs"] = self._dedupe(npc_names)
            scene["Creatures"] = self._dedupe(creature_names)
            scene["Places"] = self._dedupe(place_names)

            next_refs = []
            for key in (
                "NextScenes",
                "Next",
                "NextScene",
                "Links",
                "Transitions",
                "Choices",
                "Branches",
                "Paths",
                "Outcomes",
                "LeadsTo",
                "OnSuccess",
                "OnFailure",
                "IfSuccess",
                "IfFailure",
            ):
                next_refs.extend(self._extract_links(entry.get(key)))
            scene["NextScenes"] = self._dedupe(next_refs)

            return scene

        if isinstance(entry, str):
            text = entry.strip()
        else:
            text = str(entry).strip()
        if not text:
            return scene
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            scene["Title"] = lines[0]
            scene["Summary"] = "\n".join(lines[1:]) if len(lines) > 1 else ""
            scene["Text"] = scene["Summary"] or text
        else:
            scene["Summary"] = text
            scene["Text"] = text
        return scene

    def _coerce_scenes(self, raw):
        if not raw:
            return []
        if isinstance(raw, list):
            entries = raw
        elif isinstance(raw, dict):
            if isinstance(raw.get("Scenes"), list):
                entries = raw["Scenes"]
            else:
                entries = [raw]
        elif isinstance(raw, str):
            text = raw.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, list):
                entries = parsed
            elif isinstance(parsed, dict) and isinstance(parsed.get("Scenes"), list):
                entries = parsed["Scenes"]
            else:
                entries = [text]
        else:
            entries = [raw]

        scenes = []
        for idx, entry in enumerate(entries):
            normalised = self._normalise_scene_entry(entry, idx)
            if normalised:
                scenes.append(normalised)
        return scenes

    def _save_current_scene(self):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        scene = self.scenes[self.selected_index]
        title = self.title_var.get().strip()
        scene["Title"] = title or scene.get("Title") or f"Scene {self.selected_index + 1}"
        summary = self.summary_text.get("1.0", "end").strip()
        scene["Summary"] = summary
        scene["Text"] = summary
        next_list = self._dedupe(self._split_to_list(self.next_text.get("1.0", "end")))
        scene["NPCs"] = self._get_listbox_items("NPCs")
        scene["Creatures"] = self._get_listbox_items("Creatures")
        scene["Places"] = self._get_listbox_items("Places")
        scene["NextScenes"] = next_list
        selection = self.type_var.get()
        label = "" if selection == self.type_options[0] else selection
        scene["SceneType"] = label
        if label:
            scene["Type"] = label
        else:
            scene.pop("Type", None)
        self._update_list_item(self.selected_index)

    def add_scene(self):  # pragma: no cover - UI action
        self._save_current_scene()
        new_index = len(self.scenes)
        new_scene = self._create_scene_record(f"Scene {new_index + 1}")
        self.scenes.append(new_scene)
        self._refresh_scene_list()
        self._set_listbox_selection(new_index)
        self._apply_selection(new_index)

    def duplicate_scene(self):  # pragma: no cover - UI action
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        self._save_current_scene()
        source = self.scenes[self.selected_index]
        duplicated = copy.deepcopy(source)
        base_title = source.get("Title") or f"Scene {self.selected_index + 1}"
        duplicated["Title"] = self._generate_unique_title(base_title)
        insert_at = self.selected_index + 1
        self.scenes.insert(insert_at, duplicated)
        self._refresh_scene_list()
        self._set_listbox_selection(insert_at)
        self._apply_selection(insert_at)

    def _generate_unique_title(self, base_title):
        if not base_title:
            base_title = "Scene"
        candidate = f"{base_title} (Copy)"
        counter = 2
        existing = {scene.get("Title", "").lower() for scene in self.scenes}
        while candidate.lower() in existing:
            candidate = f"{base_title} (Copy {counter})"
            counter += 1
        return candidate

    def remove_scene(self):  # pragma: no cover - UI action
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        del self.scenes[self.selected_index]
        if not self.scenes:
            self.selected_index = None
            self._refresh_scene_list()
            return
        new_index = min(self.selected_index, len(self.scenes) - 1)
        self.selected_index = None
        self._refresh_scene_list()
        self._set_listbox_selection(new_index)
        self._apply_selection(new_index)

    def move_scene(self, direction):  # pragma: no cover - UI action
        if self.selected_index is None:
            return
        new_index = self.selected_index + direction
        if new_index < 0 or new_index >= len(self.scenes):
            return
        self._save_current_scene()
        scene = self.scenes.pop(self.selected_index)
        self.scenes.insert(new_index, scene)
        self.selected_index = new_index
        self._refresh_scene_list()
        self._set_listbox_selection(new_index)
        self._apply_selection(new_index)

    # ------------------------------------------------------------------
    # WizardStep overrides
    # ------------------------------------------------------------------
    def load_state(self, state):  # pragma: no cover - UI synchronization
        scenes = self._coerce_scenes(state.get("Scenes"))
        self.scenes = scenes
        self.selected_index = None
        self._refresh_scene_list()

    def save_state(self, state):  # pragma: no cover - UI synchronization
        self._save_current_scene()
        payload = []
        for scene in self.scenes:
            if not scene:
                continue
            title = scene.get("Title", "").strip()
            summary = scene.get("Summary", "").strip()
            has_content = bool(title or summary or scene.get("NPCs") or scene.get("Places") or scene.get("Creatures"))
            if not has_content:
                continue
            record = {
                "Title": title or "Scene",
                "Summary": summary,
                "Text": summary,
                "NPCs": list(scene.get("NPCs", [])),
                "Creatures": list(scene.get("Creatures", [])),
                "Places": list(scene.get("Places", [])),
            }
            next_scenes = list(scene.get("NextScenes", []))
            if next_scenes:
                record["NextScenes"] = next_scenes
                record["Links"] = [{"target": target, "text": target} for target in next_scenes]
            scene_type = scene.get("SceneType")
            if scene_type:
                record["SceneType"] = scene_type
                record["Type"] = scene_type
            payload.append(record)

        state["Scenes"] = payload

        for field_name in ("NPCs", "Creatures", "Places"):
            from_state = self._dedupe(self._split_to_list(state.get(field_name, [])))
            from_scenes = []
            for scene in self.scenes:
                from_scenes.extend(scene.get(field_name, []))
            merged = self._dedupe(from_state + from_scenes)
            state[field_name] = merged
        return True


class EntityLinkingStep(WizardStep):
    ENTITY_FIELDS = {
        "npcs": ("NPCs", "NPC"),
        "places": ("Places", "Place"),
        "factions": ("Factions", "Faction"),
        "creatures": ("Creatures", "Creature"),
        "objects": ("Objects", "Item"),
    }

    def __init__(self, master, wrappers):
        super().__init__(master)
        self.wrappers = wrappers
        self.selected = {field: [] for field, _ in self.ENTITY_FIELDS.values()}
        self.listboxes = {}

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        container.grid_columnconfigure((0, 1), weight=1, uniform="entities")

        for idx, (entity_type, (field, label)) in enumerate(self.ENTITY_FIELDS.items()):
            frame = ctk.CTkFrame(container)
            row, col = divmod(idx, 2)
            frame.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
            frame.grid_rowconfigure(1, weight=1)
            frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(frame, text=f"Linked {label}s", anchor="w", font=ctk.CTkFont(size=14, weight="bold")).grid(
                row=0, column=0, sticky="w", padx=6, pady=(6, 4)
            )

            listbox = tk.Listbox(frame, activestyle="none")
            listbox.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
            self.listboxes[field] = listbox

            btn_row = ctk.CTkFrame(frame)
            btn_row.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 8))
            btn_row.grid_columnconfigure((0, 1, 2), weight=1)

            ctk.CTkButton(
                btn_row,
                text="Add",
                command=lambda et=entity_type, f=field: self.open_selector(et, f),
            ).grid(row=0, column=0, padx=4, pady=2, sticky="ew")

            ctk.CTkButton(
                btn_row,
                text="Remove",
                command=lambda f=field: self.remove_selected(f),
            ).grid(row=0, column=1, padx=4, pady=2, sticky="ew")

            ctk.CTkButton(
                btn_row,
                text=f"New {label}",
                command=lambda et=entity_type, f=field, lbl=label: self.create_new_entity(et, f, lbl),
            ).grid(row=0, column=2, padx=4, pady=2, sticky="ew")

    def open_selector(self, entity_type, field):  # pragma: no cover - UI interaction
        wrapper = self.wrappers[entity_type]
        template = load_template(entity_type)
        top = ctk.CTkToplevel(self)
        top.title(f"Select {field}")
        top.geometry("1100x720")
        top.minsize(1100, 720)
        selection = GenericListSelectionView(
            top,
            entity_type,
            wrapper,
            template,
            on_select_callback=lambda et, name, f=field, win=top: self._on_entity_selected(f, name, win),
        )
        selection.pack(fill="both", expand=True)
        top.transient(self.winfo_toplevel())
        top.grab_set()

    def _on_entity_selected(self, field, name, window):  # pragma: no cover - UI callback
        if not name:
            return
        items = self.selected.setdefault(field, [])
        if name not in items:
            items.append(name)
            self.refresh_list(field)
        try:
            window.destroy()
        except Exception:
            pass

    def remove_selected(self, field):  # pragma: no cover - UI interaction
        listbox = self.listboxes.get(field)
        if not listbox:
            return
        selection = listbox.curselection()
        if not selection:
            return
        selected_items = self.selected.get(field, [])
        for index in reversed(selection):
            try:
                del selected_items[index]
            except IndexError:
                continue
        self.refresh_list(field)

    def create_new_entity(self, entity_type, field, label):  # pragma: no cover - UI interaction
        wrapper = self.wrappers.get(entity_type)
        if not wrapper:
            messagebox.showerror("Unavailable", f"No {label} data source is available.")
            return

        try:
            template = load_template(entity_type)
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(f"Failed to load template for {entity_type}: {exc}")
            messagebox.showerror("Template Error", f"Unable to load the {label} template.")
            return

        try:
            items = wrapper.load_items()
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(f"Failed to load existing {entity_type}: {exc}")
            messagebox.showerror("Database Error", f"Unable to load existing {label}s.")
            return

        new_item = {}
        editor = GenericEditorWindow(
            self.winfo_toplevel(),
            new_item,
            template,
            wrapper,
            creation_mode=True,
        )
        self.wait_window(editor)

        if not getattr(editor, "saved", False):
            return

        preferred_keys = ("Name", "Title")
        unique_key = next((key for key in preferred_keys if new_item.get(key)), None)
        unique_value = new_item.get(unique_key, "") if unique_key else ""
        if unique_key:
            replaced = False
            for idx, existing in enumerate(items):
                if existing.get(unique_key) == new_item.get(unique_key):
                    items[idx] = new_item
                    replaced = True
                    break
            if not replaced:
                items.append(new_item)
        else:
            items.append(new_item)

        try:
            wrapper.save_items(items)
            # Refresh data so future selectors pick up the new record immediately.
            wrapper.load_items()
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(f"Failed to persist new {entity_type}: {exc}")
            messagebox.showerror("Save Error", f"Unable to save the new {label}.")
            return

        if not unique_value:
            messagebox.showwarning(
                "Missing Name",
                f"The new {label.lower()} was saved without a name and cannot be linked automatically.",
            )
            return

        selected_items = self.selected.setdefault(field, [])
        if unique_value not in selected_items:
            selected_items.append(unique_value)
            self.refresh_list(field)

    def refresh_list(self, field):  # pragma: no cover - UI helper
        listbox = self.listboxes.get(field)
        if not listbox:
            return
        listbox.delete(0, tk.END)
        for name in self.selected.get(field, []):
            listbox.insert(tk.END, name)

    def load_state(self, state):  # pragma: no cover - UI synchronization
        for entity_type, (field, _) in self.ENTITY_FIELDS.items():
            values = state.get(field) or []
            if isinstance(values, str):
                values = [values]
            self.selected[field] = list(dict.fromkeys(values))
            self.refresh_list(field)

    def save_state(self, state):  # pragma: no cover - UI synchronization
        for _, (field, _) in self.ENTITY_FIELDS.items():
            state[field] = list(dict.fromkeys(self.selected.get(field, [])))
        return True


class ReviewStep(WizardStep):
    def __init__(self, master):
        super().__init__(master)
        self.text = ctk.CTkTextbox(self, state="disabled")
        self.text.pack(fill="both", expand=True, padx=20, pady=20)

    def load_state(self, state):  # pragma: no cover - UI synchronization
        summary_lines = [
            f"Title: {state.get('Title', 'Untitled Scenario')}",
            "",
            "Summary:",
            state.get("Summary", "(No summary provided.)"),
            "",
            "Secrets:",
            state.get("Secrets", "(No secrets provided.)"),
            "",
            "Scenes:",
        ]

        scenes = state.get("Scenes") or []
        if isinstance(scenes, (list, tuple)) and scenes:
            for idx, scene in enumerate(scenes, start=1):
                if isinstance(scene, dict):
                    title = scene.get("Title") or scene.get("title") or f"Scene {idx}"
                    summary_lines.append(f"  - {title}")
                else:
                    summary_lines.append(f"  - {scene}")
        else:
            summary_lines.append("  (No scenes planned.)")

        for field in ("NPCs", "Creatures", "Places", "Factions", "Objects"):
            entries = state.get(field) or []
            summary_lines.append("")
            summary_lines.append(f"{field}:")
            if entries:
                for name in entries:
                    summary_lines.append(f"  - {name}")
            else:
                summary_lines.append("  (None)")

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(summary_lines))
        self.text.configure(state="disabled")


class ScenarioBuilderWizard(ctk.CTkToplevel):
    """Interactive wizard guiding users through building a scenario."""

    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.title("Scenario Builder Wizard")
        self.geometry("1280x860")
        self.minsize(1100, 700)
        self.transient(master)
        self.on_saved = on_saved

        # NOTE: Avoid shadowing the inherited ``state()`` method from Tk by
        # storing wizard data on a dedicated attribute.
        self.wizard_state = {
            "Title": "",
            "Summary": "",
            "Secrets": "",
            "Secret": "",
            "Scenes": [],
            "NPCs": [],
            "Creatures": [],
            "Places": [],
            "Factions": [],
            "Objects": [],
        }

        self.scenario_wrapper = GenericModelWrapper("scenarios")
        self.npc_wrapper = GenericModelWrapper("npcs")
        self.creature_wrapper = GenericModelWrapper("creatures")
        self.place_wrapper = GenericModelWrapper("places")
        self.faction_wrapper = GenericModelWrapper("factions")
        self.object_wrapper = GenericModelWrapper("objects")

        self._build_layout()
        self._create_steps()
        self.current_step_index = 0
        self._show_step(0)

    def _build_layout(self):  # pragma: no cover - UI layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew")
        self.header_label = ctk.CTkLabel(
            header,
            text="Scenario Builder",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        )
        self.header_label.pack(fill="x", padx=20, pady=12)

        self.step_container = ctk.CTkFrame(self)
        self.step_container.grid(row=1, column=0, sticky="nsew")
        self.step_container.grid_rowconfigure(0, weight=1)
        self.step_container.grid_columnconfigure(0, weight=1)

        nav = ctk.CTkFrame(self)
        nav.grid(row=2, column=0, sticky="ew")
        nav.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.back_btn = ctk.CTkButton(nav, text="Back", command=self.go_back)
        self.back_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.next_btn = ctk.CTkButton(nav, text="Next", command=self.go_next)
        self.next_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.finish_btn = ctk.CTkButton(nav, text="Finish", command=self.finish)
        self.finish_btn.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
        self.cancel_btn = ctk.CTkButton(nav, text="Cancel", command=self.cancel)
        self.cancel_btn.grid(row=0, column=3, padx=10, pady=10, sticky="ew")

    def _create_steps(self):  # pragma: no cover - UI layout
        entity_wrappers = {
            "npcs": self.npc_wrapper,
            "places": self.place_wrapper,
            "factions": self.faction_wrapper,
            "creatures": self.creature_wrapper,
            "objects": self.object_wrapper,
        }

        self.steps = [
            ("Basic Information", BasicInfoStep(self.step_container)),
            (
                "Scenes",
                ScenesPlanningStep(self.step_container, {
                    key: wrapper
                    for key, wrapper in entity_wrappers.items()
                    if key in ("npcs", "creatures", "places")
                }),
            ),
            ("Entity Linking", EntityLinkingStep(self.step_container, entity_wrappers)),
            ("Review", ReviewStep(self.step_container)),
        ]

        for _, frame in self.steps:
            frame.grid(row=0, column=0, sticky="nsew")

    def _show_step(self, index):  # pragma: no cover - UI navigation
        title, frame = self.steps[index]
        self.header_label.configure(text=f"Step {index + 1} of {len(self.steps)}: {title}")
        frame.tkraise()
        frame.load_state(self.wizard_state)
        self._update_navigation_buttons()

    def _update_navigation_buttons(self):  # pragma: no cover - UI navigation
        self.back_btn.configure(state="normal" if self.current_step_index > 0 else "disabled")
        is_last = self.current_step_index == len(self.steps) - 1
        self.next_btn.configure(state="disabled" if is_last else "normal")
        self.finish_btn.configure(state="normal" if is_last else "disabled")

    def go_next(self):  # pragma: no cover - UI navigation
        step = self.steps[self.current_step_index][1]
        if not step.save_state(self.wizard_state):
            return
        self.current_step_index += 1
        self._show_step(self.current_step_index)

    def go_back(self):  # pragma: no cover - UI navigation
        step = self.steps[self.current_step_index][1]
        if not step.save_state(self.wizard_state):
            return
        self.current_step_index -= 1
        self._show_step(self.current_step_index)

    def cancel(self):  # pragma: no cover - UI navigation
        self.destroy()

    def finish(self):  # pragma: no cover - UI navigation
        step = self.steps[self.current_step_index][1]
        if not step.save_state(self.wizard_state):
            return

        title = (self.wizard_state.get("Title") or "").strip()
        if not title:
            messagebox.showwarning("Missing Title", "Please provide a title before saving the scenario.")
            return

        secrets = self.wizard_state.get("Secrets") or ""
        scenes = self.wizard_state.get("Scenes") or []
        if isinstance(scenes, str):
            scenes = [scenes]

        payload = {
            "Title": title,
            "Summary": self.wizard_state.get("Summary", ""),
            "Secrets": secrets,
            "Secret": secrets,
            "Scenes": scenes,
            "Places": list(dict.fromkeys(self.wizard_state.get("Places", []))),
            "NPCs": list(dict.fromkeys(self.wizard_state.get("NPCs", []))),
            "Creatures": list(dict.fromkeys(self.wizard_state.get("Creatures", []))),
            "Factions": list(dict.fromkeys(self.wizard_state.get("Factions", []))),
            "Objects": list(dict.fromkeys(self.wizard_state.get("Objects", []))),
        }

        buttons = {
            self.back_btn: self.back_btn.cget("state"),
            self.next_btn: self.next_btn.cget("state"),
            self.finish_btn: self.finish_btn.cget("state"),
            self.cancel_btn: self.cancel_btn.cget("state"),
        }
        for btn in buttons:
            btn.configure(state="disabled")

        try:
            while True:
                try:
                    items = self.scenario_wrapper.load_items()
                    break
                except (sqlite3.Error, json.JSONDecodeError):
                    log_exception(
                        "Failed to load scenarios for ScenarioBuilderWizard.",
                        func_name="ScenarioBuilderWizard.finish",
                    )
                    if not messagebox.askretrycancel(
                        "Load Error",
                        "An error occurred while loading scenarios. Retry?",
                    ):
                        return
            replaced = False
            for idx, existing in enumerate(items):
                if existing.get("Title") == title:
                    if not messagebox.askyesno(
                        "Overwrite Scenario",
                        f"A scenario titled '{title}' already exists. Overwrite it?",
                    ):
                        return
                    items[idx] = payload
                    replaced = True
                    break

            if not replaced:
                items.append(payload)

            log_info(
                f"Saving scenario '{title}' via builder wizard (replaced={replaced})",
                func_name="ScenarioBuilderWizard.finish",
            )

            self.scenario_wrapper.save_items(items)
            messagebox.showinfo("Scenario Saved", f"Scenario '{title}' has been saved.")
            if callable(self.on_saved):
                try:
                    self.on_saved()
                except Exception:
                    pass
        finally:
            for btn, previous_state in buttons.items():
                btn.configure(state=previous_state)
        self.destroy()

