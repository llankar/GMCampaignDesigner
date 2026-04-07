"""Interactive image editor dialog for image-library assets."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageEnhance, ImageOps, ImageTk

from modules.ui.image_library.editor.core.compositor import flatten_layers
from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.core.render.stroke_renderer import StrokeRenderer
from modules.ui.image_library.editor.history.commands import (
    AddLayerCommand,
    BrightnessCommand,
    ContrastCommand,
    DeleteLayerCommand,
    EraseCommand,
    FlipCommand,
    MoveLayerCommand,
    RotateCommand,
    StrokeCommand,
    ToggleLayerVisibilityCommand,
)
from modules.ui.image_library.editor.history.history_stack import HistoryStack
from modules.ui.image_library.editor.io import SUPPORTED_FILETYPES, SaveService
from modules.ui.image_library.editor.tools import BrushTool, EraserTool
from modules.ui.image_library.editor.widgets import EditorToolbar, LayersPanel, StatusBar, ToolOptionsBar


class ImageEditorDialog(ctk.CTkToplevel):
    """Small non-destructive editor with rotate/flip and basic paint/erase tools."""

    def __init__(self, master: tk.Misc | None, image_path: str, on_saved=None) -> None:
        super().__init__(master)
        self.title("Image Editor")
        self.geometry("1120x760")
        self.minsize(860, 620)
        self.transient(master)

        self._source_path = str(image_path or "").strip()
        self._on_saved = on_saved
        self._save_service = SaveService()

        self._base_image: Image.Image | None = None
        self._document: ImageDocument | None = None
        self._history = HistoryStack(max_depth=100)

        self._canvas_photo: ImageTk.PhotoImage | None = None
        self._canvas_image_item: int | None = None
        self._display_scale = 1.0
        self._display_offset = (0, 0)
        self._flattened_cache: Image.Image | None = None
        self._flattened_cache_valid = False
        self._drag_in_progress = False
        self._drag_needs_render = False
        self._drag_render_after_id: str | None = None
        self._drag_flattened_without_active: Image.Image | None = None

        self._brightness_var = tk.DoubleVar(value=1.0)
        self._contrast_var = tk.DoubleVar(value=1.0)
        self._last_brightness = 1.0
        self._last_contrast = 1.0
        self._brush_size_var = tk.DoubleVar(value=18.0)
        self._brush_opacity_var = tk.DoubleVar(value=1.0)
        self._active_tool_var = tk.StringVar(value="Paint")
        self._stroke_before: Image.Image | None = None
        self._stroke_layer_index: int | None = None

        self._renderer = StrokeRenderer()
        self._brush_tool: BrushTool | None = None
        self._eraser_tool: EraserTool | None = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_layout()
        self._load_image()

        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Control-z>", lambda _event: self._undo())
        self.bind("<Control-y>", lambda _event: self._redo())
        self.bind("<Control-Shift-Z>", lambda _event: self._redo())
        self.bind("<Control-Shift-z>", lambda _event: self._redo())
        self.lift()
        self.focus_force()

    def _build_layout(self) -> None:
        self._toolbar = EditorToolbar(self, source_path=self._source_path)
        self._toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))

        workspace = ctk.CTkFrame(self)
        workspace.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=1)

        preview_container = ctk.CTkFrame(workspace)
        preview_container.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        preview_container.grid_rowconfigure(0, weight=1)
        preview_container.grid_columnconfigure(0, weight=1)

        self._preview_canvas = tk.Canvas(preview_container, background="#1f1f1f", highlightthickness=0)
        self._preview_canvas.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self._preview_canvas.bind("<Configure>", lambda _event: self._refresh_preview(), add="+")
        self._preview_canvas.bind("<ButtonPress-1>", self._on_canvas_press, add="+")
        self._preview_canvas.bind("<B1-Motion>", self._on_canvas_drag, add="+")
        self._preview_canvas.bind("<ButtonRelease-1>", self._on_canvas_release, add="+")

        self._layers_panel = LayersPanel(
            workspace,
            on_changed=self._on_layers_changed,
            on_add=self._add_layer,
            on_delete=self._delete_layer,
            on_move=self._move_layer,
            on_toggle_visibility=self._toggle_layer_visibility,
        )
        self._layers_panel.grid(row=0, column=1, sticky="ns", padx=(6, 10), pady=10)

        self._tool_options = ToolOptionsBar(
            self,
            active_tool_var=self._active_tool_var,
            brush_size_var=self._brush_size_var,
            brush_opacity_var=self._brush_opacity_var,
            brightness_var=self._brightness_var,
            contrast_var=self._contrast_var,
            on_rotate_left=lambda: self._rotate(-90),
            on_rotate_right=lambda: self._rotate(90),
            on_mirror=self._mirror,
            on_flip=self._flip,
            on_reset=self._reset,
            on_undo=self._undo,
            on_redo=self._redo,
            on_brightness_change=self._on_brightness_change,
            on_contrast_change=self._on_contrast_change,
            on_save=self._save,
            on_save_as=self._save_as,
            on_tool_changed=lambda _value: self._refresh_preview(),
        )
        self._tool_options.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 4))

        self._status_bar = StatusBar(self)
        self._status_bar.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        self._update_history_buttons()

    def _load_image(self) -> None:
        if not self._source_path:
            messagebox.showerror("Image Editor", "Missing image path.")
            self.destroy()
            return
        try:
            with Image.open(self._source_path) as img:
                self._base_image = ImageOps.exif_transpose(img).convert("RGBA")
        except Exception as exc:
            messagebox.showerror("Image Editor", f"Unable to open image:\n{exc}")
            self.destroy()
            return

        self._document = ImageDocument.from_image(self._base_image)
        self._layers_panel.bind_document(self._document)
        self._brush_tool = BrushTool(
            self._document,
            self._renderer,
            size_getter=self._brush_size_var.get,
            opacity_getter=self._brush_opacity_var.get,
            hardness_getter=lambda: 0.8,
        )
        self._eraser_tool = EraserTool(
            self._document,
            self._renderer,
            size_getter=self._brush_size_var.get,
            opacity_getter=self._brush_opacity_var.get,
            hardness_getter=lambda: 0.8,
        )
        self._refresh_preview()

    def composite_preview(self) -> Image.Image | None:
        flattened = self._get_flattened_image()
        if flattened is None:
            return None
        return self._apply_preview_adjustments(flattened)

    def _apply_preview_adjustments(self, image: Image.Image) -> Image.Image:
        adjusted = ImageEnhance.Brightness(image).enhance(float(self._brightness_var.get() or 1.0))
        adjusted = ImageEnhance.Contrast(adjusted).enhance(float(self._contrast_var.get() or 1.0))
        return adjusted

    def _get_flattened_image(self) -> Image.Image | None:
        if self._document is None:
            return None
        if self._flattened_cache_valid and self._flattened_cache is not None:
            return self._flattened_cache
        self._flattened_cache = self._document.composite()
        self._flattened_cache_valid = True
        return self._flattened_cache

    def _invalidate_preview_caches(self) -> None:
        self._flattened_cache_valid = False
        self._flattened_cache = None
        self._drag_flattened_without_active = None

    def _refresh_preview(self) -> None:
        image = self.composite_preview()
        if image is None:
            return
        self._render_preview_image(image, resample=Image.Resampling.LANCZOS)

    def _refresh_preview_fast(self) -> None:
        image = self._build_drag_preview_image()
        if image is None:
            return
        self._render_preview_image(image, resample=Image.Resampling.BILINEAR)

    def _build_drag_preview_image(self) -> Image.Image | None:
        if self._document is None:
            return None
        active_layer_index = self._document.active_layer_index
        if self._drag_flattened_without_active is None:
            self._drag_flattened_without_active = flatten_layers(
                self._document.width,
                self._document.height,
                [layer for idx, layer in enumerate(self._document.layers) if idx != active_layer_index],
            )

        flattened = self._drag_flattened_without_active.copy()
        active_layer = self._document.layers[active_layer_index]
        if active_layer.visible:
            active_image = active_layer.image.convert("RGBA")
            opacity = max(0.0, min(1.0, float(active_layer.opacity)))
            if opacity < 1.0:
                channels = list(active_image.split())
                channels[3] = channels[3].point(lambda alpha: int(alpha * opacity))
                active_image = Image.merge("RGBA", channels)
            flattened.alpha_composite(active_image)
        return self._apply_preview_adjustments(flattened)

    def _render_preview_image(self, image: Image.Image, resample: int) -> None:
        if image is None:
            return

        canvas_w = max(320, self._preview_canvas.winfo_width())
        canvas_h = max(260, self._preview_canvas.winfo_height())
        scale = min(canvas_w / image.width, canvas_h / image.height)
        render_w = max(1, int(image.width * scale))
        render_h = max(1, int(image.height * scale))

        self._display_scale = scale
        self._display_offset = ((canvas_w - render_w) // 2, (canvas_h - render_h) // 2)

        self._canvas_photo = ImageTk.PhotoImage(image.resize((render_w, render_h), resample))
        if self._canvas_image_item is None:
            self._canvas_image_item = self._preview_canvas.create_image(
                self._display_offset[0],
                self._display_offset[1],
                image=self._canvas_photo,
                anchor="nw",
            )
        else:
            self._preview_canvas.coords(self._canvas_image_item, self._display_offset[0], self._display_offset[1])
            self._preview_canvas.itemconfigure(self._canvas_image_item, image=self._canvas_photo)

    def _canvas_to_document(self, x: int, y: int) -> tuple[float, float] | None:
        if self._document is None:
            return None
        dx = (x - self._display_offset[0]) / max(0.001, self._display_scale)
        dy = (y - self._display_offset[1]) / max(0.001, self._display_scale)
        if dx < 0 or dy < 0 or dx >= self._document.width or dy >= self._document.height:
            return None
        return dx, dy

    def _get_active_tool(self):
        return self._eraser_tool if self._active_tool_var.get() == "Eraser" else self._brush_tool

    def execute_command(self, command) -> None:
        self._history.execute_command(command)
        self._invalidate_preview_caches()
        self._layers_panel.refresh()
        self._refresh_preview()
        self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        self._tool_options.undo_button.configure(state="normal" if self._history.can_undo else "disabled")
        self._tool_options.redo_button.configure(state="normal" if self._history.can_redo else "disabled")

    def _undo(self) -> str:
        if self._history.undo():
            self._invalidate_preview_caches()
            self._layers_panel.refresh()
            self._refresh_preview()
            self._update_history_buttons()
            self._status_bar.set_message("Undid last action")
        return "break"

    def _redo(self) -> str:
        if self._history.redo():
            self._invalidate_preview_caches()
            self._layers_panel.refresh()
            self._refresh_preview()
            self._update_history_buttons()
            self._status_bar.set_message("Redid action")
        return "break"

    def _on_canvas_press(self, event: tk.Event) -> None:
        point = self._canvas_to_document(int(event.x), int(event.y))
        tool = self._get_active_tool()
        if point is None or tool is None or self._document is None:
            return
        self._stroke_layer_index = self._document.active_layer_index
        self._stroke_before = self._document.active_layer.copy()
        self._drag_in_progress = True
        self._drag_needs_render = False
        self._drag_flattened_without_active = None
        tool.on_press(*point)
        self._refresh_preview_fast()

    def _on_canvas_drag(self, event: tk.Event) -> None:
        point = self._canvas_to_document(int(event.x), int(event.y))
        tool = self._get_active_tool()
        if point is None or tool is None:
            return
        tool.on_drag(*point)
        self._schedule_drag_refresh()

    def _schedule_drag_refresh(self) -> None:
        self._drag_needs_render = True
        if self._drag_render_after_id is not None:
            return
        self._drag_render_after_id = self.after(16, self._flush_drag_refresh)

    def _flush_drag_refresh(self) -> None:
        self._drag_render_after_id = None
        if not self._drag_in_progress or not self._drag_needs_render:
            return
        self._drag_needs_render = False
        self._refresh_preview_fast()

    def _on_canvas_release(self, event: tk.Event) -> None:
        self._drag_in_progress = False
        self._drag_needs_render = False
        if self._drag_render_after_id is not None:
            self.after_cancel(self._drag_render_after_id)
            self._drag_render_after_id = None
        point = self._canvas_to_document(int(event.x), int(event.y))
        tool = self._get_active_tool()
        if point is None or tool is None or self._document is None or self._stroke_before is None:
            return
        layer_index = self._stroke_layer_index
        if layer_index is None or layer_index >= len(self._document.layers):
            return

        tool.on_release(*point)
        after = self._document.layers[layer_index].image.copy()
        before = self._stroke_before.copy()
        self._document.layers[layer_index].image = before.copy()

        command = EraseCommand(self._document, layer_index, before, after) if self._active_tool_var.get() == "Eraser" else StrokeCommand(self._document, layer_index, before, after)
        self.execute_command(command)

        self._stroke_before = None
        self._stroke_layer_index = None
        self._drag_flattened_without_active = None

    def _on_layers_changed(self) -> None:
        self._invalidate_preview_caches()
        self._refresh_preview()
        self._update_history_buttons()

    def _rotate(self, degrees: int) -> None:
        if self._document is not None:
            self.execute_command(RotateCommand(self._document, degrees))

    def _mirror(self) -> None:
        if self._document is not None:
            self.execute_command(FlipCommand(self._document, horizontal=True))

    def _flip(self) -> None:
        if self._document is not None:
            self.execute_command(FlipCommand(self._document, horizontal=False))

    def _on_brightness_change(self, value: float) -> None:
        current = float(value)
        if abs(current - self._last_brightness) >= 1e-6:
            self.execute_command(BrightnessCommand(self._last_brightness, current, setter=self._set_brightness))

    def _on_contrast_change(self, value: float) -> None:
        current = float(value)
        if abs(current - self._last_contrast) >= 1e-6:
            self.execute_command(ContrastCommand(self._last_contrast, current, setter=self._set_contrast))

    def _set_brightness(self, value: float) -> None:
        self._brightness_var.set(float(value))
        self._last_brightness = float(value)

    def _set_contrast(self, value: float) -> None:
        self._contrast_var.set(float(value))
        self._last_contrast = float(value)

    def _add_layer(self) -> bool:
        if self._document is None:
            return False
        self.execute_command(AddLayerCommand(self._document))
        return True

    def _delete_layer(self) -> bool:
        if self._document is None or len(self._document.layers) <= 1:
            return False
        self.execute_command(DeleteLayerCommand(self._document))
        return True

    def _move_layer(self, direction: int) -> bool:
        if self._document is None:
            return False
        target = self._document.active_layer_index + direction
        if target < 0 or target >= len(self._document.layers):
            return False
        self.execute_command(MoveLayerCommand(self._document, direction))
        return True

    def _toggle_layer_visibility(self) -> bool:
        if self._document is None:
            return False
        self.execute_command(ToggleLayerVisibilityCommand(self._document))
        return True

    def _reset(self) -> None:
        if self._base_image is None or self._document is None:
            return
        self._document.reset_from(self._base_image)
        self._history.clear()
        self._invalidate_preview_caches()
        self._set_brightness(1.0)
        self._set_contrast(1.0)
        self._layers_panel.refresh()
        self._refresh_preview()
        self._update_history_buttons()
        self._status_bar.set_message("Reset editor state")

    def _save(self) -> None:
        self._save_to_path(self._source_path)

    def _save_as(self) -> None:
        base = Path(self._source_path)
        target = filedialog.asksaveasfilename(
            parent=self,
            title="Save edited image as",
            initialdir=str(base.parent),
            initialfile=f"{base.stem}_edited{base.suffix}",
            defaultextension=base.suffix or ".png",
            filetypes=SUPPORTED_FILETYPES,
        )
        if target:
            self._save_to_path(target)

    def _save_to_path(self, target_path: str) -> None:
        image = self.composite_preview()
        if image is None:
            return

        try:
            destination = self._save_service.save_image(image, target_path)
        except Exception as exc:
            messagebox.showerror("Image Editor", f"Unable to save image:\n{exc}")
            return

        if callable(self._on_saved):
            self._on_saved(str(destination))
        self._status_bar.set_message(f"Saved: {destination.name}")
        messagebox.showinfo("Image Editor", "Image saved successfully.")


__all__ = ["ImageEditorDialog"]
