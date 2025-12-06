import os
import json
import copy
import math
import re
import webbrowser
import threading
import io
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox
import tkinter as tk
from tkinter import font as tkfont
from types import SimpleNamespace
from typing import TYPE_CHECKING
import customtkinter as ctk
from modules.maps.views.map_selector import select_map, _on_display_map
from modules.maps.views.toolbar_view import (
    _build_toolbar,
    _on_brush_size_change,
    _on_brush_shape_change,
    _change_brush,
    _on_token_size_change,
    _update_fog_button_states,
)
from modules.maps.views.canvas_view import _build_canvas, _on_delete_key
from modules.maps.services.fog_manager import (
    _set_fog,
    clear_fog,
    reset_fog,
    on_paint,
    apply_fog_rectangle,
)
# Removed direct imports from token_manager, as methods are now part of this controller or generic
# from modules.maps.services.token_manager import add_token, _on_token_press, _on_token_move, _on_token_release, _copy_token, _paste_token, _show_token_menu, _resize_token_dialog, _change_token_border_color, _delete_token, _persist_tokens
from modules.maps.services.token_manager import (
    add_token,
    _persist_tokens,
    _change_token_border_color,
    _resolve_campaign_path,
    _campaign_relative_path,
    normalize_existing_token_paths,
    _extract_entity_defense_value,
)  # Keep this if it's used by other token_manager functions not moved
from modules.maps.views.fullscreen_view import open_fullscreen, _update_fullscreen_map
from modules.maps.views.web_display_view import open_web_display, _update_web_display_map, close_web_display
from modules.maps.services.entity_picker_service import (
    open_entity_picker,
    on_entity_selected,
    on_entities_selected,
)
from modules.maps.utils.icon_loader import load_icon
from PIL import Image, ImageTk, ImageDraw
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.template_loader import load_template


CLIPBOARD_SKIP = object()
from modules.helpers.text_helpers import format_longtext
from modules.helpers.config_helper import ConfigHelper
from modules.ui.image_viewer import show_portrait
from modules.maps.utils.text_items import (
    DEFAULT_TEXT_SIZES,
    TextFontCache,
    create_text_item,
    prompt_for_text,
    text_hit_test,
)
from modules.ui.video_player import play_video_on_second_screen
from modules.ui.chatbot_dialog import (
    get_default_chatbot_wrappers,
    open_chatbot_dialog,
    _DEFAULT_NAME_FIELD_OVERRIDES as CHATBOT_NAME_OVERRIDES,
)
from modules.helpers.logging_helper import log_module_import, log_warning, log_info, log_debug
from modules.helpers.dice_markup import parse_inline_actions
from modules.maps.exporters.maptools import build_token_macros
from modules.dice import dice_engine
from modules.dice import dice_preferences
from modules.audio.entity_audio import (
    get_entity_audio_value,
    play_entity_audio,
    stop_entity_audio,
)

log_module_import(__name__)

if TYPE_CHECKING:
    from modules.dice.dice_bar_window import DiceBarWindow

DEFAULT_BRUSH_SIZE = 32  # px
DEFAULT_SHAPE_WIDTH = 50
DEFAULT_SHAPE_HEIGHT = 50

MASKS_DIR = os.path.join(ConfigHelper.get_campaign_dir(), "masks")
MAX_ZOOM = 3.0
MIN_ZOOM = 0.1
ZOOM_STEP = 0.1  # 10% per wheel notch
ctk.set_appearance_mode("dark")

LINK_PATTERN = re.compile(r"(https?://|www\.)[^\s<>]+", re.IGNORECASE)

class DisplayMapController:
    def __init__(self, parent, maps_wrapper, map_template, *, root_app=None):
        self.parent = parent
        self.maps = maps_wrapper
        self.map_template = map_template
        self._root_app = root_app

        normalize_existing_token_paths(maps_wrapper)

        self._model_wrappers = {
            "NPC":      GenericModelWrapper("npcs"),
            "Creature": GenericModelWrapper("creatures"),
            "PC": GenericModelWrapper("pcs"),
        }
        self._chatbot_wrappers = get_default_chatbot_wrappers()
        self._templates = {
            "NPC":      load_template("npcs"),
            "Creature": load_template("creatures"),
            "PC": load_template("pcs"),
        }
        # --- State ---
        self.current_map = None
        self.base_img    = None
        self.mask_img    = None
        self.base_tk     = None
        self.mask_tk     = None
        self.base_id     = None
        self.mask_id     = None
        self._zoom_after_id = None
        self._zoom_final_after_id = None
        self._fast_resample = Image.BILINEAR
        self.zoom        = 1.0
        self.pan_x       = 0
        self.pan_y       = 0
        self.selected_token  = None # Selected item (token or shape)
        self.selected_items  = []   # Track all selected items to prepare for multi-select workflows
        self._drag_select_start = None
        self._drag_select_rect_id = None
        self._drag_select_active = False
        self._pre_drag_selection = []
        self._drag_select_modifiers = {"shift": False, "ctrl": False}
        self._selection_overlays = {}
        self._selection_icon_cache = {}
        self.clipboard_token = None # Copied item data (token or shape)
    
        self.brush_size  = DEFAULT_BRUSH_SIZE
        self.brush_size_options = list(range(4, 129, 4))
        self._default_token_size = 48
        self.token_size  = self._default_token_size
        self.token_size_options = list(range(16, 129, 8))
        self.hover_font_size_options = [10, 12, 14, 16, 18, 20, 24, 28, 32]
        self.hover_font_size = 14
        self.hover_font = ctk.CTkFont(size=self.hover_font_size)
        try:
            self.text_size = int(ConfigHelper.get("Drawing", "text_size", fallback=24))
        except Exception:
            self.text_size = 24
        self.text_size_options = list(DEFAULT_TEXT_SIZES)
        if self.text_size not in self.text_size_options:
            self.text_size_options.append(self.text_size)
            self.text_size_options = sorted(set(self.text_size_options))
        self._text_font_cache = TextFontCache()
        self.brush_shape = "rectangle"
        self.fog_mode    = None
        self.tokens      = [] # List of all items (tokens and shapes)
        self._persist_lock = threading.Lock()

        self.drawing_mode = "token"
        self.shape_is_filled = True
        self.current_shape_fill_color = "#CCCCCC"
        self.current_shape_border_color = "#000000"
        self.whiteboard_color = ConfigHelper.get("Drawing", "whiteboard_color", fallback="#FF0000")
        try:
            self.whiteboard_width = float(ConfigHelper.get("Drawing", "whiteboard_width", fallback=4))
        except Exception:
            self.whiteboard_width = 4.0
        try:
            self.whiteboard_eraser_radius = float(ConfigHelper.get("Drawing", "whiteboard_eraser_radius", fallback=8))
        except Exception:
            self.whiteboard_eraser_radius = 8.0
        self._active_whiteboard_points = []
        self._whiteboard_preview_id = None
        self._eraser_active = False
        self._eraser_dirty = False
        self._eraser_repaint_scheduled = False

        self._panning      = False
        self._last_mouse   = (0, 0)
        self._orig_pan     = (0, 0)
    
        self._marker_after_id = None
        self._marker_start    = None
        self._marker_id       = None
        self._fs_marker_id    = None
        self._marker_anim_after_id = None
        self._marker_radius   = None
        self._marker_anim_dir = 1
        self._marker_min_r    = 6
        self._marker_max_r    = 25
        self._hovered_marker  = None

        self._focus_bindings_registered = False

        # --- View fit mode (initial zoom behaviour) ---
        # One of: "Contain", "Width", "Height"
        self.fit_mode = "Contain"
        self._fit_initialized = False

        # Maintain a registry of all popup windows (token info cards and marker
        # descriptions) so the toolbar button can reliably dismiss every one of
        # them even if internal bookkeeping for a token becomes desynchronised.
        self._active_hover_popups = set()
        self._hover_auto_hide_suppressed = 0

        # For interactive shape resizing (re-adding)
        self._resize_handles = []
        self._active_resize_handle_info = None # Stores info about current resize op
        self._handle_size = 8 # pixels for resize handles
        self._handle_fill = "white"
        self._handle_outline = "black"
        self._graphical_edit_mode_item = None # Stores the item for which graphical edit is active
    
        self.fs            = None
        self.fs_canvas     = None
        self.fs_base_id    = None
        self.fs_mask_id    = None
        self.fog_history = []
        self._fog_history_bytes = 0
        self._fog_action_active = False
        self._fog_rect_start_world = None
        self._fog_rect_preview_id = None
        self._fog_rect_fs_preview_id = None

        self._maps = {m["Name"]: m for m in maps_wrapper.load_items()}
        self.select_map()

        # Re-apply fit on container size changes without clobbering user panning
        try:
            self.parent.bind("<Configure>", lambda e: self._apply_fit_mode(defer=True), add="+")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Fit-to-view behaviour
    # ------------------------------------------------------------------
    def _on_fit_mode_change(self, value):
        mode = str(value or "").strip().title()
        if mode not in ("Contain", "Width", "Height"):
            mode = "Contain"
        self.fit_mode = mode
        self._fit_initialized = False
        self._apply_fit_mode()

    def _apply_fit_mode(self, *, defer: bool = False):
        canvas = getattr(self, "canvas", None)
        base = getattr(self, "base_img", None)
        if canvas is None or base is None:
            return
        try:
            if defer:
                # Defer to allow geometry to settle
                self.parent.after(10, lambda: self._apply_fit_mode(defer=False))
                return
        except Exception:
            pass

        try:
            cw = int(canvas.winfo_width())
            ch = int(canvas.winfo_height())
        except Exception:
            return
        if cw <= 1 or ch <= 1:
            return

        bw, bh = base.size if hasattr(base, "size") else (0, 0)
        if bw <= 0 or bh <= 0:
            return

        mode = (self.fit_mode or "Contain").title()
        if mode == "Width":
            zoom = cw / bw
        elif mode == "Height":
            zoom = ch / bh
        else:  # Contain (default)
            zoom = min(cw / bw, ch / bh)

        # Clamp to controller's bounds
        try:
            zmin = float(MIN_ZOOM)
        except Exception:
            zmin = 0.05
        try:
            zmax = float(MAX_ZOOM)
        except Exception:
            zmax = 6.0
        zoom = max(zmin, min(zmax, zoom))

        # Center the image
        self.zoom = zoom
        self.pan_x = (cw - bw * zoom) / 2
        self.pan_y = (ch - bh * zoom) / 2
        self._fit_initialized = True
        try:
            self._update_canvas_images()
        except Exception:
            pass

    def rotate_map_background_right(self):
        """Rotate the loaded map background clockwise by 90 degrees."""
        if getattr(self, "_video_bg_player", None):
            log_warning(
                "Rotation is currently unavailable while a video background is active.",
                func_name="DisplayMapController.rotate_map_background_right",
            )
            messagebox.showwarning(
                "Unavailable",
                "Rotate is unavailable while a video background is playing.",
            )
            return

        base_image = getattr(self, "base_img", None)
        if base_image is None:
            log_warning(
                "Rotate requested without an active base image.",
                func_name="DisplayMapController.rotate_map_background_right",
            )
            return

        try:
            rotated_base = base_image.transpose(Image.Transpose.ROTATE_270)
        except Exception as exc:
            log_warning(
                f"Failed to rotate base image: {exc}",
                func_name="DisplayMapController.rotate_map_background_right",
            )
            return

        self.base_img = rotated_base

        if getattr(self, "mask_img", None) is not None:
            try:
                self.mask_img = self.mask_img.transpose(Image.Transpose.ROTATE_270)
            except Exception as exc:
                log_warning(
                    f"Failed to rotate fog mask: {exc}",
                    func_name="DisplayMapController.rotate_map_background_right",
                )
                self.mask_img = Image.new("RGBA", self.base_img.size, (0, 0, 0, 128))

        self._fit_initialized = False
        self._apply_fit_mode()

    def _set_selection(self, items):
        """Centralised helper to assign the current selection list."""
        unique_items = []
        for candidate in items or []:
            if candidate and candidate not in unique_items:
                unique_items.append(candidate)
        self.selected_items = unique_items
        self.selected_token = unique_items[-1] if unique_items else None

        # If the graphical edit mode item is no longer part of the selection, clear its handles.
        if self._graphical_edit_mode_item and self._graphical_edit_mode_item not in self.selected_items:
            self._remove_resize_handles()
            self._graphical_edit_mode_item = None

        self._update_selection_indicators()

    def _clear_selection(self):
        if not self.selected_items and not self.selected_token:
            return
        self._set_selection([])

    def _is_shift_pressed(self, event):
        state = getattr(event, "state", 0)
        return bool(state & 0x0001)  # Tk shift mask

    def _is_ctrl_pressed(self, event):
        state = getattr(event, "state", 0)
        # Control mask works for Windows/Linux; on macOS Command also maps to 0x0004 in Tk
        return bool(state & 0x0004)

    def _update_selection_state(self, item, event=None):
        if not item:
            self._clear_selection()
            return False

        additive = self._is_shift_pressed(event)
        toggle = self._is_ctrl_pressed(event)

        new_selection = list(self.selected_items)
        item_already_selected = item in new_selection
        item_active = True

        if additive:
            if not item_already_selected:
                new_selection.append(item)
        elif toggle:
            if item_already_selected:
                new_selection = [entry for entry in new_selection if entry is not item]
                item_active = False
            else:
                new_selection.append(item)
        else:
            # Default (no modifiers): keep the current selection intact when
            # clicking an already-selected item so that drag operations affect
            # the whole group. Users can click empty space to clear the
            # selection if needed.
            if item_already_selected:
                new_selection = [entry for entry in new_selection if entry is not item]
                new_selection.append(item)
            else:
                new_selection = [item]

        self._set_selection(new_selection)
        return item_active and item in self.selected_items

    def _prepare_item_selection(self, item, event=None):
        if self._active_resize_handle_info:
            return False

        if self._graphical_edit_mode_item and self._graphical_edit_mode_item != item:
            self._remove_resize_handles()
            self._graphical_edit_mode_item = None
        elif not self._graphical_edit_mode_item and self._resize_handles:
            self._remove_resize_handles()

        return self._update_selection_state(item, event)

    def _start_drag_selection(self, event, existing_selection=None):
        self._drag_select_start = (event.x, event.y)
        self._drag_select_rect_id = None
        self._drag_select_active = False
        self._drag_select_modifiers = {
            "shift": self._is_shift_pressed(event),
            "ctrl": self._is_ctrl_pressed(event),
        }
        if existing_selection is None:
            existing_selection = list(self.selected_items)
        self._pre_drag_selection = list(existing_selection)

    def _rectangles_overlap(self, a, b):
        if not a or not b:
            return False
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)

    def _collect_items_in_rect(self, x1, y1, x2, y2):
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        rect = (x1, y1, x2, y2)
        items = []
        for item in self.tokens:
            bbox = self._calculate_item_bbox(item)
            if bbox and self._rectangles_overlap(rect, bbox):
                items.append(item)
        return items

    def _merge_drag_selection(self, items_in_rect):
        base = list(self._pre_drag_selection)
        ctrl = self._drag_select_modifiers.get("ctrl")
        shift = self._drag_select_modifiers.get("shift")

        if ctrl:
            selection = [
                existing for existing in base
                if not any(existing is candidate for candidate in items_in_rect)
            ]
            for candidate in items_in_rect:
                if not any(existing is candidate for existing in selection):
                    selection.append(candidate)
            return selection

        if shift:
            selection = list(base)
            for candidate in items_in_rect:
                if not any(existing is candidate for existing in selection):
                    selection.append(candidate)
            return selection

        return list(items_in_rect)

    def _update_drag_selection(self, event):
        if not self._drag_select_start or not getattr(self, "canvas", None):
            return

        start_x, start_y = self._drag_select_start
        dx = event.x - start_x
        dy = event.y - start_y

        if not self._drag_select_active:
            if abs(dx) < 4 and abs(dy) < 4:
                return
            self._drag_select_active = True
            try:
                self._drag_select_rect_id = self.canvas.create_rectangle(
                    start_x,
                    start_y,
                    event.x,
                    event.y,
                    outline="#4DA6FF",
                    dash=(4, 2),
                    width=1,
                    fill="",
                    tags=("drag_selection",),
                )
            except tk.TclError:
                self._drag_select_rect_id = None

        if not self._drag_select_active:
            return

        x1, y1 = min(start_x, event.x), min(start_y, event.y)
        x2, y2 = max(start_x, event.x), max(start_y, event.y)

        if self._drag_select_rect_id:
            try:
                self.canvas.coords(self._drag_select_rect_id, x1, y1, x2, y2)
            except tk.TclError:
                pass

        items_in_rect = self._collect_items_in_rect(x1, y1, x2, y2)
        selection = self._merge_drag_selection(items_in_rect)
        self._set_selection(selection)

    def _cleanup_drag_selection(self):
        if self._drag_select_rect_id and getattr(self, "canvas", None):
            try:
                self.canvas.delete(self._drag_select_rect_id)
            except tk.TclError:
                pass
        self._drag_select_rect_id = None
        self._drag_select_start = None
        self._drag_select_active = False
        self._pre_drag_selection = []
        self._drag_select_modifiers = {"shift": False, "ctrl": False}

    def _finalize_drag_selection(self, event):
        if not self._drag_select_start:
            return False

        handled = self._drag_select_active
        if self._drag_select_active:
            start_x, start_y = self._drag_select_start
            end_x, end_y = event.x, event.y
            items_in_rect = self._collect_items_in_rect(start_x, start_y, end_x, end_y)
            selection = self._merge_drag_selection(items_in_rect)
            self._set_selection(selection)
        else:
            if self._drag_select_modifiers.get("ctrl") or self._drag_select_modifiers.get("shift"):
                self._set_selection(self._pre_drag_selection)
            else:
                self._clear_selection()

        self._cleanup_drag_selection()
        return handled

    def _get_item_category(self, item):
        if not isinstance(item, dict):
            return None
        item_type = item.get("type")
        if item_type in ("rectangle", "oval"):
            return "shape"
        return item_type

    def _ensure_selection_for_context_menu(self, item):
        if not item:
            return False

        if item not in self.selected_items:
            self._set_selection([item])

        return item in self.selected_items

    def _get_selection_icon_image(self, width, height):
        width = max(1, int(width))
        height = max(1, int(height))
        key = (width, height)
        cached = self._selection_icon_cache.get(key)
        if cached:
            return cached, key

        pad = max(12, min(32, int(min(width, height) * 0.25)))
        w = width + pad
        h = height + pad
        min_dim = max(1, min(w, h))
        thickness = max(2, min(5, int(min_dim * 0.05)))
        radius = max(thickness * 2, int(min_dim * 0.18))
        radius = min(radius, min_dim // 2 - 1 if min_dim // 2 > 1 else radius)

        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        inset = thickness // 2 + 1
        rect = (inset, inset, w - inset, h - inset)
        draw.rounded_rectangle(rect, radius=radius, outline=(0, 196, 255, 230), width=thickness)

        dot_radius = max(2, thickness - 1)
        corners = [
            (rect[0], rect[1]),
            (rect[2], rect[1]),
            (rect[2], rect[3]),
            (rect[0], rect[3]),
        ]
        for cx, cy in corners:
            draw.ellipse(
                (cx - dot_radius, cy - dot_radius, cx + dot_radius, cy + dot_radius),
                fill=(0, 196, 255, 255),
            )

        tk_image = ImageTk.PhotoImage(img)
        self._selection_icon_cache[key] = tk_image
        return tk_image, key

    def _calculate_item_bbox(self, item):
        if not item or not getattr(self, "canvas", None):
            return None

        canvas_ids = [cid for cid in (item.get("canvas_ids") or ()) if cid]
        preferred_ids = []

        item_type = item.get("type")
        if item_type == "token" and canvas_ids:
            preferred_ids.append(canvas_ids[0])  # Border rectangle gives a nice bounds
        preferred_ids.extend(canvas_ids)

        if item_type == "token":
            extra = []
            if item.get("hp_canvas_ids"):
                extra.extend([cid for cid in item["hp_canvas_ids"] if cid])
            if item.get("defense_canvas_ids"):
                extra.extend([cid for cid in item["defense_canvas_ids"] if cid])
            if item.get("name_id"):
                extra.append(item.get("name_id"))
            preferred_ids.extend(extra)
        elif item_type == "marker":
            preferred_ids.extend(
                [
                    item.get("border_canvas_id"),
                    item.get("entry_canvas_id"),
                    item.get("handle_canvas_id"),
                ]
            )

        for cid in preferred_ids:
            if not cid:
                continue
            try:
                bbox = self.canvas.bbox(cid)
            except tk.TclError:
                bbox = None
            if bbox:
                return bbox
        return None

    def _remove_selection_overlay(self, item=None, key=None):
        dict_key = key if key is not None else (id(item) if item is not None else None)
        if dict_key is None:
            return
        entry = self._selection_overlays.pop(dict_key, None)
        if entry and getattr(self, "canvas", None):
            try:
                self.canvas.delete(entry.get("canvas_id"))
            except tk.TclError:
                pass

    def _update_selection_indicators(self):
        if not getattr(self, "canvas", None):
            return

        active_ids = {id(item) for item in self.selected_items}
        for key, entry in list(self._selection_overlays.items()):
            item_ref = entry.get("item")
            if id(item_ref) not in active_ids:
                self._remove_selection_overlay(item_ref, key=key)

        for item in self.selected_items:
            bbox = self._calculate_item_bbox(item)
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox
            width = max(1, x2 - x1)
            height = max(1, y2 - y1)
            icon_image, cache_key = self._get_selection_icon_image(width, height)
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            existing = self._selection_overlays.get(id(item))
            if existing:
                canvas_id = existing.get("canvas_id")
                try:
                    self.canvas.coords(canvas_id, cx, cy)
                    if existing.get("cache_key") != cache_key:
                        self.canvas.itemconfig(canvas_id, image=icon_image)
                        existing["cache_key"] = cache_key
                    self.canvas.itemconfig(canvas_id, state="disabled")
                    self.canvas.tag_raise(canvas_id)
                    existing["image"] = icon_image
                except tk.TclError:
                    self._remove_selection_overlay(item)
                else:
                    continue

            try:
                canvas_id = self.canvas.create_image(
                    cx, cy, image=icon_image, state="disabled", tags=("selection_indicator",)
                )
                self.canvas.tag_raise(canvas_id)
            except tk.TclError:
                continue
            self._selection_overlays[id(item)] = {
                "canvas_id": canvas_id,
                "image": icon_image,
                "cache_key": cache_key,
                "item": item,
            }

    def open_map_by_name(self, map_name, *, apply_fit=True):
        target = (map_name or "").strip()
        if not target:
            log_warning(
                "open_map_by_name invoked with an empty map name.",
                func_name="DisplayMapController.open_map_by_name",
            )
            return False
        previous_map_name = ""
        if isinstance(getattr(self, "current_map", None), dict):
            previous_map_name = (self.current_map.get("Name") or "").strip()
        previous_label = previous_map_name or "<none>"
        log_info(
            f"Opening map '{target}' (previous map '{previous_label}').",
            func_name="DisplayMapController.open_map_by_name",
        )
        if target not in self._maps:
            log_warning(
                f"Map '{target}' is not present in the controller cache.",
                func_name="DisplayMapController.open_map_by_name",
            )
            messagebox.showwarning("Not Found", f"Map '{target}' not found.")
            return False
        self._on_display_map("maps", target)
        item_counts = {
            "tokens": sum(1 for entry in getattr(self, "tokens", []) if entry.get("type") == "token"),
            "markers": sum(1 for entry in getattr(self, "tokens", []) if entry.get("type") == "marker"),
            "shapes": sum(1 for entry in getattr(self, "tokens", []) if entry.get("type") in ("rectangle", "oval")),
            "total": len(getattr(self, "tokens", [])),
        }
        log_info(
            f"Map '{target}' loaded with {item_counts['tokens']} tokens, {item_counts['markers']} markers, {item_counts['shapes']} shapes (total {item_counts['total']}).",
            func_name="DisplayMapController.open_map_by_name",
        )
        # Apply fit shortly after map swaps in. Use a deferred call and a few
        # retries to allow geometry to settle so we don't compute a tiny
        # initial zoom based on an undersized canvas.
        if apply_fit:
            try:
                for delay in (30, 120, 300):
                    self.parent.after(delay, lambda: self._apply_fit_mode(defer=True))
            except Exception:
                pass
        return True

    def open_global_search(self, event=None):
        if self.drawing_mode != "token":
            print("Please switch to 'Token' drawing mode to add entities.")
            return
        popup = ctk.CTkToplevel(self.parent)
        popup.title("Search Entities"); popup.geometry("400x300")
        popup.transient(self.parent); popup.grab_set()
        entry = ctk.CTkEntry(popup, placeholder_text="Type to search…")
        entry.pack(fill="x", padx=10, pady=(10,5)); popup.after(10, lambda: entry.focus_force())
        listbox = tk.Listbox(popup, activestyle="none")
        listbox.pack(fill="both", expand=True, padx=10, pady=(0,10))
        search_map = []
        def populate(initial=False, query=""):
            listbox.delete(0, "end"); search_map.clear(); q = query.lower()
            for etype, wrapper in self._model_wrappers.items():
                for item in wrapper.load_items():
                    name = item.get("Name", "")
                    if initial or q in name.lower():
                        listbox.insert("end", f"{etype}: {name}"); search_map.append((etype, name, item))
            if listbox.size() > 0: listbox.selection_clear(0, "end"); listbox.selection_set(0); listbox.activate(0)
        populate(initial=True)
        entry.bind("<KeyRelease>", lambda e: populate(False, entry.get().strip()))
        entry.bind("<Down>", lambda e: (listbox.focus_set(), "break"))
        def on_select(evt=None):
            if not search_map: return
            idx = listbox.curselection()[0]; etype, name, record = search_map[idx]
            portrait = record.get("Portrait", "")
            path = portrait.get("path") or portrait.get("text", "") if isinstance(portrait, dict) else portrait
            self.add_token(path, etype, name, record) # This specifically adds a new token
            popup.destroy()
        entry.bind("<Return>", lambda e: on_select()); listbox.bind("<Return>", lambda e: on_select())
        listbox.bind("<Double-Button-1>", on_select)

    def open_chatbot_assistant(self, event=None):
        try:
            host = self.parent.winfo_toplevel()
        except Exception:
            host = self.parent
        try:
            open_chatbot_dialog(
                host,
                wrappers=self._chatbot_wrappers,
                name_field_overrides=CHATBOT_NAME_OVERRIDES,
            )
        except Exception as exc:
            log_warning(
                f"Failed to launch chatbot: {exc}",
                func_name="DisplayMapController.open_chatbot_assistant",
            )
        return "break" if event else None

    def add_marker(self):
        if not getattr(self, "canvas", None):
            return
        try:
            self.canvas.update_idletasks()
            cw = self.canvas.winfo_width() or 0
            ch = self.canvas.winfo_height() or 0
        except tk.TclError:
            cw = ch = 0
        zoom = self.zoom if self.zoom not in (None, 0) else 1.0
        xw_center = (cw / 2 - self.pan_x) / zoom if zoom else 0
        yw_center = (ch / 2 - self.pan_y) / zoom if zoom else 0

        marker = {
            "type": "marker",
            "position": (xw_center, yw_center),
            "text": "New Marker",
            "description": "Marker description",
            "border_color": "#00ff00",
            "video_path": "",
            "linked_map": "",
            "entry_widget": None,
            "description_popup": None,
            "description_label": None,
            "description_visible": False,
            "entry_width": 180,
            "focus_pending": True,
            "border_canvas_id": None,
        }

        self.tokens.append(marker)
        self._update_canvas_images()
        self._persist_tokens()

    def _on_marker_text_change(self, marker, persist=False):
        entry = marker.get("entry_widget")
        if entry and entry.winfo_exists():
            text = entry.get()
        else:
            text = marker.get("text", "") or ""

        previous_text = marker.get("text", "") or ""
        if previous_text != text:
            marker["text"] = text
            self._update_marker_entry_dimensions(marker, expand=True)
            if persist:
                self._persist_tokens()
        elif persist:
            self._persist_tokens()

    def _on_marker_entry_return(self, event, marker):
        self._on_marker_text_change(marker, persist=True)
        self._show_marker_description(marker)
        return "break"

    def _on_marker_description_change(self, marker, new_text=None, persist=False):
        if not marker:
            return
        if new_text is None:
            new_text = marker.get("description", "")
        new_text = (new_text or "").rstrip()
        if marker.get("description") != new_text:
            marker["description"] = new_text
            if persist:
                self._persist_tokens()
        self._refresh_marker_description_popup(marker)

    def _update_marker_entry_dimensions(self, marker, expand=False):
        entry = marker.get("entry_widget")
        if not entry or not entry.winfo_exists():
            return

        text = marker.get("text", "") or ""
        try:
            font_name = entry.cget("font")
            tk_font = tkfont.nametofont(font_name) if font_name else tkfont.nametofont("TkDefaultFont")
            measured = tk_font.measure(text or " ")
        except Exception:
            measured = max(6 * max(len(text), 1), 20)

        base_width = max(40, min(measured + 24, 480))
        expanded_width = max(base_width, min(measured + 80, 700))

        marker["entry_width"] = base_width
        marker["entry_expanded_width"] = expanded_width

        entry.configure(width=base_width)
        if expand and expanded_width > base_width:
            entry.configure(width=expanded_width)

        self._refresh_marker_description_popup(marker)

    def _expand_marker_entry(self, marker):
        self._update_marker_entry_dimensions(marker, expand=True)

    def _collapse_marker_entry(self, marker):
        entry = marker.get("entry_widget")
        base = marker.get("entry_width")
        if entry and entry.winfo_exists() and base:
            entry.configure(width=base)
        self._refresh_marker_description_popup(marker)

    def _on_marker_entry_focus_in(self, marker):
        self._refresh_marker_description_popup(marker)

    def _on_marker_entry_focus_out(self, marker):
        self._on_marker_text_change(marker, persist=True)
        self._collapse_marker_entry(marker)

    def _on_marker_entry_press(self, event, marker):
        item_active = self._prepare_item_selection(marker, event)
        if not item_active:
            marker.pop("drag_data", None)

    def _on_marker_entry_click(self, event, marker):
        marker.pop("drag_data", None)
        widget = getattr(event, "widget", None)
        already_focused = widget is not None and widget.focus_get() is widget
        if marker.get("description_visible") and already_focused:
            return
        self._handle_item_click(event, marker)

    def _show_marker_description(self, marker):
        canvas = getattr(self, "canvas", None)
        if not canvas:
            return
        popup = self._ensure_marker_description_popup(marker)
        if not popup:
            return
        self._hide_all_token_hovers()
        self._hide_other_marker_descriptions(marker)
        self._refresh_marker_description_popup(marker)
        popup.deiconify()
        popup.lift()
        marker["description_visible"] = True
        self._hovered_marker = marker

    def _hide_marker_description(self, marker):
        canvas = getattr(self, "canvas", None)
        popup = marker.get("description_popup")
        marker["description_visible"] = False
        if popup and popup.winfo_exists():
            popup.withdraw()
        if getattr(self, "_hovered_marker", None) is marker:
            self._hovered_marker = None

    def _hide_all_marker_descriptions(self):
        for item in getattr(self, "tokens", []):
            if isinstance(item, dict) and item.get("type") == "marker":
                self._hide_marker_description(item)

    def _hide_other_marker_descriptions(self, active_marker):
        for item in getattr(self, "tokens", []):
            if item is active_marker:
                continue
            if isinstance(item, dict) and item.get("type") == "marker" and item.get("description_visible"):
                self._hide_marker_description(item)

    def _hide_all_token_hovers(self):
        for token in getattr(self, "tokens", []):
            if isinstance(token, dict) and token.get("hover_visible"):
                self._hide_token_hover(token)

    def _hide_other_token_hovers(self, active_token):
        for token in getattr(self, "tokens", []):
            if token is active_token:
                continue
            if isinstance(token, dict) and token.get("hover_visible"):
                self._hide_token_hover(token)

    def _on_canvas_focus_out(self, event=None):
        """Hide hover windows when the canvas loses focus, unless the focus
        moved inside one of the hover popups."""

        if getattr(self, "_hover_auto_hide_suppressed", 0):
            return

        canvas = getattr(self, "canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return

        def _collect_focus_candidates():
            candidates = []

            if event is not None:
                related = getattr(event, "related_widget", None)
                if related is not None:
                    candidates.append(related)

                widget = getattr(event, "widget", None)
                if widget is not None:
                    try:
                        focus_widget = widget.focus_get()
                    except Exception:
                        focus_widget = None
                    else:
                        if focus_widget is not None:
                            candidates.append(focus_widget)

            try:
                focus_widget = canvas.focus_get()
            except Exception:
                focus_widget = None
            else:
                if focus_widget is not None:
                    candidates.append(focus_widget)

            pointer_coords = None
            try:
                pointer_coords = canvas.winfo_pointerxy()
                pointer_widget = canvas.winfo_containing(*pointer_coords)
            except tk.TclError:
                pointer_widget = None
            if pointer_widget is not None:
                candidates.append(pointer_widget)

            # Ensure widgets that currently have focus within any active hover
            # popup windows are considered.  Some CustomTkinter widgets don't
            # consistently show up via ``focus_get`` on the canvas or via
            # ``winfo_containing`` queries, which previously caused the token
            # info window to be dismissed when clicking inline dice buttons.
            popups = getattr(self, "_active_hover_popups", set())
            for popup in list(popups):
                try:
                    focus_widget = popup.focus_get()
                except Exception:
                    focus_widget = None
                if focus_widget is not None:
                    candidates.append(focus_widget)

                if pointer_coords is not None:
                    try:
                        popup_pointer_widget = popup.winfo_containing(*pointer_coords)
                    except tk.TclError:
                        popup_pointer_widget = None
                    else:
                        if popup_pointer_widget is not None:
                            candidates.append(popup_pointer_widget)

            return candidates

        def _evaluate_focus_change():
            candidates = _collect_focus_candidates()
            if any(self._widget_is_within_hover_popup(widget) for widget in candidates if widget is not None):
                return

            self._hide_all_marker_descriptions()
            self._hide_all_token_hovers()

        try:
            canvas.after_idle(_evaluate_focus_change)
        except tk.TclError:
            _evaluate_focus_change()

    def _widget_is_within_hover_popup(self, widget) -> bool:
        """Return True if *widget* is a descendant of any registered hover popup."""

        if widget is None:
            return False

        popups = getattr(self, "_active_hover_popups", set())

        # ``winfo_toplevel`` is a more robust way to identify the parent window
        # for CustomTkinter widgets.  Some of the custom widgets used in the
        # token info window do not expose a traditional ``master`` chain (or it
        # temporarily becomes ``None`` during click handling), which caused the
        # hover popup to be treated as "outside" the active popup when its
        # buttons were pressed.  Checking the toplevel first ensures we still
        # recognise those widgets as part of the popup even if traversing the
        # ``master`` chain fails.
        try:
            toplevel = widget.winfo_toplevel()
        except Exception:
            toplevel = None
        else:
            if toplevel in popups:
                return True

        visited = set()
        current = widget

        while current is not None and current not in visited:
            visited.add(current)
            if current in popups:
                return True
            current = getattr(current, "master", None)

        return False

    def clear_hover_windows(self):
        """Hide all token and marker info popups."""
        self._hide_all_token_hovers()
        self._hide_all_marker_descriptions()
        # Explicitly withdraw any hover popup windows that may not be linked to
        # a currently tracked token (for example, if a token was deleted while its
        # info card remained). This guarantees that pressing the toolbar button
        # truly clears every hover window from the screen.
        for popup in list(self._active_hover_popups):
            try:
                exists = popup.winfo_exists()
            except tk.TclError:
                exists = False
            if exists:
                popup.withdraw()

    def _on_application_focus_out(self, event=None):
        if getattr(self, "_hover_auto_hide_suppressed", 0):
            return
        self._hide_all_marker_descriptions()
        self._hide_all_token_hovers()

    def _show_marker_menu(self, event, markers):
        valid_markers = [m for m in markers if isinstance(m, dict) and m.get("type") == "marker"]
        if not valid_markers:
            return

        if len(valid_markers) == 1:
            self._hovered_marker = valid_markers[0]
        else:
            self._hovered_marker = None

        menu = tk.Menu(self.canvas, tearoff=0)
        single_marker = valid_markers[0] if len(valid_markers) == 1 else None

        if single_marker:
            linked_name = (single_marker.get("linked_map") or "").strip()
            menu.add_command(
                label="Open Linked Map",
                command=lambda: self._open_marker_linked_map(single_marker),
                state=tk.NORMAL if linked_name else tk.DISABLED,
            )
            menu.add_command(
                label="Set Linked Map...",
                command=lambda: self._choose_marker_linked_map(single_marker),
            )
            menu.add_command(
                label="Clear Linked Map",
                command=lambda: self._clear_marker_link(single_marker),
                state=tk.NORMAL if linked_name else tk.DISABLED,
            )
            menu.add_separator()

            menu.add_command(
                label="Edit Description",
                command=lambda: self._open_marker_description_editor(single_marker),
            )

        plural = "s" if len(valid_markers) != 1 else ""
        menu.add_command(
            label=f"Change Border Color{plural}",
            command=lambda: self._change_markers_border_color(valid_markers),
        )

        menu.add_separator()
        menu.add_command(
            label="Attach Video...",
            command=lambda: self._attach_video_to_markers(valid_markers),
        )

        if single_marker:
            has_video = bool(single_marker.get("video_path"))
            menu.add_command(
                label="Play Video on Second Screen",
                command=lambda: self._play_marker_video(single_marker),
                state=tk.NORMAL if has_video else tk.DISABLED,
            )

        has_any_video = any((marker.get("video_path") for marker in valid_markers))
        menu.add_command(
            label=f"Clear Attached Video{plural}",
            command=lambda: self._clear_marker_videos(valid_markers),
            state=tk.NORMAL if has_any_video else tk.DISABLED,
        )

        menu.add_separator()
        menu.add_command(
            label=f"Delete Marker{plural}",
            command=lambda: self._delete_items(valid_markers),
        )

        menu.tk_popup(event.x_root, event.y_root)
        try:
            menu.grab_release()
        except tk.TclError:
            pass

    def _open_marker_linked_map(self, marker, silent=False):
        if not marker or marker.get("type") != "marker":
            return False
        target = (marker.get("linked_map") or "").strip()
        current_map_name = ""
        if isinstance(getattr(self, "current_map", None), dict):
            current_map_name = (self.current_map.get("Name") or "").strip()
        marker_label = (marker.get("text") or marker.get("entity_id") or "").strip() or f"marker@{id(marker):x}"
        marker_position = marker.get("position")
        current_map_label = current_map_name or "<unknown>"
        target_label = target or "<empty>"
        marker_debug_data = {key: marker.get(key) for key in ("linked_map", "border_color", "entry_width")}
        log_info(
            f"Marker '{marker_label}' on map '{current_map_label}' requested linked map '{target_label}'.",
            func_name="DisplayMapController._open_marker_linked_map",
        )
        log_debug(
            f"Marker state before linked map open: position={marker_position}, data={marker_debug_data}.",
            func_name="DisplayMapController._open_marker_linked_map",
        )
        if not target:
            if not silent:
                messagebox.showinfo("Linked Map", "No linked map is assigned to this marker.")
            log_warning(
                f"Marker '{marker_label}' does not have a linked map configured.",
                func_name="DisplayMapController._open_marker_linked_map",
            )
            return False
        success = self.open_map_by_name(target, apply_fit=False)
        log_info(
            f"Linked map open {'succeeded' if success else 'failed'} for marker '{marker_label}' (target '{target_label}').",
            func_name="DisplayMapController._open_marker_linked_map",
        )
        return success

    def _choose_marker_linked_map(self, marker):
        if not marker or marker.get("type") != "marker":
            return
        map_names = sorted(self._maps.keys(), key=lambda name: name.lower())
        if not map_names:
            messagebox.showinfo("Linked Map", "There are no maps available to link.")
            return

        dialog = ctk.CTkToplevel(self.parent)
        dialog.title("Select Linked Map")
        dialog.geometry("320x400")
        dialog.transient(self.parent)
        dialog.grab_set()

        container = ctk.CTkFrame(dialog)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(container, text="Choose a map to link to this marker:").pack(anchor="w")

        search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(container, textvariable=search_var, placeholder_text="Search maps...")
        search_entry.pack(fill="x", pady=(6, 8))

        listbox = tk.Listbox(container, activestyle="none")
        listbox.pack(fill="both", expand=True)

        button_row = ctk.CTkFrame(container)
        button_row.pack(fill="x", pady=(10, 0))

        result = {"value": None}
        filtered_names = []

        def refresh_list():
            query = (search_var.get() or "").strip().lower()
            filtered_names.clear()
            for name in map_names:
                if not query or query in name.lower():
                    filtered_names.append(name)
            listbox.delete(0, tk.END)
            for idx, name in enumerate(filtered_names):
                listbox.insert(tk.END, name)
            current = (marker.get("linked_map") or "").strip()
            if current and current in filtered_names:
                pos = filtered_names.index(current)
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(pos)
                listbox.activate(pos)

        def on_confirm(event=None):
            if not filtered_names:
                return
            try:
                selection = listbox.curselection()
                if not selection:
                    return
                idx = selection[0]
            except tk.TclError:
                return
            result["value"] = filtered_names[idx]
            dialog.destroy()

        def on_clear():
            result["value"] = "__CLEAR__"
            dialog.destroy()

        def on_cancel():
            result["value"] = None
            dialog.destroy()

        link_button = ctk.CTkButton(button_row, text="Link Map", command=on_confirm)
        link_button.pack(side="left")
        has_link = bool((marker.get("linked_map") or "").strip())
        clear_button = ctk.CTkButton(
            button_row,
            text="Clear Link",
            command=on_clear,
            state=tk.NORMAL if has_link else tk.DISABLED,
        )
        clear_button.pack(side="left", padx=6)
        cancel_button = ctk.CTkButton(button_row, text="Cancel", command=on_cancel)
        cancel_button.pack(side="right")

        listbox.bind("<Double-Button-1>", on_confirm)
        search_var.trace_add("write", lambda *args: refresh_list())

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.after(10, search_entry.focus_set)
        refresh_list()
        dialog.wait_window()

        choice = result.get("value")
        if choice == "__CLEAR__":
            self._clear_marker_link(marker)
        elif isinstance(choice, str) and choice:
            marker["linked_map"] = choice
            self._persist_tokens()

    def _clear_marker_link(self, marker):
        if not marker or marker.get("type") != "marker":
            return
        if marker.get("linked_map"):
            marker["linked_map"] = ""
            self._persist_tokens()

    def _change_markers_border_color(self, markers):
        valid_markers = [m for m in markers if isinstance(m, dict) and m.get("type") == "marker"]
        if not valid_markers:
            return
        current_color = valid_markers[0].get("border_color", "#00ff00")
        result = colorchooser.askcolor(
            parent=self.canvas,
            color=current_color,
            title="Choose Marker Border Color",
        )
        if result and result[1]:
            for marker in valid_markers:
                marker["border_color"] = result[1]
            self._update_canvas_images()
            self._persist_tokens()

    def _change_marker_border_color(self, marker):
        if not marker:
            return
        self._change_markers_border_color([marker])

    def _attach_video_to_markers(self, markers):
        valid_markers = [m for m in markers if isinstance(m, dict) and m.get("type") == "marker"]
        if not valid_markers:
            return

        try:
            campaign_dir = ConfigHelper.get_campaign_dir()
        except Exception:
            campaign_dir = None

        initial_dir = campaign_dir if campaign_dir and os.path.isdir(campaign_dir) else os.path.expanduser("~")

        filetypes = [
            ("Video Files", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"),
            ("All Files", "*.*"),
        ]

        selected = filedialog.askopenfilename(
            parent=getattr(self, "canvas", None),
            title="Select Video File",
            filetypes=filetypes,
            initialdir=initial_dir,
        )

        if not selected:
            return

        resolved_path = _resolve_campaign_path(selected)
        if not resolved_path or not os.path.exists(resolved_path):
            messagebox.showerror("Marker Video", f"Unable to locate the selected video file:\n{selected}")
            return

        storage_path = _campaign_relative_path(resolved_path)
        for marker in valid_markers:
            marker["video_path"] = storage_path

        self._persist_tokens()

    def _clear_marker_videos(self, markers):
        changed = False
        for marker in markers:
            if isinstance(marker, dict) and marker.get("type") == "marker" and marker.get("video_path"):
                marker["video_path"] = ""
                changed = True
        if changed:
            self._persist_tokens()

    def _play_marker_video(self, marker):
        if not marker or marker.get("type") != "marker":
            return

        video_value = marker.get("video_path") or ""
        if not video_value:
            messagebox.showinfo("Marker Video", "No video is attached to this marker.")
            return

        resolved_path = _resolve_campaign_path(video_value)
        if not resolved_path or not os.path.exists(resolved_path):
            messagebox.showerror("Marker Video", f"The attached video could not be found:\n{resolved_path or video_value}")
            return

        title = marker.get("text") or "Marker Video"
        try:
            play_video_on_second_screen(resolved_path, title=title)
        except Exception as exc:
            messagebox.showerror("Marker Video", f"Unable to play the video:\n{exc}")

    def _edit_marker_description(self, marker):
        self._open_marker_description_editor(marker)

    def _ensure_marker_description_popup(self, marker):
        if not marker:
            return None
        popup = marker.get("description_popup")
        label = marker.get("description_label")
        if popup and popup.winfo_exists() and label and label.winfo_exists():
            return popup
        if popup and popup.winfo_exists():
            popup.destroy()
        canvas = getattr(self, "canvas", None)
        if not canvas:
            return None
        toplevel = ctk.CTkToplevel(canvas)
        toplevel.withdraw()
        toplevel.overrideredirect(True)
        try:
            toplevel.transient(canvas.winfo_toplevel())
        except tk.TclError:
            pass
        try:
            toplevel.attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = ctk.CTkFrame(toplevel, corner_radius=8, fg_color="#1f1f1f")
        frame.pack(fill="both", expand=True)
        text_label = ctk.CTkLabel(
            frame,
            text="",
            justify="left",
            anchor="w",
            font=getattr(self, "hover_font", None)
        )
        text_label.pack(fill="both", expand=True, padx=12, pady=10)
        def _on_description_double_click(event, m=marker):
            self._open_marker_description_editor(m)
            return "break"

        text_label.bind("<Double-Button-1>", _on_description_double_click)
        frame.bind("<Double-Button-1>", _on_description_double_click)
        self._register_hover_popup(toplevel)
        marker["description_popup"] = toplevel
        marker["description_label"] = text_label
        return toplevel

    def _refresh_marker_description_popup(self, marker):
        popup = marker.get("description_popup")
        label = marker.get("description_label")
        canvas = getattr(self, "canvas", None)
        if not canvas or not popup or not popup.winfo_exists() or not label or not label.winfo_exists():
            return
        description_text = marker.get("description", "").strip()
        if not description_text:
            description_text = "(No description)"
        label.configure(
            text=description_text,
            justify="left",
            anchor="w",
            wraplength=600,
            font=getattr(self, "hover_font", None)
        )
        try:
            popup.update_idletasks()
        except tk.TclError:
            return
        width = max(label.winfo_reqwidth() + 20, 140)
        height = max(label.winfo_reqheight() + 16, 60)
        entry_id = marker.get("entry_canvas_id")
        sx = sy = None
        if entry_id:
            try:
                coords = canvas.coords(entry_id)
            except tk.TclError:
                coords = None
            if coords:
                sx, sy = coords[0], coords[1]
        if sx is None or sy is None:
            xw, yw = marker.get("position", (0, 0))
            sx = int(xw * self.zoom + self.pan_x)
            sy = int(yw * self.zoom + self.pan_y)
        entry_widget = marker.get("entry_widget")
        entry_height = 0
        if entry_widget and entry_widget.winfo_exists():
            try:
                entry_height = entry_widget.winfo_height()
            except tk.TclError:
                entry_height = entry_widget.winfo_reqheight()
        if not entry_height:
            entry_height = 28
        screen_x = canvas.winfo_rootx() + int(sx)
        screen_y = canvas.winfo_rooty() + int(sy) + int(entry_height) + 6
        popup.geometry(f"{int(width)}x{int(height)}+{screen_x}+{screen_y}")

    def _on_hover_font_size_change(self, value):
        try:
            size = int(value)
        except (TypeError, ValueError):
            return
        if size <= 0:
            return
        self.hover_font_size = size
        if size not in self.hover_font_size_options:
            self.hover_font_size_options.append(size)
            self.hover_font_size_options = sorted(set(self.hover_font_size_options))
        hover_font = getattr(self, "hover_font", None)
        if hover_font is None:
            self.hover_font = ctk.CTkFont(size=size)
            hover_font = self.hover_font
        else:
            try:
                hover_font.configure(size=size)
            except Exception:
                self.hover_font = ctk.CTkFont(size=size)
                hover_font = self.hover_font

        for item in getattr(self, "tokens", []):
            if not isinstance(item, dict):
                continue
            label = item.get("hover_label")
            if label and label.winfo_exists():
                try:
                    label.configure(font=hover_font)
                    self._refresh_token_hover_popup(item)
                except tk.TclError:
                    pass
            if item.get("type") == "marker":
                desc_label = item.get("description_label")
                if desc_label and desc_label.winfo_exists():
                    try:
                        desc_label.configure(font=hover_font)
                        self._refresh_marker_description_popup(item)
                    except tk.TclError:
                        pass

        if hasattr(self, "hover_font_size_menu"):
            try:
                values = [str(v) for v in self.hover_font_size_options]
                self.hover_font_size_menu.configure(values=values)
                self.hover_font_size_menu.set(str(size))
            except tk.TclError:
                pass

        if isinstance(getattr(self, "current_map", None), dict):
            self.current_map["hover_font_size"] = size
        try:
            self.maps.save_items(list(self._maps.values()))
        except Exception as exc:
            print(f"[hover_font_size] Failed to persist hover font size: {exc}")

    @staticmethod
    def _extract_longtext_text(value):
        if isinstance(value, dict):
            return str(value.get("text", "") or "")
        if value is None:
            return ""
        return str(value)

    def _resolve_dice_bar_window(self) -> "DiceBarWindow | None":
        candidates: list[object] = []
        seen: set[object] = set()

        def _register_candidate(obj):
            if obj is None or obj in seen:
                return
            seen.add(obj)
            candidates.append(obj)

        def _register_widget_chain(widget):
            current = widget
            while current is not None and current not in seen:
                _register_candidate(current)
                current = getattr(current, "master", None)

        root_app = getattr(self, "_root_app", None)
        if root_app is not None:
            _register_widget_chain(root_app)

        parent = getattr(self, "parent", None)
        if parent is not None:
            _register_widget_chain(parent)
            try:
                toplevel = parent.winfo_toplevel()
            except Exception:
                toplevel = None
            else:
                _register_widget_chain(toplevel)
        else:
            toplevel = None

        if toplevel is not None:
            main_app = getattr(toplevel, "master", None)
            if main_app is not None:
                _register_widget_chain(main_app)

        for candidate in candidates:
            open_method = getattr(candidate, "open_dice_bar", None)
            if callable(open_method):
                try:
                    open_method()
                except Exception as exc:
                    log_warning(
                        f"Unable to open dice bar window: {exc}",
                        func_name="DisplayMapController._resolve_dice_bar_window",
                    )

            window = getattr(candidate, "dice_bar_window", None)
            if window is not None and window.winfo_exists():
                return window

        return None

    def _get_token_hover_text(self, token):
        record = token.get("entity_record") or {}
        entity_type = token.get("entity_type")

        defense_label = str(token.get("defense_label") or "").strip()
        defense_value = token.get("defense_value")
        if defense_value is None:
            defense_info = _extract_entity_defense_value(entity_type, record)
            if defense_info:
                defense_label, defense_value = defense_info
                token["defense_label"] = defense_label
                token["defense_value"] = defense_value

        raw_stats_value = ""
        if entity_type in ("Creature", "PC"):
            raw_stats_value = record.get("Stats", "")
        elif entity_type == "NPC":
            raw_stats_value = record.get("Traits", "")

        plain_text = self._extract_longtext_text(raw_stats_value)
        cleaned_text, actions, errors = parse_inline_actions(plain_text)
        print(
            "[DEBUG] _get_token_hover_text: parse_inline_actions returned"
            f" {len(actions)} actions and {len(errors)} errors for token"
            f" '{token.get('entity_id', 'Unknown')}'"
        )

        token["_inline_markup_source"] = plain_text
        token["_inline_markup_display"] = cleaned_text or plain_text
        token["parsed_actions"] = actions
        token["action_errors"] = errors
        token["maptools_macros"] = build_token_macros(actions, token_name=token.get("entity_id"))

        display_source = token.get("_inline_markup_display", plain_text)
        display_stats_text = format_longtext(display_source)
        if isinstance(display_stats_text, (list, tuple)):
            display_stats_text = "\n".join(map(str, display_stats_text))
        else:
            display_stats_text = str(display_stats_text or "")
        if not display_stats_text.strip():
            display_stats_text = "(No details available)"

        if defense_value is not None:
            label = defense_label or "Defense"
            header_line = f"{label}: {defense_value}"
            if display_stats_text:
                display_stats_text = f"{header_line}\n\n{display_stats_text}"
            else:
                display_stats_text = header_line
        return display_stats_text

    @staticmethod
    def _format_action_header(action: dict) -> str:
        if not isinstance(action, dict):
            return "Action"
        label = str(action.get("label") or "Action")
        notes = str(action.get("notes") or "").strip()
        if notes:
            return f"{label} [{notes}]"
        return label

    @staticmethod
    def _format_attack_button_text(action: dict) -> str:
        formula = str(action.get("attack_roll_formula") or "").strip()
        if not formula:
            bonus = str(action.get("attack_bonus") or "").strip()
            return f"Attack {bonus}" if bonus else "Attack"
        return f"Attack ({formula})"

    @staticmethod
    def _format_damage_button_text(action: dict) -> str:
        formula = str(action.get("damage_formula") or "").strip()
        if not formula:
            return "Damage"
        notes = str(action.get("notes") or "").strip()
        if notes:
            return f"Damage ({formula} {notes})"
        return f"Damage ({formula})"

    def _execute_token_hover_action(self, token: dict, action: dict, roll_type: str) -> None:
        """Run a token hover action while temporarily suppressing auto-hide logic."""
        self._hover_auto_hide_suppressed = getattr(self, "_hover_auto_hide_suppressed", 0) + 1

        def _release_suppression():
            current = getattr(self, "_hover_auto_hide_suppressed", 0)
            if current > 0:
                self._hover_auto_hide_suppressed = current - 1

        try:
            self._roll_token_action(token, action, roll_type)
        finally:
            canvas = getattr(self, "canvas", None)
            if canvas and canvas.winfo_exists():
                try:
                    canvas.after_idle(_release_suppression)
                    return
                except tk.TclError:
                    pass
                except Exception:
                    pass
            _release_suppression()

    def _roll_token_action(self, token: dict, action: dict, roll_type: str) -> None:
        if not isinstance(action, dict):
            return

        was_visible = bool(token.get("hover_visible"))

        def _restore_hover():
            if was_visible:
                try:
                    self._show_token_hover(token)
                except Exception:
                    pass

        base_label = str(action.get("label") or "Action")
        display_label = base_label
        notes = str(action.get("notes") or "").strip()

        descriptor: str
        descriptor_with_notes: str

        if roll_type == "difficulty":
            difficulty_info = action.get("_difficulty") or {}
            formula = str(difficulty_info.get("formula") or "").strip()
            difficulty_label = str(difficulty_info.get("label") or "").strip()
            descriptor_base = str(difficulty_info.get("descriptor") or "Difficulty").strip() or "Difficulty"
            difficulty_notes = str(difficulty_info.get("notes") or "").strip()
            if difficulty_notes:
                notes = difficulty_notes
            descriptor_with_notes = descriptor_base
            if difficulty_label:
                if base_label:
                    display_label = f"{base_label} – {difficulty_label}"
                else:
                    display_label = difficulty_label
                if difficulty_label.lower() not in descriptor_base.lower():
                    descriptor_with_notes = f"{descriptor_base} ({difficulty_label})"
            if notes:
                descriptor_with_notes = f"{descriptor_with_notes} ({notes})"
            descriptor = descriptor_base
        else:
            roll_key = "attack_roll_formula" if roll_type == "attack" else "damage_formula"
            formula = str(action.get(roll_key) or "").strip()
            descriptor = "Attack" if roll_type == "attack" else "Damage"
            descriptor_with_notes = descriptor
            if roll_type == "damage" and notes:
                descriptor_with_notes = f"{descriptor} ({notes})"

        def _register_formula_candidate(value: str, *, fallback: bool, container: list[tuple[str, bool]]) -> None:
            text = str(value or "").strip()
            if not text:
                return
            canonical = dice_preferences.canonicalize_formula(text)
            normalized = canonical or text
            if not normalized:
                return
            if not any(existing == normalized for existing, _ in container):
                container.append((normalized, fallback))

        candidate_formulas: list[tuple[str, bool]] = []
        _register_formula_candidate(formula, fallback=False, container=candidate_formulas)

        base_formula = formula

        if roll_type == "attack":
            attack_bonus_text = str(action.get("attack_bonus") or "").strip()
            if attack_bonus_text:
                fallback_formula = dice_preferences.make_attack_roll_formula(attack_bonus_text)
                # Always treat formulas derived from the attack bonus as a fallback option.
                _register_formula_candidate(fallback_formula, fallback=True, container=candidate_formulas)

        if not candidate_formulas:
            try:
                messagebox.showinfo(
                    "Dice Roll",
                    f"No {descriptor.lower()} formula configured for {display_label}.",
                )
            finally:
                _restore_hover()
            return

        dice_window = self._resolve_dice_bar_window()
        explode = False
        separate = False
        if dice_window is not None:
            try:
                explode = bool(dice_window.exploding_var.get())
            except Exception:
                explode = False
            try:
                separate = bool(dice_window.separate_var.get())
            except Exception:
                separate = False

        supported_faces = dice_preferences.get_supported_faces()
        TextSegmentCls = None
        if dice_window is not None:
            try:
                from modules.dice.dice_bar_window import TextSegment
            except Exception:
                TextSegmentCls = None
            else:
                TextSegmentCls = TextSegment

        result = None
        used_formula = None
        used_fallback = False
        last_error: dice_engine.DiceEngineError | None = None

        for candidate, is_fallback in candidate_formulas:
            try:
                attempt = dice_engine.roll_formula(
                    candidate,
                    explode=explode,
                    supported_faces=supported_faces,
                )
            except dice_engine.DiceEngineError as exc:
                last_error = exc
                continue

            result = attempt
            used_formula = candidate
            used_fallback = is_fallback
            break

        if result is None or used_formula is None:
            error_message = last_error or dice_engine.FormulaError("Unable to parse roll formula.")
            try:
                messagebox.showerror("Dice Roll Failed", f"{display_label}: {error_message}")
            finally:
                _restore_hover()
            return

        formula = used_formula

        if roll_type == "difficulty":
            difficulty_info["formula"] = formula
        elif roll_type in {"attack", "damage"}:
            roll_key = "attack_roll_formula" if roll_type == "attack" else "damage_formula"
            try:
                action[roll_key] = formula
            except Exception:
                pass

        if used_fallback and base_formula and formula != base_formula:
            log_warning(
                f"Rolled fallback formula '{formula}' for {display_label}; stored formula '{base_formula}' failed.",
                func_name="DisplayMapController._roll_token_action",
            )
        elif used_fallback and not base_formula:
            log_warning(
                f"Derived roll formula '{formula}' for {display_label} from attack bonus.",
                func_name="DisplayMapController._roll_token_action",
            )

        try:
            if dice_window is not None and TextSegmentCls is not None:
                try:
                    formatted = dice_window._format_roll_output(result, separate)
                    prefix = TextSegmentCls(f"{display_label} – {descriptor_with_notes}: ")
                    dice_window.formula_var.set(result.canonical())
                    dice_window._display_segments(
                        [prefix, *formatted.segments],
                        header=formatted.header,
                        chips=formatted.chips,
                    )
                    dice_window._set_total_text(formatted.total_text)
                    dice_window.show()
                    return
                except Exception as exc:
                    log_warning(
                        f"Failed to display roll in dice bar: {exc}",
                        func_name="DisplayMapController._roll_token_action",
                    )

            summary = self._format_roll_summary(descriptor_with_notes, formula, result)
            messagebox.showinfo("Dice Roll", f"{display_label}\n{summary}")
        finally:
            _restore_hover()

    @staticmethod
    def _format_roll_summary(kind: str, formula: str, result) -> str:
        parts: list[str] = []
        for summary in getattr(result, "face_summaries", () ):
            values = getattr(summary, "display_values", ())
            base_count = getattr(summary, "base_count", 0)
            faces = getattr(summary, "faces", None)
            if not values or faces is None:
                continue
            parts.append(f"{base_count}d{faces}[{', '.join(values)}]")
        modifier = getattr(result, "modifier", 0)
        if modifier:
            parts.append(f"{modifier:+d}")
        breakdown = " + ".join(parts)
        if breakdown:
            return f"{kind}: {formula} = {result.total} ({breakdown})"
        return f"{kind}: {formula} = {result.total}"

    def _ensure_token_hover_popup(self, token):
        popup = token.get("hover_popup")
        label = token.get("hover_label")
        frame = token.get("hover_frame")
        links_frame = token.get("hover_links_frame")
        actions_frame = token.get("hover_actions_frame")
        canvas = getattr(self, "canvas", None)
        if popup and popup.winfo_exists() and label and label.winfo_exists():
            if not frame or not frame.winfo_exists():
                frame = label.master
                if frame and frame.winfo_exists():
                    token["hover_frame"] = frame
            if frame and frame.winfo_exists():
                if not links_frame or not links_frame.winfo_exists():
                    links_frame = ctk.CTkFrame(frame, fg_color="transparent")
                    token["hover_links_frame"] = links_frame
                if not actions_frame or not actions_frame.winfo_exists():
                    actions_frame = ctk.CTkFrame(frame, fg_color="transparent")
                    token["hover_actions_frame"] = actions_frame
            return popup
        if popup and popup.winfo_exists():
            popup.destroy()
        if not canvas:
            return None
        popup = ctk.CTkToplevel(canvas)
        popup.withdraw()
        popup.overrideredirect(True)
        try:
            popup.transient(canvas.winfo_toplevel())
        except tk.TclError:
            pass
        try:
            popup.attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = ctk.CTkFrame(popup, corner_radius=8, fg_color="#1f1f1f")
        frame.pack(fill="both", expand=True)
        label = ctk.CTkLabel(
            frame,
            text="",
            justify="left",
            anchor="w",
            font=getattr(self, "hover_font", None)
        )
        label.pack(fill="both", expand=True, padx=12, pady=10)
        links_frame = ctk.CTkFrame(frame, fg_color="transparent")
        actions_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._register_hover_popup(popup)
        token["hover_popup"] = popup
        token["hover_label"] = label
        token["hover_frame"] = frame
        token["hover_links_frame"] = links_frame
        token["hover_actions_frame"] = actions_frame
        return popup

    def _register_hover_popup(self, popup):
        """Keep a reference to created hover popups for global dismissal."""
        if popup in self._active_hover_popups:
            return

        self._active_hover_popups.add(popup)

        def _on_destroy(event, pop=popup):
            self._active_hover_popups.discard(pop)

        popup.bind("<Destroy>", _on_destroy, add="+")

    def _refresh_token_hover_popup(self, token):
        popup = token.get("hover_popup")
        label = token.get("hover_label")
        canvas = getattr(self, "canvas", None)
        if not canvas or not popup or not popup.winfo_exists() or not label or not label.winfo_exists():
            return
        display_text = self._get_token_hover_text(token)
        label.configure(
            text=display_text,
            justify="left",
            anchor="w",
            wraplength=400,
            font=getattr(self, "hover_font", None)
        )

        self._populate_token_links(token, display_text)

        actions = token.get("parsed_actions") or []
        errors = token.get("action_errors") or []
        actions_frame = token.get("hover_actions_frame")
        if actions_frame and actions_frame.winfo_exists():
            for child in list(actions_frame.winfo_children()):
                try:
                    child.destroy()
                except tk.TclError:
                    pass

            if actions or errors:
                if not actions_frame.winfo_ismapped():
                    actions_frame.pack(fill="x", padx=12, pady=(0, 10))

                if actions:
                    header_font = ctk.CTkFont(size=max(12, self.hover_font_size - 1), weight="bold")
                    ctk.CTkLabel(actions_frame, text="Actions", anchor="w", font=header_font).pack(anchor="w", pady=(0, 6))
                    for action in actions:
                        action_container = ctk.CTkFrame(actions_frame, fg_color="transparent")
                        action_container.pack(fill="x", pady=(0, 6))

                        title = self._format_action_header(action)
                        ctk.CTkLabel(
                            action_container,
                            text=title,
                            anchor="w",
                            justify="left",
                        ).pack(anchor="w")

                        buttons_row = ctk.CTkFrame(action_container, fg_color="transparent")
                        buttons_row.pack(fill="x", pady=(4, 0))

                        attack_formula = str(action.get("attack_roll_formula") or "").strip()
                        damage_formula = str(action.get("damage_formula") or "").strip()

                        buttons_added = False
                        if attack_formula:
                            attack_text = self._format_attack_button_text(action)
                            ctk.CTkButton(
                                buttons_row,
                                text=attack_text,
                                command=lambda a=action: self._execute_token_hover_action(token, a, "attack"),
                                width=0,
                            ).pack(side="left", padx=(0, 6))
                            buttons_added = True

                        if damage_formula:
                            damage_text = self._format_damage_button_text(action)
                            ctk.CTkButton(
                                buttons_row,
                                text=damage_text,
                                command=lambda a=action: self._execute_token_hover_action(token, a, "damage"),
                                width=0,
                            ).pack(side="left", padx=(0, 6))
                            buttons_added = True

                        difficulties = action.get("difficulties") or []
                        for difficulty in difficulties:
                            label_text = str(difficulty.get("label") or "Difficulty")
                            payload = {
                                "label": action.get("label"),
                                "notes": action.get("notes"),
                                "_difficulty": difficulty,
                            }
                            ctk.CTkButton(
                                buttons_row,
                                text=label_text,
                                command=lambda p=payload: self._execute_token_hover_action(token, p, "difficulty"),
                                width=0,
                            ).pack(side="left", padx=(0, 6))
                            buttons_added = True

                        if not buttons_added:
                            buttons_row.pack_forget()

                if errors:
                    error_color = "#f87171"
                    ctk.CTkLabel(
                        actions_frame,
                        text="Markup issues detected:",
                        anchor="w",
                        text_color=error_color,
                    ).pack(anchor="w", pady=(8, 2))
                    for issue in errors:
                        message = str(issue.get("message", ""))
                        ctk.CTkLabel(
                            actions_frame,
                            text=f"• {message}",
                            anchor="w",
                            justify="left",
                            text_color=error_color,
                            wraplength=360,
                        ).pack(anchor="w")
            elif actions_frame.winfo_ismapped():
                actions_frame.pack_forget()

        try:
            popup.update_idletasks()
        except tk.TclError:
            return
        container = label.master or label
        width = max(container.winfo_reqwidth() + 20, 160)
        height = max(container.winfo_reqheight() + 16, 80)
        bbox = token.get("hover_bbox")
        sx = sy = None
        if bbox:
            sx, sy = bbox[0], bbox[3]
        else:
            main_id = token.get("canvas_ids", (None,))[0]
            if main_id:
                try:
                    mbbox = canvas.bbox(main_id)
                except tk.TclError:
                    mbbox = None
                if mbbox:
                    sx, sy = mbbox[0], mbbox[3]
        if sx is None or sy is None:
            xw, yw = token.get("position", (0, 0))
            sx = int(xw * self.zoom + self.pan_x)
            sy = int(yw * self.zoom + self.pan_y)
        screen_x = canvas.winfo_rootx() + int(sx)
        screen_y = canvas.winfo_rooty() + int(sy) + 6
        popup.geometry(f"{int(width)}x{int(height)}+{screen_x}+{screen_y}")

    def _populate_token_links(self, token: dict, display_text: str) -> None:
        links_frame = token.get("hover_links_frame")
        if not links_frame or not links_frame.winfo_exists():
            return

        for child in list(links_frame.winfo_children()):
            try:
                child.destroy()
            except tk.TclError:
                pass

        link_sources = [display_text, token.get("_inline_markup_source")]

        record = token.get("entity_record")
        if record:
            link_sources.append(record)

        links = self._extract_links_from_sources(link_sources)
        if not links:
            if links_frame.winfo_ismapped():
                links_frame.pack_forget()
            return

        if not links_frame.winfo_ismapped():
            links_frame.pack(fill="x", padx=12, pady=(0, 6))

        header_font = ctk.CTkFont(size=max(12, self.hover_font_size - 1), weight="bold")
        ctk.CTkLabel(links_frame, text="Links", anchor="w", font=header_font).pack(anchor="w", pady=(0, 4))

        for url in links:
            link_label = ctk.CTkLabel(
                links_frame,
                text=url,
                anchor="w",
                justify="left",
                text_color="#93c5fd",
            )
            try:
                link_label.configure(cursor="hand2")
            except tk.TclError:
                pass
            link_label.pack(fill="x", pady=(0, 4))
            link_label.bind(
                "<Button-1>",
                lambda _event, target=url: self._open_external_link(target),
                add="+",
            )

    @staticmethod
    def _iter_text_fragments(value):
        if value is None:
            return

        if isinstance(value, str):
            yield value
            return

        if isinstance(value, dict):
            for item in value.values():
                yield from DisplayMapController._iter_text_fragments(item)
            return

        if isinstance(value, (list, tuple, set)):
            for item in value:
                yield from DisplayMapController._iter_text_fragments(item)
            return

        try:
            text = str(value)
        except Exception:
            return
        else:
            if text:
                yield text

    @classmethod
    def _extract_links_from_sources(cls, sources) -> list[str]:
        if not sources:
            return []

        seen: set[str] = set()
        results: list[str] = []
        for source in sources:
            for fragment in cls._iter_text_fragments(source):
                if not fragment:
                    continue
                fragment = fragment.strip()
                if not fragment:
                    continue
                for url in cls._extract_links_from_text(fragment):
                    if url not in seen:
                        seen.add(url)
                        results.append(url)
        return results

    @staticmethod
    def _extract_links_from_text(text: str) -> list[str]:
        if not text:
            return []

        text = str(text)

        results: list[str] = []
        seen: set[str] = set()
        for match in LINK_PATTERN.finditer(text):
            raw_url = match.group(0)
            trimmed = raw_url.rstrip('.,!?:;)"]')
            if trimmed.lower().startswith("www."):
                trimmed = f"https://{trimmed}"
            if trimmed and trimmed not in seen:
                seen.add(trimmed)
                results.append(trimmed)
        return results

    @staticmethod
    def _open_external_link(url: str) -> None:
        try:
            webbrowser.open(url, new=2)
        except Exception as exc:
            log_warning(
                f"Failed to open external link '{url}': {exc}",
                func_name="DisplayMapController._open_external_link",
            )

    def _show_token_hover(self, token):
        canvas = getattr(self, "canvas", None)
        if not canvas:
            return
        popup = self._ensure_token_hover_popup(token)
        if not popup:
            return
        self._hide_other_token_hovers(token)
        self._refresh_token_hover_popup(token)
        popup.deiconify()
        popup.lift()
        token["hover_visible"] = True

    def _hide_token_hover(self, token):
        canvas = getattr(self, "canvas", None)
        popup = token.get("hover_popup")
        token["hover_visible"] = False
        if popup and popup.winfo_exists():
            popup.withdraw()

    def _open_marker_description_editor(self, marker):
        if not marker:
            return
        canvas = getattr(self, "canvas", None)
        if not canvas:
            return
        editor = marker.get("description_editor")
        if editor and editor.winfo_exists():
            editor.lift()
            editor.focus_set()
            return
        editor = ctk.CTkToplevel(canvas)
        editor.title("Edit Marker Description")
        editor.geometry("420x320")
        marker["description_editor"] = editor

        textbox = ctk.CTkTextbox(editor, wrap="word")
        textbox.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        textbox.insert("1.0", marker.get("description", ""))

        button_frame = ctk.CTkFrame(editor)
        button_frame.pack(fill="x", padx=12, pady=(0, 12))

        def on_save():
            new_text = textbox.get("1.0", "end").rstrip()
            self._on_marker_description_change(marker, new_text=new_text, persist=True)
            marker["description_editor"] = None
            editor.destroy()

        def on_cancel():
            marker["description_editor"] = None
            editor.destroy()

        save_btn = ctk.CTkButton(button_frame, text="Save", command=on_save)
        save_btn.pack(side="right", padx=(6, 0))
        cancel_btn = ctk.CTkButton(button_frame, text="Cancel", command=on_cancel)
        cancel_btn.pack(side="right", padx=(0, 6))

        editor.protocol("WM_DELETE_WINDOW", on_cancel)
        editor.transient(canvas.winfo_toplevel())
        editor.grab_set()
        textbox.focus_set()

    def _widget_event_to_canvas_event(self, event):
        canvas = getattr(self, "canvas", None)
        if not canvas:
            return None
        try:
            x = event.x_root - canvas.winfo_rootx()
            y = event.y_root - canvas.winfo_rooty()
        except tk.TclError:
            return None
        state = getattr(event, "state", 0)
        return SimpleNamespace(x=x, y=y, state=state)

    def _on_marker_handle_press(self, event, marker):
        converted = self._widget_event_to_canvas_event(event)
        if converted:
            self._on_item_press(converted, marker)
        return "break"

    def _on_marker_handle_drag(self, event, marker):
        converted = self._widget_event_to_canvas_event(event)
        if converted:
            self._on_item_move(converted, marker)
        return "break"

    def _on_marker_handle_release(self, event, marker):
        converted = self._widget_event_to_canvas_event(event)
        if converted:
            self._on_item_release(converted, marker)
        return "break"

    def _push_fog_history(self):
        if self.mask_img is None:
            return

        buffer = io.BytesIO()
        try:
            self.mask_img.save(buffer, format="PNG")
        except Exception as exc:
            log_warning(f"Failed to snapshot fog history: {exc}")
            return

        payload = buffer.getvalue()
        if not payload:
            return

        self.fog_history.append(payload)
        self._fog_history_bytes += len(payload)

        max_budget = self._fog_history_budget_bytes()
        while self.fog_history and self._fog_history_bytes > max_budget:
            dropped = self.fog_history.pop(0)
            self._fog_history_bytes -= len(dropped)

    def _fog_history_budget_bytes(self):
        if self.mask_img is None:
            return 0

        pixel_count = max(1, self.mask_img.width * self.mask_img.height)
        min_budget = 4 * 1024 * 1024  # 4 MiB minimum history budget
        max_budget = 24 * 1024 * 1024  # cap history to 24 MiB overall
        estimated = pixel_count  # approximate PNG size scaling with pixels
        return max(min_budget, min(max_budget, estimated))

    def undo_fog(self, event=None):
        if not self.fog_history:
            return

        payload = self.fog_history.pop()
        self._fog_history_bytes -= len(payload)
        self._fog_history_bytes = max(0, self._fog_history_bytes)

        try:
            with Image.open(io.BytesIO(payload)) as restored:
                self.mask_img = restored.convert("RGBA")
        except Exception as exc:
            log_warning(f"Failed to restore fog history: {exc}")
            return

        self._update_canvas_images()
    
    # _bind_token is now _bind_item_events

    def _on_token_right_click(self, event, tokens, clicked_token):
        valid_tokens = [t for t in tokens if isinstance(t, dict) and t.get("type") == "token"]
        if not valid_tokens:
            return

        primary = clicked_token if clicked_token in valid_tokens else valid_tokens[0]
        if (
            len(valid_tokens) == 1
            and primary.get("type") == "token"
            and "hp_canvas_ids" in primary
            and primary["hp_canvas_ids"]
        ):
            hp_cid, _ = primary["hp_canvas_ids"]
            if hp_cid:
                try:
                    x1, y1, x2, y2 = self.canvas.coords(hp_cid)
                except tk.TclError:
                    x1 = y1 = x2 = y2 = None
                else:
                    pad = 4
                    if (
                        x1 is not None
                        and x1 - pad <= event.x <= x2 + pad
                        and y1 - pad <= event.y <= y2 + pad
                    ):
                        return self._on_max_hp_menu_click(event, primary)

        return self._show_token_menu(event, valid_tokens)
    
    def _on_token_double_click(self, event, token):
        print(f"Token double click on: {token.get('entity_id', 'Unknown Token')}")
        if token.get("type") != "token" or "hp_canvas_ids" not in token or not token["hp_canvas_ids"]: return
        hp_cid, _ = token["hp_canvas_ids"]
        if not hp_cid: return
        x1, y1, x2, y2 = self.canvas.coords(hp_cid); pad = 4
        if x1 - pad <= event.x <= x2 + pad and y1 - pad <= event.y <= y2 + pad:
            self._on_hp_double_click(event, token)
                                     
    def _create_marker(self):
        # Create a pulsating circle that animates while the user holds the click
        if not self._marker_start:
            return
        x0, y0 = self._marker_start
        xw = (x0 - self.pan_x) / self.zoom
        yw = (y0 - self.pan_y) / self.zoom
        sx, sy = int(xw * self.zoom + self.pan_x), int(yw * self.zoom + self.pan_y)
        # Start small then grow to max, then pulse between min and max
        self._marker_radius = self._marker_min_r
        r = self._marker_radius
        # Create or reset the ovals
        if self._marker_id:
            try:
                self.canvas.coords(self._marker_id, sx - r, sy - r, sx + r, sy + r)
            except tk.TclError:
                self._marker_id = None
        if not self._marker_id:
            self._marker_id = self.canvas.create_oval(sx - r, sy - r, sx + r, sy + r, outline='red', width=2)
        if self.fs_canvas:
            if self._fs_marker_id:
                try:
                    self.fs_canvas.coords(self._fs_marker_id, sx - r, sy - r, sx + r, sy + r)
                except tk.TclError:
                    self._fs_marker_id = None
            if not self._fs_marker_id:
                self._fs_marker_id = self.fs_canvas.create_oval(sx - r, sy - r, sx + r, sy + r, outline='red', width=2)
        # Kick off animation loop
        self._marker_anim_dir = 1
        self._schedule_marker_animation()

    def _schedule_marker_animation(self):
        # Schedule next frame of the pulsating animation
        if not self._marker_start:
            return
        # Use a short interval for smooth animation
        if self._marker_anim_after_id:
            try:
                self.canvas.after_cancel(self._marker_anim_after_id)
            except Exception:
                pass
        self._marker_anim_after_id = self.canvas.after(40, self._animate_marker)

    def _animate_marker(self):
        # If mouse released or marker removed, stop animation
        if not self._marker_start or not self._marker_id:
            return
        # Update radius
        step = 2
        self._marker_radius += step * self._marker_anim_dir
        if self._marker_radius >= self._marker_max_r:
            self._marker_radius = self._marker_max_r
            self._marker_anim_dir = -1
        elif self._marker_radius <= self._marker_min_r:
            self._marker_radius = self._marker_min_r
            self._marker_anim_dir = 1
        # Recompute current screen position from stored screen start
        x0, y0 = self._marker_start
        xw = (x0 - self.pan_x) / self.zoom
        yw = (y0 - self.pan_y) / self.zoom
        sx, sy = int(xw * self.zoom + self.pan_x), int(yw * self.zoom + self.pan_y)
        r = self._marker_radius
        try:
            self.canvas.coords(self._marker_id, sx - r, sy - r, sx + r, sy + r)
        except tk.TclError:
            self._marker_id = None
        if self.fs_canvas and self._fs_marker_id:
            try:
                self.fs_canvas.coords(self._fs_marker_id, sx - r, sy - r, sx + r, sy + r)
            except tk.TclError:
                self._fs_marker_id = None
        # Loop
        self._schedule_marker_animation()

    def _on_middle_click(self, event):
        # Start panning mode: remember starting mouse position and pan
        self._panning = True
        self._last_mouse = (event.x, event.y)
        self._orig_pan = (self.pan_x, self.pan_y)
        try:
            self.canvas.configure(cursor="fleur")
        except tk.TclError:
            pass

    def _on_middle_drag(self, event):
        # While middle button held, pan by mouse delta
        if not self._panning:
            return
        dx = event.x - self._last_mouse[0]
        dy = event.y - self._last_mouse[1]
        self.pan_x += dx
        self.pan_y += dy
        self._last_mouse = (event.x, event.y)
        # Fast path: only move existing canvas items; avoid costly resizes
        self._nudge_canvas(dx, dy)

    def _on_middle_release(self, event):
        # End panning mode
        if self._panning:
            self._panning = False
            try:
                self.canvas.configure(cursor="")
            except tk.TclError:
                pass
            # Snap to full redraw once released; also sync mirrors
            try:
                self._update_canvas_images(resample=self._fast_resample)
                if getattr(self, 'fs_canvas', None):
                    self._update_fullscreen_map()
                if getattr(self, '_web_server_thread', None):
                    self._update_web_display_map()
            except Exception:
                pass

    def _nudge_canvas(self, dx, dy):
        """Move all visible canvas items by dx,dy without recomputing images."""
        try:
            if self.base_id:
                self.canvas.move(self.base_id, dx, dy)
            if self.mask_id:
                self.canvas.move(self.mask_id, dx, dy)
            # Move tokens and shapes
            for item in self.tokens:
                for cid in item.get("canvas_ids", []):
                    if cid:
                        self.canvas.move(cid, dx, dy)
                if item.get("type", "token") == "token":
                    if item.get("name_id"):
                        self.canvas.move(item["name_id"], dx, dy)
                    if item.get("hp_canvas_ids"):
                        for hp_cid in item["hp_canvas_ids"]:
                            if hp_cid:
                                self.canvas.move(hp_cid, dx, dy)
                    if item.get("defense_canvas_ids"):
                        for def_cid in item["defense_canvas_ids"]:
                            if def_cid:
                                self.canvas.move(def_cid, dx, dy)
                    if item.get("hover_bbox"):
                        x1, y1, x2, y2 = item["hover_bbox"]
                        item["hover_bbox"] = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
                    self._refresh_token_hover_popup(item)
                    if item.get("hover_visible"):
                        self._show_token_hover(item)
            # Move resize handles if displayed
            for hid in getattr(self, '_resize_handles', []) or []:
                try:
                    self.canvas.move(hid, dx, dy)
                except tk.TclError:
                    pass
            # Move marker if present
            if self._marker_id:
                try:
                    self.canvas.move(self._marker_id, dx, dy)
                except tk.TclError:
                    pass
        except tk.TclError:
            # Fallback to full redraw if something goes wrong
            self._update_canvas_images(resample=self._fast_resample)

    def _on_mouse_down(self, event):
        # Check if a resize handle was clicked first
        # print(f"[DEBUG] _on_mouse_down: Raw click at ({event.x}, {event.y})")
        current_ids_under_cursor = self.canvas.find_withtag("current")
        if current_ids_under_cursor:
            print(f"[DEBUG] _on_mouse_down: Canvas item ID under cursor: {current_ids_under_cursor[0]}, tags: {self.canvas.gettags(current_ids_under_cursor[0])}")
        else:
            print("[DEBUG] _on_mouse_down: No canvas item directly under cursor ('current').")

        if getattr(event, "widget", None) is self.canvas:
            try:
                self.canvas.focus_set()
            except tk.TclError:
                pass

        current_tags = self.canvas.gettags("current")
        handle_type = None
        for tag in current_tags:
            if tag.endswith("_handle"): # e.g., "se_handle"
                handle_type = tag.split('_')[0]
                break

        if handle_type and self._graphical_edit_mode_item and self.selected_token == self._graphical_edit_mode_item:
            self._on_resize_handle_press(event, handle_type)
            return # A handle was pressed, resize logic takes over

        if self.drawing_mode == "eraser":
            world_x = (event.x - self.pan_x) / self.zoom
            world_y = (event.y - self.pan_y) / self.zoom
            self._eraser_active = True
            if self._erase_whiteboard_at(world_x, world_y):
                self._mark_eraser_dirty()
            self._hide_all_token_hovers()
            self._hide_all_marker_descriptions()
            if self._marker_after_id:
                try:
                    self.canvas.after_cancel(self._marker_after_id)
                except Exception:
                    pass
                self._marker_after_id = None
            self._marker_start = None
            return

        # If not clicking a handle, determine if clicking an item or empty space
        current_ids = self.canvas.find_withtag("current")
        clicked_an_item = False
        if current_ids:
            clicked_item_id = current_ids[0]
            for item_iter in self.tokens:
                item_canvas_ids = item_iter.get("canvas_ids")
                if item_canvas_ids and clicked_item_id in item_canvas_ids:
                    print(f"[DEBUG] _on_mouse_down: Matched clicked canvas ID {clicked_item_id} to item: {item_iter.get('type')} - {item_iter.get('entity_id', 'Shape')}")
                    # An item (not a handle) was clicked. Its own _on_item_press will handle selection.
                    # If this click deselects a shape that was in graphical edit mode,
                    # _on_item_press should call _remove_resize_handles.
                    clicked_an_item = True
                    break
        
        if not clicked_an_item: # Clicked on empty canvas space
            self._hide_all_token_hovers()
            self._hide_all_marker_descriptions()
            if self._graphical_edit_mode_item: # If graphical edit was active, deactivate it
                self._remove_resize_handles()
                self._graphical_edit_mode_item = None
            existing_selection = list(self.selected_items)

            if self.drawing_mode == "whiteboard":
                world_x = (event.x - self.pan_x) / self.zoom
                world_y = (event.y - self.pan_y) / self.zoom
                self._active_whiteboard_points = [(world_x, world_y)]
                self._hide_all_token_hovers()
                self._hide_all_marker_descriptions()
                self._clear_whiteboard_preview()
                if self._marker_after_id:
                    try:
                        self.canvas.after_cancel(self._marker_after_id)
                    except Exception:
                        pass
                self._marker_after_id = None
                self._marker_start = None
                return

            if self.drawing_mode == "text":
                world_x = (event.x - self.pan_x) / self.zoom
                world_y = (event.y - self.pan_y) / self.zoom
                self._create_text_at(world_x, world_y)
                return

            if self.drawing_mode in ["rectangle", "oval"]: # Create new shape if in drawing mode
                # Create new shape - This block needs to be indented
                world_x = (event.x - self.pan_x) / self.zoom; world_y = (event.y - self.pan_y) / self.zoom
                new_shape = {
                    "type": self.drawing_mode, "shape_type": self.drawing_mode,
                    "position": (world_x, world_y), "width": DEFAULT_SHAPE_WIDTH, "height": DEFAULT_SHAPE_HEIGHT,
                    "fill_color": self.current_shape_fill_color, "border_color": self.current_shape_border_color,
                    "is_filled": self.shape_is_filled, "canvas_ids": ()
                }
                self.tokens.append(new_shape); self._update_canvas_images(); self._persist_tokens()
                return # New shape created, done with this click.
            if self.fog_mode in ("add_rect", "rem_rect"):
                self._clear_fog_rectangle_preview()
                start_world_x = (event.x - self.pan_x) / self.zoom
                start_world_y = (event.y - self.pan_y) / self.zoom
                self._fog_rect_start_world = (start_world_x, start_world_y)
                if not self._fog_action_active:
                    self._push_fog_history()
                    self._fog_action_active = True
            elif self.fog_mode not in ("add", "rem"):
                self._start_drag_selection(event, existing_selection=existing_selection)
        # The following elif was part of a previous attempt and seems to be a leftover,
        # as item click handling is done by _on_item_press.
        # Removing it to simplify and avoid potential conflicts.
        # elif self.drawing_mode in ["rectangle", "oval"] and clicked_item_id not in [h for h_list in [it.get('_resize_handles', []) for it in self.tokens if it.get('_resize_handles')] for h in h_list]:
        #     pass

        if self.fog_mode in ("add", "rem") and not self._fog_action_active:
            self._push_fog_history(); self._fog_action_active = True
        self._marker_start = (event.x, event.y)
        self._marker_after_id = self.canvas.after(500, self._create_marker)

    def _on_mouse_move(self, event):
        if self._marker_after_id and self._marker_start:
            dx = event.x - self._marker_start[0]; dy = event.y - self._marker_start[1]
            if abs(dx) > 5 or abs(dy) > 5: self.canvas.after_cancel(self._marker_after_id); self._marker_after_id = None
        if self.drawing_mode == "eraser" and self._eraser_active:
            world_x = (event.x - self.pan_x) / self.zoom
            world_y = (event.y - self.pan_y) / self.zoom
            if self._erase_whiteboard_at(world_x, world_y):
                self._mark_eraser_dirty()
            return
        if self.drawing_mode == "whiteboard" and self._active_whiteboard_points:
            world_x = (event.x - self.pan_x) / self.zoom
            world_y = (event.y - self.pan_y) / self.zoom
            last_point = self._active_whiteboard_points[-1]
            dx = world_x - last_point[0]
            dy = world_y - last_point[1]
            if (dx * dx + dy * dy) >= 1.0:
                self._active_whiteboard_points.append((world_x, world_y))
                self._update_whiteboard_preview()
            return
        if self._drag_select_start:
            self._update_drag_selection(event)
        if self.fog_mode in ("add", "rem"):
            self.on_paint(event)
        elif self.fog_mode in ("add_rect", "rem_rect") and self._fog_rect_start_world is not None:
            self._update_fog_rectangle_preview(event)

    def _on_mouse_up(self, event):
        if self.drawing_mode == "eraser":
            if self._eraser_active and self._eraser_dirty:
                self._commit_eraser_changes()
            self._eraser_active = False
            self._eraser_dirty = False
            return
        if self.drawing_mode == "whiteboard" and self._active_whiteboard_points:
            self._finalize_whiteboard_stroke()
            return
        self._finalize_drag_selection(event)
        if self._marker_after_id: self.canvas.after_cancel(self._marker_after_id); self._marker_after_id = None
        if self._marker_anim_after_id:
            try:
                self.canvas.after_cancel(self._marker_anim_after_id)
            except Exception:
                pass
            self._marker_anim_after_id = None
        if self._marker_id: self.canvas.delete(self._marker_id); self._marker_id = None
        if self.fs_canvas and self._fs_marker_id: self.fs_canvas.delete(self._fs_marker_id); self._fs_marker_id = None
        if (
            self.fog_mode in ("add_rect", "rem_rect")
            and self._fog_rect_start_world is not None
            and self.mask_img is not None
        ):
            end_world_x = (event.x - self.pan_x) / self.zoom
            end_world_y = (event.y - self.pan_y) / self.zoom
            start_world_x, start_world_y = self._fog_rect_start_world

            left = math.floor(min(start_world_x, end_world_x))
            right = math.ceil(max(start_world_x, end_world_x))
            top = math.floor(min(start_world_y, end_world_y))
            bottom = math.ceil(max(start_world_y, end_world_y))

            width, height = self.mask_img.size
            if width > 0 and height > 0:
                left = int(max(0, min(width - 1, left)))
                right = int(max(0, min(width - 1, right)))
                top = int(max(0, min(height - 1, top)))
                bottom = int(max(0, min(height - 1, bottom)))

                if right < left:
                    left, right = right, left
                if bottom < top:
                    top, bottom = bottom, top

                if right == left and width > 1:
                    right = min(width - 1, right + 1)
                if bottom == top and height > 1:
                    bottom = min(height - 1, bottom + 1)

                apply_fog_rectangle(self, (left, top, right, bottom), self.fog_mode)

        self._fog_rect_start_world = None
        if self._fog_action_active:
            self._fog_action_active = False
            self._clear_fog_rectangle_preview()
            if self.base_img and self.mask_img:
                w, h = self.base_img.size; sw, sh = int(w*self.zoom), int(h*self.zoom)
                if sw > 0 and sh > 0:
                    mask_resized = self.mask_img.resize((sw, sh), resample=Image.LANCZOS)
                    self.mask_tk = ImageTk.PhotoImage(mask_resized)
                    if self.mask_id: self.canvas.itemconfig(self.mask_id, image=self.mask_tk); self.canvas.coords(self.mask_id, self.pan_x, self.pan_y)
                    fs_canvas = getattr(self, "fs_canvas", None)
                    if fs_canvas:
                        try:
                            if fs_canvas.winfo_exists():
                                self._update_fullscreen_map()
                        except tk.TclError:
                            pass

    def _clear_whiteboard_preview(self):
        canvas = getattr(self, "canvas", None)
        if canvas and self._whiteboard_preview_id:
            try:
                canvas.delete(self._whiteboard_preview_id)
            except tk.TclError:
                pass
        self._whiteboard_preview_id = None

    def _update_whiteboard_preview(self):
        canvas = getattr(self, "canvas", None)
        if not canvas or len(self._active_whiteboard_points) < 2:
            return
        screen_points = []
        for xw, yw in self._active_whiteboard_points:
            screen_points.extend([self.pan_x + xw * self.zoom, self.pan_y + yw * self.zoom])
        try:
            if self._whiteboard_preview_id and canvas.type(self._whiteboard_preview_id):
                canvas.coords(self._whiteboard_preview_id, *screen_points)
                canvas.itemconfig(
                    self._whiteboard_preview_id,
                    fill=self.whiteboard_color,
                    width=self.whiteboard_width,
                    smooth=False,
                    capstyle="butt",
                    joinstyle="miter",
                )
            else:
                self._whiteboard_preview_id = canvas.create_line(
                    *screen_points,
                    fill=self.whiteboard_color,
                    width=self.whiteboard_width,
                    smooth=False,
                    capstyle="butt",
                    joinstyle="miter",
                    tags=("whiteboard_preview",),
                )
            canvas.tag_raise(self._whiteboard_preview_id)
        except tk.TclError:
            self._whiteboard_preview_id = None

    def _simplify_polyline(self, points, tolerance=1.5):
        if len(points) < 3:
            return list(points)

        def _distance(p1, p2):
            dx = p1[0] - p2[0]
            dy = p1[1] - p2[1]
            return math.sqrt(dx * dx + dy * dy)

        simplified = [points[0]]
        for p in points[1:-1]:
            if _distance(p, simplified[-1]) >= tolerance:
                simplified.append(p)
        simplified.append(points[-1])
        return simplified

    def _finalize_whiteboard_stroke(self):
        points = self._simplify_polyline(self._active_whiteboard_points)
        self._active_whiteboard_points = []
        self._clear_whiteboard_preview()
        if len(points) < 2:
            return
        stroke = {
            "type": "whiteboard",
            "points": points,
            "color": self.whiteboard_color,
            "width": self.whiteboard_width,
            "position": points[0],
            "canvas_ids": (),
        }
        self.tokens.append(stroke)
        self._update_canvas_images(resample=self._fast_resample)
        self._persist_tokens()

    def _create_text_at(self, world_x: float, world_y: float):
        text = prompt_for_text(self.canvas, title="Add Text", prompt="Enter text:")
        if text is None:
            return
        text_item = create_text_item(
            text,
            (world_x, world_y),
            color=self.whiteboard_color,
            size=int(getattr(self, "text_size", 24)),
        )
        self.tokens.append(text_item)
        self._update_canvas_images(resample=self._fast_resample)
        self._persist_tokens()

    def _mark_eraser_dirty(self):
        self._eraser_dirty = True
        if not self._eraser_repaint_scheduled:
            self._eraser_repaint_scheduled = True
            try:
                self.parent.after(0, self._perform_eraser_repaint)
            except Exception:
                self._perform_eraser_repaint()

    def _perform_eraser_repaint(self):
        self._eraser_repaint_scheduled = False
        try:
            self._update_canvas_images(resample=self._fast_resample)
        except Exception:
            pass

    def _point_to_segment_distance(self, point, start, end):
        px, py = point
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def _polyline_hits_point(self, points, point, radius):
        if len(points) < 2:
            return False
        for start, end in zip(points, points[1:]):
            if self._point_to_segment_distance(point, start, end) <= radius:
                return True
        return False

    def _erase_whiteboard_at(self, world_x: float, world_y: float) -> bool:
        canvas = getattr(self, "canvas", None)
        changed = False
        remaining_tokens = []
        radius = float(getattr(self, "whiteboard_eraser_radius", 8.0))
        target_point = (world_x, world_y)
        screen_point = (self.pan_x + world_x * self.zoom, self.pan_y + world_y * self.zoom)
        radius_screen = radius * self.zoom
        for item in self.tokens:
            if item.get("type") == "text":
                if text_hit_test(canvas, item, screen_point=screen_point, radius=radius_screen, zoom=self.zoom, pan=(self.pan_x, self.pan_y)):
                    for cid in item.get("canvas_ids") or []:
                        if canvas:
                            try:
                                canvas.delete(cid)
                            except tk.TclError:
                                pass
                    fs_canvas = getattr(self, "fs_canvas", None)
                    for fs_cid in item.get("fs_canvas_ids") or []:
                        if fs_canvas:
                            try:
                                fs_canvas.delete(fs_cid)
                            except tk.TclError:
                                pass
                    changed = True
                    if item is self.selected_token:
                        self.selected_token = None
                    if item in self.selected_items:
                        try:
                            self.selected_items.remove(item)
                        except ValueError:
                            pass
                    continue
            if item.get("type") != "whiteboard":
                remaining_tokens.append(item)
                continue
            points = item.get("points") or []
            if len(points) < 2:
                remaining_tokens.append(item)
                continue
            effective_radius = radius + float(item.get("width", 0)) / 2.0
            if not self._polyline_hits_point(points, target_point, effective_radius):
                remaining_tokens.append(item)
                continue
            for cid in item.get("canvas_ids") or []:
                if canvas:
                    try:
                        canvas.delete(cid)
                    except tk.TclError:
                        pass
            fs_canvas = getattr(self, "fs_canvas", None)
            for fs_cid in item.get("fs_canvas_ids") or []:
                if fs_canvas:
                    try:
                        fs_canvas.delete(fs_cid)
                    except tk.TclError:
                        pass
            if item is self.selected_token:
                self.selected_token = None
            if item in self.selected_items:
                try:
                    self.selected_items.remove(item)
                except ValueError:
                    pass
            changed = True
        if changed:
            self.tokens = remaining_tokens
        return changed

    def _commit_eraser_changes(self):
        try:
            self._update_canvas_images(resample=self._fast_resample)
        except Exception:
            pass
        self._persist_tokens()
        try:
            if getattr(self, 'fs', None) and self.fs.winfo_exists() and getattr(self, 'fs_canvas', None):
                self.parent.after(0, self._update_fullscreen_map)
        except tk.TclError:
            pass
        try:
            if getattr(self, '_web_server_thread', None):
                self.parent.after(0, self._update_web_display_map)
        except Exception:
            pass

    def _update_fog_rectangle_preview(self, event):
        if self._fog_rect_start_world is None or self.zoom == 0:
            return

        canvas = getattr(self, "canvas", None)
        if not canvas:
            return

        start_world_x, start_world_y = self._fog_rect_start_world
        end_world_x = (event.x - self.pan_x) / self.zoom
        end_world_y = (event.y - self.pan_y) / self.zoom

        left = min(start_world_x, end_world_x)
        right = max(start_world_x, end_world_x)
        top = min(start_world_y, end_world_y)
        bottom = max(start_world_y, end_world_y)

        screen_left = self.pan_x + left * self.zoom
        screen_top = self.pan_y + top * self.zoom
        screen_right = self.pan_x + right * self.zoom
        screen_bottom = self.pan_y + bottom * self.zoom

        outline_color = "#d7263d" if self.fog_mode == "add_rect" else "#00a2ff"

        try:
            if self._fog_rect_preview_id and canvas.type(self._fog_rect_preview_id):
                canvas.coords(self._fog_rect_preview_id, screen_left, screen_top, screen_right, screen_bottom)
                canvas.itemconfig(self._fog_rect_preview_id, outline=outline_color)
            else:
                self._fog_rect_preview_id = canvas.create_rectangle(
                    screen_left,
                    screen_top,
                    screen_right,
                    screen_bottom,
                    outline=outline_color,
                    width=2,
                    dash=(6, 4),
                    fill="",
                    tags=("fog_preview",),
                )
            canvas.tag_raise(self._fog_rect_preview_id)
        except tk.TclError:
            self._fog_rect_preview_id = None

        fs_canvas = getattr(self, "fs_canvas", None)
        if fs_canvas:
            try:
                if not fs_canvas.winfo_exists():
                    fs_canvas = None
            except tk.TclError:
                fs_canvas = None

        if fs_canvas:
            try:
                if self._fog_rect_fs_preview_id and fs_canvas.type(self._fog_rect_fs_preview_id):
                    fs_canvas.coords(
                        self._fog_rect_fs_preview_id,
                        screen_left,
                        screen_top,
                        screen_right,
                        screen_bottom,
                    )
                    fs_canvas.itemconfig(self._fog_rect_fs_preview_id, outline=outline_color)
                else:
                    self._fog_rect_fs_preview_id = fs_canvas.create_rectangle(
                        screen_left,
                        screen_top,
                        screen_right,
                        screen_bottom,
                        outline=outline_color,
                        width=2,
                        dash=(6, 4),
                        fill="",
                        tags=("fog_preview",),
                    )
                fs_canvas.tag_raise(self._fog_rect_fs_preview_id)
            except tk.TclError:
                self._fog_rect_fs_preview_id = None

    def _clear_fog_rectangle_preview(self):
        canvas = getattr(self, "canvas", None)
        if canvas:
            try:
                canvas.delete("fog_preview")
            except tk.TclError:
                pass

        fs_canvas = getattr(self, "fs_canvas", None)
        if fs_canvas:
            try:
                if fs_canvas.winfo_exists():
                    fs_canvas.delete("fog_preview")
            except tk.TclError:
                pass

        self._fog_rect_preview_id = None
        self._fog_rect_fs_preview_id = None

    def _perform_zoom(self, final: bool):
        attr = "_zoom_final_after_id" if final else "_zoom_after_id"
        setattr(self, attr, None)
        resample = Image.LANCZOS if final else self._fast_resample; self._update_canvas_images(resample=resample)

    def _update_canvas_images(self, resample=Image.LANCZOS):
        if not self.base_img: return
        debug_payload = getattr(self, "_pending_render_debug_dump", None)
        if debug_payload is not None:
            debug_payload.setdefault("rendered_items", [])

        def _safe_canvas_coords(cid):
            if not cid:
                return None
            try:
                coords = self.canvas.coords(cid)
            except tk.TclError:
                return None
            if not coords:
                return None
            try:
                converted = []
                for value in coords:
                    if isinstance(value, (int, float)):
                        converted.append(int(round(value)))
                    else:
                        converted.append(value)
                return tuple(converted)
            except Exception:
                return tuple(coords)

        def _primary_screen_from_coords(coords):
            if not coords:
                return None
            if len(coords) >= 2:
                return (int(coords[0]), int(coords[1]))
            return None
        
        # Redraw handles if graphical edit mode is active for the selected item
        # and not currently in a drag-resize operation.
        if self.selected_token and self.selected_token == self._graphical_edit_mode_item and \
           not self._active_resize_handle_info and self.canvas.winfo_exists():
            self._draw_resize_handles(self.selected_token)
        # Ensure handles are removed if graphical edit mode is not active for the selected item
        elif self._resize_handles and (not self.selected_token or self.selected_token != self._graphical_edit_mode_item):
            self._remove_resize_handles()


        # Choose current base source (video frame if available)
        base_source = getattr(self, "_video_current_frame_pil", None) or self.base_img
        w, h = base_source.size; sw, sh = int(w*self.zoom), int(h*self.zoom)
        if sw <= 0 or sh <= 0: return 
        x0, y0 = self.pan_x, self.pan_y
        base_resized = base_source.resize((sw,sh), resample=resample); self.base_tk = ImageTk.PhotoImage(base_resized)
        if self.base_id: self.canvas.itemconfig(self.base_id, image=self.base_tk); self.canvas.coords(self.base_id, x0, y0)
        else: self.base_id = self.canvas.create_image(x0, y0, image=self.base_tk, anchor='nw')
        if self.mask_img:
            mask_resized = self.mask_img.resize((sw,sh), resample=resample); self.mask_tk = ImageTk.PhotoImage(mask_resized)
            if self.mask_id: self.canvas.itemconfig(self.mask_id, image=self.mask_tk); self.canvas.coords(self.mask_id, x0, y0)
            else: self.mask_id = self.canvas.create_image(x0, y0, image=self.mask_tk, anchor='nw')
        for item in self.tokens:
            item_type = item.get("type", "token"); xw, yw = item['position']
            if item_type == "token":
                source = item.get('source_image')
                pil = item.get('pil_image')
                size_px = item.get('size')
                if size_px is None:
                    if source is not None:
                        size_px = source.size[0]
                    elif pil is not None:
                        size_px = pil.size[0]
                    else:
                        size_px = self.token_size
                try:
                    size_px = max(1, int(size_px))
                except Exception:
                    size_px = max(1, int(self.token_size))

                if source is not None:
                    nw = nh = max(1, int(size_px * self.zoom))
                    if nw <= 0 or nh <= 0:
                        continue
                    img_r = source.resize((nw, nh), resample=resample)
                else:
                    if not pil:
                        continue
                    tw, th = pil.size; nw, nh = int(tw*self.zoom), int(th*self.zoom)
                    if nw <=0 or nh <=0: continue
                    img_r = pil.resize((nw,nh), resample=resample)

                tkimg = ImageTk.PhotoImage(img_r); item['tk_image'] = tkimg
                sx, sy = int(xw*self.zoom + self.pan_x), int(yw*self.zoom + self.pan_y)
                debug_entry = None
                if debug_payload is not None:
                    debug_entry = {
                        "type": "token",
                        "entity_id": item.get("entity_id"),
                        "entity_type": item.get("entity_type"),
                        "world_position": (xw, yw),
                        "expected_screen": (sx, sy),
                        "size": (nw, nh),
                        "border_color": item.get("border_color"),
                    }
                if item.get('canvas_ids'):
                    b_id, i_id = item['canvas_ids']
                    self.canvas.itemconfig(b_id, outline=item.get('border_color','#0000ff'))
                    self.canvas.coords(b_id, sx-3, sy-3, sx+nw+3, sy+nh+3); self.canvas.coords(i_id, sx, sy)
                    self.canvas.itemconfig(i_id, image=tkimg)
                    hp = item.get("hp", 10); max_hp = item.get("max_hp", 10)
                    ratio = hp / max_hp if max_hp > 0 else 1.0; hp_color = "#ff3333" if ratio < 0.10 else "#33cc33"
                    circle_diam = max(18, int(nw * 0.25)); cx = sx + nw - circle_diam + 4; cy = sy + nh - circle_diam + 4
                    if item.get("hp_canvas_ids"):
                        cid, tid = item["hp_canvas_ids"]
                        self.canvas.coords(cid, cx, cy, cx + circle_diam, cy + circle_diam); self.canvas.itemconfig(cid, fill=hp_color)
                        self.canvas.coords(tid, cx + circle_diam // 2, cy + circle_diam // 2); self.canvas.itemconfig(tid, text=str(hp))
                    defense_value = item.get("defense_value")
                    if defense_value is None:
                        defense_info = _extract_entity_defense_value(item.get("entity_type"), item.get("entity_record"))
                        if defense_info:
                            defense_label, defense_value = defense_info
                            item["defense_label"] = defense_label
                            item["defense_value"] = defense_value
                    defense_color = "#2563eb"
                    defense_coords = (sx - 4, sy - 4)
                    if defense_value is not None:
                        dcx, dcy = defense_coords
                        if item.get("defense_canvas_ids"):
                            dcid, dtid = item["defense_canvas_ids"]
                            if dcid:
                                self.canvas.coords(dcid, dcx, dcy, dcx + circle_diam, dcy + circle_diam)
                                self.canvas.itemconfig(dcid, fill=defense_color)
                            if dtid:
                                self.canvas.coords(dtid, dcx + circle_diam // 2, dcy + circle_diam // 2)
                                self.canvas.itemconfig(dtid, text=str(defense_value))
                        else:
                            dcid = self.canvas.create_oval(
                                dcx,
                                dcy,
                                dcx + circle_diam,
                                dcy + circle_diam,
                                fill=defense_color,
                                outline="black",
                                width=1,
                            )
                            dtid = self.canvas.create_text(
                                dcx + circle_diam // 2,
                                dcy + circle_diam // 2,
                                text=str(defense_value),
                                font=("Arial", max(10, circle_diam // 2), "bold"),
                                fill="white",
                            )
                            item["defense_canvas_ids"] = (dcid, dtid)
                    elif item.get("defense_canvas_ids"):
                        for dcid in item["defense_canvas_ids"]:
                            if dcid:
                                self.canvas.delete(dcid)
                        item.pop("defense_canvas_ids", None)
                    name_id = item.get('name_id')
                    if name_id: tx = sx + nw/2; ty = sy + nh + 2; self.canvas.coords(name_id, tx, ty); self.canvas.itemconfig(name_id, text=item.get('entity_id', ''))
                    item['hover_bbox'] = (sx - 3, sy - 3, sx + nw + 3, sy + nh + 3)
                    self._refresh_token_hover_popup(item)
                    if item.get("hover_visible"):
                        self._show_token_hover(item)
                else:
                    b_id = self.canvas.create_rectangle(sx-3, sy-3, sx+nw+3, sy+nh+3, outline=item.get('border_color','#0000ff'), width=3)
                    i_id = self.canvas.create_image(sx, sy, image=tkimg, anchor='nw')
                    tx = sx + nw/2; ty = sy + nh + 2; name_id = self.canvas.create_text(tx, ty, text=item.get('entity_id',''), fill='white', anchor='n'); item['name_id'] = name_id
                    hp = item.get("hp", 10); max_hp = item.get("max_hp", 10); ratio = hp / max_hp if max_hp > 0 else 1.0
                    hp_color = "#ff3333" if ratio < 0.10 else "#33cc33"; circle_diam = max(18, int(nw * 0.25))
                    cx = sx + nw - circle_diam + 4; cy = sy + nh - circle_diam + 4
                    cid = self.canvas.create_oval(cx, cy, cx + circle_diam, cy + circle_diam, fill=hp_color, outline="black", width=1)
                    tid = self.canvas.create_text(cx + circle_diam//2, cy + circle_diam//2, text=str(hp), font=("Arial", max(10, circle_diam // 2), "bold"), fill="white")
                    item["hp_canvas_ids"] = (cid, tid)
                    for item_id_hp in (cid, tid):
                        self.canvas.tag_bind(item_id_hp, "<Double-Button-1>", lambda e, t=item: self._on_hp_double_click(e, t))
                        self.canvas.tag_bind(item_id_hp, "<Button-3>", lambda e, t=item: self._on_max_hp_menu_click(e, t))
                    defense_value = item.get("defense_value")
                    if defense_value is None:
                        defense_info = _extract_entity_defense_value(item.get("entity_type"), item.get("entity_record"))
                        if defense_info:
                            defense_label, defense_value = defense_info
                            item["defense_label"] = defense_label
                            item["defense_value"] = defense_value
                    defense_color = "#2563eb"
                    if defense_value is not None:
                        dcx, dcy = sx - 4, sy - 4
                        dcid = self.canvas.create_oval(
                            dcx,
                            dcy,
                            dcx + circle_diam,
                            dcy + circle_diam,
                            fill=defense_color,
                            outline="black",
                            width=1,
                        )
                        dtid = self.canvas.create_text(
                            dcx + circle_diam // 2,
                            dcy + circle_diam // 2,
                            text=str(defense_value),
                            font=("Arial", max(10, circle_diam // 2), "bold"),
                            fill="white",
                        )
                        item["defense_canvas_ids"] = (dcid, dtid)
                    elif item.get("defense_canvas_ids"):
                        for dcid in item["defense_canvas_ids"]:
                            if dcid:
                                self.canvas.delete(dcid)
                        item.pop("defense_canvas_ids", None)
                    item.update({'canvas_ids': (b_id, i_id), 'name_id': name_id})
                    self._bind_item_events(item)
                    item['hover_bbox'] = (sx - 3, sy - 3, sx + nw + 3, sy + nh + 3)
                    self._refresh_token_hover_popup(item)
                if debug_entry is not None:
                    canvas_ids = item.get('canvas_ids') or ()
                    border_id = canvas_ids[0] if len(canvas_ids) >= 1 else None
                    image_id = canvas_ids[1] if len(canvas_ids) >= 2 else (canvas_ids[0] if len(canvas_ids) == 1 else None)
                    image_coords = _safe_canvas_coords(image_id)
                    border_coords = _safe_canvas_coords(border_id)
                    name_coords = _safe_canvas_coords(item.get('name_id')) if item.get('name_id') else None
                    debug_entry.update({
                        "canvas_coords": {
                            "image": image_coords,
                            "border": border_coords,
                            "name": name_coords,
                        },
                        "actual_screen": _primary_screen_from_coords(image_coords) or (sx, sy),
                    })
                    debug_payload["rendered_items"].append(debug_entry)
            elif item_type == "marker":
                item.setdefault("entry_width", 180)
                item.setdefault("entry_expanded_width", item.get("entry_width", 180))
                item.setdefault("description_visible", False)
                item.setdefault("handle_width", 22)
                item.setdefault("border_color", "#00ff00")
                sx, sy = int(xw*self.zoom + self.pan_x), int(yw*self.zoom + self.pan_y)
                debug_entry = None
                if debug_payload is not None:
                    debug_entry = {
                        "type": "marker",
                        "text": item.get("text"),
                        "linked_map": item.get("linked_map"),
                        "world_position": (xw, yw),
                        "expected_screen": (sx, sy),
                    }
                entry = item.get("entry_widget")
                desired_text = item.get("text", "")
                if not entry or not entry.winfo_exists():
                    entry = ctk.CTkEntry(self.canvas, width=item.get("entry_width", 180))
                    entry.insert(0, desired_text)
                    entry.bind("<KeyRelease>", lambda e, i=item: self._on_marker_text_change(i, persist=False))
                    entry.bind("<FocusIn>", lambda e, i=item: self._on_marker_entry_focus_in(i))
                    entry.bind("<FocusOut>", lambda e, i=item: self._on_marker_entry_focus_out(i))
                    entry.bind("<Return>", lambda e, i=item: self._on_marker_entry_return(e, i))
                    entry.bind("<ButtonPress-1>", lambda e, i=item: self._on_marker_entry_press(e, i))
                    entry.bind("<ButtonRelease-1>", lambda e, i=item: self._on_marker_entry_click(e, i))
                    entry.bind("<Double-Button-1>", lambda e, i=item: self._on_marker_double_click(e, i))
                    entry.bind("<Button-3>", lambda e, i=item: self._on_item_right_click(e, i))
                    item["entry_widget"] = entry
                else:
                    current_text = entry.get()
                    if current_text != desired_text:
                        entry.delete(0, tk.END)
                        entry.insert(0, desired_text)
                self._update_marker_entry_dimensions(item)
                entry_id = item.get("canvas_ids", (None,))[0] if item.get("canvas_ids") else None
                if entry_id:
                    self.canvas.coords(entry_id, sx, sy)
                else:
                    entry_id = self.canvas.create_window(sx, sy, anchor='nw', window=entry)
                    item["entry_canvas_id"] = entry_id
                item["entry_canvas_id"] = entry_id
                focus_pending = item.pop("focus_pending", False)
                if focus_pending:
                    entry.focus_set(); entry.select_range(0, tk.END)
                entry_height = entry.winfo_reqheight() if entry.winfo_exists() else 28
                handle_width = item.get("handle_width", 22)
                handle_x = sx - handle_width - 6
                handle_widget = item.get("handle_widget")
                if not handle_widget or not handle_widget.winfo_exists():
                    handle_widget = ctk.CTkLabel(self.canvas, text="≡", width=handle_width, fg_color="#2f2f2f")
                    handle_widget.configure(cursor="fleur")
                    handle_widget.bind("<ButtonPress-1>", lambda e, i=item: self._on_marker_handle_press(e, i))
                    handle_widget.bind("<B1-Motion>", lambda e, i=item: self._on_marker_handle_drag(e, i))
                    handle_widget.bind("<ButtonRelease-1>", lambda e, i=item: self._on_marker_handle_release(e, i))
                    handle_widget.bind("<Double-Button-1>", lambda e, i=item: self._on_marker_double_click(e, i))
                    handle_widget.bind("<Button-3>", lambda e, i=item: self._on_item_right_click(e, i))
                    item["handle_widget"] = handle_widget
                handle_widget.configure(height=entry_height)
                handle_id = item.get("handle_canvas_id")
                if handle_id:
                    self.canvas.coords(handle_id, handle_x, sy)
                else:
                    handle_id = self.canvas.create_window(handle_x, sy, anchor='nw', window=handle_widget)
                    item["handle_canvas_id"] = handle_id
                border_color = item.get("border_color", "#00ff00")
                border_id = item.get("border_canvas_id")
                try:
                    self.canvas.update_idletasks()
                except tk.TclError:
                    pass
                entry_bbox = self.canvas.bbox(entry_id) if entry_id else None
                handle_bbox = self.canvas.bbox(handle_id) if handle_id else None
                entry_height_px = entry_height or entry.winfo_height()
                if not entry_bbox:
                    entry_width_px = entry.winfo_width() or entry.winfo_reqwidth() or item.get("entry_width", 180)
                    entry_bbox = (sx, sy, sx + entry_width_px, sy + entry_height_px)
                if handle_id and not handle_bbox:
                    handle_width_px = handle_widget.winfo_width() or handle_width
                    handle_height_px = handle_widget.winfo_height() or entry_height_px
                    handle_bbox = (handle_x, sy, handle_x + handle_width_px, sy + handle_height_px)
                xs, ys = [], []
                if entry_bbox:
                    xs.extend([entry_bbox[0], entry_bbox[2]])
                    ys.extend([entry_bbox[1], entry_bbox[3]])
                if handle_bbox:
                    xs.extend([handle_bbox[0], handle_bbox[2]])
                    ys.extend([handle_bbox[1], handle_bbox[3]])
                border_margin = item.get("border_margin", 4)
                if xs and ys:
                    bx1 = min(xs) - border_margin
                    by1 = min(ys) - border_margin
                    bx2 = max(xs) + border_margin
                    by2 = max(ys) + border_margin
                    if border_id:
                        self.canvas.coords(border_id, bx1, by1, bx2, by2)
                        self.canvas.itemconfig(border_id, outline=border_color)
                    else:
                        border_id = self.canvas.create_rectangle(
                            bx1, by1, bx2, by2, outline=border_color, width=3, fill=""
                        )
                        item["border_canvas_id"] = border_id
                    if border_id:
                        try:
                            self.canvas.tag_lower(border_id)
                            if self.base_id:
                                self.canvas.lift(border_id, self.base_id)
                        except tk.TclError:
                            pass
                        if entry_id:
                            try:
                                self.canvas.tag_raise(entry_id)
                            except tk.TclError:
                                pass
                        if handle_id:
                            try:
                                self.canvas.tag_raise(handle_id)
                            except tk.TclError:
                                pass
                else:
                    if border_id:
                        self.canvas.delete(border_id)
                        border_id = None
                        item["border_canvas_id"] = None
                item["border_canvas_id"] = border_id
                canvas_ids = [entry_id, handle_id]
                if border_id:
                    canvas_ids.append(border_id)
                item["canvas_ids"] = tuple(cid for cid in canvas_ids if cid)
                self._bind_item_events(item)
                if entry_id:
                    self.canvas.tag_bind(entry_id, "<Button-3>", lambda e, i=item: self._on_item_right_click(e, i))
                if focus_pending:
                    self._show_marker_description(item)
                else:
                    if item.get("description_visible"):
                        self._show_marker_description(item)
                self._refresh_marker_description_popup(item)
                if debug_entry is not None:
                    entry_coords = _safe_canvas_coords(item.get("entry_canvas_id")) if item.get("entry_canvas_id") else None
                    handle_coords = _safe_canvas_coords(item.get("handle_canvas_id")) if item.get("handle_canvas_id") else None
                    border_coords = _safe_canvas_coords(item.get("border_canvas_id")) if item.get("border_canvas_id") else None
                    debug_entry.update({
                        "canvas_coords": {
                            "entry": entry_coords,
                            "handle": handle_coords,
                            "border": border_coords,
                        },
                        "actual_screen": _primary_screen_from_coords(entry_coords) or (sx, sy),
                    })
                    debug_payload["rendered_items"].append(debug_entry)
            elif item_type in ["rectangle", "oval"]:
                shape_width_unscaled = item.get("width", DEFAULT_SHAPE_WIDTH); shape_height_unscaled = item.get("height", DEFAULT_SHAPE_HEIGHT)
                shape_width = shape_width_unscaled * self.zoom; shape_height = shape_height_unscaled * self.zoom
                if shape_width <=0 or shape_height <=0: continue
                sx, sy = int(xw*self.zoom + self.pan_x), int(yw*self.zoom + self.pan_y)
                debug_entry = None
                if debug_payload is not None:
                    debug_entry = {
                        "type": item_type,
                        "world_position": (xw, yw),
                        "expected_screen": (sx, sy),
                        "size": (shape_width, shape_height),
                        "fill": item.get("fill_color"),
                        "border_color": item.get("border_color"),
                    }
                fill_color = item.get("fill_color", "") if item.get("is_filled") else ""; border_color = item.get("border_color", "#000000")
                if item.get('canvas_ids') and item['canvas_ids'][0] is not None:
                    shape_id = item['canvas_ids'][0]
                    if item_type == "rectangle": self.canvas.coords(shape_id, sx, sy, sx + shape_width, sy + shape_height)
                    elif item_type == "oval": self.canvas.coords(shape_id, sx, sy, sx + shape_width, sy + shape_height)
                    self.canvas.itemconfig(shape_id, fill=fill_color, outline=border_color)
                else:
                    shape_id = None
                    if item_type == "rectangle": shape_id = self.canvas.create_rectangle(sx, sy, sx + shape_width, sy + shape_height, fill=fill_color, outline=border_color, width=2)
                    elif item_type == "oval": shape_id = self.canvas.create_oval(sx, sy, sx + shape_width, sy + shape_height, fill=fill_color, outline=border_color, width=2)
                    item['canvas_ids'] = (shape_id,) if shape_id else ();
                    if shape_id: self._bind_item_events(item)
                if debug_entry is not None:
                    primary_id = item.get('canvas_ids', (None,))[0] if item.get('canvas_ids') else None
                    primary_coords = _safe_canvas_coords(primary_id)
                    debug_entry.update({
                        "canvas_coords": {
                            "shape": primary_coords,
                        },
                        "actual_screen": _primary_screen_from_coords(primary_coords) or (sx, sy),
                    })
                    debug_payload["rendered_items"].append(debug_entry)
            elif item_type == "whiteboard":
                points = item.get("points") or []
                if not points or len(points) < 2:
                    continue
                screen_coords = []
                for px, py in points:
                    screen_coords.extend([self.pan_x + px * self.zoom, self.pan_y + py * self.zoom])
                color = item.get("color", "#FF0000")
                width = item.get("width", 4)
                debug_entry = None
                if debug_payload is not None:
                    debug_entry = {
                        "type": "whiteboard",
                        "world_position": points[0],
                        "expected_screen": (self.pan_x + points[0][0] * self.zoom, self.pan_y + points[0][1] * self.zoom),
                        "points": len(points),
                        "color": color,
                        "width": width,
                    }
                if item.get("canvas_ids"):
                    line_id = item["canvas_ids"][0]
                    try:
                        self.canvas.coords(line_id, *screen_coords)
                        self.canvas.itemconfig(
                            line_id,
                            fill=color,
                            width=width,
                            smooth=False,
                            capstyle="butt",
                            joinstyle="miter",
                        )
                    except tk.TclError:
                        item["canvas_ids"] = ()
                        line_id = None
                else:
                    line_id = None
                if not line_id:
                    try:
                        line_id = self.canvas.create_line(
                            *screen_coords,
                            fill=color,
                            width=width,
                            smooth=False,
                            capstyle="butt",
                            joinstyle="miter",
                        )
                        item["canvas_ids"] = (line_id,)
                    except tk.TclError:
                        item["canvas_ids"] = ()
                if debug_entry is not None:
                    debug_entry.update({
                        "canvas_coords": {
                            "polyline": _safe_canvas_coords(item.get("canvas_ids", (None,))[0]) if item.get("canvas_ids") else None,
                        },
                        "actual_screen": (screen_coords[0], screen_coords[1]) if screen_coords else debug_entry["expected_screen"],
                    })
                    debug_payload["rendered_items"].append(debug_entry)
            elif item_type == "text":
                text_value = item.get("text", "")
                color = item.get("color", self.whiteboard_color)
                size = int(item.get("text_size", getattr(self, "text_size", 24)))
                font = self._text_font_cache.tk_font(size)
                sx = int(self.pan_x + xw * self.zoom)
                sy = int(self.pan_y + yw * self.zoom)
                debug_entry = None
                if debug_payload is not None:
                    debug_entry = {
                        "type": "text",
                        "world_position": (xw, yw),
                        "expected_screen": (sx, sy),
                        "text": text_value,
                        "color": color,
                        "size": size,
                    }
                text_id = None
                if item.get("canvas_ids"):
                    text_id = item["canvas_ids"][0]
                    try:
                        self.canvas.coords(text_id, sx, sy)
                        self.canvas.itemconfig(text_id, text=text_value, fill=color, font=font)
                    except tk.TclError:
                        text_id = None
                if not text_id:
                    try:
                        text_id = self.canvas.create_text(sx, sy, text=text_value, fill=color, anchor="nw", font=font)
                        item["canvas_ids"] = (text_id,)
                        self._bind_item_events(item)
                    except tk.TclError:
                        item["canvas_ids"] = ()
                if debug_entry is not None:
                    debug_entry.update({
                        "canvas_coords": {
                            "text": _safe_canvas_coords(item.get("canvas_ids", (None,))[0]) if item.get("canvas_ids") else None,
                        },
                        "actual_screen": _primary_screen_from_coords(_safe_canvas_coords(text_id)) or (sx, sy),
                    })
                    debug_payload["rendered_items"].append(debug_entry)
        if debug_payload is not None:
            expected = debug_payload.get("expected_items", [])
            rendered = debug_payload.get("rendered_items", [])
            map_name = debug_payload.get("map_name", "<unknown>")
            log_info(
                f"Rendered map '{map_name}' with {len(rendered)} items (expected {len(expected)}). zoom={self.zoom}, pan=({self.pan_x}, {self.pan_y}).",
                func_name="DisplayMapController._update_canvas_images",
            )
            for entry in expected:
                log_debug(
                    f"Expected {entry.get('type')} at world {entry.get('world_position')} details={entry}.",
                    func_name="DisplayMapController._update_canvas_images",
                )
            for entry in rendered:
                log_debug(
                    f"Rendered {entry.get('type')} at world {entry.get('world_position')} screen={entry.get('actual_screen') or entry.get('screen_position') or entry.get('expected_screen')} details={entry}.",
                    func_name="DisplayMapController._update_canvas_images",
                )
            def _key_entry(entry):
                item_type = entry.get("type")
                if item_type == "token":
                    return (item_type, entry.get("entity_id"))
                if item_type == "marker":
                    return (item_type, entry.get("text"), entry.get("linked_map"))
                if item_type in ("rectangle", "oval"):
                    world = entry.get("world_position")
                    if isinstance(world, (list, tuple)):
                        world = tuple(world)
                    return (item_type, world)
                if item_type == "whiteboard":
                    world = entry.get("world_position")
                    if isinstance(world, (list, tuple)):
                        world = tuple(world)
                    return (item_type, world)
                return None

            def _compute_screen(world_pos):
                if isinstance(world_pos, (list, tuple)) and len(world_pos) >= 2:
                    try:
                        return (
                            int(world_pos[0] * self.zoom + self.pan_x),
                            int(world_pos[1] * self.zoom + self.pan_y),
                        )
                    except Exception:
                        return None
                return None

            def _index_entries(entries, *, compute_screen=False):
                index = {}
                for entry in entries:
                    key = _key_entry(entry)
                    if key is None:
                        continue
                    world_pos = entry.get("world_position")
                    if isinstance(world_pos, (list, tuple)):
                        world_tuple = tuple(world_pos)
                    else:
                        world_tuple = None
                    if compute_screen:
                        screen_pos = _compute_screen(world_pos)
                    else:
                        screen_pos = entry.get("actual_screen") or entry.get("screen_position") or entry.get("expected_screen")
                    index.setdefault(key, []).append(
                        {
                            "entry": entry,
                            "world": world_tuple,
                            "screen": screen_pos,
                        }
                    )
                return index

            expected_index = _index_entries(expected, compute_screen=True)
            rendered_index = _index_entries(rendered, compute_screen=False)

            def _identifier_details(item_type, entry):
                if item_type == "token":
                    return f"entity_type={entry.get('entity_type')}, entity_id={entry.get('entity_id')}"
                if item_type == "marker":
                    return f"text={entry.get('text')!r}, linked_map={entry.get('linked_map')!r}"
                if item_type in ("rectangle", "oval"):
                    width = entry.get("width")
                    height = entry.get("height")
                    if width is not None or height is not None:
                        return f"width={width}, height={height}"
                return ""

            expected_keys = set(expected_index.keys())
            rendered_keys = set(rendered_index.keys())

            for missing_key in expected_keys - rendered_keys:
                for info in expected_index.get(missing_key, []):
                    entry = info["entry"]
                    item_type = entry.get("type")
                    identifiers = _identifier_details(item_type, entry)
                    world = info.get("world")
                    screen = info.get("screen")
                    log_warning(
                        f"Missing rendered {item_type} ({identifiers}) expected at world {world} screen {screen} for key {missing_key}.",
                        func_name="DisplayMapController._update_canvas_images",
                    )

            for unexpected_key in rendered_keys - expected_keys:
                for info in rendered_index.get(unexpected_key, []):
                    entry = info["entry"]
                    item_type = entry.get("type")
                    identifiers = _identifier_details(item_type, entry)
                    world = info.get("world")
                    screen = info.get("screen")
                    log_warning(
                        f"Unexpected rendered {item_type} ({identifiers}) at world {world} screen {screen} for key {unexpected_key}.",
                        func_name="DisplayMapController._update_canvas_images",
                    )

            for common_key in expected_keys & rendered_keys:
                expected_entries = expected_index.get(common_key, [])
                rendered_entries = rendered_index.get(common_key, [])
                pair_count = min(len(expected_entries), len(rendered_entries))
                for idx in range(pair_count):
                    exp_info = expected_entries[idx]
                    ren_info = rendered_entries[idx]
                    exp_entry = exp_info["entry"]
                    ren_entry = ren_info["entry"]
                    item_type = exp_entry.get("type") or ren_entry.get("type")
                    identifiers = _identifier_details(item_type, exp_entry or ren_entry)
                    exp_world = exp_info.get("world")
                    exp_screen = exp_info.get("screen")
                    ren_world = ren_info.get("world")
                    ren_screen = ren_info.get("screen")
                    if exp_world != ren_world or exp_screen != ren_screen:
                        log_info(
                            f"Repositioned {item_type} ({identifiers}) key {common_key}: expected world {exp_world} screen {exp_screen}, rendered world {ren_world} screen {ren_screen}.",
                            func_name="DisplayMapController._update_canvas_images",
                        )

                if len(expected_entries) > pair_count:
                    for extra in expected_entries[pair_count:]:
                        entry = extra["entry"]
                        item_type = entry.get("type")
                        identifiers = _identifier_details(item_type, entry)
                        world = extra.get("world")
                        screen = extra.get("screen")
                        log_warning(
                            f"Missing rendered {item_type} ({identifiers}) expected at world {world} screen {screen} for key {common_key} (extra expected instance).",
                            func_name="DisplayMapController._update_canvas_images",
                        )
                if len(rendered_entries) > pair_count:
                    for extra in rendered_entries[pair_count:]:
                        entry = extra["entry"]
                        item_type = entry.get("type")
                        identifiers = _identifier_details(item_type, entry)
                        world = extra.get("world")
                        screen = extra.get("screen")
                        log_warning(
                            f"Unexpected rendered {item_type} ({identifiers}) at world {world} screen {screen} for key {common_key} (extra rendered instance).",
                            func_name="DisplayMapController._update_canvas_images",
                        )

            if len(rendered) != len(expected):
                log_warning(
                    f"Render count mismatch for map '{map_name}': expected {len(expected)} items but drew {len(rendered)}.",
                    func_name="DisplayMapController._update_canvas_images",
                )
            if debug_payload is not None:
                try:
                    stack_snapshot = tuple(reversed(self.canvas.find_all()))  # topmost first
                except tk.TclError:
                    stack_snapshot = ()
                if stack_snapshot:
                    log_debug(
                        f"Canvas stack top 15 IDs: {stack_snapshot[:15]}",
                        func_name="DisplayMapController._update_canvas_images",
                    )
            setattr(self, "_pending_render_debug_dump", None)
        self._update_selection_indicators()
        fs_canvas = getattr(self, "fs_canvas", None)
        if fs_canvas:
            try:
                if fs_canvas.winfo_exists():
                    self._update_fullscreen_map()
            except tk.TclError:
                pass
        if getattr(self, '_web_server_thread', None):
            self._update_web_display_map()

    def _bind_item_events(self, item):
        if item.get("type") == "whiteboard":
            return
        if not item.get('canvas_ids'): return
        ids_to_bind = item['canvas_ids']
        existing_ids = set(self.canvas.find_all())
        for cid in ids_to_bind:
            if not cid:
                continue
            if cid not in existing_ids:
                continue
            if item.get("type") == "marker" and cid == item.get("entry_canvas_id"):
                continue
            try:
                self.canvas.tag_bind(cid, "<ButtonPress-1>", lambda e, i=item: self._on_item_press(e, i))
                self.canvas.tag_bind(cid, "<B1-Motion>", lambda e, i=item: (self._on_item_move(e, i), "break")) # 'break' prevents event propagation
                self.canvas.tag_bind(cid, "<ButtonRelease-1>", lambda e, i=item: self._on_item_release(e, i))
                self.canvas.tag_bind(cid, "<Button-3>", lambda e, i=item: self._on_item_right_click(e, i))
            except tk.TclError:
                continue

            item_type = item.get("type", "token")
            if item_type == "token":
                 self.canvas.tag_bind(cid, "<Double-Button-1>", lambda e, i=item: self._on_token_double_click(e, i))
            elif item_type == "marker":
                 self.canvas.tag_bind(cid, "<Double-Button-1>", lambda e, i=item: self._on_marker_double_click(e, i))
            elif item_type == "text":
                 self.canvas.tag_bind(cid, "<Double-Button-1>", lambda e, i=item: self._on_text_double_click(e, i))
            # elif item_type in ["rectangle", "oval"]:
            # No double-click for handles; triggered by menu now.
            pass

    def _on_item_press(self, event, item):
        print(f"[DEBUG] _on_item_press: Item type: {item.get('type')}, ID/Name: {item.get('entity_id', item.get('canvas_ids'))}")
        if self._active_resize_handle_info: # If a resize drag is active, do nothing
            print("[DEBUG] _on_item_press: Active resize handle info exists, returning.")
            return

        item_is_active = self._prepare_item_selection(item, event)
        if not item_is_active:
            item.pop("drag_data", None)
            return

        for target in self._get_drag_targets(item):
            target["drag_data"] = {"x": event.x, "y": event.y, "moved": False}
        # Handles are only drawn if "Edit Shape" is chosen from context menu.

    def _on_item_move(self, event, item):
        if self._active_resize_handle_info and self._active_resize_handle_info.get('item') == item:
            # If currently resizing this item, let the handle move logic take over.
            return

        drag_data = item.get("drag_data")
        if not drag_data:
            return
        dx = event.x - drag_data["x"]
        dy = event.y - drag_data["y"]
        movement_started = abs(dx) > 2 or abs(dy) > 2
        targets = self._get_drag_targets(item)
        for target in targets:
            drag_info = target.setdefault("drag_data", {"x": event.x, "y": event.y, "moved": False})
            if movement_started and not drag_info.get("moved"):
                drag_info["moved"] = True
            self._apply_drag_delta_to_item(target, dx, dy)
            drag_info["x"] = event.x
            drag_info["y"] = event.y

        self._update_selection_indicators()


    def _on_item_release(self, event, item):
        # If a resize operation was active for this item, it's handled by _on_resize_handle_release
        if self._active_resize_handle_info and self._active_resize_handle_info.get('item') == item:
            # The actual release logic is in _on_resize_handle_release
            return

        drag_datas = []
        for target in self._get_drag_targets(item):
            drag_datas.append((target is item, target.pop("drag_data", None)))

        any_moved = any(data and data.get("moved") for _, data in drag_datas)
        primary_drag_data = next((data for is_primary, data in drag_datas if is_primary), None)

        if primary_drag_data and not any_moved:
            self._handle_item_click(event, item)
        self._persist_tokens()
        self._update_selection_indicators()

    def _get_drag_targets(self, primary_item):
        selection = [entry for entry in self.selected_items if entry]
        if selection and primary_item in selection:
            return selection
        return [primary_item]

    def _apply_drag_delta_to_item(self, item, dx, dy):
        if not dx and not dy:
            return

        for cid in item.get("canvas_ids", []) or []:
            if not cid:
                continue
            try:
                self.canvas.move(cid, dx, dy)
            except tk.TclError:
                continue

        item_type = item.get("type", "token")

        if item_type == "token":
            name_id = item.get("name_id")
            if name_id:
                try:
                    self.canvas.move(name_id, dx, dy)
                except tk.TclError:
                    pass
            if item.get("hp_canvas_ids"):
                for hp_cid in item["hp_canvas_ids"]:
                    if not hp_cid:
                        continue
                    try:
                        self.canvas.move(hp_cid, dx, dy)
                    except tk.TclError:
                        continue
            if item.get("defense_canvas_ids"):
                for def_cid in item["defense_canvas_ids"]:
                    if not def_cid:
                        continue
                    try:
                        self.canvas.move(def_cid, dx, dy)
                    except tk.TclError:
                        continue
            main_id = item.get("canvas_ids", (None,))[0]
            bbox = None
            if main_id:
                try:
                    bbox = self.canvas.bbox(main_id)
                except tk.TclError:
                    bbox = None
            if bbox:
                item["hover_bbox"] = bbox
            self._refresh_token_hover_popup(item)
            if item.get("hover_visible"):
                self._show_token_hover(item)
        elif item_type == "marker":
            self._refresh_marker_description_popup(item)

        main_canvas_id = item.get("canvas_ids", (None,))[0] if item.get("canvas_ids") else None
        coords = None
        if main_canvas_id:
            try:
                coords = self.canvas.coords(main_canvas_id)
            except tk.TclError:
                coords = None
        if coords:
            sx, sy = coords[0], coords[1]
            item["position"] = ((sx - self.pan_x) / self.zoom, (sy - self.pan_y) / self.zoom)

        if item == self._graphical_edit_mode_item and item_type in ["rectangle", "oval"]:
            self._draw_resize_handles(item)

    def _handle_item_click(self, event, item):
        item_type = item.get("type", "token")
        if item_type == "token":
            if item.get("hover_visible"):
                self._hide_token_hover(item)
            else:
                self._hide_all_marker_descriptions()
                self._hide_all_token_hovers()
                self._show_token_hover(item)
        elif item_type == "marker":
            if item.get("description_visible"):
                self._hide_marker_description(item)
            else:
                self._hide_all_token_hovers()
                self._hide_all_marker_descriptions()
                self._show_marker_description(item)

    def _on_marker_double_click(self, event, marker):
        if self._open_marker_linked_map(marker, silent=True):
            return "break"
        return None

    def _on_text_double_click(self, event, text_item):
        current_text = text_item.get("text", "")
        updated = prompt_for_text(self.canvas, title="Edit Text", prompt="Update text:", initial=current_text)
        if updated is None or updated == current_text:
            return "break"
        text_item["text"] = updated
        self._update_canvas_images(resample=self._fast_resample)
        self._persist_tokens()
        return "break"

    def _on_item_right_click(self, event, item):
        if not self._ensure_selection_for_context_menu(item):
            return
        selection = list(self.selected_items) or ([])
        if not selection and self.selected_token:
            selection = [self.selected_token]
        if not selection:
            selection = [item]

        categories = {self._get_item_category(entry) for entry in selection if self._get_item_category(entry)}
        if not categories or len(categories) != 1:
            return

        category = categories.pop()
        if category == "token":
            tokens = [entry for entry in selection if self._get_item_category(entry) == "token"]
            return self._on_token_right_click(event, tokens, item)
        if category == "shape":
            shapes = [entry for entry in selection if self._get_item_category(entry) == "shape"]
            return self._show_shape_menu(event, shapes)
        if category == "marker":
            markers = [entry for entry in selection if self._get_item_category(entry) == "marker"]
            return self._show_marker_menu(event, markers)

    def _show_shape_menu(self, event, shapes):
        valid_shapes = [s for s in shapes if isinstance(s, dict) and s.get("type") in ("rectangle", "oval")]
        if not valid_shapes:
            return

        count = len(valid_shapes)
        plural = "s" if count != 1 else ""
        menu = tk.Menu(self.canvas, tearoff=0)

        if count == 1:
            menu.add_command(
                label="Edit Shape Graphically",
                command=lambda: self._activate_graphical_resize(valid_shapes[0]),
            )

        menu.add_command(
            label=f"Edit Color{plural}",
            command=lambda: self._edit_shapes_color(valid_shapes),
        )
        menu.add_command(
            label=f"Edit Dimensions (Numeric)",
            command=lambda: self._resize_shapes_dialog(valid_shapes),
        )
        menu.add_command(
            label=f"Toggle Fill{plural}",
            command=lambda: self._toggle_shapes_fill(valid_shapes),
        )
        menu.add_separator()
        menu.add_command(
            label=f"Copy Shape{plural}", command=lambda: self._copy_item(valid_shapes)
        )
        menu.add_command(
            label=f"Delete Shape{plural}", command=lambda: self._delete_items(valid_shapes)
        )
        menu.add_separator()
        menu.add_command(
            label="Bring to Front", command=lambda: self._bring_items_to_front(valid_shapes)
        )
        menu.add_command(
            label="Send to Back", command=lambda: self._send_items_to_back(valid_shapes)
        )

        menu.tk_popup(event.x_root, event.y_root)

    def _edit_shapes_color(self, shapes):
        valid_shapes = [s for s in shapes if isinstance(s, dict) and s.get("type") in ("rectangle", "oval")]
        if not valid_shapes:
            return

        reference = valid_shapes[0]
        current_fill = reference.get("fill_color", self.current_shape_fill_color)
        fill_res = colorchooser.askcolor(
            parent=self.canvas,
            color=current_fill,
            title="Choose Shape Fill Color",
        )

        current_border = reference.get("border_color", self.current_shape_border_color)
        border_res = colorchooser.askcolor(
            parent=self.canvas,
            color=current_border,
            title="Choose Shape Border Color",
        )

        if fill_res and fill_res[1]:
            for shape in valid_shapes:
                shape["fill_color"] = fill_res[1]

        if border_res and border_res[1]:
            for shape in valid_shapes:
                shape["border_color"] = border_res[1]

        if (fill_res and fill_res[1]) or (border_res and border_res[1]):
            self._update_canvas_images()
            self._persist_tokens()

    def _resize_shapes_dialog(self, shapes):
        valid_shapes = [s for s in shapes if isinstance(s, dict) and s.get("type") in ("rectangle", "oval")]
        if not valid_shapes:
            return

        reference = valid_shapes[0]
        width = reference.get("width", DEFAULT_SHAPE_WIDTH)
        height = reference.get("height", DEFAULT_SHAPE_HEIGHT)

        new_width = tk.simpledialog.askinteger(
            "Resize Shape",
            "New Width (pixels):",
            parent=self.canvas,
            initialvalue=width,
            minvalue=1,
        )
        if new_width is None:
            return

        new_height = tk.simpledialog.askinteger(
            "Resize Shape",
            "New Height (pixels):",
            parent=self.canvas,
            initialvalue=height,
            minvalue=1,
        )
        if new_height is None:
            return

        for shape in valid_shapes:
            shape["width"] = new_width
            shape["height"] = new_height

        self._update_canvas_images()
        self._persist_tokens()

    def _toggle_shapes_fill(self, shapes):
        valid_shapes = [s for s in shapes if isinstance(s, dict) and s.get("type") in ("rectangle", "oval")]
        if not valid_shapes:
            return
        for shape in valid_shapes:
            shape["is_filled"] = not shape.get("is_filled", True)
        self._update_canvas_images()
        self._persist_tokens()

    def _edit_shape_color_dialog(self, shape):
        self._edit_shapes_color([shape])

    def _resize_shape_dialog(self, shape):
        self._resize_shapes_dialog([shape])

    # _adjust_shape_size_relative method is removed as per request.

    def _resize_tokens(self, tokens):
        valid_tokens = [t for t in tokens if isinstance(t, dict) and t.get("type") == "token"]
        if not valid_tokens:
            return

        reference = valid_tokens[0]
        current_size = reference.get("size", self.token_size)

        try:
            import tkinter.simpledialog as simpledialog
            new_size = simpledialog.askinteger(
                "Resize Token",
                "New Size (pixels):",
                parent=self.canvas,
                initialvalue=current_size,
                minvalue=8,
            )
        except (ImportError, tk.TclError):
            return

        if not new_size or new_size <= 0:
            return

        for token in valid_tokens:
            self._apply_token_size(token, new_size)

        self._update_canvas_images()
        self._persist_tokens()

    def _apply_token_size(self, token, new_size):
        token["size"] = new_size
        source_img = token.get("source_image")

        if "image_path" in token and token["image_path"]:
            resolved_path = _resolve_campaign_path(token["image_path"])
            try:
                if source_img is None and resolved_path:
                    source_img = Image.open(resolved_path).convert("RGBA")
                if source_img is not None:
                    token["source_image"] = source_img
                    token["pil_image"] = source_img.resize((new_size, new_size), Image.LANCZOS)
            except FileNotFoundError:
                print(f"Error: Image file not found for token: {resolved_path}")
            except Exception as exc:
                print(f"Error reloading image for resized token: {exc}")
        elif source_img is not None:
            token["pil_image"] = source_img.resize((new_size, new_size), Image.LANCZOS)

    def _resize_token_dialog(self, token):
        if not token or token.get("type") != "token":
            return
        self._resize_tokens([token])
    def _show_token_menu(self, event, tokens):
        valid_tokens = [t for t in tokens if isinstance(t, dict) and t.get("type") == "token"]
        if not valid_tokens:
            return

        count = len(valid_tokens)
        plural = "s" if count != 1 else ""
        menu = tk.Menu(self.canvas, tearoff=0)

        menu.add_command(
            label=f"Resize Token{plural}",
            command=lambda: self._resize_tokens(valid_tokens),
        )
        menu.add_command(
            label=f"Change Border Color{plural}",
            command=lambda: self._prompt_change_token_border_color(valid_tokens),
        )

        menu.add_separator()
        menu.add_command(
            label=f"Copy Token{plural}",
            command=lambda: self._copy_item(valid_tokens),
        )
        menu.add_command(
            label=f"Delete Token{plural}",
            command=lambda: self._delete_items(valid_tokens),
        )
        menu.add_separator()
        menu.add_command(
            label=f"Bring to Front", command=lambda: self._bring_items_to_front(valid_tokens)
        )
        menu.add_command(
            label=f"Send to Back", command=lambda: self._send_items_to_back(valid_tokens)
        )

        if count == 1 and valid_tokens[0].get("image_path"):
            menu.add_command(
                label="Show Portrait",
                command=lambda: show_portrait(
                    valid_tokens[0]["image_path"],
                    valid_tokens[0].get("entity_id")
                    or valid_tokens[0].get("entity_type")
                    or "Entity",
                ),
            )
        elif count > 1:
            menu.add_command(
                label="Show Portraits",
                command=lambda: self._show_portraits_for_tokens(valid_tokens),
            )

        audio_tokens = [t for t in valid_tokens if self._get_token_audio_value(t)]
        if audio_tokens:
            menu.add_separator()
            menu.add_command(
                label="Play Audio", command=lambda: self._play_audio_for_tokens(audio_tokens)
            )
            menu.add_command(label="Stop Audio", command=stop_entity_audio)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError as e:
            print(f"Error displaying token menu: {e}")

    def _show_portraits_for_tokens(self, tokens):
        for token in tokens:
            path = token.get("image_path")
            if path:
                show_portrait(
                    path,
                    token.get("entity_id") or token.get("entity_type") or "Entity",
                )

    def _play_audio_for_tokens(self, tokens):
        for token in tokens:
            self._play_token_audio(token)

    def _get_token_audio_value(self, token):
        value = get_entity_audio_value(token.get("entity_record"))
        if value:
            return value
        entity_type = token.get("entity_type")
        entity_id = token.get("entity_id")
        wrapper = self._model_wrappers.get(entity_type)
        if not wrapper or not entity_id:
            return ""
        try:
            for item in wrapper.load_items():
                if item.get("Name") == entity_id:
                    raw_value = get_entity_audio_value(item)
                    if raw_value:
                        return raw_value
        except Exception:
            return ""
        return ""

    def _play_token_audio(self, token):
        audio_value = self._get_token_audio_value(token)
        if not audio_value:
            messagebox.showinfo("Audio", "No audio file configured for this token.")
            return
        name = token.get("entity_id") or token.get("entity_type") or "Entity"
        if not play_entity_audio(audio_value, entity_label=str(name)):
            messagebox.showwarning("Audio", f"Unable to play audio for {name}.")

    def _prompt_change_token_border_color(self, tokens):
        valid_tokens = [t for t in tokens if isinstance(t, dict) and t.get("type") == "token"]
        if not valid_tokens:
            return

        current_color = valid_tokens[0].get("border_color", "#0000FF")
        new_color_tuple = colorchooser.askcolor(
            parent=self.canvas,
            color=current_color,
            title="Choose Token Border Color",
        )

        if not new_color_tuple or not new_color_tuple[1]:
            return

        new_color = new_color_tuple[1]
        for token in valid_tokens:
            token["border_color"] = new_color

        self._update_canvas_images()
        self._persist_tokens()
    def _toggle_shape_fill(self, shape):
        self._toggle_shapes_fill([shape])

    def _delete_items(self, items):
        for item in list(items):
            self._delete_item(item)

    def _bring_items_to_front(self, items):
        for item in items:
            self._bring_item_to_front(item)

    def _send_items_to_back(self, items):
        for item in items:
            self._send_item_to_back(item)

    def _copy_item(self, item_to_copy=None):
        if isinstance(item_to_copy, (list, tuple, set)):
            candidates = [itm for itm in item_to_copy if isinstance(itm, dict)]
        elif item_to_copy is not None:
            candidates = [item_to_copy]
        elif self.selected_items:
            candidates = list(self.selected_items)
        elif self.selected_token:
            candidates = [self.selected_token]
        else:
            candidates = []

        if not candidates:
            self.clipboard_token = None
            return

        reference_position = None
        for item in candidates:
            pos = item.get("position") if isinstance(item, dict) else None
            if pos:
                reference_position = pos
                break
        if reference_position is None:
            reference_position = (0, 0)

        clipboard_entries = []
        for item in candidates:
            clone = self._clone_item_for_clipboard(item, reference_position)
            if clone:
                clipboard_entries.append(clone)

        self.clipboard_token = clipboard_entries if clipboard_entries else None

    def _clipboard_value_should_skip(self, value):
        if value is None:
            return False

        module_name = getattr(getattr(value, "__class__", None), "__module__", "") or ""
        if module_name.startswith(("tkinter", "_tkinter", "customtkinter")):
            return True

        if isinstance(value, (tk.Misc, tk.Variable, tkfont.Font)):
            return True

        if hasattr(value, "winfo_exists"):
            return True

        try:
            if isinstance(value, ImageTk.PhotoImage):
                return True
        except Exception:
            pass

        return False

    def _sanitize_clipboard_structure(self, value, memo=None):
        if memo is None:
            memo = {}

        obj_id = id(value)
        if obj_id in memo:
            return memo[obj_id]

        if self._clipboard_value_should_skip(value):
            return CLIPBOARD_SKIP

        if isinstance(value, dict):
            sanitized_dict = {}
            memo[obj_id] = sanitized_dict
            for key, item in value.items():
                sanitized_key = self._sanitize_clipboard_structure(key, memo)
                sanitized_value = self._sanitize_clipboard_structure(item, memo)
                if sanitized_key is CLIPBOARD_SKIP or sanitized_value is CLIPBOARD_SKIP:
                    continue
                sanitized_dict[sanitized_key] = sanitized_value
            return sanitized_dict

        if isinstance(value, list):
            sanitized_list = []
            memo[obj_id] = sanitized_list
            for item in value:
                sanitized_item = self._sanitize_clipboard_structure(item, memo)
                if sanitized_item is CLIPBOARD_SKIP:
                    continue
                sanitized_list.append(sanitized_item)
            return sanitized_list

        if isinstance(value, tuple):
            sanitized_tuple_items = []
            memo[obj_id] = sanitized_tuple_items
            for item in value:
                sanitized_item = self._sanitize_clipboard_structure(item, memo)
                if sanitized_item is CLIPBOARD_SKIP:
                    continue
                sanitized_tuple_items.append(sanitized_item)
            sanitized_tuple = tuple(sanitized_tuple_items)
            memo[obj_id] = sanitized_tuple
            return sanitized_tuple

        if isinstance(value, set):
            sanitized_set = set()
            memo[obj_id] = sanitized_set
            for item in value:
                sanitized_item = self._sanitize_clipboard_structure(item, memo)
                if sanitized_item is CLIPBOARD_SKIP:
                    continue
                sanitized_set.add(sanitized_item)
            return sanitized_set

        if isinstance(value, (int, float, str, bool, type(None))):
            memo[obj_id] = value
            return value

        try:
            sanitized_value = copy.deepcopy(value)
        except Exception:
            sanitized_value = value
        memo[obj_id] = sanitized_value
        return sanitized_value

    def _clone_item_for_clipboard(self, item, reference_position):
        if not isinstance(item, dict):
            return None

        clone = dict(item)
        keys_to_remove = [
            "pil_image",
            "source_image",
            "tk_image",
            "entity_record",
            "canvas_ids",
            "hp_canvas_ids",
            "defense_canvas_ids",
            "name_id",
            "hp_entry_widget",
            "hp_entry_widget_id",
            "max_hp_entry_widget",
            "max_hp_entry_widget_id",
            "entry_widget",
            "description_popup",
            "description_label",
            "handle_widget",
            "handle_canvas_id",
            "entry_canvas_id",
            "border_canvas_id",
            "description_editor",
            "hover_popup",
            "hover_label",
            "hover_bbox",
            "hover_visible",
            "fs_canvas_ids",
            "fs_cross_ids",
            "drag_data",
        ]
        for key in keys_to_remove:
            clone.pop(key, None)

        clone = self._sanitize_clipboard_structure(clone)
        if clone is CLIPBOARD_SKIP:
            return None

        pos = item.get("position") if isinstance(item.get("position"), tuple) else clone.get("position")
        try:
            offset = (
                float(pos[0]) - float(reference_position[0]),
                float(pos[1]) - float(reference_position[1]),
            ) if pos else (0.0, 0.0)
        except Exception:
            offset = (0.0, 0.0)

        clone.pop("_clipboard_offset", None)
        clone["_clipboard_offset"] = offset
        return clone

    def _paste_item(self, event=None):
        if not self.clipboard_token:
            return

        clipboard_items = (
            list(self.clipboard_token)
            if isinstance(self.clipboard_token, list)
            else [self.clipboard_token]
        )
        if not clipboard_items:
            return

        vcx, vcy = 100, 100
        if self.canvas:
            vcx = (self.canvas.winfo_width() // 2 - self.pan_x) / self.zoom
            vcy = (self.canvas.winfo_height() // 2 - self.pan_y) / self.zoom

            try:
                pointer_x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
                pointer_y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
            except tk.TclError:
                pointer_x = pointer_y = None
            else:
                if (
                    pointer_x is not None
                    and pointer_y is not None
                    and 0 <= pointer_x <= self.canvas.winfo_width()
                    and 0 <= pointer_y <= self.canvas.winfo_height()
                ):
                    zoom = self.zoom if self.zoom else 1.0
                    vcx = (pointer_x - self.pan_x) / zoom
                    vcy = (pointer_y - self.pan_y) / zoom

        pasted_items = []
        for entry in clipboard_items:
            if not isinstance(entry, dict):
                continue
            new_item_data = self._sanitize_clipboard_structure(entry)
            if new_item_data is CLIPBOARD_SKIP:
                continue
            offset = new_item_data.pop("_clipboard_offset", (0, 0))
            try:
                ox, oy = offset
            except Exception:
                ox = oy = 0
            position = (vcx + ox, vcy + oy)
            new_item_data["position"] = position
            new_item_data["canvas_ids"] = ()

            item_type = new_item_data.get("type", "token")

            if item_type == "token":
                image_path = new_item_data.get("image_path")
                if image_path:
                    try:
                        resolved_path = _resolve_campaign_path(image_path)
                        if not resolved_path or not os.path.exists(resolved_path):
                            raise FileNotFoundError(resolved_path or image_path)
                        sz = new_item_data.get("size", self.token_size)
                        source_img = Image.open(resolved_path).convert("RGBA")
                        new_item_data["source_image"] = source_img
                        new_item_data["pil_image"] = source_img.resize((sz, sz), Image.LANCZOS)
                    except Exception as exc:
                        print(f"Error reloading image for pasted token: {exc}")
                        new_item_data["source_image"] = None
                        new_item_data["pil_image"] = None
                else:
                    new_item_data["source_image"] = None
                    new_item_data["pil_image"] = None
                new_item_data["hover_visible"] = False
                new_item_data.pop("hover_popup", None)
                new_item_data.pop("hover_label", None)
                new_item_data.pop("hover_bbox", None)
            elif item_type == "marker":
                new_item_data.setdefault("text", "New Marker")
                new_item_data.setdefault("description", "Marker description")
                new_item_data.setdefault("border_color", "#00ff00")
                new_item_data.setdefault("linked_map", "")
                new_item_data["entry_widget"] = None
                new_item_data["description_popup"] = None
                new_item_data["description_label"] = None
                new_item_data["description_visible"] = False
                new_item_data.setdefault("entry_width", 180)
                new_item_data["description_editor"] = None
                new_item_data["focus_pending"] = True
                new_item_data["handle_widget"] = None
                new_item_data["handle_canvas_id"] = None
                new_item_data["entry_canvas_id"] = None
                new_item_data["border_canvas_id"] = None
            elif item_type in ["rectangle", "oval"]:
                new_item_data.setdefault("shape_type", item_type)
                new_item_data.setdefault("width", DEFAULT_SHAPE_WIDTH)
                new_item_data.setdefault("height", DEFAULT_SHAPE_HEIGHT)
                new_item_data.setdefault("fill_color", self.current_shape_fill_color)
                new_item_data.setdefault("border_color", self.current_shape_border_color)
                new_item_data.setdefault("is_filled", self.shape_is_filled)

            self.tokens.append(new_item_data)
            pasted_items.append(new_item_data)

        if not pasted_items:
            return

        self._update_canvas_images()
        self._persist_tokens()
        self._set_selection(pasted_items)

    def _delete_item(self, item_to_delete):
        if not item_to_delete: return
        if item_to_delete.get("canvas_ids"):
            for cid in item_to_delete["canvas_ids"]:
                if cid: self.canvas.delete(cid)
        if item_to_delete.get("type", "token") == "token":
            if item_to_delete.get("name_id"): self.canvas.delete(item_to_delete["name_id"])
            if item_to_delete.get("hp_canvas_ids"):
                for hp_cid in item_to_delete["hp_canvas_ids"]:
                    if hp_cid: self.canvas.delete(hp_cid)
            if item_to_delete.get("defense_canvas_ids"):
                for def_cid in item_to_delete["defense_canvas_ids"]:
                    if def_cid: self.canvas.delete(def_cid)
            popup = item_to_delete.get("hover_popup")
            if popup and popup.winfo_exists():
                popup.destroy()
            item_to_delete["hover_popup"] = None
            item_to_delete["hover_label"] = None
            item_to_delete["hover_visible"] = False
            item_to_delete.pop("hover_bbox", None)
        elif item_to_delete.get("type") == "marker":
            entry_widget = item_to_delete.get("entry_widget")
            if entry_widget and entry_widget.winfo_exists():
                entry_widget.destroy()
            popup = item_to_delete.get("description_popup")
            if popup and popup.winfo_exists():
                popup.destroy()
            editor = item_to_delete.get("description_editor")
            if editor and editor.winfo_exists():
                editor.destroy()
            handle_widget = item_to_delete.get("handle_widget")
            if handle_widget and handle_widget.winfo_exists():
                handle_widget.destroy()
        # Clean up fullscreen canvas artifacts if present
        if getattr(self, "fs_canvas", None):
            if item_to_delete.get("fs_canvas_ids"):
                for fs_id in item_to_delete["fs_canvas_ids"]:
                    if fs_id:
                        try:
                            self.fs_canvas.delete(fs_id)
                        except tk.TclError:
                            pass
                del item_to_delete["fs_canvas_ids"]
            if item_to_delete.get("fs_cross_ids"):
                for fs_id in item_to_delete["fs_cross_ids"]:
                    if fs_id:
                        try:
                            self.fs_canvas.delete(fs_id)
                        except tk.TclError:
                            pass
                del item_to_delete["fs_cross_ids"]
        if item_to_delete in self.tokens: self.tokens.remove(item_to_delete)
        if item_to_delete in self.selected_items or self.selected_token is item_to_delete:
            remaining = [itm for itm in self.selected_items if itm is not item_to_delete]
            self._set_selection(remaining)
        if getattr(self, "_hovered_marker", None) is item_to_delete:
            self._hovered_marker = None
        self._persist_tokens(); self._update_canvas_images()
        try:
            if getattr(self, 'fs_canvas', None) and self.fs_canvas.winfo_exists():
                self._update_fullscreen_map()
            if getattr(self, '_web_server_thread', None):
                self._update_web_display_map()
        except tk.TclError:
            pass

    def _bring_item_to_front(self, item):
        if item in self.tokens:
            self.tokens.remove(item); self.tokens.append(item)
            if item.get('canvas_ids'):
                for cid_lift in item['canvas_ids']:
                    if cid_lift: self.canvas.lift(cid_lift)
            if item.get("type", "token") == "token":
                if item.get('name_id'): self.canvas.lift(item['name_id'])
                if item.get('hp_canvas_ids'):
                    for hp_cid_lift in item['hp_canvas_ids']:
                        if hp_cid_lift: self.canvas.lift(hp_cid_lift)
                if item.get('defense_canvas_ids'):
                    for def_cid_lift in item['defense_canvas_ids']:
                        if def_cid_lift: self.canvas.lift(def_cid_lift)
            elif item.get("type") == "marker":
                popup = item.get("description_popup")
                if popup and popup.winfo_exists():
                    popup.lift()
            self._update_canvas_images(); self._persist_tokens()

    def _send_item_to_back(self, item):
        if item in self.tokens:
            item_description = f"{item.get('type')} - {item.get('entity_id', item.get('canvas_ids'))}"
            print(f"[DEBUG] _send_item_to_back: Sending item to back: {item_description}")
            self.tokens.remove(item)
            self.tokens.insert(0, item) # Move item to the beginning of the logical list

            canvas_ids_to_manage = []
            if item.get('canvas_ids'):
                canvas_ids_to_manage.extend(c_id for c_id in item['canvas_ids'] if c_id)
            
            if item.get("type", "token"): # Tokens have additional elements
                if item.get('name_id'):
                    canvas_ids_to_manage.append(item['name_id'])
                if item.get('hp_canvas_ids'):
                    canvas_ids_to_manage.extend(hp_id for hp_id in item['hp_canvas_ids'] if hp_id)
                if item.get('defense_canvas_ids'):
                    canvas_ids_to_manage.extend(def_id for def_id in item['defense_canvas_ids'] if def_id)
                # Token hover popups are separate toplevel windows and managed outside the canvas stacking order.
            # Marker popups are separate toplevel windows and are not managed via canvas stacking.

            for c_id in canvas_ids_to_manage:
                if c_id:
                    self.canvas.lower(c_id) # Send to absolute bottom first
                    if self.base_id: # If map base image exists
                        self.canvas.lift(c_id, self.base_id) # Then lift it just above the map base image
            
            self._update_canvas_images() # Redraw everything; other items will be drawn on top
            self._persist_tokens()
            
    def _on_max_hp_menu_click(self, event, token):
        if "max_hp_entry_widget" in token:
            self.canvas.delete(token["max_hp_entry_widget_id"])
            if hasattr(token["max_hp_entry_widget"], 'destroy'): token["max_hp_entry_widget"].destroy()
            del token["max_hp_entry_widget"], token["max_hp_entry_widget_id"]
        if not token.get("hp_canvas_ids"): return
        cid, tid = token["hp_canvas_ids"];
        if not tid : return
        self.canvas.itemconfigure(tid, state="hidden"); x, y = self.canvas.coords(tid)
        entry = ctk.CTkEntry(self.canvas, width=50); entry.insert(0, str(token.get("max_hp", 0)))
        entry_id = self.canvas.create_window(x, y, window=entry, anchor="center")
        token["max_hp_entry_widget"] = entry; token["max_hp_entry_widget_id"] = entry_id
        # Ensure focus + selection for immediate overwrite
        try: entry.focus_set(); entry.select_range(0, tk.END)
        except Exception: pass
        try: self.canvas.after(10, lambda e=entry: (e.focus_set(), e.select_range(0, tk.END)))
        except Exception: pass
        try: entry.bind("<FocusIn>", lambda e: e.widget.select_range(0, tk.END))
        except Exception: pass
        entry.bind("<Return>", lambda e: self._on_max_hp_entry_commit(e, token))

    def _on_max_hp_entry_commit(self, event, token):
        entry = token.get("max_hp_entry_widget"); entry_id = token.get("max_hp_entry_widget_id")
        if not entry: return
        raw = entry.get().strip()
        try: new_max = int(raw)
        except ValueError: new_max = token.get("max_hp", 1)
        new_max = max(1, new_max); cur_hp = token.get("hp", 0); cur_hp = min(cur_hp, new_max)
        token["hp"] = new_max; token["max_hp"] = new_max
        self.canvas.delete(entry_id);
        if hasattr(entry, 'destroy'): entry.destroy()
        if "max_hp_entry_widget" in token: del token["max_hp_entry_widget"]
        if "max_hp_entry_widget_id" in token: del token["max_hp_entry_widget_id"]
        if not token.get("hp_canvas_ids"): return
        cid, tid = token["hp_canvas_ids"];
        if not tid: return
        self.canvas.itemconfigure(tid, state="normal", text=f"{new_max}")
        
    def _on_hp_double_click(self, event, token):
        for attr in ("_zoom_after_id", "_zoom_final_after_id"):
            zid = getattr(self, attr, None)
            if not zid:
                setattr(self, attr, None)
                continue
            try:
                self.canvas.after_cancel(zid)
            except tk.TclError:
                pass
            finally:
                setattr(self, attr, None)
        if "hp_entry_widget" in token:
            self.canvas.delete(token["hp_entry_widget_id"])
            if hasattr(token["hp_entry_widget"], 'destroy'): token["hp_entry_widget"].destroy()
            del token["hp_entry_widget"], token["hp_entry_widget_id"]
        if not token.get("hp_canvas_ids"): return
        cid, tid = token["hp_canvas_ids"];
        if not tid: return
        self.canvas.itemconfigure(tid, state="hidden"); x, y = self.canvas.coords(tid)
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height(); margin = 20
        x = min(max(x, margin), cw - margin); y = min(max(y, margin), ch - margin)
        entry = ctk.CTkEntry(self.canvas, width=50); entry.insert(0, str(token.get("hp", 0)))
        entry_id = self.canvas.create_window(x, y, window=entry, anchor="center")
        self.canvas.lift(entry_id); self.canvas.update_idletasks()
        token["hp_entry_widget"] = entry; token["hp_entry_widget_id"] = entry_id
        # Ensure focus lands on the entry and current value is selected for immediate typing
        try: entry.focus_set(); entry.select_range(0, tk.END)
        except Exception: pass
        # Reinforce after the widget is mapped to handle focus races
        try: self.canvas.after(10, lambda e=entry: (e.focus_set(), e.select_range(0, tk.END)))
        except Exception: pass
        # If focus changes later, keep selection to allow direct +/- input
        try: entry.bind("<FocusIn>", lambda e: e.widget.select_range(0, tk.END))
        except Exception: pass
        entry.bind("<Return>", lambda e: self._on_hp_entry_commit(e, token))

    def _on_hp_entry_commit(self, event, token):
        entry = token.get("hp_entry_widget"); entry_id = token.get("hp_entry_widget_id")
        if not entry: return
        raw = entry.get().strip()
        try:
            if raw.startswith(("+", "-")): new_hp = token["hp"] + int(raw)
            else: new_hp = int(raw)
        except ValueError: new_hp = token["hp"]
        max_hp = token.get("max_hp", new_hp); new_hp = max(0, min(new_hp, max_hp)); token["hp"] = new_hp
        self.canvas.delete(entry_id);
        if hasattr(entry, 'destroy'): entry.destroy()
        if "hp_entry_widget" in token: del token["hp_entry_widget"]
        if "hp_entry_widget_id" in token: del token["hp_entry_widget_id"]
        if not token.get("hp_canvas_ids"): return
        cid, tid = token["hp_canvas_ids"];
        if not cid or not tid: return
        self.canvas.itemconfigure(tid, state="normal", text=str(new_hp))
        fill_color_hp = 'red' if new_hp/max_hp < 0.25 else 'green'
        self.canvas.itemconfig(cid, fill=fill_color_hp)
        
    def on_resize(self): self._update_canvas_images()

    def on_zoom(self, event):
        xw = (event.x - self.pan_x) / self.zoom; yw = (event.y - self.pan_y) / self.zoom
        delta = event.delta / 120; zoom_factor = 1 + (ZOOM_STEP * delta if ZOOM_STEP > 0 else 0.1 * delta)
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom * zoom_factor))
        self.pan_x = event.x - xw*self.zoom; self.pan_y = event.y - yw*self.zoom
        zid = getattr(self, "_zoom_after_id", None)
        if zid:
            try:
                self.canvas.after_cancel(zid)
            except tk.TclError:
                pass
            finally:
                self._zoom_after_id = None
        else:
            self._zoom_after_id = None
        self._zoom_after_id = self.canvas.after(50, lambda: self._perform_zoom(final=False))
        final_zid = getattr(self, "_zoom_final_after_id", None)
        if final_zid:
            try:
                self.canvas.after_cancel(final_zid)
            except tk.TclError:
                pass
            finally:
                self._zoom_final_after_id = None
        else:
            self._zoom_final_after_id = None
        self._zoom_final_after_id = self.canvas.after(300, lambda: self._perform_zoom(final=True))

    def save_map(self):
        abs_masks_dir = Path(MASKS_DIR).resolve(); abs_masks_dir.mkdir(parents=True, exist_ok=True)
        if not self.current_map or "Image" not in self.current_map: print("Error: Current map or map image not set. Cannot save mask."); return
        img_name = os.path.basename(self.current_map["Image"]); base, _ = os.path.splitext(img_name)
        mask_filename = f"{base}_mask.png"
        abs_mask_path = abs_masks_dir / mask_filename
        rel_mask_path = (Path('masks') / mask_filename).as_posix()
        if self.mask_img: self.mask_img.save(abs_mask_path, format="PNG")
        else: print("Warning: No fog mask image to save.")
        self.current_map["FogMaskPath"] = rel_mask_path; self._persist_tokens()
        self.current_map.update({
            "token_size": self.token_size,
            "pan_x": self.pan_x,
            "pan_y": self.pan_y,
            "zoom": self.zoom,
            "hover_font_size": getattr(self, "hover_font_size", 14)
        })
        all_maps = list(self._maps.values()); self.maps.save_items(all_maps)
        try:
            if getattr(self, 'fs', None) and self.fs.winfo_exists() and \
               getattr(self, 'fs_canvas', None) and self.fs_canvas.winfo_exists(): self._update_fullscreen_map()
            if getattr(self, '_web_server_thread', None):
                self._update_web_display_map()
        except tk.TclError: pass
            
    def _on_drawing_tool_change(self, selected_tool: str):
        self.drawing_mode = selected_tool.lower()
        print(f"Drawing mode changed to: {self.drawing_mode}")
        menu = getattr(self, "drawing_tool_menu", None)
        if menu:
            try:
                if menu.get() != selected_tool:
                    menu.set(selected_tool)
            except tk.TclError:
                pass
        if self.drawing_mode != "whiteboard":
            self._clear_whiteboard_preview()
            self._active_whiteboard_points = []
        if self.drawing_mode != "eraser":
            self._eraser_active = False
            self._eraser_dirty = False
        self._update_shape_controls_visibility()

    def _on_shape_fill_mode_change(self, selected_mode: str):
        self.shape_is_filled = (selected_mode == "Filled")
        print(f"Shape fill mode changed to: {'Filled' if self.shape_is_filled else 'Border Only'}")

    def _on_pick_shape_fill_color(self):
        if not hasattr(self, 'current_shape_fill_color'): self.current_shape_fill_color = "#CCCCCC"
        # Pass self.canvas as parent
        result = colorchooser.askcolor(parent=self.canvas, color=self.current_shape_fill_color, title="Choose Shape Fill Color")
        if result and result[1]: self.current_shape_fill_color = result[1]; print(f"Shape fill color: {self.current_shape_fill_color}")

    def _on_pick_shape_border_color(self):
        if not hasattr(self, 'current_shape_border_color'): self.current_shape_border_color = "#000000"
        # Pass self.canvas as parent
        result = colorchooser.askcolor(parent=self.canvas, color=self.current_shape_border_color, title="Choose Shape Border Color")
        if result and result[1]: self.current_shape_border_color = result[1]; print(f"Shape border color: {self.current_shape_border_color}")

    def _on_pick_whiteboard_color(self):
        current_color = getattr(self, "whiteboard_color", "#FF0000")
        result = colorchooser.askcolor(parent=self.canvas, color=current_color, title="Choose Whiteboard Color")
        if result and result[1]:
            self.whiteboard_color = result[1]
            ConfigHelper.set("Drawing", "whiteboard_color", self.whiteboard_color)
            try:
                if getattr(self, "whiteboard_color_button", None):
                    self.whiteboard_color_button.configure(fg_color=self.whiteboard_color)
                if getattr(self, "text_color_button", None):
                    self.text_color_button.configure(fg_color=self.whiteboard_color)
            except tk.TclError:
                pass

    def _on_whiteboard_width_change(self, value):
        try:
            width_val = float(value)
        except Exception:
            return
        self.whiteboard_width = max(1.0, min(20.0, width_val))
        ConfigHelper.set("Drawing", "whiteboard_width", self.whiteboard_width)
        label = getattr(self, "whiteboard_width_value_label", None)
        if label:
            try:
                label.configure(text=str(int(round(self.whiteboard_width))))
            except tk.TclError:
                pass

    def _on_text_size_change(self, value):
        try:
            size_val = int(value)
        except Exception:
            return
        self.text_size = max(8, min(96, size_val))
        ConfigHelper.set("Drawing", "text_size", self.text_size)
        options = list(getattr(self, "text_size_options", []))
        if self.text_size not in options:
            options.append(self.text_size)
            options = sorted(set(options))
            self.text_size_options = list(options)
            menu = getattr(self, "text_size_menu", None)
            if menu:
                try:
                    menu.configure(values=[str(v) for v in options])
                except tk.TclError:
                    pass

    def _on_eraser_radius_change(self, value):
        try:
            radius = float(value)
        except Exception:
            return
        self.whiteboard_eraser_radius = max(2.0, min(40.0, radius))
        ConfigHelper.set("Drawing", "whiteboard_eraser_radius", self.whiteboard_eraser_radius)
        label = getattr(self, "eraser_radius_value_label", None)
        if label:
            try:
                label.configure(text=str(int(round(self.whiteboard_eraser_radius))))
            except tk.TclError:
                pass

    def _update_shape_controls_visibility(self):
        shape_tool_active = self.drawing_mode in ["rectangle", "oval"]
        whiteboard_active = self.drawing_mode == "whiteboard"
        eraser_active = self.drawing_mode == "eraser"
        text_active = self.drawing_mode == "text"
        try:
            shape_fill_label = getattr(self, 'shape_fill_label', None)
            shape_fill_mode_menu = getattr(self, 'shape_fill_mode_menu', None)
            shape_fill_color_button = getattr(self, 'shape_fill_color_button', None)
            shape_border_color_button = getattr(self, 'shape_border_color_button', None)
            whiteboard_color_button = getattr(self, "whiteboard_color_button", None)
            whiteboard_width_slider = getattr(self, "whiteboard_width_slider", None)
            whiteboard_controls_frame = getattr(self, "whiteboard_controls_frame", None)
            eraser_controls_frame = getattr(self, "eraser_controls_frame", None)
            eraser_slider = getattr(self, "whiteboard_eraser_slider", None)
            text_controls_frame = getattr(self, "text_controls_frame", None)
            text_size_menu = getattr(self, "text_size_menu", None)
            if shape_tool_active:
                # Unpack all first to ensure a clean state and avoid issues with 'before'
                if shape_fill_label: shape_fill_label.pack_forget()
                if shape_fill_mode_menu: shape_fill_mode_menu.pack_forget()
                if shape_fill_color_button: shape_fill_color_button.pack_forget()
                if shape_border_color_button: shape_border_color_button.pack_forget()
                if whiteboard_color_button: whiteboard_color_button.pack_forget()
                if whiteboard_width_slider:
                    try:
                        whiteboard_width_slider.master.pack_forget()
                    except Exception:
                        pass
                if whiteboard_controls_frame:
                    whiteboard_controls_frame.pack_forget()
                if text_size_menu:
                    try:
                        text_size_menu.master.pack_forget()
                    except Exception:
                        pass
                if text_controls_frame:
                    text_controls_frame.pack_forget()
                if eraser_slider:
                    try:
                        eraser_slider.master.pack_forget()
                    except Exception:
                        pass
                if eraser_controls_frame:
                    eraser_controls_frame.pack_forget()

                shape_controls_row = getattr(self, "shape_controls_row", None)
                if shape_controls_row:
                    shape_controls_row.pack(side="top", fill="x", anchor="w", padx=(6, 2), pady=4)

                # Repack in desired order without 'before'
                if shape_fill_label: shape_fill_label.pack(side="left", padx=(10,2), pady=8)
                if shape_fill_mode_menu: shape_fill_mode_menu.pack(side="left", padx=5, pady=8)
                if shape_fill_color_button: shape_fill_color_button.pack(side="left", padx=(10,2), pady=8)
                if shape_border_color_button: shape_border_color_button.pack(side="left", padx=2, pady=8)
            elif whiteboard_active:
                shape_controls_row = getattr(self, "shape_controls_row", None)
                if shape_controls_row:
                    shape_controls_row.pack_forget()
                if shape_fill_label: shape_fill_label.pack_forget()
                if shape_fill_mode_menu: shape_fill_mode_menu.pack_forget()
                if shape_fill_color_button: shape_fill_color_button.pack_forget()
                if shape_border_color_button: shape_border_color_button.pack_forget()
                if text_controls_frame:
                    text_controls_frame.pack_forget()
                if text_size_menu:
                    try:
                        text_size_menu.master.pack_forget()
                    except Exception:
                        pass
                if whiteboard_controls_frame:
                    whiteboard_controls_frame.pack(side="top", fill="x", anchor="w", padx=(8, 2), pady=4)
                if whiteboard_color_button: whiteboard_color_button.pack(side="left", padx=(0, 6), pady=6)
                if whiteboard_width_slider:
                    try:
                        whiteboard_width_slider.master.pack(side="left", padx=(0, 6), pady=6)
                    except Exception:
                        pass
                if eraser_slider:
                    try:
                        eraser_slider.master.pack_forget()
                    except Exception:
                        pass
                if eraser_controls_frame:
                    eraser_controls_frame.pack_forget()
            elif eraser_active:
                shape_controls_row = getattr(self, "shape_controls_row", None)
                if shape_controls_row:
                    shape_controls_row.pack_forget()
                if shape_fill_label: shape_fill_label.pack_forget()
                if shape_fill_mode_menu: shape_fill_mode_menu.pack_forget()
                if shape_fill_color_button: shape_fill_color_button.pack_forget()
                if shape_border_color_button: shape_border_color_button.pack_forget()
                if whiteboard_color_button: whiteboard_color_button.pack_forget()
                if whiteboard_width_slider:
                    try:
                        whiteboard_width_slider.master.pack_forget()
                    except Exception:
                        pass
                if whiteboard_controls_frame:
                    whiteboard_controls_frame.pack_forget()
                if text_size_menu:
                    try:
                        text_size_menu.master.pack_forget()
                    except Exception:
                        pass
                if text_controls_frame:
                    text_controls_frame.pack_forget()
                if eraser_controls_frame:
                    eraser_controls_frame.pack(side="top", fill="x", anchor="w", padx=(8, 2), pady=4)
                if eraser_slider:
                    try:
                        eraser_slider.master.pack(side="left", padx=(0, 6), pady=6)
                    except Exception:
                        pass
            elif text_active:
                shape_controls_row = getattr(self, "shape_controls_row", None)
                if shape_controls_row:
                    shape_controls_row.pack_forget()
                if shape_fill_label: shape_fill_label.pack_forget()
                if shape_fill_mode_menu: shape_fill_mode_menu.pack_forget()
                if shape_fill_color_button: shape_fill_color_button.pack_forget()
                if shape_border_color_button: shape_border_color_button.pack_forget()
                if whiteboard_controls_frame:
                    whiteboard_controls_frame.pack_forget()
                if eraser_slider:
                    try:
                        eraser_slider.master.pack_forget()
                    except Exception:
                        pass
                if eraser_controls_frame:
                    eraser_controls_frame.pack_forget()
                if text_controls_frame:
                    text_controls_frame.pack(side="top", fill="x", anchor="w", padx=(8, 2), pady=4)
                if text_size_menu:
                    try:
                        text_size_menu.master.pack(side="left", padx=(0, 6), pady=6)
                    except Exception:
                        pass
                if whiteboard_color_button:
                    whiteboard_color_button.pack(side="left", padx=(0, 6), pady=6)
            else:
                shape_controls_row = getattr(self, "shape_controls_row", None)
                if shape_controls_row:
                    shape_controls_row.pack_forget()
                if shape_fill_label: shape_fill_label.pack_forget()
                if shape_fill_mode_menu: shape_fill_mode_menu.pack_forget()
                if shape_fill_color_button: shape_fill_color_button.pack_forget()
                if shape_border_color_button: shape_border_color_button.pack_forget()
                if whiteboard_color_button: whiteboard_color_button.pack_forget()
                if whiteboard_width_slider:
                    try:
                        whiteboard_width_slider.master.pack_forget()
                    except Exception:
                        pass
                if whiteboard_controls_frame:
                    whiteboard_controls_frame.pack_forget()
                if text_size_menu:
                    try:
                        text_size_menu.master.pack_forget()
                    except Exception:
                        pass
                if text_controls_frame:
                    text_controls_frame.pack_forget()
                if eraser_slider:
                    try:
                        eraser_slider.master.pack_forget()
                    except Exception:
                        pass
                if eraser_controls_frame:
                    eraser_controls_frame.pack_forget()
        except AttributeError as e: print(f"Toolbar component not found for visibility update: {e}")
        except tk.TclError as e: print(f"TclError updating shape control visibility: {e}")

    # Method assignments (some will be replaced by generic item handlers)
    _build_canvas = _build_canvas
    _build_toolbar = _build_toolbar
    _change_brush = _change_brush # For fog brush
    _change_token_border_color = _change_token_border_color # Specific to tokens via old menu
    
    _copy_item = _copy_item # Generic copy
    _paste_item = _paste_item # Generic paste
    _delete_item = _delete_item # Generic delete

    _on_item_press = _on_item_press
    _on_item_move = _on_item_move
    _on_item_release = _on_item_release
    _on_item_right_click = _on_item_right_click # Dispatches to token or shape menu

    _on_brush_shape_change = _on_brush_shape_change # For fog brush
    _on_brush_size_change = _on_brush_size_change # For fog brush
    _on_delete_key = _on_delete_key # Needs to use self.selected_token and _delete_item
    _on_display_map = _on_display_map
    
    _on_token_size_change = _on_token_size_change # Global token size slider
    _update_fog_button_states = _update_fog_button_states
    _persist_tokens = _persist_tokens # From token_manager, saves self.tokens
    _resize_token_dialog = _resize_token_dialog # Specific to tokens via old menu
    _set_fog = _set_fog
    _show_token_menu = _show_token_menu # Token-specific context menu
    _update_fullscreen_map = _update_fullscreen_map
    _update_web_display_map = _update_web_display_map
    add_token = add_token # For adding new entity tokens
    clear_fog = clear_fog
    load_icon = load_icon
    on_entity_selected = on_entity_selected
    on_entities_selected = on_entities_selected
    on_paint = on_paint # For fog
    open_entity_picker = open_entity_picker
    open_fullscreen = open_fullscreen
    open_web_display = open_web_display
    close_web_display = close_web_display
    reset_fog = reset_fog
    select_map = select_map

    def _activate_graphical_resize(self, shape):
        print(f"[DEBUG] _activate_graphical_resize called for shape: {shape.get('canvas_ids')}")
        if shape and shape.get("type") in ["rectangle", "oval"]:
            self._set_selection([shape])
            # Set the item for graphical edit mode *before* drawing handles
            self._graphical_edit_mode_item = shape
            self._draw_resize_handles(shape) # This calls _remove_resize_handles first
        else: # Not a shape or shape is None, ensure no graphical edit mode
            if self._graphical_edit_mode_item == shape: # If it was this non-shape item
                self._graphical_edit_mode_item = None
            self._remove_resize_handles() # Clear any stray handles


    def _draw_resize_handles(self, item):
        if not self.canvas or not self.canvas.winfo_exists(): return
        self._remove_resize_handles()

        item_canvas_id = item.get('canvas_ids', [None])[0]
        if not item_canvas_id: return

        try:
            coords = self.canvas.coords(item_canvas_id)
        except tk.TclError:
            return
            
        if not coords or len(coords) < 4: return

        x1, y1, x2, y2 = coords
        hs = self._handle_size / 2.0

        handle_defs = [
            (x1, y1, 'nw'), ( (x1+x2)/2, y1, 'n'), (x2, y1, 'ne'),
            (x2, (y1+y2)/2, 'e'), (x2, y2, 'se'), ( (x1+x2)/2, y2, 's'),
            (x1, y2, 'sw'), (x1, (y1+y2)/2, 'w')
        ]

        for cx, cy, handle_tag_suffix in handle_defs:
            handle_id = self.canvas.create_rectangle(
                cx - hs, cy - hs, cx + hs, cy + hs,
                fill=self._handle_fill, outline=self._handle_outline,
                tags=(f"{handle_tag_suffix}_handle", "resize_handle") # Ensure this tag is unique enough
            )
            self._resize_handles.append(handle_id)
            print(f"[DEBUG] Created handle ID: {handle_id} with tags: {self.canvas.gettags(handle_id)}")
            
            # Ensure handles are on top
            self.canvas.lift(handle_id)

            self.canvas.tag_bind(handle_id, "<ButtonPress-1>",
                                 lambda e, ht=handle_tag_suffix: self._on_resize_handle_press(e, ht))
            self.canvas.tag_bind(handle_id, "<B1-Motion>",
                                 self._on_resize_handle_move) # No 'break' needed here, handled by _active_resize_handle_info
            self.canvas.tag_bind(handle_id, "<ButtonRelease-1>",
                                 self._on_resize_handle_release)
                                 
    def _remove_resize_handles(self):
        if not self.canvas or not self.canvas.winfo_exists(): return
        for handle_id in self._resize_handles:
            try:
                self.canvas.delete(handle_id)
            except tk.TclError:
                pass
        self._resize_handles = []
        # Only clear _graphical_edit_mode_item if the item it points to is no longer selected
        # OR if we are not in an active resize operation.
        # This prevents clearing it when _draw_resize_handles calls _remove_resize_handles internally
        # for an item that IS _graphical_edit_mode_item.
        if self.selected_token != self._graphical_edit_mode_item and self._active_resize_handle_info is None:
             self._graphical_edit_mode_item = None


    def _on_resize_handle_press(self, event, handle_type):
        print(f"[DEBUG] _on_resize_handle_press: Attempting press on handle '{handle_type}' at ({event.x}, {event.y})")
        if not self._graphical_edit_mode_item:
            print("[DEBUG] _on_resize_handle_press: No graphical edit item.")
            return
        item = self._graphical_edit_mode_item
        
        if not item or item.get("type") not in ["rectangle", "oval"]:
            print(f"[DEBUG] _on_resize_handle_press: Item is not a shape or None. Item: {item}")
            return

        item_canvas_id = item.get('canvas_ids', [None])[0]
        if not item_canvas_id: return
        
        try:
            screen_coords = self.canvas.coords(item_canvas_id)
        except tk.TclError:
             return

        if not screen_coords or len(screen_coords) < 4: return

        original_width_world = item.get("width", DEFAULT_SHAPE_WIDTH)
        original_height_world = item.get("height", DEFAULT_SHAPE_HEIGHT)
        original_pos_x_world, original_pos_y_world = item.get("position", (0,0))
        print(f"[DEBUG] Handle Press: {handle_type}, Item: {item.get('canvas_ids')}, Start Coords: ({event.x}, {event.y})")
        self._active_resize_handle_info = {
            'item': item,
            'handle_type': handle_type,
            'start_event_x_screen': event.x,
            'start_event_y_screen': event.y,
            'original_width_world': original_width_world,
            'original_height_world': original_height_world,
            'original_pos_x_world': original_pos_x_world,
            'original_pos_y_world': original_pos_y_world,
        }
        if 'drag_data' in item: # Prevent normal item dragging
            del item['drag_data']


    def _on_resize_handle_move(self, event):
        if not self._active_resize_handle_info or not self.canvas.winfo_exists():
            # print(f"[DEBUG] Handle Move: No active info or canvas gone.")
            return
        # print(f"[DEBUG] Handle Move: Event ({event.x}, {event.y})")
        info = self._active_resize_handle_info
        item = info['item']
        handle_type = info['handle_type']

        delta_x_world = (event.x - info['start_event_x_screen']) / self.zoom
        delta_y_world = (event.y - info['start_event_y_screen']) / self.zoom
        
        new_x_world = info['original_pos_x_world']
        new_y_world = info['original_pos_y_world']
        new_width_world = info['original_width_world']
        new_height_world = info['original_height_world']

        min_dim_world = max(1.0, self._handle_size / self.zoom)

        if 'e' in handle_type:
            new_width_world = info['original_width_world'] + delta_x_world
        if 'w' in handle_type:
            new_width_world = info['original_width_world'] - delta_x_world
            new_x_world = info['original_pos_x_world'] + delta_x_world
        
        if 's' in handle_type:
            new_height_world = info['original_height_world'] + delta_y_world
        if 'n' in handle_type:
            new_height_world = info['original_height_world'] - delta_y_world
            new_y_world = info['original_pos_y_world'] + delta_y_world

        if new_width_world < min_dim_world:
            if 'w' in handle_type:
                 new_x_world -= (min_dim_world - new_width_world)
            new_width_world = min_dim_world
            
        if new_height_world < min_dim_world:
            if 'n' in handle_type:
                new_y_world -= (min_dim_world - new_height_world)
            new_height_world = min_dim_world

        item['width'] = new_width_world
        item['height'] = new_height_world
        item['position'] = (new_x_world, new_y_world)
        # print(f"[DEBUG] Handle Move: Updated item {item.get('canvas_ids')} to w:{new_width_world}, h:{new_height_world}, pos:({new_x_world},{new_y_world})")
        self._update_canvas_images()

    def _on_resize_handle_release(self, event):
        if not self._active_resize_handle_info:
            # print("[DEBUG] Handle Release: No active info.")
            return
        
        item = self._active_resize_handle_info['item']
        print(f"[DEBUG] Handle Release: Item {item.get('canvas_ids')}")
        self._persist_tokens()
        self._active_resize_handle_info = None # Clear active resize operation
        
        # Ensure handles are correctly redrawn for the item that was just resized,
        # if it's still the one in graphical edit mode.
        if item == self._graphical_edit_mode_item:
            self._draw_resize_handles(item)
    # Removed _on_shape_double_click as it's no longer the trigger
