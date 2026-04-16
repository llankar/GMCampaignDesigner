"""View for scenario GM screen."""

import customtkinter as ctk
import tkinter as tk
import os
import json
from datetime import datetime
from tkinter import filedialog, messagebox
from PIL import Image
from functools import partial
from typing import Optional
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.template_loader import load_template as load_entity_template
from modules.helpers.text_helpers import format_multiline_text
from customtkinter import CTkLabel, CTkImage
from modules.generic.entity_detail_factory import create_entity_detail_frame
from modules.characters.character_graph_editor import CharacterGraphEditor
from modules.scenarios.scenario_graph_editor import ScenarioGraphEditor
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.layout_scheduler import LayoutSettleScheduler
import random
from collections import deque
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_methods,
    log_warning,
    log_module_import,
)
from modules.scenarios.gm_layout_manager import GMScreenLayoutManager
from modules.maps.world_map_view import WorldMapPanel
from modules.maps.controllers.display_map_controller import DisplayMapController
from modules.scenarios.scene_flow_viewer import create_scene_flow_frame, scene_flow_content_factory
from modules.scenarios.plot_twist_scheduler import PlotTwistScheduler
from modules.scenarios.plot_twist_panel import PlotTwistPanel, roll_plot_twist
from modules.scenarios.gm_table.handouts.page import GMTableHandoutsPage
from modules.scenarios.session_notes import (
    build_scene_snapshot_entry,
    build_session_debrief_entry,
)
from modules.ui.chatbot_dialog import (
    open_chatbot_dialog,
    _DEFAULT_NAME_FIELD_OVERRIDES as CHATBOT_NAME_OVERRIDES,
)
from modules.objects.loot_generator_panel import LootGeneratorPanel
from modules.scenarios.random_tables_panel import RandomTablesPanel
from modules.whiteboard.controllers.whiteboard_controller import WhiteboardController
from modules.puzzles.puzzle_display_window import create_puzzle_display_frame
from modules.scenarios.gm_screen import CampaignDashboardPanel
from modules.scenarios.gm_screen.tab_variants import (
    TAB_VARIANTS,
    tab_category_for_name,
    tab_icon_for_name,
    tab_short_label,
)
from modules.scenarios.gm_screen.dashboard.animations import MotionController
from modules.generic.detail_ui import get_detail_palette
from modules.generic.detail_ui.scroll_host import build_scroll_host

log_module_import(__name__)

PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
MAX_PORTRAIT_SIZE = (64, 64)  # Thumbnail size for lists
DEFAULT_MAP_THUMBNAIL_SIZE = (200, 140)

@log_methods
class GMScreenView(ctk.CTkFrame):
    def __init__(self, master, scenario_item, *args, initial_layout=None, layout_manager=None, **kwargs):
        """Initialize the GMScreenView instance."""
        super().__init__(master, *args, **kwargs)
        # Persistent cache for portrait images
        self.portrait_images = {}
        self._palette = get_detail_palette()
        self.scenario = scenario_item
        self.scenario_name = scenario_item.get("Title") or scenario_item.get("Name") or "Scenario"
        self.layout_manager = layout_manager or GMScreenLayoutManager()
        self._pending_initial_layout = initial_layout
        self._scene_completion_state = {}
        self._scene_vars = {}
        self._scene_order = []
        self._active_scene_key = None
        self._rich_host = None
        self._note_cache = ""
        self.note_widget = None
        self._note_editor_window = None
        self._context_menu = None
        self._edit_menu_label = "Edit Entity"
        self._state_loaded = False
        self._scene_metadata = {}
        self._session_active = False
        self._session_start = None
        self._plot_twist_scheduler = PlotTwistScheduler(self)
        self._session_mid_var = tk.StringVar()
        self._session_end_var = tk.StringVar()
        self._reduced_motion_var = tk.BooleanVar(value=False)

        self._load_persisted_state()
        self._load_motion_settings()
        self._motion = MotionController(self.after, reduced_motion=self._reduced_motion_var.get())

        # Track transient key bindings when this view owns its toplevel window
        self._bound_shortcut_owner = None
        self._ctrl_f_binding = None
        self._ctrl_F_binding = None
        self._ctrl_shift_c_binding = None
        self._ctrl_shift_C_binding = None
        self._ctrl_shift_c_release_binding = None
        self._ctrl_shift_C_release_binding = None
        self._layout_settle_scheduler = LayoutSettleScheduler(self)
        self._layout_probe_signature = None
        self._bound_layout_hosts = set()
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._setup_toplevel_shortcuts()

        # Load your detach and reattach icon files (adjust file paths and sizes as needed)
        self.detach_icon = CTkImage(light_image=Image.open("assets/detach_icon.png"),
                                    dark_image=Image.open("assets/detach_icon.png"),
                                    size=(20, 20))
        self.reattach_icon = CTkImage(light_image=Image.open("assets/reattach_icon.png"),
                                    dark_image=Image.open("assets/reattach_icon.png"),
                                    size=(20, 20))

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
            "Books": GenericModelWrapper("books"),
        }

        # Dedicated map store for thumbnails and quick lookup
        self.map_wrapper = GenericModelWrapper("maps")
        self._map_records = self._load_map_records()
        self._map_thumbnail_cache = {}
        self._map_thumbnail_size = DEFAULT_MAP_THUMBNAIL_SIZE

        self.templates = {
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
        }

        self.tabs = {}
        self.current_tab = None
        self.tab_order = []                  # ← new: keeps track of left-to-right order
        self.dragging = None                 # ← new: holds (tab_name, start_x)
        self.current_layout_name = None
        self._default_pinned_tab_names = {self.scenario_name.lower(), "world map", "session timer"}
        self._command_deck_buttons = {}

        # A container to hold both the scrollable tab area and the plus button
        self.tab_bar_container = ctk.CTkFrame(self, height=60, fg_color=self._palette["surface_card"], border_width=1, border_color=self._palette["muted_border"], corner_radius=18)
        self.tab_bar_container.pack(side="top", fill="x")

        self.command_deck = ctk.CTkFrame(self.tab_bar_container, fg_color="transparent")
        self.command_deck.pack(side="top", anchor="e", padx=8, pady=(4, 0))
        self.command_deck_label = ctk.CTkLabel(
            self.command_deck,
            text="Command Deck",
            text_color=self._palette["muted_text"],
        )
        self.command_deck_label.pack(side="left", padx=(0, 6))

        # The scrollable canvas for tabs
        self.tab_bar_canvas = ctk.CTkCanvas(self.tab_bar_container, height=44, highlightthickness=0, bg=self._palette["surface_card"])
        self.tab_bar_canvas.pack(side="top", fill="x", expand=True)

        # Horizontal scrollbar at the bottom alongside layout status
        self.tab_bar_bottom = ctk.CTkFrame(self.tab_bar_container, fg_color="transparent")
        self.tab_bar_bottom.pack(side="bottom", fill="x")

        self.h_scrollbar = ctk.CTkScrollbar(
            self.tab_bar_bottom,
            orientation="horizontal",
            command=self.tab_bar_canvas.xview
        )
        self.h_scrollbar.pack(side="left", fill="x", expand=True)

        # The actual frame that holds the tab buttons
        self.tab_bar = ctk.CTkFrame(self.tab_bar_canvas, height=44, fg_color="transparent")
        self.tab_bar_id = self.tab_bar_canvas.create_window((0, 0), window=self.tab_bar, anchor="nw")

        # Connect the scrollbar to the canvas
        self.tab_bar_canvas.configure(xscrollcommand=self.h_scrollbar.set)

        # Update the scroll region when the tab bar resizes
        self.tab_bar.bind("<Configure>", lambda e: self.tab_bar_canvas.configure(
            scrollregion=self.tab_bar_canvas.bbox("all")))

        # The plus button stays on the right side of the container and hosts the add menu
        self.add_button = ctk.CTkButton(
            self.tab_bar,
            text="+",
            width=42,
            fg_color=self._palette["surface_overlay"],
            hover_color=self._palette["accent_hover"],
            text_color=self._palette["text"],
            corner_radius=14,
            command=self.add_new_tab
        )
        
        self.random_button = ctk.CTkButton(
            self.tab_bar,
            text="?",
            width=42,
            fg_color=self._palette["surface_overlay"],
            hover_color=self._palette["accent_hover"],
            text_color=self._palette["text"],
            corner_radius=14,
            command=self._add_random_entity
        )
        self.random_button.pack(side="left", padx=2, pady=5)
        self.add_button.pack(side="left", padx=2, pady=5)

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
            "Puzzle Display",
            "Note Tab",
            "Character Graph",
            "Scenario Graph Editor",
            "separator",
            ("Save Layout", self._prompt_save_layout),
            ("Load Layout", self._open_load_layout_dialog),
            ("Open Chatbot", self.open_chatbot),
        ]
        self._add_menu = self._build_add_menu()
        self._session_controls = ctk.CTkFrame(self.tab_bar_bottom)
        self._session_controls.pack(side="right", padx=8, pady=4)
        self._build_session_controls()
        self.layout_status_label = ctk.CTkLabel(self.tab_bar_bottom, text="", text_color=self._palette["muted_text"])
        self.layout_status_label.pack(side="right", padx=8, pady=5)

        # Main content area for scenario details
        self.content_area = ctk.CTkFrame(self)
        self.content_area.pack(fill="both", expand=True)
        self.content_area._scrollable_frame = self.content_area
        self._bind_layout_host(self.content_area)
        self._initialize_context_menu()

        # Example usage: create the first tab from the scenario_item
        self.after_idle(self._create_initial_scenario_tab)

        # Apply either the caller-specified layout or the scenario default
        self.after(100, self._apply_initial_layout)

    # -- Runtime sizing helpers -------------------------------------------------
    def _bind_layout_host(self, host) -> None:
        """Bind layout host."""
        if host is None:
            return
        host_key = str(host)
        if host_key in self._bound_layout_hosts:
            return
        self._bound_layout_hosts.add(host_key)
        try:
            self._layout_settle_scheduler.bind_configure(
                host,
                "active-tab-layout",
                self._settle_active_tab_layout,
                when=self._active_tab_layout_ready,
            )
        except Exception:
            pass

    def _ensure_rich_host(self):
        """Ensure rich host."""
        host = self._rich_host
        if host is None or not host.winfo_exists():
            host = ctk.CTkFrame(self)
            self._rich_host = host
            self._bind_layout_host(host)
        return host

    def _get_active_attached_frame(self):
        """Return active attached frame."""
        if not self.current_tab:
            return None
        tab = self.tabs.get(self.current_tab)
        if not tab or tab.get("detached"):
            return None
        return tab.get("content_frame")

    def _active_tab_layout_ready(self) -> bool:
        """Internal helper for active tab layout ready."""
        frame = self._get_active_attached_frame()
        if frame is None or not frame.winfo_exists():
            return False
        try:
            # Keep active tab layout ready resilient if this step fails.
            if not frame.winfo_manager() or not frame.winfo_ismapped():
                return False
        except Exception:
            return False
        try:
            # Keep active tab layout ready resilient if this step fails.
            rich_host = getattr(self, "_rich_host", None)
            if rich_host is not None and rich_host.winfo_exists() and frame.master == rich_host:
                viewport = rich_host
            else:
                viewport = self.content_area if hasattr(self, "content_area") else self
            viewport.update_idletasks()
            width = int(viewport.winfo_width())
            height = int(viewport.winfo_height())
        except Exception:
            return False
        if width <= 1 or height <= 1:
            return False
        probe_signature = (str(frame), str(viewport), width, height)
        if self._layout_probe_signature != probe_signature:
            self._layout_probe_signature = probe_signature
            return False
        return True

    def _request_active_tab_layout_settle(self) -> None:
        """Internal helper for request active tab layout settle."""
        self._layout_probe_signature = None
        self._layout_settle_scheduler.schedule(
            "active-tab-layout",
            self._settle_active_tab_layout,
            when=self._active_tab_layout_ready,
        )

    def _settle_active_tab_layout(self) -> None:
        """Internal helper for settle active tab layout."""
        frame = self._get_active_attached_frame()
        if frame is None:
            return

        tab_meta = {}
        if self.current_tab in self.tabs:
            tab_meta = self.tabs[self.current_tab].get("meta") or {}

        if self._should_sync_fullbleed(frame, tab_meta):
            self._sync_fullbleed_now(frame)
            return

        self._refresh_scrollregion(frame)

    def _should_sync_fullbleed(self, frame, tab_meta: dict | None = None) -> bool:
        """Return whether sync fullbleed."""
        meta = tab_meta or {}
        if meta.get("host") == "rich":
            return True
        rich_kinds = {"world_map", "map_tool", "whiteboard", "character_graph", "scenario_graph", "scene_flow"}
        if meta.get("kind") in rich_kinds:
            return True
        if getattr(frame, "_scroll_canvas", None) is None and getattr(frame, "_parent_canvas", None) is None:
            return True
        return False

    def _refresh_scrollregion(self, container) -> None:
        """Refresh scrollregion."""
        canvases = []
        scroll_canvas = getattr(container, "_scroll_canvas", None)
        parent_canvas = getattr(container, "_parent_canvas", None)
        if scroll_canvas is not None:
            canvases.append(scroll_canvas)
        if parent_canvas is not None and parent_canvas not in canvases:
            canvases.append(parent_canvas)

        for canvas in canvases:
            try:
                # Keep scrollregion resilient if this step fails.
                bbox = canvas.bbox("all")
                if bbox:
                    canvas.configure(scrollregion=bbox)
            except Exception:
                continue

    def _sync_fullbleed_now(self, container: ctk.CTkFrame | None):
        """Synchronize fullbleed now."""
        if not container or not container.winfo_exists():
            return
        try:
            # Keep fullbleed now resilient if this step fails.
            rich_host = getattr(self, "_rich_host", None)
            if rich_host is not None and rich_host.winfo_exists() and container.master == rich_host:
                viewport = rich_host
            else:
                viewport = self.content_area if hasattr(self, "content_area") else self
            viewport.update_idletasks()
            w = int(viewport.winfo_width())
            h = int(viewport.winfo_height())
            if w <= 1 or h <= 1:
                return
            container.pack_propagate(False)
            container.configure(width=w, height=h)
        except Exception:
            pass

    def _build_hidden_tab_content(self, host_parent, content_factory, *, scrollable=False):
        """Build hidden tab content."""
        container = ctk.CTkFrame(host_parent, fg_color="transparent")
        scroll_host = build_scroll_host(container) if scrollable else None
        build_parent = scroll_host if scroll_host is not None else container
        built = content_factory(build_parent)
        if built is not None and built is not container:
            try:
                # Keep hidden tab content resilient if this step fails.
                if not built.winfo_manager():
                    built.pack(fill="both", expand=True)
            except Exception:
                pass

        def _proxy_attr(attr_name):
            """Internal helper for proxy attr."""
            if built is None or not hasattr(built, attr_name):
                return
            try:
                setattr(container, attr_name, getattr(built, attr_name))
            except Exception:
                pass

        for attr in (
            "edit_entity",
            "portrait_label",
            "portrait_images",
            "text_box",
            "get_state",
            "refresh",
            "reload",
            "_scrollable_frame",
            "_parent_canvas",
            "_scroll_canvas",
            "_scrollbar",
        ):
            _proxy_attr(attr)

        scroll_ref_source = scroll_host if scroll_host is not None else built
        if scroll_ref_source is not None:
            for attr in ("_scrollable_frame", "_parent_canvas", "_scroll_canvas", "_scrollbar"):
                try:
                    setattr(container, attr, getattr(scroll_ref_source, attr, None))
                except Exception:
                    pass

        if built is not None:
            container.content_inner = built
        return container

    def _create_initial_scenario_tab(self):
        """Create initial scenario tab."""
        scenario_name = self.scenario.get("Title", "Unnamed Scenario")
        factory = lambda master: create_entity_detail_frame(
            "Scenarios",
            self.scenario,
            master=master,
            open_entity_callback=self.open_entity_tab,
        )
        frame = self._build_hidden_tab_content(self.content_area, factory)

        # Make sure the frame can get focus so the binding works
        self.focus_set()
        self.add_tab(
            scenario_name,
            frame,
            content_factory=lambda master: self._build_hidden_tab_content(master, factory),
            layout_meta={
                "kind": "entity",
                "entity_type": "Scenarios",
                "entity_name": scenario_name,
            },
            activate=True,
        )

    def _build_add_menu(self):
        """Build add menu."""
        menu = tk.Menu(self, tearoff=0)
        for option in self._add_menu_options:
            # Process each option from _add_menu_options.
            if option == "separator":
                menu.add_separator()
                continue
            if isinstance(option, tuple):
                label, command = option
                menu.add_command(label=label, command=command)
                continue
            menu.add_command(label=option, command=lambda o=option: self.open_selection_window(o))
        return menu


    def _load_map_records(self):
        """Load map records."""
        try:
            items = self.map_wrapper.load_items() if self.map_wrapper else []
        except Exception as exc:
            log_warning(
                f"Unable to load maps: {exc}",
                func_name="GMScreenView._load_map_records",
            )
            return {}

        records = {}
        for item in items or []:
            # Process each item from items or [].
            name = str(item.get("Name") or "").strip()
            if not name:
                continue
            records[name] = item
        return records

    def _get_map_record(self, map_name):
        """Return map record."""
        if not map_name:
            return None
        if map_name not in self._map_records:
            self._map_records = self._load_map_records()
        return self._map_records.get(map_name)

    def get_map_thumbnail(self, map_name, size=None):
        """Return map thumbnail."""
        name = (map_name or "").strip()
        if not name:
            return None

        if size is None:
            size = self._map_thumbnail_size
        size_tuple = tuple(size)
        cache_key = (name, size_tuple)
        cached = self._map_thumbnail_cache.get(cache_key)
        if cached is not None:
            return cached

        record = self._get_map_record(name)
        if not record:
            return None

        image_path = record.get("Image") or record.get("image")
        if not image_path:
            return None

        if not os.path.isabs(image_path):
            image_path = os.path.join(ConfigHelper.get_campaign_dir(), image_path)

        if not os.path.exists(image_path):
            log_warning(
                f"Map image for '{name}' not found at {image_path}",
                func_name="GMScreenView.get_map_thumbnail",
            )
            return None

        try:
            # Keep map thumbnail resilient if this step fails.
            with Image.open(image_path) as img:
                img = img.convert("RGBA")
                target_w, target_h = size_tuple
                ratio = min(target_w / img.width, target_h / img.height, 1.0)
                new_size = (
                    max(1, int(img.width * ratio)),
                    max(1, int(img.height * ratio)),
                )
                resized = img.resize(new_size, Image.Resampling.LANCZOS)
        except Exception as exc:
            log_warning(
                f"Failed to load thumbnail for map '{name}': {exc}",
                func_name="GMScreenView.get_map_thumbnail",
            )
            return None

        thumbnail = CTkImage(light_image=resized, dark_image=resized, size=new_size)
        self._map_thumbnail_cache[cache_key] = thumbnail
        return thumbnail

    def open_map_tool(self, map_name):
        """Open map tool."""
        target = (map_name or "").strip()
        if not target:
            return

        candidates = []
        try:
            host = self.winfo_toplevel()
        except Exception:
            host = None

        if host is not None:
            candidates.append(host)

        current = getattr(host, "master", None)
        while current is not None and current not in candidates:
            # Keep looping while current is available and current is not in candidates.
            candidates.append(current)
            current = getattr(current, "master", None)

        try:
            root = self._root()
        except Exception:
            root = None

        if root is not None and root not in candidates:
            candidates.append(root)

        for owner in candidates:
            if hasattr(owner, "map_tool"):
                try:
                    owner.map_tool(target)
                    return
                except Exception as exc:
                    log_warning(
                        f"Failed to open map tool for '{target}': {exc}",
                        func_name="GMScreenView.open_map_tool",
                    )
                    return

        log_warning(
            "No widget in hierarchy exposes a map_tool method.",
            func_name="GMScreenView.open_map_tool",
        )

    def _load_persisted_state(self):
        """Load persisted state."""
        manager = getattr(self, "layout_manager", None)
        if manager is None:
            self._state_loaded = True
            return
        state = manager.get_scenario_state(self.scenario_name) or {}
        scenes = state.get("scenes") or {}
        if isinstance(scenes, dict):
            for key, value in scenes.items():
                self._scene_completion_state[key] = bool(value)
        notes = state.get("notes")
        if isinstance(notes, str):
            self._note_cache = notes
        self._state_loaded = True

    def _setup_toplevel_shortcuts(self):
        """Bind Ctrl+F locally when the view is hosted in its own window."""
        master = getattr(self, "master", None)
        if master is None:
            return
        try:
            top = master.winfo_toplevel()
        except Exception:
            return
        if top is None or master is not top:
            return
        try:
            # Keep setup toplevel shortcuts resilient if this step fails.
            self._bound_shortcut_owner = top
            self._ctrl_f_binding = top.bind("<Control-f>", self.open_global_search, add="+")
            self._ctrl_F_binding = top.bind("<Control-F>", self.open_global_search, add="+")
            self._ctrl_shift_c_binding = top.bind("<Control-Shift-c>", self.open_chatbot, add="+")
            self._ctrl_shift_C_binding = top.bind("<Control-Shift-C>", self.open_chatbot, add="+")
            self._ctrl_shift_c_release_binding = top.bind(
                "<Control-Shift-KeyRelease-c>", self.open_chatbot, add="+"
            )
            self._ctrl_shift_C_release_binding = top.bind(
                "<Control-Shift-KeyRelease-C>", self.open_chatbot, add="+"
            )
        except Exception:
            self._bound_shortcut_owner = None
            self._ctrl_f_binding = None
            self._ctrl_F_binding = None
            self._ctrl_shift_c_binding = None
            self._ctrl_shift_C_binding = None
            self._ctrl_shift_c_release_binding = None
            self._ctrl_shift_C_release_binding = None

    def _teardown_toplevel_shortcuts(self):
        """Tear down toplevel shortcuts."""
        top = self._bound_shortcut_owner
        if not top:
            return
        try:
            # Keep toplevel shortcuts resilient if this step fails.
            if self._ctrl_f_binding:
                top.unbind("<Control-f>", self._ctrl_f_binding)
            if self._ctrl_F_binding:
                top.unbind("<Control-F>", self._ctrl_F_binding)
            if self._ctrl_shift_c_binding:
                top.unbind("<Control-Shift-c>", self._ctrl_shift_c_binding)
            if self._ctrl_shift_C_binding:
                top.unbind("<Control-Shift-C>", self._ctrl_shift_C_binding)
            if self._ctrl_shift_c_release_binding:
                top.unbind("<Control-Shift-KeyRelease-c>", self._ctrl_shift_c_release_binding)
            if self._ctrl_shift_C_release_binding:
                top.unbind("<Control-Shift-KeyRelease-C>", self._ctrl_shift_C_release_binding)
        except Exception:
            pass
        finally:
            self._bound_shortcut_owner = None
            self._ctrl_shift_c_binding = None
            self._ctrl_shift_C_binding = None
            self._ctrl_f_binding = None
            self._ctrl_F_binding = None
            self._ctrl_shift_c_release_binding = None
            self._ctrl_shift_C_release_binding = None

    def _on_destroy(self, event=None):
        """Handle destroy."""
        if event is not None and event.widget is not self:
            return
        self._end_session(silent=True)
        self._teardown_toplevel_shortcuts()

    def _build_session_controls(self):
        """Build session controls."""
        self._load_session_hours()
        ctk.CTkLabel(self._session_controls, text="Session:").pack(side="left", padx=(6, 4))

        mid_label = ctk.CTkLabel(self._session_controls, text="Mid (hrs)")
        mid_label.pack(side="left", padx=(0, 4))
        mid_entry = ctk.CTkEntry(self._session_controls, width=60, textvariable=self._session_mid_var)
        mid_entry.pack(side="left", padx=(0, 8))

        end_label = ctk.CTkLabel(self._session_controls, text="End (hrs)")
        end_label.pack(side="left", padx=(0, 4))
        end_entry = ctk.CTkEntry(self._session_controls, width=60, textvariable=self._session_end_var)
        end_entry.pack(side="left", padx=(0, 8))

        start_btn = ctk.CTkButton(self._session_controls, text="Start", width=70, command=self._start_session)
        start_btn.pack(side="left", padx=(0, 4))
        end_btn = ctk.CTkButton(self._session_controls, text="End", width=70, command=self._end_session)
        end_btn.pack(side="left", padx=(0, 4))
        capture_btn = ctk.CTkButton(
            self._session_controls,
            text="Capture",
            width=84,
            command=self._capture_scene_snapshot,
        )
        capture_btn.pack(side="left", padx=(0, 4))
        debrief_btn = ctk.CTkButton(
            self._session_controls,
            text="Debrief",
            width=84,
            command=self._append_session_debrief,
        )
        debrief_btn.pack(side="left")
        settings_btn = ctk.CTkButton(
            self._session_controls,
            text="Settings",
            width=84,
            command=self._open_settings_dialog,
        )
        settings_btn.pack(side="left", padx=(4, 0))

        mid_entry.bind("<FocusOut>", self._persist_session_hours, add="+")
        end_entry.bind("<FocusOut>", self._persist_session_hours, add="+")
        mid_entry.bind("<Return>", self._persist_session_hours, add="+")
        end_entry.bind("<Return>", self._persist_session_hours, add="+")

        self._session_mid_entry = mid_entry
        self._session_end_entry = end_entry
        self._session_start_button = start_btn
        self._session_end_button = end_btn
        self._session_capture_button = capture_btn
        self._session_debrief_button = debrief_btn
        self._session_settings_button = settings_btn
        self._update_session_controls_state()

    def _load_motion_settings(self):
        """Load reduced motion setting from persisted global preferences."""
        manager = getattr(self, "layout_manager", None)
        reduced_motion = False
        if manager is not None:
            reduced_motion = bool(manager.get_global_setting("reduced_motion", False))
        self._reduced_motion_var.set(reduced_motion)

    def _persist_motion_settings(self):
        """Persist reduced motion setting."""
        manager = getattr(self, "layout_manager", None)
        if manager is None:
            return
        manager.set_global_setting("reduced_motion", bool(self._reduced_motion_var.get()))

    def _on_reduced_motion_toggled(self):
        """Handle reduced motion toggle."""
        enabled = bool(self._reduced_motion_var.get())
        self._motion.set_reduced_motion(enabled)
        self._persist_motion_settings()

    def _open_settings_dialog(self):
        """Open compact settings dialog for global accessibility options."""
        popup = ctk.CTkToplevel(self)
        popup.title("GM Screen Settings")
        popup.geometry("360x160")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.focus_force()

        body = ctk.CTkFrame(popup, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(
            body,
            text="Accessibility",
            anchor="w",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(fill="x", pady=(0, 8))
        ctk.CTkSwitch(
            body,
            text="Reduced motion",
            variable=self._reduced_motion_var,
            command=self._on_reduced_motion_toggled,
        ).pack(anchor="w")

    def _load_session_hours(self):
        """Load session hours."""
        defaults = {"mid_hours": 1.0, "end_hours": 2.0}
        manager = getattr(self, "layout_manager", None)
        if manager is None:
            self._session_mid_var.set(str(defaults["mid_hours"]))
            self._session_end_var.set(str(defaults["end_hours"]))
            return
        stored = manager.get_session_hours(self.scenario_name)
        mid_value = stored.get("mid_hours", defaults["mid_hours"])
        end_value = stored.get("end_hours", defaults["end_hours"])
        self._session_mid_var.set("" if mid_value is None else str(mid_value))
        self._session_end_var.set("" if end_value is None else str(end_value))

    def _parse_hours_value(self, value: str) -> Optional[float]:
        """Parse hours value."""
        trimmed = value.strip()
        if not trimmed:
            return None
        try:
            return float(trimmed)
        except ValueError:
            return None

    def _persist_session_hours(self, _event=None):
        """Persist session hours."""
        mid_value = self._parse_hours_value(self._session_mid_var.get())
        end_value = self._parse_hours_value(self._session_end_var.get())
        manager = getattr(self, "layout_manager", None)
        if manager is None:
            return
        manager.set_session_hours(self.scenario_name, mid_value, end_value)

    def _start_session(self):
        """Start session."""
        mid_value = self._parse_hours_value(self._session_mid_var.get())
        end_value = self._parse_hours_value(self._session_end_var.get())
        if mid_value is None or end_value is None:
            messagebox.showwarning("Session Timers", "Please enter numeric hour offsets for both mid and end timers.")
            return
        if mid_value < 0 or end_value < 0:
            messagebox.showwarning("Session Timers", "Hour offsets must be zero or positive.")
            return

        self._persist_session_hours()
        self._session_start = datetime.now()
        self._session_active = True
        self._plot_twist_scheduler.start(
            self._session_start,
            mid_value,
            end_value,
            on_mid=self._handle_mid_plot_twist,
            on_end=self._handle_end_plot_twist,
        )
        log_info(
            f"Session started for '{self.scenario_name}' with mid={mid_value}, end={end_value}.",
            func_name="GMScreenView._start_session",
        )
        self._update_session_controls_state()

    def _end_session(self, silent: bool = False):
        """Internal helper for end session."""
        if not self._session_active and not self._plot_twist_scheduler.is_active():
            return
        if not silent:
            self._append_session_debrief()
        self._plot_twist_scheduler.cancel()
        self._session_active = False
        self._session_start = None
        if not silent:
            log_info(f"Session ended for '{self.scenario_name}'.", func_name="GMScreenView._end_session")
        self._update_session_controls_state()

    def _update_session_controls_state(self):
        """Update session controls state."""
        is_active = bool(self._session_active)
        try:
            self._session_start_button.configure(state=("disabled" if is_active else "normal"))
            self._session_end_button.configure(state=("normal" if is_active else "disabled"))
        except Exception:
            pass

    def _handle_mid_plot_twist(self):
        """Internal helper for handle mid plot twist."""
        result = roll_plot_twist()
        messagebox.showinfo(
            "Plot Twist",
            f"Mid-session plot twist:\n{result.result}\n\n{result.table} · Roll {result.roll}",
        )

    def _handle_end_plot_twist(self):
        """Internal helper for handle end plot twist."""
        result = roll_plot_twist()
        messagebox.showinfo(
            "Plot Twist",
            f"End-of-session plot twist:\n{result.result}\n\n{result.table} · Roll {result.roll}",
        )

    def _persist_scene_state(self):
        """Persist scene state."""
        if not self._state_loaded:
            return
        manager = getattr(self, "layout_manager", None)
        if manager is None:
            return
        scenes = {key: bool(val) for key, val in self._scene_completion_state.items()}
        manager.update_scenario_state(
            self.scenario_name,
            scenes=scenes,
            notes=self._note_cache,
        )


    def open_global_search(self, event=None):
        """Open global search."""
        # Ensure the view is still alive before creating child windows
        try:
            # Keep global search resilient if this step fails.
            if not int(self.winfo_exists()):
                return
        except tk.TclError:
            return

        try:
            host = self.winfo_toplevel()
        except tk.TclError:
            return

        if host is None:
            return

        # Create popup anchored to the hosting toplevel
        popup = ctk.CTkToplevel(host)
        popup.title("Global Search")
        popup.geometry("400x300")
        popup.transient(host)
        popup.grab_set()

        # 1) Search entry
        entry = ctk.CTkEntry(popup, placeholder_text="Type to search…")
        entry.pack(fill="x", padx=10, pady=(10, 5))

        actions = ctk.CTkFrame(popup, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(0, 6))

        def open_image_search():
            """Open shared image browser with current query prefilled."""
            query = entry.get().strip()
            opener = getattr(host, "open_image_library_browser", None)
            if callable(opener):
                opener(search_query=query)
                popup.destroy()

        image_button = ctk.CTkButton(actions, text="Search Images", width=140, command=open_image_search)
        image_button.pack(side="right")

        # focus once window is up
        popup.after(10, lambda: entry.focus_force())

        # 2) Theme colors
        raw_bg    = entry.cget("fg_color")
        raw_txt   = entry.cget("text_color")
        appearance = ctk.get_appearance_mode()    # "Dark" or "Light"
        idx       = 1 if appearance == "Dark" else 0
        bg_list   = raw_bg  if isinstance(raw_bg, (list, tuple))  else raw_bg.split()
        txt_list  = raw_txt if isinstance(raw_txt,(list, tuple)) else raw_txt.split()
        bg_color    = bg_list[idx]
        text_color  = txt_list[idx]
        sel_bg      = "#3a3a3a" if appearance == "Dark" else "#d9d9d9"

        # 3) Listbox for results
        listbox = tk.Listbox(
            popup,
            activestyle="none",
            bg=bg_color,
            fg=text_color,
            highlightbackground=bg_color,
            selectbackground=sel_bg,
            selectforeground=text_color
        )
        listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 4) Navigation: ↓ from entry dives into list
        def dive_into_list(evt):
            """Handle dive into list."""
            if listbox.size() > 0:
                listbox.selection_clear(0, "end")
                listbox.selection_set(0)
                listbox.activate(0)
            listbox.focus_set()
            return "break"
        entry.bind("<Down>", dive_into_list)

        # 5) Prepare storage for (type, name)
        search_map = []

        # 6) Populate & auto-select first
        def populate(initial=False, query=""):
            """Handle populate."""
            listbox.delete(0, "end")
            search_map.clear()
            for entity_type, wrapper in self.wrappers.items():
                # Process each (entity_type, wrapper) from wrappers.items().
                items = wrapper.load_items()
                key = "Title" if entity_type in ("Scenarios", "Informations") else "Name"
                for item in items:
                    # Process each item from items.
                    name = item.get(key, "")
                    if initial or query in name.lower():
                        display = f"{entity_type[:-1]}: {name}"
                        listbox.insert("end", display)
                        search_map.append((entity_type, name))
            # auto-select first if present
            if listbox.size() > 0:
                listbox.selection_clear(0, "end")
                listbox.selection_set(0)
                listbox.activate(0)
        # initial fill
        populate(initial=True)

        # 7) Filter on typing
        def on_search(evt):
            """Handle search."""
            q = entry.get().strip().lower()
            populate(initial=False, query=q)
        entry.bind("<KeyRelease>", on_search)

        # 8) Selection handler
        def on_select(evt=None):
            """Handle select."""
            if not search_map:
                return
            selection = listbox.curselection()
            if not selection:
                return
            idx = selection[0]
            entity_type, name = search_map[idx]
            self.open_entity_tab(entity_type, name)
            popup.destroy()

        # 9) Bind Enter to select from either widget
        entry.bind("<Return>", lambda e: on_select())
        listbox.bind("<Return>", lambda e: on_select())
        entry.bind("<Control-i>", lambda _event: (open_image_search(), "break")[1])
        listbox.bind("<Control-i>", lambda _event: (open_image_search(), "break")[1])

        # 10) Double-click also selects
        listbox.bind("<Double-Button-1>", on_select)

    def open_chatbot(self, event=None):
        """Open chatbot."""
        try:
            host = self.winfo_toplevel()
        except Exception:
            host = self
        try:
            open_chatbot_dialog(host, wrappers=self.wrappers, name_field_overrides=CHATBOT_NAME_OVERRIDES)
        except Exception as exc:
            log_warning(
                f"Failed to launch chatbot: {exc}",
                func_name="GMScreenView.open_chatbot",
            )

    def load_template(self, filename):
        """Load template."""
        base_path = os.path.dirname(__file__)
        template_path = os.path.join(base_path, "..", filename)
        with open(template_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        # Merge custom_fields if present so GM screen also shows user-defined fields
        fields = list(data.get("fields", []))
        if isinstance(data.get("custom_fields"), list):
            # Handle the branch where isinstance(data.get('custom_fields'), list).
            existing = {str(f.get("name", "")).strip() for f in fields}
            for f in data["custom_fields"]:
                try:
                    # Keep template resilient if this step fails.
                    name = str(f.get("name", "")).strip()
                    if not name or name in existing:
                        continue
                    out = {"name": name, "type": f.get("type", "text")}
                    if out["type"] in ("list", "list_longtext") and f.get("linked_type"):
                        out["linked_type"] = f.get("linked_type")
                    fields.append(out)
                except Exception:
                    continue
        return {"fields": fields}

    def add_tab(self, name, content_frame, content_factory=None, layout_meta=None, activate=True):
        """Handle add tab."""
        log_info(f"Adding GM screen tab: {name}", func_name="GMScreenView.add_tab")
        meta = dict(layout_meta or {})
        category = tab_category_for_name(name)
        variant = TAB_VARIANTS[category]
        short_label = tab_short_label(name)
        icon = tab_icon_for_name(name)
        meta.setdefault("category", category)
        meta.setdefault("short_label", short_label)
        meta.setdefault("icon", icon)
        if "pinned" not in meta:
            meta["pinned"] = name.strip().lower() in self._default_pinned_tab_names

        tab_frame = ctk.CTkFrame(
            self.tab_bar,
            fg_color=variant["inactive_fg"],
            border_width=1,
            border_color=variant["inactive_border"],
            corner_radius=12,
        )
        tab_frame.pack(side="left", padx=4, pady=6)

        tab_button = ctk.CTkButton(
            tab_frame,
            text="",
            width=178,
            height=30,
            fg_color="transparent",
            hover_color=variant["inactive_hover"],
            text_color=self._palette["muted_text"],
            command=lambda: self.show_tab(name),
        )
        tab_button.pack(side="left", padx=(4, 0), pady=4)

        pin_button = ctk.CTkButton(
            tab_frame,
            text="📌",
            width=30,
            height=30,
            fg_color="transparent",
            hover_color=variant["inactive_hover"],
            text_color=self._palette["muted_text"],
            command=lambda: self.toggle_tab_pin(name),
        )
        pin_button.pack(side="left", pady=4)

        close_button = ctk.CTkButton(
            tab_frame,
            text="✕",
            width=30,
            height=30,
            fg_color="transparent",
            hover_color="#B91C1C",
            text_color=self._palette["muted_text"],
            command=lambda: self.close_tab(name),
        )
        close_button.pack(side="left", pady=4)

        detach_button = ctk.CTkButton(
            tab_frame,
            image=self.detach_icon,
            text="",
            width=42,
            height=30,
            fg_color="transparent",
            hover_color=variant["inactive_hover"],
            command=lambda: self.toggle_detach_tab(name),
        )
        detach_button.pack(side="left", padx=(0, 4), pady=4)

        portrait_label = getattr(content_frame, "portrait_label", None)
        self.tabs[name] = {
            "button_frame": tab_frame,
            "content_frame": content_frame,
            "button": tab_button,
            "pin_button": pin_button,
            "detach_button": detach_button,
            "detached": False,
            "window": None,
            "portrait_label": portrait_label,
            "factory": content_factory,
            "meta": meta,
        }
        self._apply_tab_visual_state(name, is_active=False)

        content_frame.pack_forget()
        if activate:
            self.show_tab(name)
        # 1) append to order list
        self.tab_order.append(name)

        # collect ALL the widgets you need to drag
        draggable_widgets = (
            tab_frame,
            tab_button,
            pin_button,
            close_button,
            detach_button
        )

        for w in draggable_widgets:
            w.bind("<Button-1>",        lambda e=None, n=name: self._on_tab_press(e, n))
            w.bind("<B1-Motion>",       lambda e=None, n=name: self._on_tab_motion(e, n))
            w.bind("<ButtonRelease-1>", lambda e=None, n=name: self._on_tab_release(e, n))

        self.reposition_add_button()
        self._refresh_command_deck()

    def _teardown_tab_content(self, frame):
        """Tear down tab content."""
        if frame is None:
            return
        controller = getattr(frame, "whiteboard_controller", None)
        if controller and hasattr(controller, "close"):
            try:
                controller.close()
            except Exception:
                pass

    def _apply_initial_layout(self):
        """Apply initial layout."""
        layout_name = self._pending_initial_layout
        if not layout_name:
            layout_name = self.layout_manager.get_scenario_default(self.scenario_name)
        if not layout_name:
            return
        self.load_layout(layout_name, silent=True)

    def _initialize_context_menu(self):
        """Internal helper for initialize context menu."""
        if self._context_menu is not None:
            return

        self._context_menu = tk.Menu(self, tearoff=0)
        self._context_menu.add_command(
            label=self._edit_menu_label,
            command=self._edit_current_entity,
            state="disabled",
        )

        targets = [self, self.content_area, getattr(self.content_area, "_scrollable_frame", None)]
        for widget in targets:
            # Process each widget from targets.
            if widget is None:
                continue
            widget.bind("<Button-3>", self._show_context_menu)
            widget.bind("<Control-Button-1>", self._show_context_menu)

    def reset_scene_widgets(self):
        """Reset scene widgets."""
        self._scene_vars = {}
        self._scene_order = []
        self._scene_metadata = {}

    def register_scene_widget(self, scene_key, var, checkbox, display_label=None, description=None, note_title=None):
        """Register scene widget."""
        self._scene_vars[scene_key] = {
            "var": var,
            "checkbox": checkbox,
            "display_label": display_label,
        }
        self._scene_metadata[scene_key] = {
            "display_label": display_label,
            "description": description,
            "note_title": note_title,
        }
        if scene_key not in self._scene_order:
            self._scene_order.append(scene_key)
        self._scene_completion_state.setdefault(scene_key, bool(var.get()))

        def _on_change(*_):
            """Handle change."""
            self._on_scene_var_change(scene_key)

        try:
            var.trace_add("write", _on_change)
        except AttributeError:
            var.trace("w", _on_change)  # fallback for older tkinter versions

        if checkbox is not None:
            checkbox.bind("<Button-3>", self._show_context_menu)
            checkbox.bind("<Control-Button-1>", self._show_context_menu)

    def _on_scene_var_change(self, scene_key):
        """Handle scene var change."""
        var_info = self._scene_vars.get(scene_key)
        if not var_info:
            return
        var = var_info.get("var")
        self._scene_completion_state[scene_key] = bool(var.get())
        self._persist_scene_state()
        if bool(var.get()):
            self._append_scene_to_notes(scene_key)

    def get_scene_completion(self, scene_key):
        """Return scene completion."""
        return self._scene_completion_state.get(scene_key, False)

    def _set_scene_var(self, scene_key, value):
        """Set scene var."""
        var_info = self._scene_vars.get(scene_key)
        if not var_info:
            self._scene_completion_state[scene_key] = bool(value)
            return
        var = var_info.get("var")
        if bool(var.get()) == bool(value):
            self._scene_completion_state[scene_key] = bool(value)
            self._persist_scene_state()
            return
        var.set(bool(value))
        self._scene_completion_state[scene_key] = bool(value)
        if bool(value):
            self._append_scene_to_notes(scene_key)

    def set_active_scene(self, scene_key):
        """Set active scene."""
        self._active_scene_key = scene_key

    def mark_active_scene_complete(self):
        """Handle mark active scene complete."""
        if self._active_scene_key and self._active_scene_key in self._scene_vars:
            self._set_scene_var(self._active_scene_key, True)
            return True
        return self.mark_next_scene_complete()

    def mark_next_scene_complete(self):
        """Handle mark next scene complete."""
        for key in self._scene_order:
            if not self._scene_completion_state.get(key, False):
                self._active_scene_key = key
                self._set_scene_var(key, True)
                return True
        return False

    def _append_note_entry(self, entry_text):
        """Append note entry."""
        if not entry_text:
            return
        text = entry_text.strip()
        if not text:
            return

        if self.note_widget:
            existing = self.note_widget.get("1.0", "end-1c").strip()
            prefix = "\n\n" if existing else ""
            self.note_widget.insert("end", f"{prefix}{text}")
            self.note_widget.see("end")
            self._update_note_cache()
            return

        existing = self._note_cache.strip()
        prefix = "\n\n" if existing else ""
        self._note_cache = f"{existing}{prefix}{text}".strip()
        self._persist_scene_state()

    def _capture_scene_snapshot(self):
        """Internal helper for capture scene snapshot."""
        metadata = self._scene_metadata.get(self._active_scene_key) if self._active_scene_key else {}
        entry = build_scene_snapshot_entry(
            timestamp=datetime.now(),
            scene_key=self._active_scene_key,
            scene_metadata=metadata,
            active_tab=self.current_tab,
        )
        self._append_note_entry(entry)

    def _append_session_debrief(self):
        """Append session debrief."""
        labels = {}
        for key, metadata in self._scene_metadata.items():
            label = (metadata or {}).get("display_label") or key
            labels[key] = str(label).strip()

        completed = [
            labels.get(key, key)
            for key in self._scene_order
            if self._scene_completion_state.get(key, False)
        ]
        pending = [
            labels.get(key, key)
            for key in self._scene_order
            if not self._scene_completion_state.get(key, False)
        ]
        if not completed and not pending and labels:
            for key, value in labels.items():
                target = completed if self._scene_completion_state.get(key, False) else pending
                target.append(value)

        entry = build_session_debrief_entry(
            scenario_name=self.scenario_name,
            started_at=self._session_start,
            ended_at=datetime.now(),
            completed_scenes=completed,
            pending_scenes=pending,
        )
        self._append_note_entry(entry)

    def add_timestamped_note(self):
        """Handle add timestamped note."""
        if not self.note_widget:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        existing = self.note_widget.get("1.0", "end-1c").strip()
        prefix = "\n" if existing else ""
        self.note_widget.insert("end", f"{prefix}[{timestamp}] ")
        self.note_widget.see("end")
        self._update_note_cache()

    def open_note_editor(self):
        """Open note editor."""
        if self._note_editor_window and self._note_editor_window.winfo_exists():
            # Handle the branch where note editor window is set and _note_editor_window.winfo_exists().
            try:
                self._note_editor_window.lift()
                self._note_editor_window.focus_force()
            except Exception:
                pass
            return

        if self.note_widget:
            try:
                self._note_cache = self.note_widget.get("1.0", "end-1c")
            except Exception:
                pass

        try:
            host = self.winfo_toplevel()
        except Exception:
            host = None

        editor_parent = host or self
        editor = ctk.CTkToplevel(editor_parent)
        editor.title("Edit GM Notes")

        if host is not None:
            try:
                editor.transient(host)
            except Exception:
                pass

        try:
            editor.grab_set()
        except Exception:
            pass

        try:
            editor.attributes("-topmost", True)
        except Exception:
            pass

        try:
            # Keep note editor resilient if this step fails.
            editor.attributes("-fullscreen", True)
        except Exception:
            try:
                editor.state("zoomed")
            except Exception:
                try:
                    width = editor.winfo_screenwidth()
                    height = editor.winfo_screenheight()
                    editor.geometry(f"{width}x{height}+0+0")
                except Exception:
                    pass

        container = ctk.CTkFrame(editor, fg_color="transparent")
        container.pack(fill="both", expand=True)

        toolbar = ctk.CTkFrame(container, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            toolbar,
            text="Edit GM Notes",
            font=("Arial", 20, "bold"),
        ).pack(side="left")

        text_box = ctk.CTkTextbox(container, wrap="word")
        text_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        text_box.insert("1.0", self._note_cache)

        def save_and_close(event=None):
            """Save and close."""
            note_text = text_box.get("1.0", "end-1c")
            self._apply_note_editor_changes(note_text)
            self._close_note_editor_window()
            return "break"

        def cancel_and_close(event=None):
            """Handle cancel and close."""
            self._close_note_editor_window()
            return "break"

        ctk.CTkButton(
            toolbar,
            text="Save & Close",
            command=save_and_close,
            width=150,
        ).pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            toolbar,
            text="Cancel",
            command=cancel_and_close,
            width=120,
        ).pack(side="right")

        try:
            editor.protocol("WM_DELETE_WINDOW", save_and_close)
        except Exception:
            pass

        editor.bind("<Escape>", cancel_and_close)
        editor.after(10, text_box.focus_force)

        self._note_editor_window = editor

    def _apply_note_editor_changes(self, new_text):
        """Apply note editor changes."""
        self._note_cache = new_text
        widget = self.note_widget
        widget_exists = False
        if widget is not None:
            try:
                widget_exists = bool(int(widget.winfo_exists()))
            except Exception:
                widget_exists = False

        if widget_exists:
            # Continue with this path when widget exists is set.
            widget.delete("1.0", "end")
            if new_text:
                widget.insert("1.0", new_text)
            self._update_note_cache()
        else:
            self._persist_scene_state()

    def _close_note_editor_window(self, event=None):
        """Close note editor window."""
        window = getattr(self, "_note_editor_window", None)
        if window is not None:
            # Handle the branch where window is available.
            try:
                window.grab_release()
            except Exception:
                pass
            try:
                window.destroy()
            except Exception:
                pass
        self._note_editor_window = None

    def _update_note_cache(self, event=None):
        """Update note cache."""
        if self.note_widget:
            self._note_cache = self.note_widget.get("1.0", "end-1c")
            self._persist_scene_state()

    def register_note_widget(self, widget):
        """Register note widget."""
        self.note_widget = widget
        widget.delete("1.0", "end")
        if self._note_cache:
            widget.insert("1.0", self._note_cache)
        widget.bind("<KeyRelease>", self._update_note_cache)
        widget.bind("<FocusOut>", self._update_note_cache)
        widget.bind("<Button-3>", self._show_context_menu)
        widget.bind("<Control-Button-1>", self._show_context_menu)

    def get_note_text(self):
        """Return note text."""
        return self._note_cache

    def _append_scene_to_notes(self, scene_key):
        """Append scene to notes."""
        metadata = self._scene_metadata.get(scene_key) or {}
        description = (metadata.get("description") or "").strip()
        if not description:
            return
        title = metadata.get("note_title") or metadata.get("display_label") or scene_key
        title = str(title).strip()
        entry_lines = []
        if title:
            entry_lines.append(title if title.endswith(":") else f"{title}:")
        entry_lines.append(description)
        entry_text = "\n".join(entry_lines).strip()
        if not entry_text:
            return

        if self.note_widget:
            existing = self.note_widget.get("1.0", "end-1c").strip()
        else:
            existing = self._note_cache.strip()

        prefix = "\n\n" if existing else ""

        if self.note_widget:
            self.note_widget.insert("end", f"{prefix}{entry_text}")
            self.note_widget.see("end")
            self._update_note_cache()
        else:
            self._note_cache = f"{existing}{prefix}{entry_text}".strip()
            self._persist_scene_state()

    def _get_active_entity_frame(self):
        """Return active entity frame."""
        if not self.current_tab:
            return None
        tab_info = self.tabs.get(self.current_tab, {})
        meta = tab_info.get("meta") or {}
        if meta.get("kind") != "entity":
            return None
        return tab_info.get("content_frame")

    def _get_active_entity_edit_handler(self):
        """Return active entity edit handler."""
        frame = self._get_active_entity_frame()
        if frame is None:
            return None
        handler = getattr(frame, "edit_entity", None)
        return handler if callable(handler) else None

    def _edit_current_entity(self):
        """Internal helper for edit current entity."""
        handler = self._get_active_entity_edit_handler()
        if not handler:
            return

        def _open_editor():
            """Open editor."""
            try:
                # Keep editor resilient if this step fails.
                if self._context_menu is not None:
                    # Handle the branch where context menu is available.
                    try:
                        # Explicitly close any visible menu before opening the
                        # editor window. Some Tk builds can keep the menu
                        # posted (and effectively modal) even after the command
                        # callback starts running.
                        self._context_menu.unpost()
                    except Exception:
                        pass
                    try:
                        self._context_menu.grab_release()
                    except Exception:
                        pass
                handler()
            except Exception as exc:
                messagebox.showerror("Edit Entity", f"Unable to open editor: {exc}")

        # Opening the modal editor directly from the tk.Menu callback can leave
        # the menu grab active while EditWindow waits on the dialog, which blocks
        # all interaction. Deferring to idle lets tk_popup unwind cleanly first.
        self.after_idle(_open_editor)

    def _show_context_menu(self, event):
        """Show context menu."""
        if not self._context_menu:
            return
        if self.current_tab == self.scenario_name:
            return
        edit_available = self._get_active_entity_edit_handler() is not None
        if not edit_available:
            return
        try:
            self._context_menu.entryconfig(
                self._edit_menu_label,
                state="normal" if edit_available else "disabled",
            )
        except Exception:
            pass
        try:
            # Keep context menu resilient if this step fails.
            self._context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._context_menu.grab_release()

    def _update_layout_status(self, name=None):
        """Update layout status."""
        self.current_layout_name = name
        if name:
            self.layout_status_label.configure(text=f"Layout: {name}")
        else:
            self.layout_status_label.configure(text="")

    # ------------------------------------------------------------------
    # Layout persistence helpers
    # ------------------------------------------------------------------
    def _serialize_current_layout(self):
        """Serialize current layout."""
        layout_tabs = []
        for tab_name in self.tab_order:
            # Process each tab_name from tab_order.
            tab_info = self.tabs.get(tab_name)
            if not tab_info:
                continue
            meta = dict(tab_info.get("meta") or {})
            meta["title"] = tab_name
            if meta.get("kind") == "note":
                # Handle the branch where meta.get('kind') == 'note'.
                frame = tab_info.get("content_frame")
                if frame is not None and hasattr(frame, "text_box"):
                    meta["text"] = frame.text_box.get("1.0", "end-1c")
            elif meta.get("kind") == "world_map":
                # Handle the branch where meta.get('kind') == 'world_map'.
                frame = tab_info.get("content_frame")
                map_name = None
                panel = getattr(frame, "world_map_panel", None)
                if panel is not None:
                    map_name = getattr(panel, "current_map_name", None)
                if map_name:
                    meta["map_name"] = map_name
                else:
                    meta.pop("map_name", None)
            elif meta.get("kind") == "map_tool":
                # Handle the branch where meta.get('kind') == 'map_tool'.
                frame = tab_info.get("content_frame")
                controller = getattr(frame, "map_controller", None)
                current = getattr(controller, "current_map", None)
                name = None
                if isinstance(current, dict):
                    name = current.get("Name") or current.get("Title")
                if name:
                    meta["map_name"] = name
                else:
                    meta.pop("map_name", None)
            elif meta.get("kind") == "scene_flow":
                # Handle the branch where meta.get('kind') == 'scene_flow'.
                frame = tab_info.get("content_frame")
                viewer = getattr(frame, "scene_flow_viewer", None)
                title = None
                if viewer is not None and hasattr(viewer, "scenario_var"):
                    try:
                        title = str(viewer.scenario_var.get()).strip()
                    except Exception:
                        title = None
                if title and title != "No scenarios available":
                    meta["scenario_title"] = title
                else:
                    meta.pop("scenario_title", None)
            elif meta.get("kind") == "random_tables":
                # Handle the branch where meta.get('kind') == 'random_tables'.
                frame = tab_info.get("content_frame")
                if frame is not None and hasattr(frame, "get_state"):
                    meta["state"] = frame.get_state()
                else:
                    meta.pop("state", None)
            elif meta.get("kind") == "whiteboard":
                meta.pop("controller", None)
            elif meta.get("kind") == "campaign_dashboard":
                meta.pop("cache", None)
            layout_tabs.append(meta)
        return {
            "scenario": self.scenario_name,
            "tabs": layout_tabs,
            "active": self.current_tab,
        }

    def _prompt_save_layout(self):
        """Internal helper for prompt save layout."""
        data = self._serialize_current_layout()
        if not data["tabs"]:
            messagebox.showwarning("Empty Layout", "There are no tabs to save yet.")
            return

        existing_layouts = self.layout_manager.list_layouts()

        dialog = ctk.CTkToplevel(self)
        dialog.title("Save Layout")
        dialog.geometry("340x400")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Choose an existing layout to overwrite or enter a new name:",
            wraplength=300,
            justify="left",
        ).pack(fill="x", padx=10, pady=(10, 5))

        listbox = tk.Listbox(dialog, activestyle="none")
        listbox.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        existing_names = sorted(existing_layouts.keys())
        for name in existing_names:
            listbox.insert("end", name)

        entry_var = tk.StringVar(dialog, value=(self.current_layout_name or ""))
        entry = ctk.CTkEntry(dialog, textvariable=entry_var)
        entry.pack(fill="x", padx=10, pady=(0, 10))
        entry.focus_set()

        button_bar = ctk.CTkFrame(dialog)
        button_bar.pack(fill="x", padx=10, pady=(0, 10))

        def _close_dialog():
            """Close dialog."""
            if dialog.winfo_exists():
                # Handle the branch where dialog.winfo_exists().
                try:
                    dialog.grab_release()
                except Exception:
                    pass
                dialog.destroy()

        def _do_save():
            """Internal helper for do save."""
            layout_name = entry_var.get().strip()
            if not layout_name:
                messagebox.showwarning("Invalid Name", "Please enter a name for the layout.")
                return
            if layout_name in existing_layouts and not messagebox.askyesno(
                "Overwrite Layout?",
                f"A layout named '{layout_name}' already exists. Overwrite it?",
            ):
                return

            _close_dialog()
            self.layout_manager.save_layout(layout_name, data)
            if messagebox.askyesno(
                "Set Default?",
                f"Use '{layout_name}' whenever '{self.scenario_name}' is opened?",
            ):
                self.layout_manager.set_scenario_default(self.scenario_name, layout_name)
            messagebox.showinfo("Layout Saved", f"Layout '{layout_name}' saved successfully.")
            self._update_layout_status(layout_name)

        def _populate_entry(_event=None):
            """Internal helper for populate entry."""
            selection = listbox.curselection()
            if selection:
                entry_var.set(listbox.get(selection[0]))

        if existing_names:
            # Continue with this path when existing names is set.
            try:
                default_index = existing_names.index(self.current_layout_name)
            except ValueError:
                default_index = 0
            listbox.selection_set(default_index)
            listbox.see(default_index)
            if not entry_var.get().strip():
                entry_var.set(existing_names[default_index])

        listbox.bind("<<ListboxSelect>>", _populate_entry)
        listbox.bind("<Double-Button-1>", lambda _e: _do_save())
        dialog.bind("<Return>", lambda _e: _do_save())

        save_btn = ctk.CTkButton(button_bar, text="Save", command=_do_save)
        save_btn.pack(side="right")
        cancel_btn = ctk.CTkButton(button_bar, text="Cancel", command=_close_dialog)
        cancel_btn.pack(side="right", padx=(0, 5))

        dialog.protocol("WM_DELETE_WINDOW", _close_dialog)

    def _open_load_layout_dialog(self):
        """Open load layout dialog."""
        layouts = self.layout_manager.list_layouts()
        if not layouts:
            messagebox.showinfo("No Layouts", "No saved GM screen layouts were found.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Load Layout")
        dialog.geometry("320x360")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Select a layout to load:").pack(fill="x", padx=10, pady=(10, 5))
        listbox = tk.Listbox(dialog, activestyle="none")
        listbox.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        for name in layouts:
            listbox.insert("end", name)
        listbox.selection_set(0)

        set_default_var = tk.BooleanVar(dialog, value=False)
        chk = ctk.CTkCheckBox(dialog, text="Set as default for this scenario", variable=set_default_var)
        chk.pack(fill="x", padx=10, pady=5)

        button_bar = ctk.CTkFrame(dialog)
        button_bar.pack(fill="x", padx=10, pady=(0, 10))

        def _do_load():
            """Internal helper for do load."""
            selection = listbox.curselection()
            if not selection:
                return
            chosen = listbox.get(selection[0])
            dialog.grab_release()
            dialog.destroy()
            self.load_layout(chosen, set_default=set_default_var.get())

        load_btn = ctk.CTkButton(button_bar, text="Load", command=_do_load)
        load_btn.pack(side="right")
        cancel_btn = ctk.CTkButton(button_bar, text="Cancel", command=lambda: dialog.destroy())
        cancel_btn.pack(side="right", padx=(0, 5))

        listbox.bind("<Double-Button-1>", lambda _e: _do_load())
        dialog.bind("<Return>", lambda _e: _do_load())

    def _clear_all_tabs(self):
        """Clear all tabs."""
        for name, tab in list(self.tabs.items()):
            # Process each (name, tab) from list(tabs.items()).
            if tab.get("detached") and tab.get("window") is not None:
                try:
                    tab["window"].destroy()
                except Exception:
                    pass
            tab_frame = tab.get("button_frame")
            if tab_frame is not None and tab_frame.winfo_exists():
                tab_frame.destroy()
            content = tab.get("content_frame")
            self._teardown_tab_content(content)
            if content is not None and content.winfo_exists():
                content.destroy()
        self.tabs.clear()
        self.tab_order.clear()
        self.current_tab = None
        self.reposition_add_button()
        self._update_layout_status(None)

    def _restore_tab_from_config(self, tab_def):
        """Restore tab from config."""
        kind = tab_def.get("kind")
        title = tab_def.get("title")
        if kind == "entity":
            # Handle the branch where kind == 'entity'.
            entity_type = tab_def.get("entity_type")
            entity_name = tab_def.get("entity_name") or title
            if not entity_type or not entity_name:
                raise ValueError("Missing entity information")
            self._open_entity_from_layout(entity_type, entity_name)
        elif kind == "note":
            # Handle the branch where kind == 'note'.
            text = tab_def.get("text", "")
            name = title or f"Note {len(self.tabs) + 1}"
            self.add_tab(
                name,
                self.create_note_frame(initial_text=text),
                content_factory=lambda master, initial_text=text: self.create_note_frame(master=master, initial_text=initial_text),
                layout_meta={"kind": "note"},
            )
        elif kind in ("npc_graph", "pc_graph", "character_graph"):
            # Ensure rich host exists for graph editors
            parent = self._ensure_rich_host()
            self.add_tab(
                title or "Character Graph",
                self.create_character_graph_frame(master=parent),
                content_factory=lambda master=parent: self.create_character_graph_frame(master),
                layout_meta={"kind": "character_graph", "host": "rich"},
            )
        elif kind == "scenario_graph":
            # Handle the branch where kind == 'scenario_graph'.
            parent = self._ensure_rich_host()
            self.add_tab(
                title or "Scenario Graph Editor",
                self.create_scenario_graph_frame(master=parent),
                content_factory=lambda master=parent: self.create_scenario_graph_frame(master),
                layout_meta={"kind": "scenario_graph", "host": "rich"},
            )
        elif kind == "world_map":
            # Handle the branch where kind == 'world_map'.
            name = tab_def.get("map_name")
            self.open_world_map_tab(map_name=name, title=title or (f"World Map: {name}" if name else "World Map"))
        elif kind == "campaign_dashboard":
            self.open_campaign_dashboard_tab(title=title or "Campaign Dashboard")
        elif kind == "map_tool":
            # Handle the branch where kind == 'map_tool'.
            name = tab_def.get("map_name")
            self.open_map_tool_tab(map_name=name, title=title or (f"Map Tool: {name}" if name else "Map Tool"))
        elif kind == "scene_flow":
            # Handle the branch where kind == 'scene_flow'.
            scen = tab_def.get("scenario_title")
            self.open_scene_flow_tab(scenario_title=scen, title=title or (f"Scene Flow: {scen}" if scen else "Scene Flow"))
        elif kind == "loot_generator":
            self.open_loot_generator_tab(title=title or "Loot Generator")
        elif kind == "random_tables":
            self.open_random_tables_tab(title=title or "Random Tables", initial_state=tab_def.get("state"))
        elif kind == "whiteboard":
            self.open_whiteboard_tab(title=title or "Whiteboard")
        elif kind == "handouts":
            self.open_handouts_tab(title=title or "Handouts")
        elif kind == "puzzle_display":
            # Handle the branch where kind == 'puzzle_display'.
            puzzle_name = tab_def.get("puzzle_name")
            puzzle_item = None
            if puzzle_name:
                wrapper = self.wrappers.get("Puzzles")
                items = wrapper.load_items() if wrapper else []
                puzzle_item = next((i for i in items if i.get("Name") == puzzle_name), None)
            self.open_puzzle_display_tab(puzzle_item or {}, title=title or "Puzzle Display")
        else:
            raise ValueError(f"Unsupported tab kind '{kind}'")

    def load_layout(self, layout_name, set_default=False, silent=False):
        """Load layout."""
        layout = self.layout_manager.get_layout(layout_name)
        if not layout:
            # Handle the branch where layout is unavailable.
            if not silent:
                messagebox.showwarning("Layout Missing", f"Layout '{layout_name}' was not found.")
            return

        tabs = layout.get("tabs", [])
        if not tabs:
            # Handle the branch where tabs is unavailable.
            if not silent:
                messagebox.showwarning("Empty Layout", f"Layout '{layout_name}' has no tabs saved.")
            return

        self._clear_all_tabs()

        errors = []
        pending = deque(tabs)

        def _finalize_restore():
            """Internal helper for finalize restore."""
            if not self.tabs:
                # Handle the branch where tabs is unavailable.
                scenario_name = self.scenario.get("Title") or self.scenario.get("Name") or "Scenario"
                frame = create_entity_detail_frame(
                    "Scenarios",
                    self.scenario,
                    master=self.content_area,
                    open_entity_callback=self.open_entity_tab,
                )
                self.add_tab(
                    scenario_name,
                    frame,
                    content_factory=lambda master: create_entity_detail_frame(
                        "Scenarios",
                        self.scenario,
                        master=master,
                        open_entity_callback=self.open_entity_tab,
                    ),
                    layout_meta={
                        "kind": "entity",
                        "entity_type": "Scenarios",
                        "entity_name": scenario_name,
                    },
                )

            active_name = layout.get("active")
            if active_name and active_name in self.tabs:
                self.show_tab(active_name)
            elif self.tab_order:
                self.show_tab(self.tab_order[0])

            for tab_name in list(self.tabs.keys()):
                self._reset_tab_scroll_state(tab_name)

            if set_default:
                self.layout_manager.set_scenario_default(self.scenario_name, layout_name)
            elif layout.get("scenario") == self.scenario_name and layout_name == self.layout_manager.get_scenario_default(self.scenario_name):
                pass

            if self.tabs:
                status_name = layout_name if not errors else f"{layout_name} (partial)"
                self._update_layout_status(status_name)

            if errors and not silent:
                messagebox.showwarning(
                    "Layout Issues",
                    "Some tabs could not be restored:\n" + "\n".join(errors),
                )

        def _restore_next():
            """Restore next."""
            if not pending:
                _finalize_restore()
                return
            tab_def = pending.popleft()
            try:
                self._restore_tab_from_config(tab_def)
            except Exception as exc:
                errors.append(f"{tab_def.get('title', 'Unknown')}: {exc}")
            self.update_idletasks()
            self.after_idle(_restore_next)

        self.after_idle(_restore_next)

    def _open_entity_from_layout(self, entity_type, entity_name):
        """Open entity from layout."""
        if entity_type == "Scenarios" and (self.scenario.get("Title") == entity_name or self.scenario.get("Name") == entity_name):
            # Handle this branch separately before continuing.
            factory = lambda master: create_entity_detail_frame(
                "Scenarios",
                self.scenario,
                master=master,
                open_entity_callback=self.open_entity_tab,
            )
            frame = self._build_hidden_tab_content(self.content_area, factory, scrollable=False)
            self.add_tab(
                entity_name,
                frame,
                content_factory=lambda master: self._build_hidden_tab_content(master, factory, scrollable=False),
                layout_meta={
                    "kind": "entity",
                    "entity_type": "Scenarios",
                    "entity_name": entity_name,
                },
            )
            return
        self.open_entity_tab(entity_type, entity_name)

    def _on_tab_press(self, event, name):
        """Handle tab press."""
        if event is None:
            return
        # 1) Make sure winfo_x/y are up-to-date
        self.tab_bar.update_idletasks()

        # 2) Start drag state
        self.dragging = {"name": name, "start_x": event.x_root}

        # 3) Convert every tab HEADER to place() at its current pixel pos
        for tn in self.tab_order:
            f = self.tabs[tn]["button_frame"]
            fx, fy = f.winfo_x(), f.winfo_y()
            f.pack_forget()
            f.place(in_=self.tab_bar, x=fx, y=fy)

        # 4) Hide the “+” and "?" so it doesn’t get in the way
        self.add_button.pack_forget()
        self.random_button.pack_forget()
        
        # 5) Lift the one we’re dragging above the others
        self.tabs[name]["button_frame"].lift()

    def _on_tab_motion(self, event, name):
        """Handle tab motion."""
        if event is None:
            return
        frame = self.tabs[name]["button_frame"]
        rel_x = event.x_root - self.tab_bar.winfo_rootx() - frame.winfo_width() // 2

        # move the dragged tab along with the cursor
        frame.place_configure(x=rel_x)

        # same midpoint-swap logic as before…
        for idx, other in enumerate(self.tab_order):
            # Process each (idx, other) from enumerate(tab_order).
            if other == name: continue
            of = self.tabs[other]["button_frame"]
            mid = of.winfo_x() + of.winfo_width() // 2

            if rel_x < mid and self.tab_order.index(name) > idx:
                self._trigger_shift(other, dx=frame.winfo_width())
                self._swap_order(name, other)
                break
            if rel_x > mid and self.tab_order.index(name) < idx:
                self._trigger_shift(other, dx=-frame.winfo_width())
                self._swap_order(name, other)
                break
                
    def _trigger_shift(self, other_name, dx):
        """Internal helper for trigger shift."""
        oframe = self.tabs[other_name]["button_frame"]
        start = oframe.winfo_x()
        target = start + dx
        self._animate_shift([oframe], [dx])

    def _animate_shift(self, frames, deltas, step=0):
        """Internal helper for animate shift."""
        if step >= 10: return
        for frame, delta in zip(frames, deltas):
            cur = frame.winfo_x()
            frame.place_configure(x=cur + delta/10)
        self.after(20, lambda: self._animate_shift(frames, deltas, step+1))
    
    def _swap_order(self, name, other):
        """Internal helper for swap order."""
        old = self.tab_order.index(name)
        new = self.tab_order.index(other)
        self.tab_order.pop(old)
        self.tab_order.insert(new, name)

    def _on_tab_release(self, event, name):
        """Handle tab release."""
        if event is None:
            return
        # snap all headers back into pack()
        for tn in self.tab_order:
            f = self.tabs[tn]["button_frame"]
            f.place_forget()
            f.pack(side="left", padx=2, pady=5)

        # **use your helper** to put “+” back in line
        self.reposition_add_button()
        self.tab_bar_canvas.configure(
            scrollregion=self.tab_bar_canvas.bbox("all")
        )
        self.dragging = None

    def toggle_detach_tab(self, name):
        """Toggle detach tab."""
        log_info(f"Toggling detach for tab: {name}", func_name="GMScreenView.toggle_detach_tab")
        self._motion.pulse_widget(self.tabs.get(name, {}).get("detach_button"), duration_ms=140)
        if self.tabs[name]["detached"]:
            self.reattach_tab(name)
            # After reattaching, show the detach icon
            self.tabs[name]["detach_button"].configure(image=self.detach_icon)
        else:
            self.detach_tab(name)
            # When detached, change to the reattach icon
            self.tabs[name]["detach_button"].configure(image=self.reattach_icon)
        self._apply_tab_visual_state(name, is_active=(self.current_tab == name))
        self._refresh_command_deck()

    def detach_tab(self, name):
        """Handle detach tab."""
        log_info(f"Detaching tab: {name}", func_name="GMScreenView.detach_tab")
        print(f"[DETACH] Start detaching tab: {name}")
        if self.tabs[name].get("detached", False):
            print(f"[DETACH] Tab '{name}' is already detached.")
            return

        # Hide the current content
        old_frame = self.tabs[name]["content_frame"]
        self._teardown_tab_content(old_frame)
        old_frame.pack_forget()

        # Create the Toplevel (hidden briefly)
        detached_window = ctk.CTkToplevel(self)
        detached_window.withdraw()
        detached_window.title(name)
        detached_window.lift()
        detached_window.attributes("-topmost", True)
        detached_window.protocol("WM_DELETE_WINDOW", lambda: None)

        # Build the new content frame
        if name.startswith("Note") and hasattr(old_frame, "text_box"):
            txt = old_frame.text_box.get("1.0", "end-1c")
            new_frame = self.create_note_frame(detached_window, initial_text=txt)
        else:
            factory = self.tabs[name].get("factory")
            new_frame = old_frame if factory is None else factory(detached_window)

        # Pack so children are laid out
        new_frame.pack(fill="both", expand=True)
        new_frame.update_idletasks()

        # If there's a graph editor, restore its state right away
        if hasattr(old_frame, "graph_editor") and hasattr(old_frame.graph_editor, "get_state"):
            # Handle the branch where hasattr(old_frame, 'graph_editor') and hasattr(old_frame.graph_editor, 'get_state').
            state = old_frame.graph_editor.get_state()
            if state and hasattr(new_frame, "graph_editor") and hasattr(new_frame.graph_editor, "set_state"):
                ge = new_frame.graph_editor
                # draw full-size background & links
                ce = ge.canvas
                ce.update_idletasks()
                cfg = type("E", (), {
                    "width":  ce.winfo_width(),
                    "height": ce.winfo_height()
                })()
                ge._on_canvas_configure(cfg)
                ge.set_state(state)

        # Hard-code size for all graph windows
        GRAPH_W, GRAPH_H = 1600, 800
        x_off = getattr(GMScreenView, "detached_count", 0) * (GRAPH_W + 10)
        y_off = 0
        detached_window.geometry(f"{GRAPH_W}x{GRAPH_H}")
        GMScreenView.detached_count = getattr(GMScreenView, "detached_count", 0) + 1

        detached_window.deiconify()
        self._motion.fade_in_window(detached_window, duration_ms=180)
        print(f"[DETACH] Detached window shown at {GRAPH_W}×{GRAPH_H}")

        # Portrait & scenario-graph restoration (unchanged)…
        if hasattr(old_frame, "scenario_graph_editor") and hasattr(old_frame.scenario_graph_editor, "get_state"):
            # Handle this branch separately before continuing.
            scen = old_frame.scenario_graph_editor.get_state()
            if scen and hasattr(new_frame, "scenario_graph_editor") and hasattr(new_frame.scenario_graph_editor, "set_state"):
                new_frame.scenario_graph_editor.set_state(scen)

        if hasattr(new_frame, "portrait_label"):
            # Handle the branch where hasattr(new_frame, 'portrait_label').
            self.tabs[name]["portrait_label"] = new_frame.portrait_label
        else:
            pl = self.tabs[name].get("portrait_label")
            if pl and pl.winfo_exists():
                # Handle the branch where pl is set and pl.winfo_exists().
                key = getattr(pl, "entity_name", None)
                if key in self.portrait_images:
                    lab = ctk.CTkLabel(new_frame, image=self.portrait_images[key], text="")
                    lab.image = self.portrait_images[key]
                    lab.entity_name = key
                    lab.is_portrait = True
                    lab.pack(pady=10)
                    self.tabs[name]["portrait_label"] = lab

        # Mark as detached
        self.tabs[name]["detached"]       = True
        self.tabs[name]["window"]         = detached_window
        self.tabs[name]["content_frame"]  = new_frame
        print(f"[DETACH] Tab '{name}' successfully detached.")


    def create_note_frame(self, master=None, initial_text=""):
        """Create note frame."""
        if master is None:
            master = self.content_area
        frame = ctk.CTkFrame(master)
        toolbar = ctk.CTkFrame(frame)
        toolbar.pack(fill="x", padx=5, pady=5)
        save_button = ctk.CTkButton(
            toolbar,
            text="Save Note",
            command=lambda: self.save_note_to_file(frame, f"Note_{len(self.tabs)}")
        )
        save_button.pack(side="right", padx=5)
        text_box = ctk.CTkTextbox(frame, wrap="word", height=500)
        text_box.pack(fill="both", expand=True, padx=10, pady=5)
        text_box.insert("1.0", initial_text)
        frame.text_box = text_box
        return frame

    # --- Full-bleed helpers for rich, interactive views hosted in the scrollable area ---
    def _make_fullbleed(self, container: ctk.CTkFrame):
        """Force a container to match the visible area height/width.

        CTkScrollableFrame sizes its internal `_scrollable_frame` to content.
        For interactive canvases (map tool, world map, scene flow) we want to
        occupy all available space. This syncs the container size to the
        viewport on resize.
        """
        try:
            container.pack_propagate(False)
        except Exception:
            pass

    def open_whiteboard_tab(self, title=None, activate=True):
        """Open a whiteboard tab within the GM screen."""
        container = ctk.CTkFrame(self._ensure_rich_host())
        self._make_fullbleed(container)
        controller = WhiteboardController(container, root_app=self)
        container.whiteboard_controller = controller

        def _on_destroy(_event=None, ctrl=controller):
            """Handle destroy."""
            try:
                ctrl.close()
            except Exception:
                pass

        container.bind("<Destroy>", _on_destroy, add="+")

        def factory(master):
            """Handle factory."""
            host_parent = master if master is not None else self._ensure_rich_host()
            frame = ctk.CTkFrame(host_parent)
            self._make_fullbleed(frame)
            ctrl = WhiteboardController(frame, root_app=self)
            frame.whiteboard_controller = ctrl
            frame.bind("<Destroy>", lambda _e=None, c=ctrl: c.close(), add="+")
            return frame

        self.add_tab(
            title or "Whiteboard",
            container,
            content_factory=factory,
            layout_meta={"kind": "whiteboard", "host": "rich", "controller": controller},
            activate=activate,
        )

    def open_world_map_tab(self, map_name=None, title=None):
        """Open a WorldMapPanel inside a new GM-screen tab."""
        # Mount heavy interactive views into a dedicated full-bleed host
        container = ctk.CTkFrame(self._ensure_rich_host())
        panel = WorldMapPanel(container)
        panel.pack(fill="both", expand=True)
        container.world_map_panel = panel
        if map_name:
            try:
                panel.load_map(map_name, push_history=False)
            except Exception:
                pass

        tab_title = title or (f"World Map: {map_name}" if map_name else "World Map")

        def factory(master, _name=map_name):
            """Handle factory."""
            host_parent = master if master is not None else self._ensure_rich_host()
            c = ctk.CTkFrame(host_parent)
            p = WorldMapPanel(c)
            p.pack(fill="both", expand=True)
            c.world_map_panel = p
            if _name:
                try:
                    p.load_map(_name, push_history=False)
                except Exception:
                    pass
            return c

        self.add_tab(
            tab_title,
            container,
            content_factory=factory,
            layout_meta={"kind": "world_map", "map_name": map_name, "host": "rich"},
        )

    def open_map_tool_tab(self, map_name=None, title=None):
        """Open the Map Tool (DisplayMapController) inside a GM-screen tab."""
        container = ctk.CTkFrame(self._ensure_rich_host())
        maps_wrapper = GenericModelWrapper("maps")
        controller = DisplayMapController(
            container,
            maps_wrapper,
            load_entity_template("maps"),
            root_app=self,
        )
        container.map_controller = controller
        if map_name and hasattr(controller, "open_map_by_name"):
            try:
                controller.open_map_by_name(map_name)
            except Exception:
                pass

        tab_title = title or (f"Map Tool: {map_name}" if map_name else "Map Tool")

        def factory(master, _name=map_name):
            """Handle factory."""
            host_parent = master if master is not None else self._ensure_rich_host()
            c = ctk.CTkFrame(host_parent)
            mw = GenericModelWrapper("maps")
            ctrl = DisplayMapController(
                c,
                mw,
                load_entity_template("maps"),
                root_app=self,
            )
            c.map_controller = ctrl
            if _name and hasattr(ctrl, "open_map_by_name"):
                try:
                    ctrl.open_map_by_name(_name)
                except Exception:
                    pass
            return c

        self.add_tab(
            tab_title,
            container,
            content_factory=factory,
            layout_meta={"kind": "map_tool", "map_name": map_name, "host": "rich"},
        )

    def open_scene_flow_tab(self, scenario_title=None, title=None):
        """Open the Scene Flow Viewer inside a GM-screen tab."""
        container = ctk.CTkFrame(self._ensure_rich_host())
        self._make_fullbleed(container)
        viewer = create_scene_flow_frame(container, scenario_title=scenario_title)
        viewer.pack(fill="both", expand=True)
        container.scene_flow_viewer = viewer

        tab_title = title or (f"Scene Flow: {scenario_title}" if scenario_title else "Scene Flow")

        def factory(master, _title=scenario_title):
            """Handle factory."""
            host_parent = master if master is not None else self._ensure_rich_host()
            c = ctk.CTkFrame(host_parent)
            self._make_fullbleed(c)
            v = create_scene_flow_frame(c, scenario_title=_title)
            v.pack(fill="both", expand=True)
            c.scene_flow_viewer = v
            return c

        self.add_tab(
            tab_title,
            container,
            content_factory=factory,
            layout_meta={"kind": "scene_flow", "scenario_title": scenario_title, "host": "rich"},
        )


    def open_loot_generator_tab(self, title=None):
        """Open the embedded loot generator inside the GM screen."""
        template = self.templates.get("Objects")
        frame = LootGeneratorPanel(
            self.content_area,
            object_wrapper=self.wrappers.get("Objects"),
            template=template,
        )

        def factory(master):
            """Handle factory."""
            return LootGeneratorPanel(
                master,
                object_wrapper=self.wrappers.get("Objects"),
                template=self.templates.get("Objects"),
            )

        self.add_tab(
            title or "Loot Generator",
            frame,
            content_factory=factory,
            layout_meta={"kind": "loot_generator"},
        )

    def open_handouts_tab(self, title=None):
        """Open the handouts page inside the GM screen."""
        frame = GMTableHandoutsPage(
            self._ensure_rich_host(),
            scenario_name=self.scenario_name,
            scenario_item=self.scenario,
            wrappers=self.wrappers,
            map_wrapper=self.map_wrapper,
        )

        def factory(master):
            """Handle factory."""
            return GMTableHandoutsPage(
                master if master is not None else self._ensure_rich_host(),
                scenario_name=self.scenario_name,
                scenario_item=self.scenario,
                wrappers=self.wrappers,
                map_wrapper=self.map_wrapper,
            )

        self.add_tab(
            title or "Handouts",
            frame,
            content_factory=factory,
            layout_meta={"kind": "handouts", "host": "rich"},
        )

    def open_random_tables_tab(self, title=None, initial_state=None):
        """Open the random tables panel inside the GM screen."""

        tab_name = title or "Random Tables"
        panel = RandomTablesPanel(self.content_area, initial_state=initial_state)

        def factory(master, tab_ref=tab_name):
            """Handle factory."""
            state = None
            info = self.tabs.get(tab_ref)
            frame = info.get("content_frame") if info else None
            if frame is not None and hasattr(frame, "get_state"):
                state = frame.get_state()
            return RandomTablesPanel(master, initial_state=state)

        self.add_tab(
            tab_name,
            panel,
            content_factory=factory,
            layout_meta={"kind": "random_tables", "state": panel.get_state()},
        )

    def open_puzzle_display_tab(self, puzzle_item=None, title=None):
        """Open the puzzle display window inside the GM screen."""
        if puzzle_item is None:
            puzzle_item = {}
        name = puzzle_item.get("Name") or title or "Puzzle Display"
        frame = create_puzzle_display_frame(self.content_area, puzzle_item, scrollable=False)
        self.add_tab(
            title or name,
            frame,
            content_factory=lambda master: create_puzzle_display_frame(
                master,
                puzzle_item,
                scrollable=False,
            ),
            layout_meta={
                "kind": "puzzle_display",
                "puzzle_name": puzzle_item.get("Name") or "",
                "title": title or name,
            },
        )

    def open_plot_twist_popup(self):
        """Open plot twist popup."""
        host = self.winfo_toplevel()
        popup = ctk.CTkToplevel(host)
        popup.title("Plot Twists")
        popup.geometry("480x320")
        popup.transient(host)
        popup.grab_set()
        panel = PlotTwistPanel(popup)
        panel.pack(fill="both", expand=True, padx=12, pady=12)


    def reattach_tab(self, name):
        """Handle reattach tab."""
        log_info(f"Reattaching tab: {name}", func_name="GMScreenView.reattach_tab")
        print(f"[REATTACH] Start reattaching tab: {name}")
        # If the tab isn't marked detached, skip
        if not self.tabs[name].get("detached", False):
            print(f"[REATTACH] Tab '{name}' is not detached.")
            return

        # Retrieve the detached window and its content frame
        detached_window = self.tabs[name]["window"]
        current_frame = self.tabs[name]["content_frame"]
        self._teardown_tab_content(current_frame)

        # Preserve graph state if present
        saved_state = None
        if hasattr(current_frame, "graph_editor") and hasattr(current_frame.graph_editor, "get_state"):
            saved_state = current_frame.graph_editor.get_state()
        if hasattr(current_frame, "scenario_graph_editor") and hasattr(current_frame.scenario_graph_editor, "get_state"):
            saved_state = current_frame.scenario_graph_editor.get_state()

        # Special case: Note tabs store their text
        current_text = ""
        if name.startswith("Note") and hasattr(current_frame, "text_box"):
            current_text = current_frame.text_box.get("1.0", "end-1c")

        # Destroy the detached window
        if detached_window:
            detached_window.destroy()
            print("[REATTACH] Detached window destroyed.")

        # Recreate or reuse the content frame
        factory = self.tabs[name].get("factory")
        if factory is None:
            # Handle the branch where factory is missing.
            new_frame = current_frame
        else:
            # Determine host for this tab
            host_kind = (self.tabs[name].get("meta") or {}).get("host") or "scroll"
            parent = None
            if host_kind == "rich":
                parent = self._ensure_rich_host()
            else:
                parent = getattr(self.content_area, "_scrollable_frame", self.content_area)

            # Note tabs get their text back
            if name.startswith("Note"):
                new_frame = factory(parent, initial_text=current_text)
            else:
                new_frame = factory(parent)

            # Restore NPC-graph state, ensuring the canvas background exists first
            if saved_state and hasattr(new_frame, "graph_editor") and hasattr(new_frame.graph_editor, "set_state"):
                ce = new_frame.graph_editor.canvas
                ce.update_idletasks()
                # Synthesize a Configure event to lay down the background
                cfg = type("E", (), {
                    "width":  ce.winfo_width(),
                    "height": ce.winfo_height()
                })()
                new_frame.graph_editor._on_canvas_configure(cfg)
                new_frame.graph_editor.set_state(saved_state)

            # Restore scenario-graph state if present
            if saved_state and hasattr(new_frame, "scenario_graph_editor") and hasattr(new_frame.scenario_graph_editor, "set_state"):
                new_frame.scenario_graph_editor.set_state(saved_state)

        # Pack and finalize
        new_frame.pack(fill="both", expand=True)
        self.tabs[name]["content_frame"] = new_frame
        self.tabs[name]["detached"] = False
        self.tabs[name]["window"] = None
        self.show_tab(name)
        # Reorder any remaining detached windows
        if hasattr(self, "reorder_detached_windows"):
            self.reorder_detached_windows()
        print(f"[REATTACH] Tab '{name}' reattached successfully.")



    def close_tab(self, name):
        """Close tab."""
        if len(self.tabs) == 1:
            return
        if name in self._command_deck_buttons:
            self._command_deck_buttons[name].destroy()
            self._command_deck_buttons.pop(name, None)
        if name in self.tab_order:
            self.tab_order.remove(name)
        if self.tabs[name].get("detached", False) and self.tabs[name].get("window"):
            self.tabs[name]["window"].destroy()
        self._teardown_tab_content(self.tabs[name].get("content_frame"))
        self.tabs[name]["button_frame"].destroy()
        self.tabs[name]["content_frame"].destroy()
        del self.tabs[name]
        if self.current_tab == name and self.tabs:
            self.show_tab(next(iter(self.tabs)))
        self.reposition_add_button()
        self._refresh_command_deck()

    def reposition_add_button(self):
        """Handle reposition add button."""
        self.add_button.pack_forget()
        self.random_button.pack_forget()
        if self.tab_order:
            last = self.tabs[self.tab_order[-1]]["button_frame"]
            self.add_button.pack(side="left", padx=2, pady=5, after=last)
            self.random_button.pack(side="left", padx=2, pady=5, after=self.add_button)
        else:
            self.add_button.pack(side="left", padx=2, pady=5)
            self.random_button.pack(side="left", padx=2, pady=5)
    
    def _add_random_entity(self):
        """Internal helper for add random entity."""
        log_info("Adding random entity to GM screen", func_name="GMScreenView._add_random_entity")
        """Pick a random NPC, Creature, Object, Information or Clue and open it.
        """
        types = ["NPCs", "Creatures", "Bases", "Objects", "Informations", "Clues", "Puzzles"]
        random.shuffle(types)

        for etype in types:
            # Process each etype from types.
            wrapper = self.wrappers.get(etype)
            if not wrapper:
                continue
            items = wrapper.load_items()
            if not items:
                continue

            key = "Title" if etype in ("Scenarios", "Informations") else "Name"
            choice = random.choice(items)
            name = choice.get(key)
            if name:
                self.open_entity_tab(etype, name)
                return

        panel, tab_name = self._get_or_open_random_tables_panel()
        if not panel:
            messagebox.showinfo("Random Choice", "No entities or random tables are available to roll.")
            return

        result = panel.roll_random_table()
        if result:
            self.show_tab(tab_name)
            messagebox.showinfo(
                "Random Tables",
                f"{result.get('table')} ({result.get('roll')}): {result.get('result')}",
            )

    def _get_or_open_random_tables_panel(self):
        """Return or open random tables panel."""
        for name, tab in self.tabs.items():
            # Process each (name, tab) from tabs.items().
            meta = tab.get("meta") or {}
            if meta.get("kind") != "random_tables":
                continue
            frame = tab.get("content_frame")
            if frame is None and tab.get("factory"):
                frame = tab["factory"](self.content_area)
                tab["content_frame"] = frame
            return frame, name

        self.open_random_tables_tab()
        name = self.tab_order[-1] if self.tab_order else None
        frame = self.tabs.get(name, {}).get("content_frame") if name else None
        return frame, name

    def _reset_scrollable_widget_position(self, widget, *, schedule_after_idle=True):
        """Reset scrollable widget position."""
        if widget is None:
            return
        try:
            widget.update_idletasks()
        except Exception:
            return

        candidates = [widget]
        inner = getattr(widget, "_scrollable_frame", None)
        canvas = getattr(widget, "_parent_canvas", None)
        scroll_canvas = getattr(widget, "_scroll_canvas", None)
        scrollbar = getattr(widget, "_scrollbar", None)
        if inner is not None:
            # Handle the branch where inner is available.
            candidates.append(inner)
            inner_canvas = getattr(inner, "_parent_canvas", None)
            inner_scroll_canvas = getattr(inner, "_scroll_canvas", None)
            if inner_canvas is not None:
                candidates.append(inner_canvas)
            if inner_scroll_canvas is not None:
                candidates.append(inner_scroll_canvas)
        if canvas is not None:
            candidates.append(canvas)
        if scroll_canvas is not None:
            candidates.append(scroll_canvas)
        if scrollbar is not None:
            candidates.append(scrollbar)

        real_canvas = scroll_canvas or canvas
        if real_canvas is not None and real_canvas not in candidates:
            candidates.append(real_canvas)

        def _apply_reset():
            """Apply reset."""
            if real_canvas is not None:
                # Handle the branch where real canvas is available.
                try:
                    # Keep reset resilient if this step fails.
                    bbox = real_canvas.bbox("all")
                    if bbox is not None:
                        real_canvas.configure(scrollregion=bbox)
                except Exception:
                    pass
                try:
                    real_canvas.yview_moveto(0.0)
                except Exception:
                    pass
            for candidate in candidates:
                try:
                    # Keep reset resilient if this step fails.
                    if hasattr(candidate, "yview_moveto"):
                        candidate.yview_moveto(0.0)
                except Exception:
                    pass

        _apply_reset()
        if schedule_after_idle:
            self.after_idle(lambda w=widget: self._reset_scrollable_widget_position(w, schedule_after_idle=False))

    def _reset_tab_scroll_state(self, tab_name):
        """Reset tab scroll state."""
        tab = self.tabs.get(tab_name) or {}
        frame = tab.get("content_frame")
        if frame is None:
            return
        self._reset_scrollable_widget_position(frame)
        self.after_idle(lambda f=frame: self._reset_scrollable_widget_position(f))
        self.after(25, lambda f=frame: self._reset_scrollable_widget_position(f))

    def show_tab(self, name):
        """Show tab."""
        log_info(f"Showing tab: {name}", func_name="GMScreenView.show_tab")
        # Hide content for the current tab if it's not detached.
        if self.current_tab and self.current_tab in self.tabs:
            # Handle the branch where current tab is set and current tab is in tabs.
            if not self.tabs[self.current_tab]["detached"]:
                self.tabs[self.current_tab]["content_frame"].pack_forget()
            self._apply_tab_visual_state(self.current_tab, is_active=False)
        self.current_tab = name
        self._apply_tab_visual_state(name, is_active=True)
        self._motion.pulse_widget(self.tabs.get(name, {}).get("button_frame"), duration_ms=160)
        self._refresh_command_deck()
        # Only pack the content into the main content area if the tab is not detached.
        if not self.tabs[name]["detached"]:
            # Handle the branch where not tabs[name]['detached'].
            tab = self.tabs[name]
            target_host = (tab.get("meta") or {}).get("host") or "scroll"
            # Toggle which host is visible
            if target_host == "rich":
                # Hide scroll area and show rich host
                try:
                    self.content_area.pack_forget()
                except Exception:
                    pass
                host = self._ensure_rich_host()
                host.pack(fill="both", expand=True)
            else:
                # Show scroll area and hide rich host
                try:
                    # Keep tab resilient if this step fails.
                    if getattr(self, "_rich_host", None) and self._rich_host.winfo_exists():
                        self._rich_host.pack_forget()
                except Exception:
                    pass
                self.content_area.pack(fill="both", expand=True)

            frame = tab["content_frame"]
            frame.pack(fill="both", expand=True)
            self._reset_tab_scroll_state(name)
            self._request_active_tab_layout_settle()

    def _tab_status(self, name, is_active=False):
        """Return status for a tab."""
        if is_active:
            return "active"
        tab = self.tabs.get(name, {})
        if tab.get("detached"):
            return "alert"
        return "stale"

    def _tab_status_dot(self, status):
        """Return dot icon from status."""
        if status == "active":
            return "🟢"
        if status == "alert":
            return "🔴"
        return "🟡"

    def _build_tab_text(self, name, is_active=False):
        """Compose tab text with icon, short label and status dot."""
        tab = self.tabs.get(name, {})
        meta = tab.get("meta", {})
        icon = meta.get("icon") or tab_icon_for_name(name)
        short_label = meta.get("short_label") or tab_short_label(name)
        status = self._tab_status(name, is_active=is_active)
        status_dot = self._tab_status_dot(status)
        return f"{icon} {short_label} {status_dot}"

    def _apply_tab_visual_state(self, name, is_active=False):
        """Apply variant styling to tab widgets."""
        tab = self.tabs.get(name)
        if not tab:
            return
        meta = tab.get("meta", {})
        variant = TAB_VARIANTS.get(meta.get("category"), TAB_VARIANTS["default"])
        status = self._tab_status(name, is_active=is_active)
        border = variant["active_border"] if is_active else variant["inactive_border"]
        frame_fg = variant["active_fg"] if is_active else variant["inactive_fg"]
        text_color = self._palette["text"] if is_active else self._palette["muted_text"]
        tab["button_frame"].configure(
            fg_color=frame_fg,
            border_color=border,
            border_width=2 if is_active else 1,
            corner_radius=16 if is_active else 10,
        )
        tab["button"].configure(
            text=self._build_tab_text(name, is_active=is_active),
            height=20 if is_active else 15,
            hover_color=variant["active_hover"] if is_active else variant["inactive_hover"],
            text_color=text_color,
            font=ctk.CTkFont(size=14 if is_active else 12, weight="bold" if is_active else "normal"),
        )
        tab["pin_button"].configure(
            text="📌" if meta.get("pinned") else "📍",
            hover_color=variant["active_hover"] if is_active else variant["inactive_hover"],
            text_color=text_color,
        )
        tab["detach_button"].configure(
            hover_color=variant["active_hover"] if is_active else variant["inactive_hover"],
        )
        if status == "alert":
            tab["button_frame"].configure(border_color="#EF4444")

    def toggle_tab_pin(self, name):
        """Pin or unpin a tab to the command deck."""
        if name not in self.tabs:
            return
        meta = self.tabs[name].setdefault("meta", {})
        meta["pinned"] = not bool(meta.get("pinned"))
        self._apply_tab_visual_state(name, is_active=(self.current_tab == name))
        self._refresh_command_deck()

    def _refresh_command_deck(self):
        """Refresh command deck buttons for pinned tabs."""
        for button in self._command_deck_buttons.values():
            button.destroy()
        self._command_deck_buttons = {}
        pinned_names = [tab_name for tab_name in self.tab_order if self.tabs.get(tab_name, {}).get("meta", {}).get("pinned")]
        if not pinned_names:
            self.command_deck_label.configure(text="Command Deck (none)")
            return
        self.command_deck_label.configure(text="Command Deck")
        for tab_name in pinned_names[:6]:
            tab = self.tabs.get(tab_name, {})
            meta = tab.get("meta", {})
            label = f"{meta.get('icon', '◻')} {meta.get('short_label', tab_name)}"
            button = ctk.CTkButton(
                self.command_deck,
                text=label,
                height=26,
                width=108,
                fg_color=self._palette["surface_overlay"],
                hover_color=self._palette["accent_hover"],
                text_color=self._palette["text"],
                command=lambda n=tab_name: self.show_tab(n),
            )
            button.pack(side="left", padx=2)
            self._command_deck_buttons[tab_name] = button

    def add_new_tab(self):
        """Handle add new tab."""
        log_info("Opening entity selection for new tab", func_name="GMScreenView.add_new_tab")
        self._show_add_menu()

    def _show_add_menu(self):
        """Show add menu."""
        button = self.add_button
        self._motion.pulse_widget(button, duration_ms=120)
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        try:
            # Keep add menu resilient if this step fails.
            self._add_menu.tk_popup(x, y)
        finally:
            self._add_menu.grab_release()

    def open_selection_window(self, entity_type, popup=None):
        """Open selection window."""
        log_info(f"Opening selection window for {entity_type}", func_name="GMScreenView.open_selection_window")
        if popup:
            popup.destroy()
        if entity_type == "Note Tab":
            # Handle the branch where entity_type == 'Note Tab'.
            self.add_tab(
                f"Note {len(self.tabs) + 1}",
                self.create_note_frame(),
                content_factory=lambda master, initial_text="": self.create_note_frame(master=master, initial_text=initial_text),
                layout_meta={"kind": "note"},
            )
            return
        elif entity_type == "World Map":
            # Handle the branch where entity_type == 'World Map'.
            self.open_world_map_tab()
            return
        elif entity_type == "Campaign Dashboard":
            # Handle the branch where entity_type == 'Campaign Dashboard'.
            self.open_campaign_dashboard_tab()
            return
        elif entity_type == "Map Tool":
            # Handle the branch where entity_type == 'Map Tool'.
            self.open_map_tool_tab()
            return
        elif entity_type == "Scene Flow":
            # Handle the branch where entity_type == 'Scene Flow'.
            self.open_scene_flow_tab()
            return
        elif entity_type == "Image Library":
            host = self.winfo_toplevel()
            opener = getattr(host, "open_image_library_browser", None) if host is not None else None
            if callable(opener):
                opener()
            else:
                messagebox.showerror("Image Library", "Image library is unavailable from this window.")
            return
        elif entity_type == "Handouts":
            self.open_handouts_tab()
            return
        elif entity_type == "Loot Generator":
            # Handle the branch where entity_type == 'Loot Generator'.
            self.open_loot_generator_tab()
            return
        elif entity_type == "Whiteboard":
            # Handle the branch where entity_type == 'Whiteboard'.
            self.open_whiteboard_tab()
            return
        elif entity_type == "Random Tables":
            # Handle the branch where entity_type == 'Random Tables'.
            self.open_random_tables_tab()
            return
        elif entity_type == "Puzzle Display":
            # Handle the branch where entity_type == 'Puzzle Display'.
            self._select_puzzle_for_display()
            return
        elif entity_type == "Plot Twists":
            # Handle the branch where entity_type == 'Plot Twists'.
            self.open_plot_twist_popup()
            return
        elif entity_type == "Character Graph":
            # Handle the branch where entity_type == 'Character Graph'.
            host_parent = self._ensure_rich_host()
            self.add_tab(
                "Character Graph",
                self.create_character_graph_frame(master=host_parent),
                content_factory=lambda master=host_parent: self.create_character_graph_frame(master),
                layout_meta={"kind": "character_graph", "host": "rich"}
            )

            return
        elif entity_type == "Scenario Graph Editor":
            host_parent = self._ensure_rich_host()
            self.add_tab(
                "Scenario Graph Editor",
                self.create_scenario_graph_frame(master=host_parent),
                content_factory=lambda master=host_parent: self.create_scenario_graph_frame(master),
                layout_meta={"kind": "scenario_graph", "host": "rich"}
            )
            return

        model_wrapper = self.wrappers[entity_type]
        template = self.templates[entity_type]
        selection_popup = ctk.CTkToplevel(self)
        selection_popup.title(f"Select {entity_type}")
        selection_popup.geometry("1200x800")
        selection_popup.transient(self.winfo_toplevel())
        selection_popup.grab_set()
        selection_popup.focus_force()
        # Use the new GenericListSelectionView (import it accordingly)
        view = GenericListSelectionView(selection_popup, entity_type, model_wrapper, template, self.open_entity_tab)

        view.pack(fill="both", expand=True)

    def _select_puzzle_for_display(self) -> None:
        """Select puzzle for display."""
        selection_popup = ctk.CTkToplevel(self)
        selection_popup.title("Select Puzzle")
        selection_popup.geometry("1200x800")
        selection_popup.transient(self.winfo_toplevel())
        selection_popup.grab_set()
        selection_popup.focus_force()

        def _open_puzzle_tab(_entity_type: str, name: str) -> None:
            """Open puzzle tab."""
            selection_popup.destroy()
            wrapper = self.wrappers.get("Puzzles")
            items = wrapper.load_items() if wrapper else []
            puzzle_item = next((i for i in items if i.get("Name") == name), None)
            if puzzle_item is None:
                messagebox.showerror("Error", f"Puzzle '{name}' not found.")
                return
            self.open_puzzle_display_tab(puzzle_item, title=f"Puzzle Display: {name}")

        view = GenericListSelectionView(
            selection_popup,
            "Puzzles",
            self.wrappers["Puzzles"],
            self.templates["Puzzles"],
            _open_puzzle_tab,
        )
        view.pack(fill="both", expand=True)


    def open_entity_tab(self, entity_type, name):
        """Open entity tab."""
        log_info(f"Opening entity tab {entity_type}: {name}", func_name="GMScreenView.open_entity_tab")
        """
        Open a new tab for a specific entity with its details.

        Args:
            entity_type (str): The type of entity (e.g., 'Scenarios', 'NPCs', 'Creatures').
            name (str): The name or title of the specific entity to display.
        
        Raises:
            messagebox.showerror: If the specified entity cannot be found in the wrapper.

        Creates a new tab with the entity's details using a shared factory function,
        and provides a mechanism to recursively open related entities.
        """
        existing = self._find_existing_entity_tab(entity_type, name)
        if existing:
            self._focus_existing_tab(existing)
            return

        wrapper = self.map_wrapper if entity_type == "Maps" else self.wrappers.get(entity_type)
        if wrapper is None:
            messagebox.showerror("Error", f"Entity type '{entity_type}' is not available.")
            return

        items = wrapper.load_items()
        key = "Title" if entity_type in {"Scenarios", "Informations"} else "Name"
        item = next((i for i in items if i.get(key) == name), None)
        if not item:
            singular = entity_type[:-1] if entity_type.endswith("s") else entity_type
            messagebox.showerror("Error", f"{singular} '{name}' not found.")
            return
        # Use the shared factory function and pass self.open_entity_tab as the callback.
        factory = lambda master: create_entity_detail_frame(
            entity_type,
            item,
            master=master,
            open_entity_callback=self.open_entity_tab,
        )
        needs_scroll = entity_type != "Scenarios"
        frame = self._build_hidden_tab_content(self.content_area, factory, scrollable=needs_scroll)

        self.add_tab(
            name,
            frame,
            content_factory=lambda master: self._build_hidden_tab_content(master, factory, scrollable=needs_scroll),
            layout_meta={
                "kind": "entity",
                "entity_type": entity_type,
                "entity_name": name,
            },
        )

    def open_campaign_dashboard_tab(self, title="Campaign Dashboard"):
        """Open campaign dashboard tab."""
        existing_tab = next(
            (
                tab_name
                for tab_name, tab in self.tabs.items()
                if (tab.get("meta") or {}).get("kind") == "campaign_dashboard"
            ),
            None,
        )
        if existing_tab:
            self.show_tab(existing_tab)
            return

        factory = lambda master: CampaignDashboardPanel(
            master,
            wrappers=self.wrappers,
            open_entity_callback=self.open_entity_tab,
        )
        frame = self._build_hidden_tab_content(self.content_area, factory, scrollable=True)
        self.add_tab(
            title,
            frame,
            content_factory=lambda master: self._build_hidden_tab_content(master, factory, scrollable=True),
            layout_meta={"kind": "campaign_dashboard"},
        )

    def _focus_existing_tab(self, tab_name):
        """Internal helper for focus existing tab."""
        if tab_name not in self.tabs:
            return
        self.show_tab(tab_name)
        tab_info = self.tabs.get(tab_name, {})
        if tab_info.get("detached"):
            # Handle the branch where tab_info.get('detached').
            window = tab_info.get("window")
            if window and window.winfo_exists():
                try:
                    window.deiconify()
                    window.lift()
                    window.focus_force()
                except Exception:
                    pass

    def _find_existing_entity_tab(self, entity_type, entity_name):
        """Find existing entity tab."""
        for tab_name, tab_info in self.tabs.items():
            # Process each (tab_name, tab_info) from tabs.items().
            meta = tab_info.get("meta") or {}
            if (
                meta.get("kind") == "entity"
                and meta.get("entity_type") == entity_type
                and meta.get("entity_name") == entity_name
            ):
                return tab_name
        return None

    def create_scenario_graph_frame(self, master=None):
        """Create scenario graph frame."""
        log_info(f"Creating scenario graph frame", func_name="GMScreenView.create_scenario_graph_frame")
        if master is None:
            master = self.content_area
        # Allow frame to naturally expand to fill available space
        frame = ctk.CTkFrame(master)
        # Create a ScenarioGraphEditor widget.
        # Note: Ensure that self.wrappers contains "Scenarios", "NPCs", and "Places" as required.
        scenario_graph_editor = ScenarioGraphEditor(
            frame,
            self.wrappers["Scenarios"],
            self.wrappers["NPCs"],
            self.wrappers["Creatures"],
            self.wrappers["Places"]
        )
        scenario_graph_editor.pack(fill="both", expand=True)
        frame.scenario_graph_editor = scenario_graph_editor  # Optional: store a reference for state management.
        return frame

    def create_entity_frame(self, entity_type, entity, master=None):
        """Create entity frame."""
        log_info(f"Creating entity frame for {entity_type}: {entity.get('Name') or entity.get('Title')}", func_name="GMScreenView.create_entity_frame")
        if master is None:
            master = self.content_area
        frame = create_entity_detail_frame(
            entity_type,
            entity,
            master=master,
            open_entity_callback=self.open_entity_tab,
        )
        portrait_images = getattr(frame, "portrait_images", {})
        if portrait_images:
            self.portrait_images.update(portrait_images)
        portrait_label = getattr(frame, "portrait_label", None)
        if portrait_label is not None:
            frame.portrait_label = portrait_label
        return frame
    
    def insert_text(self, parent, header, content):
        """Handle insert text."""
        label = ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold"))
        label.pack(anchor="w", padx=10)
        box = ctk.CTkTextbox(parent, wrap="word", height=80)
        # Ensure content is a plain string.
        if isinstance(content, dict):
            content = content.get("text", "")
        elif isinstance(content, list):
            content = " ".join(map(str, content))
        else:
            content = str(content)
        # For debugging, you can verify:
        # print("DEBUG: content =", repr(content))

        # Override the insert method to bypass the CTkTextbox wrapper.
        box.insert = box._textbox.insert
        # Now use box.insert normally.
        box.insert("1.0", content)

        box.configure(state="disabled")
        box.pack(fill="x", padx=10, pady=5)
        
    def insert_longtext(self, parent, header, content):
        """Handle insert longtext."""
        ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold")).pack(anchor="w", padx=10)
        formatted_text = format_multiline_text(content, max_length=2000)
        box = ctk.CTkTextbox(parent, wrap="word", height=120)
        box.insert("1.0", formatted_text)
        box.configure(state="disabled")
        box.pack(fill="x", padx=10, pady=5)

    def insert_links(self, parent, header, items, linked_type):
        """Handle insert links."""
        ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold")).pack(anchor="w", padx=10)
        for item in items:
            label = ctk.CTkLabel(parent, text=item, text_color="#00BFFF", cursor="hand2")
            label.pack(anchor="w", padx=10)
            label.bind("<Button-1>", partial(self._on_link_clicked, linked_type, item))

    def _on_link_clicked(self, linked_type, item, event=None):
        """Handle link clicked."""
        self.open_entity_tab(linked_type, item)

    def save_note_to_file(self, note_frame, default_name):
        """Save note to file."""
        file_path = filedialog.asksaveasfilename(
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt")],
            title="Save Note As"
        )
        if not file_path:
            return
        content = note_frame.text_box.get("1.0", "end-1c")
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
        messagebox.showinfo("Saved", f"Note saved to {file_path}")
    
    def create_character_graph_frame(self, master=None):
        """Create character graph frame."""
        if master is None:
            master = self.content_area
        frame = ctk.CTkFrame(master)
        graph_editor = CharacterGraphEditor(
            frame,
            self.wrappers["NPCs"],
            self.wrappers["PCs"],
            self.wrappers["Factions"],
            background_style="corkboard",
        )
        graph_editor.pack(fill="both", expand=True)
        frame.graph_editor = graph_editor  # Save a reference for state management
        return frame
    
    def reorder_detached_windows(self):
        """Handle reorder detached windows."""
        screen_width = self.winfo_screenwidth()
        margin = 10  # space between windows and screen edge
        current_x = margin
        current_y = margin
        max_row_height = 0

        for name, tab in self.tabs.items():
            if tab.get("detached") and tab.get("window") is not None:
                # Handle the branch where tab.get('detached') and tab.get('window') is available.
                window = tab["window"]
                window.update_idletasks()
                req_width = window.winfo_reqwidth()
                req_height = window.winfo_reqheight()
                # If adding this window would go beyond screen width, wrap to next line
                if current_x + req_width + margin > screen_width:
                    current_x = margin
                    current_y += max_row_height + margin
                    max_row_height = 0
                window.geometry(f"{req_width}x{req_height}+{current_x}+{current_y}")
                current_x += req_width + margin
                if req_height > max_row_height:
                    max_row_height = req_height
    def destroy(self):
        """Handle destroy."""
        # remove our global Ctrl+F handler
        root = self.winfo_toplevel()
        root.unbind_all("<Control-F>")
        # now destroy as usual
        super().destroy()
