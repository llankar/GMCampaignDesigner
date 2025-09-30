import copy
import json
import sqlite3
import textwrap
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from modules.generic.generic_editor_window import GenericEditorWindow
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_module_import, log_info, log_exception
from modules.helpers.template_loader import load_template
from modules.scenarios.scene_flow_rendering import (
    SCENE_FLOW_BG,
    apply_scene_flow_canvas_styling,
    get_shadow_image,
)


def normalise_scene_links(scene, split_to_list):
    """Return the cleaned link payload for ``scene``.

    The helper mirrors :meth:`ScenesPlanningStep._get_scene_links` so that the
    same normalisation logic can be shared with lightweight previews such as
    the wizard review step without duplicating behaviour.
    """

    raw_links = scene.get("LinkData")
    cleaned = []
    if isinstance(raw_links, list):
        for item in raw_links:
            if isinstance(item, dict):
                target = str(
                    item.get("target")
                    or item.get("Scene")
                    or item.get("Next")
                    or ""
                ).strip()
                if not target:
                    continue
                text = str(item.get("text") or target).strip()
                cleaned.append({"target": target, "text": text})
            elif isinstance(item, str):
                target = item.strip()
                if target:
                    cleaned.append({"target": target, "text": target})
    if not cleaned:
        for target in split_to_list(scene.get("NextScenes", [])):
            if target:
                cleaned.append({"target": target, "text": target})
    deduped = []
    seen = set()
    for link in cleaned:
        target = link["target"]
        text = link.get("text") or target
        key = (target.lower(), text.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"target": target, "text": text})
    scene["LinkData"] = deduped
    scene["NextScenes"] = [link["target"] for link in deduped]
    return deduped


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


class SceneFlowPreview(ctk.CTkFrame):
    """Lightweight scene flow canvas used inside the wizard."""

    CARD_WIDTH = 220
    CARD_HEIGHT = 130
    GRID_SPACING = 48

    def __init__(self, master, *, on_select=None):
        super().__init__(master, corner_radius=16, fg_color=("#0f1624", "#0f1624"))
        self.on_select = on_select
        self.scenes = []
        self.selected_index = None
        self.node_regions = []

        self.canvas = tk.Canvas(self, bg="#0c121d", highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas.bind("<Configure>", lambda _event: self._draw())
        self.canvas.bind("<Button-1>", self._handle_click)

    def render(self, scenes, selected_index):
        self.scenes = scenes or []
        self.selected_index = selected_index if isinstance(selected_index, int) else None
        self._draw()

    def _draw(self, *_args, **_kwargs):
        if not hasattr(self, "canvas"):
            return
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.canvas.delete("all")
        self.node_regions = []

        for x in range(0, width, self.GRID_SPACING):
            self.canvas.create_line(x, 0, x, height, fill="#141f31")
        for y in range(0, height, self.GRID_SPACING):
            self.canvas.create_line(0, y, width, y, fill="#141f31")

        if not self.scenes:
            self.canvas.create_text(
                width / 2,
                height / 2,
                text="Add scenes to see the story flow visualised here",
                fill="#7183a5",
                font=("Segoe UI", 15, "bold"),
            )
            return

        columns = max(1, min(4, (width - 140) // (self.CARD_WIDTH + 60)))
        positions = []
        for idx, _ in enumerate(self.scenes):
            col = idx % columns
            row = idx // columns
            x = 90 + col * (self.CARD_WIDTH + 60) + self.CARD_WIDTH / 2
            y = 90 + row * (self.CARD_HEIGHT + 120)
            positions.append((x, y))

        title_lookup = {}
        for idx, scene in enumerate(self.scenes):
            title = (scene.get("Title") or f"Scene {idx + 1}").strip().lower()
            if title:
                title_lookup[title] = idx

        def resolve_target(reference):
            if reference is None:
                return None
            ref = str(reference).strip()
            if not ref:
                return None
            lowered = ref.lower()
            if lowered in title_lookup:
                return title_lookup[lowered]
            if lowered.startswith("scene "):
                try:
                    number = int(lowered.split()[1])
                except (ValueError, IndexError):
                    number = None
                if number and 1 <= number <= len(self.scenes):
                    return number - 1
            if ref.isdigit():
                number = int(ref)
                if 1 <= number <= len(self.scenes):
                    return number - 1
            return None

        for idx, scene in enumerate(self.scenes):
            start = positions[idx]
            for target in scene.get("NextScenes") or []:
                resolved = resolve_target(target)
                if resolved is None or resolved >= len(positions):
                    continue
                end = positions[resolved]
                color = "#58a2ff" if idx == self.selected_index else "#365074"
                self.canvas.create_line(
                    start[0],
                    start[1] + self.CARD_HEIGHT / 2 - 8,
                    end[0],
                    end[1] - self.CARD_HEIGHT / 2,
                    fill=color,
                    width=2.2,
                    arrow=tk.LAST,
                    smooth=True,
                )

        for idx, scene in enumerate(self.scenes):
            x, y = positions[idx]
            x1 = x - self.CARD_WIDTH / 2
            y1 = y - self.CARD_HEIGHT / 2
            x2 = x + self.CARD_WIDTH / 2
            y2 = y + self.CARD_HEIGHT / 2
            selected = idx == self.selected_index
            bg = "#1b253b" if selected else "#121a2a"
            border = "#6ab2ff" if selected else "#23314a"
            self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=bg,
                outline=border,
                width=2.4,
                tags=(f"scene-node-{idx}", "scene-node"),
            )
            title = (scene.get("Title") or f"Scene {idx + 1}").strip() or f"Scene {idx + 1}"
            summary = (scene.get("Summary") or scene.get("Text") or "").replace("\n", " ").strip()
            summary_display = (
                textwrap.shorten(summary, width=120, placeholder="...")
                if summary
                else "Click to outline this beat."
            )
            scene_type = scene.get("SceneType") or scene.get("Type") or ""
            if scene_type:
                self.canvas.create_rectangle(
                    x1 + 8,
                    y1 + 8,
                    x1 + 108,
                    y1 + 30,
                    fill="#28548a",
                    outline="",
                    tags=(f"scene-node-{idx}", "scene-node"),
                )
                self.canvas.create_text(
                    x1 + 58,
                    y1 + 19,
                    text=scene_type.upper(),
                    fill="white",
                    font=("Segoe UI", 9, "bold"),
                    tags=(f"scene-node-{idx}", "scene-node"),
                )
            self.canvas.create_text(
                x,
                y - 8,
                text=title,
                fill="white",
                font=("Segoe UI", 13, "bold"),
                width=self.CARD_WIDTH - 24,
                tags=(f"scene-node-{idx}", "scene-node"),
            )
            self.canvas.create_text(
                x,
                y + 26,
                text=summary_display,
                fill="#8d9ab7",
                font=("Segoe UI", 10),
                width=self.CARD_WIDTH - 24,
                tags=(f"scene-node-{idx}", "scene-node"),
            )
            self.node_regions.append((x1, y1, x2, y2, idx))

    def _handle_click(self, event):
        for x1, y1, x2, y2, idx in self.node_regions:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if callable(self.on_select):
                    self.on_select(idx)
                break


class SceneCanvas(ctk.CTkFrame):
    GRID = 60
    CARD_W = 240
    CARD_H = 150

    def __init__(self, master, on_select=None, on_move=None):
        super().__init__(master, corner_radius=16, fg_color=SCENE_FLOW_BG)
        self.on_select = on_select
        self.on_move = on_move
        self.scenes = []
        self.selected_index = None
        self._drag_index = None
        self._drag_offset = (0, 0)
        self._grid_tile_cache: dict[str, object] = {}
        self._shadow_cache: dict[tuple, tuple] = {}
        self._image_refs: dict[str, object] = {}

        self.canvas = tk.Canvas(
            self,
            bg=SCENE_FLOW_BG,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._draw())
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def set_scenes(self, scenes, selected_index=None):
        self.scenes = scenes or []
        self.selected_index = selected_index if isinstance(selected_index, int) else None
        self._ensure_positions()
        self._draw()

    def _ensure_positions(self):
        if not self.scenes:
            return
        spacing_x = self.CARD_W + 160
        spacing_y = self.CARD_H + 140
        cols = max(1, int(len(self.scenes) ** 0.5))
        for idx, scene in enumerate(self.scenes):
            layout = scene.setdefault("_canvas", {})
            if "x" in layout and "y" in layout:
                continue
            col = idx % cols
            row = idx // cols
            layout["x"] = 180 + col * spacing_x
            layout["y"] = 160 + row * spacing_y

    def _draw(self, *_args, **_kwargs):
        c = getattr(self, "canvas", None)
        if c is None:
            return
        width = max(c.winfo_width(), 1)
        height = max(c.winfo_height(), 1)
        c.delete("all")
        self._image_refs.clear()

        apply_scene_flow_canvas_styling(
            c,
            tile_cache=self._grid_tile_cache,
            extent_width=max(width, self.CARD_W * 4),
            extent_height=max(height, self.CARD_H * 4),
        )
        c.tag_lower("scene_flow_bg")
        if not self.scenes:
            c.create_text(
                width / 2,
                height / 2,
                text="Click Add Scene to begin",
                fill="#8ba1cc",
                font=("Segoe UI", 18, "bold"),
            )
            return
        positions = {}
        title_lookup = {}
        for idx, scene in enumerate(self.scenes):
            layout = scene.get("_canvas", {})
            x = layout.get("x", width / 2)
            y = layout.get("y", height / 2)
            positions[idx] = (x, y)
            title = (scene.get("Title") or f"Scene {idx + 1}").strip().lower()
            title_lookup[title] = idx
        # links
        for idx, scene in enumerate(self.scenes):
            start = positions.get(idx)
            if not start:
                continue
            links = scene.get("LinkData") or []
            if not isinstance(links, list) or not links:
                links = [{"target": target, "text": target} for target in scene.get("NextScenes", [])]
            for link in links:
                target_value = link.get("target")
                if target_value is None:
                    continue
                target_idx = None
                if isinstance(target_value, int):
                    if 1 <= target_value <= len(self.scenes):
                        target_idx = target_value - 1
                else:
                    target_str = str(target_value).strip()
                    if target_str.isdigit():
                        num = int(target_str)
                        if 1 <= num <= len(self.scenes):
                            target_idx = num - 1
                    if target_idx is None:
                        target_idx = title_lookup.get(target_str.lower())
                if target_idx is None or target_idx == idx:
                    continue
                end = positions.get(target_idx)
                if not end:
                    continue
                is_selected = idx == self.selected_index
                color = "#5bb8ff" if is_selected else "#2f4c6f"
                line_width = 3 if is_selected else 2
                sx = start[0] + self.CARD_W / 2 - 12
                sy = start[1]
                ex = end[0] - self.CARD_W / 2 + 12
                ey = end[1]
                mx = (sx + ex) / 2
                my = (sy + ey) / 2
                c.create_line(
                    sx,
                    sy,
                    mx,
                    my,
                    ex,
                    ey,
                    smooth=True,
                    width=line_width,
                    arrow=tk.LAST,
                    arrowshape=(16, 18, 7),
                    fill=color,
                    tags=("link", "scene_flow_link"),
                )
                label_text = str(link.get("text") or target_value).strip()
                if label_text:
                    c.create_text(
                        mx,
                        my - 14,
                        text=label_text,
                        fill="#9DB4D1",
                        font=("Segoe UI", 10, "bold" if idx == self.selected_index else "normal"),
                    )
        # cards
        self._regions = []
        for idx, scene in enumerate(self.scenes):
            x, y = positions[idx]
            x1 = x - self.CARD_W / 2
            y1 = y - self.CARD_H / 2
            x2 = x + self.CARD_W / 2
            y2 = y + self.CARD_H / 2
            shadow_image, offset = get_shadow_image(
                c, self._shadow_cache, self.CARD_W, self.CARD_H, 1.0
            )
            if shadow_image:
                shadow_id = c.create_image(
                    x1 - offset,
                    y1 - offset,
                    image=shadow_image,
                    anchor="nw",
                    tags=(f"scene-node-{idx}", "scene-node-shadow"),
                )
                c.tag_lower(shadow_id)
                self._image_refs[f"shadow-{idx}"] = shadow_image

            bg = "#1f2a40" if idx == self.selected_index else "#151e30"
            border = "#6ab2ff" if idx == self.selected_index else "#273750"
            card_id = c.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=bg,
                outline=border,
                width=3,
                tags=(f"scene-node-{idx}", "scene-node"),
            )
            c.tag_raise(card_id)
            title = scene.get("Title") or f"Scene {idx + 1}"
            c.create_text(
                x1 + 14,
                y1 + 18,
                text=title,
                anchor="nw",
                fill="#f8fafc",
                font=("Segoe UI", 13, "bold"),
                tags=(f"scene-node-{idx}", "scene-node"),
            )
            summary = scene.get("Summary") or scene.get("Text") or ""
            summary = " ".join(summary.split())[:160]
            c.create_text(
                x1 + 14,
                y1 + 48,
                text=summary,
                anchor="nw",
                fill="#c5d4f5",
                font=("Segoe UI", 10),
                width=self.CARD_W - 28,
                tags=(f"scene-node-{idx}", "scene-node"),
            )
            self._regions.append((x1, y1, x2, y2, idx))

    def _on_click(self, event):
        for x1, y1, x2, y2, idx in reversed(self._regions):
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self._drag_index = idx
                layout = self.scenes[idx].setdefault("_canvas", {})
                layout.setdefault("x", (x1 + x2) / 2)
                layout.setdefault("y", (y1 + y2) / 2)
                self._drag_offset = (event.x - layout["x"], event.y - layout["y"])
                if self.selected_index != idx:
                    self.selected_index = idx
                    if callable(self.on_select):
                        self.on_select(idx)
                    else:
                        self._draw()
                return
        self.selected_index = None
        if callable(self.on_select):
            self.on_select(None)
        else:
            self._draw()

    def _on_drag(self, event):
        if self._drag_index is None:
            return
        layout = self.scenes[self._drag_index].setdefault("_canvas", {})
        layout["x"] = event.x - self._drag_offset[0]
        layout["y"] = event.y - self._drag_offset[1]
        self._draw()

    def _on_release(self, _event):
        if self._drag_index is None:
            return
        layout = self.scenes[self._drag_index].get("_canvas", {})
        if callable(self.on_move):
            self.on_move(self._drag_index, layout.get("x"), layout.get("y"))
        self._drag_index = None


class ScenesPlanningStep(WizardStep):
    ENTITY_FIELDS = {
        "NPCs": ("npcs", "Key NPCs", "NPC"),
        "Creatures": ("creatures", "Creatures / Foes", "Creature"),
        "Places": ("places", "Locations / Places", "Place"),
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

    def __init__(self, master, entity_wrappers):
        super().__init__(master)
        self.entity_wrappers = entity_wrappers or {}
        self.scenes = []
        self.selected_index = None
        self._updating = False
        self._detail_panel_visible = True

        self.scenario_title_var = ctk.StringVar()
        self.scene_title_var = ctk.StringVar()
        self.scene_type_var = ctk.StringVar(value=self.SCENE_TYPES[0])
        self.link_var = ctk.StringVar()

        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(root, fg_color="#101827", corner_radius=14)
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(toolbar, text="Scenario Title", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        self.detail_toggle = ctk.CTkSwitch(
            toolbar,
            text="Show Details",
            command=self._toggle_detail_panel,
            onvalue=True,
            offvalue=False,
        )
        self.detail_toggle.grid(row=0, column=1, sticky="e", padx=(0, 16), pady=(12, 0))
        self.detail_toggle.select()
        self.scenario_title_entry = ctk.CTkEntry(toolbar, textvariable=self.scenario_title_var, font=ctk.CTkFont(size=18, weight="bold"))
        self.scenario_title_entry.grid(row=1, column=0, sticky="ew", padx=16)
        btn_row = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_row.grid(row=1, column=1, padx=16, pady=(0, 12))
        self.add_scene_btn = ctk.CTkButton(btn_row, text="Add Scene", command=self.add_scene)
        self.add_scene_btn.pack(side="left")
        self.dup_scene_btn = ctk.CTkButton(btn_row, text="Duplicate", command=self.duplicate_scene)
        self.dup_scene_btn.pack(side="left", padx=6)
        self.remove_scene_btn = ctk.CTkButton(btn_row, text="Remove", command=self.remove_scene)
        self.remove_scene_btn.pack(side="left")

        main = ctk.CTkFrame(root, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=0, minsize=580)
        main.grid_rowconfigure(0, weight=1)
        self._main_frame = main

        self.canvas = SceneCanvas(main, on_select=self._on_canvas_select, on_move=self._on_canvas_move)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.detail_panel = ctk.CTkFrame(main, width=580, fg_color="#101827", corner_radius=16)
        self.detail_panel.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.detail_panel.grid_rowconfigure(1, weight=0)
        self.detail_panel.grid_rowconfigure(3, weight=0)
        self.detail_panel.grid_rowconfigure(4, weight=1)
        self.detail_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.detail_panel, text="Scenario Overview", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 6))
        self.scenario_summary = ctk.CTkTextbox(self.detail_panel, height=120, wrap="word")
        self.scenario_summary.grid(row=1, column=0, sticky="nsew", padx=18)
        ctk.CTkLabel(self.detail_panel, text="Secrets", font=ctk.CTkFont(size=15, weight="bold")).grid(row=2, column=0, sticky="w", padx=18, pady=(12, 4))
        self.scenario_secrets = ctk.CTkTextbox(self.detail_panel, height=110, wrap="word")
        self.scenario_secrets.grid(row=3, column=0, sticky="nsew", padx=18)

        self.scene_section = ctk.CTkScrollableFrame(
            self.detail_panel,
            fg_color="#0f1624",
            corner_radius=14,
        )
        self.scene_section.grid(row=4, column=0, sticky="nsew", padx=18, pady=(18, 18))
        self.scene_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.scene_section, text="Selected Scene", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 4))
        self.scene_title_entry = ctk.CTkEntry(self.scene_section, textvariable=self.scene_title_var)
        self.scene_title_entry.grid(row=1, column=0, sticky="ew", padx=14)
        ctk.CTkLabel(self.scene_section, text="Scene Type", anchor="w").grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 2))
        self.scene_type_menu = ctk.CTkOptionMenu(self.scene_section, variable=self.scene_type_var, values=self.SCENE_TYPES, command=self._on_scene_type_change)
        self.scene_type_menu.grid(row=3, column=0, sticky="w", padx=14)
        ctk.CTkLabel(self.scene_section, text="Summary", anchor="w").grid(row=4, column=0, sticky="ew", padx=14, pady=(10, 2))
        self.scene_summary = ctk.CTkTextbox(self.scene_section, height=120, wrap="word")
        self.scene_summary.grid(row=5, column=0, sticky="ew", padx=14)

        ctk.CTkLabel(self.scene_section, text="Next Scenes", anchor="w").grid(row=6, column=0, sticky="ew", padx=14, pady=(12, 2))
        link_container = ctk.CTkFrame(self.scene_section, fg_color="transparent")
        link_container.grid(row=7, column=0, sticky="nsew", padx=14)
        link_container.grid_columnconfigure(0, weight=1)
        link_container.grid_rowconfigure(0, weight=1)
        self.link_list = tk.Listbox(
            link_container,
            activestyle="none",
            exportselection=False,
            height=6,
            selectmode="extended",
            highlightthickness=0,
            relief="flat",
            bg="#101827",
            fg="#FFFFFF",
            selectbackground="#1f3b67",
            selectforeground="#FFFFFF",
        )
        self.link_list.grid(row=0, column=0, sticky="nsew")
        link_scroll = tk.Scrollbar(link_container, orient="vertical", command=self.link_list.yview)
        link_scroll.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        self.link_list.configure(yscrollcommand=link_scroll.set)
        self.link_list.bind("<<ListboxSelect>>", self._on_link_selected)

        link_row = ctk.CTkFrame(self.scene_section, fg_color="transparent")
        link_row.grid(row=8, column=0, sticky="ew", padx=14, pady=(6, 0))
        link_row.grid_columnconfigure(0, weight=1)
        link_row.grid_columnconfigure(1, weight=1)
        self.link_combo = ctk.CTkComboBox(link_row, variable=self.link_var, values=[])
        self.link_combo.grid(row=0, column=0, sticky="ew")
        self.link_label_entry = ctk.CTkEntry(link_row, placeholder_text="Link text")
        self.link_label_entry.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkButton(link_row, text="Add", width=80, command=self._add_link).grid(row=0, column=2, padx=(6, 0))
        ctk.CTkButton(link_row, text="Update", width=90, command=self._update_link_label).grid(row=0, column=3, padx=(6, 0))

        ctk.CTkButton(self.scene_section, text="Remove Selected", command=self._remove_link).grid(row=9, column=0, sticky="w", padx=14, pady=(6, 0))

        self.entity_listboxes = {}
        row_index = 10
        for field, (entity_key, label, singular) in self.ENTITY_FIELDS.items():
            ctk.CTkLabel(self.scene_section, text=label, anchor="w").grid(row=row_index, column=0, sticky="ew", padx=14, pady=(12, 2))
            row_index += 1
            self.scene_section.grid_rowconfigure(row_index, weight=1)

            list_container = ctk.CTkFrame(self.scene_section, fg_color="transparent")
            list_container.grid(row=row_index, column=0, sticky="nsew", padx=14)
            list_container.grid_columnconfigure(0, weight=1)
            list_container.grid_rowconfigure(0, weight=1)

            listbox = tk.Listbox(
                list_container,
                activestyle="none",
                exportselection=False,
                height=6,
                highlightthickness=0,
                relief="flat",
                selectmode="extended",
                bg="#101827",
                fg="#FFFFFF",
                selectbackground="#1f3b67",
                selectforeground="#FFFFFF",
            )
            listbox.grid(row=0, column=0, sticky="nsew")
            scrollbar = tk.Scrollbar(list_container, orient="vertical", command=listbox.yview)
            scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 0))
            listbox.configure(yscrollcommand=scrollbar.set)
            self.entity_listboxes[field] = listbox

            row_index += 1
            control = ctk.CTkFrame(self.scene_section, fg_color="transparent")
            control.grid(row=row_index, column=0, sticky="ew", padx=14, pady=(6, 0))
            control.grid_columnconfigure((0, 1, 2), weight=1)

            ctk.CTkButton(
                control,
                text=f"Add {singular}",
                command=lambda f=field, lab=singular: self.open_entity_selector(f, lab),
            ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
            ctk.CTkButton(
                control,
                text="Create New",
                command=lambda f=field, et=entity_key, lab=singular: self.create_new_entity(et, f, lab),
            ).grid(row=0, column=1, sticky="ew", padx=(0, 6))
            ctk.CTkButton(
                control,
                text="Remove Selected",
                command=lambda f=field: self._remove_entity(f),
            ).grid(row=0, column=2, sticky="ew")

            row_index += 1
        self.scene_title_var.trace_add("write", self._on_scene_title_change)
        self._refresh_link_list()

    def _toggle_detail_panel(self, *_args) -> None:
        if getattr(self.detail_toggle, "get", lambda: True)():
            self._show_detail_panel()
        else:
            self._hide_detail_panel()

    def _show_detail_panel(self) -> None:
        if self._detail_panel_visible:
            return
        self.canvas.grid(row=0, column=0, columnspan=1, sticky="nsew")
        self.detail_panel.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        if hasattr(self, "_main_frame"):
            self._main_frame.grid_columnconfigure(1, weight=0, minsize=580)
        self._detail_panel_visible = True
        self.canvas._draw()

    def _hide_detail_panel(self) -> None:
        if not self._detail_panel_visible:
            return
        self.detail_panel.grid_remove()
        self.canvas.grid(row=0, column=0, columnspan=2, sticky="nsew")
        if hasattr(self, "_main_frame"):
            self._main_frame.grid_columnconfigure(1, weight=0, minsize=0)
        self._detail_panel_visible = False
        self.canvas._draw()

    # ------------------------------------------------------------------
    # Scene interactions
    # ------------------------------------------------------------------
    def _save_current_scene(self):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        scene = self.scenes[self.selected_index]
        scene["Title"] = self.scene_title_var.get().strip()
        selected_type = self.scene_type_var.get()
        scene["SceneType"] = "" if selected_type == self.SCENE_TYPES[0] else selected_type
        summary = self.scene_summary.get("1.0", "end").strip()
        scene["Summary"] = summary
        if summary and not scene.get("Text"):
            scene["Text"] = summary
        links = self._get_scene_links(scene)
        scene["LinkData"] = links
        scene["NextScenes"] = [link["target"] for link in links]

    def _load_scene(self, index):
        self._updating = True
        if index is None or index >= len(self.scenes):
            self.scene_title_var.set("")
            self.scene_type_var.set(self.SCENE_TYPES[0])
            self.scene_summary.delete("1.0", "end")
            self._refresh_entity_views()
            self._refresh_link_options()
            self._updating = False
            return
        scene = self.scenes[index]
        self.scene_title_var.set(scene.get("Title", ""))
        scene_type = scene.get("SceneType") or self.SCENE_TYPES[0]
        if scene_type not in self.SCENE_TYPES:
            scene_type = self.SCENE_TYPES[0]
        self.scene_type_var.set(scene_type)
        self.scene_summary.delete("1.0", "end")
        self.scene_summary.insert("1.0", scene.get("Summary", ""))
        self._refresh_entity_views()
        self._refresh_link_options()
        self._updating = False


    def _refresh_entity_views(self):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            for listbox in self.entity_listboxes.values():
                listbox.configure(state="normal")
                listbox.delete(0, tk.END)
                listbox.configure(state="disabled")
            self._refresh_link_list()
            return

        scene = self.scenes[self.selected_index]
        for field, listbox in self.entity_listboxes.items():
            values = scene.get(field, [])
            listbox.configure(state="normal")
            listbox.delete(0, tk.END)
            for name in values:
                listbox.insert(tk.END, name)
            if values:
                listbox.configure(state="normal")
            else:
                listbox.configure(state="disabled")
        self._refresh_link_list()

    def _refresh_link_list(self):
        self.link_list.delete(0, tk.END)
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            self.link_list.configure(state="disabled")
            if hasattr(self, 'link_label_entry'):
                self.link_label_entry.delete(0, tk.END)
            return

        scene = self.scenes[self.selected_index]
        links = self._get_scene_links(scene)
        self.link_list.configure(state="normal")
        self.link_label_entry.delete(0, tk.END)
        for link in links:
            target = link.get("target") or ""
            label = link.get("text") or target
            display = label if label == target else f"{label} -> {target}"
            self.link_list.insert(tk.END, display)
        self.link_list.selection_clear(0, tk.END)

    def _get_scene_links(self, scene):
        return normalise_scene_links(scene, self._split_to_list)

    def _on_link_selected(self, _event=None):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        selection = self.link_list.curselection()
        if not selection:
            return
        links = self._get_scene_links(self.scenes[self.selected_index])
        idx = selection[0]
        if 0 <= idx < len(links):
            label = links[idx].get("text") or links[idx].get("target")
            self.link_label_entry.delete(0, tk.END)
            self.link_label_entry.insert(0, label)

    def _update_link_label(self):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        selection = self.link_list.curselection()
        if not selection:
            return
        label = self.link_label_entry.get().strip()
        scene = self.scenes[self.selected_index]
        links = self._get_scene_links(scene)
        if not label:
            label = None
        for idx in selection:
            if 0 <= idx < len(links):
                links[idx]["text"] = label or links[idx]["target"]
        scene["LinkData"] = links
        scene["NextScenes"] = [link["target"] for link in links]
        self._refresh_link_list()
        self._refresh_canvas()

    def _refresh_link_options(self):
        options = []
        for idx, scene in enumerate(self.scenes):
            title = scene.get("Title") or f"Scene {idx + 1}"
            if idx != self.selected_index:
                options.append(title)
        current = (self.link_var.get() or "").strip()
        self.link_combo.configure(values=options)
        if current in options:
            self.link_combo.set(current)
        elif options:
            self.link_combo.set(options[0])
        else:
            self.link_combo.set("")

    def _on_canvas_select(self, index):
        self._save_current_scene()
        self.selected_index = index
        self.canvas.set_scenes(self.scenes, index)
        self._load_scene(index)
        self._update_buttons()

    def _on_canvas_move(self, index, x, y):
        if index is None or index >= len(self.scenes):
            return
        layout = self.scenes[index].setdefault("_canvas", {})
        layout["x"] = x
        layout["y"] = y

    def _on_scene_title_change(self, *_):
        if self._updating or self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        self.scenes[self.selected_index]["Title"] = self.scene_title_var.get().strip()
        self._refresh_link_options()
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _on_scene_type_change(self, value):
        if self._updating or self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        scene = self.scenes[self.selected_index]
        scene["SceneType"] = "" if value == self.SCENE_TYPES[0] else value
        self.canvas.set_scenes(self.scenes, self.selected_index)

    def _add_link(self):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        target = (self.link_var.get() or "").strip()
        if not target:
            return
        label = self.link_label_entry.get().strip() or target
        scene = self.scenes[self.selected_index]
        links = self._get_scene_links(scene)
        if any((link.get("target") == target and (link.get("text") or target) == label) for link in links):
            return
        links.append({"target": target, "text": label})
        scene["LinkData"] = links
        scene["NextScenes"] = [link["target"] for link in links]
        self._refresh_link_list()
        self._refresh_canvas()
        self.link_label_entry.delete(0, tk.END)

    def _remove_link(self):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        selection = self.link_list.curselection()
        if not selection:
            return
        scene = self.scenes[self.selected_index]
        links = self._get_scene_links(scene)
        for index in reversed(selection):
            if 0 <= index < len(links):
                links.pop(index)
        scene["LinkData"] = links
        scene["NextScenes"] = [link["target"] for link in links]
        self._refresh_link_list()
        self._refresh_canvas()


    def _remove_entity(self, field):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        listbox = self.entity_listboxes.get(field)
        if not listbox:
            return
        selection = listbox.curselection()
        if not selection:
            return
        entries = self.scenes[self.selected_index].get(field, [])
        for index in reversed(selection):
            if 0 <= index < len(entries):
                entries.pop(index)
        self._refresh_entity_views()
        self._refresh_canvas()

    def create_new_entity(self, entity_type, field, label):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            messagebox.showinfo("Select Scene", "Choose a scene card first.")
            return

        wrapper = self.entity_wrappers.get(entity_type)
        if not wrapper:
            messagebox.showerror("Unavailable", f"No {label} data available for creation.")
            return

        try:
            template = load_template(entity_type)
        except Exception as exc:
            log_exception(
                f"Failed to load template for {entity_type}: {exc}",
                func_name="ScenesPlanningStep.create_new_entity",
            )
            messagebox.showerror("Template Error", f"Unable to load the {label} template.")
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
                f"Failed to save {entity_type}: {exc}",
                func_name="ScenesPlanningStep.create_new_entity",
            )
            messagebox.showerror("Save Error", f"Unable to save the new {label}.")
            return

        if name:
            entries = self.scenes[self.selected_index].setdefault(field, [])
            if name not in entries:
                entries.append(name)
                self._refresh_entity_views()
                self._refresh_canvas()

    def add_scene(self):
        self._save_current_scene()
        scene = {
            "Title": f"Scene {len(self.scenes) + 1}",
            "Summary": "",
            "SceneType": "",
            "NPCs": [],
            "Creatures": [],
            "Places": [],
            "NextScenes": [],
            "LinkData": [],
        }
        self._assign_default_position(scene)
        self.scenes.append(scene)
        self.selected_index = len(self.scenes) - 1
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._load_scene(self.selected_index)
        self._update_buttons()

    def duplicate_scene(self):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        self._save_current_scene()
        source = copy.deepcopy(self.scenes[self.selected_index])
        source.pop("_canvas", None)
        dup = copy.deepcopy(source)
        dup["Title"] = self._unique_title(source.get("Title") or "Scene")
        self._assign_default_position(dup)
        insert_at = self.selected_index + 1
        self.scenes.insert(insert_at, dup)
        self.selected_index = insert_at
        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._load_scene(self.selected_index)
        self._update_buttons()

    def remove_scene(self):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        removed_scene = self.scenes.pop(self.selected_index)
        removed_title = (removed_scene.get("Title") or "").strip()

        for scene in self.scenes:
            links = self._get_scene_links(scene)
            filtered = [link for link in links if link.get("target") != removed_title]
            if len(filtered) != len(links):
                scene["LinkData"] = filtered
                scene["NextScenes"] = [link["target"] for link in filtered]

        if not self.scenes:
            self.selected_index = None
        elif self.selected_index >= len(self.scenes):
            self.selected_index = len(self.scenes) - 1

        self.canvas.set_scenes(self.scenes, self.selected_index)
        self._load_scene(self.selected_index)
        self._update_buttons()

    def _update_buttons(self):
        state = "normal" if self.selected_index is not None else "disabled"
        self.dup_scene_btn.configure(state=state)
        self.remove_scene_btn.configure(state=state)

    def _refresh_canvas(self):
        self.canvas.set_scenes(self.scenes, self.selected_index)

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
    # Entity selection
    # ------------------------------------------------------------------
    def open_entity_selector(self, field, singular_label):
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            messagebox.showinfo("Select Scene", "Choose a scene card first.")
            return
        wrapper_key = self.ENTITY_FIELDS[field][0]
        wrapper = self.entity_wrappers.get(wrapper_key)
        if not wrapper:
            messagebox.showerror("Unavailable", f"No {singular_label} library available")
            return
        template = load_template(wrapper_key)
        top = ctk.CTkToplevel(self)
        top.title(f"Select {singular_label}")
        top.geometry("1100x720")
        top.minsize(1100, 720)
        view = GenericListSelectionView(
            top,
            wrapper_key,
            wrapper,
            template,
            on_select_callback=lambda _et, name, win=top, fld=field: self._on_entity_selected(fld, name, win),
        )
        view.pack(fill="both", expand=True)
        top.transient(self.winfo_toplevel())
        top.grab_set()

    def _on_entity_selected(self, field, name, window):
        try:
            window.destroy()
        except Exception:
            pass
        if self.selected_index is None or self.selected_index >= len(self.scenes):
            return
        entries = self.scenes[self.selected_index].setdefault(field, [])
        if name not in entries:
            entries.append(name)
        self._refresh_entity_views()
        self.canvas.set_scenes(self.scenes, self.selected_index)

    # ------------------------------------------------------------------
    # WizardStep overrides
    # ------------------------------------------------------------------
    def load_state(self, state):
        self._updating = True
        self.scenario_title_var.set(state.get("Title", ""))
        self.scenario_summary.delete("1.0", "end")
        self.scenario_summary.insert("1.0", state.get("Summary", ""))
        secrets = state.get("Secrets") or state.get("Secret") or ""
        self.scenario_secrets.delete("1.0", "end")
        self.scenario_secrets.insert("1.0", secrets)
        self.scenes = self._coerce_scenes(state.get("Scenes"))
        layout = state.get("_SceneLayout")
        if isinstance(layout, list):
            for idx, scene in enumerate(self.scenes):
                if idx < len(layout) and isinstance(layout[idx], dict):
                    scene.setdefault("_canvas", {}).update(layout[idx])
        self.selected_index = None
        self.canvas.set_scenes(self.scenes, None)
        self._refresh_entity_views()
        self._refresh_link_options()
        self._update_buttons()
        self._updating = False

    def save_state(self, state):
        self._save_current_scene()
        state["Title"] = self.scenario_title_var.get().strip()
        summary = self.scenario_summary.get("1.0", "end").strip()
        secrets = self.scenario_secrets.get("1.0", "end").strip()
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
            payload.append(record)
            layout.append(scene.get("_canvas", {}))
        state["Scenes"] = payload
        state["_SceneLayout"] = layout

        for field in ("NPCs", "Creatures", "Places"):
            merged = self._dedupe(self._split_to_list(state.get(field, [])))
            for scene in self.scenes:
                merged.extend(scene.get(field, []))
            state[field] = self._dedupe(merged)
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
        scene = {
            "Title": entry.get("Title") or entry.get("Name") or f"Scene {index + 1}",
            "Summary": entry.get("Summary") or entry.get("Text") or "",
            "SceneType": entry.get("SceneType") or entry.get("Type") or "",
            "NPCs": self._split_to_list(entry.get("NPCs")),
            "Creatures": self._split_to_list(entry.get("Creatures")),
            "Places": self._split_to_list(entry.get("Places")),
            "NextScenes": [link["target"] for link in deduped],
            "LinkData": deduped,
        }
        return scene


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

        for field in ("NPCs", "Creatures", "Places", "Factions", "Objects"):
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
            (
                "Visual Builder",
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




