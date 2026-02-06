import tkinter as tk
from PIL import ImageTk, Image
from screeninfo import get_monitors
from modules.helpers.logging_helper import log_module_import
from modules.maps.utils.text_items import TextFontCache

log_module_import(__name__)

def open_fullscreen(self):
    monitors = get_monitors()
    if len(monitors) < 2:
        return
    m = monitors[1]
    self.fs = tk.Toplevel(self.parent)
    self.fs.title("Players Map")
    self.fs.resizable(True, True)
    self.fs.geometry(f"{m.width}x{m.height}+{m.x}+{m.y}")
    self.fs_canvas = tk.Canvas(self.fs, bg="black")
    self.fs_canvas.pack(fill="both", expand=True)
    # reset IDs so base/mask/tokens all get re-created on the new canvas
    self.fs_base_id = None
    self.fs_mask_id = None
    # clear any stale fullscreen token IDs
    for token in self.tokens:
        token.pop('fs_canvas_ids', None)
    self._update_fullscreen_map()

def _update_fullscreen_map(self):
    """Mirror the GM canvas into the fullscreen window."""
    fs_canvas = getattr(self, "fs_canvas", None)
    base = getattr(self, '_video_current_frame_pil', None) or getattr(self, 'base_img', None)
    if not fs_canvas or not base:
        return

    try:
        if not fs_canvas.winfo_exists():
            return
    except tk.TclError:
        return

    # Same logic as above but on fs_canvas
    w, h = base.size
    sw, sh = int(w*self.zoom), int(h*self.zoom)
    x0, y0 = self.pan_x, self.pan_y

    base_resized = base.resize((sw,sh), resample=Image.LANCZOS)
    self.fs_base_tk = ImageTk.PhotoImage(base_resized)
    if self.fs_base_id:
        self.fs_canvas.itemconfig(self.fs_base_id, image=self.fs_base_tk)
        self.fs_canvas.coords(self.fs_base_id, x0, y0)
    else:
        self.fs_base_id = self.fs_canvas.create_image(x0, y0,
                                                      image=self.fs_base_tk,
                                                      anchor='nw')

    # Clear existing token/shape representations on fs_canvas before redrawing
    # This prevents duplicates if fs_canvas_ids were not properly cleaned up or if items are removed.
    for item_to_clear in self.tokens:
        if 'fs_canvas_ids' in item_to_clear:
            for fs_id in item_to_clear['fs_canvas_ids']:
                if fs_id: # Check if fs_id is not None
                    try:
                        self.fs_canvas.delete(fs_id)
                    except tk.TclError: # Item might have already been deleted
                        pass
            # It's important to remove the key so items are fully recreated,
            # especially if their structure (e.g. number of canvas IDs) changes.
            del item_to_clear['fs_canvas_ids']
        
        if 'fs_cross_ids' in item_to_clear: # For dead token markers
            for fs_id in item_to_clear['fs_cross_ids']:
                if fs_id:
                    try:
                        self.fs_canvas.delete(fs_id)
                    except tk.TclError:
                        pass
            del item_to_clear['fs_cross_ids']
        
        item_to_clear.pop('fs_tk', None) # Remove old PhotoImage reference to allow GC

    for item in self.tokens:
        item_type = item.get("type", "token")
        xw, yw = item.get('position', (0,0)) # Use .get() for position as well for safety
        sx = int(xw * self.zoom + self.pan_x)
        sy = int(yw * self.zoom + self.pan_y)

        if item_type == "marker":
            continue

        if item_type == "token":
            if not bool(item.get('player_visible', True)):
                continue
            source = item.get('source_image')
            pil = item.get('pil_image')
            size_px = item.get('size')
            if size_px is None:
                if source is not None:
                    size_px = source.size[0]
                elif pil is not None:
                    size_px = pil.size[0]
                else:
                    size_px = getattr(self, 'token_size', 64)
            try:
                size_px = max(1, int(size_px))
            except Exception:
                size_px = max(1, int(getattr(self, 'token_size', 64)))

            if source is not None:
                nw = nh = max(1, int(size_px * self.zoom))
                if nw <= 0 or nh <= 0:
                    continue
                img_r = source.resize((nw, nh), resample=Image.LANCZOS)
            else:
                if not pil:
                    continue

                tw, th = pil.size
                if tw <= 0 or th <= 0:
                    continue

                nw, nh = int(tw * self.zoom), int(th * self.zoom)
                if nw <= 0 or nh <= 0:
                    continue

                img_r = pil.resize((nw, nh), resample=Image.LANCZOS)
            fsimg = ImageTk.PhotoImage(img_r)
            item['fs_tk'] = fsimg # Store the PhotoImage to prevent garbage collection

            # Token border, image, and name
            fs_canvas_ids = item.get('fs_canvas_ids')
            if fs_canvas_ids and len(fs_canvas_ids) == 3: # Expecting (border_id, image_id, text_id)
                b_id, i_id, t_id = fs_canvas_ids
                self.fs_canvas.coords(b_id, sx - 3, sy - 3, sx + nw + 3, sy + nh + 3)
                self.fs_canvas.itemconfig(b_id, outline=item.get('border_color', '#0000ff'))
                self.fs_canvas.coords(i_id, sx, sy)
                self.fs_canvas.itemconfig(i_id, image=fsimg)
                self.fs_canvas.coords(t_id, sx + nw // 2, sy + nh + 2)
                self.fs_canvas.itemconfig(t_id, text=item.get('entity_id', ''))
            else:
                b_id = self.fs_canvas.create_rectangle(sx - 3, sy - 3, sx + nw + 3, sy + nh + 3,
                                                       outline=item.get('border_color', '#0000ff'), width=3)
                i_id = self.fs_canvas.create_image(sx, sy, image=fsimg, anchor='nw')
                t_id = self.fs_canvas.create_text(sx + nw // 2, sy + nh + 2, text=item.get('entity_id', ''),
                                                  fill='white', anchor='n')
                item['fs_canvas_ids'] = (b_id, i_id, t_id)

            # HP-related cross for dead tokens
            hp = item.get("hp", 0)
            if hp <= 0:
                if 'fs_cross_ids' not in item:
                    tl = (sx, sy)
                    br = (sx + nw, sy + nh)
                    tr = (sx + nw, sy)
                    bl = (sx, sy + nh)
                    line1 = self.fs_canvas.create_line(*tl, *br, fill="red", width=3)
                    line2 = self.fs_canvas.create_line(*tr, *bl, fill="red", width=3)
                    item['fs_cross_ids'] = (line1, line2)
            else: # HP > 0, remove cross if it exists
                if 'fs_cross_ids' in item:
                    for x_id in item['fs_cross_ids']:
                        self.fs_canvas.delete(x_id)
                    del item['fs_cross_ids']

        elif item_type in ["rectangle", "oval"]:
            shape_width_unscaled = item.get("width", 50) # Default if missing
            shape_height_unscaled = item.get("height", 50) # Default if missing

            shape_width = int(shape_width_unscaled * self.zoom)
            shape_height = int(shape_height_unscaled * self.zoom)

            if shape_width <= 0 or shape_height <= 0:
                continue

            fill_color = item.get("fill_color", "") if item.get("is_filled", True) else ""
            border_color = item.get("border_color", "#000000")
            
            fs_shape_id_tuple = item.get('fs_canvas_ids') # Shapes usually have one ID in a tuple
            fs_shape_id = fs_shape_id_tuple[0] if fs_shape_id_tuple and len(fs_shape_id_tuple) > 0 else None

            if fs_shape_id:
                if item_type == "rectangle":
                    self.fs_canvas.coords(fs_shape_id, sx, sy, sx + shape_width, sy + shape_height)
                elif item_type == "oval":
                    self.fs_canvas.coords(fs_shape_id, sx, sy, sx + shape_width, sy + shape_height)
                self.fs_canvas.itemconfig(fs_shape_id, fill=fill_color, outline=border_color)
            else:
                new_fs_shape_id = None
                if item_type == "rectangle":
                    new_fs_shape_id = self.fs_canvas.create_rectangle(sx, sy, sx + shape_width, sy + shape_height,
                                                                  fill=fill_color, outline=border_color, width=2)
                elif item_type == "oval":
                    new_fs_shape_id = self.fs_canvas.create_oval(sx, sy, sx + shape_width, sy + shape_height,
                                                               fill=fill_color, outline=border_color, width=2)
                if new_fs_shape_id:
                    item['fs_canvas_ids'] = (new_fs_shape_id,)
        elif item_type == "whiteboard":
            points = item.get("points") or []
            if len(points) < 2:
                continue
            screen_points = []
            for px, py in points:
                screen_points.extend([self.pan_x + px * self.zoom, self.pan_y + py * self.zoom])
            color = item.get("color", "#FF0000")
            width = item.get("width", 4)
            line_id = None
            fs_ids = item.get("fs_canvas_ids") or ()
            if fs_ids:
                line_id = fs_ids[0]
                try:
                    self.fs_canvas.coords(line_id, *screen_points)
                    self.fs_canvas.itemconfig(line_id, fill=color, width=width, smooth=True)
                except tk.TclError:
                    line_id = None
            if not line_id:
                try:
                    line_id = self.fs_canvas.create_line(
                        *screen_points,
                        fill=color,
                        width=width,
                        smooth=True,
                        capstyle="round",
                        joinstyle="round",
                    )
                    item["fs_canvas_ids"] = (line_id,)
                except tk.TclError:
                    item["fs_canvas_ids"] = ()
        elif item_type == "text":
            text_value = item.get("text", "")
            color = item.get("color", "#FF0000")
            size = int(item.get("text_size", getattr(self, "text_size", 24)))
            font_cache = getattr(self, "_text_font_cache", None)
            if font_cache is None:
                font_cache = TextFontCache()
                setattr(self, "_text_font_cache", font_cache)
            font = font_cache.tk_font(size)
            text_id = None
            fs_ids = item.get("fs_canvas_ids") or ()
            if fs_ids:
                text_id = fs_ids[0]
                try:
                    self.fs_canvas.coords(text_id, sx, sy)
                    self.fs_canvas.itemconfig(text_id, text=text_value, fill=color, font=font)
                except tk.TclError:
                    text_id = None
            if not text_id:
                try:
                    text_id = self.fs_canvas.create_text(sx, sy, text=text_value, fill=color, anchor='nw', font=font)
                    item["fs_canvas_ids"] = (text_id,)
                except tk.TclError:
                    item["fs_canvas_ids"] = ()
    # Fog of War Mask (should be drawn last, on top of everything else)
    if self.mask_img: # Ensure mask_img exists
        try:
            # Ensure sw and sh for mask are valid (same as base_img scaled dimensions)
            if sw > 0 and sh > 0:
                mask_copy = self.mask_img.copy()
                # split out alpha channel
                _, _, _, alpha_channel = mask_copy.split() # Renamed to avoid conflict if alpha was a var
                # map any alpha>0 to 255, leave 0 as 0
                processed_alpha = alpha_channel.point(lambda a: 255 if a > 0 else 0)
                mask_copy.putalpha(processed_alpha)
                
                mask_resized = mask_copy.resize((sw, sh), Image.LANCZOS)
                self.fs_mask_tk = ImageTk.PhotoImage(mask_resized) # Store to prevent GC
                
                if self.fs_mask_id:
                    self.fs_canvas.itemconfig(self.fs_mask_id, image=self.fs_mask_tk)
                    self.fs_canvas.coords(self.fs_mask_id, x0, y0)
                else:
                    self.fs_mask_id = self.fs_canvas.create_image(x0, y0,
                                                                image=self.fs_mask_tk,
                                                                anchor='nw')
                self.fs_canvas.tag_raise(self.fs_mask_id) # Ensure mask is on top
            # else:
                # print("Skipping fullscreen mask rendering due to invalid scaled dimensions.")
        except Exception as e:
            # print(f"Error processing or rendering fullscreen fog mask: {e}")
            # If mask processing fails, we might want to ensure an old mask isn't shown
            if self.fs_mask_id:
                self.fs_canvas.delete(self.fs_mask_id)
                self.fs_mask_id = None
            pass
    elif self.fs_mask_id: # If no mask_img, but an old fs_mask_id exists, delete it
        self.fs_canvas.delete(self.fs_mask_id)
        self.fs_mask_id = None

    if hasattr(self, '_update_web_display_map'):
        try:
            self._update_web_display_map()
        except Exception:
            pass

