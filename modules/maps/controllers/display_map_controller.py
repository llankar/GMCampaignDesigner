import os
import json
from pathlib import Path
from tkinter import colorchooser, messagebox
import tkinter as tk
from tkinter import font as tkfont
from types import SimpleNamespace
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
from modules.maps.services.fog_manager import _set_fog, clear_fog, reset_fog, on_paint
# Removed direct imports from token_manager, as methods are now part of this controller or generic
# from modules.maps.services.token_manager import add_token, _on_token_press, _on_token_move, _on_token_release, _copy_token, _paste_token, _show_token_menu, _resize_token_dialog, _change_token_border_color, _delete_token, _persist_tokens
from modules.maps.services.token_manager import add_token, _persist_tokens, _change_token_border_color # Keep this if it's used by other token_manager functions not moved
from modules.maps.views.fullscreen_view import open_fullscreen, _update_fullscreen_map
from modules.maps.views.web_display_view import open_web_display, _update_web_display_map, close_web_display
from modules.maps.services.entity_picker_service import open_entity_picker, on_entity_selected
from modules.maps.utils.icon_loader import load_icon
from PIL import Image, ImageTk, ImageDraw
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.template_loader import load_template
from modules.helpers.text_helpers import format_longtext
from modules.helpers.config_helper import ConfigHelper
from modules.ui.image_viewer import show_portrait
from modules.helpers.logging_helper import log_module_import
from modules.audio.entity_audio import play_entity_audio, stop_entity_audio

log_module_import(__name__)

DEFAULT_BRUSH_SIZE = 32  # px
DEFAULT_SHAPE_WIDTH = 50
DEFAULT_SHAPE_HEIGHT = 50

MASKS_DIR = os.path.join(ConfigHelper.get_campaign_dir(), "masks")
MAX_ZOOM = 3.0
MIN_ZOOM = 0.1
ZOOM_STEP = 0.1  # 10% per wheel notch
ctk.set_appearance_mode("dark")

class DisplayMapController:
    def __init__(self, parent, maps_wrapper, map_template):
        self.parent = parent
        self.maps = maps_wrapper
        self.map_template = map_template
    
        self._model_wrappers = {
            "NPC":      GenericModelWrapper("npcs"),
            "Creature": GenericModelWrapper("creatures"),
            "PC": GenericModelWrapper("pcs"),
        }
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
        self._fast_resample = Image.BILINEAR
        self.zoom        = 1.0
        self.pan_x       = 0
        self.pan_y       = 0
        self.selected_token  = None # Selected item (token or shape)
        self.clipboard_token = None # Copied item data (token or shape)
    
        self.brush_size  = DEFAULT_BRUSH_SIZE
        self.brush_size_options = list(range(4, 129, 4))
        self.token_size  = 48
        self.token_size_options = list(range(16, 129, 8))
        self.hover_font_size_options = [10, 12, 14, 16, 18, 20, 24, 28, 32]
        self.hover_font_size = 14
        self.hover_font = ctk.CTkFont(size=self.hover_font_size)
        self.brush_shape = "rectangle"
        self.fog_mode    = None
        self.tokens      = [] # List of all items (tokens and shapes)
        
        self.drawing_mode = "token"
        self.shape_is_filled = True
        self.current_shape_fill_color = "#CCCCCC"
        self.current_shape_border_color = "#000000"
    
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

        # Maintain a registry of all popup windows (token info cards and marker
        # descriptions) so the toolbar button can reliably dismiss every one of
        # them even if internal bookkeeping for a token becomes desynchronised.
        self._active_hover_popups = set()

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
        self._fog_action_active = False
        
        self._maps = {m["Name"]: m for m in maps_wrapper.load_items()}
        self.select_map()

    def open_map_by_name(self, map_name):
        target = (map_name or "").strip()
        if not target:
            return False
        if target not in self._maps:
            messagebox.showwarning("Not Found", f"Map '{target}' not found.")
            return False
        self._on_display_map("maps", target)
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

    def _on_marker_entry_click(self, event, marker):
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
        self._hide_all_marker_descriptions()
        self._hide_all_token_hovers()

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
        self._hide_all_marker_descriptions()
        self._hide_all_token_hovers()

    def _show_marker_menu(self, event, marker):
        self._hovered_marker = marker
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="Edit Description", command=lambda m=marker: self._open_marker_description_editor(m))
        menu.add_command(label="Change Border Color", command=lambda m=marker: self._change_marker_border_color(m))
        menu.add_separator()
        menu.add_command(label="Delete Marker", command=lambda m=marker: self._delete_item(m))
        menu.tk_popup(event.x_root, event.y_root)
        try:
            menu.grab_release()
        except tk.TclError:
            pass

    def _change_marker_border_color(self, marker):
        if not marker:
            return
        current_color = marker.get("border_color", "#00ff00")
        result = colorchooser.askcolor(parent=self.canvas, color=current_color, title="Choose Marker Border Color")
        if result and result[1]:
            marker["border_color"] = result[1]
            self._update_canvas_images()
            self._persist_tokens()

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

    def _get_token_hover_text(self, token):
        record = token.get("entity_record") or {}
        entity_type = token.get("entity_type")
        raw_stats_text = ""
        if entity_type == "Creature":
            raw_stats_text = record.get("Stats", "")
        elif entity_type == "PC":
            raw_stats_text = record.get("Stats", "")
        elif entity_type == "NPC":
            raw_stats_text = record.get("Traits", "")
        display_stats_text = format_longtext(raw_stats_text)
        if isinstance(display_stats_text, (list, tuple)):
            display_stats_text = "\n".join(map(str, display_stats_text))
        else:
            display_stats_text = str(display_stats_text or "")
        if not display_stats_text.strip():
            display_stats_text = "(No details available)"
        return display_stats_text

    def _ensure_token_hover_popup(self, token):
        popup = token.get("hover_popup")
        label = token.get("hover_label")
        canvas = getattr(self, "canvas", None)
        if popup and popup.winfo_exists() and label and label.winfo_exists():
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
        self._register_hover_popup(popup)
        token["hover_popup"] = popup
        token["hover_label"] = label
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
        label.configure(
            text=self._get_token_hover_text(token),
            justify="left",
            anchor="w",
            wraplength=400,
            font=getattr(self, "hover_font", None)
        )
        try:
            popup.update_idletasks()
        except tk.TclError:
            return
        width = max(label.winfo_reqwidth() + 20, 160)
        height = max(label.winfo_reqheight() + 16, 80)
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
        return SimpleNamespace(x=x, y=y)

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
        if self.mask_img is not None:
            MAX_UNDO = 20; self.fog_history.append(self.mask_img.copy())
            if len(self.fog_history) > MAX_UNDO: self.fog_history.pop(0)
    
    def undo_fog(self, event=None):
        if not self.fog_history: return
        self.mask_img = self.fog_history.pop(); self._update_canvas_images()
    
    # _bind_token is now _bind_item_events

    def _on_token_right_click(self, event, token):
        print(f"Token right click on: {token.get('entity_id', 'Unknown Token')}")
        if token.get("type") == "token" and "hp_canvas_ids" in token and token["hp_canvas_ids"]: # Ensure it's a token
            hp_cid, _ = token["hp_canvas_ids"]
            if hp_cid:
                x1, y1, x2, y2 = self.canvas.coords(hp_cid)
                pad = 4
                if x1 - pad <= event.x <= x2 + pad and y1 - pad <= event.y <= y2 + pad:
                    return self._on_max_hp_menu_click(event, token)
        return self._show_token_menu(event, token) # Fallback for token specific menu
    
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
            if self.selected_token: # Deselect any item
                self.selected_token = None
            
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
        self.on_paint(event)

    def _on_mouse_up(self, event):
        if self._marker_after_id: self.canvas.after_cancel(self._marker_after_id); self._marker_after_id = None
        if self._marker_anim_after_id:
            try:
                self.canvas.after_cancel(self._marker_anim_after_id)
            except Exception:
                pass
            self._marker_anim_after_id = None
        if self._marker_id: self.canvas.delete(self._marker_id); self._marker_id = None
        if self.fs_canvas and self._fs_marker_id: self.fs_canvas.delete(self._fs_marker_id); self._fs_marker_id = None
        if self._fog_action_active:
            self._fog_action_active = False; self.canvas.delete("fog_preview")
            if self.base_img and self.mask_img:
                w, h = self.base_img.size; sw, sh = int(w*self.zoom), int(h*self.zoom)
                if sw > 0 and sh > 0:
                    mask_resized = self.mask_img.resize((sw, sh), resample=Image.LANCZOS)
                    self.mask_tk = ImageTk.PhotoImage(mask_resized)
                    if self.mask_id: self.canvas.itemconfig(self.mask_id, image=self.mask_tk); self.canvas.coords(self.mask_id, self.pan_x, self.pan_y)
        
    def _perform_zoom(self, final: bool):
        resample = Image.LANCZOS if final else self._fast_resample; self._update_canvas_images(resample=resample)

    def _update_canvas_images(self, resample=Image.LANCZOS):
        if not self.base_img: return
        
        # Redraw handles if graphical edit mode is active for the selected item
        # and not currently in a drag-resize operation.
        if self.selected_token and self.selected_token == self._graphical_edit_mode_item and \
           not self._active_resize_handle_info and self.canvas.winfo_exists():
            self._draw_resize_handles(self.selected_token)
        # Ensure handles are removed if graphical edit mode is not active for the selected item
        elif self._resize_handles and (not self.selected_token or self.selected_token != self._graphical_edit_mode_item):
            self._remove_resize_handles()


        w, h = self.base_img.size; sw, sh = int(w*self.zoom), int(h*self.zoom)
        if sw <= 0 or sh <= 0: return 
        x0, y0 = self.pan_x, self.pan_y
        base_resized = self.base_img.resize((sw,sh), resample=resample); self.base_tk = ImageTk.PhotoImage(base_resized)
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
                    item.update({'canvas_ids': (b_id, i_id), 'name_id': name_id})
                    self._bind_item_events(item)
                    item['hover_bbox'] = (sx - 3, sy - 3, sx + nw + 3, sy + nh + 3)
                    self._refresh_token_hover_popup(item)
            elif item_type == "marker":
                item.setdefault("entry_width", 180)
                item.setdefault("entry_expanded_width", item.get("entry_width", 180))
                item.setdefault("description_visible", False)
                item.setdefault("handle_width", 22)
                item.setdefault("border_color", "#00ff00")
                sx, sy = int(xw*self.zoom + self.pan_x), int(yw*self.zoom + self.pan_y)
                entry = item.get("entry_widget")
                desired_text = item.get("text", "")
                if not entry or not entry.winfo_exists():
                    entry = ctk.CTkEntry(self.canvas, width=item.get("entry_width", 180))
                    entry.insert(0, desired_text)
                    entry.bind("<KeyRelease>", lambda e, i=item: self._on_marker_text_change(i, persist=False))
                    entry.bind("<FocusIn>", lambda e, i=item: self._on_marker_entry_focus_in(i))
                    entry.bind("<FocusOut>", lambda e, i=item: self._on_marker_entry_focus_out(i))
                    entry.bind("<Return>", lambda e, i=item: self._on_marker_entry_return(e, i))
                    entry.bind("<ButtonRelease-1>", lambda e, i=item: self._on_marker_entry_click(e, i))
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
            elif item_type in ["rectangle", "oval"]:
                shape_width_unscaled = item.get("width", DEFAULT_SHAPE_WIDTH); shape_height_unscaled = item.get("height", DEFAULT_SHAPE_HEIGHT)
                shape_width = shape_width_unscaled * self.zoom; shape_height = shape_height_unscaled * self.zoom
                if shape_width <=0 or shape_height <=0: continue
                sx, sy = int(xw*self.zoom + self.pan_x), int(yw*self.zoom + self.pan_y)
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
        if self.fs_canvas:
            self._update_fullscreen_map()
        if getattr(self, '_web_server_thread', None):
            self._update_web_display_map()

    def _bind_item_events(self, item):
        if not item.get('canvas_ids'): return
        ids_to_bind = item['canvas_ids']
        for cid in ids_to_bind:
            if not cid: continue
            if item.get("type") == "marker" and cid == item.get("entry_canvas_id"):
                continue
            self.canvas.tag_bind(cid, "<ButtonPress-1>", lambda e, i=item: self._on_item_press(e, i))
            self.canvas.tag_bind(cid, "<B1-Motion>", lambda e, i=item: (self._on_item_move(e, i), "break")) # 'break' prevents event propagation
            self.canvas.tag_bind(cid, "<ButtonRelease-1>", lambda e, i=item: self._on_item_release(e, i))
            self.canvas.tag_bind(cid, "<Button-3>", lambda e, i=item: self._on_item_right_click(e, i))

            item_type = item.get("type", "token")
            if item_type == "token":
                 self.canvas.tag_bind(cid, "<Double-Button-1>", lambda e, i=item: self._on_token_double_click(e, i))
            # elif item_type in ["rectangle", "oval"]:
            # No double-click for handles; triggered by menu now.
            pass

    def _on_item_press(self, event, item):
        print(f"[DEBUG] _on_item_press: Item type: {item.get('type')}, ID/Name: {item.get('entity_id', item.get('canvas_ids'))}")
        if self._active_resize_handle_info: # If a resize drag is active, do nothing
            print("[DEBUG] _on_item_press: Active resize handle info exists, returning.")
            return

        # If the newly selected item is different from the one in graphical edit mode,
        # or if no item was in graphical edit mode, remove handles.
        if self._graphical_edit_mode_item and self._graphical_edit_mode_item != item:
            self._remove_resize_handles()
            self._graphical_edit_mode_item = None
        elif not self._graphical_edit_mode_item and self._resize_handles: # Handles visible but no item in edit mode (shouldn't happen)
             self._remove_resize_handles()


        self.selected_token = item
        item["drag_data"] = {"x": event.x, "y": event.y, "moved": False}
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
        if not drag_data.get("moved") and (abs(dx) > 2 or abs(dy) > 2):
            drag_data["moved"] = True
        for cid in item.get("canvas_ids", []):
            if cid: self.canvas.move(cid, dx, dy)
        if item.get("type", "token") == "token":
            if item.get("name_id"): self.canvas.move(item["name_id"], dx, dy)
            if item.get("hp_canvas_ids"):
                for hp_cid in item["hp_canvas_ids"]:
                    if hp_cid: self.canvas.move(hp_cid, dx, dy)
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
        elif item.get("type") == "marker":
            self._refresh_marker_description_popup(item)
        drag_data["x"] = event.x
        drag_data["y"] = event.y
        main_canvas_id = item["canvas_ids"][0] if item.get("canvas_ids") else None
        if main_canvas_id:
            coords = self.canvas.coords(main_canvas_id)
            if coords: sx, sy = coords[0], coords[1]; item["position"] = ((sx - self.pan_x)/self.zoom, (sy - self.pan_y)/self.zoom)
        
        # If moving a shape that is in graphical edit mode, redraw its handles
        if item == self._graphical_edit_mode_item and item.get("type") in ["rectangle", "oval"]:
            self._draw_resize_handles(item)


    def _on_item_release(self, event, item):
        # If a resize operation was active for this item, it's handled by _on_resize_handle_release
        if self._active_resize_handle_info and self._active_resize_handle_info.get('item') == item:
            # The actual release logic is in _on_resize_handle_release
            return

        drag_data = item.pop("drag_data", None)
        if drag_data and not drag_data.get("moved"):
            self._handle_item_click(event, item)
        self._persist_tokens()

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

    def _on_item_right_click(self, event, item):
        item_type = item.get("type", "token")
        if item_type == "token": return self._on_token_right_click(event, item)
        elif item_type in ["rectangle", "oval"]: self._show_shape_menu(event, item)
        elif item_type == "marker": self._show_marker_menu(event, item)

    def _show_shape_menu(self, event, shape):
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="Edit Shape Graphically", command=lambda s=shape: self._activate_graphical_resize(s))
        menu.add_command(label="Edit Color", command=lambda s=shape: self._edit_shape_color_dialog(s))
        menu.add_command(label="Edit Dimensions (Numeric)", command=lambda s=shape: self._resize_shape_dialog(s)) # Keep numeric input as separate option
        menu.add_command(label="Toggle Fill", command=lambda s=shape: self._toggle_shape_fill(s))
        menu.add_separator()
        menu.add_command(label="Copy Shape", command=lambda s=shape: self._copy_item(s))
        menu.add_command(label="Delete Shape", command=lambda s=shape: self._delete_item(s))
        menu.add_separator()
        menu.add_command(label="Bring to Front", command=lambda s=shape: self._bring_item_to_front(s))
        menu.add_command(label="Send to Back", command=lambda s=shape: self._send_item_to_back(s))
        menu.tk_popup(event.x_root, event.y_root)

    def _edit_shape_color_dialog(self, shape):
        current_fill = shape.get("fill_color", self.current_shape_fill_color)
        # Pass self.canvas (or a relevant toplevel) as parent to colorchooser
        fill_res = colorchooser.askcolor(parent=self.canvas, color=current_fill, title="Choose Shape Fill Color")
        if fill_res and fill_res[1]: shape["fill_color"] = fill_res[1]
        
        current_border = shape.get("border_color", self.current_shape_border_color)
        border_res = colorchooser.askcolor(parent=self.canvas, color=current_border, title="Choose Shape Border Color")
        if border_res and border_res[1]: shape["border_color"] = border_res[1]
        
        self._update_canvas_images(); self._persist_tokens()

    def _resize_shape_dialog(self, shape):
        # Pass self.canvas as parent to simpledialog
        new_width = tk.simpledialog.askinteger("Resize Shape", "New Width (pixels):", parent=self.canvas, initialvalue=shape.get("width", DEFAULT_SHAPE_WIDTH), minvalue=1)
        if new_width is None: return # User cancelled
        new_height = tk.simpledialog.askinteger("Resize Shape", "New Height (pixels):", parent=self.canvas, initialvalue=shape.get("height", DEFAULT_SHAPE_HEIGHT), minvalue=1)
        if new_height is None: return # User cancelled
        shape["width"] = new_width; shape["height"] = new_height
        self._update_canvas_images(); self._persist_tokens()

    # _adjust_shape_size_relative method is removed as per request.

    def _resize_token_dialog(self, token):
        """
        Opens a dialog to resize the given token.
        """
        if not token or token.get("type") != "token":
            # Consider logging this or showing a user-facing error
            print("Error: Valid token not provided for resizing.")
            return

        current_size = token.get("size", self.token_size)
        
        try:
            # Ensure simpledialog is available; it's part of standard tkinter
            import tkinter.simpledialog as simpledialog
            new_size = simpledialog.askinteger(
                "Resize Token",
                "New Size (pixels):",
                parent=self.canvas, # Associate dialog with the canvas/main window
                initialvalue=current_size,
                minvalue=8 # Define a reasonable minimum size
            )
        except ImportError:
            print("Error: tkinter.simpledialog not available for resizing token.")
            # Potentially fall back to a CTk dialog or log error
            return
        except tk.TclError as e:
            print(f"Error displaying resize token dialog: {e}")
            return


        if new_size is not None and new_size > 0:
            token["size"] = new_size

            source_img = token.get("source_image")

            # If the token's visual representation depends on a disk image,
            # reuse the cached high-resolution copy when possible.
            if "image_path" in token and token["image_path"]:
                try:
                    if source_img is None:
                        source_img = Image.open(token["image_path"]).convert("RGBA")
                    token["source_image"] = source_img
                    token["pil_image"] = source_img.resize((new_size, new_size), Image.LANCZOS)
                except FileNotFoundError:
                    print(f"Error: Image file not found for token: {token['image_path']}")
                except Exception as e:
                    print(f"Error reloading image for resized token: {e}")
            elif source_img is not None:
                token["pil_image"] = source_img.resize((new_size, new_size), Image.LANCZOS)

            self._update_canvas_images() # Redraw canvas to reflect new token size
            self._persist_tokens()       # Save the changes
        # else:
            # User cancelled or entered invalid size, no action needed or log if desired
            # print("Token resize cancelled or invalid size entered.")
    def _show_token_menu(self, event, token):
        """
        Displays a context menu for the given token.
        """
        if not token or token.get("type") != "token":
            print("Error: Valid token not provided for menu.")
            return

        menu = tk.Menu(self.canvas, tearoff=0)
        
        # Add commands relevant to tokens
        # Example: Resize Token (using the method we just added/fixed)
        menu.add_command(label="Resize Token", command=lambda t=token: self._resize_token_dialog(t))
        
        # Example: Change Border Color (assuming _change_token_border_color is or will be correctly handled)
        # For now, let's assume it takes the token as an argument.
        # If _change_token_border_color is an imported function that doesn't take `self`,
        # it would be `_change_token_border_color(t)`
        # If it's a method, it would be `self._change_token_border_color(t)`
        # Based on line 12 and 685, it seems to be an imported function.
        # However, a more typical OOP approach would be a method.
        # For consistency with _resize_token_dialog, let's assume we'd want a method.
        # If _change_token_border_color is indeed an external function,
        # this lambda might need adjustment or _change_token_border_color needs to be wrapped.
        # For now, let's add a placeholder or a call to a potential future method.
        menu.add_command(label="Change Border Color", command=lambda t=token: self._prompt_change_token_border_color(t))

        menu.add_separator()
        menu.add_command(label="Copy Token", command=lambda t=token: self._copy_item(t))
        menu.add_command(label="Delete Token", command=lambda t=token: self._delete_item(t))
        menu.add_separator()
        menu.add_command(label="Bring to Front", command=lambda t=token: self._bring_item_to_front(t))
        menu.add_command(label="Send to Back", command=lambda t=token: self._send_item_to_back(t))
        menu.add_command(label="Show Portrait", command=lambda t=token: show_portrait(t["image_path"], t.get("entity_type")))
        audio_value = self._get_token_audio_value(token)
        if audio_value:
            menu.add_separator()
            menu.add_command(label="Play Audio", command=lambda t=token: self._play_token_audio(t))
            menu.add_command(label="Stop Audio", command=stop_entity_audio)
        # Display the menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError as e:
            print(f"Error displaying token menu: {e}")

    def _get_token_audio_value(self, token):
        record = token.get("entity_record") or {}
        value = record.get("Audio") or ""
        if isinstance(value, dict):
            value = value.get("path") or value.get("text") or ""
        value = str(value).strip()
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
                    raw = item.get("Audio") or ""
                    if isinstance(raw, dict):
                        raw = raw.get("path") or raw.get("text") or ""
                    return str(raw).strip()
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

    def _prompt_change_token_border_color(self, token):
        """
        Prompts the user for a new border color for the token.
        """
        if not token or token.get("type") != "token":
            return
        
        current_color = token.get("border_color", "#0000FF") # Default blue
        # Pass self.canvas as parent
        new_color_tuple = colorchooser.askcolor(parent=self.canvas, color=current_color, title="Choose Token Border Color")
        
        if new_color_tuple and new_color_tuple[1]: # Check if a color was chosen
            token["border_color"] = new_color_tuple[1]
            self._update_canvas_images() # Redraw to show new border color
            self._persist_tokens()       # Save changes
    def _toggle_shape_fill(self, shape):
        shape["is_filled"] = not shape.get("is_filled", True)
        self._update_canvas_images(); self._persist_tokens()

    def _copy_item(self, item_to_copy=None):
        active_item = item_to_copy if item_to_copy else self.selected_token
        #if not active_item: return
        self.clipboard_token = active_item.copy()
        for key_to_pop in ['pil_image', 'source_image', 'tk_image', 'entity_record',
                           'canvas_ids', 'hp_canvas_ids', 'name_id',
                           'hp_entry_widget', 'hp_entry_widget_id',
                           'max_hp_entry_widget', 'max_hp_entry_widget_id',
                           'entry_widget', 'description_popup', 'description_label',
                           'handle_widget', 'handle_canvas_id', 'entry_canvas_id',
                           'border_canvas_id',
                           'description_editor', 'hover_popup', 'hover_label',
                           'hover_bbox', 'hover_visible']:
            self.clipboard_token.pop(key_to_pop, None)

    def _paste_item(self, event=None):
        if not self.clipboard_token: return

        # Determine paste position (center of canvas for now, or mouse if event is available)
        # This could be refined to paste near mouse cursor if event is passed from a keybind
        if self.canvas:
            vcx = (self.canvas.winfo_width() // 2 - self.pan_x) / self.zoom
            vcy = (self.canvas.winfo_height() // 2 - self.pan_y) / self.zoom
        else: # Fallback if canvas not ready (should not happen in normal flow)
            vcx, vcy = 100, 100 

        new_item_data = self.clipboard_token.copy() # Start with a copy of clipboard
        new_item_data["position"] = (vcx, vcy) # Set new position
        new_item_data["canvas_ids"] = () # Canvas items will be created by _update_canvas_images

        item_type = new_item_data.get("type", "token")

        if item_type == "token":
            # For tokens, we need to reload the PIL image if image_path is present
            if "image_path" in new_item_data and new_item_data["image_path"]:
                try:
                    sz = new_item_data.get("size", self.token_size)
                    source_img = Image.open(new_item_data["image_path"]).convert("RGBA")
                    new_item_data["source_image"] = source_img
                    new_item_data["pil_image"] = source_img.resize((sz, sz), Image.LANCZOS)
                except Exception as e:
                    print(f"Error reloading image for pasted token: {e}")
                    new_item_data["source_image"] = None
                    new_item_data["pil_image"] = None # Or a placeholder
            else: # No image_path, or it was removed during copy
                new_item_data["source_image"] = None # Or a placeholder
                new_item_data["pil_image"] = None # Or a placeholder
            
            # Ensure token-specific fields that might not be in clipboard are defaulted
            new_item_data.setdefault("entity_type", "Unknown") # Default if missing
            new_item_data.setdefault("entity_id", "Pasted Token")
            new_item_data.setdefault("border_color", "#0000FF")
            new_item_data.setdefault("size", self.token_size)
            new_item_data.setdefault("hp", 10)
            new_item_data.setdefault("max_hp", 10)
            new_item_data.setdefault("hover_popup", None)
            new_item_data.setdefault("hover_label", None)
            new_item_data.setdefault("hover_visible", False)
            new_item_data.setdefault("hover_bbox", None)
            # entity_record is not typically part of clipboard_token

        elif item_type == "marker":
            new_item_data.setdefault("text", "New Marker")
            new_item_data.setdefault("description", "Marker description")
            new_item_data.setdefault("border_color", "#00ff00")
            new_item_data["entry_widget"] = None
            new_item_data["description_popup"] = None
            new_item_data["description_label"] = None
            new_item_data["description_visible"] = False
            new_item_data.setdefault("entry_width", 180)
            new_item_data["description_editor"] = None
            new_item_data["focus_pending"] = True
            new_item_data["border_canvas_id"] = None

        elif item_type in ["rectangle", "oval"]:
            # Shape-specific defaults if any were missed in copy (unlikely if copy is good)
            new_item_data.setdefault("shape_type", item_type)
            new_item_data.setdefault("width", DEFAULT_SHAPE_WIDTH)
            new_item_data.setdefault("height", DEFAULT_SHAPE_HEIGHT)
            new_item_data.setdefault("fill_color", self.current_shape_fill_color)
            new_item_data.setdefault("border_color", self.current_shape_border_color)
            new_item_data.setdefault("is_filled", self.shape_is_filled)
        
        self.tokens.append(new_item_data)
        self._update_canvas_images() # This will create canvas items and bind events
        self._persist_tokens()


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
        if self.selected_token is item_to_delete: self.selected_token = None
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
        entry.focus_set(); entry.select_range(0, tk.END)
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
            if zid: self.canvas.after_cancel(zid); setattr(self, attr, None)
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
        entry.focus_set(); entry.select_range(0, tk.END)
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
        if self._zoom_after_id: self.canvas.after_cancel(self._zoom_after_id)
        self._zoom_after_id = self.canvas.after(50, lambda: self._perform_zoom(final=False))
        if hasattr(self, '_zoom_final_after_id') and self._zoom_final_after_id:
            self.canvas.after_cancel(self._zoom_final_after_id)
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

    def _update_shape_controls_visibility(self):
        shape_tool_active = self.drawing_mode in ["rectangle", "oval"]
        try:
            shape_fill_label = getattr(self, 'shape_fill_label', None)
            shape_fill_mode_menu = getattr(self, 'shape_fill_mode_menu', None)
            shape_fill_color_button = getattr(self, 'shape_fill_color_button', None)
            shape_border_color_button = getattr(self, 'shape_border_color_button', None)
            if shape_tool_active:
                # Unpack all first to ensure a clean state and avoid issues with 'before'
                if shape_fill_label: shape_fill_label.pack_forget()
                if shape_fill_mode_menu: shape_fill_mode_menu.pack_forget()
                if shape_fill_color_button: shape_fill_color_button.pack_forget()
                if shape_border_color_button: shape_border_color_button.pack_forget()

                # Repack in desired order without 'before'
                if shape_fill_label: shape_fill_label.pack(side="left", padx=(10,2), pady=8)
                if shape_fill_mode_menu: shape_fill_mode_menu.pack(side="left", padx=5, pady=8)
                if shape_fill_color_button: shape_fill_color_button.pack(side="left", padx=(10,2), pady=8)
                if shape_border_color_button: shape_border_color_button.pack(side="left", padx=2, pady=8)
            else:
                if shape_fill_label: shape_fill_label.pack_forget()
                if shape_fill_mode_menu: shape_fill_mode_menu.pack_forget()
                if shape_fill_color_button: shape_fill_color_button.pack_forget()
                if shape_border_color_button: shape_border_color_button.pack_forget()
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
            if self.selected_token != shape: # If not already selected, select it
                # Simulate a press to ensure selection logic runs (clears other handles etc.)
                # This is a bit indirect; ideally _on_item_press would be callable without an event
                # For now, we assume right-click already selected it, or this will select it.
                # A cleaner way might be to have a dedicated _select_item(item) method.
                if self.selected_token != shape: # If a different item was selected
                    if self._graphical_edit_mode_item: # And another item was in graphical edit mode
                         self._remove_resize_handles() # This will also clear _graphical_edit_mode_item
                self.selected_token = shape # Directly select
            
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
