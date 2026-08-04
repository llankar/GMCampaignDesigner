"""Dense, live-session scenario sheet for the GM Table."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from modules.scenarios.gm_table.scenario_board.bundle_service import (
    ScenarioBundle,
    resolve_scenario_bundle,
)
from modules.scenarios.gm_table.scenario_board.content import (
    ENTITY_ACTIONS,
    build_directives,
    build_info_bands,
)
from modules.scenarios.gm_table.scenario_board.entity_links import (
    add_entity_links,
    bind_full_width_wrap,
)
from modules.scenarios.gm_table.scenario_board.layout import (
    build_scene_grid_layout,
    initial_scene_wraplength,
)
from modules.scenarios.gm_table.scenario_board.models import (
    ScenarioBoardScene,
    build_scenario_board_data,
)
from modules.scenarios.gm_table.scenario_board.styles import resolve_scenario_board_palette

OpenEntityCallback = Callable[[str, str], None]
OpenMapCallback = Callable[[str | None], None]
LaunchBundleCallback = Callable[[ScenarioBundle], None]
StateChangedCallback = Callable[[], None]


class ScenarioBoardPanel(ctk.CTkFrame):
    """Compact four-column scenario reference sheet with live controls."""

    def __init__(
        self,
        master,
        *,
        scenario_name: str,
        scenario_item: dict[str, Any] | None,
        open_entity_callback: OpenEntityCallback | None = None,
        launch_bundle_callback: LaunchBundleCallback | None = None,
        open_scene_map_callback: OpenMapCallback | None = None,
        open_world_map_callback: OpenMapCallback | None = None,
        wrappers: dict[str, object] | None = None,
        map_wrapper: object | None = None,
        initial_state: dict[str, Any] | None = None,
        on_state_changed: StateChangedCallback | None = None,
    ) -> None:
        self._palette = resolve_scenario_board_palette()
        super().__init__(master, fg_color=self._palette.background)
        self.scenario_name = str(scenario_name or "").strip()
        self._scenario_item = scenario_item if isinstance(scenario_item, dict) else {}
        self._open_entity_callback = open_entity_callback
        self._launch_bundle_callback = launch_bundle_callback
        self._open_scene_map_callback = open_scene_map_callback
        self._open_world_map_callback = open_world_map_callback
        self._wrappers, self._map_wrapper = wrappers or {}, map_wrapper
        self._on_state_changed = on_state_changed
        self._data = build_scenario_board_data(scenario_item)
        state = initial_state if isinstance(initial_state, dict) else {}
        self._completed_scenes = {
            int(v) for v in state.get("completed_scenes", []) if str(v).isdigit()
        }
        self._current_scene_index = self._coerce_scene_index(state.get("current_scene"))
        if self._current_scene_index is None and self._data.scenes:
            self._current_scene_index = self._data.scenes[0].index
        self._scene_buttons: dict[int, ctk.CTkButton] = {}
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_actions()  # Deliberately retain the original top controls.
        self._build_board()
        self._refresh_scene_selection()

    def get_state(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name or self._data.title,
            "current_scene": self._current_scene_index,
            "completed_scenes": sorted(self._completed_scenes),
        }

    def _build_actions(self) -> None:
        actions = ctk.CTkScrollableFrame(
            self,
            orientation="horizontal",
            height=48,
            fg_color=self._palette.background,
            scrollbar_button_color=self._palette.control,
        )
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        entity_buttons = tuple(
            (label, lambda entity_type=entity_type: self._open_entities(entity_type))
            for label, entity_type in ENTITY_ACTIONS
        )
        buttons = (
            ("Launch Scenario Bundle", self._launch_current_bundle),
            ("Open Scene Map", self._open_current_scene_map),
            *entity_buttons,
            ("Open World Map", self._open_world_map),
            ("Mark Scene Done", self._mark_current_scene_done),
        )
        for text, command in buttons:
            ctk.CTkButton(
                actions,
                text=text,
                height=28,
                width=120,
                fg_color=self._palette.control,
                hover_color=self._palette.control_hover,
                text_color=self._palette.control_text,
                corner_radius=4,
                command=command,
            ).pack(side="left", padx=(0, 6))

    def _build_board(self) -> None:
        board = ctk.CTkScrollableFrame(
            self,
            fg_color=self._palette.background,
            scrollbar_button_color=self._palette.control,
        )
        board.grid(row=1, column=0, sticky="nsew")
        for column in range(20):
            board.grid_columnconfigure(column, weight=1, uniform="board")
        row = self._add_info_bands(board, 0)
        row = self._add_directives(board, row)
        self._add_scene_grid(board, row)

    def _add_info_bands(self, parent, row: int) -> int:
        groups = build_info_bands(self._data)
        for column, (title, entries, plain_text) in enumerate(groups):
            cell = ctk.CTkFrame(
                parent,
                fg_color=self._palette.info_bands[column],
                corner_radius=0,
                border_width=1,
                border_color=self._palette.border,
            )
            cell.grid(
                row=row, column=column * 4, columnspan=4, sticky="nsew", pady=(0, 8)
            )
            ctk.CTkLabel(
                cell,
                text=title,
                text_color=self._palette.info_band_text_colors[column],
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(pady=(7, 0))
            if plain_text:
                objective = ctk.CTkLabel(
                    cell,
                    text=plain_text,
                    justify="left",
                    text_color=self._palette.text,
                    font=ctk.CTkFont(size=13, weight="bold"),
                )
                objective.pack(fill="x", padx=7, pady=(2, 7))
                bind_full_width_wrap(objective)
            else:
                add_entity_links(
                    cell, entries, self._open_entity_callback, palette=self._palette
                )
        return row + 1

    def _add_directives(self, parent, row: int) -> int:
        directives = build_directives(self._data)
        spans = (10, 10)
        start = 0
        for (title, value, accent), span in zip(directives, spans):
            text = f"{title}  {value or '—'}"
            ctk.CTkLabel(
                parent,
                text=text,
                anchor="w",
                justify="left",
                wraplength=380,
                fg_color=self._palette.surface,
                text_color=self._palette.section_accents[accent],
                font=ctk.CTkFont(size=10, weight="bold"),
                height=34,
            ).grid(
                row=row,
                column=start,
                columnspan=span,
                sticky="nsew",
                pady=(0, 8),
                padx=(0, 2),
            )
            start += span
        return row + 1

    def _add_scene_grid(self, parent, row: int) -> None:
        if not self._data.scenes:
            ctk.CTkLabel(
                parent, text="No scenario content found.", text_color=self._palette.muted
            ).grid(row=row, column=0, columnspan=20, pady=20)
            return
        layout = build_scene_grid_layout(len(self._data.scenes))
        for offset, (scene, cell) in enumerate(zip(self._data.scenes, layout)):
            card = ctk.CTkFrame(
                parent,
                fg_color=self._palette.surface,
                corner_radius=0,
                border_width=1,
                border_color=self._palette.scene_colors[offset % 4],
            )
            card.grid(
                row=row + cell.row,
                column=cell.column,
                columnspan=cell.columnspan,
                sticky="nsew",
                padx=(0, 3),
                pady=(0, 6),
            )
            button = ctk.CTkButton(
                card,
                text=f"{scene.index}. {scene.title.upper()}",
                height=34,
                corner_radius=0,
                fg_color=self._palette.scene_colors[offset % 4],
                # Keep the computed foreground/text contrast stable on hover.
                hover_color=self._palette.scene_colors[offset % 4],
                text_color=self._palette.scene_text_colors[offset % 4],
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda idx=scene.index: self._set_current_scene(idx),
            )
            button.pack(fill="x")
            self._scene_buttons[scene.index] = button
            self._add_scene_entity_links(card, scene)
            body = scene.intro_text or scene.body
            lines = [body]
            for section in scene.sections:
                section_text = "\n".join(
                    f"• {item}" for item in section.get("items") or ()
                )
                lines.append(
                    f"{str(section.get('title') or '').upper()}\n{section_text}".strip()
                )
            body_label = ctk.CTkLabel(
                card,
                text="\n\n".join(line for line in lines if line),
                anchor="nw",
                justify="left",
                text_color=self._palette.text,
                font=ctk.CTkFont(size=14),
            )
            body_label.pack(fill="both", expand=True, padx=7, pady=7)
            bind_full_width_wrap(
                body_label,
                initial_wraplength=initial_scene_wraplength(cell.columnspan),
            )

    def _add_scene_entity_links(self, card, scene: ScenarioBoardScene) -> None:
        entries = (
            *(("NPCs", name) for name in scene.npcs),
            *(("Villains", name) for name in scene.villains),
            *(("Places", name) for name in scene.places),
        )
        if entries:
            links = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
            links.pack(fill="x", padx=2, pady=(4, 0))
            add_entity_links(
                links,
                entries,
                self._open_entity_callback,
                font_size=12,
                palette=self._palette,
            )

    def _current_scene(self) -> ScenarioBoardScene | None:
        return next(
            (s for s in self._data.scenes if s.index == self._current_scene_index),
            self._data.scenes[0] if self._data.scenes else None,
        )

    def _current_bundle(self) -> ScenarioBundle:
        return resolve_scenario_bundle(
            self._scenario_item,
            self._current_scene(),
            self._wrappers,
            self._map_wrapper,
        )

    def _set_current_scene(self, index: int) -> None:
        self._current_scene_index = index
        self._refresh_scene_selection()
        self._notify_state_changed()

    def _mark_current_scene_done(self) -> None:
        if self._current_scene_index is None:
            return
        self._completed_scenes.add(self._current_scene_index)
        self._current_scene_index = next(
            (
                s.index
                for s in self._data.scenes
                if s.index not in self._completed_scenes
            ),
            self._current_scene_index,
        )
        self._refresh_scene_selection()
        self._notify_state_changed()

    def _refresh_scene_selection(self) -> None:
        for index, button in self._scene_buttons.items():
            scene = next((s for s in self._data.scenes if s.index == index), None)
            if scene:
                marker = (
                    "✓ "
                    if index in self._completed_scenes
                    else ("▶ " if index == self._current_scene_index else "")
                )
                button.configure(text=f"{marker}{scene.index}. {scene.title.upper()}")

    def _launch_current_bundle(self) -> None:
        if callable(self._launch_bundle_callback):
            self._launch_bundle_callback(self._current_bundle())

    def _open_current_scene_map(self) -> None:
        bundle = self._current_bundle()
        if callable(self._open_scene_map_callback):
            self._open_scene_map_callback(bundle.maps[0] if bundle.maps else None)

    def _open_world_map(self) -> None:
        bundle = self._current_bundle()
        if callable(self._open_world_map_callback):
            self._open_world_map_callback(
                bundle.world_maps[0] if bundle.world_maps else None
            )

    def _open_entities(self, entity_type: str) -> None:
        bundle = self._current_bundle()
        for name in {
            "NPCs": bundle.npcs,
            "Villains": bundle.villains,
            "Places": bundle.places,
        }.get(entity_type, ()):
            if callable(self._open_entity_callback):
                self._open_entity_callback(entity_type, name)

    def _notify_state_changed(self) -> None:
        if callable(self._on_state_changed):
            self._on_state_changed()

    @staticmethod
    def _coerce_scene_index(value: Any) -> int | None:
        try:
            index = int(value)
        except (TypeError, ValueError):
            return None
        return index if index > 0 else None
