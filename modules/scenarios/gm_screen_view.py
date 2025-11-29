import customtkinter as ctk
import tkinter as tk
import os
import json
from datetime import datetime
from tkinter import filedialog, messagebox
from PIL import Image
from functools import partial
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.template_loader import load_template as load_entity_template
from modules.helpers.text_helpers import format_multiline_text
from customtkinter import CTkLabel, CTkImage
from modules.generic.entity_detail_factory import create_entity_detail_frame
from modules.npcs.npc_graph_editor import NPCGraphEditor
from modules.pcs.pc_graph_editor import PCGraphEditor
from modules.scenarios.scenario_graph_editor import ScenarioGraphEditor
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.config_helper import ConfigHelper
import random
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
from modules.ui.chatbot_dialog import (
    open_chatbot_dialog,
    _DEFAULT_NAME_FIELD_OVERRIDES as CHATBOT_NAME_OVERRIDES,
)
from modules.objects.loot_generator_panel import LootGeneratorPanel
from modules.scenarios.random_tables_panel import RandomTablesPanel
from modules.whiteboard.controllers.whiteboard_controller import WhiteboardController

log_module_import(__name__)

PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
MAX_PORTRAIT_SIZE = (64, 64)  # Thumbnail size for lists
DEFAULT_MAP_THUMBNAIL_SIZE = (200, 140)

@log_methods
class GMScreenView(ctk.CTkFrame):
    def __init__(self, master, scenario_item, *args, initial_layout=None, layout_manager=None, **kwargs):
        super().__init__(master, *args, **kwargs)
        # Persistent cache for portrait images
        self.portrait_images = {}
        self.scenario = scenario_item
        self.scenario_name = scenario_item.get("Title") or scenario_item.get("Name") or "Scenario"
        self.layout_manager = layout_manager or GMScreenLayoutManager()
        self._pending_initial_layout = initial_layout
        self._scene_completion_state = {}
        self._scene_vars = {}
        self._scene_order = []
        self._active_scene_key = None
        self._note_cache = ""
        self.note_widget = None
        self._note_editor_window = None
        self._context_menu = None
        self._edit_menu_label = "Edit Entity"
        self._state_loaded = False
        self._scene_metadata = {}

        self._load_persisted_state()

        # Track transient key bindings when this view owns its toplevel window
        self._bound_shortcut_owner = None
        self._ctrl_f_binding = None
        self._ctrl_F_binding = None
        self._ctrl_shift_c_binding = None
        self._ctrl_shift_C_binding = None
        self._ctrl_shift_c_release_binding = None
        self._ctrl_shift_C_release_binding = None
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
            "Scenarios": GenericModelWrapper("scenarios"),
            "Places": GenericModelWrapper("places"),
            "NPCs": GenericModelWrapper("npcs"),
            "PCs": GenericModelWrapper("pcs"),
            "Factions": GenericModelWrapper("factions"),
            "Creatures": GenericModelWrapper("creatures"),
            "Clues": GenericModelWrapper("clues"),
            "Informations": GenericModelWrapper("informations"),
            "Objects": GenericModelWrapper("objects"),
            "Books": GenericModelWrapper("books"),
        }

        # Dedicated map store for thumbnails and quick lookup
        self.map_wrapper = GenericModelWrapper("maps")
        self._map_records = self._load_map_records()
        self._map_thumbnail_cache = {}
        self._map_thumbnail_size = DEFAULT_MAP_THUMBNAIL_SIZE

        self.templates = {
            "Scenarios": load_entity_template("scenarios"),
            "Places": load_entity_template("places"),
            "NPCs": load_entity_template("npcs"),
            "PCs": load_entity_template("pcs"),
            "Factions": load_entity_template("factions"),
            "Creatures": load_entity_template("creatures"),
            "Clues": load_entity_template("clues"),
            "Informations": load_entity_template("informations"),
            "Objects": load_entity_template("objects"),
        }

        self.tabs = {}
        self.current_tab = None
        self.tab_order = []                  # ← new: keeps track of left-to-right order
        self.dragging = None                 # ← new: holds (tab_name, start_x)
        self.current_layout_name = None

        # A container to hold both the scrollable tab area and the plus button
        self.tab_bar_container = ctk.CTkFrame(self, height=60)
        self.tab_bar_container.pack(side="top", fill="x")

        # The scrollable canvas for tabs
        self.tab_bar_canvas = ctk.CTkCanvas(self.tab_bar_container, height=40, highlightthickness=0, bg="#2B2B2B")
        self.tab_bar_canvas.pack(side="top", fill="x", expand=True)

        # Horizontal scrollbar at the bottom alongside layout status
        self.tab_bar_bottom = ctk.CTkFrame(self.tab_bar_container)
        self.tab_bar_bottom.pack(side="bottom", fill="x")

        self.h_scrollbar = ctk.CTkScrollbar(
            self.tab_bar_bottom,
            orientation="horizontal",
            command=self.tab_bar_canvas.xview
        )
        self.h_scrollbar.pack(side="left", fill="x", expand=True)

        # The actual frame that holds the tab buttons
        self.tab_bar = ctk.CTkFrame(self.tab_bar_canvas, height=40)
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
            width=40,
            command=self.add_new_tab
        )
        
        self.random_button = ctk.CTkButton(
            self.tab_bar,
            text="?",
            width=40,
            command=self._add_random_entity
        )
        self.random_button.pack(side="left", padx=2, pady=5)
        self.add_button.pack(side="left", padx=2, pady=5)

        self._add_menu_options = [
            "World Map",
            "Map Tool",
            "Scene Flow",
            "Loot Generator",
            "Whiteboard",
            "Random Tables",
            "Factions",
            "Places",
            "NPCs",
            "PCs",
            "Creatures",
            "Scenarios",
            "Clues",
            "Informations",
            "Note Tab",
            "NPC Graph",
            "PC Graph",
            "Scenario Graph Editor",
            "separator",
            ("Save Layout", self._prompt_save_layout),
            ("Load Layout", self._open_load_layout_dialog),
            ("Open Chatbot", self.open_chatbot),
        ]
        self._add_menu = self._build_add_menu()
        self.layout_status_label = ctk.CTkLabel(self.tab_bar_bottom, text="")
        self.layout_status_label.pack(side="right", padx=8, pady=5)

        # Main content area for scenario details
        self.content_area = ctk.CTkScrollableFrame(self)
        self.content_area.pack(fill="both", expand=True)
        self._initialize_context_menu()

        # Example usage: create the first tab from the scenario_item
        scenario_name = scenario_item.get("Title", "Unnamed Scenario")
        frame = create_entity_detail_frame("Scenarios", scenario_item, master=self.content_area, open_entity_callback=self.open_entity_tab)
        
        # Make sure the frame can get focus so the binding works
        self.focus_set()
        self.add_tab(
            scenario_name,
            frame,
            content_factory=lambda master: create_entity_detail_frame("Scenarios", scenario_item, master=master, open_entity_callback=self.open_entity_tab),
            layout_meta={
                "kind": "entity",
                "entity_type": "Scenarios",
                "entity_name": scenario_name,
            },
        )

        # Apply either the caller-specified layout or the scenario default
        self.after(100, self._apply_initial_layout)

    # -- Runtime sizing helpers -------------------------------------------------
    def _sync_fullbleed_now(self, container: ctk.CTkFrame | None):
        if not container or not container.winfo_exists():
            return
        try:
            viewport = self.content_area if hasattr(self, "content_area") else self
            viewport.update_idletasks()
            w = max(1, int(viewport.winfo_width()))
            h = max(1, int(viewport.winfo_height()))
            container.pack_propagate(False)
            container.configure(width=w, height=h)
        except Exception:
            pass

    def _build_add_menu(self):
        menu = tk.Menu(self, tearoff=0)
        for option in self._add_menu_options:
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
            name = str(item.get("Name") or "").strip()
            if not name:
                continue
            records[name] = item
        return records

    def _get_map_record(self, map_name):
        if not map_name:
            return None
        if map_name not in self._map_records:
            self._map_records = self._load_map_records()
        return self._map_records.get(map_name)

    def get_map_thumbnail(self, map_name, size=None):
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
        top = self._bound_shortcut_owner
        if not top:
            return
        try:
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
        if event is not None and event.widget is not self:
            return
        self._teardown_toplevel_shortcuts()

    def _persist_scene_state(self):
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
        # Ensure the view is still alive before creating child windows
        try:
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
        popup.title("Search Entities")
        popup.geometry("400x300")
        popup.transient(host)
        popup.grab_set()

        # 1) Search entry
        entry = ctk.CTkEntry(popup, placeholder_text="Type to search…")
        entry.pack(fill="x", padx=10, pady=(10, 5))
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
            listbox.delete(0, "end")
            search_map.clear()
            for entity_type, wrapper in self.wrappers.items():
                items = wrapper.load_items()
                key = "Title" if entity_type in ("Scenarios", "Informations") else "Name"
                for item in items:
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
            q = entry.get().strip().lower()
            populate(initial=False, query=q)
        entry.bind("<KeyRelease>", on_search)

        # 8) Selection handler
        def on_select(evt=None):
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

        # 10) Double-click also selects
        listbox.bind("<Double-Button-1>", on_select)

    def open_chatbot(self, event=None):
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
        base_path = os.path.dirname(__file__)
        template_path = os.path.join(base_path, "..", filename)
        with open(template_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        # Merge custom_fields if present so GM screen also shows user-defined fields
        fields = list(data.get("fields", []))
        if isinstance(data.get("custom_fields"), list):
            existing = {str(f.get("name", "")).strip() for f in fields}
            for f in data["custom_fields"]:
                try:
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

    def add_tab(self, name, content_frame, content_factory=None, layout_meta=None):
        log_info(f"Adding GM screen tab: {name}", func_name="GMScreenView.add_tab")
        tab_frame = ctk.CTkFrame(self.tab_bar)
        tab_frame.pack(side="left", padx=2, pady=5)

        tab_button = ctk.CTkButton(tab_frame, text=name, width=150,
                                   command=lambda: self.show_tab(name))
        tab_button.pack(side="left")

        close_button = ctk.CTkButton(tab_frame, text="❌", width=30,
                                     command=lambda: self.close_tab(name))
        close_button.pack(side="left")

        # Create the detach button and store its reference.
        detach_button = ctk.CTkButton(tab_frame,image=self.detach_icon, text="", width=50,
                                      command=lambda: self.toggle_detach_tab(name))
        detach_button.pack(side="left")

        portrait_label = getattr(content_frame, "portrait_label", None)
        self.tabs[name] = {
            "button_frame": tab_frame,
            "content_frame": content_frame,
            "button": tab_button,
            "detach_button": detach_button,
            "detached": False,
            "window": None,
            "portrait_label": portrait_label,
            "factory": content_factory,
            "meta": layout_meta or {},
        }

        content_frame.pack_forget()
        self.show_tab(name)
        # 1) append to order list
        self.tab_order.append(name)

        # collect ALL the widgets you need to drag
        draggable_widgets = (
            tab_frame,
            tab_button,
            close_button,
            detach_button
        )

        for w in draggable_widgets:
            w.bind("<Button-1>",        lambda e=None, n=name: self._on_tab_press(e, n))
            w.bind("<B1-Motion>",       lambda e=None, n=name: self._on_tab_motion(e, n))
            w.bind("<ButtonRelease-1>", lambda e=None, n=name: self._on_tab_release(e, n))

        self.reposition_add_button()
        # Ensure the new content is stretched to full viewport size
        try:
            self._sync_fullbleed_now(content_frame)
            self.after(60, lambda cf=content_frame: self._sync_fullbleed_now(cf))
        except Exception:
            pass

    def _teardown_tab_content(self, frame):
        if frame is None:
            return
        controller = getattr(frame, "whiteboard_controller", None)
        if controller and hasattr(controller, "close"):
            try:
                controller.close()
            except Exception:
                pass

    def _apply_initial_layout(self):
        layout_name = self._pending_initial_layout
        if not layout_name:
            layout_name = self.layout_manager.get_scenario_default(self.scenario_name)
        if not layout_name:
            return
        self.load_layout(layout_name, silent=True)

    def _initialize_context_menu(self):
        if self._context_menu is not None:
            return

        self._context_menu = tk.Menu(self, tearoff=0)
        self._context_menu.add_command(
            label="Mark Active Scene Complete",
            command=self.mark_active_scene_complete,
        )
        self._context_menu.add_command(
            label="Mark Next Scene Complete",
            command=self.mark_next_scene_complete,
        )
        self._context_menu.add_separator()
        self._context_menu.add_command(
            label="Add Timestamped Note",
            command=self.add_timestamped_note,
        )
        self._context_menu.add_separator()
        self._context_menu.add_command(
            label=self._edit_menu_label,
            command=self._edit_current_entity,
            state="disabled",
        )

        targets = [self, self.content_area, getattr(self.content_area, "_scrollable_frame", None)]
        for widget in targets:
            if widget is None:
                continue
            widget.bind("<Button-3>", self._show_context_menu)
            widget.bind("<Control-Button-1>", self._show_context_menu)

    def reset_scene_widgets(self):
        self._scene_vars = {}
        self._scene_order = []
        self._scene_metadata = {}

    def register_scene_widget(self, scene_key, var, checkbox, display_label=None, description=None, note_title=None):
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
            self._on_scene_var_change(scene_key)

        try:
            var.trace_add("write", _on_change)
        except AttributeError:
            var.trace("w", _on_change)  # fallback for older tkinter versions

        if checkbox is not None:
            checkbox.bind("<Button-3>", self._show_context_menu)
            checkbox.bind("<Control-Button-1>", self._show_context_menu)

    def _on_scene_var_change(self, scene_key):
        var_info = self._scene_vars.get(scene_key)
        if not var_info:
            return
        var = var_info.get("var")
        self._scene_completion_state[scene_key] = bool(var.get())
        self._persist_scene_state()
        if bool(var.get()):
            self._append_scene_to_notes(scene_key)

    def get_scene_completion(self, scene_key):
        return self._scene_completion_state.get(scene_key, False)

    def _set_scene_var(self, scene_key, value):
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
        self._active_scene_key = scene_key

    def mark_active_scene_complete(self):
        if self._active_scene_key and self._active_scene_key in self._scene_vars:
            self._set_scene_var(self._active_scene_key, True)
            return True
        return self.mark_next_scene_complete()

    def mark_next_scene_complete(self):
        for key in self._scene_order:
            if not self._scene_completion_state.get(key, False):
                self._active_scene_key = key
                self._set_scene_var(key, True)
                return True
        return False

    def add_timestamped_note(self):
        if not self.note_widget:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        existing = self.note_widget.get("1.0", "end-1c").strip()
        prefix = "\n" if existing else ""
        self.note_widget.insert("end", f"{prefix}[{timestamp}] ")
        self.note_widget.see("end")
        self._update_note_cache()

    def open_note_editor(self):
        if self._note_editor_window and self._note_editor_window.winfo_exists():
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
            note_text = text_box.get("1.0", "end-1c")
            self._apply_note_editor_changes(note_text)
            self._close_note_editor_window()
            return "break"

        def cancel_and_close(event=None):
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
        self._note_cache = new_text
        widget = self.note_widget
        widget_exists = False
        if widget is not None:
            try:
                widget_exists = bool(int(widget.winfo_exists()))
            except Exception:
                widget_exists = False

        if widget_exists:
            widget.delete("1.0", "end")
            if new_text:
                widget.insert("1.0", new_text)
            self._update_note_cache()
        else:
            self._persist_scene_state()

    def _close_note_editor_window(self, event=None):
        window = getattr(self, "_note_editor_window", None)
        if window is not None:
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
        if self.note_widget:
            self._note_cache = self.note_widget.get("1.0", "end-1c")
            self._persist_scene_state()

    def register_note_widget(self, widget):
        self.note_widget = widget
        widget.delete("1.0", "end")
        if self._note_cache:
            widget.insert("1.0", self._note_cache)
        widget.bind("<KeyRelease>", self._update_note_cache)
        widget.bind("<FocusOut>", self._update_note_cache)
        widget.bind("<Button-3>", self._show_context_menu)
        widget.bind("<Control-Button-1>", self._show_context_menu)

    def get_note_text(self):
        return self._note_cache

    def _append_scene_to_notes(self, scene_key):
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
        if not self.current_tab:
            return None
        tab_info = self.tabs.get(self.current_tab, {})
        meta = tab_info.get("meta") or {}
        if meta.get("kind") != "entity":
            return None
        return tab_info.get("content_frame")

    def _get_active_entity_edit_handler(self):
        frame = self._get_active_entity_frame()
        if frame is None:
            return None
        handler = getattr(frame, "edit_entity", None)
        return handler if callable(handler) else None

    def _edit_current_entity(self):
        handler = self._get_active_entity_edit_handler()
        if not handler:
            return
        try:
            handler()
        except Exception as exc:
            messagebox.showerror("Edit Entity", f"Unable to open editor: {exc}")

    def _show_context_menu(self, event):
        if not self._context_menu:
            return
        edit_available = self._get_active_entity_edit_handler() is not None
        try:
            self._context_menu.entryconfig(
                self._edit_menu_label,
                state="normal" if edit_available else "disabled",
            )
        except Exception:
            pass
        try:
            self._context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._context_menu.grab_release()

    def _update_layout_status(self, name=None):
        self.current_layout_name = name
        if name:
            self.layout_status_label.configure(text=f"Layout: {name}")
        else:
            self.layout_status_label.configure(text="")

    # ------------------------------------------------------------------
    # Layout persistence helpers
    # ------------------------------------------------------------------
    def _serialize_current_layout(self):
        layout_tabs = []
        for tab_name in self.tab_order:
            tab_info = self.tabs.get(tab_name)
            if not tab_info:
                continue
            meta = dict(tab_info.get("meta") or {})
            meta["title"] = tab_name
            if meta.get("kind") == "note":
                frame = tab_info.get("content_frame")
                if frame is not None and hasattr(frame, "text_box"):
                    meta["text"] = frame.text_box.get("1.0", "end-1c")
            elif meta.get("kind") == "world_map":
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
                frame = tab_info.get("content_frame")
                if frame is not None and hasattr(frame, "get_state"):
                    meta["state"] = frame.get_state()
                else:
                    meta.pop("state", None)
            elif meta.get("kind") == "whiteboard":
                meta.pop("controller", None)
            layout_tabs.append(meta)
        return {
            "scenario": self.scenario_name,
            "tabs": layout_tabs,
            "active": self.current_tab,
        }

    def _prompt_save_layout(self):
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
            if dialog.winfo_exists():
                try:
                    dialog.grab_release()
                except Exception:
                    pass
                dialog.destroy()

        def _do_save():
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
            selection = listbox.curselection()
            if selection:
                entry_var.set(listbox.get(selection[0]))

        if existing_names:
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
        for name, tab in list(self.tabs.items()):
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
        kind = tab_def.get("kind")
        title = tab_def.get("title")
        if kind == "entity":
            entity_type = tab_def.get("entity_type")
            entity_name = tab_def.get("entity_name") or title
            if not entity_type or not entity_name:
                raise ValueError("Missing entity information")
            self._open_entity_from_layout(entity_type, entity_name)
        elif kind == "note":
            text = tab_def.get("text", "")
            name = title or f"Note {len(self.tabs) + 1}"
            self.add_tab(
                name,
                self.create_note_frame(initial_text=text),
                content_factory=lambda master, initial_text=text: self.create_note_frame(master=master, initial_text=initial_text),
                layout_meta={"kind": "note"},
            )
        elif kind == "npc_graph":
            # Ensure rich host exists for graph editors
            if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
                self._rich_host = ctk.CTkFrame(self)
            parent = self._rich_host
            self.add_tab(
                title or "NPC Graph",
                self.create_npc_graph_frame(master=parent),
                content_factory=lambda master=parent: self.create_npc_graph_frame(master),
                layout_meta={"kind": "npc_graph", "host": "rich"},
            )
        elif kind == "pc_graph":
            if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
                self._rich_host = ctk.CTkFrame(self)
            parent = self._rich_host
            self.add_tab(
                title or "PC Graph",
                self.create_pc_graph_frame(master=parent),
                content_factory=lambda master=parent: self.create_pc_graph_frame(master),
                layout_meta={"kind": "pc_graph", "host": "rich"},
            )
        elif kind == "scenario_graph":
            if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
                self._rich_host = ctk.CTkFrame(self)
            parent = self._rich_host
            self.add_tab(
                title or "Scenario Graph Editor",
                self.create_scenario_graph_frame(master=parent),
                content_factory=lambda master=parent: self.create_scenario_graph_frame(master),
                layout_meta={"kind": "scenario_graph", "host": "rich"},
            )
        elif kind == "world_map":
            name = tab_def.get("map_name")
            self.open_world_map_tab(map_name=name, title=title or (f"World Map: {name}" if name else "World Map"))
        elif kind == "map_tool":
            name = tab_def.get("map_name")
            self.open_map_tool_tab(map_name=name, title=title or (f"Map Tool: {name}" if name else "Map Tool"))
        elif kind == "scene_flow":
            scen = tab_def.get("scenario_title")
            self.open_scene_flow_tab(scenario_title=scen, title=title or (f"Scene Flow: {scen}" if scen else "Scene Flow"))
        elif kind == "loot_generator":
            self.open_loot_generator_tab(title=title or "Loot Generator")
        elif kind == "random_tables":
            self.open_random_tables_tab(title=title or "Random Tables", initial_state=tab_def.get("state"))
        elif kind == "whiteboard":
            self.open_whiteboard_tab(title=title or "Whiteboard")
        else:
            raise ValueError(f"Unsupported tab kind '{kind}'")

    def load_layout(self, layout_name, set_default=False, silent=False):
        layout = self.layout_manager.get_layout(layout_name)
        if not layout:
            if not silent:
                messagebox.showwarning("Layout Missing", f"Layout '{layout_name}' was not found.")
            return

        tabs = layout.get("tabs", [])
        if not tabs:
            if not silent:
                messagebox.showwarning("Empty Layout", f"Layout '{layout_name}' has no tabs saved.")
            return

        self._clear_all_tabs()

        errors = []
        for tab_def in tabs:
            try:
                self._restore_tab_from_config(tab_def)
            except Exception as exc:
                errors.append(f"{tab_def.get('title', 'Unknown')}: {exc}")

        if not self.tabs:
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

    def _open_entity_from_layout(self, entity_type, entity_name):
        if entity_type == "Scenarios" and (self.scenario.get("Title") == entity_name or self.scenario.get("Name") == entity_name):
            frame = create_entity_detail_frame(
                "Scenarios",
                self.scenario,
                master=self.content_area,
                open_entity_callback=self.open_entity_tab,
            )
            self.add_tab(
                entity_name,
                frame,
                content_factory=lambda master: create_entity_detail_frame("Scenarios", self.scenario, master=master, open_entity_callback=self.open_entity_tab),
                layout_meta={
                    "kind": "entity",
                    "entity_type": "Scenarios",
                    "entity_name": entity_name,
                },
            )
            return
        self.open_entity_tab(entity_type, entity_name)

    def _on_tab_press(self, event, name):
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
        if event is None:
            return
        frame = self.tabs[name]["button_frame"]
        rel_x = event.x_root - self.tab_bar.winfo_rootx() - frame.winfo_width() // 2

        # move the dragged tab along with the cursor
        frame.place_configure(x=rel_x)

        # same midpoint-swap logic as before…
        for idx, other in enumerate(self.tab_order):
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
        oframe = self.tabs[other_name]["button_frame"]
        start = oframe.winfo_x()
        target = start + dx
        self._animate_shift([oframe], [dx])

    def _animate_shift(self, frames, deltas, step=0):
        if step >= 10: return
        for frame, delta in zip(frames, deltas):
            cur = frame.winfo_x()
            frame.place_configure(x=cur + delta/10)
        self.after(20, lambda: self._animate_shift(frames, deltas, step+1))
    
    def _swap_order(self, name, other):
        old = self.tab_order.index(name)
        new = self.tab_order.index(other)
        self.tab_order.pop(old)
        self.tab_order.insert(new, name)

    def _on_tab_release(self, event, name):
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
        log_info(f"Toggling detach for tab: {name}", func_name="GMScreenView.toggle_detach_tab")
        if self.tabs[name]["detached"]:
            self.reattach_tab(name)
            # After reattaching, show the detach icon
            self.tabs[name]["detach_button"].configure(image=self.detach_icon)
        else:
            self.detach_tab(name)
            # When detached, change to the reattach icon
            self.tabs[name]["detach_button"].configure(image=self.reattach_icon)

    def detach_tab(self, name):
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
        print(f"[DETACH] Detached window shown at {GRAPH_W}×{GRAPH_H}")

        # Portrait & scenario-graph restoration (unchanged)…
        if hasattr(old_frame, "scenario_graph_editor") and hasattr(old_frame.scenario_graph_editor, "get_state"):
            scen = old_frame.scenario_graph_editor.get_state()
            if scen and hasattr(new_frame, "scenario_graph_editor") and hasattr(new_frame.scenario_graph_editor, "set_state"):
                new_frame.scenario_graph_editor.set_state(scen)

        if hasattr(new_frame, "portrait_label"):
            self.tabs[name]["portrait_label"] = new_frame.portrait_label
        else:
            pl = self.tabs[name].get("portrait_label")
            if pl and pl.winfo_exists():
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
        # Measure against the visible viewport (the CTkScrollableFrame itself),
        # not its inner _scrollable_frame (which tracks content height and can
        # collapse after adding short views like the map selector).
        try:
            viewport = self.content_area if hasattr(self, "content_area") else self
        except Exception:
            viewport = self

        try:
            container.pack_propagate(False)
        except Exception:
            pass

        def _sync(_evt=None):
            try:
                w = max(1, int(viewport.winfo_width()))
                h = max(1, int(viewport.winfo_height()))
                container.configure(width=w, height=h)
            except Exception:
                pass

        try:
            viewport.bind("<Configure>", _sync, add="+")
        except Exception:
            pass
        # Initial sizing once mounted
        self.after(50, _sync)

    def open_whiteboard_tab(self, title=None):
        """Open a whiteboard tab within the GM screen."""
        if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
            self._rich_host = ctk.CTkFrame(self)

        container = ctk.CTkFrame(self._rich_host)
        self._make_fullbleed(container)
        controller = WhiteboardController(container, root_app=self)
        container.whiteboard_controller = controller

        def _on_destroy(_event=None, ctrl=controller):
            try:
                ctrl.close()
            except Exception:
                pass

        container.bind("<Destroy>", _on_destroy, add="+")

        def factory(master):
            host_parent = master if master is not None else self._rich_host
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
        )

    def open_world_map_tab(self, map_name=None, title=None):
        """Open a WorldMapPanel inside a new GM-screen tab."""
        # Mount heavy interactive views into a dedicated full-bleed host
        if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
            self._rich_host = ctk.CTkFrame(self)
        container = ctk.CTkFrame(self._rich_host)
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
            c = ctk.CTkFrame(self._rich_host)
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
        if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
            self._rich_host = ctk.CTkFrame(self)
        container = ctk.CTkFrame(self._rich_host)
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
            c = ctk.CTkFrame(self._rich_host)
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
        if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
            self._rich_host = ctk.CTkFrame(self)
        container = ctk.CTkFrame(self._rich_host)
        viewer = create_scene_flow_frame(container, scenario_title=scenario_title)
        viewer.pack(fill="both", expand=True)
        container.scene_flow_viewer = viewer

        tab_title = title or (f"Scene Flow: {scenario_title}" if scenario_title else "Scene Flow")

        def factory(master, _title=scenario_title):
            c = ctk.CTkFrame(self._rich_host)
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

    def open_random_tables_tab(self, title=None, initial_state=None):
        """Open the random tables panel inside the GM screen."""

        tab_name = title or "Random Tables"
        panel = RandomTablesPanel(self.content_area, initial_state=initial_state)

        def factory(master, tab_ref=tab_name):
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


    def reattach_tab(self, name):
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
            new_frame = current_frame
        else:
            # Determine host for this tab
            host_kind = (self.tabs[name].get("meta") or {}).get("host") or "scroll"
            parent = None
            if host_kind == "rich":
                if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
                    self._rich_host = ctk.CTkFrame(self)
                parent = self._rich_host
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
        if len(self.tabs) == 1:
            return
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

    def reposition_add_button(self):
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
        log_info("Adding random entity to GM screen", func_name="GMScreenView._add_random_entity")
        """Pick a random NPC, Creature, Object, Information or Clue and open it.
        """
        types = ["NPCs", "Creatures", "Objects", "Informations", "Clues"]
        random.shuffle(types)

        for etype in types:
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
        for name, tab in self.tabs.items():
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

    def show_tab(self, name):
        log_info(f"Showing tab: {name}", func_name="GMScreenView.show_tab")
        # Hide content for the current tab if it's not detached.
        if self.current_tab and self.current_tab in self.tabs:
            if not self.tabs[self.current_tab]["detached"]:
                self.tabs[self.current_tab]["content_frame"].pack_forget()
            self.tabs[self.current_tab]["button"].configure(fg_color=("gray75", "gray25"))
        self.current_tab = name
        self.tabs[name]["button"].configure(fg_color=("gray55", "gray15"))
        # Only pack the content into the main content area if the tab is not detached.
        if not self.tabs[name]["detached"]:
            tab = self.tabs[name]
            target_host = (tab.get("meta") or {}).get("host") or "scroll"
            # Toggle which host is visible
            if target_host == "rich":
                # Hide scroll area and show rich host
                try:
                    self.content_area.pack_forget()
                except Exception:
                    pass
                host = self._rich_host if getattr(self, "_rich_host", None) else None
                if host is None or not host.winfo_exists():
                    self._rich_host = ctk.CTkFrame(self)
                    host = self._rich_host
                host.pack(fill="both", expand=True)
            else:
                # Show scroll area and hide rich host
                try:
                    if getattr(self, "_rich_host", None) and self._rich_host.winfo_exists():
                        self._rich_host.pack_forget()
                except Exception:
                    pass
                self.content_area.pack(fill="both", expand=True)

            frame = tab["content_frame"]
            frame.pack(fill="both", expand=True)

    def add_new_tab(self):
        log_info("Opening entity selection for new tab", func_name="GMScreenView.add_new_tab")
        self._show_add_menu()

    def _show_add_menu(self):
        button = self.add_button
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        try:
            self._add_menu.tk_popup(x, y)
        finally:
            self._add_menu.grab_release()

    def open_selection_window(self, entity_type, popup=None):
        log_info(f"Opening selection window for {entity_type}", func_name="GMScreenView.open_selection_window")
        if popup:
            popup.destroy()
        if entity_type == "Note Tab":
            self.add_tab(
                f"Note {len(self.tabs) + 1}",
                self.create_note_frame(),
                content_factory=lambda master, initial_text="": self.create_note_frame(master=master, initial_text=initial_text),
                layout_meta={"kind": "note"},
            )
            return
        elif entity_type == "World Map":
            self.open_world_map_tab()
            return
        elif entity_type == "Map Tool":
            self.open_map_tool_tab()
            return
        elif entity_type == "Scene Flow":
            self.open_scene_flow_tab()
            return
        elif entity_type == "Loot Generator":
            self.open_loot_generator_tab()
            return
        elif entity_type == "Whiteboard":
            self.open_whiteboard_tab()
            return
        elif entity_type == "Random Tables":
            self.open_random_tables_tab()
            return
        elif entity_type == "NPC Graph":
            if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
                self._rich_host = ctk.CTkFrame(self)
            host_parent = self._rich_host
            self.add_tab(
                "NPC Graph",
                self.create_npc_graph_frame(master=host_parent),
                content_factory=lambda master=host_parent: self.create_npc_graph_frame(master),
                layout_meta={"kind": "npc_graph", "host": "rich"}
            )

            return
        elif entity_type == "PC Graph":
            if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
                self._rich_host = ctk.CTkFrame(self)
            host_parent = self._rich_host
            self.add_tab(
                "PC Graph",
                self.create_pc_graph_frame(master=host_parent),
                content_factory=lambda master=host_parent: self.create_pc_graph_frame(master),
                layout_meta={"kind": "pc_graph", "host": "rich"}
            )

            return
        elif entity_type == "Scenario Graph Editor":
            if getattr(self, "_rich_host", None) is None or not self._rich_host.winfo_exists():
                self._rich_host = ctk.CTkFrame(self)
            host_parent = self._rich_host
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


    def open_entity_tab(self, entity_type, name):
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
        wrapper = self.wrappers[entity_type]
        items = wrapper.load_items()
        key = "Title" if (entity_type == "Scenarios" or entity_type == "Informations") else "Name"
        item = next((i for i in items if i.get(key) == name), None)
        if not item:
            messagebox.showerror("Error", f"{entity_type[:-1]} '{name}' not found.")
            return
        # Use the shared factory function and pass self.open_entity_tab as the callback.
        frame = create_entity_detail_frame(entity_type, item, master=self.content_area, open_entity_callback=self.open_entity_tab)
        
        self.add_tab(
            name,
            frame,
            content_factory=lambda master: create_entity_detail_frame(entity_type, item, master=master, open_entity_callback=self.open_entity_tab),
            layout_meta={
                "kind": "entity",
                "entity_type": entity_type,
                "entity_name": name,
            },
        )

    def _focus_existing_tab(self, tab_name):
        if tab_name not in self.tabs:
            return
        self.show_tab(tab_name)
        tab_info = self.tabs.get(tab_name, {})
        if tab_info.get("detached"):
            window = tab_info.get("window")
            if window and window.winfo_exists():
                try:
                    window.deiconify()
                    window.lift()
                    window.focus_force()
                except Exception:
                    pass

    def _find_existing_entity_tab(self, entity_type, entity_name):
        for tab_name, tab_info in self.tabs.items():
            meta = tab_info.get("meta") or {}
            if (
                meta.get("kind") == "entity"
                and meta.get("entity_type") == entity_type
                and meta.get("entity_name") == entity_name
            ):
                return tab_name
        return None

    def create_scenario_graph_frame(self, master=None):
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
        log_info(f"Creating entity frame for {entity_type}: {entity.get('Name') or entity.get('Title')}", func_name="GMScreenView.create_entity_frame")
        if master is None:
            master = self.content_area
        frame = ctk.CTkFrame(master)
        template = self.templates[entity_type]
        if (entity_type == "NPCs" or entity_type == "PCs" or entity_type == "Creatures" ) and "Portrait" in entity and os.path.exists(entity["Portrait"]):
            img = Image.open(entity["Portrait"])
            img = img.resize((200, 200), Image.Resampling.LANCZOS)
            ctk_image = ctk.CTkImage(light_image=img, size=(200, 200))
            portrait_label = ctk.CTkLabel(frame, image=ctk_image, text="")
            portrait_label.image = ctk_image
            portrait_label.entity_name = entity["Name"]
            portrait_label.is_portrait = True
            self.portrait_images[entity["Name"]] = ctk_image
            portrait_label.pack(pady=10)
            print(f"[DEBUG] Created portrait label for {entity['Name']}: is_portrait={portrait_label.is_portrait}, entity_name={portrait_label.entity_name}")
            frame.portrait_label = portrait_label
        for field in template["fields"]:
            field_name = field["name"]
            field_type = field["type"]
            if (entity_type == "NPCs" or entity_type == "PCs" or entity_type == "Creatures") and field_name == "Portrait":
                continue
            if field_type == "longtext":
                self.insert_longtext(frame, field_name, entity.get(field_name, ""))
            elif field_type == "text":
                self.insert_text(frame, field_name, entity.get(field_name, ""))
            elif field_type == "list":
                linked_type = field.get("linked_type", None)
                if linked_type:
                    self.insert_links(frame, field_name, entity.get(field_name) or [], linked_type)
        return frame
    
    def insert_text(self, parent, header, content):
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
        ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold")).pack(anchor="w", padx=10)
        formatted_text = format_multiline_text(content, max_length=2000)
        box = ctk.CTkTextbox(parent, wrap="word", height=120)
        box.insert("1.0", formatted_text)
        box.configure(state="disabled")
        box.pack(fill="x", padx=10, pady=5)

    def insert_links(self, parent, header, items, linked_type):
        ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold")).pack(anchor="w", padx=10)
        for item in items:
            label = ctk.CTkLabel(parent, text=item, text_color="#00BFFF", cursor="hand2")
            label.pack(anchor="w", padx=10)
            label.bind("<Button-1>", partial(self._on_link_clicked, linked_type, item))

    def _on_link_clicked(self, linked_type, item, event=None):
        self.open_entity_tab(linked_type, item)

    def save_note_to_file(self, note_frame, default_name):
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
    
    def create_npc_graph_frame(self, master=None):
        if master is None:
            master = self.content_area
        frame = ctk.CTkFrame(master)
        graph_editor = NPCGraphEditor(frame, self.wrappers["NPCs"], self.wrappers["Factions"])
        graph_editor.pack(fill="both", expand=True)
        frame.graph_editor = graph_editor  # Save a reference for state management
        
        return frame
    
    def create_pc_graph_frame(self, master=None):
        if master is None:
            master = self.content_area
        frame = ctk.CTkFrame(master)
        graph_editor = PCGraphEditor(frame, self.wrappers["PCs"], self.wrappers["Factions"])
        graph_editor.pack(fill="both", expand=True)
        frame.graph_editor = graph_editor  # Save a reference for state management
        return frame
    
    def reorder_detached_windows(self):
        screen_width = self.winfo_screenwidth()
        margin = 10  # space between windows and screen edge
        current_x = margin
        current_y = margin
        max_row_height = 0

        for name, tab in self.tabs.items():
            if tab.get("detached") and tab.get("window") is not None:
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
        # remove our global Ctrl+F handler
        root = self.winfo_toplevel()
        root.unbind_all("<Control-F>")
        # now destroy as usual
        super().destroy()
