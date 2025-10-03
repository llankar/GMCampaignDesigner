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

    CARD_WIDTH = 260
    CARD_MIN_HEIGHT = 190
    GRID_SPACING = 48
    TITLE_TOP_PADDING = 18
    HORIZONTAL_PADDING = 18
    TITLE_SUMMARY_GAP = 12
    SUMMARY_ENTITY_GAP = 12
    ENTITY_LINE_GAP = 6
    ICON_SECTION_GAP = 16
    ICON_SIZE = 26
    CARD_BOTTOM_PADDING = 18

    def __init__(self, master, *, on_select: Optional[Callable[[int], None]] = None):
        super().__init__(master, corner_radius=16, fg_color=(SCENE_FLOW_BG, SCENE_FLOW_BG))
        self.on_select = on_select
        self.scenes: list[dict[str, Any]] = []
        self.selected_index: Optional[int] = None
        self.node_regions: list[tuple[float, float, float, float, int]] = []
        self._grid_tile_cache: dict[str, object] = {}
        self._shadow_cache: dict[tuple, tuple] = {}
        self._image_refs: dict[str, object] = {}
        self._is_panning = False

        self.canvas = tk.Canvas(self, bg=SCENE_FLOW_BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas.bind("<Configure>", lambda _event: self._draw())
        self.canvas.bind("<Button-1>", self._handle_click)
        self.canvas.bind("<Button-2>", self._on_middle_press)
        self.canvas.bind("<B2-Motion>", self._on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self._on_middle_release)

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
        tile = apply_scene_flow_canvas_styling(
            self.canvas,
            tile_cache=self._grid_tile_cache,
            extent_width=width,
            extent_height=height,
        )
        if tile is not None:
            self._image_refs["grid"] = tile

        if not self.scenes:
            self.canvas.create_text(
                width / 2,
                height / 2,
                text="Add scenes to see the story flow visualised here",
                fill="#8ba6d0",
                font=("Segoe UI", 16, "bold"),
            )
            self.canvas.configure(scrollregion=(0, 0, width, height))
            return

        columns = max(1, min(4, (width - 180) // (self.CARD_WIDTH + 70)))
        positions: list[tuple[float, float]] = []
        for idx, _ in enumerate(self.scenes):
            col = idx % columns
            row = idx // columns
            x = 120 + col * (self.CARD_WIDTH + 70) + self.CARD_WIDTH / 2
            y = 130 + row * (self.CARD_MIN_HEIGHT + 150)
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

        card_models = [
            self._build_card_model(scene, idx, idx == self.selected_index)
            for idx, scene in enumerate(self.scenes)
        ]

        for idx, scene in enumerate(self.scenes):
            start = positions[idx]
            for target in scene.get("NextScenes") or []:
                resolved = resolve_target(target)
                if resolved is None or resolved >= len(positions):
                    continue
                end = positions[resolved]
                color = "#68b3ff" if idx == self.selected_index else "#3b587a"
                control_x = (start[0] + end[0]) / 2
                control_y = min(start[1], end[1]) - 60
                self.canvas.create_line(
                    start[0],
                    start[1] + card_models[idx]["half_height"],
                    control_x,
                    control_y,
                    end[0],
                    end[1] - card_models[resolved]["half_height"],
                    fill=color,
                    width=2.4 if idx == self.selected_index else 2.0,
                    smooth=True,
                    arrow=tk.LAST,
                    arrowshape=(16, 18, 7),
                )

        for idx, scene in enumerate(self.scenes):
            x, y = positions[idx]
            selected = idx == self.selected_index
            model = card_models[idx]
            half_height = model["half_height"]
            x1 = x - self.CARD_WIDTH / 2
            y1 = y - half_height
            x2 = x + self.CARD_WIDTH / 2
            y2 = y + half_height

            shadow_image, offset = get_shadow_image(
                self.canvas,
                self._shadow_cache,
                self.CARD_WIDTH,
                half_height * 2,
                1.0,
            )
            if shadow_image is not None:
                shadow_id = self.canvas.create_image(
                    x1 - offset,
                    y1 - offset,
                    image=shadow_image,
                    anchor="nw",
                )
                self.canvas.tag_lower(shadow_id)
                self._image_refs[f"shadow-{idx}"] = shadow_image

            bg = "#1e2a40" if selected else "#151d2f"
            border = "#75beff" if selected else "#273750"
            card_id = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=bg,
                outline=border,
                width=3 if selected else 2,
                tags=(f"scene-node-{idx}", "scene-node"),
            )
            self.canvas.tag_raise(card_id)

            current_x = x1 + self.HORIZONTAL_PADDING
            current_y = y1 + self.TITLE_TOP_PADDING

            scene_type = model["scene_type"]
            if scene_type:
                max_chip_width = self.CARD_WIDTH - 2 * self.HORIZONTAL_PADDING
                type_width = min(
                    max_chip_width,
                    max(96, len(scene_type) * 7 + 30),
                )
                self.canvas.create_rectangle(
                    current_x,
                    current_y - 6,
                    current_x + type_width,
                    current_y + 18,
                    fill="#25507f",
                    outline="",
                    tags=(f"scene-node-{idx}", "scene-node"),
                )
                self.canvas.create_text(
                    current_x + type_width / 2,
                    current_y + 6,
                    text=scene_type,
                    fill="#f4f8ff",
                    font=("Segoe UI", 9, "bold"),
                    tags=(f"scene-node-{idx}", "scene-node"),
                )
                current_y += 22

            title = model["title"]
            title_id = self.canvas.create_text(
                current_x,
                current_y,
                text=title,
                fill="#f7f9ff",
                font=("Segoe UI", 13, "bold"),
                anchor="nw",
                width=self.CARD_WIDTH - 2 * self.HORIZONTAL_PADDING,
                tags=(f"scene-node-{idx}", "scene-node"),
            )
            bbox = self.canvas.bbox(title_id)
            if bbox:
                current_y = bbox[3]
            else:
                current_y += 24

            summary = model["summary"]
            if summary:
                current_y += self.TITLE_SUMMARY_GAP
                summary_id = self.canvas.create_text(
                    current_x,
                    current_y,
                    text=summary,
                    fill="#9fb3d7",
                    font=("Segoe UI", 10),
                    anchor="nw",
                    width=self.CARD_WIDTH - 2 * self.HORIZONTAL_PADDING,
                    tags=(f"scene-node-{idx}", "scene-node"),
                )
                summary_bbox = self.canvas.bbox(summary_id)
                if summary_bbox:
                    current_y = summary_bbox[3]

            entity_lines = model["entity_lines"]
            if entity_lines:
                current_y += self.SUMMARY_ENTITY_GAP
                entity_font = ("Segoe UI", 9, "bold" if selected else "normal")
                for line_index, line in enumerate(entity_lines):
                    entity_id = self.canvas.create_text(
                        current_x,
                        current_y,
                        text=line,
                        fill="#8fa6cc",
                        font=entity_font,
                        anchor="nw",
                        width=self.CARD_WIDTH - 2 * self.HORIZONTAL_PADDING,
                        tags=(f"scene-node-{idx}", "scene-node"),
                    )
                    line_bbox = self.canvas.bbox(entity_id)
                    if line_bbox:
                        current_y = line_bbox[3]
                    if line_index != len(entity_lines) - 1:
                        current_y += self.ENTITY_LINE_GAP

            badges = model["badges"]
            if badges:
                current_y += self.ICON_SECTION_GAP
                spacing = 12
                total_width = len(badges) * self.ICON_SIZE + (len(badges) - 1) * spacing
                start_x = x2 - total_width - self.HORIZONTAL_PADDING
                for offset, (label_char, active) in enumerate(badges):
                    ix1 = start_x + offset * (self.ICON_SIZE + spacing)
                    iy1 = current_y
                    ix2 = ix1 + self.ICON_SIZE
                    iy2 = iy1 + self.ICON_SIZE
                    fill = "#27466d" if active else "#1c2940"
                    outline = "#75beff" if selected and active else "#2f3f5b"
                    oval = self.canvas.create_oval(
                        ix1,
                        iy1,
                        ix2,
                        iy2,
                        fill=fill,
                        outline=outline,
                        width=2,
                        tags=(f"scene-node-{idx}", "scene-node"),
                    )
                    self.canvas.tag_raise(oval)
                    self.canvas.create_text(
                        (ix1 + ix2) / 2,
                        (iy1 + iy2) / 2,
                        text=label_char,
                        fill="#d5e4ff" if active else "#64769a",
                        font=("Segoe UI", 10, "bold"),
                        tags=(f"scene-node-{idx}", "scene-node"),
                    )
                current_y += self.ICON_SIZE

            current_y += self.CARD_BOTTOM_PADDING
            final_bottom = max(y2, current_y)
            if final_bottom != y2:
                y2 = final_bottom
                self.canvas.coords(card_id, x1, y1, x2, y2)

            self.node_regions.append((x1, y1, x2, y2, idx))

        bbox = self.canvas.bbox("all")
        if bbox:
            x1, y1, x2, y2 = bbox
            margin = 160
            self.canvas.configure(scrollregion=(x1 - margin, y1 - margin, x2 + margin, y2 + margin))
        else:
            self.canvas.configure(scrollregion=(0, 0, width, height))

    def _handle_click(self, event):
        for x1, y1, x2, y2, idx in self.node_regions:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if callable(self.on_select):
                    self.on_select(idx)
                break

    def _on_middle_press(self, event):
        self._is_panning = True
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.configure(cursor="fleur")
        return "break"

    def _on_middle_drag(self, event):
        if not self._is_panning:
            return
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        return "break"

    def _on_middle_release(self, _event):
        if not self._is_panning:
            return
        self._is_panning = False
        self.canvas.configure(cursor="")
        return "break"

    def _build_card_model(
        self, scene: dict[str, Any], index: int, selected: bool
    ) -> dict[str, Any]:
        title_raw = scene.get("Title") or scene.get("title") or ""
        title_default = f"Scene {index + 1}" if index >= 0 else "Scene"
        title = str(title_raw).strip() or title_default
        scene_type = (
            scene.get("SceneType")
            or scene.get("Type")
            or scene.get("Scene Tag")
            or ""
        )
        scene_type_display = str(scene_type).strip().upper()
        summary = self._prepare_summary(scene)
        entity_lines = self._prepare_entity_lines(scene)
        badges = self._prepare_icon_badges(scene)
        half_height = self._compute_card_half_height(
            title,
            summary,
            entity_lines,
            bool(scene_type_display),
            len(badges),
            selected,
        )
        return {
            "title": title,
            "scene_type": scene_type_display,
            "summary": summary,
            "entity_lines": entity_lines,
            "badges": badges,
            "half_height": half_height,
        }

    def _compute_card_half_height(
        self,
        title: str,
        summary: str,
        entity_lines: list[str],
        has_type: bool,
        badge_count: int,
        selected: bool,
    ) -> float:
        width = self.CARD_WIDTH - 2 * self.HORIZONTAL_PADDING
        total_height = self.TITLE_TOP_PADDING
        if has_type:
            total_height += 22
        total_height += self._measure_text_height(
            self.canvas, title, ("Segoe UI", 13, "bold"), width
        )
        if summary:
            total_height += self.TITLE_SUMMARY_GAP
            total_height += self._measure_text_height(
                self.canvas, summary, ("Segoe UI", 10), width
            )
        if entity_lines:
            total_height += self.SUMMARY_ENTITY_GAP
            entity_font = ("Segoe UI", 9, "bold" if selected else "normal")
            for index, line in enumerate(entity_lines):
                total_height += self._measure_text_height(
                    self.canvas, line, entity_font, width
                )
                if index < len(entity_lines) - 1:
                    total_height += self.ENTITY_LINE_GAP
        if badge_count:
            total_height += self.ICON_SECTION_GAP + self.ICON_SIZE
        total_height += self.CARD_BOTTOM_PADDING
        total_height = max(float(self.CARD_MIN_HEIGHT), total_height)
        return total_height / 2.0

    def _prepare_summary(self, scene: dict[str, Any]) -> str:
        summary_sources = (
            scene.get("Summary"),
            scene.get("SceneSummary"),
            scene.get("Synopsis"),
            scene.get("Text"),
            scene.get("SceneText"),
            scene.get("Description"),
            scene.get("Details"),
            scene.get("SceneDetails"),
            scene.get("Body"),
            scene.get("Notes"),
        )
        for candidate in summary_sources:
            text = coerce_text(candidate).strip()
            if text:
                try:
                    return textwrap.shorten(text, width=170, placeholder="…")
                except ValueError:
                    return text[:167] + "…" if len(text) > 170 else text
        return "Click to outline this beat."

    def _prepare_entity_lines(self, scene: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        display_order = getattr(SceneCanvas, "ENTITY_DISPLAY_ORDER", ())
        for label_key in display_order:
            items = scene.get(label_key)
            if not items:
                continue
            if isinstance(items, str):
                values = [items]
            elif isinstance(items, (list, tuple, set)):
                values = items
            else:
                values = [items]
            display_items = [
                str(item).strip()
                for item in values
                if str(item).strip()
            ]
            if not display_items:
                continue
            display = ", ".join(display_items[:3])
            if len(display_items) > 3:
                display += ", …"
            lines.append(f"{label_key}: {display}")
        return lines

    def _prepare_icon_badges(self, scene: dict[str, Any]) -> list[tuple[str, bool]]:
        badges: list[tuple[str, bool]] = []
        icon_labels = getattr(SceneCanvas, "ICON_LABELS", {})
        for key, label_char in icon_labels.items():
            items = scene.get(key)
            if isinstance(items, str):
                active = bool(items.strip())
            elif isinstance(items, (list, tuple, set)):
                active = any(str(item).strip() for item in items)
            else:
                active = bool(items)
            if not active:
                continue
            badges.append((label_char, True))
        return badges

    def _measure_text_height(
        self, canvas: tk.Canvas, text: str, font: tuple, width: int
    ) -> float:
        if not text:
            return 0.0
        text_id = canvas.create_text(
            0,
            0,
            text=text,
            font=font,
            width=width,
            anchor="nw",
            state="hidden",
        )
        bbox = canvas.bbox(text_id)
        canvas.delete(text_id)
        if not bbox:
            return 0.0
        return float(bbox[3] - bbox[1])


class SceneCanvas(ctk.CTkFrame):
    GRID = 60
    CARD_W = 260
    CARD_MIN_H = 210
    SUMMARY_MAX_CHARS = 320
    TITLE_TOP_PADDING = 18
    HORIZONTAL_PADDING = 14
    TITLE_SUMMARY_GAP = 12
    SUMMARY_ENTITY_GAP = 12
    ENTITY_LINE_GAP = 6
    ICON_SECTION_GAP = 14
    ICON_SIZE = 24
    BOTTOM_PADDING = 16
    ICON_LABELS = {
        "NPCs": "N",
        "Creatures": "C",
        "Places": "P",
        "Maps": "M",
    }
    ENTITY_DISPLAY_ORDER = ("NPCs", "Creatures", "Places", "Maps")

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
        available_entity_types: Optional[tuple[str, ...] | list[str]] = None,
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
        self._is_panning = False
        if available_entity_types is None:
            available_entity_types = ("NPCs", "Creatures", "Places")
        self.available_entity_types = [
            entity
            for entity in available_entity_types
            if entity in self.ICON_LABELS
        ]
        if not self.available_entity_types:
            self.available_entity_types = ["NPCs", "Creatures", "Places"]

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
        self.canvas.bind("<Button-2>", self._on_middle_press)
        self.canvas.bind("<B2-Motion>", self._on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self._on_middle_release)

    def set_scenes(self, scenes, selected_index=None):
        self.scenes = scenes or []
        self.selected_index = selected_index if isinstance(selected_index, int) else None
        self._ensure_positions()
        self._draw()

    def _event_coords(self, event: tk.Event) -> tuple[float, float]:
        """Return the canvas-space coordinates for ``event``."""

        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _ensure_positions(self):
        if not self.scenes:
            return
        spacing_x = self.CARD_W + 160
        spacing_y = self.CARD_MIN_H + 140
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
            extent_height=max(height, self.CARD_MIN_H * 4),
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
            selected = idx == self.selected_index
            x, y = positions[idx]
            title = scene.get("Title") or f"Scene {idx + 1}"
            summary_raw = scene.get("Summary") or scene.get("Text") or ""
            summary_full = " ".join(coerce_text(summary_raw).split())
            summary_display = self._truncate_inline_summary(summary_full)
            entity_lines = self._prepare_entity_lines(scene)
            icon_types = [
                (etype, self.ICON_LABELS[etype])
                for etype in self.available_entity_types
                if etype in self.ICON_LABELS
            ]
            card_height = self._compute_card_height(
                c,
                title,
                summary_display,
                entity_lines,
                icon_types,
                selected=selected,
            )
            x1 = x - self.CARD_W / 2
            x2 = x + self.CARD_W / 2
            y1 = y - card_height / 2
            y2 = y + card_height / 2
            shadow_image, offset = get_shadow_image(
                c, self._shadow_cache, self.CARD_W, card_height, 1.0
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

            bg = "#1f2a40" if selected else "#151e30"
            border = "#6ab2ff" if selected else "#273750"
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
            content_x = x1 + self.HORIZONTAL_PADDING
            current_y = y1 + self.TITLE_TOP_PADDING
            title_id = c.create_text(
                content_x,
                current_y,
                text=title,
                anchor="nw",
                fill="#f8fafc",
                font=("Segoe UI", 13, "bold"),
                width=self.CARD_W - 2 * self.HORIZONTAL_PADDING,
                tags=(f"scene-node-{idx}", "scene-node"),
            )
            title_bbox = c.bbox(title_id)
            if title_bbox:
                title_bottom = title_bbox[3]
            else:
                title_bottom = y1 + self.TITLE_TOP_PADDING + self._measure_text_height(
                    c,
                    title,
                    ("Segoe UI", 13, "bold"),
                    self.CARD_W - 2 * self.HORIZONTAL_PADDING,
                )
            title_bottom = max(title_bottom, y1 + 36)
            self._move_regions.append((x1, y1, x2, title_bottom, idx))
            current_y = title_bottom
            if summary_display:
                current_y += self.TITLE_SUMMARY_GAP
                summary_id = c.create_text(
                    content_x,
                    current_y,
                    text=summary_display,
                    anchor="nw",
                    fill="#c5d4f5",
                    font=("Segoe UI", 10),
                    width=self.CARD_W - 2 * self.HORIZONTAL_PADDING,
                    tags=(f"scene-node-{idx}", "scene-node"),
                )
                summary_bbox = c.bbox(summary_id)
                if summary_bbox:
                    current_y = summary_bbox[3]
            if entity_lines:
                current_y += self.SUMMARY_ENTITY_GAP
                entity_font = ("Segoe UI", 9, "bold" if selected else "normal")
                for line_index, line in enumerate(entity_lines):
                    entity_id = c.create_text(
                        content_x,
                        current_y,
                        text=line,
                        anchor="nw",
                        fill="#9bb8df",
                        font=entity_font,
                        width=self.CARD_W - 2 * self.HORIZONTAL_PADDING,
                        tags=(f"scene-node-{idx}", "scene-node"),
                    )
                    entity_bbox = c.bbox(entity_id)
                    if entity_bbox:
                        current_y = entity_bbox[3]
                    if line_index != len(entity_lines) - 1:
                        current_y += self.ENTITY_LINE_GAP
            icon_spacing = 10
            if icon_types:
                current_y += self.ICON_SECTION_GAP
                total_width = (
                    len(icon_types) * self.ICON_SIZE
                    + (len(icon_types) - 1) * icon_spacing
                )
                icon_start = x2 - total_width - self.HORIZONTAL_PADDING
                for offset, (etype, label_char) in enumerate(icon_types):
                    ix1 = icon_start + offset * (self.ICON_SIZE + icon_spacing)
                    iy1 = current_y
                    ix2 = ix1 + self.ICON_SIZE
                    iy2 = iy1 + self.ICON_SIZE
                    icon_id = c.create_oval(
                        ix1,
                        iy1,
                        ix2,
                        iy2,
                        fill="#203758",
                        outline="#6ab2ff" if selected else "#30435f",
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
                current_y += self.ICON_SIZE
            current_y += self.BOTTOM_PADDING
            final_bottom = max(y2, current_y)
            if final_bottom != y2:
                y2 = final_bottom
                c.coords(card_id, x1, y1, x2, y2)
            self._regions.append((x1, y1, x2, y2, idx))

        bbox = c.bbox("all")
        if bbox:
            x1, y1, x2, y2 = bbox
            margin = 200
            c.configure(scrollregion=(x1 - margin, y1 - margin, x2 + margin, y2 + margin))
        else:
            c.configure(scrollregion=(0, 0, width, height))

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

    def _truncate_inline_summary(self, text: str) -> str:
        collapsed = text.strip()
        if not collapsed:
            return ""
        if len(collapsed) <= self.SUMMARY_MAX_CHARS:
            return collapsed
        try:
            return textwrap.shorten(collapsed, width=self.SUMMARY_MAX_CHARS, placeholder="...")
        except ValueError:
            return collapsed[: self.SUMMARY_MAX_CHARS - 3] + "..."

    def _prepare_entity_lines(self, scene: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        for label_key in self.ENTITY_DISPLAY_ORDER:
            items = scene.get(label_key)
            if not items:
                continue
            if isinstance(items, str):
                items = [items]
            display_items = [
                str(item).strip()
                for item in items
                if str(item).strip()
            ]
            if not display_items:
                continue
            display = ", ".join(display_items[:4])
            if len(display_items) > 4:
                display += ", …"
            lines.append(f"{label_key}: {display}")
        return lines

    def _measure_text_height(self, canvas: tk.Canvas, text: str, font: tuple, width: int) -> float:
        if not text:
            return 0.0
        text_id = canvas.create_text(
            0,
            0,
            text=text,
            font=font,
            width=width,
            anchor="nw",
            state="hidden",
        )
        bbox = canvas.bbox(text_id)
        canvas.delete(text_id)
        if not bbox:
            return 0.0
        return float(bbox[3] - bbox[1])

    def _compute_card_height(
        self,
        canvas: tk.Canvas,
        title: str,
        summary_text: str,
        entity_lines: list[str],
        icon_types: list[tuple[str, str]],
        *,
        selected: bool,
    ) -> float:
        width = self.CARD_W - 2 * self.HORIZONTAL_PADDING
        height = self.TITLE_TOP_PADDING
        height += self._measure_text_height(canvas, title, ("Segoe UI", 13, "bold"), width)
        if summary_text:
            height += self.TITLE_SUMMARY_GAP
            height += self._measure_text_height(canvas, summary_text, ("Segoe UI", 10), width)
        if entity_lines:
            height += self.SUMMARY_ENTITY_GAP
            entity_font = ("Segoe UI", 9, "bold" if selected else "normal")
            for index, line in enumerate(entity_lines):
                height += self._measure_text_height(canvas, line, entity_font, width)
                if index < len(entity_lines) - 1:
                    height += self.ENTITY_LINE_GAP
        if icon_types:
            height += self.ICON_SECTION_GAP + self.ICON_SIZE
        height += self.BOTTOM_PADDING
        return max(self.CARD_MIN_H, height)

    def _select_index(self, idx, redraw_on_none=True):
        if self.selected_index != idx:
            self.selected_index = idx
            if callable(self.on_select):
                self.on_select(idx)
            elif redraw_on_none:
                self._draw()
        elif idx is None and redraw_on_none:
            self._draw()

    def _on_middle_press(self, event):
        if self._link_preview_line is not None:
            self.canvas.delete(self._link_preview_line)
            self._link_preview_line = None
        self._drag_mode = None
        self._drag_index = None
        self._link_source_index = None
        self._link_preview_active = False
        self._is_panning = True
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.configure(cursor="fleur")
        return "break"

    def _on_middle_drag(self, event):
        if not self._is_panning:
            return
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        return "break"

    def _on_middle_release(self, _event):
        if not self._is_panning:
            return
        self._is_panning = False
        self.canvas.configure(cursor="")
        return "break"

    def _on_click(self, event):
        # Allow direct link label editing on single click for better accessibility
        event_x, event_y = self._event_coords(event)

        for x1, y1, x2, y2, source_idx, target_idx, target_value in self._link_regions:
            if x1 <= event_x <= x2 and y1 <= event_y <= y2:
                if callable(self.on_link_text_edit):
                    self.on_link_text_edit(
                        source_idx,
                        target_idx,
                        target_value,
                        (x1, y1, x2, y2),
                    )
                return

        icon_idx, icon_type = self._hit_icon(event_x, event_y)
        if icon_idx is not None:
            self._select_index(icon_idx)
            if callable(self.on_add_entity):
                self.on_add_entity(icon_idx, icon_type)
            self._drag_index = None
            self._drag_mode = None
            return

        idx = self._hit_test(event_x, event_y)
        self._drag_index = None
        self._drag_mode = None
        self._link_source_index = None
        self._link_preview_active = False
        if idx is not None:
            region = next((r for r in self._regions if r[4] == idx), None)
            if region:
                x1, y1, x2, y2, _ = region
                move_region = next((r for r in self._move_regions if r[4] == idx), None)
                if move_region and move_region[1] <= event_y <= move_region[3]:
                    self._drag_mode = "move"
                    self._drag_index = idx
                    layout = self.scenes[idx].setdefault("_canvas", {})
                    layout.setdefault("x", (x1 + x2) / 2)
                    layout.setdefault("y", (y1 + y2) / 2)
                    self._drag_offset = (
                        event_x - layout.get("x", 0),
                        event_y - layout.get("y", 0),
                    )
                else:
                    self._drag_mode = "link"
                    self._link_source_index = idx
        self._select_index(idx)

    def _on_drag(self, event):
        event_x, event_y = self._event_coords(event)
        if self._drag_mode == "move" and self._drag_index is not None:
            layout = self.scenes[self._drag_index].setdefault("_canvas", {})
            layout["x"] = event_x - self._drag_offset[0]
            layout["y"] = event_y - self._drag_offset[1]
            self._draw()
        elif self._drag_mode == "link" and self._link_source_index is not None:
            anchor = self._get_link_anchor(self._link_source_index)
            if not self._link_preview_active:
                self._link_preview_active = True
                self._link_preview_line = self.canvas.create_line(
                    anchor[0],
                    anchor[1],
                    event_x,
                    event_y,
                    dash=(6, 4),
                    width=2,
                    fill="#6ab2ff",
                    arrow=tk.LAST,
                    arrowshape=(12, 14, 6),
                )
            else:
                self.canvas.coords(
                    self._link_preview_line,
                    anchor[0],
                    anchor[1],
                    event_x,
                    event_y,
                )
        else:
            return

    def _on_release(self, event):
        event_x, event_y = self._event_coords(event)
        if self._drag_mode == "move" and self._drag_index is not None:
            layout = self.scenes[self._drag_index].get("_canvas", {})
            if callable(self.on_move):
                self.on_move(self._drag_index, layout.get("x"), layout.get("y"))
        elif self._drag_mode == "link" and self._link_source_index is not None:
            if self._link_preview_line is not None:
                self.canvas.delete(self._link_preview_line)
            self._link_preview_line = None
            if self._link_preview_active:
                target_idx = self._hit_test(event_x, event_y)
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
        event_x, event_y = self._event_coords(event)
        for x1, y1, x2, y2, source_idx, target_idx, target_value in self._link_regions:
            if x1 <= event_x <= x2 and y1 <= event_y <= y2:
                if callable(self.on_link_text_edit):
                    self.on_link_text_edit(
                        source_idx,
                        target_idx,
                        target_value,
                        (x1, y1, x2, y2),
                    )
                return
        idx = self._hit_test(event_x, event_y)
        if idx is not None:
            self._select_index(idx)
            if callable(self.on_edit):
                self.on_edit(idx)

    def _on_right_click(self, event):
        event_x, event_y = self._event_coords(event)
        idx = self._hit_test(event_x, event_y)
        if idx is not None:
            self._select_index(idx, redraw_on_none=False)
        else:
            self._select_index(None, redraw_on_none=False)
        if callable(self.on_context):
            self.on_context(event, idx)


__all__ = ["normalise_scene_links", "SceneFlowPreview", "SceneCanvas"]
