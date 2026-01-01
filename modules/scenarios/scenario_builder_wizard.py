import copy
import json
import os
import sqlite3
import textwrap
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from modules.generic.generic_editor_window import GenericEditorWindow
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import, log_info, log_exception
from modules.helpers.template_loader import load_template, load_entity_definitions
from modules.helpers.text_helpers import coerce_text
from modules.scenarios.scene_flow_components import (
    SceneCanvas,
    SceneFlowPreview,
    normalise_scene_links,
)
from modules.scenarios.scenario_character_graph import (
    ScenarioCharacterGraphEditor,
    sync_scenario_graph_to_global,
)

try:
    _IMAGE_RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - Pillow < 9.1
    _IMAGE_RESAMPLE = Image.LANCZOS


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
    ENTITY_FIELDS = {
        "NPCs": ("npcs", "Key NPCs", "NPC"),
        "Creatures": ("creatures", "Creatures / Foes", "Creature"),
        "Places": ("places", "Locations / Places", "Place"),
        "Maps": ("maps", "Maps & Handouts", "Map"),
    }

    SCENE_TYPES = [
        "Auto",
        "Setup",
        "Choice",
        "Investigation",
        "Combat",
        "Outcome",
        "Social",
        "Travel",
        "Downtime",
    ]

    ROOT_KNOWN_FIELDS = {
        "Title",
        "Summary",
        "Text",
        "Secrets",
        "Secret",
        "Scenes",
        "_SceneLayout",
        "NPCs",
        "Creatures",
        "Places",
        "Maps",
        "Factions",
        "Objects",
    }

    SCENE_KNOWN_FIELDS = {
        "Title",
        "Summary",
        "SceneSummary",
        "Text",
        "SceneText",
        "Description",
        "Body",
        "Details",
        "SceneDetails",
        "Notes",
        "Content",
        "Synopsis",
        "Overview",
        "SceneType",
        "Type",
        "NPCs",
        "Creatures",
        "Places",
        "Maps",
        "NextScenes",
        "Links",
        "LinkData",
        "_canvas",
        "_extra_fields",
    }

    def __init__(
        self,
        master,
        entity_wrappers,
        *,
        scenario_wrapper=None,
        finale_planner_callback=None,
    ):
        super().__init__(master)
        self.entity_wrappers = entity_wrappers or {}
        self.scenario_wrapper = scenario_wrapper
        self.scenes = []
        self.selected_index = None
        self._scenario_summary = ""
        self._scenario_secrets = ""
        self._inline_editor = None
        self._link_label_editor = None
        self._state_ref = None
        self._on_state_change = None
        self._finale_planner_callback = finale_planner_callback
        self._root_extra_fields = {}

        self.scenario_title_var = ctk.StringVar()

        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        available_types = [
            field
            for field, (slug, _, _) in self.ENTITY_FIELDS.items()
            if slug in self.entity_wrappers
        ]
        if not available_types:
            available_types = list(self.ENTITY_FIELDS.keys())
        self._available_entity_types = available_types

        toolbar = ctk.CTkFrame(root, fg_color="#101827", corner_radius=14)
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(toolbar, text="Scenario Title", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4)
        )
        self.scenario_title_entry = ctk.CTkEntry(
            toolbar, textvariable=self.scenario_title_var, font=ctk.CTkFont(size=18, weight="bold")
        )
        self.scenario_title_entry.grid(row=1, column=0, sticky="ew", padx=16)

        btn_row = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_row.grid(row=1, column=1, padx=16, pady=(0, 12))
        self.load_scenario_btn = ctk.CTkButton(
            btn_row, text="Load Scenario", command=self._load_existing_scenario
        )
        self.load_scenario_btn.pack(side="left")
        if self._finale_planner_callback:
            self.finale_planner_btn = ctk.CTkButton(
                btn_row,
                text="Epic Finale Planner",
                command=self._switch_to_epic_finale_planner,
            )
            self.finale_planner_btn.pack(side="left", padx=(6, 0))
        self.notes_btn = ctk.CTkButton(btn_row, text="Edit Notes", command=self._edit_scenario_info)
        self.notes_btn.pack(side="left", padx=(6, 0))
        self.add_scene_btn = ctk.CTkButton(btn_row, text="Add Scene", command=self.add_scene)
        self.add_scene_btn.pack(side="left", padx=(6, 0))
        self.dup_scene_btn = ctk.CTkButton(btn_row, text="Duplicate", command=self.duplicate_scene)
        self.dup_scene_btn.pack(side="left", padx=6)
        self.remove_scene_btn = ctk.CTkButton(btn_row, text="Remove", command=self.remove_scene)
        self.remove_scene_btn.pack(side="left")

        icon_hint = "/".join(
            f"+{SceneCanvas.ICON_LABELS.get(field, field[:1].upper())}"
            for field in self._available_entity_types
            if SceneCanvas.ICON_LABELS.get(field)
        )
        if not icon_hint:
            icon_hint = "+N/+C/+P"
        ctk.CTkLabel(
            toolbar,
            text=(
                "Double-click a scene to edit it inline, use the "
                f"{icon_hint} icons to link entities, drag from the title bar to move, "
                "or drag from the body to create scene links."
            ),
            text_color="#9db4d1",
            wraplength=420,
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 10))

        main = ctk.CTkFrame(root, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)
        self._main_frame = main

        self.canvas = SceneCanvas(
            main,
            on_select=self._on_canvas_select,
            on_move=self._on_canvas_move,
            on_edit=self._edit_scene_via_canvas,
            on_context=self._show_canvas_menu,
            on_add_entity=self._add_entity_to_scene,
            on_link=self._link_scenes_via_drag,
            on_link_text_edit=self._start_link_label_edit,
            available_entity_types=self._available_entity_types,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

    def set_state_binding(self, state, on_state_change=None):
        self._state_ref = state
        self._on_state_change = on_state_change

    def _switch_to_epic_finale_planner(self):  # pragma: no cover - UI interaction
        if not self._finale_planner_callback:
            return
        if self._state_ref is None:
            messagebox.showerror(
                "Unavailable",
                "The finale planner cannot be opened until the wizard has initialised.",
            )
            return
        if not self.save_state(self._state_ref):
            return
        try:
            payload = copy.deepcopy(self._state_ref)
            self._finale_planner_callback(payload)
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(
                f"Failed to switch to Epic Finale Planner: {exc}",
                func_name="ScenesPlanningStep._switch_to_epic_finale_planner",
            )
            messagebox.showerror(
                "Error",
                "Unable to open the Epic Finale Planner from the wizard.",
            )

    def _get_scene_links(self, scene):
        return normalise_scene_links(scene, self._split_to_list)

    def _on_canvas_select(self, index):
        if index is None or index >= len(self.scenes):
            self.selected_index = None
        else:
            if (
                self._inline_editor is not None
                and getattr(self._inline_editor, "scene_index", None) != index
            ):
                self._close_inline_scene_editor()
            self.selected_index = index
        self._close_link_label_editor()
        self.canvas.set_scenes(self.scenes, index)
        self._update_buttons()

    def _on_canvas_move(self, index, x, y):
        if index is None or index >= len(self.scenes):
            return
        layout = self.scenes[index].setdefault("_canvas", {})
        layout["x"] = x
        layout["y"] = y

    def _edit_scenario_info(self):
        dialog = ScenarioInfoDialog(
            self.winfo_toplevel(),
            title=self.scenario_title_var.get().strip() or "Scenario Notes",
            summary=self._scenario_summary,
            secrets=self._scenario_secrets,
        )
        self.wait_window(dialog)
        if dialog.result:
            self._scenario_summary = dialog.result.get("summary", "")
            self._scenario_secrets = dialog.result.get("secrets", "")

    def _load_existing_scenario(self):  # pragma: no cover - UI interaction
        if not self.scenario_wrapper:
            messagebox.showerror("Unavailable", "No scenario library is available to load from.")
            return

        scenario_name = self._choose_existing_scenario()
        if not scenario_name:
            return

        try:
            scenarios = self.scenario_wrapper.load_items()
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(
                f"Failed to load scenarios: {exc}",
                func_name="ScenesPlanningStep._load_existing_scenario",
            )
            messagebox.showerror("Load Error", "Unable to load scenarios from the database.")
            return

        match = None
        for entry in scenarios or []:
            title = entry.get("Title") or entry.get("Name")
            if title == scenario_name:
                match = entry
                break

        if not match:
            messagebox.showerror("Not Found", f"Scenario '{scenario_name}' was not found.")
            return

        self.load_from_payload(copy.deepcopy(match))

    def _choose_existing_scenario(self):  # pragma: no cover - UI interaction
        try:
            template = load_template("scenarios")
        except Exception as exc:
            log_exception(
                f"Failed to load scenario template: {exc}",
                func_name="ScenesPlanningStep._choose_existing_scenario",
            )
            messagebox.showerror("Template Error", "Unable to load the scenario list.")
            return None

        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Scenario")
        dialog.geometry("1100x720")
        dialog.minsize(1100, 720)
        result = {"name": None}

        view = GenericListSelectionView(
            dialog,
            "scenarios",
            self.scenario_wrapper,
            template,
            on_select_callback=lambda _et, name, win=dialog: (
                result.__setitem__("name", name),
                win.destroy(),
            ),
        )
        view.pack(fill="both", expand=True)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        self.wait_window(dialog)
        return result["name"]

    def load_from_payload(self, scenario):  # pragma: no cover - UI synchronization
        if not isinstance(scenario, dict):
            return
        self._apply_loaded_scenario(copy.deepcopy(scenario))

    def _apply_loaded_scenario(self, scenario):
        title = scenario.get("Title") or scenario.get("Name") or ""
        summary = coerce_text(scenario.get("Summary"))
        if not summary:
            summary = coerce_text(scenario.get("Text"))
        secrets = coerce_text(scenario.get("Secrets"))
        if not secrets:
            secrets = coerce_text(scenario.get("Secret"))

        self.scenario_title_var.set(str(title))
        self._scenario_summary = str(summary)
        self._scenario_secrets = str(secrets)

        scenes_payload = scenario.get("Scenes")
        self.scenes = self._coerce_scenes(copy.deepcopy(scenes_payload))
        layout = scenario.get("_SceneLayout")
        if isinstance(layout, list):
            for idx, scene in enumerate(self.scenes):
                if idx < len(layout) and isinstance(layout[idx], dict):
                    scene.setdefault("_canvas", {}).update(layout[idx])

        self.selected_index = 0 if self.scenes else None
        self._close_inline_scene_editor()
        self._close_link_label_editor()
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._update_buttons()

        if self._state_ref is None:
            return

        self._state_ref["Title"] = str(title)
        self._state_ref["Summary"] = summary
        self._state_ref["Secrets"] = secrets
        self._state_ref["Secret"] = secrets

        if isinstance(layout, list):
            self._state_ref["_SceneLayout"] = copy.deepcopy(layout)
        else:
            self._state_ref["_SceneLayout"] = []

        for field in ("NPCs", "Creatures", "Places", "Maps", "Factions", "Objects"):
            values = scenario.get(field) or []
            if isinstance(values, str):
                values = self._split_to_list(values)
            elif isinstance(values, list):
                values = [str(item).strip() for item in values if str(item).strip()]
            elif values:
                values = [str(values).strip()]
            else:
                values = []
            self._state_ref[field] = list(dict.fromkeys(values))

        self._root_extra_fields = {
            key: copy.deepcopy(value)
            for key, value in scenario.items()
            if key not in self.ROOT_KNOWN_FIELDS
        }

        self.save_state(self._state_ref)
        if callable(self._on_state_change):
            try:
                self._on_state_change(source=self)
            except TypeError:
                self._on_state_change()

    def _edit_scene_via_canvas(self, index):
        if index is None or index >= len(self.scenes):
            return
        self._open_inline_scene_editor(index)

    def _open_inline_scene_editor(self, index):
        bbox = self.canvas.get_card_bbox(index)
        if not bbox:
            return
        self._close_inline_scene_editor()
        self._close_link_label_editor()
        scene = self.scenes[index]
        x1, y1, x2, y2 = bbox
        width = max(120, (x2 - x1) - 16)
        height = max(120, (y2 - y1) - 16)
        editor = InlineSceneEditor(
            self.canvas,
            scene,
            scene_types=self.SCENE_TYPES,
            on_save=lambda data, idx=index: self._apply_inline_scene_update(idx, data),
            on_cancel=self._close_inline_scene_editor,
            width=width,
            height=height,
        )
        editor.scene_index = index
        editor.place(
            x=x1 + 8,
            y=y1 + 8,
        )
        self._inline_editor = editor

    def _close_inline_scene_editor(self):
        if self._inline_editor is None:
            return
        try:
            self._inline_editor.destroy()
        except Exception:
            pass
        self._inline_editor = None

    def _apply_inline_scene_update(self, index, data):
        if index is None or index >= len(self.scenes):
            return
        scene = self.scenes[index]
        scene["Title"] = data.get("Title", scene.get("Title", "")).strip() or scene.get(
            "Title", f"Scene {index + 1}"
        )
        scene["SceneType"] = data.get("SceneType", "")
        summary = data.get("Summary", "")
        scene["Summary"] = summary
        scene["Text"] = summary
        self._close_inline_scene_editor()
        self._close_link_label_editor()
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._update_buttons()

    def _show_canvas_menu(self, event, index):
        if index is None:
            self._show_background_menu(event)
        else:
            self._show_scene_menu(event, index)

    def _show_background_menu(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Add Scene", command=self.add_scene)
        menu.add_command(label="Edit Scenario Notes", command=self._edit_scenario_info)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_scene_menu(self, event, index):
        self.selected_index = index
        self.canvas.set_scenes(self.scenes, index)
        self._update_buttons()

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Edit Scene Inline",
            command=lambda idx=index: self._open_inline_scene_editor(idx),
        )
        menu.add_separator()
        menu.add_command(label="Duplicate Scene", command=lambda idx=index: self.duplicate_scene(idx))
        menu.add_command(label="Remove Scene", command=lambda idx=index: self.remove_scene(idx))

        menu.add_separator()
        for field, (slug, _, singular_label) in self.ENTITY_FIELDS.items():
            if slug in self.entity_wrappers:
                menu.add_command(
                    label=f"Create {singular_label}",
                    command=lambda f=field, idx=index: self._create_entity_for_scene(idx, f),
                )
            else:
                menu.add_command(label=f"Create {singular_label}", state="disabled")

        menu.add_separator()
        for field, (_, _, singular_label) in self.ENTITY_FIELDS.items():
            entries = []
            if 0 <= index < len(self.scenes):
                bucket = self.scenes[index].get(field)
                if isinstance(bucket, list):
                    entries = [item for item in bucket if str(item).strip()]
            if entries:
                remove_menu = tk.Menu(menu, tearoff=0)
                for name in entries:
                    display = str(name).strip()
                    if not display:
                        display = f"(Unnamed {singular_label})"
                    remove_menu.add_command(
                        label=display,
                        command=lambda value=name, idx=index, f=field: self._remove_entity_from_scene(idx, f, value),
                    )
                remove_menu.add_separator()
                remove_menu.add_command(
                    label="Clear All",
                    command=lambda idx=index, f=field: self._clear_entities_from_scene(idx, f),
                )
                menu.add_cascade(label=f"Remove {singular_label}s", menu=remove_menu)
            else:
                menu.add_command(label=f"Remove {singular_label}s", state="disabled")

        existing_links = self._get_scene_links(self.scenes[index])
        if existing_links:
            remove_menu = tk.Menu(menu, tearoff=0)
            for link in existing_links:
                target = link.get("target") or ""
                label = link.get("text") or target
                display = label if label == target else f"{label} → {target}"
                remove_menu.add_command(
                    label=display,
                    command=lambda tgt=target, idx=index: self._remove_link_between(idx, tgt),
                )
            remove_menu.add_separator()
            remove_menu.add_command(
                label="Clear All", command=lambda idx=index: self._clear_links(idx)
            )
            menu.add_cascade(label="Remove Link", menu=remove_menu)
        else:
            menu.add_command(label="Remove Link", state="disabled")

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _add_link_between(self, source_index, target_title, label=None):
        if source_index is None or source_index >= len(self.scenes):
            return
        scene = self.scenes[source_index]
        links = self._get_scene_links(scene)
        if any(link.get("target") == target_title for link in links):
            return
        display_label = (label or target_title).strip() or target_title
        links.append({"target": target_title, "text": display_label})
        scene["LinkData"] = links
        scene["NextScenes"] = [link["target"] for link in links]
        self._close_link_label_editor()
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _remove_link_between(self, source_index, target_title):
        if source_index is None or source_index >= len(self.scenes):
            return
        scene = self.scenes[source_index]
        links = [link for link in self._get_scene_links(scene) if link.get("target") != target_title]
        scene["LinkData"] = links
        scene["NextScenes"] = [link["target"] for link in links]
        self._close_link_label_editor()
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _clear_links(self, source_index):
        if source_index is None or source_index >= len(self.scenes):
            return
        scene = self.scenes[source_index]
        scene["LinkData"] = []
        scene["NextScenes"] = []
        self._close_link_label_editor()
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _remove_entity_from_scene(self, scene_index, field, name):
        if scene_index is None or scene_index >= len(self.scenes):
            return
        if field not in self.ENTITY_FIELDS:
            return
        scene = self.scenes[scene_index]
        bucket = scene.get(field)
        if not isinstance(bucket, list) or not bucket:
            return
        target = str(name).strip().lower()
        filtered = [item for item in bucket if str(item).strip().lower() != target]
        if len(filtered) == len(bucket):
            return
        scene[field] = filtered
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _clear_entities_from_scene(self, scene_index, field):
        if scene_index is None or scene_index >= len(self.scenes):
            return
        if field not in self.ENTITY_FIELDS:
            return
        scene = self.scenes[scene_index]
        if isinstance(scene.get(field), list) and scene.get(field):
            scene[field] = []
            self.canvas.set_scenes(self.scenes, self.selected_index)

    def _add_entity_to_scene(self, scene_index, entity_type):
        if scene_index is None or scene_index >= len(self.scenes):
            return
        config = self.ENTITY_FIELDS.get(entity_type)
        if not config:
            return
        slug, _, singular_label = config
        selected = self._choose_entity_from_library(slug, singular_label)
        if not selected:
            return
        scene = self.scenes[scene_index]
        bucket = scene.setdefault(entity_type, [])
        if selected not in bucket:
            bucket.append(selected)
            bucket.sort(key=lambda value: value.lower() if isinstance(value, str) else str(value))
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _create_entity_for_scene(self, scene_index, entity_type):
        if scene_index is None or scene_index >= len(self.scenes):
            return
        config = self.ENTITY_FIELDS.get(entity_type)
        if not config:
            return
        slug, _, singular_label = config
        name = self._create_entity_in_library(slug, singular_label)
        if not name:
            return
        scene = self.scenes[scene_index]
        bucket = scene.setdefault(entity_type, [])
        if name not in bucket:
            bucket.append(name)
            bucket.sort(key=lambda value: value.lower() if isinstance(value, str) else str(value))
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _link_scenes_via_drag(self, source_index, target_index):
        if (
            source_index is None
            or target_index is None
            or source_index >= len(self.scenes)
            or target_index >= len(self.scenes)
        ):
            return
        target_title = (
            self.scenes[target_index].get("Title")
            or self.scenes[target_index].get("Name")
            or f"Scene {target_index + 1}"
        )
        self._add_link_between(source_index, target_title, label=target_title)

    def _start_link_label_edit(self, source_index, target_index, target_value, bbox):
        if source_index is None or source_index >= len(self.scenes):
            return
        scene = self.scenes[source_index]
        links = self._get_scene_links(scene)
        target_str = str(target_value)
        link = next((l for l in links if str(l.get("target")) == target_str), None)
        if link is None and target_index is not None and target_index < len(self.scenes):
            fallback = self.scenes[target_index].get("Title") or f"Scene {target_index + 1}"
            link = next((l for l in links if str(l.get("target")) == fallback), None)
            target_str = fallback
        if link is None:
            return
        self._close_link_label_editor()
        x1, y1, x2, y2 = bbox
        width = max(160, int(x2 - x1 + 24))
        entry = ctk.CTkEntry(self.canvas, width=width, height=30)
        entry.insert(0, link.get("text") or target_str)
        entry.place(x=x1 - 12, y=y1 - 10)
        entry.focus_set()
        entry.select_range(0, "end")
        state = {
            "widget": entry,
            "source": source_index,
            "target": target_str,
        }
        self._link_label_editor = state

        entry.bind("<Return>", lambda _e: self._commit_link_label_editor(save=True))
        entry.bind("<Escape>", lambda _e: self._commit_link_label_editor(save=False))
        entry.bind("<FocusOut>", lambda _e: self._commit_link_label_editor(save=True))

    def _commit_link_label_editor(self, save=True):
        if not self._link_label_editor:
            return
        state = self._link_label_editor
        entry = state.get("widget")
        if entry is None:
            self._link_label_editor = None
            return
        try:
            entry.unbind("<FocusOut>")
        except Exception:
            pass
        text_value = ""
        if save:
            try:
                text_value = entry.get().strip()
            except Exception:
                text_value = ""
        try:
            entry.destroy()
        except Exception:
            pass
        self._link_label_editor = None
        if not save:
            self.canvas.set_scenes(self.scenes, self.selected_index)
            return
        if not text_value:
            text_value = state.get("target", "")
        source_index = state.get("source")
        if source_index is None or source_index >= len(self.scenes):
            self.canvas.set_scenes(self.scenes, self.selected_index)
            return
        scene = self.scenes[source_index]
        links = self._get_scene_links(scene)
        target_str = state.get("target")
        for link in links:
            if str(link.get("target")) == target_str:
                link["text"] = text_value
                break
        scene["LinkData"] = links
        scene["NextScenes"] = [link["target"] for link in links]
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _close_link_label_editor(self):
        if not self._link_label_editor:
            return
        entry = self._link_label_editor.get("widget")
        self._link_label_editor = None
        if entry is not None:
            try:
                entry.destroy()
            except Exception:
                pass

    def _choose_entity_from_library(self, entity_slug, singular_label):
        wrapper = self.entity_wrappers.get(entity_slug)
        if not wrapper:
            messagebox.showerror("Unavailable", f"No {singular_label} library available")
            return None
        try:
            template = load_template(entity_slug)
        except Exception as exc:
            log_exception(
                f"Failed to load template for {entity_slug}: {exc}",
                func_name="ScenesPlanningStep._choose_entity_from_library",
            )
            messagebox.showerror("Template Error", f"Unable to load {singular_label} list")
            return None

        top = ctk.CTkToplevel(self)
        top.title(f"Select {singular_label}")
        top.geometry("1100x720")
        top.minsize(1100, 720)
        result = {"name": None}

        view = GenericListSelectionView(
            top,
            entity_slug,
            wrapper,
            template,
            on_select_callback=lambda _et, name, win=top: (result.__setitem__("name", name), win.destroy()),
        )
        view.pack(fill="both", expand=True)
        top.transient(self.winfo_toplevel())
        top.grab_set()
        self.wait_window(top)
        return result["name"]

    def _create_entity_in_library(self, entity_slug, singular_label):
        wrapper = self.entity_wrappers.get(entity_slug)
        if not wrapper:
            messagebox.showerror("Unavailable", f"No {singular_label} data available for creation.")
            return None
        try:
            template = load_template(entity_slug)
        except Exception as exc:
            log_exception(
                f"Failed to load template for {entity_slug}: {exc}",
                func_name="ScenesPlanningStep._create_entity_in_library",
            )
            messagebox.showerror("Template Error", f"Unable to load the {singular_label} template.")
            return None

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
            return None

        try:
            items = wrapper.load_items()
        except Exception:
            items = []
        name = editor.item.get("Name") or editor.item.get("Title")
        replaced = False
        if name:
            for idx, existing in enumerate(items):
                existing_name = existing.get("Name") or existing.get("Title")
                if existing_name and existing_name == name:
                    items[idx] = editor.item
                    replaced = True
                    break
        if not replaced:
            items.append(editor.item)
        try:
            wrapper.save_items(items)
        except Exception as exc:
            log_exception(
                f"Failed to save {entity_slug}: {exc}",
                func_name="ScenesPlanningStep._create_entity_in_library",
            )
            messagebox.showerror("Save Error", f"Unable to save the new {singular_label}.")
            return None
        return name

    def add_scene(self):
        scene = {
            "Title": f"Scene {len(self.scenes) + 1}",
            "Summary": "",
            "SceneType": "",
            "NPCs": [],
            "Creatures": [],
            "Places": [],
            "Maps": [],
            "NextScenes": [],
            "LinkData": [],
        }
        self._assign_default_position(scene)
        self.scenes.append(scene)
        self.selected_index = len(self.scenes) - 1
        self._close_link_label_editor()
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._update_buttons()

    def duplicate_scene(self, index=None):
        if index is None:
            index = self.selected_index
        if index is None or index >= len(self.scenes):
            return
        source = copy.deepcopy(self.scenes[index])
        source.pop("_canvas", None)
        dup = copy.deepcopy(source)
        dup["Title"] = self._unique_title(source.get("Title") or "Scene")
        dup["_canvas"] = {}
        self._assign_default_position(dup)
        insert_at = index + 1
        self.scenes.insert(insert_at, dup)
        self.selected_index = insert_at
        self._close_link_label_editor()
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._update_buttons()

    def remove_scene(self, index=None):
        if index is None:
            index = self.selected_index
        if index is None or index >= len(self.scenes):
            return
        removed_scene = self.scenes.pop(index)
        removed_title = (removed_scene.get("Title") or "").strip()

        for scene in self.scenes:
            links = self._get_scene_links(scene)
            filtered = [link for link in links if link.get("target") != removed_title]
            if len(filtered) != len(links):
                scene["LinkData"] = filtered
                scene["NextScenes"] = [link["target"] for link in filtered]

        if not self.scenes:
            self.selected_index = None
        elif index >= len(self.scenes):
            self.selected_index = len(self.scenes) - 1
        else:
            self.selected_index = index

        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._update_buttons()

    def _update_buttons(self):
        state = "normal" if self.selected_index is not None else "disabled"
        self.dup_scene_btn.configure(state=state)
        self.remove_scene_btn.configure(state=state)

    def _assign_default_position(self, scene):
        layout = scene.setdefault("_canvas", {})
        layout.setdefault("x", 180 + len(self.scenes) * 40)
        layout.setdefault("y", 160 + len(self.scenes) * 40)

    def _unique_title(self, base):
        base = base or "Scene"
        used = {s.get("Title", "").lower() for s in self.scenes}
        if base.lower() not in used:
            return base
        counter = 2
        while f"{base} ({counter})".lower() in used:
            counter += 1
        return f"{base} ({counter})"

    # ------------------------------------------------------------------
    # WizardStep overrides
    # ------------------------------------------------------------------
    def load_state(self, state):
        self.scenario_title_var.set(state.get("Title", ""))
        self._scenario_summary = state.get("Summary", "")
        self._scenario_secrets = state.get("Secrets") or state.get("Secret") or ""
        self.scenes = self._coerce_scenes(state.get("Scenes"))
        layout = state.get("_SceneLayout")
        if isinstance(layout, list):
            for idx, scene in enumerate(self.scenes):
                if idx < len(layout) and isinstance(layout[idx], dict):
                    scene.setdefault("_canvas", {}).update(layout[idx])
        self.selected_index = None
        self._close_inline_scene_editor()
        self._close_link_label_editor()
        self.canvas.set_scenes(self.scenes, None)
        self._update_buttons()

        self._root_extra_fields = {
            key: copy.deepcopy(value)
            for key, value in (state or {}).items()
            if key not in self.ROOT_KNOWN_FIELDS
        }

    def save_state(self, state):
        self._close_inline_scene_editor()
        self._close_link_label_editor()
        state["Title"] = self.scenario_title_var.get().strip()
        summary = (self._scenario_summary or "").strip()
        secrets = (self._scenario_secrets or "").strip()
        state["Summary"] = summary
        state["Secrets"] = secrets
        state["Secret"] = secrets

        payload = []
        layout = []
        for scene in self.scenes:
            if not scene:
                continue
            record = {
                "Title": scene.get("Title", "Scene"),
                "Summary": scene.get("Summary", ""),
                "Text": scene.get("Summary", ""),
                "NPCs": list(scene.get("NPCs", [])),
                "Creatures": list(scene.get("Creatures", [])),
                "Places": list(scene.get("Places", [])),
                "Maps": list(scene.get("Maps", [])),
            }
            if scene.get("SceneType"):
                record["SceneType"] = scene["SceneType"]
                record["Type"] = scene["SceneType"]
            links = self._get_scene_links(scene)
            if links:
                record["NextScenes"] = [link["target"] for link in links]
                record["Links"] = [
                    {"target": link["target"], "text": link.get("text") or link["target"]}
                    for link in links
                ]
            extras = scene.get("_extra_fields")
            if isinstance(extras, dict):
                for key, value in extras.items():
                    if key not in record:
                        record[key] = copy.deepcopy(value)
            payload.append(record)
            layout.append(scene.get("_canvas", {}))
        state["Scenes"] = payload
        state["_SceneLayout"] = layout

        for field in ("NPCs", "Creatures", "Places", "Maps"):
            merged = self._dedupe(self._split_to_list(state.get(field, [])))
            for scene in self.scenes:
                merged.extend(scene.get(field, []))
            state[field] = self._dedupe(merged)

        if isinstance(self._root_extra_fields, dict):
            for key, value in self._root_extra_fields.items():
                state.setdefault(key, copy.deepcopy(value))
        return True

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _split_to_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            parts = [part.strip() for part in value.replace(";", ",").split(",")]
            return [part for part in parts if part]
        return [str(value).strip()]

    @staticmethod
    def _dedupe(items):
        seen = set()
        result = []
        for item in items:
            key = str(item).strip().lower()
            if key and key not in seen:
                seen.add(key)
                result.append(str(item).strip())
        return result

    def _coerce_scenes(self, raw):
        if not raw:
            return []
        if isinstance(raw, list):
            result = []
            for idx, entry in enumerate(raw):
                scene = self._normalise_scene(entry, idx)
                if scene:
                    result.append(scene)
            return result
        if isinstance(raw, dict):
            return [self._normalise_scene(raw, 0)]
        return []

    def _normalise_scene(self, entry, index):
        if not isinstance(entry, dict):
            return None
        next_refs = self._split_to_list(entry.get("NextScenes"))
        links_data = []
        raw_links = entry.get("Links")
        if isinstance(raw_links, list):
            for item in raw_links:
                if isinstance(item, dict):
                    target = str(item.get("target") or item.get("Scene") or item.get("Next") or "").strip()
                    if not target:
                        continue
                    text = str(item.get("text") or target).strip()
                    links_data.append({"target": target, "text": text})
                elif isinstance(item, str):
                    target = item.strip()
                    if target:
                        links_data.append({"target": target, "text": target})
        if not links_data:
            for target in next_refs:
                if target:
                    links_data.append({"target": target, "text": target})
        deduped = []
        seen = set()
        for link in links_data:
            target = link["target"]
            text = link.get("text") or target
            key = (target.lower(), text.lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append({"target": target, "text": text})
        summary_fragments = []
        seen_fragments = set()

        def _register_fragment(value):
            if value is None:
                return
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    _register_fragment(item)
                return
            if isinstance(value, dict):
                text_value = value.get("text")
                if text_value is not None:
                    _register_fragment(text_value)
                else:
                    for item in value.values():
                        _register_fragment(item)
                return
            fragment = coerce_text(value).strip()
            normalised = " ".join(fragment.split())
            if not normalised:
                return
            key = normalised.lower()
            if key in seen_fragments:
                return
            seen_fragments.add(key)
            summary_fragments.append(fragment)

        if isinstance(entry, dict):
            for key in (
                "Summary",
                "SceneSummary",
                "Text",
                "SceneText",
                "Description",
                "Body",
                "Details",
                "SceneDetails",
                "Notes",
                "Content",
                "Synopsis",
                "Overview",
            ):
                _register_fragment(entry.get(key))
        else:
            _register_fragment(entry)

        summary = "\n\n".join(fragment for fragment in summary_fragments if fragment)
        scene = {
            "Title": entry.get("Title") or entry.get("Name") or f"Scene {index + 1}",
            "Summary": coerce_text(summary),
            "SceneType": entry.get("SceneType") or entry.get("Type") or "",
            "NPCs": self._split_to_list(entry.get("NPCs")),
            "Creatures": self._split_to_list(entry.get("Creatures")),
            "Places": self._split_to_list(entry.get("Places")),
            "Maps": self._split_to_list(entry.get("Maps")),
            "NextScenes": [link["target"] for link in deduped],
            "LinkData": deduped,
        }
        extras = {
            key: copy.deepcopy(value)
            for key, value in entry.items()
            if key not in self.SCENE_KNOWN_FIELDS
        }
        if extras:
            scene["_extra_fields"] = extras
        return scene


class ScenarioInfoDialog(ctk.CTkToplevel):
    def __init__(self, master, *, title, summary, secrets):
        super().__init__(master)
        window_title = title or "Scenario Notes"
        self.title(window_title)
        self.geometry("720x540")
        self.minsize(640, 480)
        self.transient(master)
        self.grab_set()
        self.result = None

        container = ctk.CTkFrame(self, fg_color="#101827", corner_radius=16)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)
        container.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            container,
            text="Scenario Overview",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 8))

        self.summary_text = ctk.CTkTextbox(container, height=140, wrap="word")
        self.summary_text.grid(row=1, column=0, sticky="nsew", padx=18)
        self.summary_text.insert("1.0", summary or "")

        ctk.CTkLabel(
            container,
            text="Secrets",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=2, column=0, sticky="w", padx=18, pady=(18, 8))

        self.secrets_text = ctk.CTkTextbox(container, height=140, wrap="word")
        self.secrets_text.grid(row=3, column=0, sticky="nsew", padx=18)
        self.secrets_text.insert("1.0", secrets or "")

        button_row = ctk.CTkFrame(container, fg_color="transparent")
        button_row.grid(row=4, column=0, sticky="ew", padx=18, pady=(18, 12))
        button_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(button_row, text="Cancel", command=self._on_cancel).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ctk.CTkButton(button_row, text="Save Notes", command=self._on_save).grid(
            row=0, column=1, sticky="ew"
        )

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.summary_text.focus_set()

    def _on_save(self):
        self.result = {
            "summary": self.summary_text.get("1.0", "end").strip(),
            "secrets": self.secrets_text.get("1.0", "end").strip(),
        }
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


class InlineSceneEditor(ctk.CTkFrame):
    def __init__(self, master, scene, *, scene_types, on_save, on_cancel, width=None, height=None):
        super().__init__(
            master,
            fg_color="#0f172a",
            corner_radius=12,
            width=width,
            height=height,
        )
        self.on_save = on_save
        self.on_cancel = on_cancel
        self._scene_types = [
            value for value in (scene_types or []) if isinstance(value, str)
        ]

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self,
            text="Scene Details",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        self.title_var = ctk.StringVar(value=scene.get("Title", ""))
        self.title_entry = ctk.CTkEntry(self, textvariable=self.title_var)
        self.title_entry.grid(row=1, column=0, sticky="ew", padx=12)

        type_values = [""]
        for value in self._scene_types:
            if value not in type_values:
                type_values.append(value)
        current_type = scene.get("SceneType") or scene.get("Type") or ""
        if current_type and current_type not in type_values:
            type_values.append(current_type)
        self.type_var = ctk.StringVar(
            value=current_type if current_type in type_values else type_values[0]
        )
        self.type_menu = ctk.CTkOptionMenu(self, values=type_values or [""], variable=self.type_var)
        self.type_menu.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 6))

        self.summary_text = ctk.CTkTextbox(self, wrap="word")
        self.summary_text.grid(row=3, column=0, sticky="nsew", padx=12)
        self.summary_text.insert("1.0", scene.get("Summary") or scene.get("Text") or "")

        ctk.CTkLabel(
            self,
            text="Ctrl+Enter to save, Esc to cancel",
            text_color="#9db4d1",
            anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=12, pady=(6, 0))

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.grid(row=5, column=0, sticky="ew", padx=12, pady=(8, 10))
        button_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(button_row, text="Cancel", command=self._on_cancel).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkButton(button_row, text="Save", command=self._on_save).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        self.title_entry.bind("<Control-Return>", self._on_save)
        self.title_entry.bind("<Escape>", self._on_cancel)
        self.summary_text.bind("<Control-Return>", self._on_save)
        self.summary_text.bind("<Escape>", self._on_cancel)
        self.type_menu.bind("<Escape>", self._on_cancel)

        self.summary_text.focus_set()

    def _on_save(self, _event=None):
        data = {
            "Title": self.title_var.get().strip(),
            "SceneType": self.type_var.get().strip(),
            "Summary": self.summary_text.get("1.0", "end").strip(),
        }
        if callable(self.on_save):
            self.on_save(data)

    def _on_cancel(self, _event=None):
        if callable(self.on_cancel):
            self.on_cancel()


class EntityLinkingStep(WizardStep):
    CARD_IMAGE_SIZE = (64, 64)
    CARD_BG = ("#162338", "#0f172a")
    CARD_SELECTED_BG = ("#20324d", "#1e293b")
    CARD_BORDER = "#2a3d5a"
    CARD_SELECTED_BORDER = "#60a5fa"
    CARD_TEXT_COLOR = ("#e2e8f0", "#e2e8f0")
    CARD_SUBTEXT_COLOR = ("#94a3b8", "#94a3b8")
    ENTITY_FIELDS = {
        "npcs": ("NPCs", "NPC"),
        "places": ("Places", "Place"),
        "factions": ("Factions", "Faction"),
        "creatures": ("Creatures", "Creature"),
        "objects": ("Objects", "Item"),
        "maps": ("Maps", "Map"),
    }

    def __init__(self, master, wrappers):
        super().__init__(master)
        self.wrappers = wrappers
        self.selected = {field: [] for field, _ in self.ENTITY_FIELDS.values()}
        self.card_containers = {}
        self.card_widgets = {}
        self.card_image_refs = {}
        self.card_selection = {field: set() for field, _ in self.ENTITY_FIELDS.values()}
        self.field_to_entity = {}
        self.field_labels = {}
        self._entity_cache = {}
        self._media_fields = {}

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        default_icon = os.path.join(project_root, "assets", "icons", "empty.png")
        self._default_icon_path = default_icon if os.path.exists(default_icon) else None

        entity_defs = load_entity_definitions()
        self._entity_icons = {}
        for entity_type in self.ENTITY_FIELDS:
            icon_path = None
            meta = entity_defs.get(entity_type)
            if meta:
                icon_path = meta.get("icon")
            if icon_path and os.path.exists(icon_path):
                self._entity_icons[entity_type] = icon_path
            elif self._default_icon_path:
                self._entity_icons[entity_type] = self._default_icon_path
            else:
                self._entity_icons[entity_type] = None
            self._media_fields[entity_type] = self._detect_media_field(entity_type)

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

            cards = ctk.CTkScrollableFrame(frame, fg_color="transparent")
            cards.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
            cards.grid_columnconfigure(0, weight=1)
            self.card_containers[field] = cards
            self.card_widgets[field] = {}
            self.card_image_refs[field] = []
            self.field_to_entity[field] = entity_type
            self.field_labels[field] = label
            self.refresh_list(field)

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

    def _detect_media_field(self, entity_type):
        try:
            template = load_template(entity_type)
        except Exception:
            return None
        fields = template.get("fields") if isinstance(template, dict) else None
        if not isinstance(fields, list):
            return None
        normalized = {}
        for field in fields:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "").strip()
            if not name:
                continue
            normalized[name.lower()] = name
            field_type = str(field.get("type") or "").strip().lower()
            if field_type == "image":
                return name
        for key in ("portrait", "image"):
            if key in normalized:
                return normalized[key]
        for lower, original in normalized.items():
            if "portrait" in lower or "image" in lower:
                return original
        return None

    def _invalidate_entity_cache(self, entity_type):
        self._entity_cache.pop(entity_type, None)

    def _get_entity_record(self, entity_type, name):
        if not name:
            return None
        cache = self._entity_cache.get(entity_type)
        if cache is None:
            cache = {"exact": {}, "lower": {}}
            wrapper = self.wrappers.get(entity_type)
            if not wrapper:
                self._entity_cache[entity_type] = cache
                return None
            try:
                items = wrapper.load_items()
            except Exception:
                self._entity_cache[entity_type] = cache
                return None
            for item in items:
                if not isinstance(item, dict):
                    continue
                value = item.get("Name") or item.get("Title")
                if not value:
                    continue
                text = str(value).strip()
                if not text:
                    continue
                cache["exact"][text] = item
                cache["lower"][text.lower()] = item
            self._entity_cache[entity_type] = cache
        record = cache["exact"].get(name)
        if record:
            return record
        return cache["lower"].get(name.lower())

    def _resolve_portrait_path(self, raw_value):
        if not raw_value:
            return None
        text = str(raw_value).strip()
        if not text:
            return None
        normalized = text.replace("\\", os.sep).replace("/", os.sep)
        if os.path.isabs(normalized) and os.path.exists(normalized):
            return normalized
        candidates = []
        campaign_dir = ConfigHelper.get_campaign_dir()
        if campaign_dir:
            candidates.append(os.path.join(campaign_dir, normalized))
            candidates.append(os.path.join(campaign_dir, "assets", normalized))
            base_name = os.path.basename(normalized)
            if base_name:
                candidates.append(os.path.join(campaign_dir, "assets", "portraits", base_name))
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    def _create_card_image(self, entity_type, portrait_value):
        resolved = self._resolve_portrait_path(portrait_value)
        image_obj = None
        if resolved:
            try:
                with Image.open(resolved) as img:
                    image_obj = img.convert("RGBA")
            except Exception:
                image_obj = None
        if image_obj is None:
            fallback_path = self._entity_icons.get(entity_type) or self._default_icon_path
            if fallback_path and os.path.exists(fallback_path):
                try:
                    with Image.open(fallback_path) as img:
                        image_obj = img.convert("RGBA")
                except Exception:
                    image_obj = None
        if image_obj is None:
            image_obj = Image.new("RGBA", self.CARD_IMAGE_SIZE, color="#1f2937")
        else:
            image_obj.thumbnail(self.CARD_IMAGE_SIZE, _IMAGE_RESAMPLE)
        return ctk.CTkImage(light_image=image_obj, size=self.CARD_IMAGE_SIZE)

    def _apply_card_selection_style(self, card, selected):
        card.configure(
            fg_color=self.CARD_SELECTED_BG if selected else self.CARD_BG,
            border_color=self.CARD_SELECTED_BORDER if selected else self.CARD_BORDER,
            border_width=2 if selected else 1,
        )

    def _toggle_card_selection(self, field, name):
        cards = self.card_widgets.get(field, {})
        card = cards.get(name)
        if not card:
            return
        selected_names = self.card_selection.setdefault(field, set())
        if name in selected_names:
            selected_names.remove(name)
            self._apply_card_selection_style(card, False)
        else:
            selected_names.add(name)
            self._apply_card_selection_style(card, True)

    def _create_entity_card(self, field, name):
        entity_type = self.field_to_entity.get(field)
        record = self._get_entity_record(entity_type, name) if entity_type else None
        portrait_field = self._media_fields.get(entity_type) if entity_type else None
        portrait_value = None
        if record and portrait_field:
            portrait_value = record.get(portrait_field)
        elif record:
            for key in ("Portrait", "portrait", "Image", "image"):
                if key in record and record.get(key):
                    portrait_value = record.get(key)
                    break
        if record is None:
            display_path = "Entity not found in database"
        else:
            display_path = str(portrait_value).strip() if portrait_value else "No portrait assigned"
        image = self._create_card_image(entity_type, portrait_value)

        container = self.card_containers[field]
        card = ctk.CTkFrame(
            container,
            corner_radius=12,
            fg_color=self.CARD_BG,
            border_color=self.CARD_BORDER,
            border_width=1,
        )
        card.grid_columnconfigure(1, weight=1)

        image_label = ctk.CTkLabel(card, text="", image=image)
        image_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)

        name_label = ctk.CTkLabel(
            card,
            text=name or "(Unnamed)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.CARD_TEXT_COLOR,
            anchor="w",
        )
        name_label.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(10, 2))

        path_label = ctk.CTkLabel(
            card,
            text=display_path or "No portrait assigned",
            font=ctk.CTkFont(size=11),
            text_color=self.CARD_SUBTEXT_COLOR,
            anchor="w",
            justify="left",
            wraplength=220,
        )
        path_label.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 10))

        for widget in (card, image_label, name_label, path_label):
            widget.bind("<Button-1>", lambda _event, f=field, n=name: self._toggle_card_selection(f, n))

        self.card_widgets[field][name] = card
        self.card_image_refs[field].append(image)
        self._apply_card_selection_style(card, name in self.card_selection.get(field, set()))
        return card

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
        selected_cards = set(self.card_selection.get(field) or set())
        if not selected_cards:
            return
        current = self.selected.get(field, [])
        self.selected[field] = [name for name in current if name not in selected_cards]
        self.card_selection[field] = set()
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
        self._invalidate_entity_cache(entity_type)

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
        container = self.card_containers.get(field)
        if not container:
            return
        for child in container.winfo_children():
            child.destroy()
        self.card_widgets[field] = {}
        self.card_image_refs[field] = []
        values = self.selected.get(field, [])
        if not isinstance(values, list):
            values = list(values)
        deduped = []
        seen = set()
        for name in values:
            if name in seen:
                continue
            seen.add(name)
            deduped.append(name)
        self.selected[field] = deduped
        selection = self.card_selection.setdefault(field, set())
        selection.intersection_update(set(deduped))
        if not deduped:
            label = self.field_labels.get(field, field)
            empty_text = f"No {label.lower()}s linked yet."
            ctk.CTkLabel(
                container,
                text=empty_text,
                text_color=self.CARD_SUBTEXT_COLOR,
                anchor="w",
                justify="left",
            ).grid(row=0, column=0, sticky="w", padx=6, pady=6)
            return
        for idx, name in enumerate(deduped):
            card = self._create_entity_card(field, name)
            card.grid(row=idx, column=0, sticky="ew", padx=4, pady=4)

        container.grid_columnconfigure(0, weight=1)

    def load_state(self, state):  # pragma: no cover - UI synchronization
        for entity_type, (field, _) in self.ENTITY_FIELDS.items():
            values = state.get(field) or []
            if isinstance(values, str):
                values = [values]
            self.selected[field] = list(dict.fromkeys(values))
            self.card_selection[field] = set()
            self.refresh_list(field)

    def save_state(self, state):  # pragma: no cover - UI synchronization
        for _, (field, _) in self.ENTITY_FIELDS.items():
            state[field] = list(dict.fromkeys(self.selected.get(field, [])))
        return True


class CharacterRelationsStep(WizardStep):
    def __init__(self, master, npc_wrapper, pc_wrapper, faction_wrapper):
        super().__init__(master)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._state_ref = None

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Character Relationships",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            header,
            text=(
                "Drop NPCs and PCs onto the board, create links between them, "
                "and right-click nodes or links to delete."
            ),
            text_color="#9db4d1",
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        self.sync_to_global_var = ctk.BooleanVar(value=False)
        self.sync_switch = ctk.CTkSwitch(
            header,
            text="Sync to global character graph",
            variable=self.sync_to_global_var,
        )
        self.sync_switch.grid(row=0, column=1, padx=12, pady=(10, 0), sticky="e")

        self.sync_hint = ctk.CTkLabel(
            header,
            text="Disable to keep this graph only inside the scenario.",
            text_color="#9db4d1",
            anchor="e",
        )
        self.sync_hint.grid(row=1, column=1, padx=12, pady=(0, 10), sticky="e")

        self.graph_editor = ScenarioCharacterGraphEditor(
            self,
            npc_wrapper=npc_wrapper,
            pc_wrapper=pc_wrapper,
            faction_wrapper=faction_wrapper,
            on_entity_added=self._on_entity_added,
        )
        self.graph_editor.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))

    def set_state_binding(self, state, on_state_change=None):
        self._state_ref = state
        self._on_state_change = on_state_change

    def _on_entity_added(self, entity_type, entity_name):
        if not self._state_ref or not entity_name:
            return
        if entity_type == "npc":
            field = "NPCs"
        elif entity_type == "pc":
            field = "PCs"
        else:
            return
        values = list(self._state_ref.get(field) or [])
        if entity_name not in values:
            values.append(entity_name)
            self._state_ref[field] = values
            if callable(self._on_state_change):
                self._on_state_change(source=self)

    def load_state(self, state):  # pragma: no cover - UI synchronization
        self.sync_to_global_var.set(bool(state.get("ScenarioCharacterGraphSync")))
        graph_data = state.get("ScenarioCharacterGraph") or {}
        self.graph_editor.load_graph_data(graph_data)

    def save_state(self, state):  # pragma: no cover - UI synchronization
        graph_data = self.graph_editor.export_graph_data()
        state["ScenarioCharacterGraph"] = graph_data
        npc_names = []
        pc_names = []
        for node in graph_data.get("nodes", []):
            if not isinstance(node, dict):
                continue
            entity_type = node.get("entity_type")
            entity_name = node.get("entity_name") or node.get("npc_name") or node.get("pc_name")
            if not entity_name:
                continue
            if entity_type == "npc":
                npc_names.append(entity_name)
            elif entity_type == "pc":
                pc_names.append(entity_name)
        if npc_names:
            state["NPCs"] = list(dict.fromkeys((state.get("NPCs") or []) + npc_names))
        if pc_names:
            state["PCs"] = list(dict.fromkeys((state.get("PCs") or []) + pc_names))
        state["ScenarioCharacterGraphSync"] = bool(self.sync_to_global_var.get())
        return True


class ReviewStep(WizardStep):
    def __init__(self, master):
        super().__init__(master)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)

        preview_section = ctk.CTkFrame(self)
        preview_section.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)
        preview_section.grid_rowconfigure(0, weight=0)
        preview_section.grid_rowconfigure(1, weight=1)
        preview_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            preview_section,
            text="Scene Flow",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 4))

        self.flow_preview = SceneFlowPreview(preview_section)
        self.flow_preview.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        facts_panel = ctk.CTkFrame(self)
        facts_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=20)
        facts_panel.grid_columnconfigure(0, weight=1)
        facts_panel.grid_rowconfigure(5, weight=1)

        self.title_label = ctk.CTkLabel(
            facts_panel,
            text="",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
            wraplength=360,
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))

        self.summary_label = ctk.CTkLabel(
            facts_panel,
            text="",
            anchor="w",
            justify="left",
            wraplength=360,
        )
        self.summary_label.grid(row=1, column=0, sticky="ew", padx=16)

        self.secrets_label = ctk.CTkLabel(
            facts_panel,
            text="",
            anchor="w",
            justify="left",
            wraplength=360,
            text_color=("#b9c6dd", "#b9c6dd"),
        )
        self.secrets_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 0))

        self.stats_label = ctk.CTkLabel(
            facts_panel,
            text="",
            anchor="w",
            justify="left",
            wraplength=360,
            text_color=("#7f90ac", "#7f90ac"),
        )
        self.stats_label.grid(row=3, column=0, sticky="ew", padx=16, pady=(10, 8))

        self.details_header = ctk.CTkLabel(
            facts_panel,
            text="Details",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        self.details_header.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 2))

        self.details_text = ctk.CTkTextbox(
            facts_panel,
            height=260,
            state="disabled",
            wrap="word",
        )
        self.details_text.grid(row=5, column=0, sticky="nsew", padx=16, pady=(0, 16))

    def load_state(self, state):  # pragma: no cover - UI synchronization
        title = state.get("Title", "Untitled Scenario")
        summary = state.get("Summary") or "(No summary provided.)"
        secrets = state.get("Secrets") or "(No secrets provided.)"

        summary_preview = textwrap.shorten(summary, width=160, placeholder="…")
        secrets_preview = textwrap.shorten(secrets, width=160, placeholder="…")

        self.title_label.configure(text=title)
        self.summary_label.configure(text=f"Summary: {summary_preview}")
        self.secrets_label.configure(text=f"Secrets: {secrets_preview}")

        scenes = copy.deepcopy(state.get("Scenes") or [])
        for scene in scenes:
            if isinstance(scene, dict):
                normalise_scene_links(scene, ScenesPlanningStep._split_to_list)
        self.flow_preview.render(scenes, selected_index=None)

        scene_count = len(scenes)
        entity_counts = []
        for field, label in (
            ("NPCs", "NPCs"),
            ("Creatures", "Creatures"),
            ("Places", "Places"),
            ("Maps", "Maps"),
            ("Factions", "Factions"),
            ("Objects", "Objects"),
        ):
            entries = state.get(field) or []
            if entries:
                entity_counts.append(f"{len(entries)} {label}")
        stats_text = " • ".join(entity_counts)
        stats_prefix = f"{scene_count} scene{'s' if scene_count != 1 else ''}"
        self.stats_label.configure(
            text=f"{stats_prefix}{f' • {stats_text}' if stats_text else ''}"
        )

        summary_lines = [
            f"Title: {title}",
            "",
            "Summary:",
            summary,
            "",
            "Secrets:",
            secrets,
            "",
            "Scenes:",
        ]

        if scenes:
            for idx, scene in enumerate(scenes, start=1):
                title_value = ""
                if isinstance(scene, dict):
                    title_value = scene.get("Title") or scene.get("title") or ""
                if title_value:
                    summary_lines.append(f"  {idx}. {title_value}")
                else:
                    summary_lines.append(f"  {idx}. Scene {idx}")
        else:
            summary_lines.append("  (No scenes planned.)")

        for field in ("NPCs", "Creatures", "Places", "Maps", "Factions", "Objects"):
            entries = state.get(field) or []
            summary_lines.append("")
            summary_lines.append(f"{field}:")
            if entries:
                for name in entries:
                    summary_lines.append(f"  - {name}")
            else:
                summary_lines.append("  (None)")

        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", "\n".join(summary_lines))
        self.details_text.configure(state="disabled")


class ScenarioBuilderWizard(ctk.CTkToplevel):
    """Interactive wizard guiding users through building a scenario."""

    def __init__(self, master, on_saved=None, *, initial_scenario=None):
        super().__init__(master)
        self.title("Scenario Builder Wizard")
        self.geometry("1920x1080+0+0")
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
            "PCs": [],
            "Creatures": [],
            "Places": [],
            "Maps": [],
            "Factions": [],
            "Objects": [],
            "ScenarioCharacterGraph": {"nodes": [], "links": []},
            "ScenarioCharacterGraphSync": False,
        }

        self.scenario_wrapper = GenericModelWrapper("scenarios")
        self.npc_wrapper = GenericModelWrapper("npcs")
        self.pc_wrapper = GenericModelWrapper("pcs")
        self.creature_wrapper = GenericModelWrapper("creatures")
        self.place_wrapper = GenericModelWrapper("places")
        self.map_wrapper = GenericModelWrapper("maps")
        self.faction_wrapper = GenericModelWrapper("factions")
        self.object_wrapper = GenericModelWrapper("objects")

        self._build_layout()
        self._create_steps()
        if initial_scenario:
            try:
                self.load_existing_scenario(initial_scenario)
            except Exception:
                log_exception(
                    "Failed to load initial scenario into wizard.",
                    func_name="ScenarioBuilderWizard.__init__",
                )
        self.current_step_index = 0
        self._show_step(0)

        self._destroy_scheduled = False

    def _schedule_safe_destroy(self):  # pragma: no cover - UI teardown
        """Withdraw the window and destroy it once Tk has processed focus."""

        if getattr(self, "_destroy_scheduled", False):
            return

        self._destroy_scheduled = True

        try:
            if self.winfo_exists():
                self.withdraw()
        except Exception:
            pass

        def _finalize():
            try:
                super(ScenarioBuilderWizard, self).destroy()
            except Exception:
                pass

        try:
            self.after(150, _finalize)
        except Exception:
            _finalize()

    def destroy(self):  # pragma: no cover - UI teardown
        self._schedule_safe_destroy()

    def focus_set(self):  # pragma: no cover - UI focus handling
        """Safely set focus on the wizard if it still exists."""

        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            super().focus_set()
        except tk.TclError:
            pass

    def focus_force(self):  # pragma: no cover - UI focus handling
        """Safely force focus on the wizard if it still exists."""

        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            super().focus_force()
        except tk.TclError:
            pass

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
            "maps": self.map_wrapper,
        }

        planning_step = ScenesPlanningStep(
            self.step_container,
            {
                key: wrapper
                for key, wrapper in entity_wrappers.items()
                if key in ("npcs", "creatures", "places", "maps")
            },
            scenario_wrapper=self.scenario_wrapper,
            finale_planner_callback=self._launch_epic_finale_planner,
        )

        self.steps = [
            ("Visual Builder", planning_step),
            (
                "Character Relations",
                CharacterRelationsStep(
                    self.step_container,
                    npc_wrapper=self.npc_wrapper,
                    pc_wrapper=self.pc_wrapper,
                    faction_wrapper=self.faction_wrapper,
                ),
            ),
            ("Entity Linking", EntityLinkingStep(self.step_container, entity_wrappers)),
            ("Review", ReviewStep(self.step_container)),
        ]

        for _, frame in self.steps:
            frame.grid(row=0, column=0, sticky="nsew")

        for _, frame in self.steps:
            if hasattr(frame, "set_state_binding"):
                frame.set_state_binding(self.wizard_state, self._on_wizard_state_changed)

    def _launch_epic_finale_planner(self, state):  # pragma: no cover - UI interaction
        try:
            from modules.scenarios.epic_finale_planner import EpicFinalePlannerWizard
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(
                f"Failed to import Epic Finale Planner: {exc}",
                func_name="ScenarioBuilderWizard._launch_epic_finale_planner",
            )
            messagebox.showerror(
                "Error",
                "The Epic Finale Planner could not be loaded.",
            )
            return

        payload = copy.deepcopy(state or {})
        try:
            wizard = EpicFinalePlannerWizard(
                self.master,
                on_saved=self.on_saved,
                initial_scenario=payload,
            )
            wizard.grab_set()
            wizard.focus_force()
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(
                f"Failed to open Epic Finale Planner: {exc}",
                func_name="ScenarioBuilderWizard._launch_epic_finale_planner",
            )
            messagebox.showerror(
                "Error",
                "Unable to open the Epic Finale Planner window.",
            )
            return

        # Hide the wizard immediately to avoid any focus flicker, then
        # destroy it shortly after the new planner has taken over. This
        # prevents pending Tk focus callbacks from targeting a widget that
        # has already been destroyed (which raised TclError in practice).
        try:
            self.withdraw()
        except Exception:
            pass

        def _close_original_wizard():
            try:
                if not self.winfo_exists():
                    return
            except Exception:
                return
            self._schedule_safe_destroy()

        # Use ``after`` to ensure the destroy happens once focus hand-off has
        # completed within Tk's event loop.
        try:
            self.after(120, _close_original_wizard)
        except Exception:
            _close_original_wizard()

    def _show_step(self, index):  # pragma: no cover - UI navigation
        title, frame = self.steps[index]
        self.header_label.configure(text=f"Step {index + 1} of {len(self.steps)}: {title}")
        frame.tkraise()
        frame.load_state(self.wizard_state)
        self._update_navigation_buttons()

    def _on_wizard_state_changed(self, source=None):  # pragma: no cover - UI synchronization
        for _, frame in self.steps:
            if frame is source:
                continue
            try:
                frame.load_state(self.wizard_state)
            except Exception:
                pass

    def load_existing_scenario(self, scenario):  # pragma: no cover - UI interaction
        planning_step = next(
            (frame for _, frame in self.steps if isinstance(frame, ScenesPlanningStep)),
            None,
        )
        if planning_step is None:
            return

        scenario_payload = None
        if isinstance(scenario, str):
            try:
                items = self.scenario_wrapper.load_items()
            except Exception as exc:
                log_exception(
                    f"Failed to load scenarios for editing: {exc}",
                    func_name="ScenarioBuilderWizard.load_existing_scenario",
                )
                messagebox.showerror("Load Error", "Unable to load scenarios from the database.")
                return
            for entry in items or []:
                title = entry.get("Title") or entry.get("Name")
                if title == scenario:
                    scenario_payload = entry
                    break
            if scenario_payload is None:
                messagebox.showerror("Not Found", f"Scenario '{scenario}' was not found.")
                return
        elif isinstance(scenario, dict):
            scenario_payload = scenario
        else:
            return

        planning_step.load_from_payload(copy.deepcopy(scenario_payload))
        self.current_step_index = 0
        self._show_step(self.current_step_index)

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
            "PCs": list(dict.fromkeys(self.wizard_state.get("PCs", []))),
            "Creatures": list(dict.fromkeys(self.wizard_state.get("Creatures", []))),
            "Maps": list(dict.fromkeys(self.wizard_state.get("Maps", []))),
            "Factions": list(dict.fromkeys(self.wizard_state.get("Factions", []))),
            "Objects": list(dict.fromkeys(self.wizard_state.get("Objects", []))),
            "ScenarioCharacterGraph": self.wizard_state.get("ScenarioCharacterGraph", {}),
        }
        sync_graph = bool(self.wizard_state.get("ScenarioCharacterGraphSync"))

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
            if sync_graph:
                try:
                    sync_scenario_graph_to_global(
                        self.wizard_state.get("ScenarioCharacterGraph") or {}
                    )
                except Exception as exc:  # pragma: no cover - defensive path
                    log_exception(
                        f"Failed to sync scenario character graph: {exc}",
                        func_name="ScenarioBuilderWizard.finish",
                    )
                    messagebox.showwarning(
                        "Character Graph Sync Failed",
                        "The scenario was saved, but the global character graph could not be updated.",
                    )
        finally:
            for btn, previous_state in buttons.items():
                btn.configure(state=previous_state)
        self.destroy()
