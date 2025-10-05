from tkinter import messagebox
import ast
import json
import os
from functools import lru_cache
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.template_loader import load_template
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


def _resolve_campaign_path(path: str) -> str:
    """Return an absolute path for campaign-relative assets."""
    if not path:
        return ""
    normalized = str(path).strip()
    if not normalized:
        return ""
    if os.path.isabs(normalized):
        return os.path.normpath(normalized)
    return os.path.normpath(os.path.join(ConfigHelper.get_campaign_dir(), normalized))


def _campaign_relative_path(path: str) -> str:
    if not path:
        return ""
    if not os.path.isabs(path):
        return str(path).replace("\\", "/")
    campaign_dir = ConfigHelper.get_campaign_dir()
    try:
        relative = os.path.relpath(path, campaign_dir)
    except ValueError:
        return path
    if relative.startswith(".."):  # outside the campaign directory
        return path
    return relative.replace(os.sep, "/")


@lru_cache(maxsize=1)
def _default_token_image_path() -> str:
    """Locate the default pin image shipped with the application."""

    campaign_pin = _resolve_campaign_path(os.path.join("assets", "pin.png"))
    if campaign_pin and os.path.exists(campaign_pin):
        return campaign_pin

    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    bundled_pin = os.path.normpath(os.path.join(project_root, "assets", "pin.png"))
    if os.path.exists(bundled_pin):
        return bundled_pin

    return ""


@lru_cache(maxsize=256)
def _find_existing_token_image(original_path: str) -> str:
    """Attempt to locate a token image inside the current campaign.

    Some persisted databases contain absolute paths from other machines. When
    those paths are reloaded we try to discover a matching asset inside the
    active campaign directory by progressively stripping leading folders and
    finally falling back to a filename search beneath the campaign's assets
    directory. Returns an absolute path if a match is found, otherwise an empty
    string.
    """

    if not original_path:
        return ""

    campaign_dir = ConfigHelper.get_campaign_dir()
    normalized = os.path.normpath(str(original_path))

    if os.path.isabs(normalized) and os.path.exists(normalized):
        return normalized

    parts = [
        part for part in normalized.replace("\\", "/").split("/")
        if part and part != "." and not (len(part) == 2 and part[1] == ":") and not part.endswith(":")
    ]

    if not parts:
        return ""

    candidates = []
    seen = set()
    lowered_parts = [part.lower() for part in parts]

    if "assets" in lowered_parts:
        idx = lowered_parts.index("assets")
        candidate_rel = os.path.join(*parts[idx:])
        candidate_abs = os.path.normpath(os.path.join(campaign_dir, candidate_rel))
        if candidate_abs not in seen:
            candidates.append(candidate_abs)
            seen.add(candidate_abs)

    for start in range(len(parts)):
        candidate_rel = os.path.join(*parts[start:])
        candidate_abs = os.path.normpath(os.path.join(campaign_dir, candidate_rel))
        if candidate_abs not in seen:
            candidates.append(candidate_abs)
            seen.add(candidate_abs)

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    filename = os.path.basename(normalized)
    if not filename:
        return ""

    assets_root = os.path.join(campaign_dir, "assets")
    if not os.path.isdir(assets_root):
        return ""

    for root, _, files in os.walk(assets_root):
        if filename in files:
            return os.path.join(root, filename)

    return ""

def select_map(self):
    """Show the full‐frame map selector, replacing any existing UI."""
    for w in self.parent.winfo_children():
        w.destroy()

    selector = GenericListSelectionView(
        self.parent,
        "maps",
        self.maps,
        self.map_template,
        on_select_callback=self._on_display_map
    )
    selector.pack(fill="both", expand=True)

def _on_display_map(self, entity_type, map_name): # entity_type here is the map's default, not token's
    """Callback from selector: build editor UI and load the chosen map."""
    # 1) Lookup the chosen map record
    item = self._maps.get(map_name)
    if not item:
        messagebox.showwarning("Not Found", f"Map '{map_name}' not found.")
        return
    self.current_map = item

    # Restore token size if set
    size = item.get("token_size")
    if isinstance(size, int):
        self.token_size = size

    # Restore hover font size if persisted
    hover_size = item.get("hover_font_size")
    if isinstance(hover_size, int) and hover_size > 0:
        self.hover_font_size = hover_size
        if hover_size not in getattr(self, "hover_font_size_options", []):
            self.hover_font_size_options.append(hover_size)
            self.hover_font_size_options = sorted(set(self.hover_font_size_options))
        try:
            self.hover_font.configure(size=self.hover_font_size)
        except Exception:
            self.hover_font = ctk.CTkFont(size=self.hover_font_size)

    # 2) Tear down any existing UI & build toolbar + canvas
    for w in self.parent.winfo_children():
        w.destroy()
    self._build_toolbar()
    self._build_canvas()

    # 3) Load base image + fog mask
    image_path = (item.get("Image", "") or "").strip()
    full_image_path = _resolve_campaign_path(image_path)
    try:
        self.base_img = Image.open(full_image_path).convert("RGBA")
    except (FileNotFoundError, OSError):
        messagebox.showerror(
            "Map Image Missing",
            f"The map image for '{map_name}' could not be found."
        )
        self.base_img = Image.new("RGBA", (1280, 720), (0, 0, 0, 255))
    mask_path = (item.get("FogMaskPath") or "").strip()
    full_mask_path = _resolve_campaign_path(mask_path) if mask_path else ""
    if mask_path and os.path.isfile(full_mask_path):
        try:
            self.mask_img = Image.open(full_mask_path).convert("RGBA")
        except (FileNotFoundError, OSError):
            self.mask_img = Image.new("RGBA", self.base_img.size, (0, 0, 0, 128))
    else:
        self.mask_img = Image.new("RGBA", self.base_img.size, (0, 0, 0, 128))

    # Restore pan/zoom if available, otherwise use defaults
    zoom_raw  = item.get("zoom", 1.0)
    pan_x_raw = item.get("pan_x", 0)
    pan_y_raw = item.get("pan_y", 0)
    
    if self.zoom is None:
        self.zoom = 1.0
    if self.pan_x is None:
        self.pan_x = 0
    if self.pan_y is None:
        self.pan_y = 0
    
    try:
        self.zoom  = float(zoom_raw)
    except (TypeError, ValueError):
        self.zoom = 1.0

    try:
        self.pan_x = float(pan_x_raw)
    except (TypeError, ValueError):
        self.pan_x = 0.0

    try:
        self.pan_y = float(pan_y_raw)
    except (TypeError, ValueError):
        self.pan_y = 0.0
        
    # 4) Clear out any old tokens from both canvases
    for t_obj in self.tokens: # Renamed t to t_obj to avoid conflict
        for cid in t_obj.get("canvas_ids", []):
            self.canvas.delete(cid)
        if self.fs_canvas and t_obj.get("fs_canvas_ids"):
            for cid in t_obj["fs_canvas_ids"]:
                self.fs_canvas.delete(cid)
    self.tokens = []

    # 5) Parse persisted token list
    raw = item.get("Tokens", [])
   
    if isinstance(raw, str):
        try:
            # Try ast.literal_eval first as it's safer for simple structures
            token_list = ast.literal_eval(raw.strip() or "[]")
        except (ValueError, SyntaxError): # Catch errors from ast.literal_eval
            try:
                # Fallback to json.loads if ast.literal_eval fails
                token_list = json.loads(raw)
            except json.JSONDecodeError: # Catch errors from json.loads
                token_list = []
                print(f"[_on_display_map] Failed to parse Tokens string: {raw}")
        if not isinstance(token_list, list): # Ensure the result is a list
            print(f"[_on_display_map] Parsed Tokens string but did not get a list: {raw}")
            token_list = []

    elif isinstance(raw, list):
        token_list = raw
    else:
        token_list = []
    
    print(f"[_on_display_map] Processing {len(token_list)} items from map data.")

    # 6) Pre-load all Creature & NPC records once
    creatures = {r.get("Name"): r for r in self._model_wrappers["Creature"].load_items()}
    npcs      = {r.get("Name"): r for r in self._model_wrappers["NPC"].load_items()}
    pcs       = {r.get("Name"): r for r in self._model_wrappers["PC"].load_items()}

    # 7) Build self.tokens (now includes shapes)
    token_paths_updated = False

    for rec in token_list:
        item_type_from_rec = rec.get("type", "token") # Default to token if not specified
        
        pos = rec.get("position") # Position should always be present
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            xw, yw = pos
        else: # Fallback if position is malformed or missing x,y keys
            xw = rec.get("x", 0) 
            yw = rec.get("y", 0)

        # Base data for all items
        item_data = {
            "type": item_type_from_rec,
            "position": (xw, yw),
        }

        if item_type_from_rec == "token":

            portrait_path = (rec.get("image_path") or "").strip()
            path = _resolve_campaign_path(portrait_path) if portrait_path else ""

            if path and not os.path.exists(path):
                fallback_path = _find_existing_token_image(portrait_path)
                if not fallback_path and portrait_path != path:
                    fallback_path = _find_existing_token_image(path)
                if fallback_path and os.path.exists(fallback_path):
                    path = fallback_path
                    portrait_path = _campaign_relative_path(path)
                    print(
                        f"[_on_display_map] Updated missing token image path to '{portrait_path}'."
                    )
                    rec["image_path"] = portrait_path
                    token_paths_updated = True

            sz   = rec.get("size", self.token_size) # Use self.token_size as default
            pil_image = None
            source_image = None
            resolved_path = ""

            if path:
                if os.path.exists(path):
                    try:
                        source_image = Image.open(path).convert("RGBA")
                        pil_image = source_image.resize((sz, sz), resample=Image.LANCZOS)
                        resolved_path = path
                    except Exception as e:
                        print(f"[_on_display_map] Failed to load token image '{path}': {e}. Trying default pin image.")
                        source_image = None
                        pil_image = None
                else:
                    print(f"[_on_display_map] Token image path not found: '{path}'. Trying default pin image.")
            else:
                print(f"[_on_display_map] Token missing image_path. Trying default pin image for ID: {rec.get('entity_id')}.")

            if pil_image is None:
                default_pin_path = _default_token_image_path()
                if default_pin_path and os.path.exists(default_pin_path):
                    try:
                        source_image = Image.open(default_pin_path).convert("RGBA")
                        pil_image = source_image.resize((sz, sz), resample=Image.LANCZOS)
                        resolved_path = default_pin_path
                        print(f"[_on_display_map] Using default pin image for token '{rec.get('entity_id')}'.")
                    except Exception as fallback_error:
                        print(
                            "[_on_display_map] Failed to load default pin image: "
                            f"{fallback_error}. Creating placeholder."
                        )
                        source_image = None
                        pil_image = None
                else:
                    print("[_on_display_map] Default pin image not found. Creating placeholder.")

            if pil_image is None:
                pil_image = Image.new("RGBA", (sz, sz), (255, 0, 0, 128))
                source_image = pil_image

            storage_path = _campaign_relative_path(resolved_path) if resolved_path else portrait_path

            item_data.update({
                "entity_type":  rec.get("entity_type"), # Must come from record for tokens
                "entity_id":    rec.get("entity_id"),
                "image_path":   storage_path,
                "source_image": source_image,
                "pil_image":    pil_image,
                "border_color": rec.get("border_color", "#0000ff"), # Default blue for tokens
                "size":         sz,
                "hp":           rec.get("hp", 10),           
                "max_hp":       rec.get("max_hp", 10),
                "hp_label_id":  None,                        
                "hp_entry":     None,                        
                "hp_entry_id":  None
            })
        elif item_type_from_rec in ["rectangle", "oval"]:
            item_data.update({
                "shape_type":   rec.get("shape_type", item_type_from_rec), # Ensure this matches type
                "fill_color":   rec.get("fill_color", "#FFFFFF"),
                "border_color": rec.get("border_color", "#000000"), # Default black for shapes
                "is_filled":    rec.get("is_filled", True),
                "width":        rec.get("width", 50), # Default width for shapes
                "height":       rec.get("height", 50),# Default height for shapes
                "pil_image":    None, # Shapes don't use PIL image for drawing
            })
        elif item_type_from_rec == "marker":
            item_data.update({
                "text": rec.get("text", "New Marker"),
                "description": rec.get("description", "Marker description"),
                "entry_width": rec.get("entry_width", 180),
                "border_color": rec.get("border_color", "#00ff00"),
                "video_path": rec.get("video_path", ""),
                "linked_map": rec.get("linked_map", ""),
                "border_canvas_id": None,
                "entry_widget": None,
                "description_popup": None,
                "description_label": None,
                "description_visible": False,
                "description_editor": None,
                "focus_pending": False,
            })
        else:
            print(f"[_on_display_map] Unknown item type '{item_type_from_rec}' in map data. Skipping: {rec}")
            continue

        self.tokens.append(item_data)

    if token_paths_updated:
        try:
            self._persist_tokens()
        except Exception as exc:
            print(f"[_on_display_map] Failed to persist updated token image paths: {exc}")

    # 8) Hydrate token metadata for info card display (ONLY FOR TOKENS)
    for current_item in self.tokens:
        if current_item.get("type", "token") == "token":
            token_entity_type = current_item.get("entity_type")
            token_entity_id = current_item.get("entity_id")

            if not token_entity_type or not token_entity_id:
                print(f"[_on_display_map] Token missing entity_type or entity_id, cannot hydrate info: {current_item}")
                current_item["entity_record"] = {}
            else:
                record = {}
                if token_entity_type == "Creature":
                    record = creatures.get(token_entity_id, {})
                elif token_entity_type == "PC":
                    record = pcs.get(token_entity_id, {})
                elif token_entity_type == "NPC":
                    record = npcs.get(token_entity_id, {})
                else:
                    print(f"[_on_display_map] Unknown entity_type '{token_entity_type}' for token ID '{token_entity_id}'. Cannot hydrate info.")
                current_item["entity_record"] = record
        else:
            current_item["entity_record"] = {}

        current_item["hover_popup"] = None
        current_item["hover_label"] = None
        current_item["hover_visible"] = False
        current_item["hover_bbox"] = None

    # 9) Finally draw everything onto the canvas
    self._update_canvas_images()
    if getattr(self, '_web_server_thread', None):
        self._update_web_display_map()
