"""Scenario board page for the GM Table."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from modules.scenarios.gm_table.workspace import TABLE_PALETTE
from modules.scenarios.gm_table.scenario_board.bundle_service import (
    ScenarioBundle,
    resolve_scenario_bundle,
)
from modules.scenarios.gm_table.scenario_board.models import (
    ScenarioBoardData,
    ScenarioBoardScene,
    build_scenario_board_data,
)

OpenEntityCallback = Callable[[str, str], None]
OpenMapCallback = Callable[[str | None], None]
LaunchBundleCallback = Callable[[ScenarioBundle], None]
StateChangedCallback = Callable[[], None]


class ScenarioBoardPanel(ctk.CTkFrame):
    """Compact live-session board built from one scenario record."""

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
        super().__init__(master, fg_color="transparent")
        self.scenario_name = str(scenario_name or "").strip()
        self._scenario_item = scenario_item if isinstance(scenario_item, dict) else {}
        self._open_entity_callback = open_entity_callback
        self._launch_bundle_callback = launch_bundle_callback
        self._open_scene_map_callback = open_scene_map_callback
        self._open_world_map_callback = open_world_map_callback
        self._wrappers = wrappers or {}
        self._map_wrapper = map_wrapper
        self._on_state_changed = on_state_changed
        self._data = build_scenario_board_data(scenario_item)
        state = initial_state if isinstance(initial_state, dict) else {}
        self._completed_scenes = {
            int(value)
            for value in state.get("completed_scenes", [])
            if str(value).isdigit()
        }
        self._current_scene_index = self._coerce_scene_index(state.get("current_scene"))
        if self._current_scene_index is None and self._data.scenes:
            self._current_scene_index = self._data.scenes[0].index
        self._scene_buttons: dict[int, ctk.CTkButton] = {}
        self._scene_status_label: ctk.CTkLabel | None = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_header()
        self._build_scroll_body()
        self._refresh_scene_selection()

    def get_state(self) -> dict[str, Any]:
        """Return persisted panel state."""
        return {
            "scenario_name": self.scenario_name or self._data.title,
            "current_scene": self._current_scene_index,
            "completed_scenes": sorted(self._completed_scenes),
        }

    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self,
            fg_color=TABLE_PALETTE["panel_alt"],
            corner_radius=16,
            border_width=1,
            border_color=TABLE_PALETTE["panel_border"],
        )
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)

        title = self._data.title
        if self._data.status:
            title = f"{title}  •  {self._data.status}"
        ctk.CTkLabel(
            header,
            text=title,
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 2))
        self._scene_status_label = ctk.CTkLabel(
            header,
            text="Scenario Board",
            text_color=TABLE_PALETTE["muted"],
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self._scene_status_label.grid(
            row=1, column=0, sticky="ew", padx=14, pady=(0, 8)
        )

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
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
                fg_color=TABLE_PALETTE["table_chip"],
                hover_color="#283146",
                text_color=TABLE_PALETTE["text"],
                corner_radius=14,
                command=command,
            ).pack(side="left", padx=(0, 6), pady=(0, 6))

    def _build_scroll_body(self) -> None:
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=TABLE_PALETTE["table_chip"],
            scrollbar_button_hover_color=TABLE_PALETTE["accent"],
        )
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        row = 0

        row = self._add_text_card(scroll, row, "Summary", self._data.summary)
        row = self._add_text_card(scroll, row, "Secrets", self._data.secrets)
        row = self._add_entities_card(scroll, row, self._data)
        row = self._add_scenes(scroll, row, self._data)

        if row == 0:
            ctk.CTkLabel(
                scroll,
                text="No scenario content found.",
                text_color=TABLE_PALETTE["muted"],
            ).grid(row=0, column=0, sticky="ew", padx=16, pady=16)

    def _add_text_card(self, parent, row: int, title: str, text: str) -> int:
        if not text:
            return row
        card = self._card(parent)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        self._card_title(card, title).grid(
            row=0, column=0, sticky="ew", padx=12, pady=(10, 4)
        )
        self._wrapped_label(card, text).grid(
            row=1, column=0, sticky="ew", padx=12, pady=(0, 12)
        )
        return row + 1

    def _add_entities_card(self, parent, row: int, data: ScenarioBoardData) -> int:
        if not data.linked_entities:
            return row
        card = self._card(parent)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        self._card_title(card, "Linked Entities").grid(
            row=0, column=0, sticky="ew", padx=12, pady=(10, 4)
        )
        entity_row = 1
        for entity_type, names in data.linked_entities.items():
            ctk.CTkLabel(
                card,
                text=entity_type,
                text_color=TABLE_PALETTE["muted"],
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
            ).grid(row=entity_row, column=0, sticky="ew", padx=12, pady=(6, 2))
            entity_row += 1
            chips = ctk.CTkFrame(card, fg_color="transparent")
            chips.grid(row=entity_row, column=0, sticky="ew", padx=12, pady=(0, 2))
            for name in names:
                ctk.CTkButton(
                    chips,
                    text=name,
                    height=26,
                    fg_color=TABLE_PALETTE["table_chip"],
                    hover_color="#283146",
                    text_color=TABLE_PALETTE["text"],
                    corner_radius=13,
                    command=lambda et=entity_type, n=name: self._open_entity(et, n),
                ).pack(side="left", padx=(0, 6), pady=(0, 6))
            entity_row += 1
        return row + 1

    def _add_scenes(self, parent, row: int, data: ScenarioBoardData) -> int:
        if not data.scenes:
            return row
        for scene in data.scenes:
            card = self._card(parent)
            card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            card.grid_columnconfigure(1, weight=1)
            button = ctk.CTkButton(
                card,
                text=f"{scene.index}. {scene.title}",
                height=30,
                fg_color=TABLE_PALETTE["table_chip"],
                hover_color="#283146",
                text_color=TABLE_PALETTE["text"],
                anchor="w",
                command=lambda idx=scene.index: self._set_current_scene(idx),
            )
            button.grid(
                row=0, column=0, sticky="ew", padx=12, pady=(10, 4), columnspan=2
            )
            self._scene_buttons[scene.index] = button
            inner_row = 1
            if scene.intro_text:
                self._wrapped_label(card, scene.intro_text).grid(
                    row=inner_row,
                    column=0,
                    columnspan=2,
                    sticky="ew",
                    padx=12,
                    pady=(0, 8),
                )
                inner_row += 1
            inner_row = self._add_scene_entities(card, inner_row, scene)
            for section in scene.sections:
                inner_row = self._add_scene_section(card, inner_row, section)
            row += 1
        return row

    def _add_scene_entities(self, parent, row: int, scene: ScenarioBoardScene) -> int:
        parts = []
        for label, values in (
            ("NPCs", scene.npcs),
            ("Villains", scene.villains),
            ("Places", scene.places),
            ("Maps", scene.maps),
        ):
            if values:
                parts.append(f"{label}: {', '.join(values)}")
        if not parts:
            return row
        self._wrapped_label(
            parent, "  •  ".join(parts), text_color=TABLE_PALETTE["muted"]
        ).grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))
        return row + 1

    def _add_scene_section(self, parent, row: int, section: dict[str, Any]) -> int:
        title = f"{section.get('emoji', '')} {section.get('title', '')}".strip()
        ctk.CTkLabel(
            parent,
            text=title,
            text_color=TABLE_PALETTE["accent"],
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 2))
        items = section.get("items") or []
        text = (
            "\n".join(f"• {item}" for item in items)
            if items
            else str(section.get("raw_text") or "").strip()
        )
        if text:
            self._wrapped_label(parent, text).grid(
                row=row + 1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 4)
            )
            return row + 2
        return row + 1

    def _current_scene(self) -> ScenarioBoardScene | None:
        for scene in self._data.scenes:
            if scene.index == self._current_scene_index:
                return scene
        return self._data.scenes[0] if self._data.scenes else None

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
        next_scene = next(
            (
                scene.index
                for scene in self._data.scenes
                if scene.index not in self._completed_scenes
            ),
            None,
        )
        if next_scene is not None:
            self._current_scene_index = next_scene
        self._refresh_scene_selection()
        self._notify_state_changed()

    def _refresh_scene_selection(self) -> None:
        for index, button in self._scene_buttons.items():
            done = index in self._completed_scenes
            current = index == self._current_scene_index
            prefix = "✓ " if done else ("▶ " if current else "")
            scene = next(
                (
                    candidate
                    for candidate in self._data.scenes
                    if candidate.index == index
                ),
                None,
            )
            if scene is not None:
                button.configure(
                    text=f"{prefix}{scene.index}. {scene.title}",
                    fg_color=(
                        TABLE_PALETTE["accent_soft"]
                        if current
                        else TABLE_PALETTE["table_chip"]
                    ),
                )
        scene = self._current_scene()
        if self._scene_status_label is not None:
            if scene is None:
                text = "Scenario Board"
            else:
                text = f"Current scene: {scene.index}. {scene.title}  •  Done: {len(self._completed_scenes)}/{len(self._data.scenes)}"
            self._scene_status_label.configure(text=text)

    def _launch_current_bundle(self) -> None:
        if callable(self._launch_bundle_callback):
            self._launch_bundle_callback(self._current_bundle())

    def _open_current_scene_map(self) -> None:
        bundle = self._current_bundle()
        map_name = bundle.maps[0] if bundle.maps else None
        if callable(self._open_scene_map_callback):
            self._open_scene_map_callback(map_name)

    def _open_world_map(self) -> None:
        bundle = self._current_bundle()
        map_name = bundle.world_maps[0] if bundle.world_maps else None
        if callable(self._open_world_map_callback):
            self._open_world_map_callback(map_name)

    def _open_entities(self, entity_type: str) -> None:
        bundle = self._current_bundle()
        names = {
            "NPCs": bundle.npcs,
            "Villains": bundle.villains,
            "Places": bundle.places,
        }.get(entity_type, ())
        for name in names:
            self._open_entity(entity_type, name)

    def _open_entity(self, entity_type: str, name: str) -> None:
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

    @staticmethod
    def _wrapped_label(
        parent,
        text: str,
        *,
        text_color: str | None = None,
        horizontal_padding: int = 36,
    ) -> ctk.CTkLabel:
        """Create a label whose wrap length follows the available card width."""
        label = ctk.CTkLabel(
            parent,
            text=text,
            text_color=text_color or TABLE_PALETTE["text"],
            justify="left",
            wraplength=760,
            anchor="w",
        )

        def update_wraplength(event=None) -> None:
            width = getattr(event, "width", 0) or parent.winfo_width()
            label.configure(wraplength=max(240, width - horizontal_padding))

        parent.bind("<Configure>", update_wraplength, add="+")
        label.after_idle(update_wraplength)
        return label

    @staticmethod
    def _card(parent) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=TABLE_PALETTE["panel_alt"],
            corner_radius=14,
            border_width=1,
            border_color=TABLE_PALETTE["panel_border"],
        )
        card.grid_columnconfigure(0, weight=1)
        return card

    @staticmethod
    def _card_title(parent, text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            parent,
            text=text,
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
