"""Interactive image editor dialog for image-library assets."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageEnhance, ImageOps, ImageTk

from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.core.render.stroke_renderer import StrokeRenderer
from modules.ui.image_library.editor.core.tools.brush_tool import BrushTool
from modules.ui.image_library.editor.core.tools.eraser_tool import EraserTool
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
from modules.ui.image_library.editor.widgets.layers_panel import LayersPanel


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

        self._base_image: Image.Image | None = None
        self._document: ImageDocument | None = None
        self._history = HistoryStack(max_depth=100)

        self._canvas_photo: ImageTk.PhotoImage | None = None
        self._display_scale = 1.0
        self._display_offset = (0, 0)
        self._display_size = (0, 0)

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

        self._build_header()
        self._build_workspace()
        self._build_controls()

        self._load_image()

        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Control-z>", lambda _event: self._undo())
        self.bind("<Control-y>", lambda _event: self._redo())
        self.bind("<Control-Shift-Z>", lambda _event: self._redo())
        self.bind("<Control-Shift-z>", lambda _event: self._redo())
        self.lift()
        self.focus_force()

    def _build_header(self) -> None:
        bar = ctk.CTkFrame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        bar.grid_columnconfigure(0, weight=1)

        self._path_label = ctk.CTkLabel(bar, text=self._source_path, anchor="w")
        self._path_label.grid(row=0, column=0, sticky="ew", padx=10, pady=8)

    def _build_workspace(self) -> None:
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

    def _build_controls(self) -> None:
        controls = ctk.CTkFrame(self)
        controls.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 12))

        ctk.CTkButton(controls, text="Rotate Left", command=lambda: self._rotate(-90)).grid(
            row=0, column=0, padx=6, pady=(10, 6)
        )
        ctk.CTkButton(controls, text="Rotate Right", command=lambda: self._rotate(90)).grid(
            row=0, column=1, padx=6, pady=(10, 6)
        )
        ctk.CTkButton(controls, text="Mirror", command=self._mirror).grid(row=0, column=2, padx=6, pady=(10, 6))
        ctk.CTkButton(controls, text="Flip", command=self._flip).grid(row=0, column=3, padx=6, pady=(10, 6))
        ctk.CTkButton(controls, text="Reset", command=self._reset).grid(row=0, column=4, padx=6, pady=(10, 6))

        self._undo_button = ctk.CTkButton(controls, text="Undo", command=self._undo)
        self._undo_button.grid(row=0, column=5, padx=6, pady=(10, 6))
        self._redo_button = ctk.CTkButton(controls, text="Redo", command=self._redo)
        self._redo_button.grid(row=0, column=6, padx=6, pady=(10, 6))

        ctk.CTkLabel(controls, text="Tool").grid(row=1, column=0, padx=(10, 6), pady=4, sticky="e")
        tool_selector = ctk.CTkSegmentedButton(
            controls,
            values=["Paint", "Eraser"],
            variable=self._active_tool_var,
            command=lambda _value: self._refresh_preview(),
            width=220,
        )
        tool_selector.grid(row=1, column=1, columnspan=2, padx=4, pady=4, sticky="w")

        ctk.CTkLabel(controls, text="Brush Size").grid(row=1, column=3, padx=(10, 6), pady=4, sticky="e")
        ctk.CTkSlider(
            controls,
            from_=1,
            to=128,
            number_of_steps=127,
            variable=self._brush_size_var,
            command=lambda _value: None,
            width=220,
        ).grid(row=1, column=4, columnspan=2, padx=2, pady=4, sticky="w")

        ctk.CTkLabel(controls, text="Brush Opacity").grid(row=2, column=0, padx=(10, 6), pady=4, sticky="e")
        ctk.CTkSlider(
            controls,
            from_=0.05,
            to=1.0,
            number_of_steps=19,
            variable=self._brush_opacity_var,
            command=lambda _value: None,
            width=220,
        ).grid(row=2, column=1, columnspan=2, padx=2, pady=4, sticky="w")

        ctk.CTkLabel(controls, text="Brightness").grid(row=2, column=3, padx=(10, 6), pady=4, sticky="e")
        ctk.CTkSlider(
            controls,
            from_=0.2,
            to=2.0,
            number_of_steps=36,
            variable=self._brightness_var,
            command=self._on_brightness_change,
            width=220,
        ).grid(row=2, column=4, columnspan=2, padx=2, pady=4, sticky="w")

        ctk.CTkLabel(controls, text="Contrast").grid(row=3, column=3, padx=(10, 6), pady=4, sticky="e")
        ctk.CTkSlider(
            controls,
            from_=0.2,
            to=2.0,
            number_of_steps=36,
            variable=self._contrast_var,
            command=self._on_contrast_change,
            width=220,
        ).grid(row=3, column=4, columnspan=2, padx=2, pady=4, sticky="w")

        ctk.CTkButton(controls, text="Save", command=self._save).grid(row=4, column=4, padx=6, pady=(10, 10), sticky="e")
        ctk.CTkButton(controls, text="Save As", command=self._save_as).grid(
            row=4,
            column=5,
            padx=(0, 10),
            pady=(10, 10),
            sticky="w",
        )

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
        if self._document is None:
            return None
        image = self._document.composite()
        brightness = float(self._brightness_var.get() or 1.0)
        contrast = float(self._contrast_var.get() or 1.0)
        image = ImageEnhance.Brightness(image).enhance(brightness)
        image = ImageEnhance.Contrast(image).enhance(contrast)
        return image

    def _refresh_preview(self) -> None:
        image = self.composite_preview()
        if image is None:
            return

        canvas_w = max(320, self._preview_canvas.winfo_width())
        canvas_h = max(260, self._preview_canvas.winfo_height())
        scale = min(canvas_w / image.width, canvas_h / image.height)
        render_w = max(1, int(image.width * scale))
        render_h = max(1, int(image.height * scale))

        rendered = image.resize((render_w, render_h), Image.Resampling.LANCZOS)

        self._display_scale = scale
        self._display_size = (render_w, render_h)
        self._display_offset = ((canvas_w - render_w) // 2, (canvas_h - render_h) // 2)

        self._canvas_photo = ImageTk.PhotoImage(rendered)
        self._preview_canvas.delete("all")
        self._preview_canvas.create_image(self._display_offset[0], self._display_offset[1], image=self._canvas_photo, anchor="nw")

    def _canvas_to_document(self, x: int, y: int) -> tuple[float, float] | None:
        if self._document is None:
            return None
        dx = (x - self._display_offset[0]) / max(0.001, self._display_scale)
        dy = (y - self._display_offset[1]) / max(0.001, self._display_scale)
        if dx < 0 or dy < 0 or dx >= self._document.width or dy >= self._document.height:
            return None
        return dx, dy

    def _get_active_tool(self):
        if self._active_tool_var.get() == "Eraser":
            return self._eraser_tool
        return self._brush_tool

    def execute_command(self, command) -> None:
        self._history.execute_command(command)
        self._layers_panel.refresh()
        self._refresh_preview()
        self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        if hasattr(self, "_undo_button"):
            self._undo_button.configure(state="normal" if self._history.can_undo else "disabled")
        if hasattr(self, "_redo_button"):
            self._redo_button.configure(state="normal" if self._history.can_redo else "disabled")

    def _undo(self) -> str:
        if self._history.undo():
            self._layers_panel.refresh()
            self._refresh_preview()
            self._update_history_buttons()
        return "break"

    def _redo(self) -> str:
        if self._history.redo():
            self._layers_panel.refresh()
            self._refresh_preview()
            self._update_history_buttons()
        return "break"

    def _on_canvas_press(self, event: tk.Event) -> None:
        point = self._canvas_to_document(int(event.x), int(event.y))
        tool = self._get_active_tool()
        if point is None or tool is None or self._document is None:
            return
        self._stroke_layer_index = self._document.active_layer_index
        self._stroke_before = self._document.active_layer.copy()
        tool.on_press(*point)
        self._refresh_preview()

    def _on_canvas_drag(self, event: tk.Event) -> None:
        point = self._canvas_to_document(int(event.x), int(event.y))
        tool = self._get_active_tool()
        if point is None or tool is None:
            return
        tool.on_drag(*point)
        self._refresh_preview()

    def _on_canvas_release(self, event: tk.Event) -> None:
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

        if self._active_tool_var.get() == "Eraser":
            command = EraseCommand(self._document, layer_index, before, after)
        else:
            command = StrokeCommand(self._document, layer_index, before, after)
        self.execute_command(command)

        self._stroke_before = None
        self._stroke_layer_index = None

    def _on_layers_changed(self) -> None:
        self._refresh_preview()
        self._update_history_buttons()

    def _rotate(self, degrees: int) -> None:
        if self._document is None:
            return
        self.execute_command(RotateCommand(self._document, degrees))

    def _mirror(self) -> None:
        if self._document is None:
            return
        self.execute_command(FlipCommand(self._document, horizontal=True))

    def _flip(self) -> None:
        if self._document is None:
            return
        self.execute_command(FlipCommand(self._document, horizontal=False))

    def _on_brightness_change(self, value: float) -> None:
        current = float(value)
        if abs(current - self._last_brightness) < 1e-6:
            return
        self.execute_command(BrightnessCommand(self._last_brightness, current, setter=self._set_brightness))

    def _on_contrast_change(self, value: float) -> None:
        current = float(value)
        if abs(current - self._last_contrast) < 1e-6:
            return
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
        self._set_brightness(1.0)
        self._set_contrast(1.0)
        self._layers_panel.refresh()
        self._refresh_preview()
        self._update_history_buttons()

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
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.gif")],
        )
        if target:
            self._save_to_path(target)

    def _save_to_path(self, target_path: str) -> None:
        image = self.composite_preview()
        if image is None:
            return

        try:
            destination = Path(target_path).expanduser()
            destination.parent.mkdir(parents=True, exist_ok=True)
            extension = destination.suffix.lower()
            to_save = image
            # Export to common image formats is flattened by design.
            if extension in {".jpg", ".jpeg"}:
                to_save = image.convert("RGB")
            to_save.save(destination)
        except Exception as exc:
            messagebox.showerror("Image Editor", f"Unable to save image:\n{exc}")
            return

        if callable(self._on_saved):
            self._on_saved(str(destination))
        messagebox.showinfo("Image Editor", "Image saved successfully.")


__all__ = ["ImageEditorDialog"]
