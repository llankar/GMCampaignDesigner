"""Wizard flow for scenario builder."""
import copy
import json
import os
import sqlite3
import threading
import textwrap
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from modules.ai.story_forge.contracts import StoryForgeRequest, StoryForgeResponse
from modules.ai.story_forge.entity_catalog import load_campaign_arc_context, load_db_entity_catalog
from modules.ai.story_forge.orchestrator import StoryForgeOrchestrator
from modules.ai.story_forge.persistence_payloads import build_embedded_result_payload
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import, log_info, log_exception
from modules.helpers.template_loader import load_template, load_entity_definitions
from modules.helpers.text_helpers import coerce_text
from modules.scenarios.scene_flow_components import (
    SceneFlowPreview,
)
from modules.scenarios.scenario_character_graph import (
    ScenarioCharacterGraphEditor,
    build_scenario_graph_with_links,
    sync_scenario_graph_to_global,
)
from modules.scenarios.wizard_steps.scenes.canvas_scene_planner import CanvasScenePlanner
from modules.scenarios.wizard_steps.scenes.guided_scene_planner import GuidedScenePlanner
from modules.scenarios.wizard_steps.scenes.scene_entity_fields import (
    SCENE_ENTITY_FIELDS as SCENE_CARD_ENTITY_FIELDS,
    normalise_entity_list,
)
from modules.scenarios.wizard_steps.scenes.scene_entity_aggregator import (
    collect_scene_entity_names,
)
from modules.scenarios.wizard_steps.scenes.scene_mode_adapters import (
    canonicalise_scene,
    guided_cards_to_scenes,
    normalise_scene_links,
    scenes_to_guided_cards,
)

try:
    _IMAGE_RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - Pillow < 9.1
    _IMAGE_RESAMPLE = Image.LANCZOS


log_module_import(__name__)


SCENARIO_ENTITY_SINGULAR_LABELS = {
    "Bases": "Base",
    "Books": "Book",
    "Creatures": "Creature",
    "Events": "Event",
    "Factions": "Faction",
    "Maps": "Map",
    "NPCs": "NPC",
    "Objects": "Item",
    "PCs": "PC",
    "Places": "Place",
    "Villains": "Villain",
}

LEGACY_SCENARIO_ENTITY_FIELD_NAMES = {
    "npcs": "NPCs",
    "pcs": "PCs",
    "villains": "Villains",
    "creatures": "Creatures",
    "bases": "Bases",
    "places": "Places",
    "maps": "Maps",
    "events": "Events",
    "factions": "Factions",
    "objects": "Objects",
    "books": "Books",
}

SCENARIO_ENTITY_TYPE_ORDER = (
    "npcs",
    "pcs",
    "villains",
    "creatures",
    "bases",
    "places",
    "maps",
    "events",
    "factions",
    "objects",
    "books",
)


def _derive_scenario_entity_singular_label(field_name):
    """Internal helper for derive scenario entity singular label."""
    override = SCENARIO_ENTITY_SINGULAR_LABELS.get(field_name)
    if override:
        return override
    if field_name.endswith("ies") and len(field_name) > 3:
        return field_name[:-3] + "y"
    if field_name.endswith("s") and len(field_name) > 1:
        return field_name[:-1]
    return field_name


def _build_scenario_entity_fields():
    """Build scenario entity fields."""
    field_names = {}
    try:
        template = load_template("scenarios")
    except Exception:
        template = {}

    for field in template.get("fields") or []:
        # Process each field from template.get('fields') or [].
        if not isinstance(field, dict):
            continue
        field_name = str(field.get("name") or "").strip()
        field_type = str(field.get("type") or "").strip().lower()
        linked_type = str(field.get("linked_type") or "").strip()
        if not field_name or field_name == "Scenes" or field_type != "list" or not linked_type:
            continue
        field_names[linked_type.lower()] = field_name

    for entity_type, field_name in LEGACY_SCENARIO_ENTITY_FIELD_NAMES.items():
        field_names.setdefault(entity_type, field_name)

    ordered = {}
    for entity_type in SCENARIO_ENTITY_TYPE_ORDER:
        # Process each entity_type from SCENARIO_ENTITY_TYPE_ORDER.
        field_name = field_names.pop(entity_type, None)
        if not field_name:
            continue
        ordered[entity_type] = (
            field_name,
            _derive_scenario_entity_singular_label(field_name),
        )

    for entity_type, field_name in field_names.items():
        ordered[entity_type] = (
            field_name,
            _derive_scenario_entity_singular_label(field_name),
        )
    return ordered


SCENARIO_ENTITY_FIELDS = _build_scenario_entity_fields()
SCENARIO_ENTITY_FIELD_NAMES = tuple(
    field_name for field_name, _ in SCENARIO_ENTITY_FIELDS.values()
)


class WizardStep(ctk.CTkFrame):
    """Base class for wizard steps with state synchronization hooks."""

    def load_state(self, state):  # pragma: no cover - UI synchronization
        """Populate widgets using the shared wizard ``state``."""

    def save_state(self, state):  # pragma: no cover - UI synchronization
        """Persist widget values into the shared wizard ``state``."""
        return True


class BasicInfoStep(WizardStep):
    def __init__(self, master):
        """Initialize the BasicInfoStep instance."""
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
        """Load state."""
        self.title_var.set(state.get("Title", ""))
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", state.get("Summary", ""))
        secret_val = state.get("Secrets") or state.get("Secret") or ""
        self.secret_text.delete("1.0", "end")
        self.secret_text.insert("1.0", secret_val)

    def save_state(self, state):  # pragma: no cover - UI synchronization
        """Save state."""
        state["Title"] = self.title_var.get().strip()
        state["Summary"] = self.summary_text.get("1.0", "end").strip()
        secrets = self.secret_text.get("1.0", "end").strip()
        state["Secrets"] = secrets
        state["Secret"] = secrets  # ScenarioGraphEditor expects the singular key
        if "Scenes" not in state or state["Scenes"] is None:
            state["Scenes"] = []
        return True



class ScenesPlanningStep(WizardStep):
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
        "Bases",
        "Places",
        "Maps",
        "Factions",
        "Objects",
    }

    def __init__(self, master, entity_wrappers, *, scenario_wrapper=None, finale_planner_callback=None):
        """Initialize the ScenesPlanningStep instance."""
        super().__init__(master)
        self.entity_wrappers = entity_wrappers or {}
        self.scenario_wrapper = scenario_wrapper
        self._state_ref = None
        self._on_state_change = None
        self._finale_planner_callback = finale_planner_callback
        self._scenario_summary = ""
        self._scenario_secrets = ""
        self._root_extra_fields = {}
        self.scenario_title_var = ctk.StringVar()
        self.mode_var = ctk.StringVar(value="guided")

        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True)
        root.grid_rowconfigure(2, weight=1)
        root.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(root, fg_color="#101827", corner_radius=14)
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(toolbar, text="Scenario Title", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        self.scenario_title_entry = ctk.CTkEntry(toolbar, textvariable=self.scenario_title_var, font=ctk.CTkFont(size=18, weight="bold"))
        self.scenario_title_entry.grid(row=1, column=0, sticky="ew", padx=16)

        btn_row = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_row.grid(row=1, column=1, padx=16, pady=(0, 12))
        self.load_scenario_btn = ctk.CTkButton(btn_row, text="Load Scenario", command=self._load_existing_scenario)
        self.load_scenario_btn.pack(side="left")
        if self._finale_planner_callback:
            self.finale_planner_btn = ctk.CTkButton(btn_row, text="Epic Finale Planner", command=self._switch_to_epic_finale_planner)
            self.finale_planner_btn.pack(side="left", padx=(6, 0))
        self.notes_btn = ctk.CTkButton(btn_row, text="Edit Notes", command=self._edit_scenario_info)
        self.notes_btn.pack(side="left", padx=(6, 0))

        mode_row = ctk.CTkFrame(root, fg_color="transparent")
        mode_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        ctk.CTkLabel(mode_row, text="Planning mode", text_color="#9db4d1").pack(side="left", padx=(2, 8))
        self.mode_switch = ctk.CTkSegmentedButton(mode_row, values=["guided", "canvas"], variable=self.mode_var, command=self._on_mode_changed)
        self.mode_switch.pack(side="left")

        self._planner_holder = ctk.CTkFrame(root, fg_color="transparent")
        self._planner_holder.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._planner_holder.grid_columnconfigure(0, weight=1)
        self._planner_holder.grid_rowconfigure(0, weight=1)

        self.guided_planner = GuidedScenePlanner(
            self._planner_holder,
            entity_selector_callbacks=self._build_entity_selector_callbacks(),
        )
        self.canvas_planner = CanvasScenePlanner(
            self._planner_holder,
            entity_selector_callbacks=self._build_entity_selector_callbacks(),
        )
        self._active_mode = None
        self.scenes = []
        self._set_mode("guided", remap=False)

    def _build_entity_selector_callbacks(self):
        """Build entity selector callbacks."""
        callbacks = {}
        for field_name in SCENE_CARD_ENTITY_FIELDS:
            # Process each field_name from SCENE_CARD_ENTITY_FIELDS.
            entity_type = field_name.lower()
            wrapper = self.entity_wrappers.get(entity_type)
            if not wrapper:
                continue
            callbacks[field_name] = (
                lambda current, f=field_name, et=entity_type: self._select_scene_entities(et, f, current)
            )
        return callbacks

    def _select_scene_entities(self, entity_type, field_name, current_values):  # pragma: no cover - UI interaction
        """Select scene entities."""
        wrapper = self.entity_wrappers.get(entity_type)
        if not wrapper:
            return normalise_entity_list(current_values)
        template = load_template(entity_type)
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Select {field_name}")
        dialog.geometry("1100x720")
        dialog.minsize(1100, 720)
        selected_values = list(normalise_entity_list(current_values))
        selected_lookup = {value.casefold() for value in selected_values}
        result = {"confirmed": False}

        status_var = ctk.StringVar()

        def _update_status():
            """Update status."""
            preview = ", ".join(selected_values[:6])
            if len(selected_values) > 6:
                preview = f"{preview}, +{len(selected_values) - 6} more"
            if preview:
                status_var.set(
                    f"Queued: {len(selected_values)} · {preview}\n"
                    "Double-click to queue, then Apply Queued Selection."
                )
            else:
                status_var.set("No entities queued yet. Double-click to queue, then Apply Queued Selection.")

        def _queue_selected_entity(_et, name, _item):
            """Internal helper for queue selected entity."""
            cleaned = str(name).strip()
            if not cleaned:
                return
            lookup_key = cleaned.casefold()
            if lookup_key in selected_lookup:
                return
            selected_lookup.add(lookup_key)
            selected_values.append(cleaned)
            _update_status()

        _update_status()

        selection = GenericListSelectionView(
            dialog,
            entity_type,
            wrapper,
            template,
            allow_multi_select=True,
            double_click_action="emit_selection",
            on_select_callback=_queue_selected_entity,
        )
        selection.pack(fill="both", expand=True)

        controls = ctk.CTkFrame(dialog)
        controls.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(
            controls,
            textvariable=status_var,
            justify="left",
            anchor="w",
            text_color="#9db4d1",
        ).pack(side="left", padx=(0, 12))
        ctk.CTkButton(
            controls,
            text="Cancel",
            command=dialog.destroy,
        ).pack(side="right")
        ctk.CTkButton(
            controls,
            text="Apply Queued Selection",
            command=lambda: (result.__setitem__("confirmed", True), dialog.destroy()),
        ).pack(side="right", padx=(0, 8))
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        self.wait_window(dialog)
        if not result["confirmed"]:
            return normalise_entity_list(current_values)
        return normalise_entity_list(selected_values)

    def set_state_binding(self, state, on_state_change=None):
        """Set state binding."""
        self._state_ref = state
        self._on_state_change = on_state_change

    def _on_mode_changed(self, value):
        """Handle mode changed."""
        self._set_mode(value, remap=True)

    def _set_mode(self, mode, *, remap):
        """Set mode."""
        mode = "canvas" if str(mode).strip().lower() == "canvas" else "guided"
        if self._active_mode == mode and remap:
            return
        current_scenes = self._collect_active_scenes() if remap else self.scenes
        if mode == "guided":
            self.guided_planner.grid(row=0, column=0, sticky="nsew")
            self.canvas_planner.grid_forget()
            cards = scenes_to_guided_cards(current_scenes)
            self.guided_planner.load_cards(cards)
            self.scenes = guided_cards_to_scenes(self.guided_planner.export_cards())
        else:
            self.canvas_planner.grid(row=0, column=0, sticky="nsew")
            self.guided_planner.grid_forget()
            scenes = guided_cards_to_scenes(self.guided_planner.export_cards()) if self._active_mode == "guided" and remap else current_scenes
            self.canvas_planner.load_scenes(scenes)
            self.scenes = self.canvas_planner.export_scenes()
        self._active_mode = mode
        self.mode_var.set(mode)

    def _collect_active_scenes(self):
        """Collect active scenes."""
        if self._active_mode == "guided":
            return guided_cards_to_scenes(self.guided_planner.export_cards())
        return self.canvas_planner.export_scenes()

    def _switch_to_epic_finale_planner(self):
        """Internal helper for switch to epic finale planner."""
        if not self._finale_planner_callback or self._state_ref is None:
            return
        if not self.save_state(self._state_ref):
            return
        payload = copy.deepcopy(self._state_ref)
        self._finale_planner_callback(payload)

    def _edit_scenario_info(self):
        """Internal helper for edit scenario info."""
        dialog = ScenarioInfoDialog(self.winfo_toplevel(), title=self.scenario_title_var.get().strip() or "Scenario Notes", summary=self._scenario_summary, secrets=self._scenario_secrets)
        self.wait_window(dialog)
        if dialog.result:
            self._scenario_summary = dialog.result.get("summary", "")
            self._scenario_secrets = dialog.result.get("secrets", "")

    def _load_existing_scenario(self):
        """Load existing scenario."""
        if not self.scenario_wrapper:
            messagebox.showerror("Unavailable", "No scenario library is available to load from.")
            return
        scenario_choice = self._choose_existing_scenario()
        if not scenario_choice:
            return
        if isinstance(scenario_choice, dict):
            self.load_from_payload(copy.deepcopy(scenario_choice))
            return
        scenario_name = str(scenario_choice).strip()
        if not scenario_name:
            return
        scenarios = self.scenario_wrapper.load_items()
        match = next((entry for entry in (scenarios or []) if str(entry.get("Title") or entry.get("Name") or "").strip().casefold() == scenario_name.casefold()), None)
        if not match:
            messagebox.showerror("Not Found", f"Scenario '{scenario_name}' was not found.")
            return
        self.load_from_payload(copy.deepcopy(match))

    def _choose_existing_scenario(self):
        """Internal helper for choose existing scenario."""
        template = load_template("scenarios")
        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Scenario")
        dialog.geometry("1100x720")
        dialog.minsize(1100, 720)
        result = {"name": None, "payload": None}
        view = GenericListSelectionView(dialog, "scenarios", self.scenario_wrapper, template, on_select_callback=lambda _et, name, item=None, win=dialog: (result.__setitem__("name", name), result.__setitem__("payload", copy.deepcopy(item) if isinstance(item, dict) else None), win.destroy()))
        view.pack(fill="both", expand=True)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        self.wait_window(dialog)
        return result["payload"] if result["payload"] is not None else result["name"]

    def load_from_payload(self, scenario):
        """Load from payload."""
        if not isinstance(scenario, dict):
            return
        self._apply_loaded_scenario(copy.deepcopy(scenario))

    def _apply_loaded_scenario(self, scenario):
        """Apply loaded scenario."""
        title = scenario.get("Title") or scenario.get("Name") or ""
        self.scenario_title_var.set(str(title))
        self._scenario_summary = coerce_text(scenario.get("Summary") or scenario.get("Text"))
        self._scenario_secrets = coerce_text(scenario.get("Secrets") or scenario.get("Secret"))
        scenes_payload = [canonicalise_scene(scene, index=i) for i, scene in enumerate(scenario.get("Scenes") or [])]
        layout = scenario.get("_SceneLayout")
        if isinstance(layout, list):
            for idx, scene in enumerate(scenes_payload):
                if idx < len(layout) and isinstance(layout[idx], dict):
                    scene.setdefault("_canvas", {}).update(layout[idx])
        self.scenes = scenes_payload
        self._set_mode("guided", remap=False)
        self.guided_planner.load_cards(scenes_to_guided_cards(self.scenes))

    def load_state(self, state):
        """Load state."""
        self.scenario_title_var.set(state.get("Title", ""))
        self._scenario_summary = state.get("Summary", "")
        self._scenario_secrets = state.get("Secrets") or state.get("Secret") or ""
        scenes = [canonicalise_scene(scene, index=i) for i, scene in enumerate(state.get("Scenes") or [])]
        layout = state.get("_SceneLayout")
        if isinstance(layout, list):
            for idx, scene in enumerate(scenes):
                if idx < len(layout) and isinstance(layout[idx], dict):
                    scene.setdefault("_canvas", {}).update(layout[idx])
        self.scenes = scenes
        self._root_extra_fields = {key: copy.deepcopy(value) for key, value in (state or {}).items() if key not in self.ROOT_KNOWN_FIELDS}
        self._set_mode("guided", remap=False)
        self.guided_planner.load_cards(scenes_to_guided_cards(self.scenes))

    def save_state(self, state):
        """Save state."""
        self.scenes = self._collect_active_scenes()
        state["Title"] = self.scenario_title_var.get().strip()
        state["Summary"] = (self._scenario_summary or "").strip()
        secrets = (self._scenario_secrets or "").strip()
        state["Secrets"] = secrets
        state["Secret"] = secrets

        payload = []
        layout = []
        for scene in self.scenes:
            # Process each scene from scenes.
            record = {
                "Title": scene.get("Title", "Scene"),
                "Summary": scene.get("Summary", ""),
                "Text": scene.get("Summary", ""),
            }
            scene_type = scene.get("SceneType", "")
            if scene_type:
                record["SceneType"] = scene_type
                record["Type"] = scene_type
            links = normalise_scene_links(scene)
            if links:
                record["NextScenes"] = [link["target"] for link in links]
                record["Links"] = [{"target": link["target"], "text": link.get("text") or link["target"]} for link in links]
            for field_name in SCENE_CARD_ENTITY_FIELDS:
                record[field_name] = normalise_entity_list(scene.get(field_name))
            extras = scene.get("_extra_fields")
            if isinstance(extras, dict):
                for key, value in extras.items():
                    if key not in record:
                        record[key] = copy.deepcopy(value)
            payload.append(record)
            layout.append(copy.deepcopy(scene.get("_canvas") or {}))
        state["Scenes"] = payload
        state["_SceneLayout"] = layout

        if isinstance(self._root_extra_fields, dict):
            for key, value in self._root_extra_fields.items():
                state.setdefault(key, copy.deepcopy(value))
        return True



class ScenarioInfoDialog(ctk.CTkToplevel):
    def __init__(self, master, *, title, summary, secrets):
        """Initialize the ScenarioInfoDialog instance."""
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
        """Handle save."""
        self.result = {
            "summary": self.summary_text.get("1.0", "end").strip(),
            "secrets": self.secrets_text.get("1.0", "end").strip(),
        }
        self.destroy()

    def _on_cancel(self):
        """Handle cancel."""
        self.result = None
        self.destroy()


class InlineSceneEditor(ctk.CTkFrame):
    def __init__(self, master, scene, *, scene_types, on_save, on_cancel, width=None, height=None):
        """Initialize the InlineSceneEditor instance."""
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
        """Handle save."""
        data = {
            "Title": self.title_var.get().strip(),
            "SceneType": self.type_var.get().strip(),
            "Summary": self.summary_text.get("1.0", "end").strip(),
        }
        if callable(self.on_save):
            self.on_save(data)

    def _on_cancel(self, _event=None):
        """Handle cancel."""
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
    ENTITY_FIELDS = SCENARIO_ENTITY_FIELDS

    def __init__(self, master, wrappers):
        """Initialize the EntityLinkingStep instance."""
        super().__init__(master)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
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
            # Process each entity_type from ENTITY_FIELDS.
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

        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        container.grid_columnconfigure((0, 1), weight=1, uniform="entities")

        for idx, (entity_type, (field, label)) in enumerate(self.ENTITY_FIELDS.items()):
            # Process each (idx, (entity_type, (field, label))) from enumerate(ENTITY_FIELDS.items()).
            frame = ctk.CTkFrame(container)
            row, col = divmod(idx, 2)
            frame.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
            frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(frame, text=f"Linked {label}s", anchor="w", font=ctk.CTkFont(size=14, weight="bold")).grid(
                row=0, column=0, sticky="w", padx=6, pady=(6, 4)
            )

            cards = ctk.CTkFrame(frame, fg_color="transparent")
            cards.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
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
        """Internal helper for detect media field."""
        try:
            template = load_template(entity_type)
        except Exception:
            return None
        fields = template.get("fields") if isinstance(template, dict) else None
        if not isinstance(fields, list):
            return None
        normalized = {}
        for field in fields:
            # Process each field from fields.
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
        """Invalidate entity cache."""
        self._entity_cache.pop(entity_type, None)

    def _get_entity_record(self, entity_type, name):
        """Return entity record."""
        if not name:
            return None
        cache = self._entity_cache.get(entity_type)
        if cache is None:
            # Handle the branch where cache is missing.
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
                # Process each item from items.
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
        """Resolve portrait path."""
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
            # Continue with this path when campaign dir is set.
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
        """Create card image."""
        resolved = self._resolve_portrait_path(portrait_value)
        image_obj = None
        if resolved:
            try:
                # Keep card image resilient if this step fails.
                with Image.open(resolved) as img:
                    image_obj = img.convert("RGBA")
            except Exception:
                image_obj = None
        if image_obj is None:
            # Handle the branch where image obj is missing.
            fallback_path = self._entity_icons.get(entity_type) or self._default_icon_path
            if fallback_path and os.path.exists(fallback_path):
                try:
                    # Keep card image resilient if this step fails.
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
        """Apply card selection style."""
        card.configure(
            fg_color=self.CARD_SELECTED_BG if selected else self.CARD_BG,
            border_color=self.CARD_SELECTED_BORDER if selected else self.CARD_BORDER,
            border_width=2 if selected else 1,
        )

    def _toggle_card_selection(self, field, name):
        """Toggle card selection."""
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
        """Create entity card."""
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
        """Open selector."""
        wrapper = self.wrappers.get(entity_type)
        if not wrapper:
            messagebox.showerror("Unavailable", f"No data source is available for {field}.")
            return
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
            on_select_callback=lambda _et, name, _item, f=field, win=top: self._on_entity_selected(f, name, win),
        )
        selection.pack(fill="both", expand=True)
        top.transient(self.winfo_toplevel())
        top.grab_set()

    def _on_entity_selected(self, field, name, window):  # pragma: no cover - UI callback
        """Handle entity selected."""
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
        """Remove selected."""
        selected_cards = set(self.card_selection.get(field) or set())
        if not selected_cards:
            return
        current = self.selected.get(field, [])
        self.selected[field] = [name for name in current if name not in selected_cards]
        self.card_selection[field] = set()
        self.refresh_list(field)

    def create_new_entity(self, entity_type, field, label):  # pragma: no cover - UI interaction
        """Create new entity."""
        wrapper = self.wrappers.get(entity_type)
        if not wrapper:
            messagebox.showerror("Unavailable", f"No {label} data source is available.")
            return

        try:
            # Keep new entity resilient if this step fails.
            template = load_template(entity_type)
        except Exception as exc:  # pragma: no cover - defensive path
            log_exception(f"Failed to load template for {entity_type}: {exc}")
            messagebox.showerror("Template Error", f"Unable to load the {label} template.")
            return

        try:
            # Keep new entity resilient if this step fails.
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
            # Continue with this path when unique key is set.
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
            # Keep new entity resilient if this step fails.
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
        """Refresh list."""
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
            # Process each name from values.
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
        """Load state."""
        for entity_type, (field, _) in self.ENTITY_FIELDS.items():
            # Process each (entity_type, (field, _)) from ENTITY_FIELDS.items().
            values = state.get(field) or []
            if isinstance(values, str):
                values = [values]
            self.selected[field] = list(dict.fromkeys(values))
            self.card_selection[field] = set()
            self.refresh_list(field)

    def save_state(self, state):  # pragma: no cover - UI synchronization
        """Save state."""
        for _, (field, _) in self.ENTITY_FIELDS.items():
            state[field] = list(dict.fromkeys(self.selected.get(field, [])))
        return True


class CharacterRelationsStep(WizardStep):
    def __init__(self, master, npc_wrapper, pc_wrapper, faction_wrapper):
        """Initialize the CharacterRelationsStep instance."""
        super().__init__(master)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._state_ref = None

        root = ctk.CTkFrame(self, fg_color="transparent")
        root.grid(row=0, column=0, sticky="nsew")
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(root, fg_color="#101827", corner_radius=14)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Character Relationships",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            header,
            text=(
                "Drop NPCs and PCs onto the board, create links between them, "
                "and right-click nodes or links to delete."
            ),
            text_color="#9db4d1",
            anchor="w",
            justify="left",
            wraplength=420,
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))

        self.sync_to_global_var = ctk.BooleanVar(value=False)
        self.sync_switch = ctk.CTkSwitch(
            header,
            text="Sync to global character graph",
            variable=self.sync_to_global_var,
        )
        self.sync_switch.grid(row=0, column=1, padx=16, pady=(12, 0), sticky="e")

        self.sync_hint = ctk.CTkLabel(
            header,
            text="Disable to keep this graph only inside the scenario.",
            text_color="#9db4d1",
            anchor="e",
        )
        self.sync_hint.grid(row=1, column=1, padx=16, pady=(0, 10), sticky="e")

        graph_container = ctk.CTkFrame(root, fg_color="transparent")
        graph_container.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        graph_container.grid_rowconfigure(0, weight=1)
        graph_container.grid_columnconfigure(0, weight=1)

        self.graph_editor = ScenarioCharacterGraphEditor(
            graph_container,
            npc_wrapper=npc_wrapper,
            pc_wrapper=pc_wrapper,
            faction_wrapper=faction_wrapper,
            on_entity_added=self._on_entity_added,
            on_entity_removed=self._on_entity_removed,
            background_style="scene_flow",
            node_style="modern",
        )
        self.graph_editor.grid(row=0, column=0, sticky="nsew")

    def set_state_binding(self, state, on_state_change=None):
        """Set state binding."""
        self._state_ref = state
        self._on_state_change = on_state_change

    def _on_entity_added(self, entity_type, entity_name):
        """Handle entity added."""
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
            # Handle the branch where entity name is not in values.
            values.append(entity_name)
            self._state_ref[field] = values
            if callable(self._on_state_change):
                self._on_state_change(source=self)

    def _on_entity_removed(self, entity_type, entity_name):
        """Handle entity removed."""
        if not self._state_ref or not entity_name:
            return
        if entity_type == "npc":
            field = "NPCs"
        elif entity_type == "pc":
            field = "PCs"
        else:
            return
        values = list(self._state_ref.get(field) or [])
        if entity_name in values:
            # Handle the branch where entity name is in values.
            values = [value for value in values if value != entity_name]
            self._state_ref[field] = values
            if callable(self._on_state_change):
                self._on_state_change(source=self)

    def load_state(self, state):  # pragma: no cover - UI synchronization
        """Load state."""
        self.sync_to_global_var.set(bool(state.get("ScenarioCharacterGraphSync")))
        scene_npcs = collect_scene_entity_names(state.get("Scenes"), "NPCs")
        merged_npcs = list(dict.fromkeys((state.get("NPCs") or []) + scene_npcs))
        graph_data = state.get("ScenarioCharacterGraph") or {}
        graph_data = build_scenario_graph_with_links(
            graph_data,
            merged_npcs,
            state.get("PCs") or [],
        )
        self.graph_editor.load_graph_data(graph_data)

    def save_state(self, state):  # pragma: no cover - UI synchronization
        """Save state."""
        graph_data = self.graph_editor.export_graph_data()
        state["ScenarioCharacterGraph"] = graph_data
        npc_names = []
        pc_names = []
        for node in graph_data.get("nodes", []):
            # Process each node from graph_data.get('nodes', []).
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
        """Initialize the ReviewStep instance."""
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
        """Load state."""
        title = state.get("Title", "Untitled Scenario")
        summary = state.get("Summary") or "(No summary provided.)"
        secrets = state.get("Secrets") or "(No secrets provided.)"

        summary_preview = textwrap.shorten(summary, width=160, placeholder="…")
        secrets_preview = textwrap.shorten(secrets, width=160, placeholder="…")

        self.title_label.configure(text=title)
        self.summary_label.configure(text=f"Summary: {summary_preview}")
        self.secrets_label.configure(text=f"Secrets: {secrets_preview}")

        scenes = copy.deepcopy(state.get("Scenes") or [])
        for idx, scene in enumerate(scenes):
            # Process each (idx, scene) from enumerate(scenes).
            if not isinstance(scene, dict):
                continue
            canonical_scene = canonicalise_scene(scene, index=idx)
            scene["LinkData"] = copy.deepcopy(canonical_scene.get("LinkData") or [])
            scene["NextScenes"] = list(canonical_scene.get("NextScenes") or [])
        self.flow_preview.render(scenes, selected_index=None)

        scene_count = len(scenes)
        entity_counts = []
        for field in SCENARIO_ENTITY_FIELD_NAMES:
            # Process each field from SCENARIO_ENTITY_FIELD_NAMES.
            entries = state.get(field) or []
            if entries:
                entity_counts.append(f"{len(entries)} {field}")
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
                # Process each (idx, scene) from enumerate(scenes, start=1).
                title_value = ""
                if isinstance(scene, dict):
                    title_value = scene.get("Title") or scene.get("title") or ""
                if title_value:
                    summary_lines.append(f"  {idx}. {title_value}")
                else:
                    summary_lines.append(f"  {idx}. Scene {idx}")
        else:
            summary_lines.append("  (No scenes planned.)")

        for field in SCENARIO_ENTITY_FIELD_NAMES:
            # Process each field from SCENARIO_ENTITY_FIELD_NAMES.
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

    def __init__(
        self,
        master,
        on_saved=None,
        *,
        initial_scenario=None,
        mode="standalone",
        campaign_context=None,
        arc_context=None,
        on_embedded_result=None,
        persist_on_finish=False,
    ):
        """Initialize the ScenarioBuilderWizard instance."""
        super().__init__(master)
        self.title("Scenario Builder Wizard")
        self.geometry("1920x1080+0+0")
        self.minsize(1100, 700)
        self.transient(master)
        self.on_saved = on_saved
        self.mode = "embedded" if str(mode).lower() == "embedded" else "standalone"
        self.campaign_context = campaign_context or {}
        self.arc_context = arc_context or {}
        self.on_embedded_result = on_embedded_result
        self.persist_on_finish = bool(persist_on_finish)
        self.story_forge = StoryForgeOrchestrator()

        # NOTE: Avoid shadowing the inherited ``state()`` method from Tk by
        # storing wizard data on a dedicated attribute.
        self.wizard_state = {
            "Title": "",
            "Summary": "",
            "Secrets": "",
            "Secret": "",
            "Scenes": [],
            "ScenarioCharacterGraph": {"nodes": [], "links": []},
            "ScenarioCharacterGraphSync": False,
        }
        for field in SCENARIO_ENTITY_FIELD_NAMES:
            self.wizard_state[field] = []

        self.scenario_wrapper = GenericModelWrapper("scenarios")
        self.entity_wrappers = {
            entity_type: GenericModelWrapper(entity_type)
            for entity_type in SCENARIO_ENTITY_FIELDS
        }
        self.npc_wrapper = self.entity_wrappers["npcs"]
        self.pc_wrapper = self.entity_wrappers["pcs"]
        self.villain_wrapper = self.entity_wrappers["villains"]
        self.creature_wrapper = self.entity_wrappers["creatures"]
        self.base_wrapper = self.entity_wrappers["bases"]
        self.place_wrapper = self.entity_wrappers["places"]
        self.map_wrapper = self.entity_wrappers["maps"]
        self.event_wrapper = self.entity_wrappers["events"]
        self.faction_wrapper = self.entity_wrappers["factions"]
        self.object_wrapper = self.entity_wrappers["objects"]
        self.book_wrapper = self.entity_wrappers["books"]

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
            # Keep safe destroy resilient if this step fails.
            if self.winfo_exists():
                self.withdraw()
        except Exception:
            pass

        def _finalize():
            """Internal helper for finalize."""
            try:
                super(ScenarioBuilderWizard, self).destroy()
            except Exception:
                pass

        try:
            self.after(150, _finalize)
        except Exception:
            _finalize()

    def destroy(self):  # pragma: no cover - UI teardown
        """Handle destroy."""
        self._schedule_safe_destroy()

    def focus_set(self):  # pragma: no cover - UI focus handling
        """Safely set focus on the wizard if it still exists."""

        try:
            # Keep focus set resilient if this step fails.
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
            # Keep focus force resilient if this step fails.
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            super().focus_force()
        except tk.TclError:
            pass

    def _build_layout(self):  # pragma: no cover - UI layout
        """Build layout."""
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
        nav.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.back_btn = ctk.CTkButton(nav, text="Back", command=self.go_back)
        self.back_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.next_btn = ctk.CTkButton(nav, text="Next", command=self.go_next)
        self.next_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.finish_btn = ctk.CTkButton(nav, text="Finish", command=self.finish)
        self.finish_btn.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
        self.cancel_btn = ctk.CTkButton(nav, text="Cancel", command=self.cancel)
        self.cancel_btn.grid(row=0, column=3, padx=10, pady=10, sticky="ew")
        self.story_forge_btn = ctk.CTkButton(nav, text="Story Forge Draft", command=self._run_story_forge)
        self.story_forge_btn.grid(row=0, column=4, padx=10, pady=10, sticky="ew")

    def _create_steps(self):  # pragma: no cover - UI layout
        """Create steps."""
        entity_wrappers = dict(self.entity_wrappers)

        planning_step = ScenesPlanningStep(
            self.step_container,
            {
                key: wrapper
                for key, wrapper in entity_wrappers.items()
                if key in ("npcs", "creatures", "bases", "places", "maps")
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
        """Launch epic finale planner."""
        try:
            # Keep epic finale planner resilient if this step fails.
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
            # Keep epic finale planner resilient if this step fails.
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
            """Close original wizard."""
            try:
                # Keep original wizard resilient if this step fails.
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
        """Show step."""
        title, frame = self.steps[index]
        self.header_label.configure(text=f"Step {index + 1} of {len(self.steps)}: {title}")
        frame.tkraise()
        frame.load_state(self.wizard_state)
        self._update_navigation_buttons()

    def _on_wizard_state_changed(self, source=None):  # pragma: no cover - UI synchronization
        """Handle wizard state changed."""
        for _, frame in self.steps:
            # Process each (_, frame) from steps.
            if frame is source:
                continue
            try:
                frame.load_state(self.wizard_state)
            except Exception:
                pass

    def load_existing_scenario(self, scenario):  # pragma: no cover - UI interaction
        """Load existing scenario."""
        planning_step = next(
            (frame for _, frame in self.steps if isinstance(frame, ScenesPlanningStep)),
            None,
        )
        if planning_step is None:
            return

        scenario_payload = None
        if isinstance(scenario, str):
            # Handle the branch where isinstance(scenario, str).
            try:
                # Keep existing scenario resilient if this step fails.
                items = self.scenario_wrapper.load_items()
            except Exception as exc:
                log_exception(
                    f"Failed to load scenarios for editing: {exc}",
                    func_name="ScenarioBuilderWizard.load_existing_scenario",
                )
                messagebox.showerror("Load Error", "Unable to load scenarios from the database.")
                return
            for entry in items or []:
                # Process each entry from items or [].
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
        """Update navigation buttons."""
        self.back_btn.configure(state="normal" if self.current_step_index > 0 else "disabled")
        is_last = self.current_step_index == len(self.steps) - 1
        self.next_btn.configure(state="disabled" if is_last else "normal")
        self.finish_btn.configure(state="normal" if is_last else "disabled")

    def go_next(self):  # pragma: no cover - UI navigation
        """Handle go next."""
        step = self.steps[self.current_step_index][1]
        if not step.save_state(self.wizard_state):
            return
        self.current_step_index += 1
        self._show_step(self.current_step_index)

    def go_back(self):  # pragma: no cover - UI navigation
        """Handle go back."""
        step = self.steps[self.current_step_index][1]
        if not step.save_state(self.wizard_state):
            return
        self.current_step_index -= 1
        self._show_step(self.current_step_index)

    def cancel(self):  # pragma: no cover - UI navigation
        """Handle cancel."""
        self.destroy()

    def _run_story_forge(self):  # pragma: no cover - UI interaction
        """Run story forge."""
        step = self.steps[self.current_step_index][1]
        if not step.save_state(self.wizard_state):
            return

        brief = (self.wizard_state.get("Summary") or "").strip()
        if not brief:
            messagebox.showwarning(
                "Story Forge",
                "Add a short summary first (Visual Builder > Edit Notes) to seed Story Forge.",
            )
            return

        existing_scenarios = []
        try:
            existing_scenarios = [
                str(item.get("Title") or item.get("Name") or "").strip()
                for item in (self.scenario_wrapper.load_items() or [])
                if isinstance(item, dict)
            ]
            existing_scenarios = [name for name in existing_scenarios if name]
        except Exception:
            existing_scenarios = []

        context = load_campaign_arc_context(self.campaign_context, self.arc_context)
        request = StoryForgeRequest(
            brief=brief,
            campaign_name=context.get("campaign_name", ""),
            campaign_summary=context.get("campaign_summary", ""),
            arc_name=context.get("arc_name", ""),
            arc_summary=context.get("arc_summary", ""),
            arc_objective=context.get("arc_objective", ""),
            arc_thread=context.get("arc_thread", ""),
            existing_scenarios=existing_scenarios,
            entity_catalog=load_db_entity_catalog(),
        )

        self._set_navigation_enabled(False)

        def _worker():
            """Internal helper for worker."""
            result = self.story_forge.run(request)
            payload = result.to_scenario_payload()
            self.after(0, lambda: _on_success(payload))

        def _on_success(payload: dict):
            """Handle success."""
            self._set_navigation_enabled(True)
            self.load_existing_scenario(payload)
            messagebox.showinfo("Story Forge", "Scenario draft applied. Review and adjust before finishing.")

        def _on_error(exc: Exception):
            """Handle error."""
            self._set_navigation_enabled(True)
            log_exception(
                f"Story Forge failed: {exc}",
                func_name="ScenarioBuilderWizard._run_story_forge",
            )
            messagebox.showerror("Story Forge", f"Unable to generate a draft: {exc}")

        self._run_in_worker(_worker, on_error=_on_error)

    def _set_navigation_enabled(self, enabled: bool):  # pragma: no cover - UI interaction
        """Set navigation enabled."""
        state = "normal" if enabled else "disabled"
        for btn in (self.back_btn, self.next_btn, self.finish_btn, self.cancel_btn, self.story_forge_btn):
            try:
                # Keep navigation enabled resilient if this step fails.
                if btn.winfo_exists():
                    btn.configure(state=state)
            except Exception:
                continue

    def _run_in_worker(self, worker, *, on_error=None):
        """Run in worker."""
        def _runner():
            """Internal helper for runner."""
            try:
                worker()
            except Exception as exc:  # pragma: no cover - threaded failure path
                if on_error:
                    self.after(0, lambda: on_error(exc))
                else:
                    self.after(0, lambda: messagebox.showerror("Unexpected Error", str(exc)))

        threading.Thread(target=_runner, daemon=True).start()

    def _persist_scenario_payload(self, title, payload):
        """Persist scenario payload."""
        while True:
            # Keep looping while True.
            try:
                # Keep scenario payload resilient if this step fails.
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
                    return False, False

        replaced = False
        for idx, existing in enumerate(items):
            if existing.get("Title") == title:
                # Handle the branch where existing.get('Title') == title.
                if not messagebox.askyesno(
                    "Overwrite Scenario",
                    f"A scenario titled '{title}' already exists. Overwrite it?",
                ):
                    return False, False
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
        return True, replaced

    def finish(self):  # pragma: no cover - UI navigation
        """Handle finish."""
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
            "ScenarioCharacterGraph": self.wizard_state.get("ScenarioCharacterGraph", {}),
        }
        for field in SCENARIO_ENTITY_FIELD_NAMES:
            payload[field] = list(dict.fromkeys(self.wizard_state.get(field, [])))
        sync_graph = bool(self.wizard_state.get("ScenarioCharacterGraphSync"))

        buttons = {
            self.back_btn: self.back_btn.cget("state"),
            self.next_btn: self.next_btn.cget("state"),
            self.finish_btn: self.finish_btn.cget("state"),
            self.cancel_btn: self.cancel_btn.cget("state"),
            self.story_forge_btn: self.story_forge_btn.cget("state"),
        }
        for btn in buttons:
            btn.configure(state="disabled")

        try:
            # Keep finish resilient if this step fails.
            if self.mode == "embedded":
                # Handle the branch where mode == 'embedded'.
                if self.persist_on_finish:
                    # Continue with this path when persist on finish is set.
                    persisted, _ = self._persist_scenario_payload(title, payload)
                    if not persisted:
                        return
                if callable(self.on_embedded_result):
                    try:
                        # Keep finish resilient if this step fails.
                        callback_payload = build_embedded_result_payload(
                            StoryForgeResponse(
                                title=payload["Title"],
                                summary=payload.get("Summary", ""),
                                secrets=payload.get("Secrets", ""),
                                scenes=payload.get("Scenes", []),
                                entities={field: payload.get(field, []) for field in SCENARIO_ENTITY_FIELD_NAMES},
                            ),
                            campaign_context=self.campaign_context,
                            arc_context=self.arc_context,
                        )
                        self.on_embedded_result(callback_payload)
                    except Exception as exc:
                        log_exception(
                            f"Embedded scenario callback failed: {exc}",
                            func_name="ScenarioBuilderWizard.finish",
                        )
                        messagebox.showerror(
                            "Embedded Save Error",
                            "The scenario draft was created but could not be returned to the caller.",
                        )
                        return
                self.destroy()
                return
            persisted, _ = self._persist_scenario_payload(title, payload)
            if not persisted:
                return
            messagebox.showinfo("Scenario Saved", f"Scenario '{title}' has been saved.")
            if callable(self.on_saved):
                try:
                    self.on_saved()
                except Exception:
                    pass
            if sync_graph:
                try:
                    # Keep finish resilient if this step fails.
                    sync_scenario_graph_to_global(
                        self.wizard_state.get("ScenarioCharacterGraph") or {},
                        title,
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
