import tkinter as tk
from typing import Callable, Dict, Optional, Sequence

import customtkinter as ctk
from PIL import ImageTk

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_info, log_module_import, log_warning
from modules.scenarios.scenario_graph_editor import ScenarioGraphEditor
from modules.scenarios.scene_flow_rendering import (
    apply_scene_flow_canvas_styling,
    get_shadow_image,
)

log_module_import(__name__)


class SceneFlowViewerWindow(ctk.CTkToplevel):
    """Toplevel window hosting a dedicated scene flow viewer (v2 layout)."""

    def __init__(
        self,
        master: Optional[ctk.CTk] = None,
        *,
        scenario_wrapper: GenericModelWrapper,
        npc_wrapper: GenericModelWrapper,
        creature_wrapper: GenericModelWrapper,
        place_wrapper: GenericModelWrapper,
        initial_scenario: Optional[dict] = None,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master)

        self.title("Scene Flow Viewer")
        self.geometry("1400x900")
        self.minsize(1100, 720)
        self._on_close_callback = on_close

        self.viewer = SceneFlowViewerFrame(
            self,
            scenario_wrapper,
            npc_wrapper,
            creature_wrapper,
            place_wrapper,
            initial_scenario=initial_scenario,
        )
        self.viewer.pack(fill="both", expand=True)

        # Focus the window once the widgets are ready.
        self.after(50, self._focus_window)
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _focus_window(self) -> None:
        try:
            self.focus()
            self.lift()
        except Exception:
            pass

    def _handle_close(self) -> None:
        try:
            if callable(self._on_close_callback):
                self._on_close_callback()
        finally:
            self.destroy()


class SceneFlowViewerFrame(ScenarioGraphEditor):
    """ScenarioGraphEditor subclass that specialises in scene flow presentation (v2 layout)."""

    GRID_EXTENT_WIDTH = 6000
    GRID_EXTENT_HEIGHT = 4000
    PORTRAIT_SCALE_MULTIPLIER = 2.0

    def __init__(
        self,
        master,
        scenario_wrapper: GenericModelWrapper,
        npc_wrapper: GenericModelWrapper,
        creature_wrapper: GenericModelWrapper,
        place_wrapper: GenericModelWrapper,
        *,
        initial_scenario: Optional[dict] = None,
        **kwargs,
    ) -> None:
        # Initial fit mode for zoom behaviour in the viewer
        self.fit_mode: str = "Contain"  # Contain | Width | Height
        self._fit_initialized = False
        self._initial_scenario = initial_scenario or {}
        self._initial_title = self._extract_title(self._initial_scenario)
        self._scenario_lookup: Dict[str, dict] = {}
        self._shadow_cache: Dict[tuple, tuple] = {}
        self._grid_tile_cache: Dict[str, ImageTk.PhotoImage] = {}
        self._relayout_after_id: Optional[str] = None
        self._relayout_in_progress = False

        super().__init__(
            master,
            scenario_wrapper,
            npc_wrapper,
            creature_wrapper,
            place_wrapper,
            **kwargs,
        )

        self._apply_scene_flow_styling()
        self._populate_scenario_menu()

        # Re-apply fit after the first real canvas size is known
        try:
            self.canvas.bind("<Configure>", self._on_canvas_resized, add="+")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Portrait handling
    # ------------------------------------------------------------------
    def load_portrait_scaled(self, portrait_path, node_tag, scale: float = 1.0):  # type: ignore[override]
        """Load node portraits at twice the base size used by the editor."""

        effective_scale = (scale or 0.0) * self.PORTRAIT_SCALE_MULTIPLIER
        if effective_scale <= 0:
            effective_scale = self.PORTRAIT_SCALE_MULTIPLIER
        return super().load_portrait_scaled(portrait_path, node_tag, effective_scale)

    # ------------------------------------------------------------------
    # Toolbar configuration
    # ------------------------------------------------------------------
    def init_toolbar(self) -> None:  # type: ignore[override]
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=8, pady=(8, 4))
        self.toolbar = toolbar

        title_label = ctk.CTkLabel(
            toolbar,
            text="Scene Flow",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        title_label.pack(side="left", padx=(4, 12))

        self.scenario_var = tk.StringVar(value="")
        self.scenario_menu = ctk.CTkOptionMenu(
            toolbar,
            variable=self.scenario_var,
            values=[],
            command=self._on_scenario_selected,
            width=280,
        )
        self.scenario_menu.pack(side="left", padx=(0, 8))

        self.refresh_button = ctk.CTkButton(
            toolbar,
            text="Refresh",
            command=self._populate_scenario_menu,
            width=90,
        )
        self.refresh_button.pack(side="left")

        self.detail_toggle = ctk.CTkSwitch(
            toolbar,
            text="Show Details",
            command=self._toggle_detail_panel,
            onvalue=True,
            offvalue=False,
        )
        self.detail_toggle.pack(side="right", padx=(0, 8))
        self.detail_toggle.select()

        # Fit mode selector (initial zoom)
        fit_label = ctk.CTkLabel(toolbar, text="Fit:")
        fit_label.pack(side="right", padx=(8, 4))
        self.fit_mode_menu = ctk.CTkOptionMenu(
            toolbar,
            values=["Contain", "Width", "Height"],
            command=self._on_fit_mode_change,
            width=120,
        )
        self.fit_mode_menu.set(self.fit_mode)
        self.fit_mode_menu.pack(side="right", padx=(0, 8))

        # Keep canvas full-height under the toolbar
        try:
            self.bind("<Configure>", self._on_layout_resize, add="+")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Scenario selection helpers
    # ------------------------------------------------------------------
    def _extract_title(self, scenario: Optional[dict]) -> str:
        if not isinstance(scenario, dict):
            return ""
        title = scenario.get("Title") or scenario.get("Name") or ""
        return str(title).strip()

    def _populate_scenario_menu(self) -> None:
        try:
            scenarios = self.scenario_wrapper.load_items()
        except Exception as exc:
            log_warning(
                f"Unable to load scenarios for scene flow viewer: {exc}",
                func_name="SceneFlowViewerFrame._populate_scenario_menu",
            )
            scenarios = []

        lookup: Dict[str, dict] = {}
        names: list[str] = []
        for scenario in scenarios:
            title = self._extract_title(scenario)
            if not title:
                continue
            lookup[title] = scenario
            names.append(title)

        names.sort(key=lambda value: value.lower())

        if self._initial_title and self._initial_title not in lookup:
            lookup[self._initial_title] = self._initial_scenario
            names.insert(0, self._initial_title)

        self._scenario_lookup = lookup
        if hasattr(self, "scenario_menu"):
            menu_values: Sequence[str] = names if names else ["No scenarios available"]
            self.scenario_menu.configure(values=list(menu_values))
            if names:
                current = self.scenario_var.get()
                target = current or self._initial_title or names[0]
                self.scenario_var.set(target)
                self.scenario_menu.configure(state="normal")
                if target in lookup:
                    self._load_selected_scenario()
            else:
                self.scenario_var.set("No scenarios available")
                self.scenario_menu.configure(state="disabled")

    def _on_scenario_selected(self, _: str) -> None:
        self._load_selected_scenario()

    def _load_selected_scenario(self) -> None:
        title = self.scenario_var.get().strip()
        if not title or title == "No scenarios available":
            return
        scenario = self._scenario_lookup.get(title)
        if scenario is None:
            # Reload the cache in case data changed outside the viewer.
            self._populate_scenario_menu()
            scenario = self._scenario_lookup.get(title)
            if scenario is None:
                return
        log_info(
            f"Loading scene flow for scenario '{title}'",
            func_name="SceneFlowViewerFrame._load_selected_scenario",
        )
        self.load_scenario_scene_flow(scenario)
        # Apply the selected fit mode on first load for better initial view
        self._fit_initialized = False
        self._fit_to_view()
        self._schedule_relayout(0)

    def _on_canvas_resized(self, _event=None) -> None:
        if not self._fit_initialized:
            self._fit_to_view()
        self._schedule_relayout(80)

    def _on_fit_mode_change(self, value: str) -> None:
        self.fit_mode = (value or "Contain").title()
        self._fit_initialized = False
        self._fit_to_view()
        self._schedule_relayout(0)

    def _fit_to_view(self) -> None:
        canvas = getattr(self, "canvas", None)
        if not canvas:
            return
        try:
            canvas.update_idletasks()
            cw = int(canvas.winfo_width())
            # Account for toolbar height to compute available space
            th = 0
            try:
                th = int(self.toolbar.winfo_height()) if hasattr(self, "toolbar") else 0
            except Exception:
                th = 0
            ch = int(self.winfo_height()) - th if int(self.winfo_height()) > 1 else int(canvas.winfo_height())
        except Exception:
            return
        if cw <= 1 or ch <= 1:
            return

        bbox = self._content_bbox()
        if not bbox:
            return
        content_w = max(1, bbox[2] - bbox[0])
        content_h = max(1, bbox[3] - bbox[1])

        mode = (self.fit_mode or "Contain").title()
        if mode == "Width":
            scale = cw / content_w
        elif mode == "Height":
            scale = ch / content_h
        else:
            scale = min(cw / content_w, ch / content_h)

        # Clamp to a sensible range
        try:
            scale = float(scale)
        except Exception:
            scale = 1.0
        # Option 2: avoid upscaling to keep layout spacing consistent
        scale = max(0.2, min(1.0, scale))

        if abs(getattr(self, "canvas_scale", 1.0) - scale) > 1e-3:
            self.canvas_scale = scale
            self.draw_graph()
            canvas.update_idletasks()
            bbox = self._content_bbox() or bbox

        # Restrict the scrollregion to the visible content instead of the
        # background grid to avoid zooming out to the entire tiled canvas.
        padding = 80
        scroll_region = (
            bbox[0] - padding,
            bbox[1] - padding,
            bbox[2] + padding,
            bbox[3] + padding,
        )
        try:
            canvas.configure(scrollregion=scroll_region)
        except Exception:
            scroll_region = bbox

        # Center the view within the scrollregion
        try:
            sx0, sy0, sx1, sy1 = scroll_region
        except Exception:
            return
        width_r = max(1, sx1 - sx0)
        height_r = max(1, sy1 - sy0)
        if width_r <= 0 or height_r <= 0:
            return

        if width_r > cw:
            target_left = sx0 + (width_r - cw) / 2
            frac_x = (target_left - sx0) / width_r
            canvas.xview_moveto(max(0.0, min(1.0, frac_x)))
        else:
            canvas.xview_moveto(0.0)

        if height_r > ch:
            target_top = sy0 + (height_r - ch) / 2
            frac_y = (target_top - sy0) / height_r
            canvas.yview_moveto(max(0.0, min(1.0, frac_y)))
        else:
            canvas.yview_moveto(0.0)
        self._fit_initialized = True

    def _content_bbox(self):
        """Return the bounding box for rendered graph content only."""

        canvas = getattr(self, "canvas", None)
        if not canvas:
            return None

        for tags in (("node", "link"), ("node",), ("link",)):
            try:
                bbox = canvas.bbox(*tags)
                if bbox:
                    return bbox
            except Exception:
                continue

        try:
            return canvas.bbox("all")
        except Exception:
            return None

    def _on_layout_resize(self, _event=None) -> None:
        """Keep the canvas height matched to available space under the toolbar."""
        canvas = getattr(self, "canvas", None)
        if not canvas:
            return
        try:
            self.update_idletasks()
            w = int(self.winfo_width())
            h = int(self.winfo_height())
            th = int(self.toolbar.winfo_height()) if hasattr(self, "toolbar") else 0
            if w > 1 and h > 1:
                canvas.configure(width=w, height=max(1, h - th))
        except Exception:
            pass

    def _toggle_detail_panel(self, *_args) -> None:
        if getattr(self.detail_toggle, "get", lambda: True)():
            self._show_detail_panel()
        else:
            self._hide_detail_panel()

    # ------------------------------------------------------------------
    # Visual styling adjustments
    # ------------------------------------------------------------------
    def _apply_scene_flow_styling(self) -> None:
        self.canvas.configure(bg="#1B1F27")
        if hasattr(self, "background_id"):
            try:
                self.canvas.delete(self.background_id)
            except Exception:
                pass
            self.background_id = None
            self.background_photo = None

        apply_scene_flow_canvas_styling(
            self.canvas,
            tile_cache=self._grid_tile_cache,
            extent_width=self.GRID_EXTENT_WIDTH,
            extent_height=self.GRID_EXTENT_HEIGHT,
        )
        self.canvas.tag_lower("scene_flow_bg")

    # ------------------------------------------------------------------
    # Layout override
    # ------------------------------------------------------------------
    def _schedule_relayout(self, delay_ms: int = 60) -> None:
        """Debounce relayout to handle resize/fit changes smoothly."""
        if self._relayout_after_id:
            try:
                self.after_cancel(self._relayout_after_id)
            except Exception:
                pass
            self._relayout_after_id = None
        try:
            self._relayout_after_id = self.after(delay_ms, self._relayout_scene_flow)
        except Exception:
            self._relayout_scene_flow()

    def load_scenario_scene_flow(self, scenario=None):  # type: ignore[override]
        """Load the scene flow then re-layout nodes to fit the available canvas."""
        super().load_scenario_scene_flow(scenario)
        self._relayout_scene_flow()

    def _relayout_scene_flow(self) -> None:
        if self._relayout_in_progress:
            return
        self._relayout_in_progress = True
        self._relayout_after_id = None
        if not getattr(self, "scene_flow_scenes", None):
            self._relayout_in_progress = False
            return

        scenes = [s for s in self.scene_flow_scenes if s.get("tag")]
        if not scenes:
            self._relayout_in_progress = False
            return

        canvas = getattr(self, "canvas", None)
        if not canvas:
            self._relayout_in_progress = False
            return

        try:
            canvas.update_idletasks()
            available_width = max(int(canvas.winfo_width()), 800)
            available_height = max(int(canvas.winfo_height()), 600)
        except Exception:
            available_width = 1200
            available_height = 800

        widths = [int(s.get("card_width", 320)) for s in scenes]
        heights = [int(s.get("card_height", 220)) for s in scenes]
        if not widths or not heights:
            self._relayout_in_progress = False
            return

        avg_w = max(1, sum(widths) / len(widths))
        avg_h = max(1, sum(heights) / len(heights))

        gap_x = 30  # Fixed horizontal gap between cards (right edge to next left edge)
        base_gap_y = max(16, int(avg_h * 0.1))
        min_gap_y = max(8, int(base_gap_y * 0.6))
        edge_pad_x = max(24, int(avg_w * 0.12))
        edge_pad_y = max(24, int(avg_h * 0.1))

        count = len(scenes)
        approx_cols = max(1, int((available_width - 2 * edge_pad_x + gap_x) / max(avg_w + gap_x, 1)))
        col_count = max(1, min(count, approx_cols))
        gap_y = base_gap_y

        def chunk(items, size):
            for i in range(0, len(items), size):
                yield items[i : i + size]

        def compute_layout(cols, gx, gy):
            rows = list(chunk(scenes, max(1, cols)))
            row_heights = []
            row_widths = []
            for r in rows:
                heights = [int(s.get("card_height", avg_h)) for s in r]
                widths_row = [int(s.get("card_width", avg_w)) for s in r]
                row_heights.append(max(heights) if heights else 0)
                if widths_row:
                    row_widths.append(sum(widths_row) + gx * max(0, len(widths_row) - 1))
                else:
                    row_widths.append(0)

            total_width = edge_pad_x * 2 + (max(row_widths) if row_widths else 0)
            total_height = edge_pad_y * 2 + sum(row_heights) + gy * max(0, len(rows) - 1)

            positions = []
            cursor_y = edge_pad_y
            for row_idx, row in enumerate(rows):
                cursor_x = edge_pad_x
                height = row_heights[row_idx]
                for col_idx, scene in enumerate(row):
                    width = int(scene.get("card_width", avg_w))
                    center_x = cursor_x + width / 2
                    center_y = cursor_y + height / 2
                    positions.append((center_x, center_y))
                    cursor_x = center_x + width / 2 + gx
                cursor_y += height + gy

            return total_width, total_height, positions

        for _ in range(12):
            layout_width, layout_height, positions = compute_layout(col_count, gap_x, gap_y)
            if layout_width > available_width and col_count > 1:
                col_count -= 1
                continue
            if layout_height > available_height and col_count < count:
                col_count += 1
                continue
            if layout_height > available_height and gap_y > min_gap_y:
                gap_y = max(min_gap_y, int(gap_y * 0.9))
                continue
            break

        _, _, positions = compute_layout(col_count, gap_x, gap_y)
        for scene, (x, y) in zip(scenes, positions):
            tag = scene.get("tag")
            if not tag:
                continue
            self.node_positions[tag] = (x, y)
            for node in self.graph.get("nodes", []):
                node_tag = self._build_tag(node.get("type", ""), node.get("name", ""))
                if node_tag == tag:
                    node["x"] = x
                    node["y"] = y
                    break

        self.original_positions = dict(self.node_positions)
        self.canvas_scale = 1.0
        self.draw_graph()
        self._fit_initialized = False
        self._fit_to_view()
        self._relayout_in_progress = False

    # ------------------------------------------------------------------
    # Scene drawing overrides
    # ------------------------------------------------------------------
    def _draw_scene_card(self, node, scale):  # type: ignore[override]
        super()._draw_scene_card(node, scale)

        node_name = node.get("name", "Scene")
        node_tag = self._build_tag("scene", node_name)
        bbox = self.node_bboxes.get(node_tag)
        if not bbox:
            return
        left, top, right, bottom = bbox
        width = int(right - left)
        height = int(bottom - top)

        shadow_image, offset = get_shadow_image(
            self.canvas, self._shadow_cache, width, height, scale
        )
        if shadow_image is None:
            return

        shadow_id = self.canvas.create_image(
            left - offset,
            top - offset,
            image=shadow_image,
            anchor="nw",
            tags=("node", node_tag, "shadow"),
        )
        self.canvas.tag_lower(shadow_id, node_tag)
        cache_key = (node_tag, "shadow")
        self.node_images[cache_key] = shadow_image

    # Override scenario selection to avoid generic dialog usage.
    def select_scenario(self):  # type: ignore[override]
        self._populate_scenario_menu()


def create_scene_flow_frame(
    master=None,
    scenario_title: Optional[str] = None,
):
    """Convenience factory to embed a SceneFlowViewerFrame without a window."""
    scenario_wrapper = GenericModelWrapper("scenarios")
    npc_wrapper = GenericModelWrapper("npcs")
    creature_wrapper = GenericModelWrapper("creatures")
    place_wrapper = GenericModelWrapper("places")

    initial_scenario = None
    if scenario_title:
        try:
            items = scenario_wrapper.load_items() or []
        except Exception:
            items = []
        initial_scenario = next(
            (s for s in items if (s.get("Title") or s.get("Name")) == scenario_title),
            None,
        )

    return SceneFlowViewerFrame(
        master,
        scenario_wrapper,
        npc_wrapper,
        creature_wrapper,
        place_wrapper,
        initial_scenario=initial_scenario,
    )


def scene_flow_content_factory(scenario_title: Optional[str] = None):
    """Return a factory suitable for GM-screen tab restoration."""
    return lambda master: create_scene_flow_frame(master, scenario_title)


__all__ = [
    "SceneFlowViewerFrame",
    "SceneFlowViewerWindow",
    "create_scene_flow_frame",
    "scene_flow_content_factory",
]
