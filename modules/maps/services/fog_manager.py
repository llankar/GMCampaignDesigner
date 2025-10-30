from PIL import ImageDraw, Image, ImageTk
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

_BRUSH_FOG_MODES = {"add", "rem"}
_RECTANGLE_FOG_MODES = {"add_rect", "rem_rect"}
_ALL_FOG_MODES = _BRUSH_FOG_MODES | _RECTANGLE_FOG_MODES


def _set_fog(self, mode):
    """Toggle the active fog tool between brush/rectangle add/remove modes."""
    if mode not in _ALL_FOG_MODES:
        new_mode = None
    else:
        current = getattr(self, "fog_mode", None)
        new_mode = None if current == mode else mode

    self.fog_mode = new_mode

    updater = getattr(self, "_update_fog_button_states", None)
    if callable(updater):
        updater()

    if new_mode not in _RECTANGLE_FOG_MODES:
        reset_preview = getattr(self, "_clear_fog_rectangle_preview", None)
        if callable(reset_preview):
            reset_preview()
        if hasattr(self, "_fog_rect_start_world"):
            self._fog_rect_start_world = None


def apply_fog_rectangle(self, bounds, mode):
    """Fill a rectangular fog region directly onto the mask image."""
    if mode not in _RECTANGLE_FOG_MODES:
        return

    if not self.mask_img:
        return

    if not bounds or len(bounds) != 4:
        return

    left, top, right, bottom = bounds

    if left > right:
        left, right = right, left
    if top > bottom:
        top, bottom = bottom, top

    width, height = self.mask_img.size

    if right < 0 or bottom < 0 or left >= width or top >= height:
        return

    left = max(0, min(width - 1, left))
    right = max(0, min(width - 1, right))
    top = max(0, min(height - 1, top))
    bottom = max(0, min(height - 1, bottom))

    draw = ImageDraw.Draw(self.mask_img)
    draw_color = (0, 0, 0, 128) if mode == "add_rect" else (0, 0, 0, 0)
    draw.rectangle((left, top, right, bottom), fill=draw_color)

def clear_fog(self):
    self.mask_img = Image.new("RGBA", self.base_img.size, (0,0,0,0))
    self._update_canvas_images()

def reset_fog(self):
    self.mask_img = Image.new("RGBA", self.base_img.size, (0, 0, 0, 128))
    self._update_canvas_images()

def on_paint(self, event):
    """Paint or erase fog using a square brush of size self.brush_size,
       with semi-transparent black (alpha=128) for fog."""
    if self.fog_mode not in _BRUSH_FOG_MODES:
        return
    if any('drag_data' in t for t in self.tokens):
        return
    if not self.mask_img:
        return

    # Convert screen → world coords
    xw = (event.x - self.pan_x) / self.zoom
    yw = (event.y - self.pan_y) / self.zoom

    half = self.brush_size / 2
    left   = int(xw - half)
    top    = int(yw - half)
    right  = int(xw + half)
    bottom = int(yw + half)

    draw = ImageDraw.Draw(self.mask_img)
    # actually paint or erase on the mask_img
    if self.fog_mode == "add":
        draw_color= (0, 0, 0, 128)  # semi-transparent black
    else:
        draw_color= (0, 0, 0, 0) # semi-transparent black
    if self.brush_shape == "circle":
        draw.ellipse((left, top, right, bottom), fill=draw_color)
    else:
        draw.rectangle((left, top, right, bottom), fill=draw_color)
    
    half = self.brush_size/2
    size      = int(self.brush_size * self.zoom)
    half_size = size // 2
    size      = int(self.brush_size * self.zoom)
    half_size = size // 2

    # Directly center on the mouse‐pointer (event.x/event.y):
    px = event.x - half_size
    py = event.y - half_size

    
    # —— only resize & blit the mask ——
    w, h = self.base_img.size
    sw, sh = int(w * self.zoom), int(h * self.zoom)

    # use the interactive (fast) filter
    mask_resized = self.mask_img.resize((sw, sh), resample=self._fast_resample)
    self.mask_tk = ImageTk.PhotoImage(mask_resized)

    # update the existing canvas image item
    self.canvas.itemconfig(self.mask_id, image=self.mask_tk)
    self.canvas.coords(self.mask_id, self.pan_x, self.pan_y)

