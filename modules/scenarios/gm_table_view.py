"""Virtual tabletop style GM workspace."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from uuid import uuid4

import customtkinter as ctk

from modules.characters.character_graph_editor import CharacterGraphEditor
from modules.generic.detail_ui import build_scroll_host
from modules.generic.entity_detail_factory import create_entity_detail_frame
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.layout_scheduler import LayoutSettleScheduler
from modules.helpers.logging_helper import log_exception, log_info, log_warning
from modules.helpers.template_loader import load_template as load_entity_template
from modules.maps.controllers.display_map_controller import DisplayMapController
from modules.maps.world_map_view import WorldMapPanel
from modules.objects.loot_generator_panel import LootGeneratorPanel
from modules.objects.object_shelf_panel import create_object_shelf_panel
from modules.puzzles.puzzle_display_window import create_puzzle_display_frame
from modules.scenarios.gm_screen import CampaignDashboardPanel
from modules.scenarios.gm_table import GMTableLayoutStore, GMTableWorkspace
from modules.scenarios.gm_table.table_name_labels import build_table_switch_labels
from modules.scenarios.gm_table.organization.search_dialog import GMTablePanelSearchDialog
from modules.scenarios.gm_table.table_registry import (
    DEFAULT_GM_TABLE_ID,
    get_table_name,
    normalize_table_id,
)
from modules.scenarios.gm_table.attachments import (
    collect_entity_attachments,
    entity_has_attachments,
)
from modules.scenarios.gm_table.handouts.page import GMTableHandoutsPage
from modules.scenarios.gm_table.scenario_board import ScenarioBoardPanel, ScenarioBundle
from modules.scenarios.gm_table.container_window import GMTableContainerPage
from modules.scenarios.gm_table.pages import (
    GMTableAttachmentGallery,
    GMTableHostedPage,
    GMTableImageLibraryPage,
    GMTableImagePage,
    GMTableNotePage,
    GMTableStickyNotePage,
)
from modules.scenarios.gm_table.reveal import reveal_entity, reveal_image, reveal_map_payload
from modules.scenarios.session_notes import SessionControlsCallbacks
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
        table_id: str,
        table_name: str,
        on_switch_table=None,
        root_app=None,
        layout_store: GMTableLayoutStore | None = None,
    ) -> None:
        super().__init__(master, fg_color=TABLE_PALETTE["table_bg"])
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.table_id = normalize_table_id(table_id)
        default_table_name = get_table_name(self.table_id)
        self.table_name = (
            str(table_name or default_table_name).strip() or default_table_name
        )
        self.scenario = {}
        self.scenario_name = ""
        self._session_mid_var = tk.StringVar(value="1.0")
        self._session_end_var = tk.StringVar(value="2.0")
        self._on_switch_table = on_switch_table
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
            "Scenario Board",
            "Scene Flow",
            "Image Library",
            "Image from Library",
            "Handouts",
            "Container Window",
            "Loot Generator",
            "Object Shelf",
            "Whiteboard",
            "Random Tables",
            "Plot Twists",
            *ENTITY_TYPES,
            "Puzzle Display",
            "Note Tab",
            "Sticky Note",
            "Character Graph",
            "Scenario Graph Editor",
            "separator",
            ("Save Table Layout", self.save_layout_now),
            ("Search Panels", self._open_panel_search),
            ("Tile Panels", self._tile_panels),
            ("Align Left", lambda: self.workspace.align_panels("left")),
            ("Align Top", lambda: self.workspace.align_panels("top")),
            ("Align Center", lambda: self.workspace.align_panels("center_x")),
            ("Make Same Width", lambda: self.workspace.make_panels_same_size("width")),
            ("Make Same Height", lambda: self.workspace.make_panels_same_size("height")),
            ("Snap to Grid", lambda: self.workspace.snap_panels_to_grid()),
            ("Distribute Horizontally", lambda: self.workspace.distribute_panels("horizontal")),
            ("Distribute Vertically", lambda: self.workspace.distribute_panels("vertical")),
            ("Cluster Sticky Notes by Tag", lambda: self.workspace.cluster_sticky_notes("tag")),
            ("Cluster Sticky Notes by Color", lambda: self.workspace.cluster_sticky_notes("color")),
            ("Spread on Desk", self._spread_panels_on_desk),
            ("Cascade Panels", self._cascade_panels),
            ("Restore Minimized Panels", self._restore_all_panels),
            ("Reset Table", self.reset_table),
            ("Open Chatbot", self.open_chatbot),
        ]
        self._add_menu = self._build_add_menu()
        self._build_toolbar()
        self.workspace = GMTableWorkspace(
            self,
            on_panel_build=self._mount_panel_content,
            on_layout_changed=self._persist_layout,
            map_tool_window_provider=self._get_map_tool_window,
            on_reveal_requested=self._reveal_panel,
        )
        self.workspace.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        self.after_idle(self._restore_or_seed_layout)

    def _get_map_tool_window(self):
        """Return the standalone MapTool window if the root app has one open."""
        root_app = self._root_app
        if root_app is None:
            return None
        return getattr(root_app, "_map_tool_window", None)

    def _build_toolbar(self) -> None:
        """Build top controls."""
        bar = ctk.CTkFrame(
            self,
            fg_color=TABLE_PALETTE["table_alt"],
            corner_radius=26,
            border_width=1,
            border_color=TABLE_PALETTE["table_line"],
        )
        bar.grid(row=0, column=0, sticky="ew", padx=18, pady=10)
        bar.grid_columnconfigure(0, weight=1)

        title_frame = ctk.CTkFrame(bar, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=18, pady=8, sticky="ew")
        title_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            title_frame,
            text=self.table_name,
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            title_frame,
            text="Rename",
            width=86,
            height=28,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self._open_rename_dialog,
        ).grid(row=0, column=1, padx=(10, 0), sticky="e")

        actions = ctk.CTkFrame(bar, fg_color="transparent")
        actions.grid(row=0, column=1, padx=12, pady=8, sticky="e")

        table_names, self._table_name_to_id, self._table_label_by_id = (
            self._build_table_switch_options()
        )
        self.table_switch_var = tk.StringVar(
            value=self._table_label_by_id.get(self.table_id, self.table_name)
        )
        self.table_switch_menu = ctk.CTkOptionMenu(
            actions,
            values=table_names,
            variable=self.table_switch_var,
            width=132,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            button_color=TABLE_PALETTE["accent"],
            button_hover_color="#D97706",
            dropdown_fg_color=TABLE_PALETTE["table_alt"],
            dropdown_hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            dropdown_text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self._handle_table_switch,
        )
        self.table_switch_menu.pack(side="left", padx=(0, 10))

        self.add_button = ctk.CTkButton(
            actions,
            text="+ Add Panel",
            width=132,
            height=30,
            fg_color=TABLE_PALETTE["accent"],
            hover_color="#D97706",
            text_color="#10131B",
            corner_radius=14,
            command=self._show_add_menu,
        )
        self.add_button.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Map Tool",
            width=108,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self._focus_or_open_map_tool_panel,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Player View",
            width=116,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self._open_player_view_for_active_panel,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Search",
            width=92,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self._open_panel_search,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Tile",
            width=84,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self._tile_panels,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Spread on Desk",
            width=132,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self._spread_panels_on_desk,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Cascade",
            width=94,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self._cascade_panels,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Restore All",
            width=118,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self._restore_all_panels,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Save",
            width=84,
            height=30,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self.save_layout_now,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions,
            text="Reset",
            width=84,
            height=30,
            fg_color="#2B1C23",
            hover_color="#40222B",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=self.reset_table,
        ).pack(side="left")

    def _build_table_switch_options(
        self,
    ) -> tuple[list[str], dict[str, str], dict[str, str]]:
        """Build table switch labels from persisted names without using names as ids."""
        return build_table_switch_labels(self.layout_store.get_table_name)

    def refresh_table_names(self) -> None:
        """Refresh this window after any GM Table name changes."""
        self.table_name = self.layout_store.get_table_name(self.table_id)
        if hasattr(self, "title_label"):
            self.title_label.configure(text=self.table_name)
        table_names, self._table_name_to_id, self._table_label_by_id = (
            self._build_table_switch_options()
        )
        if hasattr(self, "table_switch_menu"):
            self.table_switch_menu.configure(values=table_names)
        if hasattr(self, "table_switch_var"):
            self.table_switch_var.set(
                self._table_label_by_id.get(self.table_id, self.table_name)
            )
        self._update_toplevel_title()

    def _update_toplevel_title(self) -> None:
        """Update the detached window title when this view is hosted in one."""
        try:
            top = self.winfo_toplevel()
            top.title(f"GM Table - {self.table_name}")
            top._gm_table_name = self.table_name
        except Exception as exc:
            log_warning(
                f"Unable to refresh GM Table window title for '{self.table_name}': {exc}",
                func_name="GMTableView.refresh_table_names",
            )

    def _open_rename_dialog(self) -> None:
        """Open a small dialog for editing this table display name."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Rename GM Table")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(dialog, text="Table name").grid(
            row=0, column=0, padx=18, pady=(18, 6), sticky="w"
        )
        name_var = tk.StringVar(value=self.table_name)
        entry = ctk.CTkEntry(dialog, textvariable=name_var, width=260)
        entry.grid(row=1, column=0, padx=18, pady=(0, 14), sticky="ew")

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.grid(row=2, column=0, padx=18, pady=(0, 18), sticky="e")

        def save() -> None:
            self.rename_table(name_var.get())
            dialog.destroy()

        ctk.CTkButton(buttons, text="Cancel", width=90, command=dialog.destroy).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(buttons, text="Save", width=90, command=save).pack(side="left")
        entry.bind("<Return>", lambda _event: save())
        entry.bind("<Escape>", lambda _event: dialog.destroy())
        entry.focus_set()
        entry.select_range(0, "end")

    def rename_table(self, name: str) -> None:
        """Delegate table renames to the root app so every label stays in sync."""
        root_app = self._root_app
        if root_app is not None and hasattr(root_app, "rename_gm_table"):
            root_app.rename_gm_table(self.table_id, name)
            return

        self.layout_store.save_table_name(self.table_id, name)
        self.refresh_table_names()

    def _handle_table_switch(self, table_name: str) -> None:
        """Request that the application opens or focuses another GM Table."""
        table_id = self._table_name_to_id.get(table_name)
        if table_id is None:
            self.table_switch_var.set(
                self._table_label_by_id.get(self.table_id, self.table_name)
            )
            return

        if table_id == self.table_id:
            return

        if self._on_switch_table is None:
            self.table_switch_var.set(
                self._table_label_by_id.get(self.table_id, self.table_name)
            )
            return

        self._on_switch_table(table_id)
        self.table_switch_var.set(
            self._table_label_by_id.get(self.table_id, self.table_name)
        )

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
            menu.add_command(
                label=option,
                command=lambda value=option: self._handle_add_option(value),
            )
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
        layout = self.layout_store.get_table_layout(self.table_id)
        layout = self._filter_attachmentless_entity_panels(layout)
        if layout.get("panels"):
            self.workspace.restore(layout)
        else:
            self._seed_default_panels()
        self._workspace_loaded = True

    def _filter_attachmentless_entity_panels(self, layout: dict) -> dict:
        """Drop only saved attachment-gallery panels that no longer have attachments."""
        if not isinstance(layout, dict):
            return {}
        filtered = dict(layout)
        panels = []
        for panel in list(layout.get("panels") or []):
            if not isinstance(panel, dict) or panel.get("kind") != "entity":
                panels.append(panel)
                continue
            state = panel.get("state") or {}
            if not isinstance(state, dict) or state.get("attachment_only") is not True:
                panels.append(panel)
                continue
            entity_type = str(state.get("entity_type") or "")
            entity_name = str(state.get("entity_name") or "")
            try:
                item = self._load_entity_item(entity_type, entity_name)
            except Exception:
                panels.append(panel)
                continue
            if entity_has_attachments(item):
                panels.append(panel)
        filtered["panels"] = panels
        return filtered

    def _seed_default_panels(self) -> None:
        """Build the default table workspace without binding it to a scenario."""
        table_id = normalize_table_id(getattr(self, "table_id", DEFAULT_GM_TABLE_ID))
        if table_id != DEFAULT_GM_TABLE_ID:
            self._create_panel(
                "note",
                f"{self.table_name} Notes",
                {
                    "text": (
                        "Use this side table for notes, maps, handouts, "
                        "or temporary planning."
                    )
                },
                geometry={"x": 24, "y": 24, "width": 520, "height": 360},
            )
            return

        self._create_panel(
            "campaign_dashboard",
            "Campaign Dashboard",
            {},
            geometry={"x": 24, "y": 24, "width": 900, "height": 700},
        )
        self._create_panel(
            "note",
            f"{self.table_name} Notes",
            {"text": ""},
            geometry={"x": 948, "y": 24, "width": 520, "height": 520},
        )

    def _persist_layout(self) -> None:
        """Persist the current workspace after edits settle."""
        if not self._workspace_loaded:
            return
        self._layout_settle_scheduler.schedule(
            "gm_table_layout", self._save_layout_snapshot
        )

    def _save_layout_snapshot(self) -> None:
        """Write the latest workspace snapshot to storage."""
        try:
            self.layout_store.save_table_layout(
                self.table_id, self.workspace.serialize()
            )
        except Exception as exc:
            log_warning(
                f"Unable to save GM Table layout: {exc}",
                func_name="GMTableView._save_layout_snapshot",
            )

    def save_layout_now(self) -> None:
        """Persist immediately and notify the user."""
        self._save_layout_snapshot()
        messagebox.showinfo("GM Table", f"Layout saved for '{self.table_name}'.")

    def reset_table(self) -> None:
        """Reset the table workspace to the starter layout."""
        if not messagebox.askyesno(
            "Reset GM Table",
            "Clear every panel on this table and recreate the starter layout?",
        ):
            return
        self.workspace.clear()
        self.layout_store.clear_table_layout(self.table_id)
        self._seed_default_panels()

    def _open_panel_search(self) -> None:
        """Open panel search and jump dialog."""
        GMTablePanelSearchDialog(self, workspace=self.workspace)

    def _tile_panels(self) -> None:
        """Tile panels into a readable layout."""
        self.workspace.auto_arrange()

    def _spread_panels_on_desk(self) -> None:
        """Spread visible panels around the current tabletop view."""
        workspace = getattr(self, "workspace", None)
        spread_panels = getattr(workspace, "spread_panels_on_desk", None)
        if callable(spread_panels):
            spread_panels()

    def _cascade_panels(self) -> None:
        """Cascade visible panels like desktop windows."""
        self.workspace.cascade_panels()

    def _restore_all_panels(self) -> None:
        """Restore minimized panels from the workspace tray."""
        self.workspace.restore_all_panels()

    def _panel_state(self, **state) -> dict:
        """Build a clean state dictionary."""
        return {
            key: value
            for key, value in state.items()
            if value not in (None, "", [], {})
        }

    def _create_panel(
        self,
        kind: str,
        title: str,
        state: dict,
        *,
        geometry: dict | None = None,
        workspace: GMTableWorkspace | None = None,
    ) -> str:
        """Create a new floating panel in the requested workspace."""
        definition = PanelDefinition(
            panel_id=uuid4().hex,
            kind=kind,
            title=title,
            state=dict(state or {}),
        )
        target_workspace = workspace or self.workspace
        target_workspace.add_panel(definition, geometry=geometry)
        return definition.panel_id

    def _create_panel_in_workspace(
        self,
        kind: str,
        title: str,
        state: dict,
        *,
        geometry: dict | None = None,
        workspace: GMTableWorkspace | None = None,
    ) -> str:
        """Create a panel while preserving older call sites that monkeypatch _create_panel."""
        if workspace is None:
            if geometry is None:
                return self._create_panel(kind, title, state)
            return self._create_panel(kind, title, state, geometry=geometry)
        return self._create_panel(
            kind, title, state, geometry=geometry, workspace=workspace
        )

    def _create_panel_in_selection_workspace(
        self,
        kind: str,
        title: str,
        state: dict,
        *,
        geometry: dict | None = None,
        workspace: GMTableWorkspace | None = None,
    ) -> str:
        """Alias used by delayed picker callbacks to target the initiating workspace."""
        return self._create_panel_in_workspace(
            kind, title, state, geometry=geometry, workspace=workspace
        )

    def _add_image_panel_from_library_result(
        self, image_result, *, workspace: GMTableWorkspace | None = None
    ) -> None:
        """Create a floating image window from an image-library selection."""
        image_path = str(getattr(image_result, "path", "") or "").strip()
        if not image_path:
            messagebox.showerror("GM Table", "The selected image has no usable path.")
            return
        image_title = str(getattr(image_result, "name", "") or "").strip() or "Image"
        self._create_panel_in_workspace(
            "image",
            image_title,
            {"image_path": image_path, "image_title": image_title},
            workspace=workspace,
        )

    def _open_image_library_for_table_image(
        self, *, workspace: GMTableWorkspace | None = None
    ) -> None:
        """Open the shared image library dialog in attach-to-table mode."""
        try:
            from modules.ui.image_library.dialogs.library_browser_dialog import (
                ImageLibraryBrowserDialog,
            )
        except Exception as exc:
            messagebox.showerror(
                "Image Library", f"Image library is unavailable: {exc}"
            )
            return

        dialog = ImageLibraryBrowserDialog(
            self.winfo_toplevel(),
            on_attach_to_entity=lambda result: self._add_image_panel_from_library_result(
                result, workspace=workspace
            ),
        )
        dialog.title("Add Image to GM Table")

    def _preferred_entity_geometry(self, entity_type: str) -> dict[str, int]:
        """Return the default geometry for an entity panel."""
        width, height = resolve_default_panel_size(
            "entity", {"entity_type": entity_type}
        )
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

    def _entity_label(
        self, entity_type: str, item: dict | None, *, fallback: str = ""
    ) -> str:
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

    def _resolve_tabletop_context(
        self, *, prefer_world_map: bool = False
    ) -> tuple[str | None, str | None, object | None]:
        """Return the most relevant map-capable panel, kind, and payload."""
        preferred_kinds = {"world_map"} if prefer_world_map else MAP_PANEL_KINDS
        panel_id = self.workspace.get_active_panel_id(
            kinds=preferred_kinds, include_minimized=False
        )
        if panel_id is None and not prefer_world_map:
            panel_id = self.workspace.get_active_panel_id(
                kinds=MAP_PANEL_KINDS, include_minimized=False
            )
        if panel_id is None:
            records = self.workspace.list_panels(
                kinds={"world_map"} if prefer_world_map else MAP_PANEL_KINDS,
                include_minimized=True,
            )
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
        target_map = str(
            map_name
            or self._current_tabletop_map_name()
            or self._infer_starting_map_name()
            or ""
        ).strip()
        records = self.workspace.list_panels(
            kinds={"world_map"}, include_minimized=True
        )
        if records:
            panel_id = str(records[-1]["panel_id"])
            self.workspace.bring_to_front(panel_id)
            payload = records[-1]["payload"]
            if target_map and hasattr(payload, "load_map"):
                try:
                    payload.load_map(target_map, push_history=False)
                except Exception as exc:
                    log_exception(
                        f"Unable to load world map '{target_map}' in existing GM Table panel: {exc}",
                        func_name="GMTableView._focus_or_open_world_map_panel",
                    )
            return panel_id
        return self._create_panel(
            "world_map",
            "Scene Map",
            self._panel_state(map_name=target_map),
        )

    def _focus_or_open_map_tool_panel(self, map_name: str | None = None) -> str | None:
        """Focus an existing map tool panel or create one."""
        target_map = str(
            map_name
            or self._current_tabletop_map_name()
            or self._infer_starting_map_name()
            or ""
        ).strip()
        records = self.workspace.list_panels(kinds={"map_tool"}, include_minimized=True)
        if records:
            panel_id = str(records[-1]["panel_id"])
            self.workspace.bring_to_front(panel_id)
            payload = records[-1]["payload"]
            if target_map and hasattr(payload, "open_map_by_name"):
                try:
                    payload.open_map_by_name(target_map)
                except Exception as exc:
                    log_exception(
                        f"Unable to load map '{target_map}' in existing GM Table map tool panel: {exc}",
                        func_name="GMTableView._focus_or_open_map_tool_panel",
                    )
            return panel_id
        return self._create_panel(
            "map_tool",
            "Map Tool",
            self._panel_state(map_name=target_map),
        )

    def open_or_focus_world_map(self, map_name: str | None = None) -> str | None:
        """Public Scenario Board helper for opening or focusing the world map panel."""
        return self._focus_or_open_world_map_panel(map_name)

    def open_or_focus_map_panel(self, map_name: str | None = None) -> str | None:
        """Public Scenario Board helper for opening or focusing a scene map panel."""
        return self._focus_or_open_map_tool_panel(map_name)

    def open_or_focus_entity_panel(self, entity_type: str, name: str) -> None:
        """Public Scenario Board helper for deduplicated entity panels."""
        self.open_entity_panel(entity_type, name)

    def launch_scenario_bundle(self, bundle: ScenarioBundle) -> None:
        """Open the active scene's resolved bundle onto the GM Table."""
        if bundle.maps:
            self.open_or_focus_map_panel(bundle.maps[0])
        if bundle.world_maps:
            self.open_or_focus_world_map(bundle.world_maps[0])
        for entity_type, names in (
            ("NPCs", bundle.npcs),
            ("Villains", bundle.villains),
            ("Places", bundle.places),
        ):
            for name in names:
                self.open_or_focus_entity_panel(entity_type, name)

    def open_or_focus_scenario_board(
        self, scenario_name: str, *, workspace: GMTableWorkspace | None = None
    ) -> str:
        """Open one Scenario Board per scenario and focus it when already present."""
        target_workspace = workspace or self.workspace
        normalized = self._normalize_entity_name(scenario_name)
        for panel in target_workspace.serialize().get("panels", []):
            state = panel.get("state") or {}
            if (
                panel.get("kind") == "scenario_board"
                and self._normalize_entity_name(state.get("scenario_name"))
                == normalized
            ):
                panel_id = str(panel.get("panel_id"))
                target_workspace.bring_to_front(panel_id)
                width, height = resolve_default_panel_size("scenario_board")
                target_workspace.ensure_panel_minimum_size(panel_id, width, height)
                return panel_id

        title = str(scenario_name or "").strip() or "Untitled Scenario"
        width, height = resolve_default_panel_size("scenario_board")
        return self._create_panel_in_workspace(
            "scenario_board",
            f"Scenario Board: {title}",
            {"scenario_name": title},
            geometry={"width": width, "height": height},
            workspace=workspace,
        )

    def _open_player_view_for_active_panel(self) -> None:
        """Open the player display for the active scene map."""
        panel_id, kind, payload = self._resolve_tabletop_context(prefer_world_map=True)
        if kind != "world_map" or payload is None:
            target_map = self._current_tabletop_map_name()
            panel_id = self._focus_or_open_world_map_panel(target_map)
            if panel_id is None:
                messagebox.showinfo(
                    "GM Table", "Open a scene map before launching player view."
                )
                return
            payload = self.workspace.get_panel_payload(panel_id)
            kind = "world_map"
        if kind == "world_map" and hasattr(payload, "open_player_display"):
            payload.open_player_display()

    def _reveal_panel(
        self,
        panel_id: str,
        workspace: GMTableWorkspace | None = None,
    ) -> None:
        """Reveal the requested GM Table panel to the player-facing display."""
        target_workspace = workspace or self.workspace
        definition = target_workspace.get_panel_definition(panel_id)
        if definition is None:
            messagebox.showinfo("Reveal", "This panel is no longer available.")
            return

        payload = self._unwrap_hosted_payload(target_workspace.get_panel_payload(panel_id))
        kind = definition.kind
        state = definition.state if isinstance(definition.state, dict) else {}

        if kind == "image":
            path = str(state.get("image_path") or "").strip()
            title = str(state.get("image_title") or definition.title or "Image").strip()
            reveal_image(path, title=title)
            return

        if kind in MAP_PANEL_KINDS:
            reveal_map_payload(payload, title=definition.title)
            return

        if kind == "entity":
            entity_type = str(state.get("entity_type") or "").strip()
            entity_name = str(state.get("entity_name") or definition.title or "").strip()
            try:
                item = self._load_entity_item(entity_type, entity_name)
            except Exception as exc:
                messagebox.showwarning("Reveal", f"Unable to load entity for reveal:\n{exc}")
                return
            reveal_entity(entity_type, item, title=self._entity_label(entity_type, item, fallback=entity_name))
            return

        if hasattr(payload, "reveal") and callable(payload.reveal):
            payload.reveal()
            return

        messagebox.showinfo("Reveal", "This panel does not support player reveal.")

    @staticmethod
    def _unwrap_hosted_payload(payload: object) -> object:
        """Return the inner widget/controller for hosted GM Table pages."""
        inner = getattr(payload, "_payload", None)
        return inner if inner is not None else payload

    def _apply_fog_action(self, action: str) -> None:
        """Route fog controls to the active map-capable tabletop panel."""
        _panel_id, _kind, payload = self._resolve_tabletop_context()
        if payload is None:
            messagebox.showinfo("GM Table", "Open a map panel before using fog tools.")
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
        if hasattr(payload, "_set_fog"):
            payload._set_fog(action)
            return
        messagebox.showinfo(
            "GM Table", "The active map panel does not support fog tools."
        )

    def _handle_add_option(
        self, option: str, *, workspace: GMTableWorkspace | None = None
    ) -> None:
        """Route add-menu options to the main table or a nested container workspace."""
        if option == "Campaign Dashboard":
            self._create_panel_in_workspace(
                "campaign_dashboard", "Campaign Dashboard", {}, workspace=workspace
            )
            return
        if option == "World Map":
            self._create_panel_in_workspace(
                "world_map", "World Map", {}, workspace=workspace
            )
            return
        if option == "Map Tool":
            self._create_panel_in_workspace(
                "map_tool", "Map Tool", {}, workspace=workspace
            )
            return
        if option == "Scenario Board":
            (
                self._open_scenario_selection_for_panel("scenario_board")
                if workspace is None
                else self._open_scenario_selection_for_panel(
                    "scenario_board", workspace=workspace
                )
            )
            return
        if option == "Scene Flow":
            (
                self._open_scenario_selection_for_panel("scene_flow")
                if workspace is None
                else self._open_scenario_selection_for_panel(
                    "scene_flow", workspace=workspace
                )
            )
            return
        if option == "Image Library":
            self._create_panel_in_workspace(
                "image_library", "Image Library", {}, workspace=workspace
            )
            return
        if option == "Image from Library":
            (
                self._open_image_library_for_table_image()
                if workspace is None
                else self._open_image_library_for_table_image(workspace=workspace)
            )
            return
        if option == "Handouts":
            (
                self._open_scenario_selection_for_panel("handouts")
                if workspace is None
                else self._open_scenario_selection_for_panel(
                    "handouts", workspace=workspace
                )
            )
            return
        if option == "Container Window":
            self._create_panel_in_workspace(
                "container_window", "Container Window", {}, workspace=workspace
            )
            return
        if option == "Loot Generator":
            self._create_panel_in_workspace(
                "loot_generator", "Loot Generator", {}, workspace=workspace
            )
            return
        if option == "Object Shelf":
            self._create_panel_in_workspace(
                "object_shelf", "Object Shelf", {}, workspace=workspace
            )
            return
        if option == "Whiteboard":
            self._create_panel_in_workspace(
                "whiteboard", "Whiteboard", {}, workspace=workspace
            )
            return
        if option == "Random Tables":
            self._create_panel_in_workspace(
                "random_tables", "Random Tables", {}, workspace=workspace
            )
            return
        if option == "Plot Twists":
            self._create_panel_in_workspace(
                "plot_twists", "Plot Twists", {}, workspace=workspace
            )
            return
        if option == "Puzzle Display":
            (
                self._open_puzzle_selection()
                if workspace is None
                else self._open_puzzle_selection(workspace=workspace)
            )
            return
        if option == "Sticky Note":
            self._create_panel_in_workspace(
                "sticky_note",
                "Sticky Note",
                {"title": "", "body": "", "text": "", "color": "Yellow", "tags": [], "vote_marker": "", "pinned": False},
                workspace=workspace,
            )
            return
        if option == "Note Tab":
            existing_notes = [
                panel
                for panel in (workspace or self.workspace).serialize().get("panels", [])
                if panel.get("kind") == "note"
            ]
            self._create_panel_in_workspace(
                "note",
                f"Note {len(existing_notes) + 1}",
                {"text": ""},
                workspace=workspace,
            )
            return
        if option == "Character Graph":
            self._create_panel_in_workspace(
                "character_graph", "Character Graph", {}, workspace=workspace
            )
            return
        if option == "Scenario Graph Editor":
            self._create_panel_in_workspace(
                "scenario_graph", "Scenario Graph", {}, workspace=workspace
            )
            return
        if option in ENTITY_TYPES:
            (
                self._open_entity_selection(option)
                if workspace is None
                else self._open_entity_selection(option, workspace=workspace)
            )
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
                    builder=lambda host: self._build_world_map_content(
                        host, definition.state
                    ),
                    state_getter=lambda payload: self._panel_state(
                        map_name=getattr(payload, "current_map_name", None)
                    ),
                )
            if kind == "map_tool":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_map_tool_content(
                        host, definition.state
                    ),
                    state_getter=lambda payload: self._panel_state(
                        map_name=(
                            (getattr(payload, "current_map", None) or {}).get("Name")
                        )
                    ),
                )
            if kind == "scenario_board":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_scenario_board_content(
                        host, definition.state
                    ),
                    state_getter=lambda payload: payload.get_state(),
                )
            if kind == "scene_flow":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_scene_flow_content(
                        host, definition.state
                    ),
                    state_getter=lambda _payload: self._panel_state(
                        scenario_title=definition.state.get("scenario_title")
                    ),
                )
            if kind == "image_library":
                return GMTableImageLibraryPage(
                    parent,
                    initial_state=definition.state,
                    on_attach_to_table=self._add_image_panel_from_library_result,
                )
            if kind == "image":
                return GMTableImagePage(
                    parent,
                    image_path=str(definition.state.get("image_path") or ""),
                    title=str(definition.state.get("image_title") or definition.title),
                )
            if kind == "handouts":
                scenario_name = str(definition.state.get("scenario_name") or "").strip()
                scenario_item = (
                    self._load_scenario_item(scenario_name) if scenario_name else {}
                )
                return GMTableHandoutsPage(
                    parent,
                    scenario_name=scenario_name,
                    scenario_item=scenario_item,
                    wrappers=self.wrappers,
                    map_wrapper=self.map_wrapper,
                    initial_state=definition.state,
                )
            if kind == "container_window":
                return GMTableContainerPage(
                    parent,
                    initial_state=definition.state,
                    add_menu_options=getattr(self, "_add_menu_options", []),
                    on_add_panel=lambda option, target_workspace: self._handle_add_option(
                        option, workspace=target_workspace
                    ),
                    panel_builder=self._mount_panel_content,
                    on_layout_changed=self._persist_layout,
                    on_reveal_requested=self._reveal_panel,
                )
            if kind == "loot_generator":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_loot_generator_content(host),
                )
            if kind == "object_shelf":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: create_object_shelf_panel(
                        host, open_entity_callback=self.open_entity_panel
                    ),
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
                    builder=lambda host: self._build_random_tables_content(
                        host, definition.state
                    ),
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
                    builder=lambda host: self._build_entity_content(
                        host, definition.state
                    ),
                )
            if kind == "puzzle_display":
                return GMTableHostedPage(
                    parent,
                    builder=lambda host: self._build_puzzle_display_content(
                        host, definition.state
                    ),
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
            if kind == "sticky_note":
                return GMTableStickyNotePage(parent, initial_state=definition.state)
            if kind == "note":
                return GMTableNotePage(
                    parent,
                    initial_text=str(definition.state.get("text") or ""),
                    session_mid_variable=self._session_mid_var,
                    session_end_variable=self._session_end_var,
                    session_callbacks=SessionControlsCallbacks(
                        on_start=self._handle_note_session_action,
                        on_end=self._handle_note_session_action,
                        on_capture=self._handle_note_session_action,
                        on_debrief=self._handle_note_session_action,
                        on_settings=self._handle_note_session_settings,
                    ),
                    session_controls_enabled=False,
                    scenario_actions_enabled=False,
                )
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

    def _handle_note_session_action(self) -> None:
        """Explain why scenario session actions are disabled on global notes."""
        messagebox.showinfo(
            "Scenario Session",
            "GM Table note tabs are global table notes. Open a scenario GM screen to start "
            "a timed session, capture the active scene, or append a scenario debrief.",
        )

    def _handle_note_session_settings(self) -> None:
        """Explain where shared session settings are available for global notes."""
        messagebox.showinfo(
            "Scenario Session",
            "Session settings are scenario-specific. Open a scenario GM screen to adjust "
            "timer offsets and accessibility settings.",
        )

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
            except Exception as exc:
                log_exception(
                    f"Unable to restore world map '{map_name}' in GM Table panel: {exc}",
                    func_name="GMTableView._build_world_map_content",
                )
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
            except Exception as exc:
                log_exception(
                    f"Unable to restore map tool map '{map_name}' in GM Table panel: {exc}",
                    func_name="GMTableView._build_map_tool_content",
                )
        return controller

    def _build_scene_flow_content(self, host, state: dict):
        """Build the scene flow page."""
        widget = create_scene_flow_frame(
            host,
            scenario_title=state.get("scenario_title") or "",
        )
        widget.grid(row=0, column=0, sticky="nsew")
        return widget

    def _build_scenario_board_content(self, host, state: dict):
        """Build the scenario board page."""
        scenario_name = str(state.get("scenario_name") or "").strip()
        scenario_item = self._load_scenario_item(scenario_name) if scenario_name else {}
        widget = ScenarioBoardPanel(
            host,
            scenario_name=scenario_name,
            scenario_item=scenario_item,
            open_entity_callback=self.open_or_focus_entity_panel,
            launch_bundle_callback=self.launch_scenario_bundle,
            open_scene_map_callback=self.open_or_focus_map_panel,
            open_world_map_callback=self.open_or_focus_world_map,
            wrappers=self.wrappers,
            map_wrapper=self.map_wrapper,
            initial_state=state,
            on_state_changed=self._persist_layout,
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
        try:
            item = self._load_entity_item(entity_type, entity_name)
        except Exception:
            return self._build_unavailable_entity_content(
                host, entity_type=entity_type, entity_name=entity_name
            )
        attachments = collect_entity_attachments(item)

        if attachments:
            host.grid_rowconfigure(0, weight=1)
            host.grid_columnconfigure(0, weight=1)
            scrollable_host = build_scroll_host(host)
            attachment_gallery = GMTableAttachmentGallery(
                scrollable_host,
                attachments=attachments,
            )
            attachment_gallery.pack(fill="x", padx=8, pady=(8, 12))
            detail_frame = create_entity_detail_frame(
                entity_type,
                item,
                master=scrollable_host,
                open_entity_callback=self.open_entity_panel,
                spotlight_only=False,
                show_spotlight=False,
            )
            detail_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
            return scrollable_host

        if self._uses_readable_entity_detail(entity_type):
            scrollable_host = build_scroll_host(host)
            frame = create_entity_detail_frame(
                entity_type,
                item,
                master=scrollable_host,
                open_entity_callback=self.open_entity_panel,
                spotlight_only=False,
            )
            frame.pack(fill="both", expand=True)
            return frame

        frame = create_entity_detail_frame(
            entity_type,
            item,
            master=host,
            open_entity_callback=self.open_entity_panel,
            spotlight_only=True,
        )
        frame.grid(row=0, column=0, sticky="nsew")
        return frame

    def _build_unavailable_entity_content(
        self, host, *, entity_type: str | None, entity_name: str | None
    ):
        """Build a clear fallback for saved entity panels whose record is gone."""
        host.grid_rowconfigure(0, weight=1)
        host.grid_columnconfigure(0, weight=1)
        label = str(entity_name or "Unnamed").strip() or "Unnamed"
        type_label = str(entity_type or "entity").strip() or "entity"
        frame = ctk.CTkFrame(host, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            frame,
            text="Entity unavailable",
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            frame,
            text=(
                f"The saved panel points to {type_label} '{label}', "
                "but that record could not be found. The panel was kept so you "
                "can decide whether to close it or recreate the entity."
            ),
            text_color=TABLE_PALETTE["muted"],
            justify="left",
            wraplength=460,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(10, 0))
        return frame

    @staticmethod
    def _uses_readable_entity_detail(entity_type: str | None) -> bool:
        """Return whether GM Table panels should show full text details."""
        return entity_type == "Objects"

    def _build_puzzle_display_content(self, host, state: dict):
        """Build the puzzle display page."""
        puzzle_name = state.get("puzzle_name")
        wrapper = self.wrappers.get("Puzzles")
        items = wrapper.load_items() if wrapper is not None else []
        puzzle_item = next(
            (item for item in items if item.get("Name") == puzzle_name), {}
        )
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
        workspace: GMTableWorkspace | None = None,
    ) -> str | None:
        """Return the existing entity panel id when present in a workspace."""
        target_workspace = workspace or self.workspace
        layout = target_workspace.serialize()
        lookup_names = self._entity_aliases(
            entity_type, item=item, fallback=entity_name
        )
        for panel in layout.get("panels", []):
            state = panel.get("state") or {}
            if (
                panel.get("kind") == "entity"
                and state.get("entity_type") == entity_type
                and self._normalize_entity_name(state.get("entity_name"))
                in lookup_names
            ):
                return str(panel.get("panel_id"))
        return None

    def open_entity_panel(
        self,
        entity_type: str,
        name: str,
        *,
        workspace: GMTableWorkspace | None = None,
        attachment_only: bool = False,
    ) -> None:
        """Open a specific entity inside the GM Table or a nested container."""
        target_workspace = workspace or self.workspace
        try:
            item = self._load_entity_item(entity_type, name)
        except Exception as exc:
            messagebox.showerror("GM Table", str(exc))
            return

        label = self._entity_label(entity_type, item, fallback=name)
        has_attachments = entity_type != "Scenarios" and entity_has_attachments(item)
        existing = self._find_existing_entity_panel(
            entity_type, label, item=item, workspace=target_workspace
        )
        if existing is not None:
            target_workspace.bring_to_front(existing)
            preferred = self._preferred_entity_geometry(entity_type)
            target_workspace.ensure_panel_minimum_size(
                existing,
                preferred["width"],
                preferred["height"],
            )
            return

        singular = entity_type[:-1] if entity_type.endswith("s") else entity_type
        state = {
            "entity_type": entity_type,
            "entity_name": label,
        }
        if has_attachments and attachment_only:
            state["attachment_only"] = True
        self._create_panel_in_workspace(
            "entity",
            f"{singular}: {label}",
            state,
            geometry=self._preferred_entity_geometry(entity_type),
            workspace=workspace,
        )

    def _load_scenario_item(self, scenario_name: str) -> dict:
        """Resolve a scenario by title/name for scenario-specific panels."""
        if not scenario_name:
            return {}
        try:
            item = self._load_entity_item("Scenarios", scenario_name)
        except Exception:
            return {}
        return item if isinstance(item, dict) else {}

    def _open_scenario_selection_for_panel(
        self, panel_kind: str, *, workspace: GMTableWorkspace | None = None
    ) -> None:
        """Ask which scenario should power a scenario-specific panel."""
        wrapper = self.wrappers.get("Scenarios")
        template = self._templates.get("Scenarios")
        if wrapper is None or template is None:
            messagebox.showerror("GM Table", "Scenarios are not available.")
            return

        popup = ctk.CTkToplevel(self)
        popup.title("Select Scenario")
        popup.geometry("1200x800")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.focus_force()

        def _open_selected(
            selected_type: str, selected_name: str, item: dict | None = None
        ) -> None:
            del selected_type
            popup.destroy()
            scenario_title = self._entity_label(
                "Scenarios", item, fallback=selected_name
            )
            if panel_kind == "scene_flow":
                self._create_panel_in_selection_workspace(
                    "scene_flow",
                    f"Scene Flow: {scenario_title}",
                    {"scenario_title": scenario_title},
                    workspace=workspace,
                )
                return
            if panel_kind == "scenario_board":
                self.open_or_focus_scenario_board(scenario_title, workspace=workspace)
                return
            if panel_kind == "handouts":
                self._create_panel_in_selection_workspace(
                    "handouts",
                    f"Handouts: {scenario_title}",
                    {"scenario_name": scenario_title},
                    workspace=workspace,
                )

        view = GenericListSelectionView(
            popup, "Scenarios", wrapper, template, _open_selected
        )
        view.pack(fill="both", expand=True)

    def _open_entity_selection(
        self, entity_type: str, *, workspace: GMTableWorkspace | None = None
    ) -> None:
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

        def _open_selected(
            selected_type: str, selected_name: str, item: dict | None = None
        ) -> None:
            popup.destroy()
            self.open_entity_panel(
                selected_type,
                self._entity_label(selected_type, item, fallback=selected_name),
                workspace=workspace,
            )

        view = GenericListSelectionView(
            popup, entity_type, wrapper, template, _open_selected
        )
        view.pack(fill="both", expand=True)

    def _open_puzzle_selection(
        self, *, workspace: GMTableWorkspace | None = None
    ) -> None:
        """Open the puzzle selector for a display panel."""
        popup = ctk.CTkToplevel(self)
        popup.title("Select Puzzle")
        popup.geometry("1200x800")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.focus_force()

        def _open_selected(_entity_type: str, selected_name: str) -> None:
            popup.destroy()
            self._create_panel_in_selection_workspace(
                "puzzle_display",
                f"Puzzle Display: {selected_name}",
                {"puzzle_name": selected_name},
                workspace=workspace,
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
            messagebox.showerror(
                "GM Table", "Chatbot is unavailable from this workspace."
            )

    def focus_panel(self, panel_id: str) -> None:
        """Bring a panel to the front."""
        self.workspace.bring_to_front(panel_id)

    def log_workspace_opened(self) -> None:
        """Write a trace entry once the view is live."""
        log_info(
            f"Opened GM Table {self.table_id} ({self.table_name})",
            func_name="GMTableView.log_workspace_opened",
        )

    def destroy(self) -> None:
        """Persist and tear down embedded panels cleanly."""
        try:
            if self._workspace_loaded:
                self._save_layout_snapshot()
        except Exception as exc:
            log_exception(
                f"Unable to save GM Table layout during teardown: {exc}",
                func_name="GMTableView.destroy",
            )
        try:
            self._layout_settle_scheduler.cancel_all()
        except Exception as exc:
            log_warning(
                f"Unable to cancel GM Table layout settle jobs during teardown: {exc}",
                func_name="GMTableView.destroy",
            )
        try:
            self.workspace.dispose()
        except Exception as exc:
            log_warning(
                f"Unable to dispose GM Table workspace during teardown: {exc}",
                func_name="GMTableView.destroy",
            )
        super().destroy()
