"""Interactive image editor dialog for image-library assets."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageEnhance, ImageOps


class ImageEditorDialog(ctk.CTkToplevel):
    """Small non-destructive editor with rotate/flip and tonal adjustments."""

    def __init__(self, master: tk.Misc | None, image_path: str, on_saved=None) -> None:
        super().__init__(master)
        self.title("Image Editor")
        self.geometry("980x760")
        self.minsize(760, 620)
        self.transient(master)

        self._source_path = str(image_path or "").strip()
        self._on_saved = on_saved

        self._base_image: Image.Image | None = None
        self._working_image: Image.Image | None = None
        self._preview_image: ctk.CTkImage | None = None

        self._brightness_var = tk.DoubleVar(value=1.0)
        self._contrast_var = tk.DoubleVar(value=1.0)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_preview()
        self._build_controls()

        self._load_image()

        self.bind("<Escape>", lambda _event: self.destroy())
        self.lift()
        self.focus_force()

    def _build_header(self) -> None:
        bar = ctk.CTkFrame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        bar.grid_columnconfigure(0, weight=1)

        self._path_label = ctk.CTkLabel(bar, text=self._source_path, anchor="w")
        self._path_label.grid(row=0, column=0, sticky="ew", padx=10, pady=8)

    def _build_preview(self) -> None:
        container = ctk.CTkFrame(self)
        container.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self._preview_label = ctk.CTkLabel(container, text="", anchor="center")
        self._preview_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self._preview_label.bind("<Configure>", lambda _event: self._refresh_preview(), add="+")

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

        ctk.CTkLabel(controls, text="Brightness").grid(row=1, column=0, columnspan=1, padx=(8, 2), pady=4, sticky="e")
        brightness = ctk.CTkSlider(
            controls,
            from_=0.2,
            to=2.0,
            number_of_steps=36,
            variable=self._brightness_var,
            command=lambda _value: self._refresh_preview(),
            width=220,
        )
        brightness.grid(row=1, column=1, columnspan=2, padx=2, pady=4, sticky="w")

        ctk.CTkLabel(controls, text="Contrast").grid(row=1, column=3, columnspan=1, padx=(12, 2), pady=4, sticky="e")
        contrast = ctk.CTkSlider(
            controls,
            from_=0.2,
            to=2.0,
            number_of_steps=36,
            variable=self._contrast_var,
            command=lambda _value: self._refresh_preview(),
            width=220,
        )
        contrast.grid(row=1, column=4, columnspan=2, padx=2, pady=4, sticky="w")

        ctk.CTkButton(controls, text="Save", command=self._save).grid(row=2, column=4, padx=6, pady=(10, 10), sticky="e")
        ctk.CTkButton(controls, text="Save As", command=self._save_as).grid(
            row=2,
            column=5,
            padx=(0, 10),
            pady=(10, 10),
            sticky="w",
        )

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
        self._working_image = self._base_image.copy()
        self._refresh_preview()

    def _compose_preview_image(self) -> Image.Image | None:
        if self._working_image is None:
            return None
        image = self._working_image.copy()
        brightness = float(self._brightness_var.get() or 1.0)
        contrast = float(self._contrast_var.get() or 1.0)
        image = ImageEnhance.Brightness(image).enhance(brightness)
        image = ImageEnhance.Contrast(image).enhance(contrast)
        return image

    def _refresh_preview(self) -> None:
        image = self._compose_preview_image()
        if image is None:
            return

        max_w = max(320, self._preview_label.winfo_width() - 18)
        max_h = max(260, self._preview_label.winfo_height() - 18)
        rendered = image.copy()
        rendered.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

        self._preview_image = ctk.CTkImage(light_image=rendered, dark_image=rendered, size=rendered.size)
        self._preview_label.configure(image=self._preview_image)

    def _rotate(self, degrees: int) -> None:
        if self._working_image is None:
            return
        self._working_image = self._working_image.rotate(-degrees, expand=True)
        self._refresh_preview()

    def _mirror(self) -> None:
        if self._working_image is None:
            return
        self._working_image = ImageOps.mirror(self._working_image)
        self._refresh_preview()

    def _flip(self) -> None:
        if self._working_image is None:
            return
        self._working_image = ImageOps.flip(self._working_image)
        self._refresh_preview()

    def _reset(self) -> None:
        if self._base_image is None:
            return
        self._working_image = self._base_image.copy()
        self._brightness_var.set(1.0)
        self._contrast_var.set(1.0)
        self._refresh_preview()

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
        image = self._compose_preview_image()
        if image is None:
            return

        try:
            destination = Path(target_path).expanduser()
            destination.parent.mkdir(parents=True, exist_ok=True)
            extension = destination.suffix.lower()
            to_save = image
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
