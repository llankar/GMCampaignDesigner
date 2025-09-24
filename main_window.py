import os
import sys
import json
import sqlite3
import subprocess
import time
import requests
import shutil
import re
import unicodedata
import tkinter as tk
from difflib import SequenceMatcher
from tkinter import (
    filedialog,
    messagebox,
    Toplevel,
    Listbox,
    MULTIPLE,
    PhotoImage,
    simpledialog,
)
from tkinter import ttk

import customtkinter as ctk
from PIL import Image, ImageTk
from docx import Document

# Modular helper imports
from modules.helpers.window_helper import position_window_at_top
from modules.helpers.template_loader import load_template
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.swarmui_helper import get_available_models
from modules.helpers.logging_helper import (
    initialize_logging,
    log_module_import,
    log_debug,
    log_exception,
    log_info,
    log_methods,
    log_warning,
)
from modules.ui.tooltip import ToolTip
from modules.ui.icon_button import create_icon_button

from modules.generic.generic_list_view import GenericListView
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.scenarios.gm_screen_view import GMScreenView
from modules.npcs.npc_graph_editor import NPCGraphEditor
from modules.pcs.pc_graph_editor import PCGraphEditor
from modules.scenarios.scenario_graph_editor import ScenarioGraphEditor
from modules.scenarios.scenario_importer import ScenarioImportWindow
from modules.scenarios.scenario_generator_view import ScenarioGeneratorView
from modules.generic.export_for_foundry import preview_and_export_foundry
from modules.helpers import text_helpers
from db.db import load_schema_from_json, initialize_db
from modules.factions.faction_graph_editor import FactionGraphEditor
from modules.pcs.display_pcs import display_pcs_in_banner
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.maps.controllers.display_map_controller import DisplayMapController
from modules.maps.world_map_view import WorldMapWindow
from modules.generic.custom_fields_editor import CustomFieldsEditor


from modules.dice.dice_roller_window import DiceRollerWindow
from modules.dice.dice_bar_window import DiceBarWindow
from modules.audio.audio_bar_window import AudioBarWindow
from modules.audio.audio_controller import get_audio_controller
from modules.audio.sound_manager_window import SoundManagerWindow

initialize_logging()
log_module_import(__name__)

# Set up CustomTkinter appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Global process variable for SwarmUI
SWARMUI_PROCESS = None

#logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')


@log_methods
class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        log_info("Initializing MainWindow", func_name="main_window.MainWindow.__init__")

        self.title("GMCampaignDesigner")
        self.geometry("1920x980")
        self.minsize(1920, 980)
        self.attributes("-fullscreen", True)
        self.current_open_view   = None
        self.current_open_entity = None    # ← initialize here to avoid AttributeError
        initialize_db()
        log_info("Database initialization complete", func_name="main_window.MainWindow.__init__")
        position_window_at_top(self)
        self.set_window_icon()
        self.create_layout()
        self.load_icons()
        self.create_sidebar()
        self.create_content_area()
        self.create_exit_button()
        self.load_model_config()
        self.init_wrappers()
        self.current_gm_view = None
        self.dice_roller_window = None
        self.dice_bar_window = None
        self.audio_controller = get_audio_controller()
        self.sound_manager_window = None
        self.audio_bar_window = None
        root = self.winfo_toplevel()
        root.bind_all("<Control-f>", self._on_ctrl_f)

        self.after(200, self.open_dice_bar)
        self.after(400, self.open_audio_bar)

    def open_ai_settings(self):
        log_info("Opening AI settings dialog", func_name="main_window.MainWindow.open_ai_settings")
        top = ctk.CTkToplevel(self)
        top.title("AI Settings")
        top.geometry("520x360")
        top.lift(); top.focus_force(); top.attributes("-topmost", True); top.after_idle(lambda: top.attributes("-topmost", False))

        # Current config values
        base_url = ConfigHelper.get("AI", "base_url", fallback="http://localhost:8080") or ""
        model = ConfigHelper.get("AI", "model", fallback="gpt-oss") or ""
        temperature = ConfigHelper.get("AI", "temperature", fallback="0.7") or "0.7"
        max_tokens = ConfigHelper.get("AI", "max_tokens", fallback="512") or "512"
        api_key = ConfigHelper.get("AI", "api_key", fallback="") or ""

        # Vars
        v_base = ctk.StringVar(value=base_url)
        v_model = ctk.StringVar(value=model)
        v_temp = ctk.StringVar(value=str(temperature))
        v_max = ctk.StringVar(value=str(max_tokens))
        v_key = ctk.StringVar(value=api_key)

        form = ctk.CTkFrame(top)
        form.pack(fill="both", expand=True, padx=12, pady=12)

        def row(label, widget):
            r = ctk.CTkFrame(form)
            r.pack(fill="x", pady=6)
            ctk.CTkLabel(r, text=label, width=140, anchor="w").pack(side="left")
            widget.pack(side="left", fill="x", expand=True)

        row("Base URL", ctk.CTkEntry(form, textvariable=v_base, placeholder_text="http://localhost:8080"))
        row("Model", ctk.CTkEntry(form, textvariable=v_model, placeholder_text="gpt-oss"))
        row("Temperature", ctk.CTkEntry(form, textvariable=v_temp))
        row("Max Tokens", ctk.CTkEntry(form, textvariable=v_max))
        row("API Key", ctk.CTkEntry(form, textvariable=v_key))

        btns = ctk.CTkFrame(top)
        btns.pack(fill="x", padx=12, pady=(0,12))

        def save():
            try:
                # Basic normalization
                _ = float(v_temp.get())
                _ = int(v_max.get())
            except Exception:
                log_warning("Rejected AI settings save due to invalid numeric values",
                            func_name="main_window.MainWindow.open_ai_settings.save")
                messagebox.showerror("Invalid Values", "Temperature must be a float and Max Tokens an integer.")
                return
            ConfigHelper.set("AI", "base_url", v_base.get().strip())
            ConfigHelper.set("AI", "model", v_model.get().strip())
            ConfigHelper.set("AI", "temperature", v_temp.get().strip())
            ConfigHelper.set("AI", "max_tokens", v_max.get().strip())
            ConfigHelper.set("AI", "api_key", v_key.get())
            log_info(
                "AI settings saved",
                func_name="main_window.MainWindow.open_ai_settings.save",
            )
            messagebox.showinfo("Saved", "AI settings saved.")

        def reset_defaults():
            v_base.set("http://localhost:8080")
            v_model.set("gpt-oss")
            v_temp.set("0.7")
            v_max.set("512")
            v_key.set("")
            log_info(
                "AI settings reset to defaults",
                func_name="main_window.MainWindow.open_ai_settings.reset_defaults",
            )

        ctk.CTkButton(btns, text="Save", command=save).pack(side="right", padx=6)
        ctk.CTkButton(btns, text="Defaults", command=reset_defaults).pack(side="right", padx=6)
        ctk.CTkButton(btns, text="Close", command=top.destroy).pack(side="right", padx=6)

    # ---------------------------
    # Setup and Layout Methods
    # ---------------------------
    def set_window_icon(self):
        icon_path = os.path.join("assets", "GMCampaignDesigner.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        icon_image = PhotoImage(file=os.path.join("assets", "GMCampaignDesigner logo.png"))
        self.tk.call('wm', 'iconphoto', self._w, icon_image)

    def create_layout(self):
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True)

    def load_icons(self):
        log_debug("Loading sidebar icons", func_name="main_window.MainWindow.load_icons")
        self.icons = {
            "change_db": self.load_icon("database_icon.png", size=(60, 60)),
            "swarm_path": self.load_icon("folder_icon.png", size=(60, 60)),
            "customize_fields": self.load_icon("customize_fields.png", size=(60, 60)),
            "manage_scenarios": self.load_icon("scenario_icon.png", size=(60, 60)),
            "manage_pcs": self.load_icon("pc_icon.png", size=(60, 60)),
            "manage_npcs": self.load_icon("npc_icon.png", size=(60, 60)),
            "manage_creatures": self.load_icon("creature_icon.png", size=(60, 60)),
            "manage_factions": self.load_icon("faction_icon.png", size=(60, 60)),
            "manage_places": self.load_icon("places_icon.png", size=(60, 60)),
            "manage_objects": self.load_icon("objects_icon.png", size=(60, 60)),
            "manage_informations": self.load_icon("informations_icon.png", size=(60, 60)),
            "manage_clues": self.load_icon("clues_icon.png", size=(60, 60)),
            "manage_maps": self.load_icon("maps_icon.png", size=(60, 60)),
            "export_scenarios": self.load_icon("export_icon.png", size=(60, 60)),
            "gm_screen": self.load_icon("gm_screen_icon.png", size=(60, 60)),
            "npc_graph": self.load_icon("npc_graph_icon.png", size=(60, 60)),
            "pc_graph": self.load_icon("pc_graph_icon.png", size=(60, 60)),
            "faction_graph": self.load_icon("faction_graph_icon.png", size=(60, 60)),
            "scenario_graph": self.load_icon("scenario_graph_icon.png", size=(60, 60)),
            "world_map": self.load_icon("maps_icon.png", size=(60, 60)),
            "generate_portraits": self.load_icon("generate_icon.png", size=(60, 60)),
            "associate_portraits": self.load_icon("associate_icon.png", size=(60, 60)),
            "import_portraits": self.load_icon("import_icon.png", size=(60, 60)),
            "import_scenario": self.load_icon("import_icon.png", size=(60, 60)),
            "import_creatures_pdf": self.load_icon("import_icon.png", size=(60, 60)),
            "export_foundry": self.load_icon("export_foundry_icon.png", size=(60, 60)),
            "map_tool": self.load_icon("map_tool_icon.png", size=(60, 60)),
            "generate_scenario": self.load_icon("generate_scenario_icon.png", size=(60, 60)),
            "dice_roller": self.load_icon("dice_roller_icon.png", size=(60, 60)),
            "dice_bar": self.load_icon("dice_roller_icon.png", size=(60, 60)),
            "sound_manager": self.load_icon("sound_manager_icon.png", size=(60, 60)),
            "audio_controls": self.load_icon("sound_manager_icon.png", size=(60, 60)),
            "scene_flow_viewer": self.load_icon("scenes_flow_icon.png", size=(60, 60)),
        }

    def open_custom_fields_editor(self):
        try:
            log_info("Opening Custom Fields Editor", func_name="main_window.MainWindow.open_custom_fields_editor")
            top = CustomFieldsEditor(self)
            top.transient(self)
            top.lift(); top.focus_force()
        except Exception as e:
            log_exception(f"Failed to open Custom Fields Editor: {e}",
                          func_name="main_window.MainWindow.open_custom_fields_editor")
            messagebox.showerror("Error", f"Failed to open Custom Fields Editor:\n{e}")

    def load_icon(self, file_name, size=(60, 60)):
        path = os.path.join("assets", file_name)
        try:
            pil_image = Image.open(path)
        except Exception as e:
            log_warning(f"Unable to load icon {file_name}: {e}",
                        func_name="main_window.MainWindow.load_icon")
            return None
        log_debug(f"Loaded icon {file_name}", func_name="main_window.MainWindow.load_icon")
        return ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=size)

    def create_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self.main_frame, width=220)
        self.sidebar_frame.pack(side="left", fill="y", padx=5, pady=5)
        self.sidebar_frame.pack_propagate(False)
        self.sidebar_inner = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.sidebar_inner.pack(fill="both", expand=True, padx=5, pady=5)

        # Logo
        logo_path = os.path.join("assets", "GMCampaignDesigner logo.png")
        if os.path.exists(logo_path):
            logo_image = Image.open(logo_path).resize((60, 60))
            logo = ctk.CTkImage(light_image=logo_image, dark_image=logo_image, size=(80, 80))
            self.logo_image = logo
            logo_label = ctk.CTkLabel(self.sidebar_inner, image=logo, text="")
            logo_label.pack(pady=(0, 3), anchor="center")

        # Header label
        header_label = ctk.CTkLabel(self.sidebar_inner, text="Campaign Tools", font=("Helvetica", 16, "bold"))
        header_label.pack(pady=(0, 2), anchor="center")

        # Database display container
        db_container = ctk.CTkFrame(self.sidebar_inner, fg_color="transparent",
                                    border_color="#005fa3", border_width=2, corner_radius=8)
        db_container.pack(pady=(0, 5), anchor="center", fill="x", padx=5)
        db_title_label = ctk.CTkLabel(db_container, text="Database:", font=("Segoe UI", 16, "bold"),
                                    fg_color="transparent", text_color="white")
        db_title_label.pack(pady=(3, 0), anchor="center")
        db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db")
        db_name = os.path.splitext(os.path.basename(db_path))[0]
        self.db_name_label = ctk.CTkLabel(db_container, text=db_name,
                                        font=("Segoe UI", 14, "italic"), fg_color="transparent", text_color="white")
        self.db_name_label.pack(pady=(0, 1), anchor="center")
        try:
            # Show full absolute path on hover
            full_path = os.path.abspath(db_path)
            self.db_tooltip = ToolTip(self.db_name_label, full_path)
        except Exception:
            self.db_tooltip = None

        self.create_accordion_sidebar()

    def create_accordion_sidebar(self):
        container = ctk.CTkFrame(self.sidebar_inner, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=2, pady=2)
        sections = []  # track all sections to enforce single-open behavior
        default_title = "Campaign Workshop"
        default_meta = {"sec": None}
        active_section = {"sec": None}

        def make_section(parent, title, buttons):
            sec = ctk.CTkFrame(parent)
            sec.pack(fill="x", pady=(4, 6))

            header = ctk.CTkFrame(sec, fg_color="#0b3d6e")
            header.pack(fill="x")
            title_lbl = ctk.CTkLabel(header, text=title, anchor="center")
            title_lbl.pack(fill="x", pady=6)
            state = {"open": False}

            body = ctk.CTkFrame(sec, fg_color="transparent")
            cols = 2
            for c in range(cols):
                body.grid_columnconfigure(c, weight=1)
            for idx, (icon_key, tooltip, cmd) in enumerate(buttons):
                r, c = divmod(idx, cols)
                icon = self.icons.get(icon_key)
                btn = create_icon_button(body, icon, tooltip, cmd)
                btn.grid(row=r, column=c, padx=2, pady=2, sticky="ew")

            def expand():
                if state["open"]:
                    return
                state["open"] = True
                try:
                    body.pack(fill="x", padx=2, pady=(2, 2))
                except Exception:
                    pass

            def collapse():
                if not state["open"]:
                    return
                state["open"] = False
                try:
                    body.pack_forget()
                except Exception:
                    pass

            def toggle(_event=None):
                if state["open"]:
                    collapse()
                    if active_section["sec"] is sec:
                        active_section["sec"] = None
                else:
                    for meta in sections:
                        if meta["sec"] is sec:
                            continue
                        meta["collapse"]()
                    expand()
                    active_section["sec"] = sec

            header.bind("<Button-1>", toggle)
            title_lbl.bind("<Button-1>", toggle)

            sections.append({
                "sec": sec,
                "state": state,
                "collapse": collapse,
                "expand": expand,
                "toggle": toggle,
                "title": title,
            })
            return sec

        # Group buttons
        data_system = [
            ("change_db", "Change Data Storage", self.change_database_storage),
            ("swarm_path", "Set SwarmUI Path", self.select_swarmui_path),
            ("customize_fields", "Customize Fields", self.open_custom_fields_editor),
        ]
        content = [
            ("manage_scenarios", "Manage Scenarios", lambda: self.open_entity("scenarios")),
            ("manage_pcs", "Manage PCs", lambda: self.open_entity("pcs")),
            ("manage_npcs", "Manage NPCs", lambda: self.open_entity("npcs")),
            ("manage_creatures", "Manage Creatures", lambda: self.open_entity("creatures")),
            ("manage_factions", "Manage Factions", lambda: self.open_entity("factions")),
            ("manage_places", "Manage Places", lambda: self.open_entity("places")),
            ("manage_objects", "Manage Objects", lambda: self.open_entity("objects")),
            ("manage_informations", "Manage Informations", lambda: self.open_entity("informations")),
            ("manage_clues", "Manage Clues", lambda: self.open_entity("clues")),
            ("manage_maps", "Manage Maps", lambda: self.open_entity("maps")),
        ]
        relations = [
            ("npc_graph", "Open NPC Graph Editor", self.open_npc_graph_editor),
            ("pc_graph", "Open PC Graph Editor", self.open_pc_graph_editor),
            ("faction_graph", "Open Factions Graph Editor", self.open_faction_graph_editor),
            ("scenario_graph", "Open Scenario Graph Editor", self.open_scenario_graph_editor),
            ("scene_flow_viewer", "Open Scene Flow Viewer", self.open_scene_flow_viewer),
            ("world_map", "Open World Map", self.open_world_map),
        ]
        utilities = [
            ("generate_scenario", "Generate Scenario", self.open_scenario_generator),
            ("import_scenario", "Import Scenario", self.open_scenario_importer),
            ("import_creatures_pdf", "Import Creatures from PDF", self.open_creature_importer),
            ("gm_screen", "Open GM Screen", self.open_gm_screen),
            ("export_scenarios", "Export Scenarios", self.preview_and_export_scenarios),
            ("export_foundry", "Export Scenarios for Foundry", self.export_foundry),
            ("generate_portraits", "Generate Portraits", self.generate_missing_portraits),
            ("associate_portraits", "Associate NPC Portraits", self.associate_npc_portraits),
            ("import_portraits", "Import Portraits from Folder", self.import_portraits_from_directory),
            ("map_tool", "Map Tool", self.map_tool),
            ("sound_manager", "Sound & Music Manager", self.open_sound_manager),
            ("audio_controls", "Audio Controls Bar", self.open_audio_bar),
            ("dice_bar", "Dice Bar", self.open_dice_bar),
            ("dice_roller", "Open Dice Roller", self.open_dice_roller),
        ]

        make_section(container, "Data & System", data_system)
        make_section(container, "Campaign Workshop", content)
        make_section(container, "Relations & Graphs", relations)
        make_section(container, "Utilities", utilities)

        # Open the default section by default
        for meta in sections:
            if meta.get("title") == default_title:
                default_meta = meta
                try:
                    meta["expand"]()
                    active_section["sec"] = meta["sec"]
                except Exception:
                    pass
                break

    def create_content_area(self):
        self.content_frame = ctk.CTkFrame(self.main_frame)
        self.content_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=0)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # ✅ Always explicitly create these initially:
        self.banner_frame = ctk.CTkFrame(self.content_frame, height=150, fg_color="#444")
        # — Monkey-patch banner_frame.pack to grid instead, so open_gm_screen’s pack() won’t clash
        self.banner_frame.pack = lambda *args, **kwargs: self.banner_frame.grid(row=0, column=0, sticky="ew")
        self.inner_content_frame = ctk.CTkFrame(self.content_frame, fg_color="#222")

        self.banner_toggle_btn = ctk.CTkButton(
            self.sidebar_inner,
            text="▼",
            width=40,
            height=30,
            command=self._toggle_banner,
            fg_color="#555",
            hover_color="#777",
            font=("", 16)
        )
        self.banner_toggle_btn.place(relx=1.0, rely=0.0, anchor="ne")

        self.banner_visible = False
        self.current_open_view = None

    def _toggle_banner(self):
        # --- GRAPH MODE?  (no current_open_entity but a graph_type set) ---
        if self.current_open_entity is None and getattr(self, "_graph_type", None):
            # snapshot existing graph state
            old_container = self.current_open_view
            old_editor    = getattr(old_container, "graph_editor", None)
            state         = old_editor.get_state() if old_editor else None

            # hide or show banner + inner frames
            if self.banner_visible:
                self.banner_frame.grid_remove()
                self.inner_content_frame.grid_remove()
                self.content_frame.grid_rowconfigure(0, weight=1)
                self.content_frame.grid_rowconfigure(1, weight=0)
                self.banner_visible = False
                self.banner_toggle_btn.configure(text="▼")
            else:
                self.banner_frame.grid(row=0, column=0, sticky="ew")
                self.inner_content_frame.grid(row=1, column=0, sticky="nsew")
                display_pcs_in_banner(
                    self.banner_frame,
                    {pc["Name"]: pc for pc in self.pc_wrapper.load_items()}
                )
                self.inner_content_frame.grid_rowconfigure(0, weight=1)
                self.inner_content_frame.grid_columnconfigure(0, weight=1)
                self.content_frame.grid_rowconfigure(0, weight=0)
                self.content_frame.grid_rowconfigure(1, weight=1)
                self.banner_visible = True
                self.banner_toggle_btn.configure(text="▲")

            # destroy the old container (it was still parented in the wrong frame)
            old_container.destroy()

            # now re‐create the same graph under the correct container
            parent = self.get_content_container()
            new_container = ctk.CTkFrame(parent)
            new_container.grid(row=0, column=0, sticky="nsew")
            parent.grid_rowconfigure(0, weight=1)
            parent.grid_columnconfigure(0, weight=1)

            # re‐instantiate the proper editor type, then restore its state
            if self._graph_type == 'npc':
                editor = NPCGraphEditor(new_container, self.npc_wrapper, self.faction_wrapper)
            elif self._graph_type == 'pc':
                editor = PCGraphEditor(new_container, self.pc_wrapper, self.faction_wrapper)
            elif self._graph_type == 'faction':
                editor = FactionGraphEditor(new_container, self.faction_wrapper)
            else:  # 'scenario'
                editor = ScenarioGraphEditor(
                    new_container,
                    GenericModelWrapper("scenarios"),
                    GenericModelWrapper("npcs"),
                    GenericModelWrapper("creatures"),
                    GenericModelWrapper("places")
                )

            editor.pack(fill="both", expand=True)
            if state is not None and hasattr(editor, "set_state"):
                editor.set_state(state)

            # save the new container/editor
            new_container.graph_editor = editor
            self.current_open_view     = new_container
            # leave current_open_entity = None

            return  # end of graph‐mode toggle
        if self.banner_visible:
            # COLLAPSE BANNER
            if self.banner_frame.winfo_exists():
                self.banner_frame.grid_remove()
            if self.inner_content_frame.winfo_exists():
                self.inner_content_frame.grid_remove()

            if self.current_open_view:
                # Save entity and then destroy
                entity = self.current_open_entity
                self.current_open_view.destroy()

                # Re-create content in content_frame
                self.current_open_view = ctk.CTkFrame(self.content_frame)
                self.current_open_view.grid(row=0, column=0, sticky="nsew")

                wrapper = GenericModelWrapper(entity)
                template = load_template(entity)
                view = GenericListView(self.current_open_view, wrapper, template)
                view.pack(fill="both", expand=True)

                load_button = ctk.CTkButton(
                    self.current_open_view,
                    text=f"Load {entity.capitalize()}",
                    command=lambda: self.load_items_from_json(view, entity)
                )
                load_button.pack(side="right", padx=(5,5))
                # Assuming `editor_window` is your CTkToplevel or CTkFrame
                save_btn = ctk.CTkButton(
                    self.current_open_view,
                    text=f"Save {entity.capitalize()}",
                    command=lambda: self.save_items_to_json(view, entity)
                )
                save_btn.pack(side="right", padx=(5,5))

            self.content_frame.grid_rowconfigure(0, weight=1)
            self.content_frame.grid_rowconfigure(1, weight=0)

            self.banner_visible = False
            self.banner_toggle_btn.configure(text="▼")
        else:
            # EXPAND BANNER
            if not self.banner_frame.winfo_exists():
                self.banner_frame = ctk.CTkFrame(self.content_frame, height=150, fg_color="#444")

            if not self.inner_content_frame.winfo_exists():
                self.inner_content_frame = ctk.CTkFrame(self.content_frame, fg_color="#222")

            self.banner_frame.grid(row=0, column=0, sticky="ew")
            self.inner_content_frame.grid(row=1, column=0, sticky="nsew")
            pcs_items = {pc["Name"]: pc for pc in self.pc_wrapper.load_items()}
            display_pcs_in_banner(self.banner_frame, pcs_items)

            # ✅ CRITICAL FIX: make inner_content_frame fully expandable
            self.inner_content_frame.grid_rowconfigure(0, weight=1)
            self.inner_content_frame.grid_columnconfigure(0, weight=1)

            if self.current_open_view:
                entity = self.current_open_entity
                self.current_open_view.destroy()

                self.current_open_view = ctk.CTkFrame(self.inner_content_frame)
                self.current_open_view.grid(row=0, column=0, sticky="nsew")

                wrapper = GenericModelWrapper(entity)
                template = load_template(entity)
                view = GenericListView(self.current_open_view, wrapper, template)
                view.pack(fill="both", expand=True)

                load_button = ctk.CTkButton(
                    self.current_open_view,
                    text=f"Load {entity.capitalize()}",
                    command=lambda: self.load_items_from_json(view, entity)
                )
                load_button.pack(side="right", padx=(5,5))
                # Assuming `editor_window` is your CTkToplevel or CTkFrame
                save_btn = ctk.CTkButton(
                    self.current_open_view,
                    text=f"Save {entity.capitalize()}",
                    command=lambda: self.save_items_to_json(view, entity)
                )
                save_btn.pack(side="right", padx=(5,5))

            self.content_frame.grid_rowconfigure(0, weight=0)
            self.content_frame.grid_rowconfigure(1, weight=1)

            self.banner_visible = True
            self.banner_toggle_btn.configure(text="▲")

    def get_content_container(self):
        """Choose correct parent depending on banner state."""
        if self.banner_visible:
            return self.inner_content_frame
        else:
            return self.content_frame
    def create_exit_button(self):
        exit_button = ctk.CTkButton(self, text="✕", command=self.destroy,
                                    fg_color="red", hover_color="#AA0000",
                                    width=20, height=20, corner_radius=15)
        exit_button.place(relx=0.9999, rely=0.01, anchor="ne")

    def load_model_config(self):
        self.models_path = ConfigHelper.get("Paths", "models_path",
                                            fallback=r"E:\SwarmUI\SwarmUI\Models\Stable-diffusion")
        self.model_options = get_available_models()
        log_debug(
            f"Models path resolved to {self.models_path}",
            func_name="main_window.MainWindow.load_model_config",
        )
        log_info(
            f"Loaded {len(self.model_options)} available AI models",
            func_name="main_window.MainWindow.load_model_config",
        )

    def init_wrappers(self):
        self.place_wrapper = GenericModelWrapper("places")
        self.npc_wrapper = GenericModelWrapper("npcs")
        self.pc_wrapper = GenericModelWrapper("pcs")
        self.faction_wrapper = GenericModelWrapper("factions")
        self.object_wrapper = GenericModelWrapper("objects")
        self.creature_wrapper = GenericModelWrapper("creatures")
        self.clues_wrapper = GenericModelWrapper("clues")
        self.informations_wrapper = GenericModelWrapper("informations")
        self.maps_wrapper = GenericModelWrapper("maps")
        log_info("Entity wrappers initialized", func_name="main_window.MainWindow.init_wrappers")

    def open_faction_graph_editor(self):
        self._graph_type = 'faction'
        self.current_gm_view = None
        self.clear_current_content()
        self.banner_toggle_btn.configure(state="normal")
        parent = self.get_content_container()

        container = ctk.CTkFrame(parent)
        container.grid(row=0, column=0, sticky="nsew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        editor = FactionGraphEditor(container, self.faction_wrapper)
        editor.pack(fill="both", expand=True)

        # keep both container and editor so we can snapshot/restore
        container.graph_editor = editor
        self.current_open_view   = container
        self.current_open_entity = None
        

    # =============================================================
    # Methods Called by Icon Buttons (Event Handlers)
    # =============================================================
    def clear_current_content(self):
        if self.banner_visible:
            # If banner is visible, clear only inner_content_frame
            for widget in self.inner_content_frame.winfo_children():
                widget.destroy()
        else:
            # If banner is hidden, clear ONLY dynamic children of content_frame, NOT banner_frame
            for widget in self.content_frame.winfo_children():
                if widget not in (self.banner_frame, self.inner_content_frame):
                    widget.destroy()

    def move_current_view(self):
        """Move the current open view to the correct container based on banner state."""
        if self.current_open_view is not None:
            try:
                self.current_open_view.grid_forget()
            except tk.TclError:
                # If the widget was destroyed (because it was inside inner_content_frame), clear it
                self.current_open_view = None
                return

            parent = self.get_content_container()
            self.current_open_view.master = parent
            self.current_open_view.grid(row=0, column=0, sticky="nsew")

    def open_entity(self, entity):
        self.clear_current_content()
        target_parent = self.get_content_container()
        self.banner_toggle_btn._state="normal"
        container = ctk.CTkFrame(target_parent)
        container.grid(row=0, column=0, sticky="nsew")
        self.current_open_view = container
        self.current_open_entity = entity  # ✅ Add this clearly!

        wrapper = GenericModelWrapper(entity)
        template = load_template(entity)
        view = GenericListView(container, wrapper, template)
        view.pack(fill="both", expand=True)

        load_button = ctk.CTkButton(
            container,
            text=f"Load {entity.capitalize()}",
            command=lambda: self.load_items_from_json(view, entity)
        )
        load_button.pack(side="right", padx=(5,5))
        # Assuming `editor_window` is your CTkToplevel or CTkFrame
        save_btn = ctk.CTkButton(
            container,
            text=f"Save {entity.capitalize()}",
            command=lambda: self.save_items_to_json(view, entity)
        )
        save_btn.pack(side="right", padx=(5,5))
    
    def save_items_to_json(self, view, entity_name):
        # 1) Ask the user where to save
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title=f"Export {entity_name.capitalize()} to JSON"
        )
        if not path:
            return  # user hit “Cancel”

        # 2) Grab the items from the view if possible…
        try:
            # GenericListView *might* have a method or attribute that holds its current items
            items = view.get_items()                # ← if you’ve added a get_items()
        except AttributeError:
            try:
                items = view.items                  # ← or maybe it’s stored in view.items
            except Exception:
                # 3) …otherwise fall back on the DB
                wrapper = GenericModelWrapper(entity_name)
                items   = wrapper.load_items()

        # 4) Serialize to JSON
        data = { entity_name: items }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save {entity_name}:\n{e}")
            return

        # 5) Let the user know it worked
        messagebox.showinfo("Export Successful", f"Wrote {len(items)} {entity_name} to:\n{path}")

    def load_items_from_json(self, view, entity_name):
        file_path = filedialog.askopenfilename(
            title=f"Load {entity_name.capitalize()} from JSON",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                items = data.get(entity_name, [])
                view.add_items(items)
                messagebox.showinfo("Success", f"{len(items)} {entity_name} loaded successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load {entity_name}: {e}")

    def open_gm_screen(self):
        # 1) Clear any existing content
        self.clear_current_content()
        # 2) Load all scenarios
        scenario_wrapper = GenericModelWrapper("scenarios")
        scenarios = scenario_wrapper.load_items()
        if not scenarios:
            messagebox.showwarning("No Scenarios", "No scenarios available.")
            return

        # 3) Ensure the PC‐banner is shown and up to date
        if getattr(self, 'banner_frame', None) and self.banner_frame.winfo_exists():
            if not self.banner_frame.winfo_ismapped():
                self.banner_frame.pack(fill='x')
        else:
            # banner_frame was destroyed (or never created): re-create it
            self.banner_frame = self._create_banner_frame()
            self.banner_frame.pack(fill='x')
        pcs_items = {pc["Name"]: pc for pc in self.pc_wrapper.load_items()}
        if pcs_items:
            display_pcs_in_banner(self.banner_frame, pcs_items)

        # 4) Prepare inner content area
        self.inner_content_frame.grid(row=1, column=0, sticky="nsew")
        for w in self.inner_content_frame.winfo_children():
            w.destroy()
        parent = self.inner_content_frame

        # 5) Callback to open a selected scenario in detail
        def on_scenario_select(entity_type, entity_name):
            selected = next(
                (s for s in scenarios
                if s.get("Name", s.get("Title", "")) == entity_name),
                None
            )
            if not selected:
                messagebox.showwarning("Not Found", f"Scenario '{entity_name}' not found.")
                return
            # clear list and show scenario detail
            for w in parent.winfo_children():
                w.destroy()
            detail_container = ctk.CTkFrame(parent)
            detail_container.grid(row=0, column=0, sticky="nsew")
            view = GMScreenView(detail_container, scenario_item=selected)
            view.pack(fill="both", expand=True)
            # track the active GM-screen view for our Ctrl+F handler
            self.current_gm_view = view

        # 6) Insert the generic list‐selection view
        list_selection = GenericListSelectionView(
            parent,
            "scenarios",
            scenario_wrapper,
            load_template("scenarios"),
            on_select_callback=on_scenario_select
        )
        list_selection.pack(fill="both", expand=True)
        self.current_gm_view = None
        # 7) Lock banner and configure grid weights
        self.banner_visible = True
        self.banner_toggle_btn.configure(text="▲")
        self.banner_toggle_btn._state = "disabled"

        # Make row 0 (banner) fixed height, row 1 (content) expand
        self.content_frame.grid_rowconfigure(0, weight=0)
        self.content_frame.grid_rowconfigure(1, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Make the inner_content_frame fully fill its cell
        self.inner_content_frame.grid_rowconfigure(0, weight=1)
        self.inner_content_frame.grid_columnconfigure(0, weight=1)

    def open_npc_graph_editor(self):
        self._graph_type = 'npc'
        self.current_gm_view = None
        self.clear_current_content()
        self.banner_toggle_btn.configure(state="normal")
        parent = self.get_content_container()

        container = ctk.CTkFrame(parent)
        container.grid(row=0, column=0, sticky="nsew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        editor = NPCGraphEditor(container, self.npc_wrapper, self.faction_wrapper)
        editor.pack(fill="both", expand=True)

        # keep both container and editor so we can snapshot/restore
        container.graph_editor = editor
        self.current_open_view   = container
        self.current_open_entity = None


    def open_pc_graph_editor(self):
        self._graph_type = 'pc'
        self.current_gm_view = None
        self.clear_current_content()
        self.banner_toggle_btn.configure(state="normal")
        parent = self.get_content_container()

        container = ctk.CTkFrame(parent)
        container.grid(row=0, column=0, sticky="nsew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        editor = PCGraphEditor(container, self.pc_wrapper, self.faction_wrapper)
        editor.pack(fill="both", expand=True)

        container.graph_editor = editor
        self.current_open_view   = container
        self.current_open_entity = None


    def open_world_map(self):
        """Launch the World Map nested navigation window."""
        log_info("Opening World Map window", func_name="main_window.MainWindow.open_world_map")
        existing = getattr(self, "_world_map_window", None)
        if existing and existing.winfo_exists():
            existing.focus_force()
            existing.lift()
            existing.attributes("-topmost", True)
            existing.after_idle(lambda: existing.attributes("-topmost", False))
            return
        window = WorldMapWindow(self)
        window.lift()
        window.focus_force()
        window.attributes("-topmost", True)
        window.after_idle(lambda: window.attributes("-topmost", False))
        self._world_map_window = window

    def open_scenario_graph_editor(self):
        self._graph_type = 'scenario'
        self.current_gm_view = None
        self.clear_current_content()
        self.banner_toggle_btn.configure(state="normal")
        parent = self.get_content_container()

        container = ctk.CTkFrame(parent)
        container.grid(row=0, column=0, sticky="nsew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        editor = ScenarioGraphEditor(
            container,
            GenericModelWrapper("scenarios"),
            GenericModelWrapper("npcs"),
            GenericModelWrapper("creatures"),
            GenericModelWrapper("places")
        )
        editor.pack(fill="both", expand=True)

        container.graph_editor = editor
        self.current_open_view   = container
        self.current_open_entity = None

    def open_scene_flow_viewer(self):
        from modules.scenarios.scene_flow_viewer import SceneFlowViewerWindow

        if getattr(self, "_scene_flow_window", None) and self._scene_flow_window.winfo_exists():
            try:
                self._scene_flow_window.focus()
                self._scene_flow_window.lift()
            except Exception:
                pass
            return

        def _on_close():
            self._scene_flow_window = None

        window = SceneFlowViewerWindow(
            self,
            scenario_wrapper=GenericModelWrapper("scenarios"),
            npc_wrapper=GenericModelWrapper("npcs"),
            creature_wrapper=GenericModelWrapper("creatures"),
            place_wrapper=GenericModelWrapper("places"),
            on_close=_on_close,
        )
        self._scene_flow_window = window

    def export_foundry(self):
        preview_and_export_foundry(self)

    def open_scenario_importer(self):
        self.clear_current_content()
        container = ctk.CTkFrame(self.content_frame)
        container.grid(row=0, column=0, sticky="nsew")
        ScenarioImportWindow(container)

    def open_creature_importer(self):
        from modules.creatures.creature_importer import CreatureImportWindow

        self.clear_current_content()
        container = ctk.CTkFrame(self.content_frame)
        container.grid(row=0, column=0, sticky="nsew")
        CreatureImportWindow(container)

    def open_scenario_generator(self):
        self.clear_current_content()
        parent = self.get_content_container()
        container = ScenarioGeneratorView(parent)
        container.grid(row=0, column=0, sticky="nsew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        self.current_open_view = container
        self.current_open_entity = None

    

    def change_database_storage(self):
        # 1) Pick or create .db
        # Ensure we start file dialogs in the Campaigns directory under the app directory
        try:
            # If packaged (e.g., PyInstaller), use the executable directory; else use this file's directory
            app_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        except Exception:
            app_dir = os.getcwd()
        campaigns_dir = os.path.join(app_dir, "Campaigns")
        os.makedirs(campaigns_dir, exist_ok=True)

        choice = messagebox.askquestion(
            "Change Database",
            "Do you want to open an existing database file?"
        )
        if choice == "yes":
            new_db_path = filedialog.askopenfilename(
                title="Select Database",
                initialdir=campaigns_dir,
                filetypes=[("SQLite DB Files", "*.db"), ("All Files", "*.*")]
            )
        else:
            # Ask for a campaign/database name, create a subdirectory under Campaigns,
            # and place the new DB file inside that subdirectory.
            while True:
                name = simpledialog.askstring("New Campaign", "Enter campaign name:", parent=self)
                if name is None:
                    new_db_path = None
                    break
                safe = "".join(ch for ch in name.strip() if ch.isalnum() or ch in ("_","-"," ")).strip()
                safe = safe.replace(" ", "_")
                if not safe:
                    messagebox.showwarning("Invalid Name", "Please enter a valid campaign name.")
                    continue
                target_dir = os.path.join(campaigns_dir, safe)
                try:
                    os.makedirs(target_dir, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create folder:\n{e}")
                    continue
                new_db_path = os.path.join(target_dir, f"{safe}.db")
                break
        if not new_db_path:
            return

        # 2) Persist to config so get_connection()/init_db() will pick it up
        ConfigHelper.set("Database", "path", new_db_path)

        # 3) If new DB, seed campaign-local templates from defaults
        is_new_db = (choice != "yes")
        if is_new_db:
            try:
                from shutil import copyfile
                entities = ("pcs","npcs","scenarios","factions","places","objects","creatures","informations","clues","maps")
                camp_dir = os.path.abspath(os.path.dirname(new_db_path))
                tpl_dir = os.path.join(camp_dir, "templates")
                os.makedirs(tpl_dir, exist_ok=True)
                for e in entities:
                    src = os.path.join("modules", e, f"{e}_template.json")
                    dst = os.path.join(tpl_dir, f"{e}_template.json")
                    try:
                        if not os.path.exists(dst):
                            copyfile(src, dst)
                    except Exception:
                        pass
            except Exception:
                pass

        # 4) Open a fresh connection and create all tables based on JSON templates
        conn = sqlite3.connect(new_db_path)
        cursor = conn.cursor()

        # For each entity, load its template and build a CREATE TABLE
        for entity in ("pcs","npcs", "scenarios", "factions",
                    "places", "objects", "creatures", "informations","clues", "maps"):

            tpl = load_template(entity)   # loads modules/<entity>/<entity>_template.json
            cols = []
            for i, field in enumerate(tpl["fields"]):
                name = field["name"]
                ftype = field["type"]
                # map JSON -> SQL
                if ftype in ("text", "longtext"):
                    sql_type = "TEXT"
                elif ftype == "boolean":
                    sql_type = "BOOLEAN"
                elif ftype == "list":
                    # we store lists as JSON strings
                    sql_type = "TEXT"
                elif ftype == "file":
                    # we store lists as JSON strings
                    sql_type = "TEXT"
                else:
                    sql_type = "TEXT"

                # first field is primary key
                if i == 0:
                    cols.append(f"{name} {sql_type} PRIMARY KEY")
                else:
                    cols.append(f"{name} {sql_type}")

            ddl = f"CREATE TABLE IF NOT EXISTS {entity} ({', '.join(cols)})"
            cursor.execute(ddl)

        # 4) Re‑create the graph viewer tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_name TEXT,
                x INTEGER,
                y INTEGER,
                color TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_name1 TEXT,
                npc_name2 TEXT,
                text TEXT,
                arrow_mode TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shapes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                x INTEGER,
                y INTEGER,
                w INTEGER,
                h INTEGER,
                color TEXT,
                tag TEXT,
                z INTEGER
            )
        """)

        conn.commit()
        conn.close()

        # 5) Re‑initialise your in‑memory wrappers & update the label
        #    (and run any schema‐migrations if you still need them)
        self.place_wrapper    = GenericModelWrapper("places")
        self.npc_wrapper      = GenericModelWrapper("npcs")
        self.pc_wrapper      = GenericModelWrapper("pcs")
        self.faction_wrapper  = GenericModelWrapper("factions")
        self.object_wrapper   = GenericModelWrapper("objects")
        self.creature_wrapper = GenericModelWrapper("creatures")
        self.information_wrapper = GenericModelWrapper("informations")
        self.clues_wrapper = GenericModelWrapper("clues")

        db_name = os.path.splitext(os.path.basename(new_db_path))[0]
        self.db_name_label.configure(text=db_name)
        # Update tooltip text to reflect new full path
        try:
            full_path = os.path.abspath(new_db_path)
            if getattr(self, 'db_tooltip', None) is None:
                self.db_tooltip = ToolTip(self.db_name_label, full_path)
            else:
                # Update text on existing tooltip
                self.db_tooltip.text = full_path
        except Exception:
            self.db_tooltip = None

    def select_swarmui_path(self):
        folder = filedialog.askdirectory(title="Select SwarmUI Path")
        if folder:
            ConfigHelper.set("Paths", "swarmui_path", folder)
            messagebox.showinfo("SwarmUI Path Set", f"SwarmUI path set to:\n{folder}")

    def launch_swarmui(self):
        global SWARMUI_PROCESS
        swarmui_path = ConfigHelper.get("Paths", "swarmui_path", fallback=r"E:\SwarmUI\SwarmUI")
        SWARMUI_CMD = os.path.join(swarmui_path, "launch-windows.bat")
        env = os.environ.copy()
        env.pop('VIRTUAL_ENV', None)
        if SWARMUI_PROCESS is None or SWARMUI_PROCESS.poll() is not None:
            try:
                SWARMUI_PROCESS = subprocess.Popen(
                    SWARMUI_CMD,
                    shell=True,
                    cwd=swarmui_path,
                    env=env
                )
                time.sleep(20.0)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to launch SwarmUI: {e}")

    def cleanup_swarmui(self):
        global SWARMUI_PROCESS
        if SWARMUI_PROCESS is not None and SWARMUI_PROCESS.poll() is None:
            SWARMUI_PROCESS.terminate()

    # ------------------------------------------------------
    # Unified Generate Portraits for NPCs and Creatures
    # ------------------------------------------------------
    def generate_missing_portraits(self):
        top = ctk.CTkToplevel(self)
        top.title("Generate Portraits")
        top.geometry("300x150")
        top.transient(self)
        top.grab_set()
        # Use ctk.StringVar (not CTkStringVar)
        selection = ctk.StringVar(value="NPC")
        ctk.CTkLabel(top, text="Generate portraits for:").pack(pady=10)
        ctk.CTkRadioButton(top, text="NPCs", variable=selection, value="NPC").pack(pady=5)
        ctk.CTkRadioButton(top, text="Creatures", variable=selection, value="Creature").pack(pady=5)
        def on_confirm():
            choice = selection.get()
            top.destroy()
            if choice == "NPC":
                self.generate_missing_npc_portraits()
            else:
                self.generate_missing_creature_portraits()
        ctk.CTkButton(top, text="Continue", command=on_confirm).pack(pady=10)

    def generate_missing_npc_portraits(self):
        def confirm_model_and_continue():
            ConfigHelper.set("LastUsed", "model", self.selected_model.get())
            top.destroy()
            self.generate_portraits_continue_npcs()
        top = ctk.CTkToplevel(self)
        top.title("Select AI Model for NPCs")
        top.geometry("400x200")
        top.transient(self)
        top.grab_set()
        ctk.CTkLabel(top, text="Select AI Model to use for NPC portrait generation:").pack(pady=20)
        last_model = ConfigHelper.get("LastUsed", "model", fallback=None)
        # Use ctk.StringVar
        if last_model in self.model_options:
            self.selected_model = ctk.StringVar(value=last_model)
        else:
            self.selected_model = ctk.StringVar(value=self.model_options[0])
        ctk.CTkOptionMenu(top, values=self.model_options, variable=self.selected_model).pack(pady=10)
        ctk.CTkButton(top, text="Continue", command=confirm_model_and_continue).pack(pady=10)

    def generate_portraits_continue_npcs(self):
        db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM npcs")
        npc_rows = cursor.fetchall()
        modified = False
        for npc in npc_rows:
            portrait = npc["Portrait"] if npc["Portrait"] is not None else ""
            if not portrait.strip():
                npc_dict = dict(npc)
                self.generate_portrait_for_npc(npc_dict)
                if npc_dict.get("Portrait"):
                    cursor.execute("UPDATE npcs SET Portrait = ? WHERE Name = ?", (npc_dict["Portrait"], npc["Name"]))
                    modified = True
        if modified:
            conn.commit()
            print("Updated NPC database with generated portraits.")
        else:
            print("No NPCs were missing portraits.")
        conn.close()

    def generate_missing_creature_portraits(self):
        def confirm_model_and_continue():
            ConfigHelper.set("LastUsed", "model", self.selected_model.get())
            top.destroy()
            self.generate_portraits_continue_creatures()
        top = ctk.CTkToplevel(self)
        top.title("Select AI Model for Creatures")
        top.geometry("400x200")
        top.transient(self)
        top.grab_set()
        ctk.CTkLabel(top, text="Select AI Model to use for creature portrait generation:").pack(pady=20)
        last_model = ConfigHelper.get("LastUsed", "model", fallback=None)
        if last_model in self.model_options:
            self.selected_model = ctk.StringVar(value=last_model)
        else:
            self.selected_model = ctk.StringVar(value=self.model_options[0])
        ctk.CTkOptionMenu(top, values=self.model_options, variable=self.selected_model).pack(pady=10)
        ctk.CTkButton(top, text="Continue", command=confirm_model_and_continue).pack(pady=10)

    def generate_portraits_continue_creatures(self):
        db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM creatures")
        creature_rows = cursor.fetchall()
        modified = False
        for creature in creature_rows:
            portrait = creature["Portrait"] if creature["Portrait"] is not None else ""
            if not portrait.strip():
                creature_dict = dict(creature)
                self.generate_portrait_for_creature(creature_dict)
                if creature_dict.get("Portrait"):
                    cursor.execute("UPDATE creatures SET Portrait = ? WHERE Name = ?", (creature_dict["Portrait"], creature_dict["Name"]))
                    modified = True
        if modified:
            conn.commit()
            print("Updated creature database with generated portraits.")
        else:
            print("No creatures were missing portraits.")
        conn.close()

    def generate_portrait_for_npc(self, npc):
        self.launch_swarmui()
        SWARM_API_URL = "http://127.0.0.1:7801"
        try:
            session_url = f"{SWARM_API_URL}/API/GetNewSession"
            session_response = requests.post(session_url, json={}, headers={"Content-Type": "application/json"})
            session_data = session_response.json()
            session_id = session_data.get("session_id")
            if not session_id:
                print(f"Failed to obtain session ID for NPC {npc.get('Name', 'Unknown')}")
                return
            npc_name = npc.get("Name", "Unknown")
            npc_role = npc.get("Role", "Unknown")
            npc_faction = npc.get("Factions", "Unknown")
            npc_desc = npc.get("Description", "Unknown")
            npc_desc = text_helpers.format_longtext(npc_desc)
            prompt = f"{npc_name} {npc_desc} {npc_role} {npc_faction}"
            prompt_data = {
                "session_id": session_id,
                "images": 1,
                "prompt": prompt,
                "negativeprompt": ("blurry, low quality, comics style, mangastyle, paint style, watermark, ugly, "
                                "monstrous, too many fingers, too many legs, too many arms, bad hands, "
                                "unrealistic weapons, bad grip on equipment, nude"),
                "model": self.selected_model.get(),
                "width": 1024,
                "height": 1024,
                "cfgscale": 9,
                "steps": 20,
                "seed": -1
            }
            generate_url = f"{SWARM_API_URL}/API/GenerateText2Image"
            image_response = requests.post(generate_url, json=prompt_data, headers={"Content-Type": "application/json"})
            image_data = image_response.json()
            images = image_data.get("images")
            if not images or len(images) == 0:
                print(f"Image generation failed for NPC '{npc_name}'")
                return
            image_url = f"{SWARM_API_URL}/{images[0]}"
            downloaded_image = requests.get(image_url)
            if downloaded_image.status_code != 200:
                print(f"Failed to download generated image for NPC '{npc_name}'")
                return
            output_filename = f"{npc_name.replace(' ', '_')}_portrait.png"
            with open(output_filename, "wb") as f:
                f.write(downloaded_image.content)
            GENERATED_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "generated")
            os.makedirs(GENERATED_FOLDER, exist_ok=True)
            shutil.copy(output_filename, os.path.join(GENERATED_FOLDER, output_filename))
            npc["Portrait"] = self.copy_and_resize_portrait(npc, output_filename)
            os.remove(output_filename)
            print(f"Generated portrait for NPC '{npc_name}'")
        except Exception as e:
            print(f"Error generating portrait for NPC '{npc.get('Name', 'Unknown')}': {e}")

    def generate_portrait_for_creature(self, creature):
        self.launch_swarmui()
        SWARM_API_URL = "http://127.0.0.1:7801"
        try:
            session_url = f"{SWARM_API_URL}/API/GetNewSession"
            session_response = requests.post(session_url, json={}, headers={"Content-Type": "application/json"})
            session_data = session_response.json()
            session_id = session_data.get("session_id")
            if not session_id:
                print(f"Failed to obtain session ID for Creature {creature.get('Name', 'Unknown')}")
                return
            creature_name = creature.get("Name", "Unknown")
            creature_desc = creature.get("Description", "Unknown")
            stats = creature.get("Stats", "")
            creature_desc_formatted = text_helpers.format_longtext(creature_desc)
            prompt = f"{creature_name} {creature_desc_formatted} {stats}"
            prompt_data = {
                "session_id": session_id,
                "images": 1,
                "prompt": prompt,
                "negativeprompt": ("blurry, low quality, comics style, mangastyle, paint style, watermark, ugly, "
                                "monstrous, too many fingers, too many legs, too many arms, bad hands, "
                                "unrealistic weapons, bad grip on equipment, nude"),
                "model": self.selected_model.get(),
                "width": 1024,
                "height": 1024,
                "cfgscale": 9,
                "steps": 20,
                "seed": -1
            }
            generate_url = f"{SWARM_API_URL}/API/GenerateText2Image"
            image_response = requests.post(generate_url, json=prompt_data, headers={"Content-Type": "application/json"})
            image_data = image_response.json()
            images = image_data.get("images")
            if not images or len(images) == 0:
                print(f"Image generation failed for Creature '{creature_name}'")
                return
            image_url = f"{SWARM_API_URL}/{images[0]}"
            downloaded_image = requests.get(image_url)
            if downloaded_image.status_code != 200:
                print(f"Failed to download generated image for Creature '{creature_name}'")
                return
            output_filename = f"{creature_name.replace(' ', '_')}_portrait.png"
            with open(output_filename, "wb") as f:
                f.write(downloaded_image.content)
            GENERATED_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "generated")
            os.makedirs(GENERATED_FOLDER, exist_ok=True)
            shutil.copy(output_filename, os.path.join(GENERATED_FOLDER, output_filename))
            creature["Portrait"] = self.copy_and_resize_portrait(creature, output_filename)
            os.remove(output_filename)
            print(f"Generated portrait for Creature '{creature_name}'")
        except Exception as e:
            print(f"Error generating portrait for Creature '{creature.get('Name', 'Unknown')}': {e}")

    def copy_and_resize_portrait(self, entity, src_path):
        campaign_dir = ConfigHelper.get_campaign_dir()
        PORTRAIT_FOLDER = os.path.join(campaign_dir, "assets", "portraits")
        MAX_PORTRAIT_SIZE = (1024, 1024)
        os.makedirs(PORTRAIT_FOLDER, exist_ok=True)
        name = entity.get("Name", "Unnamed").replace(" ", "_")
        ext = os.path.splitext(src_path)[-1].lower()
        dest_filename = f"{name}_{id(self)}{ext}"
        dest_path = os.path.join(PORTRAIT_FOLDER, dest_filename)
        with Image.open(src_path) as img:
            img = img.convert("RGB")
            img.thumbnail(MAX_PORTRAIT_SIZE)
            img.save(dest_path)
        return dest_path

    def import_portraits_from_directory(self):
        """Match and import portraits from a directory for all portrait-capable entities."""
        directory = filedialog.askdirectory(title="Select Portrait Directory")
        if not directory:
            log_info(
                "Portrait import cancelled: no directory selected",
                func_name="main_window.MainWindow.import_portraits_from_directory",
            )
            return

        supported_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
        image_candidates = []

        for root, _dirs, files in os.walk(directory):
            for file_name in files:
                ext = os.path.splitext(file_name)[1].lower()
                if ext not in supported_exts:
                    continue
                base_name = os.path.splitext(file_name)[0]
                normalized = self.normalize_name(base_name)
                cleaned = re.sub(
                    r"\b(portrait|token|image|img|picture|photo|pic)\b",
                    " ",
                    normalized,
                )
                cleaned = " ".join(cleaned.split())
                candidate = cleaned or normalized
                if not candidate:
                    continue

                path = os.path.join(root, file_name)
                image_candidates.append(
                    {
                        "normalized": candidate,
                        "compact": candidate.replace(" ", ""),
                        "path": path,
                        "display": file_name,
                        "relative": os.path.relpath(path, directory),
                    }
                )

        if not image_candidates:
            log_info(
                "Portrait import aborted: no compatible images discovered",
                func_name="main_window.MainWindow.import_portraits_from_directory",
            )
            messagebox.showinfo(
                "Import Portraits",
                "No image files were found in the selected directory.",
            )
            return

        replace_existing = messagebox.askyesno(
            "Import Portraits",
            "Replace existing portraits when a match is found?\n\n"
            "Choose 'Yes' to overwrite existing portraits, or 'No' to update only missing ones.",
            icon="question",
            default="no",
        )

        entity_configs = [
            ("npcs", "Name"),
            ("pcs", "Name"),
            ("creatures", "Name"),
            ("places", "Name"),
            ("objects", "Name"),
            ("clues", "Name"),
        ]
        display_names = {
            "npcs": "NPCs",
            "pcs": "PCs",
            "creatures": "Creatures",
            "places": "Places",
            "objects": "Objects",
            "clues": "Clues",
        }

        def compute_matches(normalized_name):
            matches = []
            if not normalized_name:
                return matches

            compact_name = normalized_name.replace(" ", "")
            for candidate in image_candidates:
                score_full = SequenceMatcher(
                    None,
                    normalized_name,
                    candidate["normalized"],
                ).ratio()
                if compact_name:
                    score_compact = SequenceMatcher(
                        None,
                        compact_name,
                        candidate["compact"],
                    ).ratio()
                else:
                    score_compact = score_full
                score = max(score_full, score_compact)
                matches.append(
                    {
                        "score": score,
                        "path": candidate["path"],
                        "display": candidate["display"],
                        "relative": candidate["relative"],
                        "normalized": candidate["normalized"],
                    }
                )

            matches.sort(key=lambda item: item["score"], reverse=True)
            return matches[:20]

        entity_review_data = []

        db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        total_updates = 0
        skipped_existing = 0
        skipped_low_score = 0
        per_entity_updates = []

        try:
            cursor = conn.cursor()
            for table, key_field in entity_configs:
                cursor.execute(f"SELECT {key_field}, Portrait FROM {table}")
                rows = cursor.fetchall()
                updated_here = 0
                for row in rows:
                    raw_name = row[key_field]
                    if raw_name is None:
                        continue
                    name = str(raw_name).strip()
                    if not name:
                        continue
                    existing_portrait = str(row["Portrait"] or "").strip()
                    normalized_name = self.normalize_name(name)
                    matches = compute_matches(normalized_name)
                    best_match = matches[0] if matches else None
                    best_score = best_match["score"] if best_match else 0.0

                    entity_record = {
                        "table": table,
                        "key_field": key_field,
                        "display_table": display_names.get(table, table.title()),
                        "name": name,
                        "existing_portrait": existing_portrait,
                        "matches": matches,
                        "best_score": best_score,
                        "best_source": best_match["path"] if best_match else "",
                        "status": "Ready to review" if matches else "No portrait suggestions",
                    }
                    entity_review_data.append(entity_record)

                    if existing_portrait and not replace_existing:
                        skipped_existing += 1
                        entity_record["status"] = "Skipped (existing portrait)"
                        continue

                    if not best_match or best_score < 0.85:
                        skipped_low_score += 1
                        if not matches:
                            entity_record["status"] = "No portrait suggestions"
                        else:
                            entity_record["status"] = "No match ≥85%"
                        continue

                    try:
                        new_path = self.copy_and_resize_portrait({"Name": name}, best_match["path"])
                    except Exception as exc:
                        log_exception(
                            f"Failed to copy portrait for {name}: {exc}",
                            func_name="main_window.MainWindow.import_portraits_from_directory",
                        )
                        entity_record["status"] = f"Error importing ({exc})"
                        continue

                    cursor.execute(
                        f"UPDATE {table} SET Portrait = ? WHERE {key_field} = ?",
                        (new_path, name),
                    )
                    updated_here += 1
                    total_updates += 1
                    entity_record["status"] = f"Imported automatically ({best_score * 100:.1f}%)"
                    entity_record["applied_path"] = new_path
                    entity_record["applied_source"] = best_match["path"]
                    entity_record["applied_score"] = best_score
                    log_info(
                        f"Imported portrait for {display_names.get(table, table.title())} '{name}' (score {best_score * 100:.1f}%)",
                        func_name="main_window.MainWindow.import_portraits_from_directory",
                    )

                if updated_here:
                    per_entity_updates.append(
                        f"{display_names.get(table, table.title())}: {updated_here}"
                    )

            if total_updates:
                conn.commit()
            else:
                conn.rollback()

        except Exception as exc:
            conn.rollback()
            log_exception(
                f"Portrait import failed: {exc}",
                func_name="main_window.MainWindow.import_portraits_from_directory",
            )
            messagebox.showerror(
                "Import Portraits",
                f"Portrait import failed:\n{exc}",
            )
            return
        finally:
            conn.close()

        if total_updates:
            log_info(
                f"Imported {total_updates} portraits from directory {directory}",
                func_name="main_window.MainWindow.import_portraits_from_directory",
            )
            summary_lines = [
                "Imported portraits for the following entities:",
                *per_entity_updates,
            ]
            if not per_entity_updates:
                summary_lines.append("(No entities were updated despite successful matches.)")
            if skipped_existing and not replace_existing:
                summary_lines.append(
                    f"Skipped {skipped_existing} entries that already had portraits."
                )
            if skipped_low_score:
                summary_lines.append(
                    f"Skipped {skipped_low_score} entries without a ≥85% name match."
                )
            if image_candidates:
                summary_lines.append(
                    "Review and fine-tune matches in the portrait matcher window that opens next."
                )
            messagebox.showinfo("Import Portraits", "\n".join(summary_lines))
        else:
            log_info(
                "No portraits met the similarity threshold during import",
                func_name="main_window.MainWindow.import_portraits_from_directory",
            )
            details = []
            if skipped_existing and not replace_existing:
                details.append(
                    f"{skipped_existing} entities already had portraits (not replaced)."
                )
            if skipped_low_score:
                details.append(
                    f"{skipped_low_score} entities had no image above the 85% similarity threshold."
                )
            if not details:
                details.append(
                    "Ensure image file names closely match entity names (≥85% similarity)."
                )
            elif image_candidates:
                details.append(
                    "Adjust matches manually in the review window that opens next."
                )
            messagebox.showinfo("Import Portraits", "\n".join(details))

        if image_candidates and entity_review_data:
            self.show_portrait_import_review(entity_review_data, replace_existing)

    def show_portrait_import_review(self, entity_review_data, replace_existing):
        """Display an interactive window to review and fine-tune portrait matches."""

        if not entity_review_data:
            return

        if not any(record.get("matches") for record in entity_review_data):
            return

        review_window = ctk.CTkToplevel(self)
        review_window.title("Portrait Import Review")
        review_window.geometry("1020x620")
        review_window.minsize(900, 520)
        position_window_at_top(review_window)

        review_window.columnconfigure(0, weight=1)
        review_window.rowconfigure(0, weight=1)

        container = ctk.CTkFrame(review_window)
        container.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(2, weight=1)

        title_font = ctk.CTkFont(size=18, weight="bold")
        subtitle_font = ctk.CTkFont(size=13)

        header = ctk.CTkLabel(container, text="Review portrait matches", font=title_font, anchor="w")
        header.grid(row=0, column=0, columnspan=2, sticky="w")

        subheader = ctk.CTkLabel(
            container,
            text=(
                "Double-click an entity to inspect potential portraits. Use the similarity slider to widen or narrow "
                "the suggestions and double-click a portrait to assign it."
            ),
            font=subtitle_font,
            justify="left",
            wraplength=880,
            anchor="w",
        )
        subheader.grid(row=1, column=0, columnspan=2, sticky="we", pady=(4, 12))

        left_frame = ctk.CTkFrame(container)
        left_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        left_label = ctk.CTkLabel(left_frame, text="Entities", anchor="w")
        left_label.grid(row=0, column=0, sticky="we")

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            # Fallback to default theme if clam is unavailable
            pass
        style.configure(
            "PortraitReview.Treeview",
            background="#1e1e1e",
            fieldbackground="#1e1e1e",
            foreground="#f2f2f2",
            bordercolor="#2a2a2a",
            rowheight=26,
        )
        style.configure(
            "PortraitReview.Treeview.Heading",
            background="#2a2a2a",
            foreground="#f2f2f2",
            relief="flat",
        )
        style.map(
            "PortraitReview.Treeview",
            background=[("selected", "#3a7ebf")],
            foreground=[("selected", "#ffffff")],
        )

        columns = ("type", "name", "score", "status")
        tree = ttk.Treeview(
            left_frame,
            columns=columns,
            show="headings",
            style="PortraitReview.Treeview",
            selectmode="browse",
        )
        tree.heading("type", text="Type")
        tree.heading("name", text="Entity")
        tree.heading("score", text="Best match")
        tree.heading("status", text="Status")
        tree.column("type", width=110, anchor="w")
        tree.column("name", width=200, anchor="w")
        tree.column("score", width=110, anchor="center")
        tree.column("status", width=240, anchor="w")

        tree_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.grid(row=1, column=0, sticky="nsew")
        tree_scroll.grid(row=1, column=1, sticky="ns")

        left_hint = ctk.CTkLabel(
            left_frame,
            text="Tip: double-click an entity to load suggested portraits.",
            anchor="w",
            wraplength=360,
            justify="left",
        )
        left_hint.grid(row=2, column=0, columnspan=2, sticky="we", pady=(6, 0))

        detail_frame = ctk.CTkFrame(container)
        detail_frame.grid(row=2, column=1, sticky="nsew")
        detail_frame.grid_columnconfigure(0, weight=1)
        detail_frame.grid_rowconfigure(4, weight=1)

        entity_title_label = ctk.CTkLabel(
            detail_frame,
            text="Select an entity to review matches.",
            font=ctk.CTkFont(size=16, weight="bold"),
            justify="left",
            wraplength=360,
            anchor="w",
        )
        entity_title_label.grid(row=0, column=0, sticky="we")

        detail_status_label = ctk.CTkLabel(
            detail_frame,
            text="",
            justify="left",
            wraplength=360,
            anchor="w",
        )
        detail_status_label.grid(row=1, column=0, sticky="we", pady=(4, 6))

        similarity_frame = ctk.CTkFrame(detail_frame)
        similarity_frame.grid(row=2, column=0, sticky="we")
        similarity_frame.grid_columnconfigure(1, weight=1)

        similarity_label = ctk.CTkLabel(similarity_frame, text="Similarity threshold:")
        similarity_label.grid(row=0, column=0, padx=(0, 6), sticky="w")

        threshold_var = tk.DoubleVar(value=85.0)

        def update_threshold_label(value):
            try:
                numeric = float(value)
            except (TypeError, ValueError, tk.TclError):
                numeric = threshold_var.get()
            threshold_display.configure(text=f"{numeric:.0f}%")

        def on_slider_change(value):
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return
            threshold_var.set(numeric)
            update_threshold_label(numeric)
            populate_match_list()

        slider = ttk.Scale(
            similarity_frame,
            from_=50,
            to=100,
            orient="horizontal",
            command=on_slider_change,
        )
        slider.set(85.0)
        slider.grid(row=0, column=1, sticky="we")

        def on_spin_change():
            try:
                numeric = float(threshold_var.get())
            except (TypeError, ValueError, tk.TclError):
                return
            numeric = min(max(numeric, 50.0), 100.0)
            threshold_var.set(numeric)
            slider.set(numeric)
            update_threshold_label(numeric)
            populate_match_list()

        threshold_spin = tk.Spinbox(
            similarity_frame,
            from_=50,
            to=100,
            textvariable=threshold_var,
            width=5,
            command=on_spin_change,
        )
        threshold_spin.grid(row=0, column=2, padx=(8, 6))
        threshold_spin.bind("<Return>", lambda _event: on_spin_change())
        threshold_spin.bind("<FocusOut>", lambda _event: on_spin_change())

        threshold_display = ctk.CTkLabel(similarity_frame, text="85%")
        threshold_display.grid(row=0, column=3, sticky="e")

        matches_label = ctk.CTkLabel(detail_frame, text="Suggested portraits", anchor="w")
        matches_label.grid(row=3, column=0, sticky="we", pady=(10, 4))

        matches_frame = tk.Frame(detail_frame, bg="#1e1e1e", highlightthickness=1, highlightbackground="#2a2a2a")
        matches_frame.grid(row=4, column=0, sticky="nsew")
        matches_frame.grid_columnconfigure(0, weight=1)
        matches_frame.grid_rowconfigure(0, weight=1)

        match_listbox = tk.Listbox(
            matches_frame,
            activestyle="none",
            selectmode="browse",
            exportselection=False,
            bg="#1e1e1e",
            fg="#f2f2f2",
            highlightthickness=0,
            selectbackground="#3a7ebf",
            selectforeground="#ffffff",
        )
        match_listbox.grid(row=0, column=0, sticky="nsew")

        match_scroll = tk.Scrollbar(matches_frame, orient="vertical", command=match_listbox.yview)
        match_scroll.grid(row=0, column=1, sticky="ns")
        match_listbox.configure(yscrollcommand=match_scroll.set)

        match_info_label = ctk.CTkLabel(
            detail_frame,
            text="Select a portrait to preview.",
            justify="left",
            wraplength=360,
            anchor="w",
        )
        match_info_label.grid(row=5, column=0, sticky="we", pady=(8, 6))

        preview_frame = ctk.CTkFrame(detail_frame)
        preview_frame.grid(row=6, column=0, sticky="we")
        preview_frame.grid_columnconfigure(0, weight=1)

        preview_label = tk.Label(
            preview_frame,
            text="Portrait preview",
            bg="#1e1e1e",
            fg="#f2f2f2",
            width=40,
            height=18,
            anchor="center",
            justify="center",
            wraplength=320,
            relief="ridge",
        )
        preview_label.grid(row=0, column=0, sticky="we")

        assign_button = ctk.CTkButton(
            detail_frame,
            text="Assign Selected Portrait",
            command=lambda: assign_selected_portrait(),
            state="disabled",
        )
        assign_button.grid(row=7, column=0, sticky="we", pady=(12, 6))

        detail_hint_label = ctk.CTkLabel(
            detail_frame,
            text="Tip: double-click a portrait in the list to assign it instantly.",
            wraplength=360,
            justify="left",
            anchor="w",
        )
        detail_hint_label.grid(row=8, column=0, sticky="we")

        tree.tag_configure("auto", foreground="#7bcf8d")
        tree.tag_configure("manual", foreground="#80caff")
        tree.tag_configure("skipped", foreground="#f4c77f")
        tree.tag_configure("error", foreground="#f28b82")

        tree_records: dict[str, dict] = {}
        current_entity: dict | None = None
        match_index_map: list[dict] = []
        preview_image = None

        for record in entity_review_data:
            score_text = (
                f"{record.get('best_score', 0) * 100:.1f}%" if record.get("best_score") else "—"
            )
            status_text = record.get("status") or "Ready to review"
            lowered = status_text.lower()
            tags = []
            if "error" in lowered:
                tags.append("error")
            elif "assigned manually" in lowered:
                tags.append("manual")
            elif "imported automatically" in lowered:
                tags.append("auto")
            elif "skipped" in lowered or "no match" in lowered:
                tags.append("skipped")
            tree_id = tree.insert(
                "",
                "end",
                values=(record.get("display_table"), record.get("name"), score_text, status_text),
                tags=tags if tags else ("default",),
            )
            record["tree_id"] = tree_id
            tree_records[tree_id] = record

        def populate_match_list():
            nonlocal match_index_map, preview_image
            match_listbox.delete(0, "end")
            match_index_map = []
            assign_button.configure(state="disabled")
            preview_image = None
            preview_label.configure(image="", text="Portrait preview")
            preview_label.image = None

            if current_entity is None:
                match_info_label.configure(text="Select an entity to see suggested portraits.")
                return

            matches = current_entity.get("matches") or []
            if not matches:
                match_info_label.configure(text="No portrait suggestions are available for this entity.")
                return

            try:
                threshold = float(threshold_var.get()) / 100.0
            except (TypeError, ValueError, tk.TclError):
                threshold = 0.85

            filtered = [m for m in matches if m.get("score", 0) >= threshold]
            if not filtered:
                filtered = matches[:5]
                if filtered:
                    match_info_label.configure(
                        text="No portraits meet the chosen threshold. Showing the closest matches instead."
                    )
                else:
                    match_info_label.configure(
                        text="No portrait suggestions are available for this entity."
                    )
            else:
                match_info_label.configure(
                    text=f"Showing {len(filtered)} portrait(s) with ≥{threshold_var.get():.0f}% similarity."
                )

            for match in filtered:
                entry_text = f"{match.get('score', 0) * 100:.1f}% · {match.get('display')}"
                match_listbox.insert("end", entry_text)
                match_index_map.append(match)

            if match_index_map:
                match_listbox.selection_set(0)
                on_match_select()

        def on_match_select(event=None):
            nonlocal preview_image
            selection = match_listbox.curselection()
            if not selection:
                assign_button.configure(state="disabled")
                preview_label.configure(image="", text="Portrait preview")
                preview_label.image = None
                return

            match = match_index_map[selection[0]]
            assign_button.configure(state="normal")
            rel_path = match.get("relative") or os.path.basename(match.get("path", ""))
            match_info_label.configure(
                text=f"{match.get('score', 0) * 100:.1f}% similarity\n{rel_path}"
            )

            try:
                with Image.open(match.get("path")) as img:
                    img.thumbnail((340, 340))
                    preview_image = ImageTk.PhotoImage(img)
            except Exception as exc:
                preview_image = None
                preview_label.configure(
                    text=f"Unable to load preview:\n{exc}",
                    image="",
                )
                preview_label.image = None
                assign_button.configure(state="disabled")
                return

            preview_label.configure(image=preview_image, text="")
            preview_label.image = preview_image

        match_listbox.bind("<<ListboxSelect>>", on_match_select)

        def show_entity_details(record: dict | None):
            nonlocal current_entity
            current_entity = record
            if not record:
                entity_title_label.configure(text="Select an entity to review matches.")
                detail_status_label.configure(text="")
                match_info_label.configure(text="Select a portrait to preview.")
                match_listbox.delete(0, "end")
                assign_button.configure(state="disabled")
                preview_label.configure(image="", text="Portrait preview")
                preview_label.image = None
                return

            entity_title_label.configure(
                text=f"{record.get('display_table')}: {record.get('name')}"
            )
            detail_status_label.configure(text=record.get("status") or "Ready to review")

            default_threshold = 85.0
            if record.get("best_score"):
                default_threshold = min(100.0, max(50.0, round(record["best_score"] * 100)))

            threshold_var.set(default_threshold)
            slider.set(default_threshold)
            update_threshold_label(default_threshold)

            populate_match_list()

        def on_tree_select(_event=None):
            selection = tree.selection()
            if not selection:
                return
            record = tree_records.get(selection[0])
            show_entity_details(record)

        def on_tree_double_click(event):
            item_id = tree.identify_row(event.y)
            if not item_id:
                return
            tree.selection_set(item_id)
            tree.focus(item_id)
            show_entity_details(tree_records.get(item_id))

        tree.bind("<<TreeviewSelect>>", on_tree_select)
        tree.bind("<Double-1>", on_tree_double_click)

        def assign_selected_portrait(event=None):
            nonlocal preview_image
            if current_entity is None:
                return
            selection = match_listbox.curselection()
            if not selection:
                return

            match = match_index_map[selection[0]]
            target_path = match.get("path")
            if not target_path:
                return

            if (
                current_entity.get("existing_portrait")
                and not replace_existing
                and not current_entity.get("applied_path")
            ):
                confirm = messagebox.askyesno(
                    "Replace Portrait?",
                    (
                        f"{current_entity.get('display_table')} '{current_entity.get('name')}' already has a portrait.\n"
                        "Do you want to replace it with the selected one?"
                    ),
                )
                if not confirm:
                    return

            try:
                new_path = self.copy_and_resize_portrait(
                    {"Name": current_entity.get("name", "Unnamed")},
                    target_path,
                )
            except Exception as exc:
                messagebox.showerror(
                    "Import Portraits",
                    f"Failed to copy portrait:\n{exc}",
                )
                return

            try:
                db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db")
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        f"UPDATE {current_entity['table']} SET Portrait = ? WHERE {current_entity['key_field']} = ?",
                        (new_path, current_entity.get("name")),
                    )
                    conn.commit()
            except Exception as exc:
                messagebox.showerror(
                    "Import Portraits",
                    f"Failed to save portrait to the database:\n{exc}",
                )
                return

            current_entity["status"] = f"Assigned manually ({match.get('score', 0) * 100:.1f}%)"
            current_entity["applied_path"] = new_path
            current_entity["applied_source"] = target_path
            current_entity["applied_score"] = match.get("score", 0)
            current_entity["existing_portrait"] = new_path

            detail_status_label.configure(text=current_entity["status"])
            rel_path = match.get("relative") or os.path.basename(target_path)
            match_info_label.configure(
                text=f"Assigned portrait ({match.get('score', 0) * 100:.1f}% match)\n{rel_path}"
            )

            tree.set(current_entity["tree_id"], "status", current_entity["status"])
            tree.set(
                current_entity["tree_id"],
                "score",
                f"{match.get('score', 0) * 100:.1f}%",
            )
            tree.item(current_entity["tree_id"], tags=("manual",))
            assign_button.configure(state="disabled")

        match_listbox.bind("<Double-Button-1>", assign_selected_portrait)

        review_window.bind("<Escape>", lambda _event: review_window.destroy())

        # Preselect the first entity that has matches to streamline the workflow.
        for record in entity_review_data:
            if record.get("matches"):
                show_entity_details(record)
                tree.selection_set(record["tree_id"])
                tree.focus(record["tree_id"])
                break

    def preview_and_export_scenarios(self):
        scenario_wrapper = GenericModelWrapper("scenarios")
        scenario_items = scenario_wrapper.load_items()
        if not scenario_items:
            messagebox.showwarning("No Scenarios", "There are no scenarios available.")
            return
        selection_window = Toplevel()
        selection_window.title("Select Scenarios to Export")
        selection_window.geometry("400x300")
        listbox = Listbox(selection_window, selectmode="multiple", height=15)
        listbox.pack(fill="both", expand=True, padx=10, pady=10)
        scenario_titles = [scenario.get("Title", "Unnamed Scenario") for scenario in scenario_items]
        for title in scenario_titles:
            listbox.insert("end", title)
        def export_selected():
            selected_indices = listbox.curselection()
            if not selected_indices:
                messagebox.showwarning("No Selection", "Please select at least one scenario to export.")
                return
            selected_scenarios = [scenario_items[i] for i in selected_indices]
            self.preview_and_save(selected_scenarios)
            selection_window.destroy()
        ctk.CTkButton(selection_window, text="Export Selected", command=export_selected).pack(pady=5)

    def preview_and_save(self, selected_scenarios):
        creature_items = {creature["Name"]: creature for creature in self.creature_wrapper.load_items()}
        place_items = {place["Name"]: place for place in self.place_wrapper.load_items()}
        npc_items = {npc["Name"]: npc for npc in self.npc_wrapper.load_items()}

        file_path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word Files", "*.docx"), ("All Files", "*.*")],
            title="Save Scenario Export"
        )
        if not file_path:
            return

        doc = Document()
        doc.add_heading("Campaign Scenarios", level=1)
        for scenario in selected_scenarios:
            title = scenario.get("Title", "Unnamed Scenario")
            summary = scenario.get("Summary", "No description provided.")
            secrets = scenario.get("Secrets", "No secrets provided.")

            doc.add_heading(title, level=2)
            doc.add_heading("Summary", level=3)
            if isinstance(summary, dict):
                p = doc.add_paragraph()
                run = p.add_run(summary.get("text", ""))
                self.apply_formatting(run, summary.get("formatting", {}))
            else:
                doc.add_paragraph(str(summary))

            doc.add_heading("Secrets", level=3)
            if isinstance(secrets, dict):
                p = doc.add_paragraph()
                run = p.add_run(secrets.get("text", ""))
                self.apply_formatting(run, secrets.get("formatting", {}))
            else:
                doc.add_paragraph(str(secrets))
            scenes = scenario.get("Scenes") or []
            if scenes:
                doc.add_heading("Scenes", level=3)
                for scene in scenes:
                    scene_title = ""
                    text_payload = scene
                    links_payload = []
                    if isinstance(scene, dict):
                        scene_title = scene.get("Title") or scene.get("Scene") or ""
                        text_payload = scene.get("Text") or scene.get("text") or scene
                        links_payload = scene.get("Links") or []
                    if scene_title:
                        doc.add_paragraph(scene_title, style="List Bullet")
                    if isinstance(text_payload, dict):
                        p = doc.add_paragraph()
                        run = p.add_run(text_payload.get("text", ""))
                        self.apply_formatting(run, text_payload.get("formatting", {}))
                    else:
                        doc.add_paragraph(str(text_payload))
                    if links_payload:
                        for link in links_payload:
                            target = link.get("Target") or link.get("target") or ""
                            text = link.get("Text") or link.get("text") or "Continue"
                            doc.add_paragraph(f"  → {text}: {target}")
            
            # Places Section
            doc.add_heading("Places", level=3)
            for place_name in scenario.get("Places", []):
                place = place_items.get(place_name, {"Name": place_name, "Description": "Unknown Place"})
                if isinstance(place["Description"], dict):
                    description_text = place["Description"].get("text", "Unknown Place")
                else:
                    description_text = place["Description"]
                doc.add_paragraph(f"- {place['Name']}: {description_text}")

            # NPCs Section
            doc.add_heading("NPCs", level=3)
            for npc_name in scenario.get("NPCs", []):
                npc = npc_items.get(npc_name, {"Name": npc_name, "Role": "Unknown",
                                                "Description": {"text": "Unknown NPC", "formatting": {}}})
                p = doc.add_paragraph(f"- {npc['Name']} ({npc['Role']}, {npc.get('Faction', 'Unknown')}): ")
                description = npc['Description']
                if isinstance(description, dict):
                    run = p.add_run(description.get("text", ""))
                    self.apply_formatting(run, description.get("formatting", {}))
                else:
                    p.add_run(str(description))

            # Creatures Section
            doc.add_heading("Creatures", level=3)
            for creature_name in scenario.get("Creatures", []):
                creature = creature_items.get(creature_name, {
                    "Name": creature_name,
                    "Stats": {"text": "No Stats", "formatting": {}},
                    "Powers": {"text": "No Powers", "formatting": {}},
                    "Description": {"text": "Unknown Creature", "formatting": {}}
                })
                stats = creature["Stats"]
                if isinstance(stats, dict):
                    stats_text = stats.get("text", "No Stats")
                else:
                    stats_text = stats
                powers = creature.get("Powers", "Unknown")
                if isinstance(powers, dict):
                    powers_text = powers.get("text", "No Powers")
                else:
                    powers_text = powers
                p = doc.add_paragraph(f"- {creature['Name']} ({stats_text}, {powers_text}): ")
                description = creature["Description"]
                if isinstance(description, dict):
                    run = p.add_run(description.get("text", ""))
                    self.apply_formatting(run, description.get("formatting", {}))
                else:
                    p.add_run(str(description))
        doc.save(file_path)
        messagebox.showinfo("Export Successful", f"Scenario exported successfully to:\n{file_path}")

    def apply_formatting(self, run, formatting):
        if formatting.get('bold'):
            run.bold = True
        if formatting.get('italic'):
            run.italic = True
        if formatting.get('underline'):
            run.underline = True

    def normalize_name(self, name):
        if name is None:
            return ""
        text = unicodedata.normalize("NFKD", str(name))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.lower().replace('_', ' ')
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())

    def build_portrait_mapping(self):
        mapping = {}
        campaign_dir = ConfigHelper.get_campaign_dir()
        dir_txt_path = os.path.join(campaign_dir, "assets", "portraits", "dir.txt")
        if not os.path.exists(dir_txt_path):
            print(f"dir.txt not found at {dir_txt_path}")
            return mapping
        with open(dir_txt_path, "r", encoding="cp1252") as f:
            for line in f:
                line = line.strip()
                if not line.lower().endswith(".png"):
                    continue
                tokens = line.split()
                file_name = tokens[-1]
                if file_name.lower() == "dir.txt":
                    continue
                base_name = os.path.splitext(file_name)[0]
                parts = base_name.split("_")
                filtered_parts = []
                for part in parts:
                    if part.lower() == "portrait" or part.isdigit():
                        continue
                    filtered_parts.append(part)
                if filtered_parts:
                    candidate = " ".join(filtered_parts)
                    normalized_candidate = self.normalize_name(candidate)
                    mapping[normalized_candidate] = file_name
        return mapping

    def associate_npc_portraits(self):
        portrait_mapping = self.build_portrait_mapping()
        if not portrait_mapping:
            print("No portrait mapping was built.")
            return
        db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT Name, Portrait FROM npcs")
        npc_rows = cursor.fetchall()
        modified = False
        for npc in npc_rows:
            npc_name = npc["Name"].strip()
            normalized_npc = self.normalize_name(npc_name)
            if normalized_npc in portrait_mapping:
                portrait_file = portrait_mapping[normalized_npc]
                if not npc["Portrait"] or npc["Portrait"].strip() == "":
                    campaign_dir = ConfigHelper.get_campaign_dir()
                    new_portrait_path = os.path.join(campaign_dir, "assets", "portraits", portrait_file)
                    cursor.execute("UPDATE npcs SET Portrait = ? WHERE Name = ?", (new_portrait_path, npc_name))
                    print(f"Associated portrait '{portrait_file}' with NPC '{npc_name}'")
                    modified = True
        if modified:
            conn.commit()
            print("NPC database updated with associated portraits.")
        else:
            print("No NPC records were updated. Either all have portraits or no matches were found.")
        conn.close()

    def _on_ctrl_f(self, event=None):
        """Global Ctrl+F binding: only opens search when GM screen is active."""
        if self.current_gm_view:
            self.current_gm_view.open_global_search()
         # otherwise ignore silently


    def open_audio_bar(self):
        try:
            window = self.audio_bar_window
        except AttributeError:
            window = None
        try:
            if window is None or not window.winfo_exists():
                self.audio_bar_window = AudioBarWindow(self, controller=self.audio_controller)
                self.audio_bar_window.bind("<Destroy>", self._on_audio_bar_destroyed)
                window = self.audio_bar_window
            window.show()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open Audio Controls Bar:\n{exc}")

    def _on_audio_bar_destroyed(self, event=None):
        if event is None or event.widget is self.audio_bar_window:
            self.audio_bar_window = None
            try:
                if self.dice_bar_window and self.dice_bar_window.winfo_exists():
                    self.dice_bar_window._apply_geometry()
            except Exception:
                pass

    def open_dice_bar(self):
        try:
            window = self.dice_bar_window
        except AttributeError:
            window = None
        try:
            if window is None or not window.winfo_exists():
                self.dice_bar_window = DiceBarWindow(self)
                self.dice_bar_window.bind("<Destroy>", self._on_dice_bar_destroyed)
                window = self.dice_bar_window
            window.show()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open Dice Bar:\n{exc}")

    def _on_dice_bar_destroyed(self, event=None):
        if event is None:
            self.dice_bar_window = None
            return
        if event.widget is self.dice_bar_window:
            self.dice_bar_window = None

    def open_sound_manager(self):
        try:
            window = self.sound_manager_window
        except AttributeError:
            window = None
        try:
            if window is None or not window.winfo_exists():
                self.sound_manager_window = SoundManagerWindow(self, controller=self.audio_controller)
                self.sound_manager_window.bind("<Destroy>", self._on_sound_manager_destroyed)
                window = self.sound_manager_window
            window.show()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open Sound & Music Manager:\n{exc}")

    def _on_sound_manager_destroyed(self, event=None):
        if event is None:
            self.sound_manager_window = None
            return
        if event.widget is self.sound_manager_window:
            self.sound_manager_window = None

    def open_dice_roller(self):
        try:
            window = self.dice_roller_window
            if window is None or not window.winfo_exists():
                self.dice_roller_window = DiceRollerWindow(self)
                self.dice_roller_window.bind("<Destroy>", self._on_dice_window_destroyed)
            self.dice_roller_window.show()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open Dice Roller:\n{exc}")

    def _on_dice_window_destroyed(self, event=None):
        if event is None:
            self.dice_roller_window = None
            return
        if event.widget is self.dice_roller_window:
            self.dice_roller_window = None

    def map_tool(self, map_name=None):
        log_info(
            f"Opening Map Tool (map={map_name})",
            func_name="main_window.MainWindow.map_tool",
        )

        existing = getattr(self, "_map_tool_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            existing.attributes("-topmost", True)
            existing.after_idle(lambda: existing.attributes("-topmost", False))
            controller = getattr(self, "map_controller", None)
            if map_name and controller and hasattr(controller, "open_map_by_name"):
                controller.open_map_by_name(map_name)
            return

        maps_wrapper = GenericModelWrapper("maps")

        top = ctk.CTkToplevel(self)
        top.lift()
        top.focus_force()
        top.attributes("-topmost", True)
        top.after_idle(lambda: top.attributes("-topmost", False))
        top.title("Map Tool")
        top.geometry("1920x1080+0+0")

        map_frame = ctk.CTkFrame(top)
        map_frame.pack(fill="both", expand=True)

        self.map_controller = DisplayMapController(
            map_frame,
            maps_wrapper,
            load_template("maps")
        )
        if map_name and hasattr(self.map_controller, "open_map_by_name"):
            self.map_controller.open_map_by_name(map_name)

        def _on_close():
            try:
                controller = getattr(self, "map_controller", None)
                if controller is not None:
                    controller.close_web_display()
            except Exception:
                log_exception("Error while closing web display")
            finally:
                self._map_tool_window = None
                self.map_controller = None
                top.destroy()

        top.protocol("WM_DELETE_WINDOW", _on_close)
        self._map_tool_window = top

if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
