"""World Map exploration window with nested map navigation and entity synthesis."""
import os
import json
import textwrap
import tkinter as tk
from tkinter import messagebox, simpledialog
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw

from db.db import get_connection, ensure_entity_schema

from modules.generic.entity_detail_factory import open_entity_window
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.template_loader import load_template
from modules.helpers.text_helpers import format_longtext
from modules.helpers.logging_helper import (
    log_debug,
    log_error,
    log_info,
    log_warning,
    log_module_import,
)

log_module_import(__name__)

WORLD_TOKENS_KEY = "WorldTokens"

_TOKEN_COLORS = {
    "NPC": "#FFB347",
    "PC": "#6ECFF6",
    "Creature": "#FF6F91",
    "Place": "#B5E48C",
    "Map": "#F9C74F",
}

class WorldMapWindow(ctk.CTkToplevel):
    """Interactive world map viewer with nested map support."""

    CANVAS_BG = "#05070D"
    PORTRAIT_SIZE = (320, 240)
    ZOOM_MIN = 0.25
    ZOOM_MAX = 6.0
    ZOOM_FACTOR = 1.1

    def __init__(self, master=None):
        super().__init__(master)
        self.title("World Map")
        self.geometry("1400x900")
        self.minsize(1200, 720)
        self.configure(fg_color="#0C0F1A")

        self.maps_wrapper = GenericModelWrapper("maps")
        self.npc_wrapper = GenericModelWrapper("npcs")
        self.pc_wrapper = GenericModelWrapper("pcs")
        self.creature_wrapper = GenericModelWrapper("creatures")
        self.place_wrapper = GenericModelWrapper("places")

        self.maps_wrapper_data = {item.get("Name", ""): item for item in self.maps_wrapper.load_items() if item.get("Name")}

        self.world_map_dir = os.path.join(ConfigHelper.get_campaign_dir(), "world_maps")
        os.makedirs(self.world_map_dir, exist_ok=True)
        self.world_map_file = os.path.join(self.world_map_dir, "world_map_data.json")
        self.world_maps = self._load_world_map_store()
        self._seed_world_maps()
        self.map_names = sorted(self.world_maps.keys())

        self.current_map_name: str | None = None
        self.current_world_map: dict | None = None
        self.map_stack: list[str] = []

        self.tokens: list[dict] = []
        self.selected_token: dict | None = None
        self.base_image = None
        self.base_photo = None
        self.render_params = None
        self.image_cache: dict[str, Image.Image] = {}
        self._portrait_photo: ImageTk.PhotoImage | None = None
        self._portrait_placeholder: Image.Image | None = None
        self._inspector_token: dict | None = None
        self._entity_tab_images: list[ImageTk.PhotoImage] = []
        self._notes_textbox: ctk.CTkTextbox | None = None
        self._notes_status_label: ctk.CTkLabel | None = None

        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._pan_anchor: tuple[float, float, float, float] | None = None
        self._pending_view_state: dict | None = None

        self._suppress_map_change = False

        self._build_layout()

        if self.map_names:
            self.map_selector.configure(values=self.map_names)
            self.map_selector.set(self.map_names[0])
            self.load_map(self.map_names[0], push_history=False)
        else:
            self._show_empty_state()

        self._update_map_tool_button_state()

        self.bind("<Destroy>", self._on_destroy, add="+")

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        toolbar = ctk.CTkFrame(self, fg_color="#101429")
        toolbar.pack(side="top", fill="x", padx=12, pady=(12, 0))

        left_group = ctk.CTkFrame(toolbar, fg_color="transparent")
        left_group.pack(side="left", padx=8, pady=8)

        ctk.CTkLabel(left_group, text="Map:", font=("Segoe UI", 14, "bold")).pack(side="left", padx=(4, 6))
        self.map_selector = ctk.CTkOptionMenu(
            left_group,
            values=self.map_names,
            command=self._on_map_selected,
            width=240,
        )
        self.map_selector.pack(side="left", padx=(0, 12))

        self.back_button = ctk.CTkButton(
            left_group,
            text="Back",
            width=120,
            command=self.navigate_back,
            state=ctk.DISABLED,
        )
        self.back_button.pack(side="left", padx=(0, 12))

        entity_group = ctk.CTkFrame(toolbar, fg_color="transparent")
        entity_group.pack(side="left", padx=8, pady=8)

        ctk.CTkButton(entity_group, text="Add NPC", command=lambda: self._open_picker("NPC")).pack(side="left", padx=4)
        ctk.CTkButton(entity_group, text="Add PC", command=lambda: self._open_picker("PC")).pack(side="left", padx=4)
        ctk.CTkButton(entity_group, text="Add Creature", command=lambda: self._open_picker("Creature")).pack(side="left", padx=4)
        ctk.CTkButton(entity_group, text="Add Place", command=lambda: self._open_picker("Place")).pack(side="left", padx=4)
        ctk.CTkButton(entity_group, text="Add Map", command=lambda: self._open_picker("Map")).pack(side="left", padx=4)

        self.save_button = ctk.CTkButton(toolbar, text="Save", width=120, command=self._persist_tokens)
        self.save_button.pack(side="right", padx=12)

        self.map_tool_button = ctk.CTkButton(
            toolbar,
            text="Open in Map Tool",
            width=160,
            command=self._open_in_map_tool,
            state=ctk.DISABLED,
        )
        self.map_tool_button.pack(side="right", padx=(0, 12))

        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.pack(fill="both", expand=True, padx=12, pady=12)
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_columnconfigure(1, weight=0, minsize=380)

        self.canvas_container = ctk.CTkFrame(workspace, fg_color=self.CANVAS_BG, corner_radius=18)
        self.canvas_container.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.canvas = tk.Canvas(
            self.canvas_container,
            bg=self.CANVAS_BG,
            highlightthickness=0,
            relief="flat",
        )
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)
        self.canvas.bind("<Configure>", lambda e: self._draw_scene())
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._on_mouse_wheel(e, direction=1))
        self.canvas.bind("<Button-5>", lambda e: self._on_mouse_wheel(e, direction=-1))
        self.canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_move)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_end)

        self.inspector_container = ctk.CTkFrame(workspace, fg_color="#11182A", corner_radius=18, width=380)
        self.inspector_container.grid(row=0, column=1, sticky="nsew")
        self.inspector_container.grid_propagate(False)
        self.inspector_container.grid_rowconfigure(2, weight=1)

        self.inspector_header = ctk.CTkFrame(self.inspector_container, fg_color="#1B233A", corner_radius=18)
        self.inspector_header.pack(fill="x", padx=12, pady=(12, 8))

        self.title_label = ctk.CTkLabel(self.inspector_header, text="World Map", font=("Segoe UI", 20, "bold"))
        self.title_label.pack(anchor="w", padx=16, pady=(12, 4))

        self.subtitle_label = ctk.CTkLabel(self.inspector_header, text="Select an entity to view its synthesis.", font=("Segoe UI", 14))
        self.subtitle_label.pack(anchor="w", padx=16, pady=(0, 12))

        self.inspector_actions = ctk.CTkFrame(self.inspector_header, fg_color="transparent")
        self.inspector_actions.pack(fill="x", padx=12, pady=(0, 12))

        self.focus_map_button = ctk.CTkButton(
            self.inspector_actions,
            text="Focus on Map",
            width=130,
            command=self._focus_on_selected_token,
            state=ctk.DISABLED,
        )
        self.focus_map_button.pack(side="left", padx=(4, 6))

        self.open_record_button = ctk.CTkButton(
            self.inspector_actions,
            text="Open Record",
            width=130,
            command=self._open_selected_record,
            state=ctk.DISABLED,
        )
        self.open_record_button.pack(side="left", padx=6)

        self.open_map_tool_button = ctk.CTkButton(
            self.inspector_actions,
            text="Open in Map Tool",
            width=150,
            command=self._open_selected_in_map_tool,
            state=ctk.DISABLED,
        )
        self.open_map_tool_button.pack(side="left", padx=6)

        self.portrait_frame = ctk.CTkFrame(self.inspector_container, fg_color="#141C30", corner_radius=18)
        self.portrait_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.portrait_label = ctk.CTkLabel(
            self.portrait_frame,
            text="",
            width=self.PORTRAIT_SIZE[0],
            height=self.PORTRAIT_SIZE[1],
            anchor="center",
        )
        self.portrait_label.pack(fill="both", expand=True, padx=16, pady=16)

        self._portrait_placeholder = self._create_portrait_placeholder()
        self._set_portrait_image(None)

        self.badge_frame = ctk.CTkFrame(self.inspector_container, fg_color="transparent")
        self.badge_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.quick_actions_frame = ctk.CTkFrame(self.inspector_container, fg_color="transparent")
        self.quick_actions_frame.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            self.quick_actions_frame,
            text="Quick Actions",
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")

        self.highlight_button = ctk.CTkButton(
            self.quick_actions_frame,
            text="Highlight",
            width=120,
            command=self._on_highlight_token,
            state=ctk.DISABLED,
        )
        self.highlight_button.pack(side="right")

        tabs_wrapper = ctk.CTkFrame(self.inspector_container, fg_color="transparent")
        tabs_wrapper.pack(fill="x", padx=16, pady=(0, 12))

        self.tab_selector = ctk.CTkSegmentedButton(
            tabs_wrapper,
            values=["Summary", "Notes", "Characters"],
            command=self._on_inspector_tab_selected,
        )
        self.tab_selector.pack(fill="x")
        self.tab_selector.set("Summary")

        self.tab_content_container = ctk.CTkFrame(self.inspector_container, fg_color="transparent")
        self.tab_content_container.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._tab_frames: dict[str, ctk.CTkFrame] = {}
        for name in ("Summary", "Notes", "Characters"):
            frame = ctk.CTkFrame(self.tab_content_container, fg_color="transparent")
            self._tab_frames[name] = frame

        self.summary_container = self._tab_frames["Summary"]
        self.notes_container = self._tab_frames["Notes"]
        self.characters_container = self._tab_frames["Characters"]
        self._active_tab: str | None = None
        self._select_inspector_tab("Summary")

        self.bind("<Delete>", self._delete_selected_token)
        self.bind("<Control-s>", self._on_save_shortcut)

        self._clear_inspector()

    def _on_inspector_tab_selected(self, tab_name: str) -> None:
        if not tab_name:
            return
        self._select_inspector_tab(tab_name)

    def _select_inspector_tab(self, tab_name: str) -> None:
        if tab_name not in getattr(self, "_tab_frames", {}):
            return
        if self._active_tab == tab_name:
            frame = self._tab_frames[tab_name]
            if not frame.winfo_ismapped():
                frame.pack(fill="both", expand=True)
            return
        for frame in self._tab_frames.values():
            frame.pack_forget()
        target = self._tab_frames[tab_name]
        target.pack(fill="both", expand=True)
        self._active_tab = tab_name

    def _clear_tab_contents(self, tab_name: str) -> None:
        frame = getattr(self, "_tab_frames", {}).get(tab_name)
        if not frame:
            return
        for child in frame.winfo_children():
            child.destroy()

    def _render_tab_message(self, tab_name: str, message: str) -> None:
        frame = getattr(self, "_tab_frames", {}).get(tab_name)
        if not frame:
            return
        self._clear_tab_contents(tab_name)
        ctk.CTkLabel(
            frame,
            text=message,
            font=("Segoe UI", 13),
            wraplength=360,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 12), anchor="w")

    def _load_world_map_store(self) -> dict:
        if not os.path.exists(self.world_map_file):
            return {}
        try:
            with open(self.world_map_file, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception as exc:
            log_warning(f"Failed to load world map store: {exc}", func_name="WorldMapWindow._load_world_map_store")
            return {}
        maps = data.get('maps') if isinstance(data, dict) else None
        return maps if isinstance(maps, dict) else {}

    def _save_world_map_store(self) -> None:
        payload = {'maps': self.world_maps}
        try:
            with open(self.world_map_file, 'w', encoding='utf-8') as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            log_error(f"Failed to save world map store: {exc}", func_name="WorldMapWindow._save_world_map_store")

    def _seed_world_maps(self) -> None:
        changed = False
        for name, record in self.maps_wrapper_data.items():
            if not name:
                continue
            if name not in self.world_maps:
                image = record.get('Image', '') if isinstance(record, dict) else ''
                self.world_maps[name] = {'image': image, 'tokens': []}
                changed = True
            else:
                entry = self.world_maps[name]
                if isinstance(record, dict) and not entry.get('image'):
                    entry['image'] = record.get('Image', '')
                    changed = True
                if 'tokens' not in entry or not isinstance(entry['tokens'], list):
                    entry['tokens'] = []
                    changed = True
        if changed:
            self._save_world_map_store()

    def _ensure_world_map_entry(self, map_name: str) -> dict | None:
        if not map_name:
            return None
        entry = self.world_maps.get(map_name)
        if not entry:
            record = self.maps_wrapper_data.get(map_name, {})
            image = record.get('Image', '') if isinstance(record, dict) else ''
            entry = {'image': image, 'tokens': []}
            self.world_maps[map_name] = entry
            self._save_world_map_store()
            self.map_names = sorted(self.world_maps.keys())
            if hasattr(self, 'map_selector'):
                self.map_selector.configure(values=self.map_names)
        return entry

    def _show_empty_state(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(
            self.canvas.winfo_width() // 2,
            self.canvas.winfo_height() // 2,
            text="No maps available. Create a map to begin.",
            fill="#FFFFFF",
            font=("Segoe UI", 18, "bold"),
        )
        self.current_map_name = None
        self.current_world_map = None
        self._update_map_tool_button_state()

    # ------------------------------------------------------------------
    # Map navigation
    # ------------------------------------------------------------------
    def _on_map_selected(self, selected: str) -> None:
        if self._suppress_map_change:
            return
        if selected and selected != self.current_map_name:
            self.load_map(selected)

    def load_map(self, map_name: str, *, push_history: bool = True) -> None:
        log_info(f"Loading world map '{map_name}'", func_name="WorldMapWindow.load_map")
        entry = self._ensure_world_map_entry(map_name)
        if entry is None:
            log_warning(f"World map entry '{map_name}' could not be created", func_name="WorldMapWindow.load_map")
            self.current_map_name = None
            self.current_world_map = None
            self._update_map_tool_button_state()
            return

        if push_history and self.current_map_name:
            self.map_stack.append(self.current_map_name)
        elif not push_history:
            self.map_stack.clear()
        self._update_back_button_state()

        self.current_map_name = map_name
        self.current_world_map = entry
        self._update_map_tool_button_state()

        view_state = entry.get("view_state") if isinstance(entry, dict) else None
        if isinstance(view_state, dict):
            zoom_value = view_state.get("zoom")
            if isinstance(zoom_value, (int, float)):
                self.zoom = self._clamp_zoom(float(zoom_value))
            else:
                self.zoom = 1.0
            self.pan_x = 0.0
            self.pan_y = 0.0
            self._pending_view_state = view_state
        else:
            self.zoom = 1.0
            self.pan_x = 0.0
            self.pan_y = 0.0
            self._pending_view_state = None

        if self.map_selector.get() != map_name:
            self._suppress_map_change = True
            self.map_selector.set(map_name)
            self._suppress_map_change = False

        self._load_base_image()
        self.tokens = self._deserialize_tokens(entry)
        self._draw_scene()
        self._clear_inspector()

    def navigate_back(self) -> None:
        if not self.map_stack:
            return
        parent = self.map_stack.pop()
        self._update_back_button_state()
        self.load_map(parent, push_history=False)

    def navigate_to_map(self, child_map: str | None) -> None:
        if not child_map:
            return
        if child_map not in self.world_maps and child_map not in self.maps_wrapper_data:
            messagebox.showwarning("Missing Map", f"Map '{child_map}' is not available.")
            return
        self.load_map(child_map)

    def _update_back_button_state(self) -> None:
        if self.map_stack:
            self.back_button.configure(state=ctk.NORMAL, text=f"Back to {self.map_stack[-1]}")
        else:
            self.back_button.configure(state=ctk.DISABLED, text="Back")

    def _update_map_tool_button_state(self) -> None:
        if not hasattr(self, "map_tool_button"):
            return
        state = ctk.NORMAL if self.current_map_name else ctk.DISABLED
        self.map_tool_button.configure(state=state)

    def _open_in_map_tool(self) -> None:
        target_map = None
        if self.selected_token and self.selected_token.get("type") == "map":
            target_map = self.selected_token.get("linked_map") or self.selected_token.get("entity_id")
        if not target_map:
            target_map = self.current_map_name
        if not target_map:
            messagebox.showinfo("No Map Available", "Select a map to open in Map Tool.")
            return

        master = getattr(self, "master", None)
        if not master or not hasattr(master, "map_tool"):
            messagebox.showwarning("Map Tool Unavailable", "The Map Tool is not available from this window.")
            return

        try:
            master.map_tool(map_name=target_map)
        except TypeError:
            master.map_tool(target_map)
        except Exception as exc:
            log_error(
                f"Failed to open Map Tool for '{target_map}': {exc}",
                func_name="WorldMapWindow._open_in_map_tool",
            )
            messagebox.showerror("Error", f"Could not open '{target_map}' in Map Tool.\n{exc}")
            return

        log_info(
            f"Opened map '{target_map}' in Map Tool",
            func_name="WorldMapWindow._open_in_map_tool",
        )

    def _focus_on_selected_token(self) -> None:
        token = self._inspector_token or self.selected_token
        if not token:
            return
        self._focus_on_token(token)

    def _focus_on_token(self, token: dict) -> None:
        if not self.render_params or not self.base_image:
            return
        canvas = getattr(self, "canvas", None)
        if not canvas or not canvas.winfo_exists():
            return

        scale, offset_x, offset_y, base_w, base_h = self.render_params
        canvas_w = canvas.winfo_width()
        canvas_h = canvas.winfo_height()
        if canvas_w <= 0 or canvas_h <= 0:
            return

        base_offset_x = offset_x - self.pan_x
        base_offset_y = offset_y - self.pan_y

        x_norm = token.get("x_norm")
        y_norm = token.get("y_norm")
        if x_norm is None or y_norm is None:
            return

        token_x = base_offset_x + float(x_norm) * base_w * scale
        token_y = base_offset_y + float(y_norm) * base_h * scale

        center_x = canvas_w / 2
        center_y = canvas_h / 2

        self.pan_x += center_x - token_x
        self.pan_y += center_y - token_y
        self._draw_scene()
        self._pulse_token(token)

    def _open_selected_record(self) -> None:
        token = self._inspector_token or self.selected_token
        if not token or token.get("type") == "map":
            return

        entity_type = token.get("entity_type")
        entity_id = token.get("entity_id")
        if not entity_type or not entity_id:
            return

        type_map = {
            "NPC": "NPCs",
            "PC": "PCs",
            "Creature": "Creatures",
            "Place": "Places",
        }
        target_type = type_map.get(entity_type)
        if not target_type:
            return

        try:
            open_entity_window(target_type, entity_id)
        except Exception as exc:
            log_error(
                f"Failed to open record '{entity_id}' ({entity_type}): {exc}",
                func_name="WorldMapWindow._open_selected_record",
            )
            messagebox.showerror("Error", f"Unable to open {entity_type} '{entity_id}'.\n{exc}")

    def _open_selected_in_map_tool(self) -> None:
        token = self._inspector_token or self.selected_token
        if token and token is not self.selected_token:
            self.selected_token = token
        self._open_in_map_tool()

    # ------------------------------------------------------------------
    # Token creation & persistence
    # ------------------------------------------------------------------
    def _open_picker(self, entity_type: str) -> None:
        wrappers = {
            "NPC": self.npc_wrapper,
            "PC": self.pc_wrapper,
            "Creature": self.creature_wrapper,
            "Place": self.place_wrapper,
            "Map": self.maps_wrapper,
        }
        templates = {
            "NPC": load_template("npcs"),
            "PC": load_template("pcs"),
            "Creature": load_template("creatures"),
            "Place": load_template("places"),
            "Map": load_template("maps"),
        }
        wrapper = wrappers.get(entity_type)
        template = templates.get(entity_type)
        if not wrapper or not template:
            return

        picker = ctk.CTkToplevel(self)
        picker.title(f"Select {entity_type}")
        picker.geometry("960x640")
        picker.minsize(720, 520)
        picker.transient(self)
        picker.lift()
        picker.after(10, picker.lift)
        picker.grab_set()
        picker.focus_set()

        def on_select(_, name):
            picker.destroy()
            record = next(
                (item for item in wrapper.load_items() if item.get("Name") == name or item.get("Title") == name),
                None,
            )
            if record is None:
                log_warning(f"Selected {entity_type} '{name}' not found", func_name="WorldMapWindow._open_picker")
                return
            self._add_token(entity_type, record)

        GenericListSelectionView(
            picker,
            entity_type.lower() if entity_type != "Map" else "maps",
            wrapper,
            template,
            on_select_callback=on_select,
        ).pack(fill="both", expand=True)

    def _add_token(self, entity_type: str, record: dict) -> None:
        if not self.base_image:
            return
        token = self._build_token(entity_type, record)
        self.tokens.append(token)
        self._draw_scene()
        self._persist_tokens()
        if entity_type == "Map":
            self._show_map_hint(token)
        else:
            self._show_entity_synthesis(token)

    def _build_token(self, entity_type: str, record: dict) -> dict:
        return {
            "entity_type": entity_type,
            "entity_id": record.get("Name") or record.get("Title") or "Unnamed",
            "record": record,
            "type": "map" if entity_type == "Map" else "entity",
            "x_norm": 0.5,
            "y_norm": 0.5,
            "size": 120,
            "portrait_path": self._resolve_portrait_path(record) if entity_type != "Map" else None,
            "image_path": self._resolve_map_image(record) if entity_type == "Map" else None,
            "linked_map": record.get("Name") if entity_type == "Map" else None,
            "color": _TOKEN_COLORS.get(entity_type, "#FFFFFF"),
        }

    def _deserialize_tokens(self, entry: dict) -> list[dict]:
        raw = entry.get('tokens')
        legacy_source = False
        if raw is None:
            raw = entry.get(WORLD_TOKENS_KEY) or entry.get('Tokens') or []
            legacy_source = True
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, json.JSONDecodeError):
                log_warning("Failed to parse stored tokens; starting fresh", func_name="WorldMapWindow._deserialize_tokens")
                raw = []
        if not isinstance(raw, list):
            raw = []

        tokens: list[dict] = []
        for value in raw:
            if not isinstance(value, dict):
                continue
            entity_type = value.get('entity_type') or value.get('type') or 'Entity'
            token_type = value.get('type')
            if token_type not in {'map', 'entity', 'world'}:
                continue
            if str(entity_type).lower() in {'rectangle', 'oval', 'circle', 'shape', 'line', 'polygon'}:
                continue
            record_ref = self._fetch_record(entity_type, value.get('entity_id'))
            tokens.append(
                {
                    'entity_type': entity_type,
                    'entity_id': value.get('entity_id', 'Unnamed'),
                    'record': record_ref or {},
                    'type': 'map' if token_type == 'map' or entity_type == 'Map' else 'entity',
                    'x_norm': value.get('x_norm', 0.5),
                    'y_norm': value.get('y_norm', 0.5),
                    'size': value.get('size', 120),
                    'portrait_path': value.get('portrait_path'),
                    'image_path': value.get('image_path'),
                    'linked_map': value.get('linked_map'),
                    'color': value.get('color', _TOKEN_COLORS.get(entity_type, '#FFFFFF')),
                }
            )
        if legacy_source and raw and entry.get('tokens') is None:
            entry['tokens'] = raw
            entry.pop(WORLD_TOKENS_KEY, None)
            self.world_maps[self.current_map_name] = entry
            self._save_world_map_store()
        return tokens

    def _persist_tokens(self) -> None:
        if not self.current_world_map or not self.current_map_name:
            return
        serialized: list[dict] = []
        for token in self.tokens:
            if str(token.get("entity_type", "")).lower() in {"rectangle", "oval", "circle", "shape", "line", "polygon"}:
                continue
            serialized.append(
                {
                    "entity_type": token.get("entity_type"),
                    "entity_id": token.get("entity_id"),
                    "type": token.get("type"),
                    "x_norm": token.get("x_norm", 0.5),
                    "y_norm": token.get("y_norm", 0.5),
                    "size": token.get("size", 120),
                    "portrait_path": token.get("portrait_path"),
                    "image_path": token.get("image_path"),
                    "linked_map": token.get("linked_map"),
                    "color": token.get("color"),
                }
            )
        self.current_world_map["tokens"] = serialized
        view_state = self._capture_view_state()
        if view_state is not None:
            self.current_world_map["view_state"] = view_state
        else:
            self.current_world_map.pop("view_state", None)
        self.world_maps[self.current_map_name] = self.current_world_map
        self._save_world_map_store()
        log_debug("World map tokens saved", func_name="WorldMapWindow._persist_tokens")

    def _load_base_image(self) -> None:
        if not self.current_world_map:
            self.base_image = None
            return
        image_path = self.current_world_map.get("image", "")
        if not image_path and self.current_map_name in self.maps_wrapper_data:
            record = self.maps_wrapper_data[self.current_map_name]
            if isinstance(record, dict):
                image_path = record.get("Image", "")
                if image_path:
                    self.current_world_map["image"] = image_path
                    self.world_maps[self.current_map_name] = self.current_world_map
                    self._save_world_map_store()
        if not image_path:
            self.base_image = Image.new("RGBA", (1280, 720), "#1E1E1E")
            return
        full = image_path if os.path.isabs(image_path) else os.path.join(ConfigHelper.get_campaign_dir(), image_path)
        if not os.path.exists(full):
            self.base_image = Image.new("RGBA", (1280, 720), "#1E1E1E")
            log_warning(f"Map image '{full}' not found", func_name="WorldMapWindow._load_base_image")
            return
        self.base_image = Image.open(full).convert("RGBA")

    def _draw_scene(self) -> None:
        if not self.base_image:
            return
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            return

        self.canvas.delete("all")
        base_w, base_h = self.base_image.size
        if base_w <= 0 or base_h <= 0:
            return

        base_scale = min(canvas_w / base_w, canvas_h / base_h)
        if base_scale <= 0:
            return

        self.zoom = self._clamp_zoom(self.zoom)
        if self._pending_view_state:
            self._apply_pending_view_state(base_scale, base_w, base_h)

        scale = base_scale * self.zoom
        scaled_w = base_w * scale
        scaled_h = base_h * scale
        offset_x = (canvas_w - scaled_w) / 2 + self.pan_x
        offset_y = (canvas_h - scaled_h) / 2 + self.pan_y
        self.render_params = (scale, offset_x, offset_y, base_w, base_h)

        resized = self.base_image.resize(
            (max(1, int(round(scaled_w))), max(1, int(round(scaled_h)))),
            Image.LANCZOS,
        )
        self.base_photo = ImageTk.PhotoImage(resized)
        self.canvas.create_image(offset_x, offset_y, anchor="nw", image=self.base_photo)

        for token in self.tokens:
            self._draw_token(token)

    def _apply_pending_view_state(self, base_scale: float, base_w: int, base_h: int) -> None:
        view_state = self._pending_view_state
        if not isinstance(view_state, dict):
            return
        pan_norm = view_state.get("pan_norm")
        if isinstance(pan_norm, (list, tuple)) and len(pan_norm) >= 2:
            try:
                self.pan_x = float(pan_norm[0]) * base_w * base_scale
                self.pan_y = float(pan_norm[1]) * base_h * base_scale
            except (TypeError, ValueError):
                self.pan_x = 0.0
                self.pan_y = 0.0
        else:
            pan_dict = view_state.get("pan") if isinstance(view_state.get("pan"), dict) else None
            if pan_dict:
                pan_x_val = pan_dict.get("x") if pan_dict.get("x") is not None else pan_dict.get("pan_x")
                pan_y_val = pan_dict.get("y") if pan_dict.get("y") is not None else pan_dict.get("pan_y")
            else:
                pan_x_val = view_state.get("pan_x")
                pan_y_val = view_state.get("pan_y")
            self.pan_x = self._safe_float(pan_x_val)
            self.pan_y = self._safe_float(pan_y_val)
        self._pending_view_state = None

    def _capture_view_state(self) -> dict | None:
        if not self.render_params:
            return None
        scale, _, _, base_w, base_h = self.render_params
        if base_w <= 0 or base_h <= 0:
            return None
        if self.zoom <= 0:
            return None
        base_scale = scale / self.zoom
        if base_scale <= 0:
            return None
        pan_norm_x = self.pan_x / (base_w * base_scale)
        pan_norm_y = self.pan_y / (base_h * base_scale)
        return {
            "zoom": round(self.zoom, 4),
            "pan_norm": [round(pan_norm_x, 4), round(pan_norm_y, 4)],
        }

    def _clamp_zoom(self, zoom: float) -> float:
        if zoom <= 0:
            return self.ZOOM_MIN
        return max(self.ZOOM_MIN, min(self.ZOOM_MAX, zoom))

    def _on_mouse_wheel(self, event, direction: int | None = None):
        if direction is None:
            delta = getattr(event, "delta", 0)
            if delta == 0:
                return
            direction = 1 if delta > 0 else -1
        if direction == 0:
            return
        factor = self.ZOOM_FACTOR if direction > 0 else 1 / self.ZOOM_FACTOR
        self._adjust_zoom(factor, focus=(event.x, event.y))
        return "break"

    def _adjust_zoom(self, factor: float, focus: tuple[float, float] | None = None) -> None:
        if not self.base_image or not self.render_params:
            return
        if factor <= 0:
            return
        focus_x: float
        focus_y: float
        if focus is None:
            focus_x = self.canvas.winfo_width() / 2
            focus_y = self.canvas.winfo_height() / 2
        else:
            focus_x, focus_y = focus

        old_zoom = self.zoom
        new_zoom = self._clamp_zoom(old_zoom * factor)
        if abs(new_zoom - old_zoom) < 1e-4:
            return

        scale, offset_x, offset_y, base_w, base_h = self.render_params
        if base_w <= 0 or base_h <= 0 or scale <= 0 or old_zoom <= 0:
            return

        base_scale = scale / old_zoom
        image_x = (focus_x - offset_x) / scale
        image_y = (focus_y - offset_y) / scale

        self.zoom = new_zoom
        new_scale = base_scale * new_zoom
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        new_base_offset_x = (canvas_w - base_w * new_scale) / 2
        new_base_offset_y = (canvas_h - base_h * new_scale) / 2

        self.pan_x = focus_x - new_base_offset_x - image_x * new_scale
        self.pan_y = focus_y - new_base_offset_y - image_y * new_scale

        self._draw_scene()

    def _on_pan_start(self, event):
        if not self.base_image:
            return
        self._pan_anchor = (event.x, event.y, self.pan_x, self.pan_y)
        self.canvas.configure(cursor="fleur")
        return "break"

    def _on_pan_move(self, event):
        if not self._pan_anchor:
            return
        start_x, start_y, origin_x, origin_y = self._pan_anchor
        self.pan_x = origin_x + (event.x - start_x)
        self.pan_y = origin_y + (event.y - start_y)
        self._draw_scene()
        return "break"

    def _on_pan_end(self, _event):
        if not self._pan_anchor:
            return
        self._pan_anchor = None
        self.canvas.configure(cursor="")
        return "break"

    def _on_save_shortcut(self, _event=None):
        self._persist_tokens()
        return "break"

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    def _draw_token(self, token: dict) -> None:
        if not self.render_params:
            return
        scale, offset_x, offset_y, base_w, base_h = self.render_params
        x = offset_x + token.get("x_norm", 0.5) * base_w * scale
        y = offset_y + token.get("y_norm", 0.5) * base_h * scale
        size = max(48, int(token.get("size", 120) * scale))

        image = self._resolve_token_image(token, size)
        radius = size // 2

        canvas_ids: list[int] = []
        image_id = self.canvas.create_image(x, y, image=image, anchor="center")
        label_id = self.canvas.create_text(
            x,
            y + radius + 18,
            text=token.get("entity_id", ""),
            fill="#F3F5FF",
            font=("Segoe UI", 12, "bold"),
        )

        canvas_ids.extend([image_id, label_id])
        token["canvas_ids"] = canvas_ids
        token["tk_image"] = image

        for cid in canvas_ids:
            self.canvas.tag_bind(cid, "<ButtonPress-1>", lambda e, t=token: self._on_token_press(e, t))
            self.canvas.tag_bind(cid, "<B1-Motion>", lambda e, t=token: self._on_token_drag(e, t))
            self.canvas.tag_bind(cid, "<ButtonRelease-1>", lambda e, t=token: self._on_token_release(e, t))
            self.canvas.tag_bind(cid, "<Double-Button-1>", lambda e, t=token: self._on_token_double_click(e, t))
            self.canvas.tag_bind(cid, "<Button-3>", lambda e, t=token: self._show_token_menu(e, t))
    def _resolve_token_image(self, token: dict, size: int) -> ImageTk.PhotoImage:
        portrait = token.get("portrait_path") or token.get("image_path")
        if portrait:
            pil = self._load_image(portrait)
            if pil is not None:
                return ImageTk.PhotoImage(pil.resize((size, size), Image.LANCZOS))
        placeholder = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(placeholder)
        draw.ellipse((0, 0, size, size), fill=(token.get("color") or "#FFFFFF"))
        label = (token.get("entity_id") or "?")[:2].upper()
        draw.text((size / 2, size / 2), label, fill="#0B0B0B", anchor="mm", align="center")
        return ImageTk.PhotoImage(placeholder)

    def _load_image(self, path: str) -> Image.Image | None:
        if path in self.image_cache:
            return self.image_cache[path]
        candidate = path
        if not os.path.isabs(candidate):
            candidate = os.path.join(ConfigHelper.get_campaign_dir(), candidate)
        if not os.path.exists(candidate):
            return None
        try:
            image = Image.open(candidate).convert("RGBA")
            self.image_cache[path] = image
            return image
        except Exception as exc:
            log_warning(f"Failed to load image '{candidate}': {exc}", func_name="WorldMapWindow._load_image")
            return None

    def _create_portrait_placeholder(self) -> Image.Image:
        width, height = self.PORTRAIT_SIZE
        placeholder = Image.new("RGBA", (width, height), (20, 27, 48, 255))
        draw = ImageDraw.Draw(placeholder)
        margin = 6
        draw.rounded_rectangle(
            (margin, margin, width - margin, height - margin),
            radius=18,
            outline=(58, 72, 108, 255),
            width=2,
        )
        draw.text(
            (width / 2, height / 2),
            "No\nPortrait",
            fill=(132, 146, 184, 255),
            anchor="mm",
            align="center",
        )
        return placeholder

    def _set_portrait_image(self, pil_image: Image.Image | None) -> None:
        base_image = self._portrait_placeholder if pil_image is None else pil_image
        if base_image is None:
            return
        width, height = self.PORTRAIT_SIZE
        image = base_image.convert("RGBA") if base_image.mode != "RGBA" else base_image.copy()
        image.thumbnail(self.PORTRAIT_SIZE, Image.LANCZOS)
        canvas = Image.new("RGBA", self.PORTRAIT_SIZE, (20, 27, 48, 255))
        offset = ((width - image.width) // 2, (height - image.height) // 2)
        canvas.paste(image, offset, image)
        photo = ImageTk.PhotoImage(canvas)
        self.portrait_label.configure(image=photo)
        self.portrait_label.image = photo
        self._portrait_photo = photo

    # ------------------------------------------------------------------
    # Token interactions
    # ------------------------------------------------------------------
    def _on_token_press(self, event, token: dict) -> None:
        self.selected_token = token
        token["drag_anchor"] = (event.x, event.y)
        if token.get("type") == "map":
            self._show_map_hint(token)
        else:
            self._show_entity_synthesis(token)

    def _on_token_drag(self, event, token: dict) -> None:
        if "drag_anchor" not in token or not self.render_params:
            return
        scale, offset_x, offset_y, base_w, base_h = self.render_params
        radius = token.get("size", 120) * scale / 2
        x = max(offset_x + radius, min(offset_x + base_w * scale - radius, event.x))
        y = max(offset_y + radius, min(offset_y + base_h * scale - radius, event.y))
        dx = x - token["drag_anchor"][0]
        dy = y - token["drag_anchor"][1]
        if abs(dx) < 1 and abs(dy) < 1:
            return
        token["drag_anchor"] = (x, y)
        for cid in token.get("canvas_ids", []):
            self.canvas.move(cid, dx, dy)
        token["x_norm"] = (x - offset_x) / (base_w * scale)
        token["y_norm"] = (y - offset_y) / (base_h * scale)
    def _on_token_release(self, _event, token: dict) -> None:
        token.pop("drag_anchor", None)
        self._persist_tokens()

    def _on_token_double_click(self, _event, token: dict) -> None:
        if token.get("type") == "map":
            self.navigate_to_map(token.get("linked_map"))

    def _delete_selected_token(self, _event=None) -> None:
        token = self.selected_token
        if not token:
            return
        if token not in self.tokens:
            self.selected_token = None
            return
        self.tokens = [t for t in self.tokens if t is not token]
        self.selected_token = None
        self._draw_scene()
        self._persist_tokens()
        self._clear_inspector()

    def _show_token_menu(self, event, token: dict) -> None:
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="Resize?", command=lambda: self._prompt_resize(token))
        menu.add_separator()
        menu.add_command(label="Delete", command=lambda: self._delete_token(token))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _prompt_resize(self, token: dict) -> None:
        initial = int(token.get('size', 120))
        new_size = simpledialog.askinteger(
            "Resize Token",
            "Enter token size (pixels):",
            parent=self,
            initialvalue=initial,
            minvalue=40,
            maxvalue=800,
        )
        if new_size is None:
            return
        token['size'] = new_size
        self._draw_scene()
        self._persist_tokens()

    def _delete_token(self, token: dict) -> None:
        if token not in self.tokens:
            return
        self.tokens = [t for t in self.tokens if t is not token]
        if self.selected_token is token:
            self.selected_token = None
        self._draw_scene()
        self._persist_tokens()
        self._clear_inspector()

    def _configure_inspector_actions(self, token: dict | None) -> None:
        focus_state = ctk.NORMAL if token else ctk.DISABLED
        record_state = ctk.NORMAL if token and token.get("type") != "map" else ctk.DISABLED
        map_state = ctk.DISABLED
        if token and token.get("type") == "map":
            target = token.get("linked_map") or token.get("entity_id")
            map_state = ctk.NORMAL if target else ctk.DISABLED

        if hasattr(self, "focus_map_button"):
            self.focus_map_button.configure(state=focus_state)
        if hasattr(self, "open_record_button"):
            self.open_record_button.configure(state=record_state)
        if hasattr(self, "open_map_tool_button"):
            self.open_map_tool_button.configure(state=map_state)

    def _clear_inspector(self) -> None:
        self.title_label.configure(text="World Map")
        self.subtitle_label.configure(text="Select an entity to view its synthesis.")
        self._set_portrait_image(None)
        for child in self.badge_frame.winfo_children():
            child.destroy()
        if hasattr(self, "tab_selector"):
            self.tab_selector.set("Summary")
        self._select_inspector_tab("Summary")
        self._render_summary_message(
            "Use the controls above to place NPCs, PCs, creatures, places, and nested maps. "
            "Double-click a map token to dive deeper, and drag entities to reposition them."
        )
        self._notes_textbox = None
        self._notes_status_label = None
        self._entity_tab_images = []
        self._render_tab_message("Notes", "Select an entity to capture your campaign notes.")
        self._render_tab_message(
            "Characters",
            "Add NPCs or creatures to this map to review their stats here.",
        )
        self._inspector_token = None
        self._set_quick_actions_state(False)
        self._configure_inspector_actions(None)

    def _show_entity_synthesis(self, token: dict) -> None:
        record = token.get("record") or {}
        entity_type = token.get("entity_type", "Entity")
        name = token.get("entity_id", "Unnamed")
        sections = self._compose_summary(entity_type, record)
        badges = self._collect_badges(entity_type, record)

        self._inspector_token = token
        self._set_quick_actions_state(True)
        self._configure_inspector_actions(token)

        portrait_path = token.get("portrait_path") or token.get("image_path")
        portrait_image = self._load_image(portrait_path) if portrait_path else None
        self._set_portrait_image(portrait_image)

        self.title_label.configure(text=name)
        self.subtitle_label.configure(text=entity_type)
        self._render_badges(badges)
        self._populate_summary_tab(sections)
        self._populate_notes_tab(record)
        self._populate_characters_tab(record)

    def _show_map_hint(self, token: dict) -> None:
        map_name = token.get("linked_map") or token.get("entity_id") or "Nested Map"
        entry = self.world_maps.get(map_name, {})
        wrapper_record = self.maps_wrapper_data.get(map_name, {})
        summary_text = entry.get('summary') or self._normalize_text(wrapper_record.get("Summary")) or self._normalize_text(wrapper_record.get("Description"))
        badges = self._summarize_map_contents(entry)

        self._inspector_token = token
        self._set_quick_actions_state(True)
        self._configure_inspector_actions(token)

        portrait_path = token.get("portrait_path") or token.get("image_path")
        portrait_image = self._load_image(portrait_path) if portrait_path else None
        self._set_portrait_image(portrait_image)

        self.title_label.configure(text=map_name)
        self.subtitle_label.configure(text="Nested Map")
        self._render_badges(badges or ["Double-click to enter"])

        hint = summary_text or "Double-click this map token to open its layer and keep building your world."
        self._render_summary_message(hint)
        self._populate_notes_tab(None)
        self._populate_characters_tab(None)

    def _set_quick_actions_state(self, enabled: bool) -> None:
        if hasattr(self, "highlight_button"):
            state = ctk.NORMAL if enabled else ctk.DISABLED
            self.highlight_button.configure(state=state)

    def _on_highlight_token(self) -> None:
        token = self._inspector_token or self.selected_token
        if not token:
            return
        self._pulse_token(token)

    def _pulse_token(self, token: dict) -> None:
        canvas = getattr(self, "canvas", None)
        if not canvas or not canvas.winfo_exists():
            return
        if not token:
            return

        animation = token.pop("_pulse_animation", None)
        if animation:
            for after_id in animation.get("after_ids", []):
                try:
                    canvas.after_cancel(after_id)
                except tk.TclError:
                    pass
            outline_id = animation.get("outline_id")
            if outline_id:
                try:
                    canvas.delete(outline_id)
                except tk.TclError:
                    pass

        canvas_ids = token.get("canvas_ids") or []
        if not canvas_ids:
            return

        image_id = canvas_ids[0]
        try:
            coords = canvas.coords(image_id)
        except tk.TclError:
            return
        if not coords:
            return
        x, y = coords[0], coords[1]

        try:
            bbox = canvas.bbox(image_id)
        except tk.TclError:
            bbox = None

        if bbox:
            radius = max((bbox[2] - bbox[0]) / 2, (bbox[3] - bbox[1]) / 2)
        else:
            logical_size = token.get("size", 120)
            scale = self.render_params[0] if self.render_params else 1.0
            radius = (logical_size * scale) / 2
        radius = max(radius, 24)

        outline_id = canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline="#F1FA8C",
            width=3,
        )
        canvas.tag_raise(outline_id)

        animation_info = {"outline_id": outline_id, "after_ids": []}
        token["_pulse_animation"] = animation_info

        scales = [1.0, 1.08, 1.18, 1.08, 1.0]
        step_delay = 60

        def animate(index: int) -> None:
            if token.get("_pulse_animation") is not animation_info:
                return
            if index >= len(scales):
                try:
                    canvas.delete(outline_id)
                except tk.TclError:
                    pass
                token.pop("_pulse_animation", None)
                return
            scale_factor = scales[index]
            canvas.coords(
                outline_id,
                x - radius * scale_factor,
                y - radius * scale_factor,
                x + radius * scale_factor,
                y + radius * scale_factor,
            )
            after_id = canvas.after(step_delay, lambda: animate(index + 1))
            animation_info["after_ids"].append(after_id)

        animate(0)

    def _render_badges(self, labels: list[str]) -> None:
        for child in self.badge_frame.winfo_children():
            child.destroy()
        for label in labels[:6]:
            ctk.CTkLabel(
                self.badge_frame,
                text=label,
                corner_radius=12,
                fg_color="#1F2A44",
                font=("Segoe UI", 11, "bold"),
                padx=10,
                pady=4,
            ).pack(side="left", padx=4)

    def _clear_summary_sections(self) -> None:
        self._clear_tab_contents("Summary")

    def _render_summary_message(self, message: str) -> None:
        self._render_tab_message("Summary", message)

    def _render_summary_sections(self, sections: dict[str, list[str]]) -> None:
        if not sections:
            self._render_summary_message("No synthesis data available yet. Add notes for richer context.")
            return
        self._clear_summary_sections()
        for title, values in sections.items():
            frame = ctk.CTkFrame(self.summary_container, fg_color="#141C30", corner_radius=12)
            frame.pack(fill="x", pady=(0, 12))
            ctk.CTkLabel(
                frame,
                text=title,
                font=("Segoe UI", 13, "bold"),
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(12, 6))
            content = values if values else ["No details have been recorded yet."]
            for value in content:
                ctk.CTkLabel(
                    frame,
                    text=value,
                    font=("Segoe UI", 12),
                    wraplength=500,
                    justify="left",
                    anchor="w",
                ).pack(fill="x", padx=12, pady=(0, 8))

    def _populate_summary_tab(self, sections: dict[str, list[str]]) -> None:
        self._render_summary_sections(sections)

    def _populate_notes_tab(self, record: dict | None) -> None:
        self._clear_tab_contents("Notes")
        self._notes_textbox = None
        self._notes_status_label = None

        token = self._inspector_token or self.selected_token
        if not token or token.get("type") == "map":
            self._render_tab_message(
                "Notes",
                "Notes are available for NPCs, PCs, creatures, and places.",
            )
            return

        container = self.notes_container
        textbox = ctk.CTkTextbox(
            container,
            wrap="word",
            font=("Segoe UI", 12),
            height=220,
        )
        textbox.pack(fill="both", expand=True, pady=(0, 12))

        existing_notes = ""
        if isinstance(record, dict):
            raw_value = record.get("Notes")
            if isinstance(raw_value, str):
                existing_notes = raw_value
            elif raw_value is not None:
                existing_notes = self._normalize_text(raw_value)
        if existing_notes:
            textbox.insert("1.0", existing_notes)

        controls = ctk.CTkFrame(container, fg_color="transparent")
        controls.pack(fill="x")
        status_label = ctk.CTkLabel(controls, text="", font=("Segoe UI", 11))
        status_label.pack(side="left", padx=(0, 6))
        save_button = ctk.CTkButton(
            controls,
            text="Save Notes",
            width=120,
            command=self._on_save_notes,
        )
        save_button.pack(side="right")

        self._notes_textbox = textbox
        self._notes_status_label = status_label

    def _populate_characters_tab(self, _record: dict | None) -> None:
        self._clear_tab_contents("Characters")
        self._entity_tab_images = []

        relevant_tokens = [
            token
            for token in self.tokens
            if str(token.get("entity_type")).upper() in {"NPC", "CREATURE"}
        ]
        if not relevant_tokens:
            self._render_tab_message(
                "Characters",
                "Add NPCs or creatures to this map to review their stats here.",
            )
            return

        relevant_tokens.sort(
            key=lambda token: (
                str(token.get("entity_type") or ""),
                str(token.get("entity_id") or ""),
            )
        )

        for token in relevant_tokens:
            frame = ctk.CTkFrame(self.characters_container, fg_color="#141C30", corner_radius=12)
            frame.pack(fill="x", pady=(0, 12))

            body = ctk.CTkFrame(frame, fg_color="transparent")
            body.pack(fill="x", padx=12, pady=12)
            body.grid_columnconfigure(1, weight=1)
            body.grid_columnconfigure(2, weight=0)

            thumbnail = self._resolve_token_image(token, 72)
            self._entity_tab_images.append(thumbnail)
            portrait_label = ctk.CTkLabel(body, text="", image=thumbnail)
            portrait_label.grid(row=0, column=0, rowspan=2, sticky="nw")

            name = token.get("entity_id", "Unnamed")
            entity_type = token.get("entity_type", "Entity")
            title_label = ctk.CTkLabel(
                body,
                text=f"{name}",
                font=("Segoe UI", 14, "bold"),
                anchor="w",
            )
            title_label.grid(row=0, column=1, sticky="w", padx=(12, 0))

            type_label = ctk.CTkLabel(
                body,
                text=entity_type,
                font=("Segoe UI", 11, "bold"),
                text_color="#93A2D3",
            )
            type_label.grid(row=0, column=2, sticky="ne")

            stats_preview = self._get_stats_preview(token.get("record"))
            stats_label = ctk.CTkLabel(
                body,
                text=stats_preview,
                font=("Segoe UI", 12),
                wraplength=320,
                justify="left",
                anchor="w",
            )
            stats_label.grid(row=1, column=1, columnspan=2, sticky="we", padx=(12, 0), pady=(6, 0))

    def _on_entity_card_selected(self, token: dict) -> None:
        if token not in self.tokens:
            return
        self.selected_token = token
        self._show_entity_synthesis(token)
        if hasattr(self, "tab_selector"):
            self.tab_selector.set("Summary")
        self._select_inspector_tab("Summary")

    def _get_stats_preview(self, record: dict | None) -> str:
        if not isinstance(record, dict):
            return "No stats available yet."
        stats_value = record.get("Traits")
        if not stats_value:
            stats_value = record.get("Stats")
            
        if not stats_value:
            return "No stats available yet."

        if isinstance(stats_value, dict):
            candidate = None
            for key in ("text", "value", "content"):
                value = stats_value.get(key)
                if isinstance(value, str) and value.strip():
                    candidate = value
                    break
            if candidate:
                stats_value = candidate
            else:
                joined = "\n".join(
                    str(value).strip()
                    for value in stats_value.values()
                    if isinstance(value, str) and value.strip()
                )
                stats_value = joined or stats_value

        normalized = self._normalize_text(stats_value).strip()
        return normalized if normalized else "No stats available yet."

    def _get_summary_preview(self, record: dict | None) -> str:
        if not isinstance(record, dict):
            return "No details available yet."
        for key in ("Summary", "Synopsis", "Description", "Background", "Notes"):
            value = record.get(key)
            if not value:
                continue
            normalized = self._normalize_text(value).strip()
            if not normalized:
                continue
            single_line = " ".join(normalized.split())
            if not single_line:
                continue
            return textwrap.shorten(single_line, width=220, placeholder="...")
        return "No details available yet."

    def _on_save_notes(self) -> None:
        token = self._inspector_token or self.selected_token
        textbox = self._notes_textbox
        if not token or not textbox:
            return
        if token.get("type") == "map":
            if self._notes_status_label:
                self._notes_status_label.configure(
                    text="Notes are not supported for maps.",
                    text_color="#F7C948",
                )
            return

        notes = textbox.get("1.0", "end").rstrip()
        success = self._save_entity_notes(token, notes)

        if success:
            entity_type = token.get("entity_type", "Entity")
            entity_id = token.get("entity_id")
            updated_record = self._fetch_record(entity_type, entity_id)
            if isinstance(updated_record, dict):
                token["record"] = updated_record
                self._update_token_records(entity_type, entity_id, updated_record)
                sections = self._compose_summary(entity_type, updated_record)
                self._populate_summary_tab(sections)
                self._populate_characters_tab(updated_record)
            if self._notes_status_label:
                self._notes_status_label.configure(
                    text="Notes saved",
                    text_color="#7CD992",
                )
        else:
            if self._notes_status_label:
                self._notes_status_label.configure(
                    text="Failed to save notes",
                    text_color="#F17171",
                )

    def _save_entity_notes(self, token: dict, notes: str) -> bool:
        entity_type = token.get("entity_type")
        table = self._get_entity_table_name(entity_type)
        if not table:
            return False

        ensure_entity_schema(table)
        identifier = token.get("entity_id")
        if not identifier:
            return False

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in cursor.fetchall()}
            if "Notes" not in columns:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN Notes TEXT")
                columns.add("Notes")

            cursor.execute(
                f"UPDATE {table} SET Notes = ? WHERE Name = ?",
                (notes, identifier),
            )
            updated = cursor.rowcount
            if updated == 0 and "Title" in columns:
                cursor.execute(
                    f"UPDATE {table} SET Notes = ? WHERE Title = ?",
                    (notes, identifier),
                )
                updated = cursor.rowcount

            conn.commit()

            if updated == 0:
                cursor.execute(
                    f"SELECT 1 FROM {table} WHERE Name = ?",
                    (identifier,),
                )
                exists = cursor.fetchone() is not None
                if not exists and "Title" in columns:
                    cursor.execute(
                        f"SELECT 1 FROM {table} WHERE Title = ?",
                        (identifier,),
                    )
                    exists = cursor.fetchone() is not None
                if not exists:
                    log_warning(
                        f"No rows updated when saving notes for {entity_type} '{identifier}'",
                        func_name="WorldMapWindow._save_entity_notes",
                    )
                return exists
            return True
        except Exception as exc:
            log_error(
                f"Failed to persist notes for {entity_type}: {exc}",
                func_name="WorldMapWindow._save_entity_notes",
            )
            return False
        finally:
            conn.close()

    @staticmethod
    def _get_entity_table_name(entity_type: str | None) -> str | None:
        if not entity_type:
            return None
        mapping = {
            "NPC": "npcs",
            "PC": "pcs",
            "CREATURE": "creatures",
            "PLACE": "places",
            "MAP": "maps",
        }
        return mapping.get(str(entity_type).upper())

    def _update_token_records(self, entity_type: str | None, entity_id: str | None, record: dict) -> None:
        if not entity_type or not entity_id:
            return
        for entry in self.tokens:
            if (
                str(entry.get("entity_type")).upper() == str(entity_type).upper()
                and entry.get("entity_id") == entity_id
            ):
                entry["record"] = record

    def _compose_summary(self, entity_type: str, record: dict) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        summary = None
        for key in ("Summary", "Synopsis", "Description", "Background", "Notes"):
            value = record.get(key)
            if value:
                summary = self._normalize_text(value)
                if summary:
                    break
        sections["Overview"] = [summary] if summary else []

        detail_fields: dict[str, tuple[str, list[str]]] = {
            "NPC": ("Profile", ["Role", "Traits", "Motivation", "Secret"]),
            "PC": ("Adventurer Details", ["Role", "Traits", "Background", "Secret"]),
            "Creature": ("Creature Traits", ["Type", "Powers", "Stats", "Weakness"]),
            "Place": ("Location Facts", ["Description", "NPCs", "Secrets", "PlayerDisplay"]),
        }

        header, fields = detail_fields.get(entity_type, ("Details", []))
        harvested = self._harvest_fields(record, fields)[:6] if fields else []
        sections[header] = harvested

        summary_keys = {"Summary", "Synopsis", "Description", "Background", "Notes"}
        general_details = []
        for key, value in record.items():
            if key in summary_keys or key in fields:
                continue
            if isinstance(value, (dict, set)):
                continue
            if isinstance(value, (list, tuple)):
                formatted = ", ".join(str(v) for v in value if v)
            elif isinstance(value, str):
                formatted = self._normalize_text(value)
            else:
                formatted = str(value).strip()
            if formatted:
                general_details.append(f"{key}: {formatted}")
        if general_details:
            if fields:
                sections["Additional Notes"] = general_details[:6]
            else:
                sections[header] = general_details[:6]

        return sections

    def _harvest_fields(self, record: dict, fields: list[str]) -> list[str]:
        out = []
        for field in fields:
            value = record.get(field)
            if isinstance(value, (list, tuple)):
                joined = ", ".join(str(v) for v in value if v)
                if joined:
                    out.append(f"{field}: {joined}")
            elif isinstance(value, dict):
                normalized = self._normalize_text(value)
                if normalized:
                    out.append(f"{field}: {normalized}")
            elif value:
                out.append(f"{field}: {value}")
        return out

    def _collect_badges(self, entity_type: str, record: dict) -> list[str]:
        badges = []
        for key in ("Role", "Type", "Alignment", "Challenge", "Faction", "Status", "Class", "Level"):
            value = record.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                badges.append(str(value).strip())
        tags = record.get("Tags")
        if isinstance(tags, (list, tuple)):
            badges.extend(str(tag).strip() for tag in tags if tag)
        if entity_type and entity_type not in badges:
            badges.insert(0, entity_type)
        seen = []
        for badge in badges:
            badge = badge.strip()
            if badge and badge not in seen:
                seen.append(badge)
        return seen[:5]

    def _summarize_map_contents(self, record: dict) -> list[str]:
        raw = record.get(WORLD_TOKENS_KEY) or []
        legacy_source = False
        if not raw:
            raw = record.get("Tokens") or []
            legacy_source = True
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, json.JSONDecodeError):
                raw = []
        if not isinstance(raw, list):
            return []
        counts: dict[str, int] = {}
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            entry_type = entry.get("entity_type") or entry.get("type")
            entry_type_lower = str(entry_type).lower() if entry_type is not None else ""
            if legacy_source and entry.get("type") not in {"map", "entity", "world"}:
                continue
            if entry_type_lower in {"rectangle", "oval", "circle", "shape", "line", "polygon"}:
                continue
            if entry_type:
                counts[entry_type] = counts.get(entry_type, 0) + 1
        return [f"{label}: {count}" for label, count in counts.items() if count]

    def _normalize_text(self, value) -> str:
        if value is None:
            return ""
        normalized = format_longtext(value)
        if isinstance(normalized, (list, tuple)):
            return "\n".join(str(v) for v in normalized if v)
        return str(normalized)

    def _resolve_portrait_path(self, record: dict) -> str | None:
        portrait = record.get("Portrait")
        if isinstance(portrait, dict):
            return portrait.get("path") or portrait.get("text")
        if isinstance(portrait, str):
            return portrait
        return None

    def _resolve_map_image(self, record: dict) -> str | None:
        return record.get("Image")

    def _fetch_record(self, entity_type: str, name: str | None) -> dict | None:
        if not name:
            return None
        wrappers = {
            "NPC": self.npc_wrapper,
            "PC": self.pc_wrapper,
            "Creature": self.creature_wrapper,
            "Place": self.place_wrapper,
            "Map": self.maps_wrapper,
        }
        wrapper = wrappers.get(entity_type)
        if not wrapper:
            return None
        return next(
            (item for item in wrapper.load_items() if item.get("Name") == name or item.get("Title") == name),
            None,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _on_destroy(self, _event=None) -> None:
        if getattr(self.master, "_world_map_window", None) is self:
            self.master._world_map_window = None
