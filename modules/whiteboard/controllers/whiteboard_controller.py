import io
import math
import tkinter as tk
from tkinter import colorchooser
from typing import List, Dict, Tuple

import customtkinter as ctk
from PIL import Image, ImageTk
from screeninfo import get_monitors

from modules.helpers.logging_helper import log_module_import, log_info, log_warning
from modules.maps.utils.text_items import prompt_for_text, text_hit_test
from modules.whiteboard.services.whiteboard_storage import WhiteboardStorage, WhiteboardState
from modules.whiteboard.utils.whiteboard_renderer import render_whiteboard_image
from modules.whiteboard.views.web_whiteboard_view import (
    open_whiteboard_display,
    close_whiteboard_display,
)

log_module_import(__name__)


class WhiteboardController:
    def __init__(self, parent, *, root_app=None):
        self.parent = parent
        self._root_app = root_app

        self.tool = "pen"
        self.ink_color = "#FF0000"
        self.stroke_width = 4
        self.eraser_radius = 10
        self.text_size = 24

        self._active_points: List[Tuple[float, float]] = []
        self._preview_id = None
        self._eraser_active = False
        self._eraser_dirty = False

        self._player_view_window = None
        self._player_view_canvas = None
        self._player_view_image_id = None
        self._player_view_photo = None

        self._dragging_text_item = None
        self._dragging_text_offset = (0.0, 0.0)

        self.state: WhiteboardState = WhiteboardStorage.load_state()
        self.whiteboard_items: List[Dict] = list(self.state.items)
        self.board_size: Tuple[int, int] = tuple(self.state.size)

        self._build_ui()
        self._redraw_canvas()
        self._update_web_display_whiteboard()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        toolbar = ctk.CTkFrame(self.parent)
        toolbar.pack(fill="x", side="top", padx=6, pady=4)
        self._build_toolbar(toolbar)

        self.canvas = tk.Canvas(self.parent, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def _build_toolbar(self, toolbar: ctk.CTkFrame):
        tool_label = ctk.CTkLabel(toolbar, text="Tool")
        tool_label.pack(side="left", padx=(0, 6))
        tool_menu = ctk.CTkOptionMenu(
            toolbar,
            values=["Pen", "Text", "Eraser"],
            command=self._on_tool_change,
            width=140,
        )
        tool_menu.set("Pen")
        tool_menu.pack(side="left", padx=(0, 10))

        color_btn = ctk.CTkButton(toolbar, text="Ink Color", command=self._on_pick_color, width=110)
        color_btn.pack(side="left", padx=(0, 8))
        self._color_button = color_btn

        width_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        width_frame.pack(side="left", padx=(0, 8))
        width_label = ctk.CTkLabel(width_frame, text="Width")
        width_label.pack(side="left", padx=(0, 4))
        width_slider = ctk.CTkSlider(width_frame, from_=1, to=20, number_of_steps=19, command=self._on_width_change, width=140)
        width_slider.set(self.stroke_width)
        width_slider.pack(side="left")
        self._width_slider = width_slider

        eraser_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        eraser_frame.pack(side="left", padx=(0, 8))
        eraser_label = ctk.CTkLabel(eraser_frame, text="Eraser")
        eraser_label.pack(side="left", padx=(0, 4))
        eraser_slider = ctk.CTkSlider(
            eraser_frame,
            from_=4,
            to=60,
            number_of_steps=56,
            command=self._on_eraser_change,
            width=140,
        )
        eraser_slider.set(self.eraser_radius)
        eraser_slider.pack(side="left")
        self._eraser_slider = eraser_slider

        text_size_label = ctk.CTkLabel(toolbar, text="Text Size")
        text_size_label.pack(side="left", padx=(6, 4))
        text_sizes = ["16", "20", "24", "32", "40", "48"]
        text_menu = ctk.CTkOptionMenu(toolbar, values=text_sizes, command=self._on_text_size_change, width=100)
        text_menu.set(str(self.text_size))
        text_menu.pack(side="left", padx=(0, 10))
        self._text_menu = text_menu

        save_btn = ctk.CTkButton(toolbar, text="Save", command=self._persist_state)
        save_btn.pack(side="left", padx=(0, 6))

        clear_btn = ctk.CTkButton(toolbar, text="Clear", command=self.clear_board)
        clear_btn.pack(side="left", padx=(0, 6))

        player_btn = ctk.CTkButton(toolbar, text="Open Player View", command=self.open_player_view)
        player_btn.pack(side="left", padx=(0, 6))

    # ------------------------------------------------------------------
    # Event Handling
    # ------------------------------------------------------------------
    def _on_tool_change(self, selection: str):
        self.tool = selection.lower()

    def _on_pick_color(self):
        result = colorchooser.askcolor(color=self.ink_color)
        if result and result[1]:
            self.ink_color = result[1]
            try:
                self._color_button.configure(fg_color=self.ink_color)
            except Exception:
                pass

    def _on_width_change(self, value):
        try:
            self.stroke_width = max(1, float(value))
        except Exception:
            self.stroke_width = 4

    def _on_eraser_change(self, value):
        try:
            self.eraser_radius = max(2, float(value))
        except Exception:
            self.eraser_radius = 10

    def _on_text_size_change(self, value: str):
        try:
            self.text_size = int(value)
        except Exception:
            self.text_size = 24

    def _on_canvas_resize(self, event):
        new_size = (max(1, int(event.width)), max(1, int(event.height)))
        if new_size != self.board_size:
            self.board_size = new_size
            self._persist_state(update_only=False)

    def _on_mouse_down(self, event):
        if self.tool == "pen":
            self._active_points = [(event.x, event.y)]
            self._clear_preview()
        elif self.tool == "text":
            hit = self._find_text_item_at(event.x, event.y)
            if hit:
                self._start_text_drag(hit, event.x, event.y)
            else:
                self._create_text_at(event.x, event.y)
        elif self.tool == "eraser":
            self._eraser_active = True
            if self._erase_at(event.x, event.y):
                self._eraser_dirty = True

    def _on_mouse_move(self, event):
        if self.tool == "pen" and self._active_points:
            last = self._active_points[-1]
            dx = event.x - last[0]
            dy = event.y - last[1]
            if (dx * dx + dy * dy) >= 1.0:
                self._active_points.append((event.x, event.y))
                self._update_preview()
        elif self.tool == "text" and self._dragging_text_item:
            self._update_text_drag(event.x, event.y)
        elif self.tool == "eraser" and self._eraser_active:
            if self._erase_at(event.x, event.y):
                self._eraser_dirty = True

    def _on_mouse_up(self, _event):
        if self.tool == "pen" and self._active_points:
            self._finalize_stroke()
        elif self.tool == "eraser":
            if self._eraser_dirty:
                self._persist_state()
            self._eraser_active = False
            self._eraser_dirty = False
        elif self.tool == "text" and self._dragging_text_item:
            self._persist_state()
            self._dragging_text_item = None
            self._dragging_text_offset = (0.0, 0.0)

    def _on_double_click(self, event):
        if self.tool != "text":
            return
        hit = self._find_text_item_at(event.x, event.y)
        if not hit:
            return
        current_text = hit.get("text", "")
        updated = prompt_for_text(self.canvas, title="Edit Text", prompt="Update text:", initial=current_text)
        if updated is None:
            return
        hit["text"] = updated
        self._apply_text_update(hit)
        self._persist_state()

    # ------------------------------------------------------------------
    # Drawing Helpers
    # ------------------------------------------------------------------
    def _update_preview(self):
        if len(self._active_points) < 2:
            return
        flattened = []
        for x, y in self._active_points:
            flattened.extend([x, y])
        if self._preview_id and self.canvas.type(self._preview_id):
            self.canvas.coords(self._preview_id, *flattened)
            self.canvas.itemconfig(self._preview_id, fill=self.ink_color, width=self.stroke_width, smooth=True)
        else:
            self._preview_id = self.canvas.create_line(
                *flattened,
                fill=self.ink_color,
                width=self.stroke_width,
                smooth=True,
                capstyle="round",
                joinstyle="round",
            )

    def _clear_preview(self):
        if self._preview_id:
            try:
                self.canvas.delete(self._preview_id)
            except tk.TclError:
                pass
        self._preview_id = None

    def _finalize_stroke(self):
        points = self._simplify_polyline(self._active_points)
        self._active_points = []
        self._clear_preview()
        if len(points) < 2:
            return
        stroke = {
            "type": "stroke",
            "points": points,
            "color": self.ink_color,
            "width": self.stroke_width,
        }
        self.whiteboard_items.append(stroke)
        self._persist_state()

    def _simplify_polyline(self, points: List[Tuple[float, float]], tolerance: float = 1.5):
        if len(points) < 3:
            return list(points)

        def _distance(p1, p2):
            return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

        simplified = [points[0]]
        for p in points[1:-1]:
            if _distance(p, simplified[-1]) >= tolerance:
                simplified.append(p)
        simplified.append(points[-1])
        return simplified

    def _create_text_at(self, x: float, y: float):
        text = prompt_for_text(self.canvas, title="Add Text", prompt="Enter text:")
        if text is None:
            return
        entry = {
            "type": "text",
            "position": (x, y),
            "text": text,
            "color": self.ink_color,
            "size": self.text_size,
            "text_size": self.text_size,
        }
        self.whiteboard_items.append(entry)
        self._persist_state()

    def _find_text_item_at(self, x: float, y: float, *, radius: float = 6.0):
        for item in reversed(self.whiteboard_items):
            if item.get("type") != "text":
                continue
            if text_hit_test(self.canvas, item, screen_point=(x, y), radius=radius, zoom=1.0, pan=(0, 0)):
                return item
        return None

    def _start_text_drag(self, item: Dict, x: float, y: float):
        position = item.get("position", (0.0, 0.0))
        self._dragging_text_item = item
        self._dragging_text_offset = (x - position[0], y - position[1])

    def _update_text_drag(self, x: float, y: float):
        item = self._dragging_text_item
        if not item:
            return
        dx, dy = self._dragging_text_offset
        new_pos = (x - dx, y - dy)
        item["position"] = new_pos
        self._apply_text_update(item)

    def _apply_text_update(self, item: Dict):
        canvas_ids = item.get("canvas_ids") or ()
        if canvas_ids:
            try:
                position = item.get("position", (0, 0))
                font_size = int(item.get("size", self.text_size))
                item["text_size"] = font_size
                self.canvas.coords(canvas_ids[0], *position)
                self.canvas.itemconfig(
                    canvas_ids[0],
                    text=item.get("text", ""),
                    fill=item.get("color", self.ink_color),
                    font=("Arial", font_size),
                )
            except tk.TclError:
                pass

    def _erase_at(self, x: float, y: float) -> bool:
        changed = False
        remaining = []
        point = (x, y)
        radius = float(self.eraser_radius)
        radius_screen = radius
        for item in self.whiteboard_items:
            item_type = item.get("type")
            if item_type == "text":
                if text_hit_test(self.canvas, item, screen_point=point, radius=radius_screen, zoom=1.0, pan=(0, 0)):
                    changed = True
                    continue
            elif item_type == "stroke":
                if self._polyline_hits_point(item.get("points") or [], point, radius + float(item.get("width", 0)) / 2.0):
                    changed = True
                    continue
            remaining.append(item)
        if changed:
            self.whiteboard_items = remaining
            self._redraw_canvas()
        return changed

    def _polyline_hits_point(self, points: List[Tuple[float, float]], target: Tuple[float, float], radius: float) -> bool:
        if len(points) < 2:
            return False
        for start, end in zip(points, points[1:]):
            if self._point_to_segment_distance(target, start, end) <= radius:
                return True
        return False

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

    # ------------------------------------------------------------------
    # Persistence and Rendering
    # ------------------------------------------------------------------
    def _persist_state(self, update_only: bool = False):
        self.state.items = list(self.whiteboard_items)
        self.state.size = tuple(self.board_size)
        if not update_only:
            WhiteboardStorage.save_state(self.state)
        self._redraw_canvas()
        self._update_web_display_whiteboard()

    def _redraw_canvas(self):
        self.canvas.delete("all")
        for item in self.whiteboard_items:
            if item.get("type") == "stroke":
                points = item.get("points") or []
                if len(points) < 2:
                    continue
                flattened = []
                for x, y in points:
                    flattened.extend([x, y])
                line_id = self.canvas.create_line(
                    *flattened,
                    fill=item.get("color", self.ink_color),
                    width=item.get("width", self.stroke_width),
                    smooth=True,
                    capstyle="round",
                    joinstyle="round",
                )
                item["canvas_ids"] = (line_id,)
            elif item.get("type") == "text":
                pos = item.get("position") or (0, 0)
                size = int(item.get("size", self.text_size))
                item["text_size"] = size
                text_id = self.canvas.create_text(
                    pos[0],
                    pos[1],
                    text=item.get("text", ""),
                    fill=item.get("color", self.ink_color),
                    font=("Arial", size),
                    anchor="nw",
                )
                item["canvas_ids"] = (text_id,)

    def _render_whiteboard_image(self):
        return render_whiteboard_image(self.whiteboard_items, self.board_size)

    def _update_web_display_whiteboard(self):
        if not getattr(self, "_whiteboard_web_thread", None):
            self._update_player_view()
            return
        img = self._render_whiteboard_image()
        if img is None:
            return
        buffer = io.BytesIO()
        try:
            img.save(buffer, format="PNG")
            self._whiteboard_image_bytes = buffer.getvalue()
        finally:
            buffer.close()
        self._update_player_view()

    def clear_board(self):
        if not self.whiteboard_items:
            return
        self.whiteboard_items = []
        WhiteboardStorage.clear_state()
        self._persist_state()

    # ------------------------------------------------------------------
    # Player View management
    # ------------------------------------------------------------------
    def open_player_view(self):
        monitors = get_monitors()
        if not monitors:
            log_warning("No monitors available for whiteboard player view", func_name="WhiteboardController.open_player_view")
            return

        existing = getattr(self, "_player_view_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            self._update_player_view()
            return

        target = monitors[1] if len(monitors) > 1 else monitors[0]

        win = ctk.CTkToplevel(self.parent)
        win.title("Whiteboard Player View")
        win.geometry(f"{target.width}x{target.height}+{target.x}+{target.y}")
        win.lift(); win.focus_force(); win.attributes("-topmost", True); win.after_idle(lambda: win.attributes("-topmost", False))

        canvas = tk.Canvas(win, bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        self._player_view_window = win
        self._player_view_canvas = canvas
        self._player_view_image_id = None
        self._player_view_photo = None

        def _on_resize(_event=None):
            self._update_player_view()

        def _on_close():
            self.close_player_view()

        win.bind("<Configure>", _on_resize)
        win.protocol("WM_DELETE_WINDOW", _on_close)

        log_info("Opened player whiteboard view", func_name="WhiteboardController.open_player_view")
        self._update_player_view()

    def close_player_view(self):
        close_whiteboard_display(self)
        window = getattr(self, "_player_view_window", None)
        if window is not None:
            try:
                if window.winfo_exists():
                    window.destroy()
            except Exception:
                pass
        self._player_view_window = None
        self._player_view_canvas = None
        self._player_view_image_id = None
        self._player_view_photo = None

    def _update_player_view(self):
        canvas = getattr(self, "_player_view_canvas", None)
        window = getattr(self, "_player_view_window", None)
        if not canvas or not window or not window.winfo_exists():
            return

        img = self._render_whiteboard_image()
        if img is None:
            return

        canvas.update_idletasks()
        cw = max(canvas.winfo_width(), 1)
        ch = max(canvas.winfo_height(), 1)
        scale = min(cw / img.width, ch / img.height)
        if scale <= 0:
            return
        if scale != 1:
            target_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
            img = img.resize(target_size, resample=Image.LANCZOS)

        photo = ImageTk.PhotoImage(img)
        self._player_view_photo = photo
        if self._player_view_image_id:
            canvas.itemconfig(self._player_view_image_id, image=photo)
            canvas.coords(self._player_view_image_id, 0, 0)
        else:
            self._player_view_image_id = canvas.create_image(0, 0, image=photo, anchor="nw")

    def close(self):
        self.close_player_view()
