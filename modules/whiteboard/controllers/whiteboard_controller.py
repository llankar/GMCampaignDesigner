import io
import math
import os
import socket
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog
from typing import List, Dict, Tuple, Iterable, Callable, Any, cast

import customtkinter as ctk
from PIL import Image, ImageTk
from screeninfo import get_monitors

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import, log_info, log_warning
from modules.maps.utils.text_items import TextFontCache, prompt_for_text, text_hit_test
from modules.whiteboard.models.layer_types import WhiteboardLayer, normalize_layer
from modules.whiteboard.services.whiteboard_storage import WhiteboardStorage, WhiteboardState
from modules.whiteboard.services.whiteboard_history import WhiteboardHistory
from modules.whiteboard.utils.remote_access_guard import RemoteAccessGuard
from modules.whiteboard.utils.grid_overlay import GridOverlay
from modules.whiteboard.utils.stamp_assets import available_stamp_assets, load_tk_asset
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
        self._ui_dispatch_lock = threading.Lock()

        self.tool = "pen"
        self.ink_color = "#FF0000"
        self.stroke_width = 4
        self.eraser_radius = 10
        self.text_size = 24
        self.stamp_size = 64
        self.stamp_asset = None
        self.grid_enabled = False
        self.grid_size = 50
        self.snap_to_grid = False
        self.active_layer: str = WhiteboardLayer.SHARED.value
        self.show_shared_layer: bool = True
        self.show_gm_layer: bool = True

        self._active_points: List[Tuple[float, float]] = []
        self._preview_id = None
        self._eraser_active = False
        self._eraser_dirty = False
        self._eraser_recorded = False
        self._grid_overlay = GridOverlay()
        self._history = WhiteboardHistory()

        self.view_zoom: float = 1.0
        self._min_zoom: float = 0.5
        self._max_zoom: float = 3.0
        self._view_pan: Tuple[float, float] = (0.0, 0.0)
        self._base_pan: Tuple[float, float] = (0.0, 0.0)
        self._view_pan_offset: Tuple[float, float] = (0.0, 0.0)
        self._panning_active = False
        self._pan_start = (0.0, 0.0)
        self._pan_origin_offset = (0.0, 0.0)

        self._player_view_window = None
        self._player_view_canvas = None
        self._player_view_image_id = None
        self._player_view_photo = None
        self._share_qr_image: ctk.CTkImage | None = None

        self._font_cache = TextFontCache()

        self._dragging_text_item = None
        self._dragging_text_offset = (0.0, 0.0)
        self._dragging_stamp_item = None
        self._dragging_stamp_offset = (0.0, 0.0)

        self.state: WhiteboardState = WhiteboardStorage.load_state()
        self.whiteboard_items: List[Dict] = list(self.state.items)
        self.board_size: Tuple[int, int] = (int(self.state.size[0]), int(self.state.size[1]))
        self.view_zoom = max(self._min_zoom, min(self._max_zoom, float(getattr(self.state, "zoom", 1.0) or 1.0)))

        self.grid_enabled = bool(getattr(self.state, "grid_enabled", False))
        self.grid_size = int(getattr(self.state, "grid_size", 50) or 50)
        self.snap_to_grid = bool(getattr(self.state, "snap_to_grid", False))
        self.active_layer = normalize_layer(getattr(self.state, "active_layer", WhiteboardLayer.SHARED.value))
        self.show_shared_layer = bool(getattr(self.state, "show_shared_layer", True))
        self.show_gm_layer = bool(getattr(self.state, "show_gm_layer", True))
        self.remote_access_guard = RemoteAccessGuard.from_config(enabled=bool(getattr(self.state, "remote_edit_enabled", False)))

        assets = available_stamp_assets()
        self._stamp_assets_map = {os.path.basename(path): path for path in assets}
        if assets:
            self.stamp_asset = assets[0]

        self._build_ui()
        self._history.reset(self.whiteboard_items)
        self._redraw_canvas()
        self._update_web_display_whiteboard()
        self._ensure_web_display_running()

    def _dispatch_to_ui_thread(self, func: Callable[[], Any]):
        """
        Ensure operations touching Tk widgets run on the UI thread.

        Remote whiteboard edits arrive on the Flask server thread; directly
        invoking Tk calls from there can crash the interpreter. We marshal the
        work back to the UI thread and block until completion to preserve the
        request/response flow.
        """

        if threading.current_thread() is threading.main_thread():
            return func()

        result: dict[str, Any] = {}
        done = threading.Event()

        def _runner():
            try:
                result["value"] = func()
            except Exception as exc:  # noqa: BLE001
                result["error"] = exc
            finally:
                done.set()

        with self._ui_dispatch_lock:
            try:
                self.parent.after(0, _runner)
            except Exception:
                # If "after" is unavailable, execute immediately to avoid deadlock
                _runner()
                done.set()
                return result.get("value")

        if not done.wait(timeout=3):
            raise TimeoutError("Timed out applying whiteboard change on UI thread")
        if "error" in result:
            raise result["error"]
        return result.get("value")

    # ------------------------------------------------------------------
    # View Helpers
    # ------------------------------------------------------------------
    def _refresh_viewport(self):
        if not getattr(self, "canvas", None):
            return
        try:
            self.canvas.update_idletasks()
        except Exception:
            pass
        canvas_width = max(1, int(self.canvas.winfo_width()))
        canvas_height = max(1, int(self.canvas.winfo_height()))
        self._base_pan = self._compute_base_pan(canvas_width, canvas_height)
        self._update_view_pan()
        padded = 100000
        content_width = max(canvas_width, int(float(self.board_size[0]) * float(self.view_zoom))) + padded * 2
        content_height = max(canvas_height, int(float(self.board_size[1]) * float(self.view_zoom))) + padded * 2
        self.canvas.configure(
            scrollregion=(
                -padded,
                -padded,
                content_width - padded,
                content_height - padded,
            )
        )

    def _board_to_screen(self, x: float, y: float) -> Tuple[float, float]:
        px, py = self._view_pan
        return px + x * self.view_zoom, py + y * self.view_zoom

    def _screen_to_board(self, x: float, y: float) -> Tuple[float, float]:
        px, py = self._view_pan
        return (x - px) / self.view_zoom, (y - py) / self.view_zoom

    def _set_zoom(self, value: float):
        clamped = max(self._min_zoom, min(self._max_zoom, float(value)))
        if math.isclose(clamped, self.view_zoom, rel_tol=1e-3):
            return
        self.view_zoom = clamped
        self.state.zoom = self.view_zoom
        self._refresh_viewport()
        self._redraw_canvas()
        self._update_web_display_whiteboard()

    def _update_view_pan(self):
        base_x, base_y = self._base_pan
        off_x, off_y = self._view_pan_offset
        self._view_pan = (base_x + off_x, base_y + off_y)

    def _set_view_pan_offset(self, offset: Tuple[float, float]):
        self._view_pan_offset = offset
        self._update_view_pan()
        self._redraw_canvas()
        self._update_player_view()

    def _compute_base_pan(self, canvas_width: int, canvas_height: int) -> Tuple[float, float]:
        content_width = float(self.board_size[0]) * float(self.view_zoom)
        content_height = float(self.board_size[1]) * float(self.view_zoom)
        return (
            (canvas_width - content_width) / 2.0,
            (canvas_height - content_height) / 2.0,
        )

    def _get_canvas_size(self) -> Tuple[int, int]:
        if getattr(self, "canvas", None):
            try:
                return max(1, int(self.canvas.winfo_width())), max(1, int(self.canvas.winfo_height()))
            except Exception:
                pass
        return max(1, int(self.board_size[0])), max(1, int(self.board_size[1]))

    def _current_view_origin(self) -> Tuple[float, float]:
        return self._screen_to_board(0, 0)

    def _view_board_size(self) -> Tuple[int, int]:
        canvas_width, canvas_height = self._get_canvas_size()
        return (
            max(1, int(canvas_width / max(0.05, self.view_zoom))),
            max(1, int(canvas_height / max(0.05, self.view_zoom))),
        )

    def _translate_item_for_view(self, item: Dict, origin: Tuple[float, float]) -> Dict:
        origin_x, origin_y = origin
        translated = dict(item)
        item_type = item.get("type")
        if item_type == "stroke":
            points = item.get("points") or []
            translated["points"] = [(x - origin_x, y - origin_y) for x, y in points]
        elif item_type in ("text", "stamp"):
            pos = item.get("position") or (0, 0)
            translated["position"] = (pos[0] - origin_x, pos[1] - origin_y)
        return translated

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _resolve_ctk_color(self, value):
        if isinstance(value, (tuple, list)):
            colors = list(value)
            if not colors:
                return None
            primary = colors[0]
            secondary = colors[1] if len(colors) > 1 else primary
            return secondary if ctk.get_appearance_mode() == "Dark" else primary
        if isinstance(value, str):
            if " " in value:
                parts = value.split()
                if len(parts) >= 2:
                    return parts[1] if ctk.get_appearance_mode() == "Dark" else parts[0]
            return value
        try:
            return str(value)
        except Exception:
            return None

    def _build_ui(self):
        toolbar_container = ctk.CTkFrame(self.parent)
        toolbar_container.pack(fill="x", side="top", padx=6, pady=(2, 4))

        toolbar_canvas = tk.Canvas(toolbar_container, height=35, highlightthickness=0, bd=0)
        container_fg = self._resolve_ctk_color(toolbar_container.cget("fg_color"))
        if container_fg:
            toolbar_canvas.configure(bg=container_fg)
        scrollbar = ctk.CTkScrollbar(toolbar_container, orientation="horizontal", command=toolbar_canvas.xview)
        toolbar_canvas.configure(xscrollcommand=scrollbar.set)

        toolbar_canvas.pack(fill="x", side="top", expand=True)

        toolbar = ctk.CTkFrame(toolbar_canvas)
        toolbar_canvas.create_window((0, 0), window=toolbar, anchor="nw")

        def _update_scroll_region(_event=None):
            bbox = toolbar_canvas.bbox("all")
            toolbar_canvas.configure(scrollregion=bbox)
            if not bbox:
                if scrollbar.winfo_ismapped():
                    scrollbar.pack_forget()
                return
            content_width = bbox[2] - bbox[0]
            canvas_width = toolbar_canvas.winfo_width()
            if content_width > canvas_width:
                if not scrollbar.winfo_ismapped():
                    scrollbar.pack(fill="x", side="bottom")
            elif scrollbar.winfo_ismapped():
                scrollbar.pack_forget()

        def _sync_canvas_width(event):
            toolbar_canvas.configure(width=event.width)
            _update_scroll_region()

        toolbar.bind("<Configure>", _update_scroll_region)
        toolbar_container.bind("<Configure>", _sync_canvas_width)

        self._toolbar_container = toolbar_container
        self._build_toolbar(toolbar)

        self.canvas = tk.Canvas(self.parent, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind("<Button-5>", self._on_mouse_wheel)
        self.canvas.bind("<ButtonPress-2>", self._on_middle_mouse_down)
        self.canvas.bind("<B2-Motion>", self._on_middle_mouse_move)
        self.canvas.bind("<ButtonRelease-2>", self._on_middle_mouse_up)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        def _resize_canvas(_event=None):
            toolbar_height = self._toolbar_container.winfo_height()
            try:
                parent_width = int(self.parent.winfo_width())
                parent_height = int(self.parent.winfo_height())
            except Exception:
                return
            new_height = max(1, parent_height - toolbar_height)
            self.canvas.configure(width=parent_width, height=new_height)
            self._refresh_viewport()

        self.parent.bind("<Configure>", _resize_canvas, add="+")
        _resize_canvas()

    def _build_toolbar(self, toolbar: ctk.CTkFrame):
        tool_label = ctk.CTkLabel(toolbar, text="Tool")
        tool_label.pack(side="left", padx=(0, 4))
        tool_menu = ctk.CTkOptionMenu(
            toolbar,
            values=["Pen", "Text", "Stamp", "Eraser"],
            command=self._on_tool_change,
            width=130,
        )
        tool_menu.set("Pen")
        tool_menu.pack(side="left", padx=(0, 6))

        tool_controls_holder = ctk.CTkFrame(toolbar, fg_color="transparent")
        tool_controls_holder.pack(side="left", padx=(0, 8))

        pen_frame = ctk.CTkFrame(tool_controls_holder, fg_color="transparent")
        color_btn = ctk.CTkButton(
            pen_frame,
            text="",
            command=self._on_pick_color,
            width=36,
            height=32,
            fg_color=self.ink_color,
            hover_color=self.ink_color,
            border_width=2,
            border_color="#3a3a3a",
        )
        color_btn.pack(side="left", padx=(0, 6))
        self._color_button = color_btn

        width_values = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
        if self.stroke_width not in width_values:
            width_values.append(int(self.stroke_width))
            width_values = sorted(set(width_values))
        width_menu = ctk.CTkOptionMenu(
            pen_frame,
            values=[str(v) for v in width_values],
            command=self._on_width_change,
            width=88,
        )
        width_menu.set(str(self.stroke_width))
        width_menu.pack(side="left", padx=(0, 6))
        self._width_menu = width_menu

        eraser_frame = ctk.CTkFrame(tool_controls_holder, fg_color="transparent")
        eraser_values = [4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40, 48, 56, 60]
        if self.eraser_radius not in eraser_values:
            eraser_values.append(int(self.eraser_radius))
            eraser_values = sorted(set(eraser_values))
        eraser_menu = ctk.CTkOptionMenu(
            eraser_frame,
            values=[str(v) for v in eraser_values],
            command=self._on_eraser_change,
            width=88,
        )
        eraser_menu.set(str(self.eraser_radius))
        eraser_menu.pack(side="left", padx=(0, 6))
        self._eraser_menu = eraser_menu

        text_frame = ctk.CTkFrame(tool_controls_holder, fg_color="transparent")
        text_size_label = ctk.CTkLabel(text_frame, text="Text Size")
        text_size_label.pack(side="left", padx=(0, 4))
        text_sizes = ["16", "20", "24", "32", "40", "48"]
        text_menu = ctk.CTkOptionMenu(text_frame, values=text_sizes, command=self._on_text_size_change, width=92)
        text_menu.set(str(self.text_size))
        text_menu.pack(side="left", padx=(0, 6))
        self._text_menu = text_menu

        stamp_frame = ctk.CTkFrame(tool_controls_holder, fg_color="transparent")
        ctk.CTkLabel(stamp_frame, text="Stamp").pack(side="left", padx=(0, 4))
        self._stamp_label_var = tk.StringVar(value=os.path.basename(self.stamp_asset) if self.stamp_asset else "Choose Stamp")
        stamp_btn = ctk.CTkButton(
            stamp_frame,
            text="📁",
            width=36,
            height=32,
            command=self._on_select_stamp_asset,
        )
        stamp_btn.pack(side="left", padx=(0, 4))
        stamp_values = [24, 32, 40, 48, 64, 80, 96, 120, 144, 168, 196]
        if self.stamp_size not in stamp_values:
            stamp_values.append(int(self.stamp_size))
            stamp_values = sorted(set(stamp_values))
        stamp_size_menu = ctk.CTkOptionMenu(
            stamp_frame,
            values=[str(v) for v in stamp_values],
            command=self._on_stamp_size_change,
            width=96,
        )
        stamp_size_menu.set(str(self.stamp_size))
        stamp_size_menu.pack(side="left")
        self._stamp_size_menu = stamp_size_menu

        self._tool_frames = {
            "pen": pen_frame,
            "eraser": eraser_frame,
            "text": text_frame,
            "stamp": stamp_frame,
        }

        layer_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        layer_frame.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(layer_frame, text="Layer").pack(side="left", padx=(0, 4))
        layer_menu = ctk.CTkOptionMenu(
            layer_frame,
            values=["Shared", "GM Only"],
            command=self._on_layer_change,
            width=112,
        )
        layer_menu.set("GM Only" if self.active_layer == WhiteboardLayer.GM.value else "Shared")
        layer_menu.pack(side="left")
        self._layer_menu = layer_menu

        self._build_toggle_menu(toolbar)

        grid_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        grid_frame.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(grid_frame, text="Grid Size").pack(side="left", padx=(0, 4))
        grid_values = list(range(20, 201, 20))
        if self.grid_size not in grid_values:
            grid_values.append(int(self.grid_size))
            grid_values = sorted(set(grid_values))
        grid_menu = ctk.CTkOptionMenu(
            grid_frame,
            values=[str(v) for v in grid_values],
            command=self._on_grid_size_change,
            width=90,
        )
        grid_menu.set(str(self.grid_size))
        grid_menu.pack(side="left")
        self._grid_menu = grid_menu

        history_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        history_frame.pack(side="left", padx=(0, 6))
        undo_btn = ctk.CTkButton(history_frame, text="Undo", command=self._undo_action, width=76)
        undo_btn.pack(side="left", padx=(0, 4))
        redo_btn = ctk.CTkButton(history_frame, text="Redo", command=self._redo_action, width=76)
        redo_btn.pack(side="left")

        remote_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        remote_frame.pack(side="left", padx=(0, 6))
        self._remote_toggle_var = tk.BooleanVar(value=self.remote_access_guard.enabled)
        remote_switch = ctk.CTkSwitch(
            remote_frame,
            text="Player Editing",
            variable=self._remote_toggle_var,
            command=self._on_remote_toggle,
        )
        remote_switch.pack(side="left", padx=(0, 4))
        share_btn = ctk.CTkButton(remote_frame, text="Share Link", command=self._open_share_dialog, width=110)
        share_btn.pack(side="left")

        save_btn = ctk.CTkButton(toolbar, text="Save", command=self._persist_state)
        save_btn.pack(side="left", padx=(0, 4))

        clear_btn = ctk.CTkButton(toolbar, text="Clear", command=self.clear_board)
        clear_btn.pack(side="left", padx=(0, 4))

        player_btn = ctk.CTkButton(toolbar, text="Open Player View", command=self.open_player_view)
        player_btn.pack(side="left", padx=(0, 4))

        self._update_tool_controls()

    def _build_toggle_menu(self, toolbar: ctk.CTkFrame):
        menu_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        menu_frame.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(menu_frame, text="Visibility/Grid").pack(side="left", padx=(0, 4))
        toggle_menu = ctk.CTkOptionMenu(
            menu_frame,
            values=self._toggle_menu_values(),
            command=self._handle_toggle_menu_selection,
            width=152,
        )
        toggle_menu.set("Visibility/Grid")
        toggle_menu.pack(side="left")
        self._toggle_menu = toggle_menu

    def _toggle_menu_values(self):
        return [
            self._format_toggle_option("Shared visible", self.show_shared_layer),
            self._format_toggle_option("GM visible", self.show_gm_layer),
            self._format_toggle_option("Grid enabled", self.grid_enabled),
            self._format_toggle_option("Snap to grid", self.snap_to_grid),
        ]

    def _format_toggle_option(self, label: str, enabled: bool) -> str:
        return f"☑ {label}" if enabled else f"☐ {label}"

    def _handle_toggle_menu_selection(self, selection: str):
        label = selection[2:].strip() if selection.startswith(("☑", "☐")) else selection
        handlers = {
            "Shared visible": lambda: self._on_toggle_shared_layer(not self.show_shared_layer),
            "GM visible": lambda: self._on_toggle_gm_layer(not self.show_gm_layer),
            "Grid enabled": lambda: self._on_toggle_grid(not self.grid_enabled),
            "Snap to grid": lambda: self._on_toggle_snap(not self.snap_to_grid),
        }
        action = handlers.get(label)
        if action:
            action()
        self._refresh_toggle_menu()

    def _refresh_toggle_menu(self):
        toggle_menu = getattr(self, "_toggle_menu", None)
        if not toggle_menu:
            return
        values = self._toggle_menu_values()
        try:
            toggle_menu.configure(values=values)
            toggle_menu.set("Visibility/Grid")
        except Exception:
            pass

    def _on_remote_toggle(self):
        enabled = bool(self._remote_toggle_var.get())
        self.remote_access_guard.set_enabled(enabled)
        self._ensure_web_display_running()
        self._persist_state(update_only=False)

    def _local_ip_address(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("8.8.8.8", 80))
                return probe.getsockname()[0]
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"

    def _resolve_public_host(self) -> str:
        raw_host = str(ConfigHelper.get("WhiteboardServer", "public_host", fallback="") or "").strip()
        cleaned_host = raw_host.split("://", 1)[-1].split("/", 1)[0]

        try:
            socket.inet_aton(cleaned_host)
            return cleaned_host
        except OSError:
            pass

        if cleaned_host:
            try:
                resolved = socket.gethostbyname(cleaned_host)
                if resolved:
                    return resolved
            except Exception:
                pass

        return self._local_ip_address()

    def _build_share_url(self) -> str:
        configured_port = ConfigHelper.get("WhiteboardServer", "port", fallback="") or getattr(self, "_whiteboard_port", None)
        port = str(configured_port or "").strip()
        host = self._resolve_public_host()
        base = f"http://{str(host).rstrip('/')}"
        if port and f":{port}" not in base.split("//", 1)[-1]:
            base = f"{base}:{port}"
        token = getattr(self.remote_access_guard, "token", "")
        query = f"?token={token}" if token else ""
        return f"{base}/{query}"

    def _build_qr_image(self, url: str) -> ctk.CTkImage | None:
        try:
            import qrcode
            from qrcode.image.pil import PilImage

            qr_image = qrcode.make(url, image_factory=PilImage)
            pil_image = cast(Image.Image, qr_image.get_image() if hasattr(qr_image, "get_image") else qr_image)
            qr_size = 320
            resized = pil_image.resize((qr_size, qr_size))
            return ctk.CTkImage(light_image=resized, dark_image=resized, size=(qr_size, qr_size))
        except Exception:
            return None

    def _open_share_dialog(self):
        self._ensure_web_display_running()
        dialog = ctk.CTkToplevel(self.parent)
        dialog.title("Share Whiteboard")
        dialog.geometry("580x460")
        try:
            dialog.transient(self.parent)
            dialog.lift()
            dialog.focus_force()
            dialog.attributes("-topmost", True)
            dialog.after(200, lambda: dialog.attributes("-topmost", False))
        except Exception:
            pass

        url = self._build_share_url()
        description = (
            "Provide this link to players. They will need the GM editing toggle enabled "
            "and, if configured, the token present in the URL."
        )
        ctk.CTkLabel(dialog, text=description, wraplength=480, justify="left").pack(padx=10, pady=(10, 8))

        entry = ctk.CTkEntry(dialog, width=460)
        entry.insert(0, url)
        entry.pack(padx=10, pady=(0, 6))

        def _copy_url():
            try:
                dialog.clipboard_clear()
                dialog.clipboard_append(entry.get())
            except Exception:
                pass

        copy_btn = ctk.CTkButton(dialog, text="Copy URL", command=_copy_url)
        copy_btn.pack(pady=(0, 10))

        qr = self._build_qr_image(url)
        if qr is not None:
            self._share_qr_image = qr
            qr_label = ctk.CTkLabel(dialog, image=qr, text="")
            qr_label.pack(pady=(4, 6))
        else:
            ctk.CTkLabel(dialog, text="Install the 'qrcode' package to render QR codes.").pack(pady=(4, 6))

    # ------------------------------------------------------------------
    # Event Handling
    # ------------------------------------------------------------------
    def _update_tool_controls(self):
        frames = getattr(self, "_tool_frames", {})
        active = frames.get(self.tool)
        for frame in frames.values():
            try:
                frame.pack_forget()
            except Exception:
                pass
        if active:
            try:
                active.pack(side="left", padx=(0, 6))
            except Exception:
                pass

    def _on_tool_change(self, selection: str):
        self.tool = selection.lower()
        self._update_tool_controls()

    def _on_pick_color(self):
        result = colorchooser.askcolor(color=self.ink_color)
        if result and result[1]:
            self.ink_color = result[1]
            try:
                self._color_button.configure(fg_color=self.ink_color, hover_color=self.ink_color)
            except Exception:
                pass

    def _on_select_stamp_asset(self):
        selection = filedialog.askopenfilename(
            title="Choose Stamp Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if selection:
            self.stamp_asset = selection
            
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

    def _on_layer_change(self, selection: str):
        self.active_layer = WhiteboardLayer.GM.value if selection.lower().startswith("gm") else WhiteboardLayer.SHARED.value
        self.state.active_layer = self.active_layer
        self._persist_state(update_only=True)

    def _on_toggle_shared_layer(self, value=None):
        if value is None:
            value = not self.show_shared_layer
        self.show_shared_layer = bool(value)
        self.state.show_shared_layer = self.show_shared_layer
        self._refresh_toggle_menu()
        self._persist_state(update_only=True)

    def _on_toggle_gm_layer(self, value=None):
        if value is None:
            value = not self.show_gm_layer
        self.show_gm_layer = bool(value)
        self.state.show_gm_layer = self.show_gm_layer
        self._refresh_toggle_menu()
        self._persist_state(update_only=True)

    def _on_toggle_grid(self, value=None):
        if value is None:
            value = not self.grid_enabled
        self.grid_enabled = bool(value)
        self.state.grid_enabled = self.grid_enabled
        self._refresh_toggle_menu()
        self._persist_state(update_only=True)

    def _on_grid_size_change(self, value):
        try:
            self.grid_size = max(10, int(float(value)))
        except Exception:
            self.grid_size = 50
        self.state.grid_size = self.grid_size
        self._persist_state(update_only=True)

    def _on_toggle_snap(self, value=None):
        if value is None:
            value = not self.snap_to_grid
        self.snap_to_grid = bool(value)
        self.state.snap_to_grid = self.snap_to_grid
        self._refresh_toggle_menu()
        self._persist_state(update_only=True)

    def _on_stamp_size_change(self, value):
        try:
            self.stamp_size = max(16, int(float(value)))
        except Exception:
            self.stamp_size = 64

    def _on_canvas_resize(self, event):
        new_size: Tuple[int, int] = (max(1, int(event.width)), max(1, int(event.height)))
        self._refresh_viewport()
        if new_size != self.board_size:
            self.board_size = new_size
            self._persist_state(update_only=False)
        else:
            self._redraw_canvas()

    def _on_mouse_wheel(self, event):
        delta = 0
        if hasattr(event, "delta") and event.delta:
            delta = event.delta
        elif getattr(event, "num", None) == 4:
            delta = 120
        elif getattr(event, "num", None) == 5:
            delta = -120
        if delta == 0:
            return
        step = 1.1 if delta > 0 else 0.9
        self._set_zoom(self.view_zoom * step)

    def _on_middle_mouse_down(self, event):
        self._panning_active = True
        self._pan_start = (event.x, event.y)
        self._pan_origin_offset = self._view_pan_offset

    def _on_middle_mouse_move(self, event):
        if not self._panning_active:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        new_offset = (self._pan_origin_offset[0] + dx, self._pan_origin_offset[1] + dy)
        self._set_view_pan_offset(new_offset)

    def _on_middle_mouse_up(self, _event):
        self._panning_active = False

    def _on_mouse_down(self, event):
        board_x, board_y = self._screen_to_board(event.x, event.y)
        if self.tool == "pen":
            snapped = self._snap_point(board_x, board_y) if self.snap_to_grid else (board_x, board_y)
            self._active_points = [snapped]
            self._clear_preview()
        elif self.tool == "text":
            hit = self._find_text_item_at(board_x, board_y)
            if hit:
                self._history.checkpoint(self.whiteboard_items)
                self._start_text_drag(hit, board_x, board_y)
            else:
                self._create_text_at(board_x, board_y)
        elif self.tool == "stamp":
            hit = self._find_stamp_item_at(board_x, board_y)
            if hit:
                self._history.checkpoint(self.whiteboard_items)
                self._start_stamp_drag(hit, board_x, board_y)
            else:
                self._add_stamp_at(board_x, board_y)
        elif self.tool == "eraser":
            self._eraser_active = True
            if self._erase_at(board_x, board_y):
                self._eraser_dirty = True
                self._eraser_recorded = True

    def _on_mouse_move(self, event):
        board_x, board_y = self._screen_to_board(event.x, event.y)
        if self.tool == "pen" and self._active_points:
            last = self._active_points[-1]
            target_point = self._snap_point(board_x, board_y) if self.snap_to_grid else (board_x, board_y)
            dx = target_point[0] - last[0]
            dy = target_point[1] - last[1]
            if (dx * dx + dy * dy) >= 1.0:
                self._active_points.append(target_point)
                self._update_preview()
        elif self.tool == "text" and self._dragging_text_item:
            self._update_text_drag(board_x, board_y)
        elif self.tool == "stamp" and self._dragging_stamp_item:
            self._update_stamp_drag(board_x, board_y)
        elif self.tool == "eraser" and self._eraser_active:
            if self._erase_at(board_x, board_y):
                self._eraser_dirty = True

    def _on_mouse_up(self, _event):
        if self.tool == "pen" and self._active_points:
            self._finalize_stroke()
        elif self.tool == "eraser":
            if self._eraser_dirty:
                self._persist_state()
            self._eraser_active = False
            self._eraser_dirty = False
            self._eraser_recorded = False
        elif self.tool == "text" and self._dragging_text_item:
            self._persist_state()
            self._dragging_text_item = None
            self._dragging_text_offset = (0.0, 0.0)
        elif self.tool == "stamp" and self._dragging_stamp_item:
            self._persist_state()
            self._dragging_stamp_item = None
            self._dragging_stamp_offset = (0.0, 0.0)

    def _on_double_click(self, event):
        if self.tool != "text":
            return
        board_x, board_y = self._screen_to_board(event.x, event.y)
        hit = self._find_text_item_at(board_x, board_y)
        if not hit:
            return
        current_text = hit.get("text", "")
        updated = prompt_for_text(self.canvas, title="Edit Text", prompt="Update text:", initial=current_text)
        if updated is None:
            return
        self._history.checkpoint(self.whiteboard_items)
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
            sx, sy = self._board_to_screen(x, y)
            flattened.extend([sx, sy])
        width = max(1.0, float(self.stroke_width) * float(self.view_zoom))
        if self._preview_id and self.canvas.type(self._preview_id):
            self.canvas.coords(self._preview_id, *flattened)
            self.canvas.itemconfig(
                self._preview_id,
                fill=self.ink_color,
                width=width,
                smooth=False,
                capstyle="butt",
                joinstyle="miter",
            )
        else:
            self._preview_id = self.canvas.create_line(
                *flattened,
                fill=self.ink_color,
                width=width,
                smooth=False,
                capstyle="butt",
                joinstyle="miter",
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
        self._history.checkpoint(self.whiteboard_items)
        stroke = {
            "type": "stroke",
            "points": points,
            "color": self.ink_color,
            "width": self.stroke_width,
            "layer": self.active_layer,
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

    # ------------------------------------------------------------------
    # Remote Submissions
    # ------------------------------------------------------------------
    def handle_remote_stroke(self, *, points, color: str, width: float):
        def _apply():
            clean_points: List[Tuple[float, float]] = []
            for point in points:
                try:
                    x, y = float(point[0]), float(point[1])
                    clean_points.append((x, y))
                except Exception:
                    continue
            simplified = self._simplify_polyline(clean_points)
            if len(simplified) < 2:
                raise ValueError("Not enough points to record stroke")
            self._history.checkpoint(self.whiteboard_items)
            stroke = {
                "type": "stroke",
                "points": simplified,
                "color": color,
                "width": float(width),
                "layer": WhiteboardLayer.SHARED.value,
            }
            self.whiteboard_items.append(stroke)
            self._persist_state()

        self._dispatch_to_ui_thread(_apply)

    def handle_remote_text(self, *, text: str, position, color: str, size: float):
        def _apply():
            if not isinstance(position, (list, tuple)) or len(position) != 2:
                raise ValueError("Position must include x and y")
            pos = (float(position[0]), float(position[1]))
            item = {
                "type": "text",
                "text": text,
                "position": pos,
                "color": color,
                "size": float(size),
                "text_size": float(size),
                "layer": WhiteboardLayer.SHARED.value,
            }
            self._history.checkpoint(self.whiteboard_items)
            self.whiteboard_items.append(item)
            self._persist_state()

        self._dispatch_to_ui_thread(_apply)

    def handle_remote_undo(self):
        def _apply():
            restored, changed = self._history.undo(self.whiteboard_items)
            if changed:
                self.whiteboard_items = restored
                self._persist_state()

        self._dispatch_to_ui_thread(_apply)

    def _create_text_at(self, x: float, y: float):
        text = prompt_for_text(self.canvas, title="Add Text", prompt="Enter text:")
        if text is None:
            return
        self._history.checkpoint(self.whiteboard_items)
        point = self._snap_point(x, y) if self.snap_to_grid else (x, y)
        entry = {
            "type": "text",
            "position": point,
            "text": text,
            "color": self.ink_color,
            "size": self.text_size,
            "text_size": self.text_size,
            "layer": self.active_layer,
        }
        self.whiteboard_items.append(entry)
        self._persist_state()

    def _add_stamp_at(self, x: float, y: float):
        if not self.stamp_asset:
            return
        self._history.checkpoint(self.whiteboard_items)
        point = self._snap_point(x, y) if self.snap_to_grid else (x, y)
        stamp = {
            "type": "stamp",
            "position": point,
            "asset": self.stamp_asset,
            "size": self.stamp_size,
            "layer": self.active_layer,
        }
        self.whiteboard_items.append(stamp)
        self._persist_state()

    def _find_stamp_item_at(self, x: float, y: float):
        for item in reversed(self.whiteboard_items):
            if item.get("type") != "stamp":
                continue
            layer = normalize_layer(item.get("layer"))
            if layer == WhiteboardLayer.SHARED.value and not self.show_shared_layer:
                continue
            if layer == WhiteboardLayer.GM.value and not self.show_gm_layer:
                continue
            pos = item.get("position") or (0.0, 0.0)
            size = float(item.get("size", self.stamp_size))
            if pos[0] <= x <= pos[0] + size and pos[1] <= y <= pos[1] + size:
                return item
        return None

    def _find_text_item_at(self, x: float, y: float, *, radius: float = 6.0):
        for item in reversed(self.whiteboard_items):
            if item.get("type") != "text":
                continue
            screen_point = self._board_to_screen(x, y)
            if text_hit_test(self.canvas, item, screen_point=screen_point, radius=radius * self.view_zoom, zoom=self.view_zoom, pan=self._view_pan):
                return item
        return None

    def _start_stamp_drag(self, item: Dict, x: float, y: float):
        position = item.get("position", (0.0, 0.0))
        self._dragging_stamp_item = item
        self._dragging_stamp_offset = (x - position[0], y - position[1])

    def _update_stamp_drag(self, x: float, y: float):
        item = self._dragging_stamp_item
        if not item:
            return
        dx, dy = self._dragging_stamp_offset
        new_pos = (x - dx, y - dy)
        if self.snap_to_grid:
            new_pos = self._snap_point(*new_pos)
        item["position"] = new_pos
        self._apply_stamp_update(item)

    def _apply_stamp_update(self, item: Dict):
        canvas_ids = item.get("canvas_ids") or ()
        if canvas_ids:
            try:
                position = item.get("position", (0, 0))
                screen_pos = self._board_to_screen(*position)
                self.canvas.coords(canvas_ids[0], *screen_pos)
            except tk.TclError:
                pass

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
        if self.snap_to_grid:
            new_pos = self._snap_point(*new_pos)
        item["position"] = new_pos
        self._apply_text_update(item)

    def _apply_text_update(self, item: Dict):
        canvas_ids = item.get("canvas_ids") or ()
        if canvas_ids:
            try:
                position = item.get("position", (0, 0))
                screen_pos = self._board_to_screen(*position)
                font_size = int(item.get("size", self.text_size))
                item["text_size"] = font_size
                scaled_font_size = max(1, int(font_size * self.view_zoom))
                self.canvas.coords(canvas_ids[0], *screen_pos)
                self.canvas.itemconfig(
                    canvas_ids[0],
                    text=item.get("text", ""),
                    fill=item.get("color", self.ink_color),
                    font=self._font_cache.tk_font(scaled_font_size),
                )
            except tk.TclError:
                pass

    def _iter_visible_items(self, *, for_player: bool = False) -> Iterable[Dict]:
        for item in self.whiteboard_items:
            layer = normalize_layer(item.get("layer"))
            if for_player and layer == WhiteboardLayer.GM.value:
                continue
            if not for_player:
                if layer == WhiteboardLayer.SHARED.value and not self.show_shared_layer:
                    continue
                if layer == WhiteboardLayer.GM.value and not self.show_gm_layer:
                    continue
            yield item

    def _erase_at(self, x: float, y: float) -> bool:
        changed = False
        remaining = []
        point = (x, y)
        screen_point = self._board_to_screen(x, y)
        radius = float(self.eraser_radius)
        radius_screen = radius * self.view_zoom
        for item in self.whiteboard_items:
            layer = normalize_layer(item.get("layer"))
            if layer == WhiteboardLayer.SHARED.value and not self.show_shared_layer:
                remaining.append(item)
                continue
            if layer == WhiteboardLayer.GM.value and not self.show_gm_layer:
                remaining.append(item)
                continue
            item_type = item.get("type")
            if item_type == "text":
                if text_hit_test(self.canvas, item, screen_point=screen_point, radius=radius_screen, zoom=self.view_zoom, pan=self._view_pan):
                    changed = True
                    continue
            elif item_type == "stroke":
                if self._polyline_hits_point(item.get("points") or [], point, radius + float(item.get("width", 0)) / 2.0):
                    changed = True
                    continue
            elif item_type == "stamp":
                pos = item.get("position") or (0, 0)
                size = float(item.get("size", self.stamp_size))
                if abs(pos[0] - x) <= radius + size / 2 and abs(pos[1] - y) <= radius + size / 2:
                    changed = True
                    continue
            remaining.append(item)
        if changed:
            if not self._eraser_recorded:
                self._history.checkpoint(self.whiteboard_items)
                self._eraser_recorded = True
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

    def _snap_point(self, x: float, y: float) -> Tuple[float, float]:
        grid = max(1, int(self.grid_size))
        snapped_x = round(x / grid) * grid
        snapped_y = round(y / grid) * grid
        return float(snapped_x), float(snapped_y)

    # ------------------------------------------------------------------
    # Persistence and Rendering
    # ------------------------------------------------------------------
    def _persist_state(self, update_only: bool = False):
        self.state.items = list(self.whiteboard_items)
        self.state.size = (int(self.board_size[0]), int(self.board_size[1]))
        self.state.grid_enabled = self.grid_enabled
        self.state.grid_size = int(self.grid_size)
        self.state.snap_to_grid = self.snap_to_grid
        self.state.active_layer = self.active_layer
        self.state.show_shared_layer = self.show_shared_layer
        self.state.show_gm_layer = self.show_gm_layer
        self.state.zoom = self.view_zoom
        self.state.remote_edit_enabled = bool(getattr(self, "remote_access_guard", None) and self.remote_access_guard.enabled)
        if not update_only:
            WhiteboardStorage.save_state(self.state)
        self._redraw_canvas()
        self._update_web_display_whiteboard()

    def _undo_action(self):
        restored, changed = self._history.undo(self.whiteboard_items)
        if changed:
            self.whiteboard_items = restored
            self._persist_state()

    def _redo_action(self):
        restored, changed = self._history.redo(self.whiteboard_items)
        if changed:
            self.whiteboard_items = restored
            self._persist_state()

    def _redraw_canvas(self):
        self._refresh_viewport()
        self.canvas.delete("all")
        if self.grid_enabled:
            viewport_size = self._get_canvas_size()
            origin = self._current_view_origin()
            self._grid_overlay.draw_on_canvas(
                self.canvas,
                viewport_size,
                self.grid_size,
                zoom=self.view_zoom,
                pan=self._view_pan,
                origin=origin,
            )
        for item in self._iter_visible_items():
            if item.get("type") == "stroke":
                points = item.get("points") or []
                if len(points) < 2:
                    continue
                flattened = []
                for x, y in points:
                    sx, sy = self._board_to_screen(x, y)
                    flattened.extend([sx, sy])
                line_width = max(1.0, float(item.get("width", self.stroke_width)) * float(self.view_zoom))
                line_id = self.canvas.create_line(
                    *flattened,
                    fill=item.get("color", self.ink_color),
                    width=line_width,
                    smooth=False,
                    capstyle="butt",
                    joinstyle="miter",
                )
                item["canvas_ids"] = (line_id,)
            elif item.get("type") == "text":
                pos = item.get("position") or (0, 0)
                size = int(item.get("size", self.text_size))
                item["text_size"] = size
                screen_pos = self._board_to_screen(*pos)
                scaled_size = max(1, int(size * self.view_zoom))
                text_id = self.canvas.create_text(
                    screen_pos[0],
                    screen_pos[1],
                    text=item.get("text", ""),
                    fill=item.get("color", self.ink_color),
                    font=self._font_cache.tk_font(scaled_size),
                    anchor="nw",
                )
                item["canvas_ids"] = (text_id,)
            elif item.get("type") == "stamp":
                asset_path = item.get("asset")
                if not asset_path:
                    continue
                pos = item.get("position") or (0, 0)
                size = int(item.get("size", self.stamp_size))
                scaled_size = max(1, int(size * self.view_zoom))
                try:
                    photo = load_tk_asset(asset_path, scaled_size)
                    screen_pos = self._board_to_screen(*pos)
                    stamp_id = self.canvas.create_image(screen_pos[0], screen_pos[1], image=photo, anchor="nw")
                    item["canvas_ids"] = (stamp_id,)
                    item["_image_ref"] = photo
                except Exception:
                    continue
        if self._active_points:
            self._update_preview()

    def _render_whiteboard_image(
        self,
        *,
        include_text: bool = True,
        for_player: bool = False,
        viewport_size: Tuple[int, int] | None = None,
        origin: Tuple[float, float] | None = None,
        zoom: float | None = None,
    ):
        viewport_size = viewport_size or self._view_board_size()
        origin = origin if origin is not None else self._current_view_origin()
        zoom_value = self.view_zoom if zoom is None else float(zoom)
        visible_items = [
            self._translate_item_for_view(item, origin)
            for item in self._iter_visible_items(for_player=for_player)
        ]
        return render_whiteboard_image(
            visible_items,
            viewport_size,
            font_cache=self._font_cache,
            include_text=include_text,
            grid_enabled=self.grid_enabled,
            grid_size=self.grid_size,
            grid_origin=origin,
            for_player=for_player,
            zoom=zoom_value,
        )

    def _update_web_display_whiteboard(self):
        if not getattr(self, "_whiteboard_web_thread", None):
            self._update_player_view()
            return
        img = self._render_whiteboard_image(
            for_player=True,
            viewport_size=self.board_size,
            origin=(0.0, 0.0),
            zoom=1.0,
        )
        if img is None:
            return
        buffer = io.BytesIO()
        try:
            img.save(buffer, format="PNG")
            self._whiteboard_image_bytes = buffer.getvalue()
        finally:
            buffer.close()
        self._update_player_view()

    def _ensure_web_display_running(self):
        if getattr(self, "_whiteboard_web_thread", None):
            return
        try:
            open_whiteboard_display(self)
        except Exception:
            log_warning("Unable to start whiteboard web display", func_name="WhiteboardController._ensure_web_display_running")

    def clear_board(self):
        if not self.whiteboard_items:
            return
        self._history.checkpoint(self.whiteboard_items)
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

        canvas = tk.Canvas(win, bg="white", highlightthickness=0)
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
        if threading.current_thread() is not threading.main_thread():
            return self._dispatch_to_ui_thread(self._update_player_view)

        canvas = getattr(self, "_player_view_canvas", None)
        window = getattr(self, "_player_view_window", None)
        if not canvas or not window or not window.winfo_exists():
            return

        canvas.update_idletasks()
        cw = max(canvas.winfo_width(), 1)
        ch = max(canvas.winfo_height(), 1)

        viewport_size = (
            max(1, int(cw / max(0.05, self.view_zoom))),
            max(1, int(ch / max(0.05, self.view_zoom))),
        )

        origin = self._current_view_origin()

        img = self._render_whiteboard_image(
            include_text=False, for_player=True, viewport_size=viewport_size
        )
        if img is None:
            return

        x_offset = 0
        y_offset = 0

        photo = ImageTk.PhotoImage(img)
        self._player_view_photo = photo
        if self._player_view_image_id:
            canvas.itemconfig(self._player_view_image_id, image=photo)
            canvas.coords(self._player_view_image_id, x_offset, y_offset)
        else:
            self._player_view_image_id = canvas.create_image(
                x_offset, y_offset, image=photo, anchor="nw"
            )

        # Render text using canvas primitives to mirror map second-screen behavior
        canvas.delete("player_text")
        for item in self._iter_visible_items(for_player=True):
            if item.get("type") != "text":
                continue
            pos = item.get("position") or (0, 0)
            size = int(item.get("text_size", item.get("size", self.text_size)))
            scaled_size = max(1, int(size * self.view_zoom))
            color = item.get("color", self.ink_color)
            font = self._font_cache.tk_font(scaled_size)
            screen_x = (pos[0] - origin[0]) * self.view_zoom
            screen_y = (pos[1] - origin[1]) * self.view_zoom
            canvas.create_text(
                x_offset + screen_x,
                y_offset + screen_y,
                text=item.get("text", ""),
                fill=color,
                font=font,
                anchor="nw",
                tags=("player_text",),
            )

    def close(self):
        self.close_player_view()
        close_whiteboard_display(self)
