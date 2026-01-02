import json
import math
import customtkinter as ctk
from modules.helpers import theme_manager
import tkinter.font as tkFont
import re
import os
import ctypes
from typing import Optional
from ctypes import wintypes
#import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Menu
from PIL import Image, ImageTk
import textwrap
import html
from collections.abc import Mapping

try:  # Optional rich-text renderer for detail panel content
    from tkhtmlview import HTMLLabel  # type: ignore
except Exception:  # pragma: no cover - fallback when library is absent
    HTMLLabel = None

from modules.helpers.template_loader import load_template
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.portrait_helper import (
    parse_portrait_value,
    portrait_menu_label,
    primary_portrait,
    resolve_portrait_candidate,
    resolve_portrait_path,
)
from modules.helpers.text_helpers import deserialize_possible_json, format_longtext
from modules.ui.image_viewer import show_portrait
from modules.helpers.template_loader import load_template
from modules.audio.entity_audio import (
    get_entity_audio_value,
    play_entity_audio,
    stop_entity_audio,
)
from modules.helpers.logging_helper import log_module_import, log_warning

log_module_import(__name__)

# Global constants
PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
MAX_PORTRAIT_SIZE = (128, 128)
ENTITY_TOOLTIP_PORTRAIT_MAX_SIZE = (180, 180)
PORTRAIT_MENU_THUMB_SIZE = (48, 48)
try:
    RESAMPLE_MODE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1 fallback
    RESAMPLE_MODE = Image.LANCZOS
ctk.set_appearance_mode("Dark")
theme_manager.apply_theme(theme_manager.get_theme())


class LinkEditDialog(ctk.CTkToplevel):
    def __init__(self, master, link_record, scene_lookup):
        super().__init__(master)
        self.title("Edit Link")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result = None
        self.link_record = link_record or {}
        self.scene_lookup = scene_lookup or {}

        self.columnconfigure(1, weight=1)

        link_text = (self.link_record.get("text") or "").strip()
        link_data = self.link_record.get("link_data")
        if not isinstance(link_data, dict):
            link_data = {}

        ctk.CTkLabel(self, text="Label:").grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
        self.label_var = tk.StringVar(value=link_text)
        self.label_entry = ctk.CTkEntry(self, textvariable=self.label_var, width=320)
        self.label_entry.grid(row=0, column=1, padx=12, pady=(12, 6), sticky="ew")

        ctk.CTkLabel(self, text="Target Scene Tag:").grid(row=1, column=0, padx=12, pady=6, sticky="w")
        tag_options = sorted([tag for tag in self.scene_lookup.keys() if tag])
        initial_target = self._initial_target_value(link_data)
        if initial_target and initial_target not in tag_options:
            tag_options.append(initial_target)
            tag_options.sort()
        self.target_var = tk.StringVar(value=initial_target)
        self.target_combo = ctk.CTkComboBox(
            self,
            variable=self.target_var,
            values=tag_options,
            state="readonly" if tag_options else "normal",
            width=320,
        )
        self.target_combo.grid(row=1, column=1, padx=12, pady=6, sticky="ew")
        if initial_target:
            self.target_combo.set(initial_target)

        ctk.CTkLabel(self, text="Conditional metadata (JSON):").grid(
            row=2, column=0, padx=12, pady=6, sticky="nw"
        )
        self.metadata_textbox = ctk.CTkTextbox(self, width=320, height=140)
        self.metadata_textbox.grid(row=2, column=1, padx=12, pady=6, sticky="ew")
        initial_metadata = self._prepare_initial_metadata(link_data)
        if initial_metadata:
            self.metadata_textbox.insert("1.0", initial_metadata)

        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=3, column=0, columnspan=2, padx=12, pady=(6, 12), sticky="e")

        cancel_btn = ctk.CTkButton(button_frame, text="Cancel", command=self._on_cancel)
        cancel_btn.pack(side="right", padx=(0, 6))
        save_btn = ctk.CTkButton(button_frame, text="Save", command=self._on_submit)
        save_btn.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.after(100, self._focus_label_entry)

    def _focus_label_entry(self):
        self.label_entry.focus_set()
        self.label_entry.icursor("end")

    def _initial_target_value(self, link_data):
        target_tag = self.link_record.get("target_tag") or self.link_record.get("to")
        if target_tag:
            return target_tag
        if isinstance(link_data, dict):
            return link_data.get("target_tag") or link_data.get("target") or ""
        return ""

    def _prepare_initial_metadata(self, link_data):
        metadata_value = None
        if isinstance(link_data, dict):
            if link_data.get("conditions") is not None:
                metadata_value = link_data.get("conditions")
            elif link_data.get("metadata") is not None:
                metadata_value = link_data.get("metadata")
        if metadata_value is None:
            return ""
        try:
            return json.dumps(metadata_value, indent=2)
        except TypeError:
            return str(metadata_value)

    def _on_submit(self):
        text_value = (self.label_var.get() or "").strip()
        if not text_value:
            messagebox.showerror("Validation", "Link label cannot be empty.")
            return

        target_value = (self.target_var.get() or "").strip()
        if not target_value:
            messagebox.showerror("Validation", "A target scene tag must be selected.")
            return
        if target_value not in self.scene_lookup:
            messagebox.showerror("Validation", "Selected target tag is not valid.")
            return

        metadata_text = self.metadata_textbox.get("1.0", "end").strip()
        metadata_payload = None
        if metadata_text:
            try:
                metadata_payload = json.loads(metadata_text)
            except json.JSONDecodeError as exc:
                messagebox.showerror("Validation", f"Metadata must be valid JSON: {exc}")
                return

        self.result = {
            "text": text_value,
            "target_tag": target_value,
            "metadata": metadata_payload,
        }
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

#logging.basicConfig(level=logging.DEBUG)

ENTITY_TOOLTIP_HIDE_DELAY_MS = 600

SCENE_CARD_WIDTHS = {
    "S": 260,
    "M": 320,
    "L": 380,
}

SCENE_TYPE_STYLE_MAP = {
    "setup": {"label": "Setup", "color": "#3B82F6"},
    "choice": {"label": "Choice", "color": "#8B5CF6"},
    "investigation": {"label": "Investigation", "color": "#F59E0B"},
    "combat": {"label": "Combat", "color": "#EF4444"},
    "outcome": {"label": "Outcome", "color": "#10B981"},
    "social": {"label": "Social", "color": "#6366F1"},
    "travel": {"label": "Travel", "color": "#0EA5E9"},
    "downtime": {"label": "Downtime", "color": "#A855F7"},
}

SCENE_CARD_BG = "#23262F"
SCENE_CARD_BORDER = "#3B3F4C"

TAG_SANITIZE_PATTERN = re.compile(r"[^0-9A-Za-z_]")
TAG_UNDERSCORE_COLLAPSE_PATTERN = re.compile(r"_+")

DETAIL_PANEL_WIDTH = 350
DETAIL_PANEL_PADDING = 12


def clean_longtext(data, max_length=2000):
    # First, get the plain text using your existing helper.
    text = format_longtext(data, max_length)
    # Remove curly braces.
    text = re.sub(r'[{}]', '', text)
    # Remove backslash control words (simple approach).
    text = re.sub(r'\\[a-zA-Z]+\s?', '', text)
    return text.strip()

class ScenarioGraphEditor(ctk.CTkFrame):
    def __init__(self, master,
                scenario_wrapper: GenericModelWrapper,
                npc_wrapper: GenericModelWrapper,
                creature_wrapper: GenericModelWrapper,
                place_wrapper: GenericModelWrapper,
                *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.scenario_wrapper = scenario_wrapper
        self.npc_wrapper = npc_wrapper
        self.creature_wrapper = creature_wrapper
        self.place_wrapper = place_wrapper
        self.node_holder_images = {}    # ← keep PhotoImage refs here
        self.node_bboxes = {}
        self.node_images = {}  # Prevent garbage collection of PhotoImage objects
        self.overlay_images={}
        # Preload NPC, Creature and Place data for quick lookup.
        self.npcs = {npc["Name"]: npc for npc in self.npc_wrapper.load_items()}
        self.creatures = {creature["Name"]: creature for creature in self.creature_wrapper.load_items()}
        self.places = {pl["Name"]: pl for pl in self.place_wrapper.load_items()}

        self.scenario = None
        self.canvas_scale = 1.0
        self.zoom_factor = 1.1
        self.type_icon_paths = {
            "npc": "assets/npc_icon.png",
            "place": "assets/places_icon.png",
            "scenario": "assets/gm_screen_icon.png",
            "creature": "assets/creature_icon.png",
            "scene": "assets/scenario_icon.png",
        }
        self.type_icons = {}
        self._scaled_type_icons = {}
        
        # Graph structure.
        self.graph = {"nodes": [], "links": []}
        self.node_positions = {}   # Maps node_tag -> (x, y)
        self.node_rectangles = {}  # Maps node_tag -> rectangle_id
        self.selected_node = None
        self.selected_items = []
        self.drag_start = None
        self.original_positions = {}
        self.canvas_link_items = {}
        self.scene_flow_scenes = []
        self.scene_flow_scene_lookup = {}

        self.detail_panel_width = DETAIL_PANEL_WIDTH
        self.detail_panel_padding = DETAIL_PANEL_PADDING
        self._detail_panel_visible = True

        # Tooltip state for scene entity portraits
        self._entity_tooltip_window = None
        self._entity_tooltip_after_id = None
        self._entity_tooltip_pending = None
        self._entity_tooltip_image_cache = {}
        self._entity_tooltip_hide_after_id = None
        self._entity_tooltip_active_tag = None
        self._portrait_menu_images = []

        self.init_toolbar()
        self.active_detail_scene_tag = None
        postit_path = "assets/images/post-it.png"
        pin_path = "assets/images/thumbtack.png"

        # Layout container combining canvas and side panel
        self.main_container = ctk.CTkFrame(self)
        self.main_container.pack(fill="both", expand=True)

        self.canvas_frame = ctk.CTkFrame(self.main_container)
        self.canvas_frame.grid(row=0, column=0, sticky="nsew")
        self.detail_panel = ctk.CTkFrame(self.main_container, fg_color="#1B1D23", corner_radius=0)
        self.detail_panel.grid(row=0, column=1, sticky="nsew")
        self.detail_panel.configure(width=self.detail_panel_width)
        self.detail_panel.grid_propagate(False)

        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(1, weight=0, minsize=self.detail_panel_width)

        self.canvas = ctk.CTkCanvas(self.canvas_frame, bg="#2B2B2B", highlightthickness=0)
        self.h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        VIRTUAL_WIDTH = 5000
        VIRTUAL_HEIGHT = 5000
        if os.path.exists(postit_path):
            img = Image.open(postit_path).convert("RGBA")
            self.postit_base = img

        if os.path.exists(pin_path):
            pin_img = Image.open(pin_path)
            self.pin_image = ImageTk.PhotoImage(pin_img.resize((32, 32), Image.Resampling.LANCZOS), master=self.canvas)
        # Load and display the background image at the top-left
        background_path = "assets/images/corkboard_bg.png"
       
        if os.path.exists(background_path):
            self.background_image = Image.open(background_path)

            # Resize the PIL image (e.g. 2x scale)
            zoom_factor = 2
            w=1920
            h=1080
            self.background_image = self.background_image.resize((w * zoom_factor, h * zoom_factor), Image.Resampling.LANCZOS)

            self.background_photo = ImageTk.PhotoImage(self.background_image, master=self.canvas)
            self.background_id = self.canvas.create_image(
                0, 0,
                image=self.background_photo,
                anchor="center",  # or "nw" if you want top-left alignment
                tags="background"
            )
            self.canvas.tag_lower("background")

        self._load_default_type_icons()

        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self._init_detail_panel()

        # Start with the detail panel hidden until the scene flow view is shown.
        self._hide_detail_panel()

        # Global mouse events.
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel_y)
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom)  # Windows
        self.canvas.bind("<Control-Button-4>", self._on_zoom)    # Linux scroll up
        self.canvas.bind("<Control-Button-5>", self._on_zoom)    # Linux scroll down
        self.canvas.bind("<Shift-Button-4>", self._on_mousewheel_x)
        self.canvas.bind("<Shift-Button-5>", self._on_mousewheel_x)
        self._is_panning = False
        self.canvas.bind("<Button-2>", self._start_canvas_pan)
        self.canvas.bind("<B2-Motion>", self._do_canvas_pan)
        self.canvas.bind("<ButtonRelease-2>", self._end_canvas_pan)

    def _sanitize_tag_component(self, value):
        text = str(value or "")
        text = text.replace(" ", "_")
        text = TAG_SANITIZE_PATTERN.sub("_", text)
        text = TAG_UNDERSCORE_COLLAPSE_PATTERN.sub("_", text)
        return text

    def _build_tag(self, prefix, name=None):
        prefix_part = self._sanitize_tag_component(prefix)
        if name is None:
            return prefix_part
        name_part = self._sanitize_tag_component(name)
        return f"{prefix_part}_{name_part}"

    def _on_zoom(self, event):
        if event.delta > 0 or event.num == 4:
            scale = self.zoom_factor
        else:
            scale = 1 / self.zoom_factor

        new_scale = self.canvas_scale * scale
        new_scale = max(0.5, min(new_scale, 2.5))  # Clamp zoom to reasonable range
        scale_change = new_scale / self.canvas_scale
        self.canvas_scale = new_scale

        # Use mouse pointer as anchor for better UX
        anchor_x = self.canvas.canvasx(event.x)
        anchor_y = self.canvas.canvasy(event.y)

        # Rescale all node positions
        for tag, (x, y) in self.node_positions.items():
            dx = x - anchor_x
            dy = y - anchor_y
            new_x = anchor_x + dx * scale_change
            new_y = anchor_y + dy * scale_change
            self.node_positions[tag] = (new_x, new_y)

            # Update x/y in the node data as well
            for node in self.graph["nodes"]:
                node_tag = self._build_tag(node.get('type', ''), node.get('name', ''))
                if node_tag == tag:
                    node["x"], node["y"] = new_x, new_y
                    break

        self.draw_graph()

        # Optional: zoom font sizes, overlays, etc., here if you want to support them visually
    def reset_zoom(self):
        self.canvas_scale = 1.0

        # Restore original node positions
        for node in self.graph["nodes"]:
            tag = self._build_tag(node.get('type', ''), node.get('name', ''))
            if tag in self.original_positions:
                x, y = self.original_positions[tag]
                node["x"] = x
                node["y"] = y

        # Rebuild node_positions from graph data
        self.node_positions = {
            self._build_tag(node.get('type', ''), node.get('name', '')): (node["x"], node["y"])
            for node in self.graph["nodes"]
        }

        self.draw_graph()
    
    def init_toolbar(self):
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Select Scenario", command=self.select_scenario).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Save Graph", command=self.save_graph).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Load Graph", command=self.load_graph).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="Reset Zoom", command=self.reset_zoom).pack(side="left", padx=5)

    def _init_detail_panel(self):
        pad = self.detail_panel_padding
        wrap_length = max(10, self.detail_panel_width - 2 * pad)
        self.detail_panel_title = ctk.CTkLabel(
            self.detail_panel,
            text="Scene Details",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=wrap_length,
        )
        self.detail_panel_title.pack(fill="x", padx=pad, pady=(pad, 4))

        self.detail_panel_meta = ctk.CTkLabel(
            self.detail_panel,
            text="Select a scene card to view its full content.",
            justify="left",
            anchor="w",
            wraplength=wrap_length,
        )
        self.detail_panel_meta.pack(fill="x", padx=pad)

        self.detail_html_label = None
        self.detail_textbox = None
        self._rich_renderer_available = False

        self.detail_content_container = ctk.CTkFrame(
            self.detail_panel,
            fg_color="transparent",
        )
        self.detail_content_container.pack(fill="both", expand=True, padx=pad, pady=(8, pad))

        if HTMLLabel is not None:
            try:
                panel_bg = self._resolve_panel_background_color()
                self.detail_html_label = HTMLLabel(
                    self.detail_content_container,
                    html="",
                    background=panel_bg,
                    foreground="#F8FAFC",
                )
                self.detail_html_label.pack(fill="both", expand=True)
                self.detail_html_label.pack_configure(pady=(0, 8))
                self._rich_renderer_available = True
            except Exception:
                self.detail_html_label = None
                self._rich_renderer_available = False

        if not self._rich_renderer_available:
            self._create_plain_textbox()

        self.entity_heading_label = ctk.CTkLabel(
            self.detail_content_container,
            text="Key Entities",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
            justify="left",
        )
        self.entity_button_container = ctk.CTkFrame(
            self.detail_content_container,
            fg_color="transparent",
        )

        self._clear_detail_panel()

    def _resolve_panel_background_color(self):
        try:
            bg = self.detail_panel.cget("fg_color")
        except Exception:
            bg = None
        if isinstance(bg, (tuple, list)):
            bg = bg[-1]
        if not bg or bg in {"", "transparent"}:
            return "#1F2933"
        return bg

    def _create_plain_textbox(self):
        if self.detail_textbox is None or not int(self.detail_textbox.winfo_exists()):
            self.detail_textbox = ctk.CTkTextbox(
                self.detail_content_container,
                wrap="word",
            )
        if not self.detail_textbox.winfo_manager():
            self.detail_textbox.pack(fill="both", expand=True)
        self.detail_textbox.pack_configure(pady=(0, 8))
        self.detail_textbox.configure(state="disabled")

    def _fallback_to_plain_text(self, text):
        if self.detail_html_label is not None:
            try:
                self.detail_html_label.pack_forget()
                self.detail_html_label.destroy()
            except Exception:
                pass
            finally:
                self.detail_html_label = None
        self._rich_renderer_available = False
        self._create_plain_textbox()
        if self.detail_textbox is not None:
            self.detail_textbox.configure(state="normal")
            self.detail_textbox.delete("1.0", "end")
            self.detail_textbox.insert("1.0", text)
            self.detail_textbox.configure(state="disabled")

    def _update_detail_text(self, html_text, plain_text):
        if self._rich_renderer_available and self.detail_html_label is not None:
            try:
                self.detail_html_label.set_html(html_text)
                if self.detail_textbox is not None and self.detail_textbox.winfo_manager():
                    self.detail_textbox.pack_forget()
                return
            except Exception:
                self._fallback_to_plain_text(plain_text)
                return

        if self.detail_textbox is None:
            self._create_plain_textbox()

        if self.detail_textbox is not None:
            self.detail_textbox.configure(state="normal")
            self.detail_textbox.delete("1.0", "end")
            self.detail_textbox.insert("1.0", plain_text)
            self.detail_textbox.configure(state="disabled")
        if self.detail_html_label is not None and self.detail_html_label.winfo_manager():
            self.detail_html_label.pack_forget()

    def _rebuild_entity_buttons(self, entities):
        if not hasattr(self, "entity_button_container"):
            return

        for child in list(self.entity_button_container.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        if hasattr(self, "entity_heading_label") and self.entity_heading_label.winfo_manager():
            self.entity_heading_label.pack_forget()
        if self.entity_button_container.winfo_manager():
            self.entity_button_container.pack_forget()

        valid_entities = [ent for ent in (entities or []) if isinstance(ent, dict)]
        if not valid_entities:
            return

        if hasattr(self, "entity_heading_label") and not self.entity_heading_label.winfo_manager():
            self.entity_heading_label.pack(fill="x", pady=(0, 4))
        if not self.entity_button_container.winfo_manager():
            self.entity_button_container.pack(fill="x", pady=(0, 8))

        for index, entity in enumerate(valid_entities):
            label_text = self._format_entity_button_label(entity)
            button = ctk.CTkButton(
                self.entity_button_container,
                text=label_text,
                anchor="w",
                command=lambda ent=entity: self._open_entity_editor(ent),
            )
            button.pack(fill="x", pady=(0 if index == 0 else 4, 0))
            try:
                button.configure(takefocus=True)
            except Exception:
                pass
            button.bind("<Return>", lambda _event, btn=button: btn.invoke())
            button.bind("<space>", lambda _event, btn=button: btn.invoke())

    def _format_entity_button_label(self, entity):
        if not isinstance(entity, dict):
            return "Unnamed Entity"
        name = (entity.get("name") or entity.get("Name") or "Unnamed").strip() or "Unnamed"
        ent_type = (entity.get("type") or entity.get("Type") or "").strip()
        if ent_type:
            return f"{name} ({ent_type.title()})"
        return name

    def _open_entity_editor(self, entity_entry):
        context = self._resolve_entity_editor_context(entity_entry)
        if not context:
            messagebox.showinfo("Entity", "No editor is available for this entity.")
            return

        record = context.get("record")
        wrapper = context.get("wrapper")
        template_key = context.get("template_key")
        display_type = context.get("display_type") or "Entity"
        entity_name = context.get("entity_name") or "Entity"

        if not record or not wrapper:
            messagebox.showwarning(
                display_type,
                f"Unable to locate data for {display_type.rstrip('s')} '{entity_name}'.",
            )
            return

        try:
            template = load_template(template_key)
        except Exception as exc:
            messagebox.showerror(display_type, f"Unable to load editor template: {exc}")
            return

        GenericEditorWindow(None, record, template, wrapper)

    def _resolve_entity_editor_context(self, entity_entry):
        if not isinstance(entity_entry, dict):
            return None

        raw_name = entity_entry.get("name") or entity_entry.get("Name") or ""
        raw_type = entity_entry.get("type") or entity_entry.get("Type") or ""
        name = str(raw_name).strip()
        ent_type = str(raw_type).strip().lower()

        if not name:
            return None

        type_aliases = {
            "character": "npc",
            "ally": "npc",
            "npcs": "npc",
            "monster": "creature",
            "enemy": "creature",
            "foe": "creature",
            "creatures": "creature",
            "places": "place",
            "location": "place",
            "locations": "place",
            "site": "place",
        }
        base_type = type_aliases.get(ent_type, ent_type or "npc")

        collection = None
        wrapper = None
        template_key = None
        display_type = None
        record = None

        if base_type == "npc":
            collection = getattr(self, "npcs", {})
            wrapper = getattr(self, "npc_wrapper", None)
            template_key = "npcs"
            display_type = "NPCs"
            record = self._lookup_entity_by_name("npc", name)
        elif base_type == "creature":
            collection = getattr(self, "creatures", {})
            wrapper = getattr(self, "creature_wrapper", None)
            template_key = "creatures"
            display_type = "Creatures"
            record = self._lookup_entity_by_name("creature", name)
        elif base_type == "place":
            collection = getattr(self, "places", {})
            wrapper = getattr(self, "place_wrapper", None)
            template_key = "places"
            display_type = "Places"
            record = self._lookup_entity_by_name("place", name)
        elif base_type == "faction":
            collection = getattr(self, "factions", {})
            wrapper = getattr(self, "faction_wrapper", None)
            template_key = "factions"
            display_type = "Factions"
            record = self._lookup_from_collection(collection, name)
        elif base_type == "scenario":
            collection = {str((self.scenario or {}).get("Title", "")): self.scenario}
            wrapper = getattr(self, "scenario_wrapper", None)
            template_key = "scenarios"
            display_type = "Scenarios"
            record = self._lookup_from_collection(collection, name)

        if record is None and collection:
            record = self._lookup_from_collection(collection, name)

        if not template_key:
            return None

        return {
            "record": record,
            "wrapper": wrapper,
            "template_key": template_key,
            "display_type": display_type,
            "entity_name": name,
        }

    @staticmethod
    def _lookup_from_collection(collection, name):
        if not isinstance(collection, dict):
            return None
        if name in collection:
            return collection[name]
        lower = name.lower()
        for key, value in collection.items():
            try:
                if str(key).lower() == lower:
                    return value
            except Exception:
                continue
        return None

    @staticmethod
    def _apply_inline_markup(text):
        escaped = html.escape(text, quote=False)
        escaped = re.sub(r"\*\*(.+?)\*\*", lambda m: f"<strong>{m.group(1)}</strong>", escaped)
        escaped = re.sub(
            r"(?<!_)__(?!_)(.+?)(?<!_)__(?!_)",
            lambda m: f"<strong>{m.group(1)}</strong>",
            escaped,
        )
        escaped = re.sub(
            r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)",
            lambda m: f"<em>{m.group(1)}</em>",
            escaped,
        )
        escaped = re.sub(
            r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)",
            lambda m: f"<em>{m.group(1)}</em>",
            escaped,
        )
        escaped = re.sub(r"`(.+?)`", lambda m: f"<code>{m.group(1)}</code>", escaped)
        return escaped

    def _convert_scene_text_to_html(self, text):
        trimmed = (text or "").strip()
        if not trimmed:
            return "<p>No scene notes provided.</p>"

        html_parts = []
        paragraph_lines = []
        in_list = False

        def close_list():
            nonlocal in_list
            if in_list:
                html_parts.append("</ul>")
                in_list = False

        def flush_paragraph():
            nonlocal paragraph_lines
            if not paragraph_lines:
                return
            processed = [self._apply_inline_markup(line.strip()) for line in paragraph_lines if line.strip()]
            if processed:
                html_parts.append(f"<p>{'<br/>'.join(processed)}</p>")
            paragraph_lines = []

        for raw_line in trimmed.splitlines():
            stripped_line = raw_line.strip()
            if not stripped_line:
                flush_paragraph()
                close_list()
                continue

            bullet_match = re.match(r"^[\-\*]\s+(.*)$", stripped_line)
            if bullet_match:
                flush_paragraph()
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                item_text = bullet_match.group(1).strip()
                html_parts.append(f"<li>{self._apply_inline_markup(item_text)}</li>")
                continue

            close_list()
            paragraph_lines.append(stripped_line)

        flush_paragraph()
        close_list()

        if not html_parts:
            return "<p>No scene notes provided.</p>"

        return "\n".join(html_parts)

    def _show_detail_panel(self):
        if self._detail_panel_visible:
            return
        self.detail_panel.grid(row=0, column=1, sticky="nsew")
        self.detail_panel.configure(width=self.detail_panel_width)
        self.main_container.grid_columnconfigure(1, weight=0, minsize=self.detail_panel_width)
        wrap_length = max(10, self.detail_panel_width - 2 * self.detail_panel_padding)
        if hasattr(self, "detail_panel_title"):
            self.detail_panel_title.configure(wraplength=wrap_length)
        if hasattr(self, "detail_panel_meta"):
            self.detail_panel_meta.configure(wraplength=wrap_length)
        self._detail_panel_visible = True

    def _hide_detail_panel(self):
        if not self._detail_panel_visible:
            return
        self.detail_panel.grid_remove()
        self.main_container.grid_columnconfigure(1, weight=0, minsize=0)
        self._detail_panel_visible = False

    def _clear_detail_panel(self):
        self.active_detail_scene_tag = None
        if hasattr(self, "detail_panel_title"):
            self.detail_panel_title.configure(text="Scene Details")
        if hasattr(self, "detail_panel_meta"):
            self.detail_panel_meta.configure(
                text="Select a scene card to view its full content.",
                text_color="#94A3B8",
            )
        default_text = "Select a scene card to view its full content."
        self._update_detail_text(self._convert_scene_text_to_html(default_text), default_text)
        self._rebuild_entity_buttons([])

    def _show_node_detail(self, node_tag):
        if not self._detail_panel_visible:
            return
        if not node_tag or not node_tag.startswith("scene_"):
            return
        if node_tag == self.active_detail_scene_tag:
            return
        scene_data = (self.scene_flow_scene_lookup or {}).get(node_tag)
        if scene_data is None:
            scene_data = self._build_scene_payload_from_graph(node_tag)
        if scene_data is None:
            self._clear_detail_panel()
            return
        self._populate_detail_panel(scene_data)
        self.active_detail_scene_tag = node_tag

    def _populate_detail_panel(self, scene_data):
        title = scene_data.get("title") or scene_data.get("display_name") or scene_data.get("name") or "Scene"
        source_entry = scene_data.get("source_entry") or {}
        scene_color = scene_data.get("color") or "#3B82F6"
        type_label, header_color, _ = self._resolve_scene_type_style(source_entry, scene_color)
        badges = self._extract_scene_badges(source_entry)

        if hasattr(self, "detail_panel_title"):
            self.detail_panel_title.configure(text=title)
        meta_parts = []
        if type_label:
            meta_parts.append(type_label)
        if badges:
            meta_parts.extend(f"{badge['label']}: {badge['value']}" for badge in badges)
        meta_text = " • ".join(meta_parts) if meta_parts else "No metadata"
        if hasattr(self, "detail_panel_meta"):
            self.detail_panel_meta.configure(text=meta_text, text_color=header_color or "#CBD5F5")

        full_text = scene_data.get("text") or scene_data.get("Text") or "No scene notes provided."
        full_text = full_text.strip() or "No scene notes provided."
        entities = scene_data.get("entities") or scene_data.get("Entities") or []

        html_content = self._convert_scene_text_to_html(full_text)
        plain_content = full_text

        self._update_detail_text(html_content, plain_content)
        self._rebuild_entity_buttons(entities)

    def _build_scene_payload_from_graph(self, node_tag):
        for node in self.graph.get("nodes", []):
            name = node.get("name", "")
            tag = self._build_tag(node.get('type', ''), name)
            if tag != node_tag:
                continue
            data = node.get("data", {}) or {}
            payload = {
                "title": node.get("name"),
                "display_name": node.get("name"),
                "text": data.get("Text") or data.get("text") or "",
                "entities": data.get("Entities") or [],
                "source_entry": data.get("SourceEntry") or {},
                "color": node.get("color"),
            }
            if not payload["text"] and isinstance(payload["source_entry"], dict):
                payload["text"] = payload["source_entry"].get("Text", "")
            return payload
        return None

    def _measure_text_height(self, text, font_obj, wrap_width):
        safe_width = max(int(wrap_width), 10)
        temp_id = self.canvas.create_text(
            0,
            0,
            text=text or "",
            font=font_obj,
            width=safe_width,
            anchor="nw",
        )
        bbox = self.canvas.bbox(temp_id)
        self.canvas.delete(temp_id)
        if bbox:
            return bbox[3] - bbox[1]
        return 0

    def _summarize_scene_text(self, text, max_lines=4, min_lines=2):
        if not text:
            return ["No scene notes provided."], False

        text = deserialize_possible_json(text)

        if isinstance(text, Mapping):
            candidate = text.get("text") or text.get("Text")
            candidate = deserialize_possible_json(candidate)
            if isinstance(candidate, str) and candidate.strip():
                text = candidate
            elif isinstance(candidate, (list, tuple, set)):
                text = "\n".join(str(v).strip() for v in candidate if str(v).strip())
            else:
                text = str(candidate or "")
        elif hasattr(text, "text") and isinstance(getattr(text, "text"), str):
            text = getattr(text, "text")
        elif isinstance(text, (list, tuple, set)):
            text = "\n".join(str(v).strip() for v in text if str(v).strip())

        text = deserialize_possible_json(text)
        if isinstance(text, (list, tuple, set)):
            text = "\n".join(str(v).strip() for v in text if str(v).strip())

        normalized = str(text or "").replace("\r", "\n")

        def canonical_key(fragment: str) -> str:
            cleaned = re.sub(r"\s+", " ", fragment or "").strip()
            if not cleaned:
                return ""
            cleaned = re.sub(r"^[\-*\u2022•\s]+", "", cleaned)
            cleaned = re.sub(r"^[0-9]+[\.)]\s*", "", cleaned)
            cleaned = cleaned.strip(" :;-•\u2022")
            return cleaned.lower()

        raw_fragments = [frag.strip() for frag in normalized.splitlines() if frag.strip()]
        fragments: list[str] = []
        seen_fragment_keys: set[str] = set()
        for frag in raw_fragments:
            key = canonical_key(frag)
            if not key or key in seen_fragment_keys:
                continue
            seen_fragment_keys.add(key)
            fragments.append(frag)

        if len(fragments) < min_lines:
            sentences = re.split(r"(?<=[.!?])\s+", normalized)
            for sentence in sentences:
                cleaned_sentence = sentence.strip()
                if not cleaned_sentence:
                    continue
                key = canonical_key(cleaned_sentence)
                if not key or key in seen_fragment_keys:
                    continue
                seen_fragment_keys.add(key)
                fragments.append(cleaned_sentence)

        cleaned_lines: list[str] = []
        seen_keys: set[str] = set()
        def strip_leading_markers(value: str) -> str:
            without_markers = re.sub(r"^[\-*\u2022•\s]+", "", value or "").strip()
            without_numbers = re.sub(r"^[0-9]+[\.)]\s*", "", without_markers)
            return without_numbers.strip()

        for fragment in fragments:
            cleaned = re.sub(r"\s+", " ", fragment).strip()
            key = canonical_key(cleaned)
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            cleaned_lines.append(strip_leading_markers(cleaned))
            if len(cleaned_lines) >= max_lines:
                break

        truncated = len(cleaned_lines) < len(fragments)
        if not cleaned_lines:
            return ["No scene notes provided."], False

        if len(cleaned_lines) < min_lines:
            wrapped = textwrap.wrap(normalized, width=90)
            for chunk in wrapped:
                chunk_clean = re.sub(r"\s+", " ", chunk).strip()
                key = canonical_key(chunk_clean)
                if not key or key in seen_keys:
                    continue
                candidate_line = strip_leading_markers(chunk_clean)
                candidate_lower = candidate_line.lower()
                # Avoid manufacturing duplicate bullets when we only have a single long fragment
                if any(candidate_lower in existing.lower() or existing.lower() in candidate_lower for existing in cleaned_lines):
                    continue
                cleaned_lines.append(candidate_line)
                seen_keys.add(key)
                if len(cleaned_lines) >= min_lines:
                    break

        cleaned_lines = cleaned_lines[:max_lines]
        truncated = truncated or len(cleaned_lines) < len(fragments)
        return cleaned_lines, truncated

    def _truncate_line(self, text, width):
        if not text:
            return ""
        safe_width = max(int(width), 8)
        try:
            return textwrap.shorten(str(text), width=safe_width, placeholder="…")
        except ValueError:
            return str(text)

    def _estimate_scene_card_dimensions(
        self,
        text: str,
        entity_entries: list[dict],
        source_entry: Optional[dict],
        card_size_key: str,
        scale: float = 1.0,
    ) -> tuple[int, int]:
        safe_scale = scale or 1.0
        card_size_key = str(card_size_key or "M").upper()
        card_width = int(SCENE_CARD_WIDTHS.get(card_size_key, SCENE_CARD_WIDTHS["M"]) * safe_scale)

        header_height = max(int(40 * safe_scale), 32)
        padding_x = max(int(16 * safe_scale), 12)
        body_padding_y = max(int(12 * safe_scale), 10)
        body_wrap_width = max(card_width - 2 * padding_x, int(160 * safe_scale))

        bullet_lines, truncated = self._summarize_scene_text(text, max_lines=4)
        bullet_lines = [self._truncate_line(line, 96) for line in bullet_lines]
        more_line_needed = truncated
        if more_line_needed and len(bullet_lines) >= 4:
            bullet_lines = bullet_lines[:3]

        if not bullet_lines:
            bullet_lines = ["No scene notes provided."]
            more_line_needed = False

        bullet_text = "\n".join(f"• {line}" for line in bullet_lines)
        body_font = tkFont.Font(family="Arial", size=max(1, int(10 * safe_scale)))
        more_font = tkFont.Font(family="Arial", size=max(1, int(10 * safe_scale)), slant="italic")
        body_text_height = self._measure_text_height(bullet_text, body_font, body_wrap_width)
        more_line_height = self._measure_text_height("• More…", more_font, body_wrap_width) if more_line_needed else 0
        more_line_spacing = int(4 * safe_scale) if more_line_needed else 0
        body_height = body_padding_y * 2 + body_text_height + (
            more_line_height + more_line_spacing if more_line_needed else 0
        )

        chip_entities = [
            ent
            for ent in (entity_entries or [])
            if isinstance(ent, dict)
            and (ent.get("type") or "").lower() in {"npc", "creature", "place"}
        ]
        chip_count = min(len(chip_entities), 6)
        chip_size = max(int(32 * safe_scale), 24)
        chip_vertical_padding = max(int(8 * safe_scale), 4)
        chips_height = chip_vertical_padding * 2 + chip_size if chip_count else 0

        badge_font = tkFont.Font(family="Arial", size=max(1, int(9 * safe_scale)), weight="bold")
        badge_height = max(int(24 * safe_scale), 18)
        badge_gap = max(int(6 * safe_scale), 4)
        badge_inner_pad = max(int(8 * safe_scale), 4)
        badges = self._extract_scene_badges(source_entry or {})
        badge_texts = [f"{badge['label']}: {badge['value']}" for badge in badges]
        layout_width = max(card_width - 2 * padding_x, int(160 * safe_scale))
        badge_section_height = 0
        if badge_texts:
            badge_section_height, _ = self._compute_badge_layout(
                badge_texts,
                badge_font,
                layout_width,
                badge_height,
                badge_gap,
                badge_inner_pad,
            )
        footer_padding = max(int(10 * safe_scale), 6)
        footer_height = badge_section_height + 2 * footer_padding if badge_texts else 0

        card_height = header_height + body_height + chips_height + footer_height
        return card_width, int(card_height)

    def _determine_scene_card_size(self, text, entity_count):
        length = len(text or "")
        if entity_count >= 5 or length > 900:
            return "L"
        if length < 280 and entity_count <= 2:
            return "S"
        return "M"

    def _extract_scene_type_label(self, entry, explicit_type=None):
        if isinstance(explicit_type, str) and explicit_type.strip():
            return explicit_type.strip()
        if isinstance(entry, dict):
            for key in ("SceneType", "Type", "Category", "Mood", "Role"):
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        if isinstance(entry, str):
            return entry.strip()
        return ""

    def _classify_scene_type(self, type_label):
        text = (type_label or "").lower()
        if any(token in text for token in ("setup", "intro", "hook", "opening")):
            return "setup"
        if any(token in text for token in ("choice", "decision", "branch", "option")):
            return "choice"
        if any(token in text for token in ("invest", "myster", "clue", "explor", "detect")):
            return "investigation"
        if any(token in text for token in ("combat", "battle", "fight", "skirmish", "attack")):
            return "combat"
        if any(token in text for token in ("outcome", "result", "resolution", "aftermath", "conclusion")):
            return "outcome"
        if any(token in text for token in ("social", "roleplay", "diplom", "parley", "talk")):
            return "social"
        if any(token in text for token in ("travel", "journey", "chase", "pursuit", "voyage")):
            return "travel"
        if any(token in text for token in ("downtime", "rest", "interlude", "camp")):
            return "downtime"
        return "scene"

    def _resolve_scene_type_style(self, source_entry, fallback_color, explicit_type=None):
        raw_label = self._extract_scene_type_label(source_entry, explicit_type)
        canonical = self._classify_scene_type(raw_label)
        style = SCENE_TYPE_STYLE_MAP.get(canonical)
        if style:
            return style["label"], style["color"], canonical
        label = raw_label if raw_label else "Scene"
        color = fallback_color or SCENE_TYPE_STYLE_MAP.get("setup", {}).get("color", "#3B82F6")
        return label, color, canonical

    def _extract_scene_badges(self, source_entry):
        if not isinstance(source_entry, dict):
            return []
        badges = []
        difficulty = source_entry.get("Difficulty") or source_entry.get("difficulty")
        if difficulty:
            badges.append({"label": "Difficulty", "value": self._normalize_badge_value(difficulty)})
        rewards = (
            source_entry.get("Rewards")
            or source_entry.get("Reward")
            or source_entry.get("Treasure")
            or source_entry.get("Loot")
        )
        if rewards:
            badges.append({"label": "Rewards", "value": self._normalize_badge_value(rewards)})
        clue = (
            source_entry.get("Clue")
            or source_entry.get("ClueNumber")
            or source_entry.get("Clue #")
            or source_entry.get("ClueID")
        )
        if clue:
            badges.append({"label": "Clue #", "value": self._normalize_badge_value(clue)})
        return [badge for badge in badges if badge["value"]]

    def _normalize_badge_value(self, value):
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            joined = ", ".join(str(item).strip() for item in value if str(item).strip())
            return self._truncate_line(joined, 40)
        if isinstance(value, dict):
            parts = [f"{key}: {val}" for key, val in value.items() if val]
            return self._truncate_line(", ".join(parts), 40)
        text = str(value).strip()
        return self._truncate_line(text, 40)

    def _compute_badge_layout(self, texts, font_obj, max_width, badge_height, gap, inner_padding):
        if not texts:
            return 0, []
        safe_width = max(int(max_width), 50)
        positions = []
        x_offset = 0
        y_offset = 0
        for text in texts:
            text_width = font_obj.measure(text) + inner_padding * 2
            text_width = min(text_width, safe_width)
            if x_offset > 0 and x_offset + text_width > safe_width:
                x_offset = 0
                y_offset += badge_height + gap
            positions.append((x_offset, y_offset, text_width))
            x_offset += text_width + gap
        total_height = positions[-1][1] + badge_height
        return total_height, positions


    def show_scene_flow(self):
        if not self.scenario:
            messagebox.showinfo("Select Scenario", "Please select a scenario first to build the scene flow view.")
            return
        if getattr(self, "_scene_flow_window", None) and self._scene_flow_window.winfo_exists():
            try:
                self._scene_flow_window.focus()
                self._scene_flow_window.lift()
            except Exception:
                pass
            return

        try:
            from modules.scenarios.scene_flow_viewer import SceneFlowViewerWindow
        except ImportError as exc:  # pragma: no cover - defensive guard
            messagebox.showerror(
                "Scene Flow",
                f"Unable to open the scene flow viewer: {exc}",
            )
            return

        def _on_close():
            self._scene_flow_window = None

        self._scene_flow_window = SceneFlowViewerWindow(
            self.winfo_toplevel(),
            scenario_wrapper=self.scenario_wrapper,
            npc_wrapper=self.npc_wrapper,
            creature_wrapper=self.creature_wrapper,
            place_wrapper=self.place_wrapper,
            initial_scenario=self.scenario,
            on_close=_on_close,
        )

    def select_scenario(self):
        def on_scenario_selected(scenario_name):
            # Lookup the full pc dictionary using the pc wrapper.
            scenario_list = self.scenario_wrapper.load_items()
            selected_scenario = None
            for scenario in scenario_list:
                if scenario.get("Title") == scenario_name:
                    selected_scenario = scenario
                    break
            if not selected_scenario:
                messagebox.showerror("Error", f"scenario '{scenario_name}' not found.")
                return
            dialog.destroy()
            self.load_scenario(selected_scenario)

        scenario_template = load_template("scenarios")
        dialog = ctk.CTkToplevel(self)
        dialog.title("Select scenario")
        dialog.geometry("1200x800")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()
        # The new GenericListSelectionView returns the pc name (string)
        selection_view = GenericListSelectionView(
            dialog,
            "scenarios",
            self.scenario_wrapper,
            scenario_template,
            on_select_callback=lambda et, scenario: on_scenario_selected(scenario)
        )
        selection_view.pack(fill="both", expand=True)
        dialog.wait_window()


    def display_portrait_window(self):
       #logging.debug("Entering display_portrait_window")
        if not self.selected_node or not (self.selected_node.startswith("npc_") or self.selected_node.startswith("creature_")):
            messagebox.showerror("Error", "No NPC or Creature selected.")
            return

        # Extract name after prefix. Note that creatures use "creature_" prefix.
        if self.selected_node.startswith("npc_"):
            name_key = self.selected_node.replace("npc_", "").replace("_", " ")
            data_source = self.npcs
        else:
            name_key = self.selected_node.replace("creature_", "").replace("_", " ")
            data_source = self.creatures

       #logging.debug(f"Extracted name: {name_key}")
        entity_data = data_source.get(name_key)
        if not entity_data:
            messagebox.showerror("Error", f"Entity '{name_key}' not found.")
            return

        portrait_path = primary_portrait(entity_data.get("Portrait", ""))
        resolved_portrait = resolve_portrait_path(portrait_path, ConfigHelper.get_campaign_dir())
        if not resolved_portrait or not os.path.exists(resolved_portrait):
            messagebox.showerror("Error", "No valid portrait found for this entity.")
            return
        show_portrait(portrait_path, name_key)
        

    def load_scenario(self, scenario):
        # Use full text; no truncation—wrapping will be handled by canvas.
        summary = scenario.get("Summary", "")
        summary = clean_longtext(summary, max_length=5000)
        # Extract secret for the scenario node.
        secret = scenario.get("Secret", "")
        secret = clean_longtext(secret, max_length=5000)
        self.scenario = scenario
        self.graph = {"nodes": [], "links": []}
        self.node_positions.clear()
        self._hide_detail_panel()
        self._clear_detail_panel()

        center_x, center_y = 400, 300
        scenario_title = scenario.get("Title", "No Title")
        scenario_tag = self._build_tag("scenario", scenario_title)
        self.graph["nodes"].append({
            "type": "scenario",
            "name": scenario_title,
            "x": center_x,
            "y": center_y,
            "color": "darkolivegreen",
            "data": {**scenario, "Summary": summary, "Secret": secret}
        })
        self.node_positions[scenario_tag] = (center_x, center_y)

        # NPC nodes
        npcs_list = scenario.get("NPCs", [])
        npcs_count = len(npcs_list)
        if npcs_count > 0:
            arc_start_npcs = 30
            arc_end_npcs = 150
            offset_npcs = 350

            for i, npc_name in enumerate(npcs_list):
                if npc_name not in self.npcs:
                    continue
                angle_deg = (arc_start_npcs if npcs_count == 1
                            else arc_start_npcs + i * (arc_end_npcs - arc_start_npcs) / (npcs_count - 1))
                angle_rad = math.radians(angle_deg)
                x = center_x + offset_npcs * math.cos(angle_rad)
                y = center_y + offset_npcs * math.sin(angle_rad)
                npc_data = self.npcs[npc_name]
                secret = npc_data.get("Secret", "")
                secret = clean_longtext(secret, max_length=5000)
                npc_data["Secret"] = secret
                traits = npc_data.get("Traits", "")
                traits = clean_longtext(traits, max_length=5000)
                npc_data["Traits"] = traits
                npc_tag = self._build_tag("npc", npc_name)
                self.graph["nodes"].append({
                    "type": "npc",
                    "name": npc_name,
                    "x": x,
                    "y": y,
                    "color": "darkslateblue",
                    "data": npc_data
                })
                self.node_positions[npc_tag] = (x, y)
                self.graph["links"].append({
                    "from": scenario_tag,
                    "to": npc_tag,
                    "text": ""
                })

        # Place nodes
        places_list = scenario.get("Places", [])
        places_count = len(places_list)
        if places_count > 0:
            arc_start_places = 210
            arc_end_places = 330
            offset_places = 350

            for j, place_name in enumerate(places_list):
                if place_name not in self.places:
                    continue
                angle_deg = (arc_start_places if places_count == 1
                            else arc_start_places + j * (arc_end_places - arc_start_places) / (places_count - 1))
                angle_rad = math.radians(angle_deg)
                x = center_x + offset_places * math.cos(angle_rad)
                y = center_y + offset_places * math.sin(angle_rad)
                place_data = self.places[place_name]
                pd = place_data.get("Description", "")
                pd = clean_longtext(pd, max_length=5000)
                place_data["Description"] = pd
                # Add secret field processing for places
                secret = place_data.get("Secret", "")
                secret = clean_longtext(secret, max_length=5000)
                place_data["Secret"] = secret
                place_tag = self._build_tag("place", place_name)
                self.graph["nodes"].append({
                    "type": "place",
                    "name": place_name,
                    "x": x,
                    "y": y,
                    "color": "sienna",
                    "data": place_data
                })
                self.node_positions[place_tag] = (x, y)
                self.graph["links"].append({
                    "from": scenario_tag,
                    "to": place_tag,
                    "text": ""
                })

        # Creature nodes
        creatures_list = scenario.get("Creatures") or []
        creatures_count = len(creatures_list)
        if creatures_count > 0:
            # Define an arc for creatures (e.g. between 150° and 210°)
            arc_start_creatures = 150
            arc_end_creatures = 210
            offset_creatures = 350

            for k, creature_name in enumerate(creatures_list):
                if creature_name not in self.creatures:
                    continue
                angle_deg = (arc_start_creatures if creatures_count == 1
                            else arc_start_creatures + k * (arc_end_creatures - arc_start_creatures) / (creatures_count - 1))
                angle_rad = math.radians(angle_deg)
                x = center_x + offset_creatures * math.cos(angle_rad)
                y = center_y + offset_creatures * math.sin(angle_rad)
                creature_data = self.creatures[creature_name]
                desc = creature_data.get("Description", "")
                desc = clean_longtext(desc, max_length=5000)
                creature_data["Description"] = desc
                # Add secret field processing for creatures
                weakness = creature_data.get("Weakness", "")
                weakness = clean_longtext(weakness, max_length=5000)
                creature_data["Weakness"] = weakness
                creature_tag = self._build_tag("creature", creature_name)
                self.graph["nodes"].append({
                    "type": "creature",
                    "name": creature_name,
                    "x": x,
                    "y": y,
                    "color": "darkblue",
                    "data": creature_data
                })
                self.node_positions[creature_tag] = (x, y)
                self.graph["links"].append({
                    "from": scenario_tag,
                    "to": creature_tag,
                    "text": ""
                })

        self.draw_graph()
        self.canvas.update_idletasks()

        # Center view on scenario node (or graph content center)
        if scenario_tag in self.node_positions:
            x, y = self.node_positions[scenario_tag]

            # Get current scrollregion
            scroll_x0, scroll_y0, scroll_x1, scroll_y1 = self.canvas.bbox("all")
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            # Calculate scroll fractions (clamped between 0.0 and 1.0)
            scroll_x_frac = max(0.0, min(1.0, (x - canvas_width / 2 - scroll_x0) / (scroll_x1 - scroll_x0)))
            scroll_y_frac = max(0.0, min(1.0, (y - canvas_height / 2 - scroll_y0) / (scroll_y1 - scroll_y0)))

            self.canvas.xview_moveto(scroll_x_frac)
            self.canvas.yview_moveto(scroll_y_frac)

    def load_scenario_scene_flow(self, scenario=None):
        if scenario is not None:
            self.scenario = scenario
        scenario_data = self.scenario
        if not scenario_data:
            messagebox.showinfo("Select Scenario", "Please select a scenario first to build the scene flow view.")
            return

        scenes_raw = scenario_data.get("Scenes")
        scenes_list = self._coerce_scene_list(scenes_raw)
        if not scenes_list:
            messagebox.showinfo("Scene Flow", "This scenario does not contain any scenes to display.")
            return

        scenario_npcs = self._dedupe_preserve_order(self._to_list(scenario_data.get("NPCs")))
        scenario_creatures = self._dedupe_preserve_order(self._to_list(scenario_data.get("Creatures")))
        scenario_places = self._dedupe_preserve_order(self._to_list(scenario_data.get("Places")))

        normalized_scenes = []
        for idx, entry in enumerate(scenes_list):
            normalized = self._normalize_scene_entry(
                entry,
                idx,
                scenario_npcs,
                scenario_creatures,
                scenario_places
            )
            if normalized:
                normalized_scenes.append(normalized)

        if not normalized_scenes:
            messagebox.showinfo("Scene Flow", "No readable scenes were found for this scenario.")
            return

        self.graph = {"nodes": [], "links": []}
        self.node_positions.clear()
        self.scene_flow_scenes = normalized_scenes
        self._show_detail_panel()
        self._clear_detail_panel()

        count = len(normalized_scenes)
        max_card_width = SCENE_CARD_WIDTHS["M"]
        max_card_height = 0
        card_widths = []
        card_heights = []
        for scene in normalized_scenes:
            text = scene.get("text", "") or ""
            entities = scene.get("entities") or []
            source_entry = scene.get("source_entry") or {}
            card_size = self._determine_scene_card_size(text, len(entities)) or "M"
            card_width, card_height = self._estimate_scene_card_dimensions(
                text,
                entities if isinstance(entities, list) else [],
                source_entry if isinstance(source_entry, dict) else {},
                card_size,
                scale=1.0,
            )
            scene["card_width"] = card_width
            scene["card_height"] = card_height
            card_widths.append(card_width)
            card_heights.append(card_height)
            max_card_width = max(max_card_width, card_width)
            max_card_height = max(max_card_height, card_height)

        avg_card_width = sum(card_widths) / max(1, len(card_widths))
        avg_card_height = sum(card_heights) / max(1, len(card_heights))
        base_padding_x = max(12, int(avg_card_width * 0.05))
        base_padding_y = max(12, int(avg_card_height * 0.08))

        self.canvas.update_idletasks()
        canvas_width = max(self.canvas.winfo_width(), 1)
        origin_x = 400
        origin_y = 260

        def build_rows(col_count):
            return [normalized_scenes[i:i + col_count] for i in range(0, count, col_count)]

        def build_column_widths(rows, col_count):
            widths = [0] * col_count
            for row in rows:
                for col_index in range(col_count):
                    if col_index >= len(row):
                        continue
                    scene = row[col_index]
                    widths[col_index] = max(widths[col_index], scene.get("card_width", max_card_width))
            return widths

        def build_row_heights(rows):
            heights = []
            for row in rows:
                row_height = 0
                for scene in row:
                    row_height = max(row_height, scene.get("card_height", max_card_height))
                heights.append(row_height)
            return heights

        def choose_columns(padding_x):
            max_cols = max(1, count)
            chosen = 1
            for col_count in range(1, max_cols + 1):
                rows = build_rows(col_count)
                col_widths = build_column_widths(rows, col_count)
                total_width = sum(col_widths) + padding_x * max(0, col_count - 1)
                if total_width <= canvas_width:
                    chosen = col_count
            return chosen

        def compute_layout(padding_x, padding_y):
            col_count = choose_columns(padding_x)
            rows = build_rows(col_count)
            row_count = max(1, len(rows))
            col_widths = build_column_widths(rows, col_count)
            row_heights = build_row_heights(rows)
            total_width = sum(col_widths) + padding_x * max(0, col_count - 1)
            column_centers = []
            cursor_x = origin_x - total_width / 2
            for width in col_widths:
                column_centers.append(cursor_x + width / 2)
                cursor_x += width + padding_x
            row_centers = []
            cursor_y = origin_y
            for height in row_heights:
                row_centers.append(cursor_y + height / 2)
                cursor_y += height + padding_y
            positions = []
            for row_index, row in enumerate(rows):
                for col_index, _scene in enumerate(row):
                    positions.append((column_centers[col_index], row_centers[row_index]))
            return col_count, row_count, positions

        def layout_has_overlap(positions):
            bboxes = []
            for (x, y), scene in zip(positions, normalized_scenes):
                width = scene.get("card_width", max_card_width)
                height = scene.get("card_height", max_card_height)
                bbox = (x - width / 2, y - height / 2, x + width / 2, y + height / 2)
                for existing in bboxes:
                    if not (
                        bbox[2] <= existing[0]
                        or bbox[0] >= existing[2]
                        or bbox[3] <= existing[1]
                        or bbox[1] >= existing[3]
                    ):
                        return True
                bboxes.append(bbox)
            return False

        padding_x = base_padding_x
        padding_y = base_padding_y
        positions = []
        for _ in range(3):
            cols, rows, positions = compute_layout(padding_x, padding_y)
            if not layout_has_overlap(positions):
                break
            padding_x = int(padding_x * 1.2)
            padding_y = int(padding_y * 1.2)
        if layout_has_overlap(positions):
            log_warning("Scene flow layout overlaps detected; padding adjustments were insufficient.")

        for idx, scene in enumerate(normalized_scenes):
            x, y = positions[idx]

            display_name = scene.get("display_name") or f"Scene {idx + 1}"
            node_tag = self._build_tag("scene", display_name)
            scene["tag"] = node_tag
            node_data = {
                "type": "scene",
                "name": display_name,
                "x": x,
                "y": y,
                "color": scene.get("color", "#d1a86d"),
                "data": {
                    "Text": scene.get("text", ""),
                    "FullText": scene.get("text", ""),
                    "Entities": scene.get("entities", []),
                    "SourceEntry": scene.get("source_entry"),
                    "SceneType": self._extract_scene_type_label(scene.get("source_entry")),
                    "CardSize": self._determine_scene_card_size(scene.get("text", ""), len(scene.get("entities", [])))
                }
            }
            self.graph["nodes"].append(node_data)
            self.node_positions[node_tag] = (x, y)

        lookup, index_lookup = self._build_scene_lookup(normalized_scenes)
        self.scene_flow_scene_lookup = {
            scene.get("tag"): scene for scene in normalized_scenes if scene.get("tag")
        }

        existing_links = set()
        tag_lookup = self.scene_flow_scene_lookup
        for scene in normalized_scenes:
            from_tag = scene.get("tag")
            if not from_tag:
                continue
            links = list(scene.get("links", []))
            if not links and scene.get("index", 0) < count - 1:
                next_scene = normalized_scenes[scene["index"] + 1]
                if next_scene.get("tag"):
                    links.append(
                        {
                            "target_tag": next_scene["tag"],
                            "text": "",
                            "text_auto_generated": True,
                        }
                    )
            prepared_links = []

            for link in links:
                text_auto_generated = bool(link.get("text_auto_generated"))
                text = (link.get("text") or "").strip()
                if (
                    text_auto_generated
                    and self._link_text_matches_target(text, link)
                ):
                    text = ""
                    link["text"] = ""
                if not text and not text_auto_generated:
                    text_auto_generated = True
                    link["text_auto_generated"] = True

                target_tag = link.get("target_tag")
                if not target_tag:
                    target_index = link.get("target_index")
                    if isinstance(target_index, int):
                        target_tag = index_lookup.get(target_index)
                if not target_tag:
                    target_tag = self._resolve_scene_reference(link.get("target_key"), lookup, index_lookup)
                if not target_tag:
                    target_tag = self._resolve_scene_reference(link.get("target"), lookup, index_lookup)

                if not target_tag or target_tag == from_tag:
                    continue

                target_scene = tag_lookup.get(target_tag)
                if target_scene and not isinstance(link.get("target_index"), int):
                    link["target_index"] = target_scene.get("index")
                link["target_tag"] = target_tag
                link["source_tag"] = from_tag
                link["source_scene_index"] = scene.get("index")
                if target_scene:
                    link["target_scene_index"] = target_scene.get("index")

                prepared_links.append(
                    {
                        "text": text,
                        "text_auto_generated": text_auto_generated,
                        "target_tag": target_tag,
                        "target_scene": target_scene,
                        "link": link,
                    }
                )

            pairs_with_explicit = {
                (from_tag, item["target_tag"])
                for item in prepared_links
                if not item["text_auto_generated"]
            }

            for item in prepared_links:
                pair = (from_tag, item["target_tag"])
                if item["text_auto_generated"] and pair in pairs_with_explicit:
                    continue

                key = (from_tag, item["target_tag"], item["text"])
                if key in existing_links:
                    continue
                existing_links.add(key)

                self.graph["links"].append({
                    "from": from_tag,
                    "to": item["target_tag"],
                    "text": item["text"],
                    "source_scene_index": scene.get("index"),
                    "target_scene_index": item["target_scene"].get("index") if item["target_scene"] else None,
                    "link_data": item["link"],
                    "text_auto_generated": item["text_auto_generated"],
                })

        self.original_positions = dict(self.node_positions)
        self.canvas_scale = 1.0
        self.draw_graph()
        self.canvas.update_idletasks()

        bbox_nodes = self.canvas.bbox("node")
        bbox_all = self.canvas.bbox("all")
        target_bbox = bbox_nodes or bbox_all
        if target_bbox:
            x0, y0, x1, y1 = target_bbox
            canvas_width = self.canvas.winfo_width() or 1
            canvas_height = self.canvas.winfo_height() or 1
            center_x = (x0 + x1) / 2
            center_y = (y0 + y1) / 2
            span_x = max(1, x1 - x0)
            span_y = max(1, y1 - y0)
            self.canvas.xview_moveto(max(0.0, min(1.0, (center_x - canvas_width / 2 - x0) / span_x)))
            self.canvas.yview_moveto(max(0.0, min(1.0, (center_y - canvas_height / 2 - y0) / span_y)))

    def _coerce_scene_list(self, scenes_raw):
        if not scenes_raw:
            return []
        if isinstance(scenes_raw, list):
            return scenes_raw
        if isinstance(scenes_raw, dict):
            if isinstance(scenes_raw.get("Scenes"), list):
                return scenes_raw["Scenes"]
            return [scenes_raw]
        if isinstance(scenes_raw, str):
            text = scenes_raw.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                if isinstance(parsed.get("Scenes"), list):
                    return parsed["Scenes"]
                return [parsed]
            blocks = [block.strip() for block in re.split(r"\n{2,}", text) if block.strip()]
            return blocks or [text]
        return [scenes_raw]

    def _normalize_scene_entry(self, entry, index, scenario_npcs, scenario_creatures, scenario_places):
        raw_text = ""
        if isinstance(entry, dict):
            text_fragments: list[str] = []
            fragment_keys: set[str] = set()

            def register_fragment(value) -> None:
                if value is None:
                    return
                fragment = str(value)
                normalized = re.sub(r"\s+", " ", fragment).strip()
                if not normalized:
                    return
                key = normalized.lower()
                if key in fragment_keys:
                    return
                fragment_keys.add(key)
                text_fragments.append(fragment.strip())

            for key in ("Text", "text", "Description", "Summary", "Body", "Details", "Notes", "Gist", "Content"):
                value = entry.get(key)
                if isinstance(value, str):
                    register_fragment(value)
                elif isinstance(value, list):
                    for item in value:
                        register_fragment(item)
                elif isinstance(value, dict):
                    if isinstance(value.get("text"), str):
                        register_fragment(value.get("text"))
                    else:
                        for item in value.values():
                            if isinstance(item, str):
                                register_fragment(item)
            raw_text = "\n\n".join(fragment for fragment in text_fragments if str(fragment).strip())
            if not raw_text:
                alt = entry.get("text")
                if isinstance(alt, dict):
                    raw_text = alt.get("text", "")
                elif isinstance(alt, str):
                    raw_text = alt
        elif isinstance(entry, str):
            raw_text = entry
        else:
            raw_text = str(entry)

        cleaned_text = clean_longtext(raw_text, max_length=1600).strip()
        lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]

        title_text = ""
        if isinstance(entry, dict):
            for key in ("Title", "Scene", "Heading", "Name", "Label"):
                val = entry.get(key)
                if isinstance(val, str) and val.strip():
                    title_text = val.strip()
                    break

        if not title_text and lines:
            title_text = lines[0]
            lines = lines[1:]
        title_text = self._clean_scene_title(title_text) if title_text else ""

        if lines:
            body_text = "\n".join(lines).strip()
        else:
            body_text = cleaned_text

        if len(body_text) > 1200:
            trimmed = body_text[:1200]
            cut = trimmed.rfind(" ")
            if cut > 900:
                trimmed = trimmed[:cut]
            body_text = trimmed.rstrip() + "..."

        if not title_text:
            title_text = f"Scene {index + 1}"

        npc_names = []
        creature_names = []
        place_names = []
        if isinstance(entry, dict):
            for field in ("NPCs", "InvolvedNPCs", "Participants", "Allies", "Characters"):
                npc_names.extend(self._to_list(entry.get(field)))
            for field in ("Creatures", "Monsters", "Enemies", "Foes", "Opponents", "Threats"):
                creature_names.extend(self._to_list(entry.get(field)))
            for field in ("Places", "Locations", "Site", "Setting", "Where", "Venue"):
                place_names.extend(self._to_list(entry.get(field)))

            entity_blob = entry.get("Entities") or entry.get("EntityRefs") or entry.get("Actors")
            if isinstance(entity_blob, list):
                for ent in entity_blob:
                    if isinstance(ent, dict):
                        ent_type = (ent.get("type") or ent.get("Type") or ent.get("category") or "").lower()
                        ent_name = ent.get("name") or ent.get("Name") or ent.get("title")
                        if ent_name:
                            if ent_type in ("npc", "character", "ally"):
                                npc_names.append(ent_name)
                            elif ent_type in ("creature", "monster", "enemy", "foe"):
                                creature_names.append(ent_name)
                            elif ent_type in ("place", "location", "site"):
                                place_names.append(ent_name)
                            else:
                                npc_names.append(ent_name)
                    elif isinstance(ent, str):
                        npc_names.append(ent)

        npc_names = self._dedupe_preserve_order(npc_names)
        creature_names = self._dedupe_preserve_order(creature_names)
        place_names = self._dedupe_preserve_order(place_names)

        search_text = f"{title_text}\n{body_text}".lower()
        if not npc_names:
            npc_names.extend(self._find_mentions(search_text, scenario_npcs))
        if not creature_names:
            creature_names.extend(self._find_mentions(search_text, scenario_creatures))
        if not place_names:
            place_names.extend(self._find_mentions(search_text, scenario_places))

        npc_names = self._dedupe_preserve_order(npc_names)
        creature_names = self._dedupe_preserve_order(creature_names)
        place_names = self._dedupe_preserve_order(place_names)

        entities = []
        seen_pairs = set()

        def add_entities(names, ent_type):
            for name in names:
                cleaned = str(name).strip()
                if not cleaned:
                    continue
                key = (ent_type, cleaned.lower())
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                record = self._lookup_entity_by_name(ent_type, cleaned)
                portrait = self._extract_entity_image(record, ent_type) if record else ""
                synopsis = self._build_entity_synopsis(ent_type, record) if record else ""
                entities.append({
                    "type": ent_type,
                    "name": cleaned,
                    "portrait": portrait,
                    "synopsis": synopsis
                })

        add_entities(npc_names, "npc")
        add_entities(creature_names, "creature")
        add_entities(place_names, "place")

        raw_links = []
        if isinstance(entry, dict):
            for field in ("Links", "Transitions", "Choices", "Branches", "Paths", "Outcomes"):
                raw_links.extend(self._coerce_scene_links(entry.get(field)))
            for field in ("Next", "NextScene", "NextScenes", "LeadsTo", "OnSuccess", "OnFailure", "IfSuccess", "IfFailure"):
                raw_links.extend(self._coerce_scene_links(entry.get(field)))

        normalised_links = []
        seen_links = set()
        for item in raw_links:
            if not isinstance(item, dict):
                continue
            target_value = item.get("target")
            text_value = item.get("text")
            if isinstance(target_value, dict):
                target_value = target_value.get("target") or target_value.get("Scene") or target_value.get("Next")
            text_clean = self._normalise_link_text_value(text_value)
            target_index = None
            if isinstance(target_value, (int, float)):
                target_index = int(target_value)
            elif isinstance(target_value, str):
                stripped = target_value.strip()
                if stripped.isdigit():
                    target_index = int(stripped)
                else:
                    match = re.search(r"(scene|act)\s*(\d+)", stripped, re.IGNORECASE)
                    if match:
                        target_index = int(match.group(2))
            key = (repr(target_value), text_clean)
            if key in seen_links:
                continue
            seen_links.add(key)
            normalised_links.append(
                {
                    "target": target_value,
                    "target_key": target_value,
                    "target_index": target_index,
                    "text": text_clean,
                    "text_auto_generated": bool(
                        item.get("text_auto_generated")
                    ),
                }
            )

        base_title = title_text.strip()
        if len(base_title) > 80:
            base_title = base_title[:77].rstrip() + "..."
        display_title = base_title or f"Scene {index + 1}"
        display_name = f"{index + 1}. {display_title}"
        if len(display_name) > 60:
            display_name = display_name[:57].rstrip() + "..."

        identifiers = set()
        identifiers.add(str(index + 1))
        identifiers.add(display_title)
        identifiers.add(display_name)
        identifiers.add(self._normalize_scene_identifier_key(display_title))
        identifiers.add(self._slugify_scene_identifier(display_title))
        if isinstance(entry, dict):
            for key_name in ("Id", "ID", "SceneId", "Key", "Slug", "Tag", "Reference"):
                value = entry.get(key_name)
                if value:
                    identifiers.add(str(value))
                    norm = self._normalize_scene_identifier_key(value)
                    if norm:
                        identifiers.add(norm)
                    slug = self._slugify_scene_identifier(value)
                    if slug:
                        identifiers.add(slug)

        identifiers = {ident for ident in identifiers if ident}

        return {
            "index": index,
            "display_name": display_name,
            "title": display_title,
            "text": body_text,
            "entities": entities,
            "links": normalised_links,
            "color": self._scene_color_from_entry(entry),
            "identifiers": identifiers,
            "source_entry": entry if isinstance(entry, dict) else None,
        }

    def _scene_color_from_entry(self, entry):
        if not isinstance(entry, dict):
            return "#d1a86d"
        type_value = entry.get("Type") or entry.get("type") or entry.get("Category") or entry.get("SceneType") or entry.get("Mood")
        if isinstance(type_value, str):
            lowered = type_value.lower()
            if any(token in lowered for token in ("combat", "battle", "fight", "skirmish")):
                return "#b96a55"
            if any(token in lowered for token in ("social", "role", "parley", "diplom")):
                return "#4f6fb5"
            if any(token in lowered for token in ("invest", "myster", "clue", "explor")):
                return "#c3973a"
            if any(token in lowered for token in ("travel", "chase", "journey", "pursuit")):
                return "#5e8f6b"
            if any(token in lowered for token in ("downtime", "rest", "interlude")):
                return "#8d7ac0"
        return "#d1a86d"

    def _clean_scene_title(self, text):
        if not text:
            return ""
        cleaned = str(text).strip()
        cleaned = re.sub(r"^[\u2022\-\*\s\t]+", "", cleaned)
        cleaned = re.sub(r"^(?:scene|act)\s*\d+\s*[:.\-]*\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^[^\w]+", "", cleaned)
        return cleaned.strip()

    def _to_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, dict):
                    name = item.get("Name") or item.get("Title") or item.get("name") or item.get("text")
                    if name:
                        result.append(str(name).strip())
                else:
                    item_str = str(item).strip()
                    if item_str:
                        result.append(item_str)
            return result
        if isinstance(value, (set, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, dict):
            collected = []
            for sub in value.values():
                collected.extend(self._to_list(sub))
            return collected
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if parsed is not None:
                return self._to_list(parsed)
            parts = [part.strip() for part in re.split(r"[,;\n]", text) if part.strip()]
            return parts or [text]
        return [str(value)]

    def _dedupe_preserve_order(self, values):
        result = []
        seen = set()
        for value in values or []:
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    def _lookup_entity_by_name(self, entity_type, name):
        if not name:
            return None
        name_text = str(name).strip()
        if not name_text:
            return None
        pools = {
            "npc": self.npcs,
            "creature": self.creatures,
            "place": self.places,
        }
        collection = pools.get(entity_type)
        if not isinstance(collection, dict):
            return None
        if name_text in collection:
            return collection[name_text]
        lower = name_text.lower()
        for key, value in collection.items():
            if key.lower() == lower:
                return value
        return None

    def _normalize_synopsis_text(self, value, max_length=240):
        if value is None:
            return ""
        snippet = clean_longtext(value, max_length=max_length)
        snippet = snippet.strip()
        if not snippet:
            return ""
        if snippet.lower() == "none":
            return ""
        return snippet

    def _build_entity_synopsis(self, entity_type, record):
        if not isinstance(record, dict):
            return ""

        type_specific = {
            "npc": [
                "Synopsis", "Summary", "Description", "Background",
                "Traits", "Role", "Motivation", "Personality",
                "RoleplayingCues", "Quote"
            ],
            "creature": [
                "Synopsis", "Summary", "Description", "Background",
                "Type", "Powers", "Weakness", "Stats"
            ],
            "place": [
                "Synopsis", "Summary", "Description", "Background",
                "Secrets", "Tags"
            ],
        }
        fallback_fields = [
            "Synopsis", "Summary", "Description", "Background",
            "Notes", "Details", "Text"
        ]

        fields = type_specific.get(entity_type, []) + fallback_fields
        seen = set()
        for field in fields:
            key = field.lower()
            if key in seen:
                continue
            seen.add(key)
            snippet = self._normalize_synopsis_text(record.get(field))
            if snippet:
                return snippet

        # Assemble a short synopsis from smaller fields if needed
        composite_map = {
            "npc": [("Role", "Role"), ("Motivation", "Motivation"), ("Traits", "Traits")],
            "creature": [("Type", "Type"), ("Powers", "Powers"), ("Weakness", "Weakness")],
            "place": [("Tags", "Tags"), ("Population", "Population"), ("Secrets", "Secrets")],
        }
        parts = []
        for label, key in composite_map.get(entity_type, []):
            snippet = self._normalize_synopsis_text(record.get(key), max_length=120)
            if snippet:
                parts.append(f"{label}: {snippet}")
            if len(parts) >= 2:
                break
        if parts:
            return "\n".join(parts)

        return ""

    def _get_entity_synopsis_for_display(self, entity):
        if not isinstance(entity, dict):
            return ""
        synopsis = entity.get("synopsis")
        synopsis = self._normalize_synopsis_text(synopsis) if synopsis else ""
        if synopsis:
            return synopsis
        for key in ("Summary", "summary", "Description", "description", "Text", "text", "Notes", "notes"):
            value = entity.get(key)
            snippet = self._normalize_synopsis_text(value)
            if snippet:
                return snippet
        return ""

    def _compose_entity_tooltip_text(self, entity_info):
        if not isinstance(entity_info, dict):
            return ""
        name = entity_info.get("name", "") or ""
        ent_type = entity_info.get("type", "") or ""
        synopsis = entity_info.get("synopsis", "") or ""
        synopsis = self._normalize_synopsis_text(synopsis)
        header = ""
        if name and ent_type:
            header = f"{name} ({ent_type.title()})"
        elif name:
            header = name
        elif ent_type:
            header = ent_type.title()

        if synopsis:
            if header:
                return f"{header}\n\n{synopsis}"
            return synopsis
        fallback = "No synopsis available."
        if header:
            return f"{header}\n\n{fallback}"
        return fallback

    def _load_entity_tooltip_portrait(self, entity_info):
        if not isinstance(entity_info, dict):
            return None

        portrait_path = ""
        for key in (
            "portrait_path",
            "portrait",
            "Portrait",
            "image",
            "Image",
            "tokenImage",
            "TokenImage",
            "token",
            "Token",
        ):
            value = entity_info.get(key)
            if value:
                portrait_path = value
                break

        if not portrait_path:
            return None

        resolved_path = self._resolve_existing_image_path(portrait_path)
        if not resolved_path and os.path.exists(portrait_path):
            resolved_path = portrait_path

        if not resolved_path:
            return None

        cache_key = (resolved_path, ENTITY_TOOLTIP_PORTRAIT_MAX_SIZE)
        cached = self._entity_tooltip_image_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            with Image.open(resolved_path) as pil_img:
                img = pil_img.copy()
            resample_method = getattr(Image, "Resampling", Image).LANCZOS
            img.thumbnail(ENTITY_TOOLTIP_PORTRAIT_MAX_SIZE, resample_method)
            photo = ImageTk.PhotoImage(img, master=self)
            self._entity_tooltip_image_cache[cache_key] = photo
            return photo
        except Exception:
            return None

    def _cancel_entity_tooltip_schedule(self):
        if self._entity_tooltip_after_id:
            try:
                self.after_cancel(self._entity_tooltip_after_id)
            except Exception:
                pass
            self._entity_tooltip_after_id = None
        self._entity_tooltip_pending = None

    def _cancel_entity_tooltip_hide(self):
        if self._entity_tooltip_hide_after_id:
            try:
                self.after_cancel(self._entity_tooltip_hide_after_id)
            except Exception:
                pass
            self._entity_tooltip_hide_after_id = None

    def _hide_entity_tooltip(self):
        self._cancel_entity_tooltip_hide()
        if self._entity_tooltip_window:
            try:
                self._entity_tooltip_window.destroy()
            except Exception:
                pass
            self._entity_tooltip_window = None
        self._entity_tooltip_active_tag = None

    def _dismiss_entity_tooltip(self):
        self._cancel_entity_tooltip_schedule()
        self._hide_entity_tooltip()

    def _schedule_entity_tooltip_hide(self, tag, delay=ENTITY_TOOLTIP_HIDE_DELAY_MS):
        if tag and self._entity_tooltip_active_tag and tag != self._entity_tooltip_active_tag:
            return
        self._cancel_entity_tooltip_hide()
        self._entity_tooltip_hide_after_id = self.after(delay, self._dismiss_entity_tooltip)

    def _schedule_entity_tooltip(self, root_x, root_y, entity_info, tag):
        self._cancel_entity_tooltip_schedule()
        self._entity_tooltip_pending = (root_x, root_y, entity_info, tag)
        self._entity_tooltip_after_id = self.after(
            250,
            lambda: self._show_entity_tooltip_at(root_x, root_y, entity_info, tag)
        )

    def _show_entity_tooltip_at(self, root_x, root_y, entity_info, tag):
        self._entity_tooltip_after_id = None
        self._entity_tooltip_pending = None
        text = self._compose_entity_tooltip_text(entity_info)
        if not text:
            return
        self._hide_entity_tooltip()
        self._entity_tooltip_active_tag = tag
        tw = tk.Toplevel(self.canvas)
        tw.wm_overrideredirect(True)
        try:
            tw.attributes("-topmost", True)
        except Exception:
            pass
        offset_x = int(root_x + 16)
        offset_y = int(root_y + 24)
        tw.wm_geometry(f"+{offset_x}+{offset_y}")
        container = tk.Frame(
            tw,
            background="#ffffe0",
            borderwidth=1,
            relief="solid",
        )
        container.pack()

        portrait_image = self._load_entity_tooltip_portrait(entity_info)
        if portrait_image is not None:
            portrait_label = tk.Label(
                container,
                image=portrait_image,
                background="#ffffe0",
                borderwidth=0,
                highlightthickness=0,
                padx=6,
                pady=0,
            )
            portrait_label.image = portrait_image
            portrait_label.pack(pady=(6, 4))

        text_padding = (4, 6) if portrait_image is not None else (6, 6)
        label = tk.Label(
            container,
            text=text,
            justify="left",
            background="#ffffe0",
            borderwidth=0,
            font=("Segoe UI", 9, "normal"),
            padx=6,
            pady=4,
            wraplength=320,
        )
        label.pack(pady=text_padding)
        self._entity_tooltip_window = tw

    def _on_entity_hover_enter(self, event, entity_info, tag):
        root_x = self.canvas.winfo_rootx() + event.x
        root_y = self.canvas.winfo_rooty() + event.y
        self._entity_tooltip_active_tag = tag
        self._cancel_entity_tooltip_hide()
        self._schedule_entity_tooltip(root_x, root_y, entity_info, tag)

    def _on_entity_hover_leave(self, event=None, tag=None):
        self._schedule_entity_tooltip_hide(tag)

    def _bind_entity_tooltip(self, tag, entity_info):
        if not self.canvas:
            return
        self.canvas.tag_bind(
            tag,
            "<Enter>",
            lambda event, info=entity_info, t=tag: self._on_entity_hover_enter(event, info, t),
            add="+"
        )
        self.canvas.tag_bind(tag, "<Leave>", lambda event, t=tag: self._on_entity_hover_leave(event, t), add="+")
        self.canvas.tag_bind(tag, "<ButtonPress>", lambda event, t=tag: self._on_entity_hover_leave(event, t), add="+")

    def _find_mentions(self, text, candidates):
        if not text or not candidates:
            return []
        lower_text = text.lower()
        matches = []
        for candidate in candidates:
            if not candidate:
                continue
            candidate_text = str(candidate).strip()
            if not candidate_text:
                continue
            if candidate_text.lower() in lower_text:
                matches.append(candidate_text)
        return matches

    def _coerce_scene_links(self, value):
        links = []
        if value is None:
            return links
        if isinstance(value, list):
            for item in value:
                links.extend(self._coerce_scene_links(item))
            return links
        if isinstance(value, dict):
            target = None
            text = None
            for key in ("target", "Target", "to", "To", "scene", "Scene", "next", "Next", "id", "Id", "goto", "GoTo"):
                if key in value:
                    target = value[key]
                    break
            for key in ("text", "Text", "label", "Label", "description", "Description", "summary", "Summary", "choice", "Choice", "result", "Result", "outcome", "Outcome", "condition", "Condition"):
                if key in value:
                    text = value[key]
                    break
            if target is not None or text is not None:
                links.append({"target": target, "text": text})
            else:
                for key, sub in value.items():
                    sub_links = self._coerce_scene_links(sub)
                    if sub_links:
                        for link in sub_links:
                            if not link.get("text") and isinstance(key, str):
                                link["text"] = key
                        links.extend(sub_links)
                    else:
                        links.append({"target": sub, "text": key})
            return links
        if isinstance(value, (int, float)):
            links.append({"target": int(value), "text": ""})
            return links
        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return links
            links.append(
                {
                    "target": text_value,
                    "text": text_value,
                    "text_auto_generated": True,
                }
            )
            return links

    def _normalise_link_text_value(self, value):
        """Convert raw link text payloads into display strings without truncation."""

        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, dict):
            for key in (
                "text",
                "Text",
                "label",
                "Label",
                "description",
                "Description",
                "summary",
                "Summary",
                "value",
                "Value",
            ):
                if key in value:
                    return self._normalise_link_text_value(value.get(key))
            return format_longtext(value, max_length=5000).strip()

        if isinstance(value, (list, tuple, set)):
            parts = [self._normalise_link_text_value(item) for item in value]
            return ", ".join([part for part in parts if part])

        return str(value).strip()

    def _link_text_matches_target(self, text, link_record):
        """Return True when the provided label simply mirrors the link target."""

        if not text or not isinstance(link_record, dict):
            return False

        target_value = (
            link_record.get("target_key")
            if link_record.get("target_key") is not None
            else link_record.get("target")
        )
        if target_value is None:
            return False

        text_str = str(text).strip()
        target_str = str(target_value).strip()
        if not text_str or not target_str:
            return False

        if text_str.lower() == target_str.lower():
            return True

        normalized_text = self._normalize_scene_identifier_key(text_str)
        normalized_target = self._normalize_scene_identifier_key(target_str)
        if normalized_text and normalized_target and normalized_text == normalized_target:
            return True

        slug_text = self._slugify_scene_identifier(text_str)
        slug_target = self._slugify_scene_identifier(target_str)
        if slug_text and slug_target and slug_text == slug_target:
            return True

        digits_text = re.findall(r"\d+", text_str)
        digits_target = re.findall(r"\d+", target_str)
        if digits_text and digits_target and digits_text[0] == digits_target[0]:
            return True

        return False

    def _build_scene_lookup(self, scenes):
        lookup = {}
        index_lookup = {}
        for scene in scenes:
            tag = scene.get("tag")
            raw_index = scene.get("index", 0)
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                index = None
            if tag and index is not None:
                index_lookup.setdefault(index, tag)
                index_lookup.setdefault(index + 1, tag)
            for ident in scene.get("identifiers", []) or []:
                norm = self._normalize_scene_identifier_key(ident)
                if norm and norm not in lookup:
                    lookup[norm] = tag
                slug = self._slugify_scene_identifier(ident)
                if slug and slug not in lookup:
                    lookup[slug] = tag
        return lookup, index_lookup

    def _resolve_scene_reference(self, reference, lookup, index_lookup):
        if reference is None:
            return None
        if isinstance(reference, dict):
            for key in ("target", "Target", "Scene", "scene", "Next", "next", "Id", "id"):
                if key in reference:
                    resolved = self._resolve_scene_reference(reference[key], lookup, index_lookup)
                    if resolved:
                        return resolved
            return None
        if isinstance(reference, list):
            for item in reference:
                resolved = self._resolve_scene_reference(item, lookup, index_lookup)
                if resolved:
                    return resolved
            return None
        if isinstance(reference, (int, float)):
            return index_lookup.get(int(reference))
        if isinstance(reference, str):
            ref = reference.strip()
            if not ref:
                return None
            if ref.isdigit():
                target = index_lookup.get(int(ref))
                if target:
                    return target
            lowered = ref.lower()
            match = re.search(r"(scene|act)\s*(\d+)", lowered)
            if match:
                num = int(match.group(2))
                target = index_lookup.get(num)
                if target:
                    return target
            candidates = [ref, lowered]
            cleaned = re.sub(r"^(scene|act)\s*", "", lowered, flags=re.IGNORECASE).strip()
            if cleaned and cleaned != lowered:
                candidates.append(cleaned)
            if ":" in ref:
                prefix = ref.split(":", 1)[0].strip()
                if prefix:
                    candidates.append(prefix)
            for candidate in candidates:
                norm = self._normalize_scene_identifier_key(candidate)
                if norm and norm in lookup:
                    return lookup[norm]
                slug = self._slugify_scene_identifier(candidate)
                if slug and slug in lookup:
                    return lookup[slug]
        return None

    def _normalize_scene_identifier_key(self, value):
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return str(int(value))
        text = str(value).strip().lower()
        if not text:
            return ""
        text = text.replace("’", "'")
        text = re.sub(r"[\s_/]+", " ", text)
        return text

    def _slugify_scene_identifier(self, value):
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return str(int(value))
        text = str(value).lower().replace("’", "")
        slug = re.sub(r"[^a-z0-9]+", "-", text)
        return slug.strip('-')

    def draw_graph(self):
        self._dismiss_entity_tooltip()
        self.canvas.delete("node")
        self.canvas.delete("link")
        self.node_rectangles.clear()
        self.draw_nodes()
        self.draw_links()
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if bbox:
            padding = 50
            self.canvas.configure(scrollregion=(
                bbox[0] - padding, bbox[1] - padding,
                bbox[2] + padding, bbox[3] + padding
            ))
        # Ensure proper layering
        if getattr(self, "background_id", None) is not None:
            # Use the tag assigned during creation so Tk always receives
            # a valid identifier. Passing a missing/empty identifier leads
            # to a Tcl "wrong # args" error on some platforms when the
            # image was not created successfully.
            self.canvas.tag_lower("background")

        self.canvas.tag_raise("link")  # Put links behind everything
        self.canvas.tag_raise("node")  # Bring nodes to the top

    def _extract_entity_image(self, record, entity_type):
        if not isinstance(record, dict):
            return ""
        priority_keys = ["Portrait", "portrait", "Image", "image", "TokenImage", "tokenImage", "Token", "token"]
        if entity_type == "place":
            priority_keys = ["Image", "image", "Portrait", "portrait", "TokenImage", "tokenImage", "Token", "token"]
        for key in priority_keys:
            value = record.get(key)
            if value:
                return value
        return ""

    def _resolve_scene_entity_portrait(self, entity):
        if not isinstance(entity, dict):
            return ""
        for key in ("portrait", "Portrait", "image", "Image", "tokenImage", "TokenImage", "token", "Token"):
            value = entity.get(key)
            if value:
                return value
        return ""

    def _iter_image_candidates(self, value):
        if value is None:
            return

        if isinstance(value, dict):
            for key in ("path", "Path", "file", "File", "image", "Image", "portrait", "Portrait", "value", "Value", "text", "Text"):
                if key in value:
                    yield from self._iter_image_candidates(value[key])
            return

        if isinstance(value, (list, tuple, set)):
            for item in value:
                yield from self._iter_image_candidates(item)
            return

        text = str(value).strip()
        if not text:
            return

        expanded = os.path.expandvars(os.path.expanduser(text))
        normalized = expanded.replace("\\", os.sep)
        yield normalized

        if not os.path.isabs(normalized):
            campaign_dir = ConfigHelper.get_campaign_dir()
            if campaign_dir:
                yield os.path.join(campaign_dir, normalized)
            if PORTRAIT_FOLDER:
                normalized_lower = normalized.replace("\\", "/").lower()
                if not normalized_lower.startswith("assets/"):
                    yield os.path.join(PORTRAIT_FOLDER, normalized)

    def _resolve_existing_image_path(self, portrait_path):
        seen = set()
        for candidate in self._iter_image_candidates(portrait_path):
            if not candidate:
                continue
            normalized = os.path.normpath(candidate)
            if normalized in seen:
                continue
            seen.add(normalized)
            if os.path.exists(normalized):
                return normalized
        return None

    def load_portrait(self, portrait_path, node_tag):
        resolved_path = self._resolve_existing_image_path(portrait_path)
        if not resolved_path:
            return None, (0, 0)
        try:
            with Image.open(resolved_path) as pil_img:
                img = pil_img.copy()
            resample_method = getattr(Image, "Resampling", Image).LANCZOS
            img.thumbnail(MAX_PORTRAIT_SIZE, resample_method)
            portrait_image = ImageTk.PhotoImage(img, master=self.canvas)
            self.node_images[node_tag] = portrait_image
            return portrait_image, img.size
        except Exception as e:
            print(f"Error loading portrait for {node_tag}: {e}")
            return None, (0, 0)

    def load_portrait_scaled(self, portrait_path, node_tag, scale=1.0):
        resolved_path = self._resolve_existing_image_path(portrait_path)
        if not resolved_path:
            return None, (0, 0)
        try:
            with Image.open(resolved_path) as pil_img:
                img = pil_img.copy()
            size = int(MAX_PORTRAIT_SIZE[0] * scale), int(MAX_PORTRAIT_SIZE[1] * scale)
            resample_method = getattr(Image, "Resampling", Image).LANCZOS
            img.thumbnail(size, resample_method)
            portrait_image = ImageTk.PhotoImage(img, master=self.canvas)
            self.node_images[node_tag] = portrait_image
            return portrait_image, img.size
        except Exception as e:
            print(f"Error loading portrait for {node_tag}: {e}")
            return None, (0, 0)

    def load_thumbnail(self, portrait_path, cache_key, size):
        resolved_path = self._resolve_existing_image_path(portrait_path)
        if not resolved_path:
            return None
        try:
            with Image.open(resolved_path) as pil_img:
                img = pil_img.copy()
            resample_method = getattr(Image, "Resampling", Image).LANCZOS
            img.thumbnail(size, resample_method)
            thumb = ImageTk.PhotoImage(img, master=self.canvas)
            self.node_images[cache_key] = thumb
            return thumb
        except Exception as exc:
            print(f"Error loading portrait thumbnail '{portrait_path}': {exc}")
            return None

    def _entity_placeholder_color(self, entity_type):
        base = (entity_type or "").lower()
        color_map = {
            "npc": "#3f6fb5",
            "creature": "#b85a4a",
            "monster": "#b85a4a",
            "place": "#4f8750",
            "location": "#4f8750",
        }
        return color_map.get(base, "#666666")

    def _load_default_type_icons(self):
        self.type_icons.clear()
        self._scaled_type_icons.clear()
        for icon_type, path in self.type_icon_paths.items():
            icon = self.load_icon(path, 32, 0.6)
            if icon:
                self.type_icons[icon_type] = icon
                self._scaled_type_icons[(icon_type, 32)] = icon

    def _get_scaled_type_icon(self, entity_type, size):
        entity_key = (entity_type or "").lower()
        if not entity_key:
            return None
        try:
            target_size = int(size)
        except (TypeError, ValueError):
            return None
        if target_size <= 0:
            return None
        cache_key = (entity_key, target_size)
        if cache_key in self._scaled_type_icons:
            return self._scaled_type_icons[cache_key]
        path = self.type_icon_paths.get(entity_key)
        if not path:
            return None
        icon = self.load_icon(path, target_size, 0.6)
        if icon:
            self._scaled_type_icons[cache_key] = icon
        return icon

    def draw_nodes(self):

        scale = self.canvas_scale

        GAP = int(5 * scale)
        PAD = int(10 * scale)

        # Prepare node_bboxes
        if not hasattr(self, "node_bboxes"):
            self.node_bboxes = {}
        else:
            self.node_bboxes.clear()

        for node in self.graph["nodes"]:
            node_type = node["type"]
            node_name = node["name"]
            node_tag = self._build_tag(node_type, node_name)
            x, y = node["x"], node["y"]
            data = node.get("data", {}) or {}
            title_text = node_name

            if node_type == "scene":
                self._draw_scene_card(node, scale)
                continue

            entity_entries = []

            if node_type == "scenario":
                summary = data.get("Summary", "")
                secret  = data.get("Secret", "")
                body_text = f"{summary}\nSecrets: {secret}" if secret else summary
            elif node_type == "scene":
                raw_text = data.get("Text") or data.get("text") or ""
                body_text = clean_longtext(raw_text, max_length=1200)
                body_text = body_text.strip()
                if len(body_text) > 700:
                    trimmed = body_text[:700]
                    cut = trimmed.rfind(" ")
                    if cut > 400:
                        trimmed = trimmed[:cut]
                    body_text = trimmed.rstrip() + "..."
                if not body_text:
                    body_text = "No scene notes provided."
                entities_raw = data.get("Entities") or data.get("entities") or []
                if isinstance(entities_raw, list):
                    entity_entries = [ent for ent in entities_raw if isinstance(ent, dict)]
                else:
                    entity_entries = []
            elif node_type == "place":
                desc   = data.get("Description", "")
                secret = data.get("Secret", "")
                body_text = f"{desc}\nSecret: {secret}" if secret else desc
            elif node_type == "creature":
                stats     = data.get("Stats", {})
                stats_text = stats.get("text", "No Stats") if isinstance(stats, dict) else str(stats)
                weakness  = data.get("Weakness", "")
                body_text = f"Stats: {stats_text}\nWeakness: {weakness}" if weakness else f"Stats: {stats_text}"
            else:
                traits = data.get("Traits", "")
                secret = data.get("Secret", "")
                body_text = f"{traits}\nSecret: {secret}" if secret else traits

            if node_type == "scene" and entity_entries:
                max_entities = 8
                if len(entity_entries) > max_entities:
                    entity_entries = entity_entries[:max_entities]
            else:
                entity_entries = entity_entries or []

            # Load portrait if applicable
            portrait = None
            p_w = p_h = 0
            if node_type in ["npc", "creature"]:
                portrait, (p_w, p_h) = self.load_portrait_scaled(
                    primary_portrait(data.get("Portrait", "")),
                    node_tag,
                    scale
                )

            # Compute wrap width
            desired_chars_per_line = 45 if node_type == "scene" else 40
            avg_char_width = 7
            wrap_width = max(90, int(desired_chars_per_line * avg_char_width))
            if portrait and p_w > 0:
                wrap_width = max(wrap_width, 160)

            # Fonts
            title_font = tkFont.Font(family="Arial",
                                    size=max(1, int(10 * scale)),
                                    weight="bold")
            body_font = tkFont.Font(family="Arial",
                                    size=max(1, int(9 * scale)))

            thumb_size = max(48, int(80 * scale))
            thumb_gap = max(4, int(6 * scale))
            icons_height = thumb_size if entity_entries else 0
            icon_row_width = (
                len(entity_entries) * thumb_size
                + (len(entity_entries) - 1) * thumb_gap if entity_entries else 0
            )

            # Measure text heights
            title_h = self._measure_text_height(title_text, title_font, wrap_width)
            body_h  = self._measure_text_height(body_text,  body_font,  wrap_width)
            gap     = int(4 * scale)
            text_h  = title_h + gap + body_h

            # Node content size
            content_width  = max(p_w, wrap_width, icon_row_width)
            content_height = p_h + (GAP if portrait else 0) + text_h
            if entity_entries:
                content_height += GAP + icons_height
            min_w = content_width + 2 * PAD
            min_h = content_height + 2 * PAD

            # === BACKGROUND IMAGE: Post-it ===
            if self.postit_base:
                orig_w, orig_h = self.postit_base.size

                # scale so the post-it is at least as big as our minimum box
                scale_factor = max(min_w / orig_w, min_h / orig_h)
                node_width  = int(orig_w * scale_factor)
                node_height = int(orig_h * scale_factor)

                # resize with preserved aspect ratio
                scaled = self.postit_base.resize(
                    (node_width, node_height),
                    Image.Resampling.LANCZOS
                )

                # create PhotoImage and stash it
                photo = ImageTk.PhotoImage(scaled, master=self.canvas)
                self.node_holder_images[node_tag] = photo

                # draw the background post-it
                self.canvas.create_image(
                    x, y,
                    image=photo,
                    anchor="center",
                    tags=("node", node_tag)
                )

                # ── NEW: draw the semitransparent watermark icon ──
                icon = self.type_icons.get(node_type)
                if icon:
                    # compute top-left corner of the post-it
                    left = x - node_width  / 2
                    top  = y - node_height / 2
                    # margin inside the pad
                    margin = int(8 * scale)
                    icon_x = left + margin + icon.width()//2
                    icon_y = top  + margin + icon.height()//2
                    self.canvas.create_image(
                        icon_x, icon_y,
                        image=icon,
                        anchor="center",
                        tags=("node", node_tag)
                    )

            else:
                # fallback to plain rectangle
                node_width, node_height = min_w, min_h
                rect = self.canvas.create_rectangle(
                    x - node_width/2, y - node_height/2,
                    x + node_width/2, y + node_height/2,
                    fill=node.get("color","white"),
                    outline="black",
                    tags=("node", node_tag)
                )
                self.node_rectangles[node_tag] = rect

            # === PIN (unchanged) ===
            if hasattr(self, "pin_image") and self.pin_image:
                self.canvas.create_image(
                    x,
                    y - node_height // 2 - 10,
                    image=self.pin_image,
                    anchor="n",
                    tags=("node", node_tag)
                )

            # Compute content start coordinates
            left = x - node_width/2
            top  = y - node_height/2

            # 1) Portrait at top center
            if portrait and p_w > 0:
                portrait_x = x
                portrait_y = top + PAD + p_h/2 + 10
                self.canvas.create_image(
                    portrait_x, portrait_y,
                    image=portrait,
                    anchor="center",
                    tags=("node", node_tag)
                )
                text_top = portrait_y + p_h/2 + GAP
            else:
                text_top = top + PAD

            # 2) Title text
            title_id = self.canvas.create_text(
                x,
                text_top + title_h/2 + 10,
                text=title_text,
                font=title_font,
                fill="black",
                width=wrap_width,
                anchor="center",
                tags=("node", node_tag)
            )

            # 3) Body text
            body_id = self.canvas.create_text(
                x,
                text_top + title_h + gap + body_h/2 + 10,
                text=body_text,
                font=body_font,
                fill="black",
                width=wrap_width,
                anchor="center",
                tags=("node", node_tag)
            )

            if entity_entries:
                text_bottom = text_top + title_h + gap + body_h + 10
                row_width = icon_row_width
                row_left = x - row_width / 2
                icons_y = text_bottom + GAP + icons_height / 2
                for idx, entity in enumerate(entity_entries):
                    name = entity.get("name") or entity.get("Name") or ""
                    portrait_path = self._resolve_scene_entity_portrait(entity)
                    resolved_portrait_path = (
                        self._resolve_existing_image_path(portrait_path)
                        if portrait_path
                        else None
                    )
                    thumb_key = f"{node_tag}_thumb_{idx}"
                    icon = None
                    if portrait_path:
                        icon = self.load_thumbnail(portrait_path, thumb_key, (thumb_size, thumb_size))
                    entity_type_value = entity.get("type") or entity.get("Type") or ""
                    entity_type = (entity_type_value or "").lower()
                    if icon is None:
                        icon = self._get_scaled_type_icon(entity_type, thumb_size)
                        if icon is not None:
                            self.node_images[thumb_key] = icon
                    tooltip_synopsis = self._get_entity_synopsis_for_display(entity)
                    tooltip_info = {
                        "name": name,
                        "type": entity_type_value or entity.get("type") or "",
                        "synopsis": tooltip_synopsis,
                    }
                    if portrait_path:
                        tooltip_info["portrait_path"] = (
                            resolved_portrait_path or portrait_path
                        )
                    entity_tag = f"{node_tag}_entity_{idx}"
                    icon_x = row_left + idx * (thumb_size + thumb_gap) + thumb_size / 2
                    if icon is not None:
                        self.canvas.create_image(
                            icon_x,
                            icons_y,
                            image=icon,
                            anchor="center",
                            tags=("node", node_tag, entity_tag)
                        )
                        self._bind_entity_tooltip(entity_tag, tooltip_info)
                    else:
                        color = self._entity_placeholder_color(entity_type_value)
                        radius = thumb_size / 2
                        self.canvas.create_oval(
                            icon_x - radius,
                            icons_y - radius,
                            icon_x + radius,
                            icons_y + radius,
                            fill=color,
                            outline="",
                            tags=("node", node_tag, entity_tag)
                        )
                        initial = (name or "?")[0].upper()
                        marker_font = tkFont.Font(family="Arial", size=max(1, int(10 * scale)), weight="bold")
                        self.canvas.create_text(
                            icon_x,
                            icons_y,
                            text=initial,
                            font=marker_font,
                            fill="white",
                            tags=("node", node_tag, entity_tag)
                        )
                        self._bind_entity_tooltip(entity_tag, tooltip_info)

            # Record bounding box for hit-testing
            self.node_bboxes[node_tag] = (
                x - node_width / 2,
                y - node_height/2,
                x + node_width / 2,
                y + node_height/2
            )

    def draw_links(self):
        self.canvas_link_items = {}
        for link in self.graph["links"]:
            self.draw_one_link(link)
        self.canvas.tag_lower("link_line")
        self.canvas.tag_raise("link_label")

    def _draw_scene_card(self, node, scale):
        node_name = node.get("name", "Scene")
        node_tag = self._build_tag("scene", node_name)
        x, y = node.get("x", 0), node.get("y", 0)
        data = node.get("data", {}) or {}

        lookup_entry = (self.scene_flow_scene_lookup or {}).get(node_tag)
        source_entry = data.get("SourceEntry")
        if lookup_entry and not source_entry:
            source_entry = lookup_entry.get("source_entry")
        explicit_type = (
            data.get("SceneType")
            or data.get("SceneTypeLabel")
            or data.get("Type")
        )

        full_text = ""
        if lookup_entry and lookup_entry.get("text"):
            full_text = lookup_entry.get("text")
        full_text = full_text or data.get("FullText") or data.get("Text") or data.get("text") or ""

        entity_entries = []
        if lookup_entry and isinstance(lookup_entry.get("entities"), list):
            entity_entries = lookup_entry.get("entities")
        elif isinstance(data.get("Entities"), list):
            entity_entries = data.get("Entities")

        card_size_key = (data.get("CardSize") or data.get("Size") or self._determine_scene_card_size(full_text, len(entity_entries)) or "M")
        card_size_key = str(card_size_key).upper()
        card_width = int(SCENE_CARD_WIDTHS.get(card_size_key, SCENE_CARD_WIDTHS["M"]) * scale)

        header_height = max(int(40 * scale), 32)
        padding_x = max(int(16 * scale), 12)
        body_padding_y = max(int(12 * scale), 10)
        body_wrap_width = max(card_width - 2 * padding_x, int(160 * scale))

        bullet_lines, truncated = self._summarize_scene_text(full_text, max_lines=4)
        bullet_lines = [self._truncate_line(line, 96) for line in bullet_lines]
        more_line_needed = truncated
        if more_line_needed and len(bullet_lines) >= 4:
            bullet_lines = bullet_lines[:3]

        if not bullet_lines:
            bullet_lines = ["No scene notes provided."]
            more_line_needed = False

        bullet_text = "\n".join(f"• {line}" for line in bullet_lines)
        body_font = tkFont.Font(family="Arial", size=max(1, int(10 * scale)))
        more_font = tkFont.Font(family="Arial", size=max(1, int(10 * scale)), slant="italic")
        body_text_height = self._measure_text_height(bullet_text, body_font, body_wrap_width)
        more_line_height = self._measure_text_height("• More…", more_font, body_wrap_width) if more_line_needed else 0
        more_line_spacing = int(4 * scale) if more_line_needed else 0
        body_height = body_padding_y * 2 + body_text_height + (more_line_height + more_line_spacing if more_line_needed else 0)

        chip_entities = [
            ent
            for ent in (entity_entries or [])
            if isinstance(ent, dict)
            and (ent.get("type") or "").lower() in {"npc", "creature", "place"}
        ]
        chip_count = min(len(chip_entities), 6)
        chip_size = max(int(32 * scale), 24)
        chip_gap = max(int(8 * scale), 4)
        chip_vertical_padding = max(int(8 * scale), 4)
        chips_height = chip_vertical_padding * 2 + chip_size if chip_count else 0

        badge_font = tkFont.Font(family="Arial", size=max(1, int(9 * scale)), weight="bold")
        badge_height = max(int(24 * scale), 18)
        badge_gap = max(int(6 * scale), 4)
        badge_inner_pad = max(int(8 * scale), 4)
        badges = self._extract_scene_badges(source_entry or data)
        badge_texts = [f"{badge['label']}: {badge['value']}" for badge in badges]
        layout_width = max(card_width - 2 * padding_x, int(160 * scale))
        badge_section_height = 0
        badge_positions = []
        if badge_texts:
            badge_section_height, badge_positions = self._compute_badge_layout(
                badge_texts,
                badge_font,
                layout_width,
                badge_height,
                badge_gap,
                badge_inner_pad,
            )
        footer_padding = max(int(10 * scale), 6)
        footer_height = badge_section_height + 2 * footer_padding if badge_positions else 0

        card_height = header_height + body_height + chips_height + footer_height
        left = x - card_width / 2
        top = y - card_height / 2
        right = x + card_width / 2
        bottom = y + card_height / 2

        self.canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            fill=SCENE_CARD_BG,
            outline=SCENE_CARD_BORDER,
            width=max(1, int(1 * scale)),
            tags=("node", node_tag, "scene_card"),
        )

        type_label, header_color, _ = self._resolve_scene_type_style(source_entry or data, node.get("color"), explicit_type)
        header_rect = self.canvas.create_rectangle(
            left,
            top,
            right,
            top + header_height,
            fill=header_color,
            outline="",
            tags=("node", node_tag, "scene_card_header"),
        )
        self.node_rectangles[node_tag] = header_rect

        header_font = tkFont.Font(family="Arial", size=max(1, int(12 * scale)), weight="bold")
        type_font = tkFont.Font(family="Arial", size=max(1, int(10 * scale)), weight="bold")

        type_text = type_label.upper() if type_label else ""
        type_width = type_font.measure(type_text) if type_text else 0
        available_title_width = card_width - 2 * padding_x - (type_width + (int(12 * scale) if type_text else 0))
        approx_chars = max(int(available_title_width / max(6 * scale, 1)), 12)
        title_display = self._truncate_line(node_name, approx_chars)

        self.canvas.create_text(
            left + padding_x,
            top + header_height / 2,
            text=title_display,
            font=header_font,
            fill="#F8FAFC",
            anchor="w",
            width=available_title_width,
            tags=("node", node_tag),
        )
        if type_text:
            self.canvas.create_text(
                right - padding_x,
                top + header_height / 2,
                text=type_text,
                font=type_font,
                fill="#F8FAFC",
                anchor="e",
                tags=("node", node_tag),
            )

        self.canvas.create_line(
            left,
            top + header_height,
            right,
            top + header_height,
            fill=SCENE_CARD_BORDER,
            width=max(1, int(1 * scale)),
            tags=("node", node_tag),
        )

        body_top = top + header_height
        body_text_top = body_top + body_padding_y
        self.canvas.create_text(
            left + padding_x,
            body_text_top,
            text=bullet_text,
            font=body_font,
            fill="#E2E8F0",
            width=body_wrap_width,
            anchor="nw",
            tags=("node", node_tag),
        )
        text_drawn_height = self._measure_text_height(bullet_text, body_font, body_wrap_width)
        current_y = body_text_top + text_drawn_height
        if more_line_needed:
            current_y += more_line_spacing
            self.canvas.create_text(
                left + padding_x,
                current_y,
                text="• More…",
                font=more_font,
                fill="#C7D2FE",
                anchor="nw",
                tags=("node", node_tag, f"{node_tag}_more"),
            )
            current_y += more_line_height
        current_y = body_top + body_height

        if chip_count:
            chips_top = body_top + body_height
            chip_center_y = chips_top + chip_vertical_padding + chip_size / 2
            row_width = chip_count * chip_size + (chip_count - 1) * chip_gap
            chip_left = x - row_width / 2
            for idx, entity in enumerate(chip_entities[:chip_count]):
                chip_x = chip_left + idx * (chip_size + chip_gap) + chip_size / 2
                entity_tag = f"{node_tag}_entity_{idx}"
                portrait_path = entity.get("portrait") or self._resolve_scene_entity_portrait(entity)
                thumb_key = f"{node_tag}_chip_{idx}"
                bg_left = chip_x - chip_size / 2
                bg_top = chip_center_y - chip_size / 2
                bg_right = chip_x + chip_size / 2
                bg_bottom = chip_center_y + chip_size / 2
                self.canvas.create_rectangle(
                    bg_left,
                    bg_top,
                    bg_right,
                    bg_bottom,
                    fill="#1F2933",
                    outline="#475569",
                    width=max(1, int(1 * scale)),
                    tags=("node", node_tag, entity_tag),
                )
                icon = None
                if portrait_path:
                    icon = self.load_thumbnail(portrait_path, thumb_key, (chip_size, chip_size))
                if icon:
                    self.node_images[thumb_key] = icon
                    self.canvas.create_image(
                        chip_x,
                        chip_center_y,
                        image=icon,
                        anchor="center",
                        tags=("node", node_tag, entity_tag),
                    )
                else:
                    color = self._entity_placeholder_color(entity.get("type"))
                    self.canvas.create_oval(
                        bg_left,
                        bg_top,
                        bg_right,
                        bg_bottom,
                        fill=color,
                        outline="",
                        tags=("node", node_tag, entity_tag),
                    )
                    marker_font = tkFont.Font(family="Arial", size=max(1, int(10 * scale)), weight="bold")
                    initial = (entity.get("name") or "?")[0].upper()
                    self.canvas.create_text(
                        chip_x,
                        chip_center_y,
                        text=initial,
                        font=marker_font,
                        fill="#FFFFFF",
                        tags=("node", node_tag, entity_tag),
                    )
                tooltip_info = {
                    "name": entity.get("name") or "",
                    "type": entity.get("type") or "",
                    "synopsis": entity.get("synopsis") or "",
                }
                resolved_portrait_path = None
                if portrait_path:
                    resolved_portrait_path = self._resolve_existing_image_path(portrait_path)
                if portrait_path:
                    tooltip_info["portrait_path"] = (
                        resolved_portrait_path or portrait_path
                    )
                self._bind_entity_tooltip(entity_tag, tooltip_info)

        if badge_positions:
            badge_area_left = left + padding_x
            badge_area_top = bottom - footer_height + footer_padding
            for (offset_x, offset_y, badge_width), badge_text in zip(badge_positions, badge_texts):
                rect_left = badge_area_left + offset_x
                rect_top = badge_area_top + offset_y
                rect_right = rect_left + badge_width
                rect_bottom = rect_top + badge_height
                self.canvas.create_rectangle(
                    rect_left,
                    rect_top,
                    rect_right,
                    rect_bottom,
                    fill="#2F3545",
                    outline="#4A5161",
                    width=max(1, int(1 * scale)),
                    tags=("node", node_tag),
                )
                self.canvas.create_text(
                    rect_left + badge_width / 2,
                    rect_top + badge_height / 2,
                    text=badge_text,
                    font=badge_font,
                    fill="#E2E8F0",
                    anchor="c",
                    tags=("node", node_tag),
                )

        self.node_bboxes[node_tag] = (left, top, right, bottom)

    def draw_one_link(self, link):
        tag_from = link["from"]
        tag_to = link["to"]
        x1, y1 = self.node_positions.get(tag_from, (0, 0))
        x2, y2 = self.node_positions.get(tag_to, (0, 0))
        default_line_color = "#5BB8FF"
        line_color = (
            link.get("line_color")
            or link.get("color")
            or default_line_color
        )
        try:
            line_width = float(link.get("line_width") or link.get("width") or 2)
        except (TypeError, ValueError):
            line_width = 2

        line_id = self.canvas.create_line(
            x1, y1, x2, y2,
            fill=line_color,
            width=line_width,
            tags=("link", "link_line")
        )
        self.canvas.tag_lower(line_id)
        self.canvas_link_items[line_id] = link

        text = (link.get("text") or "").strip()
        if text:
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy) or 1
            offset = 18
            offset_x = -dy / length * offset
            offset_y = dx / length * offset
            label_x = mid_x + offset_x
            label_y = mid_y + offset_y
            default_font_size = max(8, int(10 * self.canvas_scale))

            font_spec = link.get("label_font") or link.get("font")
            if isinstance(font_spec, (tuple, list)) and font_spec:
                family = font_spec[0]
                size = None
                weight = None
                if len(font_spec) > 1:
                    try:
                        size = int(font_spec[1])
                    except (TypeError, ValueError):
                        size = None
                if len(font_spec) > 2:
                    weight = font_spec[2]
            else:
                family = link.get("label_font_family") or link.get("font_family") or "Arial"
                try:
                    size = int(link.get("label_font_size") or link.get("font_size") or default_font_size)
                except (TypeError, ValueError):
                    size = default_font_size
                weight = link.get("label_font_weight") or link.get("font_weight") or "bold"

            if size is None:
                size = default_font_size
            if not family:
                family = "Arial"
            if not weight:
                weight = "bold"

            label_font = tkFont.Font(family=family, size=size, weight=weight)
            label_color = link.get("label_color") or link.get("text_color") or "#FFFFFF"
            label_id = self.canvas.create_text(
                label_x,
                label_y,
                text=text,
                font=label_font,
                fill=label_color,
                width=180,
                justify="center",
                tags=("link", "link_label")
            )
            self.canvas_link_items[label_id] = link

    def start_drag(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        items = self.canvas.find_closest(x, y)
        if not items:
            return
        item_id = items[0]
        tags = self.canvas.gettags(item_id)
        if "link" in tags:
            self.selected_node = None
            self.drag_start = None
            return
        node_tag = next((t for t in tags if t.startswith("scenario_")
                        or t.startswith("npc_")
                        or t.startswith("creature_")
                        or t.startswith("place_")
                        or t.startswith("faction_")
                        or t.startswith("scene_")), None)
        # Ignore background and any non-node items that share a "scene_" prefix
        if node_tag in ("background", "scene_flow_bg"):
            node_tag = None
        # Only allow dragging for nodes we actively track positions for
        if node_tag and node_tag not in self.node_positions:
            node_tag = None
        if node_tag:
            self.selected_node = node_tag
            self.selected_items = self.canvas.find_withtag(node_tag)
            self.drag_start = (x, y)
            self._show_node_detail(node_tag)
        else:
            self.selected_node = None
            self.drag_start = None

    def on_drag(self, event):
        if not self.selected_node or not self.drag_start:
            return
        # Ensure the selected node is a tracked node
        if self.selected_node not in self.node_positions:
            self.selected_node = None
            self.drag_start = None
            return

        # 1) canvas coords & delta
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        dx = x - self.drag_start[0]
        dy = y - self.drag_start[1]
        if dx == 0 and dy == 0:
            return

        # 2) move only the selected items
        for item_id in self.selected_items:
            self.canvas.move(item_id, dx, dy)

        # 3) update position in memory
        # Guard against race conditions where a tag was removed
        pos = self.node_positions.get(self.selected_node)
        if not pos:
            self.selected_node = None
            self.drag_start = None
            return
        old_x, old_y = pos
        new_pos = (old_x + dx, old_y + dy)
        self.node_positions[self.selected_node] = new_pos
        for node in self.graph["nodes"]:
            tag = self._build_tag(node.get('type', ''), node.get('name', ''))
            if tag == self.selected_node:
                node["x"], node["y"] = new_pos
                break

        # 4) redraw just the links
        self.canvas.delete("link")
        self.draw_links()                   # draws + tag_lower("link") :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}

        # 5) **re-stack** them above the background
        self.canvas.tag_lower("background")
        self.canvas.tag_raise("link", "background")
        # (optional) self.canvas.tag_raise("node")

        # 6) reset drag origin
        self.drag_start = (x, y)

    def on_double_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        items = self.canvas.find_closest(x, y)
        if not items:
            return
        item_id = items[0]
        tags = self.canvas.gettags(item_id)
        if "link" in tags:
            self.edit_link_text(item_id)
            return
        node_tag = None
        for t in tags:
            if t.startswith("scenario_") or t.startswith("npc_") or t.startswith("creature_") or t.startswith("place_") or t.startswith("faction_"):
                node_tag = t
                break
        if not node_tag:
            return
        if node_tag.startswith("scenario_"):
            entity_type = "scenarios"
            entity_name = node_tag.replace("scenario_", "").replace("_", " ")
            entity = self.scenario
            wrapper=self.scenario_wrapper
        elif node_tag.startswith("npc_"):
            entity_type = "NPCs"
            entity_name = node_tag.replace("npc_", "").replace("_", " ")
            entity = self.npcs.get(entity_name)
            wrapper=self.npc_wrapper
        elif node_tag.startswith("creature_"):
            entity_type = "Creatures"
            entity_name = node_tag.replace("creature_", "").replace("_", " ")
            entity = self.creatures.get(entity_name)
            wrapper=self.creature_wrapper
            
        elif node_tag.startswith("place_"):
            entity_type = "Places"
            entity_name = node_tag.replace("place_", "").replace("_", " ")
            entity = self.places.get(entity_name)
            wrapper=self.place_wrapper
        elif node_tag.startswith("faction_"):
            entity_type = "Factions"
            entity_name = node_tag.replace("faction_", "").replace("_", " ")
            entity = self.factions.get(entity_name)
            wrapper=self.faction_wrapper
        else:
            return

        if not entity:
            messagebox.showerror("Error", f"{entity_type[:-1]} '{entity_name}' not found.")
            return

        template = load_template(entity_type.lower())
        GenericEditorWindow(None, entity, template,wrapper)

    def on_right_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        items = self.canvas.find_closest(x, y)
        if not items:
            return
        item_id = items[0]
        tags = self.canvas.gettags(item_id)
        if "link" in tags:
            return
        node_tag = next((t for t in tags if t.startswith("scenario_")
                        or t.startswith("npc_")
                        or t.startswith("creature_")
                        or t.startswith("place_")
                        or t.startswith("faction_")), None)
        if node_tag:
            self.selected_node = node_tag
            self.show_node_menu(x, y)

    def _on_mousewheel_y(self, event):
        if self.canvas.yview() == (0.0, 1.0):  # No scrolling available
            return
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def _on_mousewheel_x(self, event):
        if self.canvas.xview() == (0.0, 1.0):  # No scrolling available
            return
        if event.num == 4 or event.delta > 0:
            self.canvas.xview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.xview_scroll(1, "units")

    def _start_canvas_pan(self, event):
        self._is_panning = True
        self.canvas.scan_mark(event.x, event.y)

    def _do_canvas_pan(self, event):
        if not self._is_panning:
            return
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _end_canvas_pan(self, _event):
        self._is_panning = False

    def _load_portrait_menu_image(self, path: str) -> ImageTk.PhotoImage | None:
        resolved = resolve_portrait_candidate(path, ConfigHelper.get_campaign_dir())
        if not resolved:
            return None
        try:
            img = Image.open(resolved)
            img.thumbnail(PORTRAIT_MENU_THUMB_SIZE, RESAMPLE_MODE)
            photo = ImageTk.PhotoImage(img)
            self._portrait_menu_images.append(photo)
            return photo
        except Exception as exc:
            log_warning(
                f"Failed to load portrait menu thumbnail for '{path}': {exc}",
                func_name="ScenarioGraphEditor._load_portrait_menu_image",
            )
            return None

    def show_node_menu(self, x, y):
        node_menu = Menu(self.canvas, tearoff=0)
        self._portrait_menu_images = []
        node_menu.add_command(label="Delete Node", command=self.delete_node)
        node_menu.add_separator()
        node_menu.add_command(label="Change Color", command=lambda: self.show_color_menu(x, y))
        record = None
        entity_name = None
        if self.selected_node:
            if self.selected_node.startswith("npc_"):
                entity_name = self.selected_node.replace("npc_", "").replace("_", " ")
                record = self.npcs.get(entity_name, {})
            elif self.selected_node.startswith("creature_"):
                entity_name = self.selected_node.replace("creature_", "").replace("_", " ")
                record = self.creatures.get(entity_name, {})
            elif self.selected_node.startswith("place_"):
                entity_name = self.selected_node.replace("place_", "").replace("_", " ")
                record = self.places.get(entity_name, {})
        if record and entity_name and (
            self.selected_node.startswith("npc_") or self.selected_node.startswith("creature_")
        ):
            portrait_paths = [
                path
                for path in parse_portrait_value(record.get("Portrait", ""))
                if resolve_portrait_candidate(path, ConfigHelper.get_campaign_dir())
            ]
            if portrait_paths:
                if len(portrait_paths) == 1:
                    node_menu.add_command(
                        label="Display Portrait",
                        command=lambda p=portrait_paths[0], n=entity_name: show_portrait(p, n),
                    )
                else:
                    portrait_menu = Menu(node_menu, tearoff=0)
                    for index, path in enumerate(portrait_paths, start=1):
                        portrait_image = self._load_portrait_menu_image(path)
                        if portrait_image:
                            portrait_menu.add_command(
                                label=portrait_menu_label(path, index),
                                image=portrait_image,
                                compound="left",
                                command=lambda p=path, n=entity_name: show_portrait(p, n),
                            )
                        else:
                            portrait_menu.add_command(
                                label=portrait_menu_label(path, index),
                                command=lambda p=path, n=entity_name: show_portrait(p, n),
                            )
                    node_menu.add_cascade(label="Display Portraits", menu=portrait_menu)
        audio_value = self._get_entity_audio(record)
        if audio_value:
            node_menu.add_separator()
            node_menu.add_command(
                label="Play Audio",
                command=lambda n=entity_name, r=record: self._play_entity_audio(r, n),
            )
            node_menu.add_command(label="Stop Audio", command=stop_entity_audio)
        node_menu.post(int(x), int(y))

    def _get_entity_audio(self, record):
        return get_entity_audio_value(record)

    def _play_entity_audio(self, record, name):
        audio_value = self._get_entity_audio(record)
        if not audio_value:
            messagebox.showinfo("Audio", "No audio file configured for this entity.")
            return
        label = name or "Entity"
        if not play_entity_audio(audio_value, entity_label=str(label)):
            messagebox.showwarning("Audio", f"Unable to play audio for {label}.")

    def show_color_menu(self, x, y):
        COLORS = [
            "red", "green", "blue", "yellow", "purple",
            "orange", "pink", "cyan", "magenta", "lightgray"
        ]
        color_menu = Menu(self.canvas, tearoff=0)
        for color in COLORS:
            color_menu.add_command(label=color, command=lambda c=color: self.change_node_color(c))
        color_menu.post(int(x), int(y))

    def change_node_color(self, color):
        if not self.selected_node:
            return
        rect_id = self.node_rectangles.get(self.selected_node)
        if rect_id:
            self.canvas.itemconfig(rect_id, fill=color)
        for node in self.graph["nodes"]:
            tag = self._build_tag(node.get('type', ''), node.get('name', ''))
            if tag == self.selected_node:
                node["color"] = color
                break
        self.draw_graph()

    def delete_node(self):
        if not self.selected_node:
            return
        node_name = self.selected_node.split("_", 1)[-1].replace("_", " ")
        self.graph["nodes"] = [n for n in self.graph["nodes"] if n["name"] != node_name]
        self.graph["links"] = [l for l in self.graph["links"]
                            if l["from"] != self.selected_node and l["to"] != self.selected_node]
        if self.selected_node in self.node_positions:
            del self.node_positions[self.selected_node]
        self.draw_graph()

    def edit_link_text(self, item_id):
        link_record = self.canvas_link_items.get(item_id)
        if not link_record:
            return

        dialog = LinkEditDialog(self, link_record, self.scene_flow_scene_lookup)
        self.wait_window(dialog)
        if not dialog.result:
            return

        new_text = dialog.result.get("text", "").strip()
        target_tag = dialog.result.get("target_tag")
        metadata_payload = dialog.result.get("metadata")

        link_record["text"] = new_text
        link_record.pop("text_auto_generated", None)
        if target_tag:
            link_record["to"] = target_tag
            link_record["target_tag"] = target_tag

        link_data = link_record.get("link_data")
        if not isinstance(link_data, dict):
            link_data = {}
            link_record["link_data"] = link_data

        link_data["text"] = new_text
        link_data.pop("text_auto_generated", None)
        if target_tag:
            link_data["target_tag"] = target_tag
            link_data["target"] = target_tag

        target_scene = None
        if target_tag:
            target_scene = (self.scene_flow_scene_lookup or {}).get(target_tag)

        if target_scene:
            target_index = target_scene.get("index")
            link_record["target_scene_index"] = target_index
            link_data["target_scene_index"] = target_index
            link_data["target_index"] = target_index
        else:
            link_record.pop("target_scene_index", None)
            link_data.pop("target_scene_index", None)
            link_data.pop("target_index", None)

        if metadata_payload is not None:
            link_data["conditions"] = metadata_payload
        else:
            link_data.pop("conditions", None)

        self.canvas.delete("link")
        self.draw_links()
        try:
            self._persist_scene_links()
            self._save_scenario_changes()
        except Exception as exc:
            messagebox.showerror("Save Error", f"Failed to update link text: {exc}")

    def _get_scenario_scenes_list(self):
        scenes_raw = self.scenario.get("Scenes") if self.scenario else None
        if isinstance(scenes_raw, dict):
            if isinstance(scenes_raw.get("Scenes"), list):
                return scenes_raw["Scenes"]
            scenes_raw["Scenes"] = []
            return scenes_raw["Scenes"]
        if isinstance(scenes_raw, list):
            return scenes_raw
        if scenes_raw is None:
            self.scenario["Scenes"] = []
            return self.scenario["Scenes"]
        if isinstance(scenes_raw, str):
            self.scenario["Scenes"] = [scenes_raw]
        else:
            self.scenario["Scenes"] = [scenes_raw]
        return self.scenario["Scenes"]

    def _ensure_scene_entry(self, index):
        scenes_list = self._get_scenario_scenes_list()
        while len(scenes_list) <= index:
            scenes_list.append({})
        entry = scenes_list[index]
        if not isinstance(entry, dict):
            entry = {"Text": entry if isinstance(entry, str) else str(entry)}
            scenes_list[index] = entry
        return entry

    def _persist_scene_links(self):
        if not isinstance(self.scene_flow_scenes, list):
            return
        tag_lookup = self.scene_flow_scene_lookup or {}
        for scene in self.scene_flow_scenes:
            idx = scene.get("index")
            if idx is None:
                continue
            entry = self._ensure_scene_entry(idx)
            links_payload = []
            for link in scene.get("links", []):
                text_val = (link.get("text") or "").strip()
                link_record = {}
                target_scene = None
                target_tag = link.get("target_tag")
                if target_tag:
                    target_scene = tag_lookup.get(target_tag)
                target_idx = link.get("target_scene_index")
                if target_scene is None and isinstance(target_idx, int):
                    target_scene = next(
                        (sc for sc in self.scene_flow_scenes if sc.get("index") == target_idx),
                        None,
                    )
                if target_scene:
                    target_title = target_scene.get("title") or target_scene.get("display_name")
                    if target_title:
                        link_record["Target"] = target_title
                    else:
                        link_record["Target"] = target_scene.get("index", 0) + 1
                    link_record["TargetIndex"] = target_scene.get("index")
                else:
                    raw_target = link.get("target") or link.get("target_key") or link.get("target_index")
                    if isinstance(raw_target, (int, float)):
                        link_record["Target"] = int(raw_target)
                    elif raw_target:
                        link_record["Target"] = raw_target
                if text_val:
                    link_record["Text"] = text_val
                links_payload.append(link_record)
            entry["Links"] = links_payload

    def _save_scenario_changes(self):
        if not self.scenario_wrapper or not self.scenario:
            return
        try:
            items = self.scenario_wrapper.load_items()
            title = self.scenario.get("Title")
            saved = False
            for idx, item in enumerate(items):
                if item.get("Title") == title:
                    items[idx] = self.scenario
                    saved = True
                    break
            if not saved:
                items.append(self.scenario)
            self.scenario_wrapper.save_items(items)
        except Exception as exc:
            raise RuntimeError(exc)

    def save_graph(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json")
        if file_path:
            for node in self.graph["nodes"]:
                node_tag = self._build_tag(node.get('type', ''), node.get('name', ''))
                x, y = self.node_positions.get(node_tag, (node["x"], node["y"]))
                node["x"], node["y"] = x, y
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.graph, f, indent=2)

    def load_graph(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                self.graph = json.load(f)
            self.node_positions.clear()
            contains_scene_nodes = any(
                (node.get("type") or "").lower() == "scene"
                for node in self.graph.get("nodes", [])
            )
            if contains_scene_nodes:
                self._show_detail_panel()
            else:
                self._hide_detail_panel()
            self._clear_detail_panel()
            self.scene_flow_scenes = []
            self.scene_flow_scene_lookup = {}
            for node in self.graph["nodes"]:
                node_tag = self._build_tag(node.get('type', ''), node.get('name', ''))
                self.node_positions[node_tag] = (node["x"], node["y"])
            self.draw_graph()
        # Try to find the scenario node and set self.scenario
        scenario_node = next((n for n in self.graph["nodes"] if n["type"] == "scenario"), None)
        if scenario_node:
            title = scenario_node["name"]
            all_scenarios = self.scenario_wrapper.load_items()
            matched = next((s for s in all_scenarios if s.get("Title") == title), None)
            if matched:
                self.scenario = matched
            else:
                print(f"[WARNING] Scenario titled '{title}' not found in data.")
        for node in self.graph["nodes"]:
            tag = self._build_tag(node.get('type', ''), node.get('name', ''))
            self.original_positions[tag] = (node["x"], node["y"])
        
        # --- Scroll to center on the scenario node ---
        self.canvas.update_idletasks()
        scenario_node = next((n for n in self.graph["nodes"] if n["type"] == "scenario"), None)
        if scenario_node:
            tag = self._build_tag("scenario", scenario_node.get('name', ''))
            if tag in self.node_positions:
                x, y = self.node_positions[tag]

                # Get canvas scroll region and view dimensions
                scroll_x0, scroll_y0, scroll_x1, scroll_y1 = self.canvas.bbox("all")
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()

                # Compute scroll fractions
                scroll_x_frac = max(0.0, min(1.0, (x - canvas_width / 2 - scroll_x0) / (scroll_x1 - scroll_x0)))
                scroll_y_frac = max(0.0, min(1.0, (y - canvas_height / 2 - scroll_y0) / (scroll_y1 - scroll_y0)))

                self.canvas.xview_moveto(scroll_x_frac)
                self.canvas.yview_moveto(scroll_y_frac)
        
        
    def get_state(self):
        return {
            "graph": self.graph,
            "node_positions": self.node_positions,
        }

    def set_state(self, state):
        self.graph = state.get("graph", {})
        self.node_positions = state.get("node_positions", {})
        self.draw_graph()
    def load_icon(self, path, size, opacity):
        if not path or not os.path.exists(path):
            return None
        img = Image.open(path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        alpha = img.split()[3].point(lambda p: int(p * opacity))
        img.putalpha(alpha)
        return ImageTk.PhotoImage(img, master=self.canvas)
        
def make_watermarked_postit(base_path, icon_path, size=(200,200), icon_size=32, margin=8, opacity=80):
        # 1) load base
        base = Image.open(base_path).convert("RGBA")
        base = base.resize(size, Image.ANTIALIAS)

        # 2) load & prep icon
        icon = Image.open(icon_path).convert("RGBA")
        icon = icon.resize((icon_size, icon_size), Image.ANTIALIAS)
        # tint down alpha
        alpha = icon.split()[3].point(lambda p: p * (opacity/100))
        icon.putalpha(alpha)

        # 3) compute paste coords (bottom-right corner)
        bx, by = base.size
        ix, iy = icon.size
        pos = (bx - ix - margin, by - iy - margin)

        # 4) composite and convert to PhotoImage
        base.paste(icon, pos, icon)
        return ImageTk.PhotoImage(base)

    
