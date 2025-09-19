"""World Map exploration window with nested map navigation and entity synthesis."""
import os
import json
import tkinter as tk
from tkinter import messagebox, simpledialog
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw

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

        self._suppress_map_change = False

        self._build_layout()

        if self.map_names:
            self.map_selector.configure(values=self.map_names)
            self.map_selector.set(self.map_names[0])
            self.load_map(self.map_names[0], push_history=False)
        else:
            self._show_empty_state()

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

        ctk.CTkButton(toolbar, text="Save", width=120, command=self._persist_tokens).pack(side="right", padx=12)

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

        self.badge_frame = ctk.CTkFrame(self.inspector_container, fg_color="transparent")
        self.badge_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.summary_box = ctk.CTkTextbox(self.inspector_container, wrap="word", font=("Segoe UI", 13))

        self.bind("<Delete>", self._delete_selected_token)
        self.summary_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.summary_box.configure(state="disabled")

        self._clear_inspector()

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
            return

        if push_history and self.current_map_name:
            self.map_stack.append(self.current_map_name)
        elif not push_history:
            self.map_stack.clear()
        self._update_back_button_state()

        self.current_map_name = map_name
        self.current_world_map = entry

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
        picker.geometry("900x600")

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
        scale = min(canvas_w / base_w, canvas_h / base_h)
        scaled_w, scaled_h = int(base_w * scale), int(base_h * scale)
        offset_x = (canvas_w - scaled_w) // 2
        offset_y = (canvas_h - scaled_h) // 2
        self.render_params = (scale, offset_x, offset_y, base_w, base_h)

        resized = self.base_image.resize((scaled_w, scaled_h), Image.LANCZOS)
        self.base_photo = ImageTk.PhotoImage(resized)
        self.canvas.create_image(offset_x, offset_y, anchor="nw", image=self.base_photo)

        for token in self.tokens:
            self._draw_token(token)
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

    def _clear_inspector(self) -> None:
        self.title_label.configure(text="World Map")
        self.subtitle_label.configure(text="Select an entity to view its synthesis.")
        for child in self.badge_frame.winfo_children():
            child.destroy()
        self.summary_box.configure(state="normal")
        self.summary_box.delete("1.0", "end")
        self.summary_box.insert(
            "1.0",
            "Use the controls above to place NPCs, PCs, creatures, places, and nested maps. "
            "Double-click a map token to dive deeper, and drag entities to reposition them.",
        )
        self.summary_box.configure(state="disabled")

    def _show_entity_synthesis(self, token: dict) -> None:
        record = token.get("record") or {}
        entity_type = token.get("entity_type", "Entity")
        name = token.get("entity_id", "Unnamed")
        summary_text, bullet_lines = self._compose_summary(entity_type, record)
        badges = self._collect_badges(entity_type, record)

        self.title_label.configure(text=name)
        self.subtitle_label.configure(text=entity_type)
        self._render_badges(badges)

        body = []
        if summary_text:
            body.append(summary_text)
        body.extend(bullet_lines)
        if not body:
            body.append("No synthesis data available yet. Add notes for richer context.")

        self.summary_box.configure(state="normal")
        self.summary_box.delete("1.0", "end")
        self.summary_box.insert("1.0", "\n\n".join(body))
        self.summary_box.configure(state="disabled")

    def _show_map_hint(self, token: dict) -> None:
        map_name = token.get("linked_map") or token.get("entity_id") or "Nested Map"
        entry = self.world_maps.get(map_name, {})
        wrapper_record = self.maps_wrapper_data.get(map_name, {})
        summary_text = entry.get('summary') or self._normalize_text(wrapper_record.get("Summary")) or self._normalize_text(wrapper_record.get("Description"))
        badges = self._summarize_map_contents(entry)

        self.title_label.configure(text=map_name)
        self.subtitle_label.configure(text="Nested Map")
        self._render_badges(badges or ["Double-click to enter"])

        hint = summary_text or "Double-click this map token to open its layer and keep building your world."
        self.summary_box.configure(state="normal")
        self.summary_box.delete("1.0", "end")
        self.summary_box.insert("1.0", hint)
        self.summary_box.configure(state="disabled")

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

    def _compose_summary(self, entity_type: str, record: dict) -> tuple[str, list[str]]:
        summary = None
        for key in ("Summary", "Synopsis", "Description", "Background", "Notes"):
            value = record.get(key)
            if value:
                summary = self._normalize_text(value)
                if summary:
                    break
        bullets = []
        if entity_type == "NPC":
            bullets.extend(self._harvest_fields(record, ["Role", "Faction", "Motivation", "Secrets"]))
        elif entity_type == "PC":
            bullets.extend(self._harvest_fields(record, ["Class", "Level", "Player", "Goals"]))
        elif entity_type == "Creature":
            bullets.extend(self._harvest_fields(record, ["Type", "Challenge", "Abilities", "Weaknesses"]))
        elif entity_type == "Place":
            bullets.extend(self._harvest_fields(record, ["Tags", "Population", "Climate", "Resources"]))
        return summary or "", bullets[:6]

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
