import copy
import tkinter as tk

import customtkinter as ctk

from modules.scenarios.scene_flow_components import SceneCanvas
from modules.scenarios.wizard_steps.scenes.scene_entity_fields import (
    SCENE_ENTITY_FIELDS,
    normalise_entity_list,
)
from modules.scenarios.wizard_steps.scenes.scene_mode_adapters import normalise_scene_links


class InlineSceneEditor(ctk.CTkFrame):
    def __init__(self, master, scene, *, scene_types, on_save, on_cancel, width=None, height=None):
        super().__init__(master, fg_color="#0f172a", corner_radius=12, width=width, height=height)
        self.on_save = on_save
        self.on_cancel = on_cancel

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text="Scene Details", font=ctk.CTkFont(size=14, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=12, pady=(12, 6)
        )

        self.title_var = ctk.StringVar(value=scene.get("Title", ""))
        ctk.CTkEntry(self, textvariable=self.title_var).grid(row=1, column=0, sticky="ew", padx=12)

        type_values = [""] + [value for value in scene_types or [] if value]
        current_type = scene.get("SceneType") or scene.get("Type") or ""
        if current_type and current_type not in type_values:
            type_values.append(current_type)
        self.type_var = ctk.StringVar(value=current_type)
        self.type_menu = ctk.CTkOptionMenu(self, values=type_values, variable=self.type_var)
        self.type_menu.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 6))

        self.summary_text = ctk.CTkTextbox(self, wrap="word")
        self.summary_text.grid(row=3, column=0, sticky="nsew", padx=12)
        self.summary_text.insert("1.0", scene.get("Summary") or scene.get("Text") or "")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=4, column=0, sticky="ew", padx=12, pady=(8, 10))
        row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(row, text="Cancel", command=self._on_cancel).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(row, text="Save", command=self._on_save).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _on_save(self):
        self.on_save(
            {
                "Title": self.title_var.get().strip(),
                "SceneType": self.type_var.get().strip(),
                "Summary": self.summary_text.get("1.0", "end").strip(),
            }
        )

    def _on_cancel(self):
        self.on_cancel()


class CanvasScenePlanner(ctk.CTkFrame):
    SCENE_TYPES = ["Auto", "Setup", "Choice", "Investigation", "Combat", "Outcome", "Social", "Travel", "Downtime"]

    def __init__(self, master, *, entity_selector_callbacks=None):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.scenes = []
        self.selected_index = None
        self._inline_editor = None
        self.entity_selector_callbacks = entity_selector_callbacks or {}

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 6))
        self.add_scene_btn = ctk.CTkButton(buttons, text="Add Scene", command=self.add_scene)
        self.add_scene_btn.pack(side="left")
        self.dup_scene_btn = ctk.CTkButton(buttons, text="Duplicate", command=self.duplicate_scene)
        self.dup_scene_btn.pack(side="left", padx=6)
        self.remove_scene_btn = ctk.CTkButton(buttons, text="Remove", command=self.remove_scene)
        self.remove_scene_btn.pack(side="left")

        self.canvas = SceneCanvas(
            self,
            on_select=self._on_canvas_select,
            on_move=self._on_canvas_move,
            on_edit=self._open_inline_scene_editor,
            on_context=self._show_canvas_menu,
            on_add_entity=self._on_add_entity_to_scene,
            on_link=self._link_scenes_via_drag,
            on_link_text_edit=lambda *_: None,
            available_entity_types=["NPCs", "Creatures", "Places", "Bases", "Maps"],
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._update_buttons()

    def load_scenes(self, scenes):
        self.scenes = [copy.deepcopy(scene) for scene in (scenes or [])]
        self.selected_index = 0 if self.scenes else None
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._update_buttons()

    def export_scenes(self):
        exported = []
        for scene in self.scenes:
            record = copy.deepcopy(scene)
            for entity_field in SCENE_ENTITY_FIELDS:
                if entity_field in record:
                    record[entity_field] = normalise_entity_list(record.get(entity_field))
            exported.append(record)
        return exported

    def add_scene(self):
        scene = {"Title": f"Scene {len(self.scenes) + 1}", "Summary": "", "SceneType": "", "LinkData": [], "NextScenes": [], "_canvas": {}}
        self._assign_default_position(scene)
        self.scenes.append(scene)
        self.selected_index = len(self.scenes) - 1
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._update_buttons()

    def duplicate_scene(self):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        source = copy.deepcopy(self.scenes[self.selected_index])
        source["Title"] = f"{source.get('Title') or 'Scene'} Copy"
        source["_canvas"] = {}
        self._assign_default_position(source)
        self.scenes.insert(self.selected_index + 1, source)
        self.selected_index += 1
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._update_buttons()

    def remove_scene(self):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        removed = self.scenes.pop(self.selected_index)
        removed_title = str(removed.get("Title") or "").strip()
        for scene in self.scenes:
            links = [l for l in normalise_scene_links(scene) if l.get("target") != removed_title]
            scene["LinkData"] = links
            scene["NextScenes"] = [link["target"] for link in links]
        self.selected_index = min(self.selected_index, len(self.scenes) - 1) if self.scenes else None
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._update_buttons()

    def _on_canvas_select(self, index):
        self.selected_index = index if isinstance(index, int) and 0 <= index < len(self.scenes) else None
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._update_buttons()

    def _on_canvas_move(self, index, x, y):
        if index is None or index >= len(self.scenes):
            return
        self.scenes[index].setdefault("_canvas", {}).update({"x": x, "y": y})

    def _open_inline_scene_editor(self, index):
        if index is None or index >= len(self.scenes):
            return
        bbox = self.canvas.get_card_bbox(index)
        if not bbox:
            return
        if self._inline_editor is not None:
            self._inline_editor.destroy()
        x1, y1, x2, y2 = bbox
        editor = InlineSceneEditor(
            self.canvas,
            self.scenes[index],
            scene_types=self.SCENE_TYPES,
            on_save=lambda data, idx=index: self._apply_inline_scene_update(idx, data),
            on_cancel=self._close_inline_scene_editor,
            width=max(120, (x2 - x1) - 16),
            height=max(120, (y2 - y1) - 16),
        )
        editor.place(x=x1 + 8, y=y1 + 8)
        self._inline_editor = editor

    def _apply_inline_scene_update(self, index, data):
        scene = self.scenes[index]
        scene["Title"] = data.get("Title") or scene.get("Title") or f"Scene {index + 1}"
        scene["Summary"] = data.get("Summary", "")
        scene["SceneType"] = data.get("SceneType", "")
        self._close_inline_scene_editor()
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _close_inline_scene_editor(self):
        if self._inline_editor is not None:
            self._inline_editor.destroy()
            self._inline_editor = None

    def _show_canvas_menu(self, event, index):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Add Scene", command=self.add_scene)
        if index is not None:
            self.selected_index = index
            menu.add_command(label="Edit", command=lambda idx=index: self._open_inline_scene_editor(idx))
            menu.add_command(label="Duplicate", command=self.duplicate_scene)
            menu.add_command(label="Remove", command=self.remove_scene)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _link_scenes_via_drag(self, source_index, target_index):
        if source_index is None or target_index is None:
            return
        if source_index >= len(self.scenes) or target_index >= len(self.scenes):
            return
        source = self.scenes[source_index]
        target_title = self.scenes[target_index].get("Title") or f"Scene {target_index + 1}"
        links = normalise_scene_links(source)
        if any(link.get("target") == target_title for link in links):
            return
        links.append({"target": target_title, "text": target_title})
        source["LinkData"] = links
        source["NextScenes"] = [link["target"] for link in links]
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _on_add_entity_to_scene(self, index, entity_type):
        if index is None or index >= len(self.scenes):
            return
        selector = self.entity_selector_callbacks.get(entity_type)
        if not callable(selector):
            return
        scene = self.scenes[index]
        current_values = normalise_entity_list(scene.get(entity_type))
        selected_values = normalise_entity_list(selector(current_values))
        if not selected_values:
            return
        merged_values = normalise_entity_list(current_values + selected_values)
        scene[entity_type] = merged_values
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _assign_default_position(self, scene):
        scene.setdefault("_canvas", {})
        scene["_canvas"].setdefault("x", 180 + len(self.scenes) * 40)
        scene["_canvas"].setdefault("y", 160 + len(self.scenes) * 40)

    def _update_buttons(self):
        state = "normal" if self.selected_index is not None else "disabled"
        self.dup_scene_btn.configure(state=state)
        self.remove_scene_btn.configure(state=state)
