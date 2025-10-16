import ast
import json
from PIL import Image
from tkinter import messagebox, colorchooser
import os
from modules.helpers.config_helper import ConfigHelper
from modules.ui.image_viewer import show_portrait
import tkinter.simpledialog as sd
import tkinter as tk
import threading
from typing import Any, Tuple
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


def _resolve_campaign_path(path: str) -> str:
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


def _normalize_geometry(value):
    """Convert tuples to lists for JSON serialisation while preserving structure."""
    if isinstance(value, dict):
        return {key: _normalize_geometry(sub_value) for key, sub_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_geometry(item) for item in value]
    return value


def _deserialize_tokens_field(raw_tokens: Any) -> Tuple[list, type]:
    """Return a list of token dicts and remember the original container type."""
    if isinstance(raw_tokens, list):
        return raw_tokens, list
    if isinstance(raw_tokens, str):
        trimmed = raw_tokens.strip()
        if not trimmed:
            return [], str
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, list):
                return parsed, str
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(trimmed)
                if isinstance(parsed, list):
                    return parsed, str
            except (ValueError, SyntaxError):
                pass
        return [], str
    return [], type(raw_tokens)


def normalize_existing_token_paths(maps_wrapper) -> bool:
    """Convert stored token image paths to campaign-relative references."""
    if not maps_wrapper:
        return False

    try:
        items = maps_wrapper.load_items()
    except Exception:
        return False

    updated_items = []
    any_updated = False

    for item in items:
        raw_tokens = item.get("Tokens")
        tokens_list, original_type = _deserialize_tokens_field(raw_tokens)
        if not tokens_list:
            updated_items.append(item)
            continue

        item_updated = False
        for token in tokens_list:
            if not isinstance(token, dict):
                continue
            existing_path = token.get("image_path")
            if existing_path:
                resolved = _resolve_campaign_path(existing_path)
                relative = _campaign_relative_path(resolved)
                if relative and relative != existing_path:
                    token["image_path"] = relative
                    item_updated = True

            if token.get("type") == "marker":
                existing_video = token.get("video_path")
                if existing_video:
                    resolved_video = _resolve_campaign_path(existing_video)
                    relative_video = _campaign_relative_path(resolved_video)
                    if relative_video and relative_video != existing_video:
                        token["video_path"] = relative_video
                        item_updated = True

            if token.get("type") == "overlay":
                overlay_path = token.get("animation_path") or token.get("animation_asset_path")
                if overlay_path:
                    resolved_overlay = _resolve_campaign_path(overlay_path)
                    relative_overlay = _campaign_relative_path(resolved_overlay)
                    if relative_overlay and relative_overlay != overlay_path:
                        token["animation_path"] = relative_overlay
                        token["animation_asset_path"] = relative_overlay
                        item_updated = True

        if item_updated:
            new_item = dict(item)
            if original_type is str:
                new_item["Tokens"] = json.dumps(tokens_list)
            else:
                new_item["Tokens"] = tokens_list
            updated_items.append(new_item)
            any_updated = True
        else:
            updated_items.append(item)

    if any_updated:
        try:
            maps_wrapper.save_items(updated_items)
        except Exception:
            return False

    return any_updated

def add_token(self, path, entity_type, entity_name, entity_record=None):
    img_path = _resolve_campaign_path(path)
    if not img_path or not os.path.exists(img_path):
        messagebox.showerror(
            "Error",
            f"Token image not found for '{entity_name}': {img_path}"
        )
        return

    source_img = Image.open(img_path).convert("RGBA")
    logical_size = int(self.token_size)
    pil_img = source_img.resize((logical_size, logical_size), resample=Image.LANCZOS)

    storage_path = _campaign_relative_path(img_path)

    # Get canvas center in world coords
    self.canvas.update_idletasks()
    cw = self.canvas.winfo_width()
    ch = self.canvas.winfo_height()
    xw_center = (cw/2 - self.pan_x) / self.zoom
    yw_center = (ch/2 - self.pan_y) / self.zoom

    token = {
        "type":         "token",
        "entity_type":  entity_type,
        "entity_id":    entity_name,
        "image_path":   storage_path,
        "size":         logical_size,
        "source_image": source_img,
        "pil_image":    pil_img,
        "position":     (xw_center, yw_center),
        "border_color": "#0000ff",
        "entity_record": entity_record or {},
        "hp": 10,
        "hp_label_id": None,
        "hp_entry": None,
        "hp_entry_id": None,
        "hover_popup": None,
        "hover_textbox": None,
        "hover_visible": False,
        "hover_bbox": None,
    }

    self.tokens.append(token)
    self._update_canvas_images()
    self._persist_tokens()

    if getattr(self, "fs_canvas", None) and self.fs_canvas.winfo_exists():
        self._update_fullscreen_map()
    if getattr(self, '_web_server_thread', None):
        self._update_web_display_map()

def _on_token_press(self, event, token):
    # mark this as the “selected” token for copy/paste
    self.selected_token = token
    token["drag_data"] = {"x": event.x, "y": event.y}

def _on_token_move(self, event, token):
    dx = event.x - token["drag_data"]["x"]
    dy = event.y - token["drag_data"]["y"]
    b_id, i_id = token["canvas_ids"]
    self.canvas.move(b_id, dx, dy)
    self.canvas.move(i_id, dx, dy)
    # move the name label too, if it exists
    name_id = token.get("name_id")
    if name_id:
        self.canvas.move(name_id, dx, dy)
    token["drag_data"] = {"x": event.x, "y": event.y}
    sx, sy = self.canvas.coords(i_id)
    if "hp_canvas_ids" in token:
        cid, tid = token["hp_canvas_ids"]
        self.canvas.move(cid, dx, dy)
        self.canvas.move(tid, dx, dy)
    try:
        bbox = self.canvas.bbox(b_id)
    except tk.TclError:
        bbox = None
    if bbox:
        token["hover_bbox"] = bbox
    refresh = getattr(self, "_refresh_token_hover_popup", None)
    if callable(refresh):
        refresh(token)
        if token.get("hover_visible"):
            show_fn = getattr(self, "_show_token_hover", None)
            if callable(show_fn):
                show_fn(token)
    token["position"] = ((sx - self.pan_x)/self.zoom, (sy - self.pan_y)/self.zoom)

def _on_token_release(self, event, token):
    token.pop("drag_data", None)
    # debounce any pending save
    try:
        self.canvas.after_cancel(self._persist_after_id)
    except AttributeError:
        pass

    # schedule one save after the UI becomes idle
    self._persist_after_id = self.canvas.after_idle(self._persist_tokens)

def _copy_token(self, event=None):
    """Copy the last‐clicked token’s data into a buffer."""
    """Ctrl+C → copy the currently selected token."""
    if not self.selected_token:
        return
    t = self.selected_token
    # store only the minimal data needed to recreate it
    self.clipboard_token = {
        "entity_type":  t["entity_type"],
        "entity_id":    t["entity_id"],
        "image_path":   t["image_path"],
        "size":         t.get("size", self.token_size),
        "border_color": t.get("border_color", "#0000ff"),
        "hp":           t.get("hp", 10),        # ← copy current HP
        "max_hp":       t.get("max_hp", 10),    # ← copy maximum HP
    }

def _paste_token(self, event=None):
    c = getattr(self, "clipboard_token", None)
    if not c:
        return
    # compute center of the *visible* canvas in world coords
    vcx = (self.canvas.winfo_width() // 2 - self.pan_x) / self.zoom
    vcy = (self.canvas.winfo_height() // 2 - self.pan_y) / self.zoom

    # Re-create the PIL image at the original token size
    resolved_path = _resolve_campaign_path(c.get("image_path"))
    source_img = Image.open(resolved_path).convert("RGBA")
    storage_path = _campaign_relative_path(resolved_path)
    size = int(c["size"])
    pil_img = source_img.resize((size, size), Image.LANCZOS)

    # Clone all relevant fields into a new token dict
    token = {
        "type":         "token",
        "entity_type":  c["entity_type"],
        "entity_id":    c["entity_id"],
        "image_path":   storage_path,
        "size":         size,
        "source_image": source_img,
        "border_color": c["border_color"],
        "pil_image":    pil_img,
        "position":     (vcx, vcy),
        "drag_data":    {},
        "hp":           c["hp"],      # ← restore current HP
        "max_hp":       c["max_hp"],  # ← restore max HP
    }

    # Add it to your tokens list, then persist & re-draw everything
    self.tokens.append(token)
    self._persist_tokens()
    self._update_canvas_images()

def _resize_token_dialog(self, token):
    """Prompt for a new px size, then redraw just that token."""
    # use the current slider value as the popup’s starting point
    new_size = sd.askinteger(
        "Resize Token",
        "Enter new token size (px):",
        initialvalue=self.token_size,
        minvalue=8, maxvalue=512
    )
    if new_size is None:
        return

    # 1) update the token’s PIL image & stored size
    try:
        source_img = token.get("source_image")
        if source_img is None:
            resolved = _resolve_campaign_path(token.get("image_path"))
            source_img = Image.open(resolved).convert("RGBA")
        pil = source_img.resize((new_size, new_size), Image.LANCZOS)
    except Exception as e:
        messagebox.showerror("Error", f"Could not resize token image:\n{e}")
        return

    token["source_image"] = source_img
    token["pil_image"] = pil
    token["size"]      = new_size

    # 2) re-draw the canvas (this will pick up token['pil_image'])
    self._update_canvas_images()
    if getattr(self, "fs_canvas", None):
        self._update_fullscreen_map()
    if getattr(self, '_web_server_thread', None):
        self._update_web_display_map()

    # 3) persist both tokens *and* the global slider
    self._persist_tokens()
    self.current_map["token_size"] = self.token_size
    self.maps.save_items(list(self._maps.values()))

def _change_token_border_color(self, token):
    """Open a color chooser and update the token’s border."""
    result = colorchooser.askcolor(
        color=token.get("border_color", "#0000ff"),
        title="Choose token border color"
    )
    # result == ( (r,g,b), "#rrggbb" ) or (None, None) if cancelled
    if result and result[1]:
        new_color = result[1]
        token["border_color"] = new_color
        # update GM canvas border
        b_id = token["canvas_ids"][0]
        self.canvas.itemconfig(b_id, outline=new_color)
        # update fullscreen border if open
        if getattr(self, "fs_canvas", None) and "fs_canvas_ids" in token:
            fs_b_id = token["fs_canvas_ids"][0]
            self.fs_canvas.itemconfig(fs_b_id, outline=new_color)
        # persist the choice
        self._persist_tokens()

def _delete_token(self, token):
    """Remove a token’s canvas items (image, border, name, HP UI, info widget, edit entries) and its data."""
    # 1) Main token border & image
    for cid in token.get("canvas_ids", []):
        self.canvas.delete(cid)

    # 2) Name label under the token
    if "name_id" in token:
        self.canvas.delete(token["name_id"])
        del token["name_id"]

    # 3) HP circle + text
    if "hp_canvas_ids" in token:
        for cid in token["hp_canvas_ids"]:
            self.canvas.delete(cid)
        del token["hp_canvas_ids"]

    # 4) Any inline HP edit entry
    if "hp_entry_widget_id" in token:
        self.canvas.delete(token["hp_entry_widget_id"])
        token["hp_entry_widget"].destroy()
        del token["hp_entry_widget"], token["hp_entry_widget_id"]

    # 5) Any inline max-HP edit entry
    if "max_hp_entry_widget_id" in token:
        self.canvas.delete(token["max_hp_entry_widget_id"])
        token["max_hp_entry_widget"].destroy()
        del token["max_hp_entry_widget"], token["max_hp_entry_widget_id"]

    # 6) The info widget on the right
    popup = token.get("hover_popup")
    if popup and popup.winfo_exists():
        popup.destroy()
    token["hover_popup"] = None
    token["hover_textbox"] = None
    token["hover_visible"] = False
    token.pop("hover_bbox", None)

    # 7) Fullscreen mirror items, if present
    if getattr(self, "fs_canvas", None):
        # remove the border/image/Text on the second screen
        if "fs_canvas_ids" in token:
            for cid in token["fs_canvas_ids"]:
                self.fs_canvas.delete(cid)
            del token["fs_canvas_ids"]
        # **also** remove the red‐cross lines if they exist
        if "fs_cross_ids" in token:
            for cid in token["fs_cross_ids"]:
                self.fs_canvas.delete(cid)
            del token["fs_cross_ids"]

    # 8) Finally remove from state & persist
    self.tokens.remove(token)
    self._persist_tokens()

def _persist_tokens(self):
    """Quickly capture token state, then hand off the heavy write to a daemon thread."""
    # 1) Build the JSON in–memory (cheap)
    data = []
    try:
        if isinstance(getattr(self, "current_map", None), dict):
            hover_size = int(getattr(self, "hover_font_size", 14))
            if hover_size > 0:
                self.current_map["hover_font_size"] = hover_size
    except Exception:
        pass
    for t in self.tokens:
        try:
            x, y = t["position"]
            item_type = t.get("type", "token")

            item_data = {
                "type": item_type,
                "x": x,
                "y": y,
            }

            if item_type == "token":
                storage_path = _campaign_relative_path(t.get("image_path", ""))
                item_data.update({
                    "entity_type":    t.get("entity_type", ""),
                    "entity_id":      t.get("entity_id", ""),
                    "image_path":     storage_path,
                    "size":           t.get("size", self.token_size),
                    "hp":             t.get("hp", 10),
                    "max_hp":         t.get("max_hp", 10),
                    "border_color":   t.get("border_color", "#0000ff"),
                })
            elif item_type in ["rectangle", "oval"]:
                item_data.update({
                    "shape_type":     t.get("shape_type", item_type),
                    "fill_color":     t.get("fill_color", "#FFFFFF"),
                    "is_filled":      t.get("is_filled", True),
                    "width":          t.get("width", 50),
                    "height":         t.get("height", 50),
                    "border_color":   t.get("border_color", "#000000"),
                })
            elif item_type == "marker":
                entry_widget = t.get("entry_widget")
                if entry_widget and entry_widget.winfo_exists():
                    t["text"] = entry_widget.get()
                video_path = t.get("video_path", "")
                resolved_video = _resolve_campaign_path(video_path)
                storage_video = _campaign_relative_path(resolved_video) if resolved_video else ""
                item_data.update({
                    "text": t.get("text", ""),
                    "description": t.get("description", ""),
                    "entry_width": t.get("entry_width", 180),
                    "border_color": t.get("border_color", "#00ff00"),
                    "video_path": storage_video,
                    "linked_map": t.get("linked_map", ""),
                })
            elif item_type == "overlay":
                animation_path = t.get("animation_path") or t.get("animation_asset_path") or ""
                resolved_animation = _resolve_campaign_path(animation_path)
                storage_animation = _campaign_relative_path(resolved_animation) if resolved_animation else animation_path
                playback = t.get("playback") or t.get("playback_settings") or {}
                if not isinstance(playback, dict):
                    try:
                        playback = dict(playback)
                    except Exception:
                        playback = {}
                opacity = t.get("opacity", 1.0)
                try:
                    opacity = float(opacity)
                except (TypeError, ValueError):
                    opacity = 1.0
                coverage = _normalize_geometry(t.get("coverage") or t.get("coverage_geometry") or {})
                item_data.update({
                    "animation_path": storage_animation,
                    "animation_asset_path": storage_animation,
                    "playback": playback,
                    "opacity": opacity,
                    "coverage": coverage,
                })
            else:
                # Silently skip unknown types for now
                continue

            data.append(item_data)
        except Exception as e:
            print(f"Error processing item {t} for persistence: {e}")
            continue

    self.current_map["Tokens"] = json.dumps(data)
    all_maps = list(self._maps.values())

    # 2) Fire‐and‐forget the actual disk write so the UI never blocks
    
    def _write_maps():
            try:
                    self.maps.save_items(all_maps)
            except Exception as e:
                    print(f"[persist_tokens] Background save error: {e}")

    threading.Thread(target=_write_maps, daemon=True).start()
