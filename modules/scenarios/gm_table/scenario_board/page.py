"""Dense, live-session scenario sheet for the GM Table."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from modules.scenarios.gm_table.scenario_board.bundle_service import (
    ScenarioBundle,
    resolve_scenario_bundle,
)
from modules.scenarios.gm_table.scenario_board.models import (
    ScenarioBoardData,
    ScenarioBoardScene,
    build_scenario_board_data,
)
from modules.scenarios.gm_table.scenario_board.styles import (
    BOARD_BACKGROUND,
    BOARD_BORDER,
    BOARD_MUTED,
    BOARD_SURFACE,
    BOARD_TEXT,
    INFO_BAND_COLORS,
    SCENE_COLORS,
    SECTION_ACCENTS,
)
from modules.scenarios.gm_table.workspace import TABLE_PALETTE

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
        super().__init__(master, fg_color=BOARD_BACKGROUND)
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
            fg_color=BOARD_BACKGROUND,
            scrollbar_button_color=TABLE_PALETTE["table_chip"],
        )
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        buttons = (
            ("Launch Scenario Bundle", self._launch_current_bundle),
            ("Open Scene Map", self._open_current_scene_map),
            ("Open NPCs", lambda: self._open_entities("NPCs")),
            ("Open Villain", lambda: self._open_entities("Villains")),
            ("Open Places", lambda: self._open_entities("Places")),
            ("Open World Map", self._open_world_map),
            ("Mark Scene Done", self._mark_current_scene_done),
        )
        for text, command in buttons:
            ctk.CTkButton(
                actions,
                text=text,
                height=28,
                width=120,
                fg_color=TABLE_PALETTE["table_chip"],
                hover_color="#283146",
                text_color=BOARD_TEXT,
                corner_radius=4,
                command=command,
            ).pack(side="left", padx=(0, 6))

    def _build_board(self) -> None:
        board = ctk.CTkScrollableFrame(
            self,
            fg_color=BOARD_BACKGROUND,
            scrollbar_button_color=TABLE_PALETTE["table_chip"],
        )
        board.grid(row=1, column=0, sticky="nsew")
        for column in range(20):
            board.grid_columnconfigure(column, weight=1, uniform="board")
        row = self._add_info_bands(board, 0)
        row = self._add_directives(board, row)
        row = self._add_checkpoint(board, row)
        self._add_scene_grid(board, row)

    def _add_info_bands(self, parent, row: int) -> int:
        groups = (
            ("PCS", self._data.linked_entities.get("PCs", ())),
            ("MAJOR NPCS", self._data.linked_entities.get("NPCs", ())),
            (
                "ADVERSARIES",
                (
                    *self._data.linked_entities.get("Villains", ()),
                    *self._data.linked_entities.get("Creatures", ()),
                ),
            ),
            ("FACTIONS", self._data.linked_entities.get("Factions", ())),
            (
                "PLACES / CLUES",
                (
                    *self._data.linked_entities.get("Places", ()),
                    *self._data.linked_entities.get("Clues", ()),
                ),
            ),
        )
        for column, (title, values) in enumerate(groups):
            cell = ctk.CTkFrame(
                parent,
                fg_color=INFO_BAND_COLORS[column],
                corner_radius=0,
                border_width=1,
                border_color=BOARD_BORDER,
            )
            cell.grid(
                row=row, column=column * 4, columnspan=4, sticky="nsew", pady=(0, 8)
            )
            ctk.CTkLabel(
                cell,
                text=title,
                text_color=SCENE_COLORS[column % 4],
                font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(pady=(7, 0))
            ctk.CTkLabel(
                cell,
                text="\n".join(values) or "—",
                text_color=BOARD_TEXT,
                font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(padx=6, pady=(0, 7))
        return row + 1

    def _add_directives(self, parent, row: int) -> int:
        directives = (
            ("OBJECTIVE", self._data.objective or self._data.summary, "objective"),
            ("SECRET", self._data.secrets, "secret"),
            ("PRESSURE", self._data.pressure or self._data.status, "pressure"),
        )
        spans = (7, 7, 6)
        start = 0
        for (title, value, accent), span in zip(directives, spans):
            text = f"{title}  {value or '—'}"
            ctk.CTkLabel(
                parent,
                text=text,
                anchor="w",
                justify="left",
                wraplength=380,
                fg_color=BOARD_SURFACE,
                text_color=SECTION_ACCENTS[accent],
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

    def _add_checkpoint(self, parent, row: int) -> int:
        route = self._data.checkpoint or "  →  ".join(
            f"{scene.index}. {scene.title}" for scene in self._data.scenes
        )
        ctk.CTkLabel(
            parent,
            text=route or "No scenes defined",
            fg_color=BOARD_SURFACE,
            text_color=BOARD_TEXT,
            font=ctk.CTkFont(size=11, weight="bold"),
            height=28,
        ).grid(row=row, column=0, columnspan=20, sticky="ew", pady=(0, 12))
        return row + 1

    def _add_scene_grid(self, parent, row: int) -> None:
        if not self._data.scenes:
            ctk.CTkLabel(
                parent, text="No scenario content found.", text_color=BOARD_MUTED
            ).grid(row=row, column=0, columnspan=20, pady=20)
            return
        for offset, scene in enumerate(self._data.scenes):
            grid_row, column = row + offset // 4, (offset % 4) * 5
            card = ctk.CTkFrame(
                parent,
                fg_color=BOARD_SURFACE,
                corner_radius=0,
                border_width=1,
                border_color=SCENE_COLORS[offset % 4],
            )
            card.grid(
                row=grid_row,
                column=column,
                columnspan=5,
                sticky="nsew",
                padx=(0, 3),
                pady=(0, 6),
            )
            button = ctk.CTkButton(
                card,
                text=f"{scene.index}. {scene.title.upper()}",
                height=34,
                corner_radius=0,
                fg_color=SCENE_COLORS[offset % 4],
                hover_color=SCENE_COLORS[offset % 4],
                text_color="#09111d",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda idx=scene.index: self._set_current_scene(idx),
            )
            button.pack(fill="x")
            self._scene_buttons[scene.index] = button
            entities = self._scene_entity_text(scene)
            body = scene.intro_text or scene.body
            lines = [entities, body]
            for section in scene.sections:
                section_text = "\n".join(
                    f"• {item}" for item in section.get("items") or ()
                )
                lines.append(
                    f"{str(section.get('title') or '').upper()}\n{section_text}".strip()
                )
            ctk.CTkLabel(
                card,
                text="\n\n".join(line for line in lines if line),
                anchor="nw",
                justify="left",
                wraplength=235,
                text_color=BOARD_TEXT,
                font=ctk.CTkFont(size=10),
            ).pack(fill="both", expand=True, padx=7, pady=7)

    @staticmethod
    def _scene_entity_text(scene: ScenarioBoardScene) -> str:
        parts = []
        for label, values in (
            ("NPCS", scene.npcs),
            ("ADVERSARIES", scene.villains),
            ("PLACES", scene.places),
            ("MAPS", scene.maps),
        ):
            if values:
                parts.append(f"{label}: {', '.join(values)}")
        return "\n".join(parts)

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
