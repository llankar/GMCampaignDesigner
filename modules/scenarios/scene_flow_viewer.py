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
    """Toplevel window hosting a dedicated scene flow viewer."""

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
    """ScenarioGraphEditor subclass that specialises in scene flow presentation."""

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
        self._initial_scenario = initial_scenario or {}
        self._initial_title = self._extract_title(self._initial_scenario)
        self._scenario_lookup: Dict[str, dict] = {}
        self._shadow_cache: Dict[tuple, tuple] = {}
        self._grid_tile_cache: Dict[str, ImageTk.PhotoImage] = {}

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

    # ------------------------------------------------------------------
    # Portrait handling
    # ------------------------------------------------------------------
    def load_portrait_scaled(self, portrait_path, node_tag, scale: float = 1.0):  # type: ignore[override]
        """Load node portraits at twice the base size used by the editor.

        The underlying graph editor already supports zoom scaling via the
        ``scale`` parameter. By multiplying the provided scale we effectively
        double the rendered size of portraits in the dedicated scene flow
        viewer while still respecting zoom changes.
        """

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


__all__ = ["SceneFlowViewerFrame", "SceneFlowViewerWindow"]
