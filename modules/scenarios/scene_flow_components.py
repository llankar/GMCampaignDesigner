"""Reusable scene flow widgets and helpers shared across scenario tools."""

from __future__ import annotations

import textwrap
import tkinter as tk
from typing import Any, Callable, Optional

import customtkinter as ctk

from modules.helpers.text_helpers import coerce_text
from modules.scenarios.scene_flow_rendering import (
    SCENE_FLOW_BG,
    apply_scene_flow_canvas_styling,
    get_shadow_image,
)


def normalise_scene_links(scene: dict, split_to_list: Callable[[Any], list[str]]):
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


class SceneFlowPreview(ctk.CTkFrame):
    """Lightweight scene flow canvas used inside the wizard."""

    CARD_WIDTH = 220
    CARD_HEIGHT = 130
    GRID_SPACING = 48

    def __init__(self, master, *, on_select: Optional[Callable[[int], None]] = None):
        super().__init__(master, corner_radius=16, fg_color=("#0f1624", "#0f1624"))
        self.on_select = on_select
        self.scenes: list[dict[str, Any]] = []
        self.selected_index: Optional[int] = None
        self.node_regions: list[tuple[float, float, float, float, int]] = []

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
        positions: list[tuple[float, float]] = []
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
            summary_raw = scene.get("Summary") or scene.get("Text") or ""
            summary = coerce_text(summary_raw).replace("\n", " ").strip()
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
    CARD_W = 260
    CARD_H = 210

    def __init__(
        self,
        master,
        on_select: Optional[Callable[[Optional[int]], None]] = None,
        on_move: Optional[Callable[[int, float, float], None]] = None,
        on_edit: Optional[Callable[[int], None]] = None,
        on_context: Optional[Callable[[tk.Event, Optional[int]], None]] = None,
        on_add_entity: Optional[Callable[[int, str], None]] = None,
        on_link: Optional[Callable[[int, int], None]] = None,
        on_link_text_edit: Optional[Callable[[int, int, Any, tuple[float, float, float, float]], None]] = None,
    ):
        super().__init__(master, corner_radius=16, fg_color=SCENE_FLOW_BG)
        self.on_select = on_select
        self.on_move = on_move
        self.on_edit = on_edit
        self.on_context = on_context
        self.on_add_entity = on_add_entity
        self.on_link = on_link
        self.on_link_text_edit = on_link_text_edit
        self.scenes: list[dict[str, Any]] = []
        self.selected_index: Optional[int] = None
        self._drag_index: Optional[int] = None
        self._drag_mode: Optional[str] = None
        self._drag_offset = (0, 0)
        self._link_source_index: Optional[int] = None
        self._link_preview_line: Optional[int] = None
        self._link_preview_active = False
        self._grid_tile_cache: dict[str, object] = {}
        self._shadow_cache: dict[tuple, tuple] = {}
        self._image_refs: dict[str, object] = {}
        self._regions: list[tuple] = []
        self._move_regions: list[tuple] = []
        self._icon_regions: list[tuple] = []
        self._link_regions: list[tuple] = []
        self._positions: dict[int, tuple[float, float]] = {}

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
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._on_right_click)

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
        self._positions = {}
        for idx, scene in enumerate(self.scenes):
            layout = scene.get("_canvas", {})
            x = layout.get("x", width / 2)
            y = layout.get("y", height / 2)
            positions[idx] = (x, y)
            self._positions[idx] = (x, y)
            title = (scene.get("Title") or f"Scene {idx + 1}").strip().lower()
            title_lookup[title] = idx
        # links
        self._link_regions = []
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
                    text_id = c.create_text(
                        mx,
                        my - 14,
                        text=label_text,
                        fill="#9DB4D1",
                        font=("Segoe UI", 10, "bold" if idx == self.selected_index else "normal"),
                        tags=("link-label",),
                    )
                    bbox = c.bbox(text_id)
                    if bbox:
                        x1, y1, x2, y2 = bbox
                        self._link_regions.append(
                            (x1, y1, x2, y2, idx, target_idx, link.get("target"))
                        )
        # cards
        self._regions = []
        self._move_regions = []
        self._icon_regions = []
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
            self._move_regions.append((x1, y1, x2, y1 + 36, idx))
            summary_raw = scene.get("Summary") or scene.get("Text") or ""
            summary = " ".join(coerce_text(summary_raw).split())[:160]
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
            info_y = y1 + 116
            for label_key, items in (
                ("NPCs", scene.get("NPCs")),
                ("Creatures", scene.get("Creatures")),
                ("Places", scene.get("Places")),
            ):
                if items:
                    display = ", ".join(items[:4])
                    if len(items) > 4:
                        display += ", …"
                    c.create_text(
                        x1 + 14,
                        info_y,
                        text=f"{label_key}: {display}",
                        anchor="nw",
                        fill="#9bb8df",
                        font=("Segoe UI", 9, "bold" if idx == self.selected_index else "normal"),
                        width=self.CARD_W - 28,
                        tags=(f"scene-node-{idx}", "scene-node"),
                    )
                    info_y += 18
            icon_size = 24
            icon_spacing = 10
            icon_types = [
                ("NPCs", "N"),
                ("Creatures", "C"),
                ("Places", "P"),
            ]
            total_width = len(icon_types) * icon_size + (len(icon_types) - 1) * icon_spacing
            icon_start = x2 - total_width - 16
            for offset, (etype, label_char) in enumerate(icon_types):
                ix1 = icon_start + offset * (icon_size + icon_spacing)
                iy1 = y2 - icon_size - 12
                ix2 = ix1 + icon_size
                iy2 = iy1 + icon_size
                icon_id = c.create_oval(
                    ix1,
                    iy1,
                    ix2,
                    iy2,
                    fill="#203758",
                    outline="#6ab2ff" if idx == self.selected_index else "#30435f",
                    width=2,
                    tags=("scene-node",),
                )
                c.create_text(
                    (ix1 + ix2) / 2,
                    (iy1 + iy2) / 2,
                    text="+" + label_char,
                    fill="#d8e6ff",
                    font=("Segoe UI", 9, "bold"),
                    tags=("scene-node",),
                )
                self._icon_regions.append((ix1, iy1, ix2, iy2, idx, etype))
            self._regions.append((x1, y1, x2, y2, idx))

    def _hit_test(self, x, y):
        for x1, y1, x2, y2, idx in reversed(self._regions):
            if x1 <= x <= x2 and y1 <= y <= y2:
                return idx
        return None

    def _hit_icon(self, x, y):
        for x1, y1, x2, y2, idx, etype in self._icon_regions:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return idx, etype
        return None, None

    def get_card_bbox(self, index):
        for x1, y1, x2, y2, idx in self._regions:
            if idx == index:
                return x1, y1, x2, y2
        return None

    def _get_link_anchor(self, idx):
        position = self._positions.get(idx)
        if not position:
            return 0, 0
        x, y = position
        return x + self.CARD_W / 2 - 12, y

    def _select_index(self, idx, redraw_on_none=True):
        if self.selected_index != idx:
            self.selected_index = idx
            if callable(self.on_select):
                self.on_select(idx)
            elif redraw_on_none:
                self._draw()
        elif idx is None and redraw_on_none:
            self._draw()

    def _on_click(self, event):
        # Allow direct link label editing on single click for better accessibility
        for x1, y1, x2, y2, source_idx, target_idx, target_value in self._link_regions:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if callable(self.on_link_text_edit):
                    self.on_link_text_edit(
                        source_idx,
                        target_idx,
                        target_value,
                        (x1, y1, x2, y2),
                    )
                return

        icon_idx, icon_type = self._hit_icon(event.x, event.y)
        if icon_idx is not None:
            self._select_index(icon_idx)
            if callable(self.on_add_entity):
                self.on_add_entity(icon_idx, icon_type)
            self._drag_index = None
            self._drag_mode = None
            return

        idx = self._hit_test(event.x, event.y)
        self._drag_index = None
        self._drag_mode = None
        self._link_source_index = None
        self._link_preview_active = False
        if idx is not None:
            region = next((r for r in self._regions if r[4] == idx), None)
            if region:
                x1, y1, x2, y2, _ = region
                move_region = next((r for r in self._move_regions if r[4] == idx), None)
                if move_region and move_region[1] <= event.y <= move_region[3]:
                    self._drag_mode = "move"
                    self._drag_index = idx
                    layout = self.scenes[idx].setdefault("_canvas", {})
                    layout.setdefault("x", (x1 + x2) / 2)
                    layout.setdefault("y", (y1 + y2) / 2)
                    self._drag_offset = (event.x - layout["x"], event.y - layout["y"])
                else:
                    self._drag_mode = "link"
                    self._link_source_index = idx
        self._select_index(idx)

    def _on_drag(self, event):
        if self._drag_mode == "move" and self._drag_index is not None:
            layout = self.scenes[self._drag_index].setdefault("_canvas", {})
            layout["x"] = event.x - self._drag_offset[0]
            layout["y"] = event.y - self._drag_offset[1]
            self._draw()
        elif self._drag_mode == "link" and self._link_source_index is not None:
            anchor = self._get_link_anchor(self._link_source_index)
            if not self._link_preview_active:
                self._link_preview_active = True
                self._link_preview_line = self.canvas.create_line(
                    anchor[0],
                    anchor[1],
                    event.x,
                    event.y,
                    dash=(6, 4),
                    width=2,
                    fill="#6ab2ff",
                    arrow=tk.LAST,
                    arrowshape=(12, 14, 6),
                )
            else:
                self.canvas.coords(self._link_preview_line, anchor[0], anchor[1], event.x, event.y)
        else:
            return

    def _on_release(self, event):
        if self._drag_mode == "move" and self._drag_index is not None:
            layout = self.scenes[self._drag_index].get("_canvas", {})
            if callable(self.on_move):
                self.on_move(self._drag_index, layout.get("x"), layout.get("y"))
        elif self._drag_mode == "link" and self._link_source_index is not None:
            if self._link_preview_line is not None:
                self.canvas.delete(self._link_preview_line)
            self._link_preview_line = None
            if self._link_preview_active:
                target_idx = self._hit_test(event.x, event.y)
                if (
                    target_idx is not None
                    and target_idx != self._link_source_index
                    and callable(self.on_link)
                ):
                    self.on_link(self._link_source_index, target_idx)
        self._drag_mode = None
        self._drag_index = None
        self._link_source_index = None
        self._link_preview_active = False

    def _on_double_click(self, event):
        for x1, y1, x2, y2, source_idx, target_idx, target_value in self._link_regions:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if callable(self.on_link_text_edit):
                    self.on_link_text_edit(
                        source_idx,
                        target_idx,
                        target_value,
                        (x1, y1, x2, y2),
                    )
                return
        idx = self._hit_test(event.x, event.y)
        if idx is not None:
            self._select_index(idx)
            if callable(self.on_edit):
                self.on_edit(idx)

    def _on_right_click(self, event):
        idx = self._hit_test(event.x, event.y)
        if idx is not None:
            self._select_index(idx, redraw_on_none=False)
        else:
            self._select_index(None, redraw_on_none=False)
        if callable(self.on_context):
            self.on_context(event, idx)


__all__ = ["normalise_scene_links", "SceneFlowPreview", "SceneCanvas"]
