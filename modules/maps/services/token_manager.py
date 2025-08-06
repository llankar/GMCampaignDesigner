import json
from PIL import Image, ImageTk
import customtkinter as ctk
from tkinter import messagebox, colorchooser
import os
from modules.helpers.config_helper import ConfigHelper
from modules.ui.image_viewer import show_portrait
import tkinter.simpledialog as sd
import tkinter as tk
import threading

def add_token(self, path, entity_type, entity_name, entity_record=None):
    img_path = path
    if img_path and not os.path.isabs(img_path):
        candidate = os.path.join(ConfigHelper.get_campaign_dir(), img_path)
        if os.path.exists(candidate):
            img_path = candidate
    if not img_path or not os.path.exists(img_path):
        messagebox.showerror(
            "Error",
            f"Token image not found for '{entity_name}': {img_path}"
        )
        return

    pil_img = Image.open(img_path).convert("RGBA")
    pil_img = pil_img.resize((self.token_size, self.token_size), resample=Image.LANCZOS)

    # Get canvas center in world coords
    self.canvas.update_idletasks()
    cw = self.canvas.winfo_width()
    ch = self.canvas.winfo_height()
    xw_center = (cw/2 - self.pan_x) / self.zoom
    yw_center = (ch/2 - self.pan_y) / self.zoom

    # Hydrate the info box
    raw = entity_record.get("Stats", "") if entity_type == "Creature" else entity_record.get("Traits", "")
    display = "\n".join(map(str, raw)) if isinstance(raw, (list, tuple)) else str(raw)
    height = self.token_size * 2
    info_widget = ctk.CTkTextbox(self.canvas, width=100, height=height, wrap="word")
    info_widget._textbox.delete("1.0", "end")
    info_widget._textbox.insert("1.0", display)

    token = {
        "entity_type":  entity_type,
        "entity_id":    entity_name,
        "image_path":   img_path,
        "pil_image":    pil_img,
        "position":     (xw_center, yw_center),
        "border_color": "#0000ff",
        "entity_record": entity_record or {},
        "info_widget": info_widget,  # ✅ fix crash here
        "hp": 10,
        "hp_label_id": None,
        "hp_entry": None,
        "hp_entry_id": None
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
    info_widget_id = token.get("info_widget_id")
    if info_widget_id:
        self.canvas.move(info_widget_id, dx, dy)
    sx, sy = self.canvas.coords(i_id)
    if "hp_canvas_ids" in token:
        cid, tid = token["hp_canvas_ids"]
        self.canvas.move(cid, dx, dy)
        self.canvas.move(tid, dx, dy)
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
    pil_img = Image.open(c["image_path"]).convert("RGBA") \
                .resize((c["size"], c["size"]), Image.LANCZOS)

    # Clone all relevant fields into a new token dict
    token = {
        "entity_type":  c["entity_type"],
        "entity_id":    c["entity_id"],
        "image_path":   c["image_path"],
        "size":         c["size"],
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
        pil = Image.open(token["image_path"]) \
                .convert("RGBA") \
                .resize((new_size, new_size), Image.LANCZOS)
    except Exception as e:
        messagebox.showerror("Error", f"Could not resize token image:\n{e}")
        return

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
    if "info_widget_id" in token:
        self.canvas.delete(token["info_widget_id"])
        token["info_widget"].destroy()
        del token["info_widget"], token["info_widget_id"]

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
                item_data.update({
                    "entity_type":    t.get("entity_type", ""),
                    "entity_id":      t.get("entity_id", ""),
                    "image_path":     t.get("image_path", ""),
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
