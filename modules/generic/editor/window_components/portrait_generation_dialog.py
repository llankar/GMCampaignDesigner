"""Dialog helpers for configuring portrait generation."""

from __future__ import annotations

import customtkinter as ctk

from modules.helpers.config_helper import ConfigHelper


PORTRAIT_GENERATION_SECTION = "PortraitGeneration"
PORTRAIT_IMAGE_COUNT_KEY = "image_count"
DEFAULT_PORTRAIT_IMAGE_COUNT = 6
MIN_PORTRAIT_IMAGE_COUNT = 1
MAX_PORTRAIT_IMAGE_COUNT = 10


def clamp_portrait_image_count(value) -> int:
    """Return a safe portrait generation image count in the supported range."""
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = DEFAULT_PORTRAIT_IMAGE_COUNT
    return max(MIN_PORTRAIT_IMAGE_COUNT, min(MAX_PORTRAIT_IMAGE_COUNT, count))


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


class PortraitGenerationDialog(ctk.CTkToplevel):
    """Modal dialog that collects SwarmUI model and candidate count."""

    def __init__(self, master, *, model_options: list[str], selected_model: str):
        super().__init__(master)
        self.result: dict[str, object] | None = None
        self._model_options = model_options
        self._count_var = ctk.IntVar(value=get_default_portrait_image_count())
        self._selected_model = ctk.StringVar(value=selected_model)
        self._count_label_var = ctk.StringVar()

        self.title("Portrait Generation")
        self.geometry("480x430")
        self.minsize(460, 400)
        self.transient(master)
        self.grab_set()
        self._build_ui()
        self._update_count_label(self._count_var.get())

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
            text="Choose the model and how many portrait candidates SwarmUI should generate.",
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

        actions = ctk.CTkFrame(shell, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=20, pady=(4, 18))
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

    def _confirm(self) -> None:
        count = clamp_portrait_image_count(self._count_var.get())
        save_default_portrait_image_count(count)
        ConfigHelper.set("LastUsed", "model", self._selected_model.get())
        self.result = {"model": self._selected_model.get(), "image_count": count}
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
