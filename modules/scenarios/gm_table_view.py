"""Virtual tabletop style GM workspace."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from uuid import uuid4

import customtkinter as ctk

from modules.characters.character_graph_editor import CharacterGraphEditor
from modules.generic.entity_detail_factory import create_entity_detail_frame
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.layout_scheduler import LayoutSettleScheduler
from modules.helpers.logging_helper import log_info, log_warning
from modules.helpers.template_loader import load_template as load_entity_template
from modules.maps.controllers.display_map_controller import DisplayMapController
from modules.maps.world_map_view import WorldMapPanel
from modules.objects.loot_generator_panel import LootGeneratorPanel
from modules.puzzles.puzzle_display_window import create_puzzle_display_frame
from modules.scenarios.gm_screen import CampaignDashboardPanel
from modules.scenarios.gm_table import GMTableLayoutStore, GMTableWorkspace
from modules.scenarios.gm_table.handouts.page import GMTableHandoutsPage
from modules.scenarios.gm_table.pages import (
    GMTableHostedPage,
    GMTableImageLibraryPage,
    GMTableNotePage,
)
from modules.scenarios.gm_table.workspace import (
    PanelDefinition,
    TABLE_PALETTE,
    resolve_default_panel_size,
)
from modules.scenarios.plot_twist_panel import PlotTwistPanel
from modules.scenarios.random_tables_panel import RandomTablesPanel
from modules.scenarios.scenario_graph_editor import ScenarioGraphEditor
from modules.scenarios.scene_flow_viewer import create_scene_flow_frame
from modules.ui.chatbot_dialog import (
    _DEFAULT_NAME_FIELD_OVERRIDES as CHATBOT_NAME_OVERRIDES,
    open_chatbot_dialog,
)
from modules.whiteboard.controllers.whiteboard_controller import WhiteboardController


ENTITY_TYPES = (
    "Factions",
    "Bases",
    "Places",
    "NPCs",
    "Villains",
    "PCs",
    "Creatures",
    "Scenarios",
    "Clues",
    "Informations",
    "Puzzles",
)

TITLE_KEY_ENTITY_TYPES = {"Scenarios", "Informations"}
MAP_PANEL_KINDS = {"world_map", "map_tool"}


class GMTableView(ctk.CTkFrame):
    """Freeform GM workspace with draggable panels."""

    def __init__(
        self,
        master,
        *,
        scenario_item: dict,
        root_app=None,
        layout_store: GMTableLayoutStore | None = None,
    ) -> None:
        super().__init__(master, fg_color=TABLE_PALETTE["table_bg"])
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.scenario = scenario_item or {}
        self.scenario_name = (
            self.scenario.get("Title")
            or self.scenario.get("Name")
            or "Scenario"
        )
        self._root_app = root_app
        self.layout_store = layout_store or GMTableLayoutStore()
        self._layout_settle_scheduler = LayoutSettleScheduler(self)
        self._workspace_loaded = False
        self._templates = {
            "Campaigns": load_entity_template("campaigns"),
            "Scenarios": load_entity_template("scenarios"),
            "Places": load_entity_template("places"),
            "Bases": load_entity_template("bases"),
            "NPCs": load_entity_template("npcs"),
            "Villains": load_entity_template("villains"),
            "PCs": load_entity_template("pcs"),
            "Factions": load_entity_template("factions"),
            "Creatures": load_entity_template("creatures"),
            "Clues": load_entity_template("clues"),
            "Informations": load_entity_template("informations"),
            "Puzzles": load_entity_template("puzzles"),
            "Objects": load_entity_template("objects"),
            "Maps": load_entity_template("maps"),
        }
        self.wrappers = {
            "Campaigns": GenericModelWrapper("campaigns"),
            "Scenarios": GenericModelWrapper("scenarios"),
            "Places": GenericModelWrapper("places"),
            "Bases": GenericModelWrapper("bases"),
            "NPCs": GenericModelWrapper("npcs"),
            "Villains": GenericModelWrapper("villains"),
            "PCs": GenericModelWrapper("pcs"),
            "Factions": GenericModelWrapper("factions"),
            "Creatures": GenericModelWrapper("creatures"),
            "Clues": GenericModelWrapper("clues"),
            "Informations": GenericModelWrapper("informations"),
            "Puzzles": GenericModelWrapper("puzzles"),
            "Objects": GenericModelWrapper("objects"),
        }
        self.map_wrapper = GenericModelWrapper("maps")

        self._add_menu_options = [
            "Campaign Dashboard",
            "World Map",
            "Map Tool",
            "Scene Flow",
            "Image Library",
            "Handouts",
            "Loot Generator",
            "Whiteboard",
            "Random Tables",
            "Plot Twists",
            *ENTITY_TYPES,
            "Puzzle Display",
            "Note Tab",
            "Character Graph",
            "Scenario Graph Editor",
            "separator",
            ("Save Table Layout", self.save_layout_now),
            ("Tile Panels", self._tile_panels),
            ("Cascade Panels", self._cascade_panels),
            ("Restore Minimized Panels", self._restore_all_panels),
            ("Reset Table", self.reset_table),
            ("Open Chatbot", self.open_chatbot),
        ]
        self._add_menu = self._build_add_menu()
        self._fog_menu = self._build_fog_menu()

        self._build_toolbar()
        self.workspace = GMTableWorkspace(
            self,
            on_panel_build=self._mount_panel_content,
            on_layout_changed=self._persist_layout,
        )
        self.workspace.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        self.after_idle(self._restore_or_seed_layout)

    def _build_toolbar(self) -> None:
        """Build top controls."""
        bar = ctk.CTkFrame(
            self,
            fg_color=TABLE_PALETTE["table_alt"],
            corner_radius=26,
            border_width=1,
            border_color=TABLE_PALETTE["table_line"],
        )
        bar.grid(row=0, column=0, sticky="ew", padx=18, pady=18)
        bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bar,
            text=self.scenario_name,
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=18, pady=14, sticky="ew")

        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.grid(row=0, column=1, padx=16, pady=14, sticky="e")

        self.add_button = ctk.CTkButton(
            actions,
            text="+ Add Panel",
            width=132,
            height=36,
            fg_color=TABLE_PALETTE["accent"],
            hover_color="#D97706",
            text_color="#10131B",
            corner_radius=16,
            command=self._show_add_menu,
        )
        self.add_button.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Scene",
            width=100,
            height=36,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=16,
            command=self._focus_or_open_world_map_panel,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Map Tool",
            width=108,
            height=36,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=16,
            command=self._focus_or_open_map_tool_panel,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Player View",
            width=116,
            height=36,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=16,
            command=self._open_player_view_for_active_panel,
        ).pack(side="left", padx=(0, 10))

        self.fog_button = ctk.CTkButton(
            actions,
            text="Fog",
            width=84,
            height=36,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=16,
            command=self._show_fog_menu,
        )
        self.fog_button.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Tile",
            width=84,
            height=36,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=16,
            command=self._tile_panels,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Cascade",
            width=94,
            height=36,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=16,
            command=self._cascade_panels,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Restore All",
            width=118,
            height=36,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=16,
            command=self._restore_all_panels,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Save",
            width=84,
            height=36,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=16,
            command=self.save_layout_now,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Reset",
            width=84,
            height=36,
            fg_color="#2B1C23",
            hover_color="#40222B",
            text_color=TABLE_PALETTE["text"],
            corner_radius=16,
            command=self.reset_table,
        ).pack(side="left")

    def _build_fog_menu(self) -> tk.Menu:
        """Build tabletop fog actions for the active map-capable panel."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Add Fog Brush", command=lambda: self._apply_fog_action("add"))
        menu.add_command(label="Reveal Brush", command=lambda: self._apply_fog_action("rem"))
        menu.add_command(label="Add Fog Rectangle", command=lambda: self._apply_fog_action("add_rect"))
        menu.add_command(label="Reveal Rectangle", command=lambda: self._apply_fog_action("rem_rect"))
        menu.add_separator()
        menu.add_command(label="Clear Fog", command=lambda: self._apply_fog_action("clear"))
        menu.add_command(label="Reset Fog", command=lambda: self._apply_fog_action("reset"))
        menu.add_command(label="Undo Fog", command=lambda: self._apply_fog_action("undo"))
        return menu

    def _build_add_menu(self) -> tk.Menu:
        """Build the add panel menu."""
        menu = tk.Menu(self, tearoff=0)
        for option in self._add_menu_options:
            if option == "separator":
                menu.add_separator()
                continue
            if isinstance(option, tuple):
                label, command = option
                menu.add_command(label=label, command=command)
                continue
            menu.add_command(label=option, command=lambda value=option: self._handle_add_option(value))
        return menu

    def _show_add_menu(self) -> None:
        """Open the add menu under the toolbar button."""
        x = self.add_button.winfo_rootx()
        y = self.add_button.winfo_rooty() + self.add_button.winfo_height()
        try:
            self._add_menu.tk_popup(x, y)
        finally:
            self._add_menu.grab_release()

    def _restore_or_seed_layout(self) -> None:
        """Restore saved workspace or create a starter tabletop."""
        layout = self.layout_store.get_scenario_layout(self.scenario_name)
        if layout.get("panels"):
            self.workspace.restore(layout)
        else:
            self._seed_default_panels()
        self._workspace_loaded = True

    def _seed_default_panels(self) -> None:
        """Build a map-centric default workspace."""
        starter_map_name = self._infer_starting_map_name()
        self._create_panel(
            "world_map",
            "Scene Map",
            self._panel_state(map_name=starter_map_name),
            geometry={"x": 24, "y": 24, "width": 980, "height": 640},
        )
        self._create_panel(
            "map_tool",
            "Map Tool",
            self._panel_state(map_name=starter_map_name),
            geometry={"x": 1020, "y": 24, "width": 620, "height": 640},
        )
        self._create_panel(
            "handouts",
            "Handouts",
            {"scenario_name": self.scenario_name},
            geometry={"x": 24, "y": 680, "width": 440, "height": 300},
        )
        self._create_panel(
            "note",
            "Session Notes",
            {"text": ""},
            geometry={"x": 476, "y": 680, "width": 520, "height": 300},
        )
        self._create_panel(
            "scene_flow",
            f"Scene Flow: {self.scenario_name}",
            {"scenario_title": self.scenario_name},
            geometry={"x": 1012, "y": 680, "width": 628, "height": 300},
        )

    def _persist_layout(self) -> None:
        """Persist the current workspace after edits settle."""
        if not self._workspace_loaded:
            return
        self._layout_settle_scheduler.schedule("gm_table_layout", self._save_layout_snapshot)

    def _save_layout_snapshot(self) -> None:
        """Write the latest workspace snapshot to storage."""
        try:
            self.layout_store.save_scenario_layout(self.scenario_name, self.workspace.serialize())
        except Exception as exc:
            log_warning(
                f"Unable to save GM Table layout: {exc}",
                func_name="GMTableView._save_layout_snapshot",
            )

    def save_layout_now(self) -> None:
        """Persist immediately and notify the user."""
        self._save_layout_snapshot()
        messagebox.showinfo("GM Table", f"Layout saved for '{self.scenario_name}'.")

    def reset_table(self) -> None:
        """Reset the scenario workspace to the starter layout."""
        if not messagebox.askyesno(
            "Reset GM Table",
            "Clear every panel on this table and recreate the starter layout?",
        ):
            return
        self.workspace.clear()
        self.layout_store.clear_scenario_layout(self.scenario_name)
        self._seed_default_panels()

    def _tile_panels(self) -> None:
        """Tile panels into a readable layout."""
        self.workspace.auto_arrange()

    def _cascade_panels(self) -> None:
        """Cascade visible panels like desktop windows."""
        self.workspace.cascade_panels()

    def _restore_all_panels(self) -> None:
        """Restore minimized panels from the workspace tray."""
        self.workspace.restore_all_panels()

    def _panel_state(self, **state) -> dict:
        """Build a clean state dictionary."""
        return {key: value for key, value in state.items() if value not in (None, "", [], {})}

    def _create_panel(self, kind: str, title: str, state: dict, *, geometry: dict | None = None) -> str:
        """Create a new floating panel."""
        definition = PanelDefinition(
            panel_id=uuid4().hex,
            kind=kind,
            title=title,
            state=dict(state or {}),
        )
        self.workspace.add_panel(definition, geometry=geometry)
        return definition.panel_id

    def _preferred_entity_geometry(self, entity_type: str) -> dict[str, int]:
        """Return the default geometry for an entity panel."""
        width, height = resolve_default_panel_size("entity", {"entity_type": entity_type})
        return {"width": width, "height": height}

    @staticmethod
    def _normalize_entity_name(value) -> str:
        """Normalize an entity identifier for comparisons."""
        return str(value or "").strip().casefold()

    @staticmethod
    def _entity_name_keys(entity_type: str) -> tuple[str, ...]:
        """Return the ordered name keys for an entity type."""
        if entity_type in TITLE_KEY_ENTITY_TYPES:
            return ("Title", "Name")
        return ("Name", "Title")

    def _entity_label(self, entity_type: str, item: dict | None, *, fallback: str = "") -> str:
        """Return the canonical display label for an entity."""
        if isinstance(item, dict):
            for key in self._entity_name_keys(entity_type):
                value = str(item.get(key) or "").strip()
                if value:
                    return value
        return str(fallback or "").strip() or "Unnamed"

    def _entity_aliases(
        self,
        entity_type: str,
        *,
        item: dict | None = None,
        fallback: str = "",
    ) -> set[str]:
        """Return every normalized alias that may identify an entity."""
        aliases: set[str] = set()
        if isinstance(item, dict):
            for key in self._entity_name_keys(entity_type):
                value = self._normalize_entity_name(item.get(key))
                if value:
                    aliases.add(value)
        fallback_value = self._normalize_entity_name(fallback)
        if fallback_value:
            aliases.add(fallback_value)
        return aliases

    def _infer_starting_map_name(self) -> str | None:
        """Infer a likely starting map from the scenario record."""
        for key in ("Map", "MapName", "WorldMap", "WorldMapName", "SceneMap"):
            value = str(self.scenario.get(key) or "").strip()
            if value:
                return value
        return None

    def _show_fog_menu(self) -> None:
        """Open the fog menu beneath the toolbar button."""
        x = self.fog_button.winfo_rootx()
        y = self.fog_button.winfo_rooty() + self.fog_button.winfo_height()
        try:
            self._fog_menu.tk_popup(x, y)
        finally:
            self._fog_menu.grab_release()

    def _resolve_tabletop_context(self, *, prefer_world_map: bool = False) -> tuple[str | None, str | None, object | None]:
        """Return the most relevant map-capable panel, kind, and payload."""
        preferred_kinds = {"world_map"} if prefer_world_map else MAP_PANEL_KINDS
        panel_id = self.workspace.get_active_panel_id(kinds=preferred_kinds, include_minimized=False)
        if panel_id is None and not prefer_world_map:
            panel_id = self.workspace.get_active_panel_id(kinds=MAP_PANEL_KINDS, include_minimized=False)
        if panel_id is None:
            records = self.workspace.list_panels(
                kinds={"world_map"} if prefer_world_map else MAP_PANEL_KINDS,
                include_minimized=True,
            )
            if not prefer_world_map and not records:
                records = self.workspace.list_panels(kinds=MAP_PANEL_KINDS, include_minimized=True)
            if records:
                panel_id = str(records[-1]["panel_id"])
        if panel_id is None:
            return None, None, None
        definition = self.workspace.get_panel_definition(panel_id)
        payload = self.workspace.get_panel_payload(panel_id)
        kind = definition.kind if definition is not None else None
        return panel_id, kind, payload

    def _current_tabletop_map_name(self) -> str | None:
        """Return the active map name from the tabletop when available."""
        _panel_id, kind, payload = self._resolve_tabletop_context()
        if kind == "world_map":
            return str(getattr(payload, "current_map_name", "") or "").strip() or None
        if kind == "map_tool":
            current_map = getattr(payload, "current_map", None) or {}
            return str(current_map.get("Name") or "").strip() or None
        return None

    def _focus_or_open_world_map_panel(self, map_name: str | None = None) -> str | None:
        """Focus an existing world map panel or create one."""
        target_map = str(map_name or self._current_tabletop_map_name() or self._infer_starting_map_name() or "").strip()
        records = self.workspace.list_panels(kinds={"world_map"}, include_minimized=True)
        if records:
            panel_id = str(records[-1]["panel_id"])
            self.workspace.bring_to_front(panel_id)
            payload = records[-1]["payload"]
            if target_map and hasattr(payload, "load_map"):
                try:
                    payload.load_map(target_map, push_history=False)
                except Exception:
                    pass
            return panel_id
        return self._create_panel(
            "world_map",
            "Scene Map",
            self._panel_state(map_name=target_map),
        )

    def _focus_or_open_map_tool_panel(self, map_name: str | None = None) -> str | None:
        """Focus an existing map tool panel or create one."""
        target_map = str(map_name or self._current_tabletop_map_name() or self._infer_starting_map_name() or "").strip()
        records = self.workspace.list_panels(kinds={"map_tool"}, include_minimized=True)
        if records:
            panel_id = str(records[-1]["panel_id"])
            self.workspace.bring_to_front(panel_id)
            payload = records[-1]["payload"]
            if target_map and hasattr(payload, "open_map_by_name"):
                try:
                    payload.open_map_by_name(target_map)
                except Exception:
                    pass
            return panel_id
        return self._create_panel(
            "map_tool",
            "Map Tool",
            self._panel_state(map_name=target_map),
        )

    def _open_player_view_for_active_panel(self) -> None:
        """Open the player display for the active scene map."""
        panel_id, kind, payload = self._resolve_tabletop_context(prefer_world_map=True)
        if kind != "world_map" or payload is None:
            target_map = self._current_tabletop_map_name()
            panel_id = self._focus_or_open_world_map_panel(target_map)
            if panel_id is None:
                messagebox.showinfo("GM Table", "Open a scene map before launching player view.")
                return
            payload = self.workspace.get_panel_payload(panel_id)
            kind = "world_map"
        if kind == "world_map" and hasattr(payload, "open_player_display"):
            payload.open_player_display()

    def _apply_fog_action(self, action: str) -> None:
        """Route a fog command to the active map-capable panel."""
        _panel_id, _kind, payload = self._resolve_tabletop_context()
        if payload is None:
            messagebox.showinfo("GM Table", "Open a scene map or map tool panel to work with fog.")
            return
        if action in {"add", "rem", "add_rect", "rem_rect"} and hasattr(payload, "_set_fog"):
            payload._set_fog(action)
            return
        if action == "clear" and hasattr(payload, "clear_fog"):
            payload.clear_fog()
            return
        if action == "reset" and hasattr(payload, "reset_fog"):
            payload.reset_fog()
            return
        if action == "undo" and hasattr(payload, "undo_fog"):
            payload.undo_fog()
            return
        messagebox.showinfo("GM Table", "This panel does not support the requested fog command.")

    def _handle_add_option(self, option: str) -> None:
        """Route add-menu options."""
        if option == "Campaign Dashboard":
            self._create_panel("campaign_dashboard", "Campaign Dashboard", {})
            return
        if option == "World Map":
            self._create_panel("world_map", "World Map", {})
            return
        if option == "Map Tool":
            self._create_panel("map_tool", "Map Tool", {})
            return
        if option == "Scene Flow":
            self._create_panel("scene_flow", f"Scene Flow: {self.scenario_name}", {"scenario_title": self.scenario_name})
            return
        if option == "Image Library":
            self._create_panel("image_library", "Image Library", {})
            return
        if option == "Handouts":
            self._create_panel("handouts", "Handouts", {"scenario_name": self.scenario_name})
            return
        if option == "Loot Generator":
            self._create_panel("loot_generator", "Loot Generator", {})
            return
        if option == "Whiteboard":
            self._create_panel("whiteboard", "Whiteboard", {})
            return
        if option == "Random Tables":
            self._create_panel("random_tables", "Random Tables", {})
            return
        if option == "Plot Twists":
            self._create_panel("plot_twists", "Plot Twists", {})
            return
        if option == "Puzzle Display":
            self._open_puzzle_selection()
            return
        if option == "Note Tab":
            existing_notes = [
                panel
                for panel in self.workspace.serialize().get("panels", [])
                if panel.get("kind") == "note"
            ]
            self._create_panel("note", f"Note {len(existing_notes) + 1}", {"text": ""})
            return
        if option == "Character Graph":
            self._create_panel("character_graph", "Character Graph", {})
            return
        if option == "Scenario Graph Editor":
            self._create_panel("scenario_graph", "Scenario Graph", {})
            return
        if option in ENTITY_TYPES:
            self._open_entity_selection(option)
            return

    def _mount_panel_content(self, parent: ctk.CTkFrame, definition: PanelDefinition):
        """Build the page hosted inside a floating panel."""
        kind = definition.kind
        try:
            if kind == "campaign_dashboard":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_dashboard_content(host),
                )
            if kind == "world_map":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_world_map_content(host, definition.state),
                    state_getter=lambda payload: self._panel_state(
                        map_name=getattr(payload, "current_map_name", None)
                    ),
                )
            if kind == "map_tool":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_map_tool_content(host, definition.state),
                    state_getter=lambda payload: self._panel_state(
                        map_name=((getattr(payload, "current_map", None) or {}).get("Name"))
                    ),
                )
            if kind == "scene_flow":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_scene_flow_content(host, definition.state),
                    state_getter=lambda _payload: self._panel_state(
                        scenario_title=definition.state.get("scenario_title") or self.scenario_name
                    ),
                )
            if kind == "image_library":
                return GMTableImageLibraryPage(parent, initial_state=definition.state)
            if kind == "handouts":
                return GMTableHandoutsPage(
                    parent,
                    scenario_name=self.scenario_name,
                    scenario_item=self.scenario,
                    wrappers=self.wrappers,
                    map_wrapper=self.map_wrapper,
                    initial_state=definition.state,
                )
            if kind == "loot_generator":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_loot_generator_content(host),
                )
            if kind == "whiteboard":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_whiteboard_content(host),
                    close_callback=lambda payload: payload.close(),
                )
            if kind == "random_tables":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_random_tables_content(host, definition.state),
                    state_getter=lambda payload: payload.get_state(),
                )
            if kind == "plot_twists":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_plot_twists_content(host),
                )
            if kind == "entity":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_entity_content(host, definition.state),
                )
            if kind == "puzzle_display":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_puzzle_display_content(host, definition.state),
                )
            if kind == "character_graph":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_character_graph_content(host),
                )
            if kind == "scenario_graph":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_scenario_graph_content(host),
                )
            if kind == "note":
                return GMTableNotePage(parent, initial_text=str(definition.state.get("text") or ""))
        except Exception as exc:
            log_warning(
                f"Unable to build GM Table panel '{definition.title}': {exc}",
                func_name="GMTableView._mount_panel_content",
            )

        fallback = ctk.CTkLabel(
            parent,
            text=f"Panel unavailable: {definition.title}",
            text_color=TABLE_PALETTE["text"],
            justify="left",
        )
        fallback.grid(row=0, column=0, sticky="nsew")
        return fallback

    def _build_dashboard_content(self, host):
        """Build the campaign dashboard page."""
        widget = CampaignDashboardPanel(
            host,
            wrappers=self.wrappers,
            open_entity_callback=self.open_entity_panel,
        )
        widget.grid(row=0, column=0, sticky="nsew")
        return widget

    def _build_world_map_content(self, host, state: dict):
        """Build the world map page."""
        widget = WorldMapPanel(host)
        widget.grid(row=0, column=0, sticky="nsew")
        map_name = state.get("map_name")
        if map_name:
            try:
                widget.load_map(map_name, push_history=False)
            except Exception:
                pass
        return widget

    def _build_map_tool_content(self, host, state: dict):
        """Build the embedded map tool page."""
        controller = DisplayMapController(
            host,
            self.map_wrapper,
            self._templates["Maps"],
            root_app=self._root_app or self,
        )
        map_name = state.get("map_name")
        if map_name and hasattr(controller, "open_map_by_name"):
            try:
                controller.open_map_by_name(map_name)
            except Exception:
                pass
        return controller

    def _build_scene_flow_content(self, host, state: dict):
        """Build the scene flow page."""
        widget = create_scene_flow_frame(
            host,
            scenario_title=state.get("scenario_title") or self.scenario_name,
        )
        widget.grid(row=0, column=0, sticky="nsew")
        return widget

    def _build_loot_generator_content(self, host):
        """Build the loot generator page."""
        widget = LootGeneratorPanel(
            host,
            object_wrapper=self.wrappers.get("Objects"),
            template=self._templates.get("Objects"),
        )
        widget.grid(row=0, column=0, sticky="nsew")
        return widget

    def _build_whiteboard_content(self, host):
        """Build the whiteboard page."""
        controller = WhiteboardController(host, root_app=self._root_app or self)
        return controller

    def _build_random_tables_content(self, host, state: dict):
        """Build the random tables page."""
        widget = RandomTablesPanel(host, initial_state=state or None)
        widget.grid(row=0, column=0, sticky="nsew")
        return widget

    def _build_plot_twists_content(self, host):
        """Build the plot twist page."""
        widget = PlotTwistPanel(host)
        widget.grid(row=0, column=0, sticky="nsew")
        return widget

    def _build_entity_content(self, host, state: dict):
        """Build an entity detail page."""
        entity_type = state.get("entity_type")
        entity_name = state.get("entity_name")
        item = self._load_entity_item(entity_type, entity_name)
        frame = create_entity_detail_frame(
            entity_type,
            item,
            master=host,
            open_entity_callback=self.open_entity_panel,
        )
        frame.grid(row=0, column=0, sticky="nsew")
        return frame

    def _build_puzzle_display_content(self, host, state: dict):
        """Build the puzzle display page."""
        puzzle_name = state.get("puzzle_name")
        wrapper = self.wrappers.get("Puzzles")
        items = wrapper.load_items() if wrapper is not None else []
        puzzle_item = next((item for item in items if item.get("Name") == puzzle_name), {})
        frame = create_puzzle_display_frame(host, puzzle_item, scrollable=False)
        frame.grid(row=0, column=0, sticky="nsew")
        return frame

    def _build_character_graph_content(self, host):
        """Build the character graph page."""
        widget = CharacterGraphEditor(
            host,
            npc_wrapper=self.wrappers["NPCs"],
            pc_wrapper=self.wrappers["PCs"],
            faction_wrapper=self.wrappers["Factions"],
            villain_wrapper=self.wrappers["Villains"],
            allowed_entity_types={"npc", "pc", "villain"},
        )
        widget.grid(row=0, column=0, sticky="nsew")
        return widget

    def _build_scenario_graph_content(self, host):
        """Build the scenario graph page."""
        widget = ScenarioGraphEditor(
            host,
            self.wrappers["Scenarios"],
            self.wrappers["NPCs"],
            self.wrappers["Creatures"],
            self.wrappers["Places"],
            faction_wrapper=self.wrappers["Factions"],
            villain_wrapper=self.wrappers["Villains"],
        )
        widget.grid(row=0, column=0, sticky="nsew")
        return widget

    def _load_entity_item(self, entity_type: str, entity_name: str):
        """Resolve an entity item by name/title."""
        wrapper = self.wrappers.get(entity_type)
        if wrapper is None:
            raise KeyError(f"Unknown entity type '{entity_type}'")
        items = wrapper.load_items()
        lookup_name = self._normalize_entity_name(entity_name)
        item = next(
            (
                record
                for record in items
                if lookup_name in self._entity_aliases(entity_type, item=record)
            ),
            None,
        )
        if item is None:
            raise KeyError(f"{entity_type} '{entity_name}' not found")
        return item

    def _find_existing_entity_panel(
        self,
        entity_type: str,
        entity_name: str,
        *,
        item: dict | None = None,
    ) -> str | None:
        """Return the existing entity panel id when present."""
        layout = self.workspace.serialize()
        lookup_names = self._entity_aliases(entity_type, item=item, fallback=entity_name)
        for panel in layout.get("panels", []):
            state = panel.get("state") or {}
            if (
                panel.get("kind") == "entity"
                and state.get("entity_type") == entity_type
                and self._normalize_entity_name(state.get("entity_name")) in lookup_names
            ):
                return str(panel.get("panel_id"))
        return None

    def open_entity_panel(self, entity_type: str, name: str) -> None:
        """Open a specific entity inside the GM Table."""
        try:
            item = self._load_entity_item(entity_type, name)
        except Exception as exc:
            messagebox.showerror("GM Table", str(exc))
            return

        label = self._entity_label(entity_type, item, fallback=name)
        existing = self._find_existing_entity_panel(entity_type, label, item=item)
        if existing is not None:
            self.workspace.bring_to_front(existing)
            preferred = self._preferred_entity_geometry(entity_type)
            self.workspace.ensure_panel_minimum_size(
                existing,
                preferred["width"],
                preferred["height"],
            )
            return

        singular = entity_type[:-1] if entity_type.endswith("s") else entity_type
        self._create_panel(
            "entity",
            f"{singular}: {label}",
            {
                "entity_type": entity_type,
                "entity_name": label,
            },
            geometry=self._preferred_entity_geometry(entity_type),
        )

    def _open_entity_selection(self, entity_type: str) -> None:
        """Open the generic picker for entity-backed panels."""
        wrapper = self.wrappers.get(entity_type)
        template = self._templates.get(entity_type)
        if wrapper is None or template is None:
            messagebox.showerror("GM Table", f"{entity_type} is not available.")
            return
        popup = ctk.CTkToplevel(self)
        popup.title(f"Select {entity_type}")
        popup.geometry("1200x800")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.focus_force()

        def _open_selected(selected_type: str, selected_name: str, item: dict | None = None) -> None:
            popup.destroy()
            self.open_entity_panel(
                selected_type,
                self._entity_label(selected_type, item, fallback=selected_name),
            )

        view = GenericListSelectionView(popup, entity_type, wrapper, template, _open_selected)
        view.pack(fill="both", expand=True)

    def _open_puzzle_selection(self) -> None:
        """Open the puzzle selector for a display panel."""
        popup = ctk.CTkToplevel(self)
        popup.title("Select Puzzle")
        popup.geometry("1200x800")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.focus_force()

        def _open_selected(_entity_type: str, selected_name: str) -> None:
            popup.destroy()
            self._create_panel(
                "puzzle_display",
                f"Puzzle Display: {selected_name}",
                {"puzzle_name": selected_name},
            )

        view = GenericListSelectionView(
            popup,
            "Puzzles",
            self.wrappers["Puzzles"],
            self._templates["Puzzles"],
            _open_selected,
        )
        view.pack(fill="both", expand=True)

    def open_chatbot(self, event=None) -> None:
        """Open the shared chatbot from the tabletop."""
        del event
        try:
            open_chatbot_dialog(
                self.winfo_toplevel(),
                wrappers=self.wrappers,
                name_field_overrides=CHATBOT_NAME_OVERRIDES,
            )
        except Exception as exc:
            log_warning(
                f"Unable to open GM Table chatbot: {exc}",
                func_name="GMTableView.open_chatbot",
            )
            messagebox.showerror("GM Table", "Chatbot is unavailable from this workspace.")

    def focus_panel(self, panel_id: str) -> None:
        """Bring a panel to the front."""
        self.workspace.bring_to_front(panel_id)

    def log_workspace_opened(self) -> None:
        """Write a trace entry once the view is live."""
        log_info(
            f"Opened GM Table for {self.scenario_name}",
            func_name="GMTableView.log_workspace_opened",
        )

    def destroy(self) -> None:
        """Persist and tear down embedded panels cleanly."""
        try:
            if self._workspace_loaded:
                self._save_layout_snapshot()
        except Exception:
            pass
        try:
            self._layout_settle_scheduler.cancel_all()
        except Exception:
            pass
        try:
            self.workspace.dispose()
        except Exception:
            pass
        super().destroy()
