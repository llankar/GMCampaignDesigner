"""Dialog helpers for configuring portrait generation."""

from __future__ import annotations

import customtkinter as ctk

from modules.helpers.config_helper import ConfigHelper


PORTRAIT_GENERATION_SECTION = "PortraitGeneration"
PORTRAIT_IMAGE_COUNT_KEY = "image_count"
PORTRAIT_CFG_SCALE_KEY = "cfgscale"
DEFAULT_PORTRAIT_IMAGE_COUNT = 6
MIN_PORTRAIT_IMAGE_COUNT = 1
MAX_PORTRAIT_IMAGE_COUNT = 10
DEFAULT_PORTRAIT_CFG_SCALE = 9.0
MIN_PORTRAIT_CFG_SCALE = 1.0
MAX_PORTRAIT_CFG_SCALE = 20.0
CFG_SCALE_STEP = 0.5


def clamp_portrait_image_count(value) -> int:
    """Return a safe portrait generation image count in the supported range."""
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = DEFAULT_PORTRAIT_IMAGE_COUNT
    return max(MIN_PORTRAIT_IMAGE_COUNT, min(MAX_PORTRAIT_IMAGE_COUNT, count))


def clamp_portrait_cfg_scale(value) -> float:
    """Return a safe CFG scale in the supported SwarmUI range."""
    try:
        scale = float(value)
    except (TypeError, ValueError):
        scale = DEFAULT_PORTRAIT_CFG_SCALE
    scale = max(MIN_PORTRAIT_CFG_SCALE, min(MAX_PORTRAIT_CFG_SCALE, scale))
    return round(scale * 2) / 2


def format_cfg_scale(value) -> str:
    """Format CFG scale without unnecessary trailing decimals."""
    scale = clamp_portrait_cfg_scale(value)
    return str(int(scale)) if scale.is_integer() else f"{scale:.1f}"


def get_default_portrait_image_count() -> int:
    """Read the configured portrait generation image count."""
    raw_value = ConfigHelper.get(
        PORTRAIT_GENERATION_SECTION,
        PORTRAIT_IMAGE_COUNT_KEY,
        fallback=str(DEFAULT_PORTRAIT_IMAGE_COUNT),
    )
    return clamp_portrait_image_count(raw_value)


def save_default_portrait_image_count(count: int) -> None:
    """Persist the portrait generation image count for future generations."""
    ConfigHelper.set(
        PORTRAIT_GENERATION_SECTION,
        PORTRAIT_IMAGE_COUNT_KEY,
        clamp_portrait_image_count(count),
    )


def get_default_portrait_cfg_scale() -> float:
    """Read the configured portrait generation CFG scale."""
    raw_value = ConfigHelper.get(
        PORTRAIT_GENERATION_SECTION,
        PORTRAIT_CFG_SCALE_KEY,
        fallback=str(DEFAULT_PORTRAIT_CFG_SCALE),
    )
    return clamp_portrait_cfg_scale(raw_value)


def save_default_portrait_cfg_scale(scale: float) -> None:
    """Persist the portrait generation CFG scale for future generations."""
    ConfigHelper.set(
        PORTRAIT_GENERATION_SECTION,
        PORTRAIT_CFG_SCALE_KEY,
        format_cfg_scale(scale),
    )


class PortraitGenerationDialog(ctk.CTkToplevel):
    """Modal dialog that collects SwarmUI model and candidate count."""

    def __init__(self, master, *, model_options: list[str], selected_model: str):
        super().__init__(master)
        self.result: dict[str, object] | None = None
        self._model_options = model_options
        self._count_var = ctk.IntVar(value=get_default_portrait_image_count())
        self._selected_model = ctk.StringVar(value=selected_model)
        self._cfg_scale_var = ctk.DoubleVar(value=get_default_portrait_cfg_scale())
        self._count_label_var = ctk.StringVar()
        self._cfg_label_var = ctk.StringVar()

        self.title("Portrait Generation")
        self.geometry("520x680")
        self.minsize(500, 650)
        self.transient(master)
        self.grab_set()
        self._build_ui()
        self._update_count_label(self._count_var.get())
        self._update_cfg_label(self._cfg_scale_var.get())

    def _build_ui(self) -> None:
        shell = ctk.CTkFrame(self, corner_radius=18)
        shell.pack(fill="both", expand=True, padx=18, pady=18)
        shell.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            shell,
            text="Create AI Portraits",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 4))
        ctk.CTkLabel(
            shell,
            text="Choose the model, candidate count, and CFG guidance strength SwarmUI should use.",
            wraplength=400,
            justify="left",
            text_color=("#5f6368", "#b8beca"),
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 18))

        model_card = ctk.CTkFrame(shell, corner_radius=14, fg_color=("#edf2ff", "#1e293b"))
        model_card.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 14))
        model_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(model_card, text="AI model", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 6)
        )
        ctk.CTkOptionMenu(
            model_card,
            values=self._model_options,
            variable=self._selected_model,
            height=36,
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))

        count_card = ctk.CTkFrame(shell, corner_radius=14, fg_color=("#f8fafc", "#111827"))
        count_card.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 14))
        count_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(count_card, textvariable=self._count_label_var, font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 2)
        )
        ctk.CTkLabel(
            count_card,
            text="More candidates gives better choice, but takes longer to generate.",
            wraplength=380,
            justify="left",
            text_color=("#667085", "#9ca3af"),
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
        ctk.CTkSlider(
            count_card,
            from_=MIN_PORTRAIT_IMAGE_COUNT,
            to=MAX_PORTRAIT_IMAGE_COUNT,
            number_of_steps=MAX_PORTRAIT_IMAGE_COUNT - MIN_PORTRAIT_IMAGE_COUNT,
            variable=self._count_var,
            command=self._update_count_label,
        ).grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 8))
        quick_row = ctk.CTkFrame(count_card, fg_color="transparent")
        quick_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))
        for count in (1, 3, 6, 10):
            ctk.CTkButton(
                quick_row,
                text=str(count),
                width=48,
                command=lambda value=count: self._set_count(value),
            ).pack(side="left", padx=(0, 8))

        cfg_card = ctk.CTkFrame(shell, corner_radius=14, fg_color=("#fff7ed", "#24140a"))
        cfg_card.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 14))
        cfg_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cfg_card, textvariable=self._cfg_label_var, font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 2)
        )
        ctk.CTkLabel(
            cfg_card,
            text="Lower CFG is looser and more creative; higher CFG follows the prompt harder.",
            wraplength=420,
            justify="left",
            text_color=("#9a3412", "#fdba74"),
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
        ctk.CTkSlider(
            cfg_card,
            from_=MIN_PORTRAIT_CFG_SCALE,
            to=MAX_PORTRAIT_CFG_SCALE,
            number_of_steps=int((MAX_PORTRAIT_CFG_SCALE - MIN_PORTRAIT_CFG_SCALE) / CFG_SCALE_STEP),
            variable=self._cfg_scale_var,
            command=self._update_cfg_label,
        ).grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 8))
        preset_row = ctk.CTkFrame(cfg_card, fg_color="transparent")
        preset_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))
        for label, scale in (("Dreamy", 5.0), ("Balanced", 9.0), ("Sharp", 12.0), ("Strict", 15.0)):
            ctk.CTkButton(
                preset_row,
                text=f"{label} {format_cfg_scale(scale)}",
                width=92,
                command=lambda value=scale: self._set_cfg_scale(value),
            ).pack(side="left", padx=(0, 8))

        actions = ctk.CTkFrame(shell, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="ew", padx=20, pady=(4, 18))
        ctk.CTkButton(actions, text="Cancel", fg_color="transparent", border_width=1, command=self._cancel).pack(side="right", padx=(8, 0))
        ctk.CTkButton(actions, text="Generate Portraits", command=self._confirm).pack(side="right")

    def _set_count(self, value: int) -> None:
        self._count_var.set(clamp_portrait_image_count(value))
        self._update_count_label(self._count_var.get())

    def _update_count_label(self, raw_value) -> None:
        count = clamp_portrait_image_count(round(float(raw_value)))
        self._count_var.set(count)
        suffix = "candidate" if count == 1 else "candidates"
        self._count_label_var.set(f"Generate {count} portrait {suffix}")

    def _set_cfg_scale(self, value: float) -> None:
        self._cfg_scale_var.set(clamp_portrait_cfg_scale(value))
        self._update_cfg_label(self._cfg_scale_var.get())

    def _update_cfg_label(self, raw_value) -> None:
        scale = clamp_portrait_cfg_scale(raw_value)
        self._cfg_scale_var.set(scale)
        self._cfg_label_var.set(f"CFG guidance scale: {format_cfg_scale(scale)}")

    def _confirm(self) -> None:
        count = clamp_portrait_image_count(self._count_var.get())
        cfg_scale = clamp_portrait_cfg_scale(self._cfg_scale_var.get())
        save_default_portrait_image_count(count)
        save_default_portrait_cfg_scale(cfg_scale)
        ConfigHelper.set("LastUsed", "model", self._selected_model.get())
        self.result = {"model": self._selected_model.get(), "image_count": count, "cfgscale": cfg_scale}
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
