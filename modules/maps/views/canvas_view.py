import tkinter as tk
from PIL import ImageDraw
MIN_ZOOM = 0.01  # Minimum zoom level to prevent division by zero

def _build_canvas(self):
    self.canvas = tk.Canvas(self.parent, bg="black")
    self.canvas.pack(fill="both", expand=True)

    # Global Copy/Paste/Delete bindings on the real Tk root
    root = self.parent.winfo_toplevel()
    root.bind_all("<Control-c>", lambda event: self._copy_item()) # Use generic item copy
    root.bind_all("<Control-C>", lambda event: self._copy_item()) # Case insensitive
    root.bind_all("<Control-v>", lambda event: self._paste_item()) # Use generic item paste
    root.bind_all("<Control-V>", lambda event: self._paste_item()) # Case insensitive
    root.bind_all("<Delete>", self._on_delete_key) # Calls updated _on_delete_key
    
    # Undo fog
    root.bind_all("<Control-z>",   lambda e: self.undo_fog(e))
    root.bind_all("<Control-Z>",   lambda e: self.undo_fog(e))
    
    root.bind_all("<Control-f>", self.open_global_search)
    root.bind_all("<Control-F>", self.open_global_search)
    
    root.bind_all("<Control-s>", lambda e: self.save_map())
    root.bind_all("<Control-S>", lambda e: self.save_map())

    root.bind_all("<Control-p>", lambda e: self.open_fullscreen())
    root.bind_all("<Control-P>", lambda e: self.open_fullscreen())
    # Painting, panning, markers
    self.canvas.bind("<ButtonPress-1>",    self._on_mouse_down)
    self.canvas.bind("<B1-Motion>",        self._on_mouse_move)
    self.canvas.bind("<ButtonRelease-1>",  self._on_mouse_up)
    self.canvas.bind("<ButtonPress-2>",    self._on_middle_click) # Typically middle mouse
    
    # Zoom & resize
    self.canvas.bind("<MouseWheel>",       self.on_zoom)
    # Configure binding might be better on self.canvas if self.parent is not the direct container that resizes
    self.parent.bind("<Configure>",        lambda e: self._update_canvas_images() if self.base_img else None)


def _on_delete_key(self, event=None):
    """If an item (token or shape) is selected, delete it on Delete key."""
    if not self.selected_token: # selected_token now refers to the selected item
        return
    
    item_to_delete = self.selected_token
    self.selected_token = None # Clear selection before deleting
    self._delete_item(item_to_delete) # Use the generic delete method

def on_paint2(self, event):
    """Paint or erase fog using a square brush of size self.brush_size,
       with semi-transparent black (alpha=128) for fog."""
    # Prevent fog painting if a drag operation is in progress for any item
    if any(t.get('drag_data') for t in self.tokens):
        return
    if not self.mask_img:
        return

    # Convert screen → world coords
    # Ensure zoom is not zero to prevent division by zero error
    current_zoom = self.zoom if self.zoom != 0 else MIN_ZOOM 
    xw = (event.x - self.pan_x) / current_zoom
    yw = (event.y - self.pan_y) / current_zoom

    half = self.brush_size / 2
    left   = int(xw - half)
    top    = int(yw - half)
    right  = int(xw + half)
    bottom = int(yw + half)

    draw = ImageDraw.Draw(self.mask_img)
    fill_color = (0,0,0,0) # Default to erase (transparent)
    if self.fog_mode == "add":
        fill_color = (0,0,0,128) # Semi-transparent black to add fog
    
    if self.brush_shape == "circle":
        draw.ellipse([left, top, right, bottom], fill=fill_color)
    else: # Default to rectangle
        draw.rectangle([left, top, right, bottom], fill=fill_color)

    self._update_canvas_images()
