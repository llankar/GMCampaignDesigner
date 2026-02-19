from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from modules.timer.models import TimerPreset
from modules.timer.service import TimerService


class PresetsPanel(ctk.CTkFrame):
    DEFAULT_PRESETS = [
        ("Combat", 360, "countdown", False),
        ("Pause", 900, "countdown", False),
        ("Scène", 1200, "countdown", False),
        ("Session", 14400, "countdown", False),
    ]

    def __init__(self, parent, timer_service: TimerService, on_apply: Callable[[TimerPreset], None]):
        super().__init__(parent)
        self._timer_service = timer_service
        self._on_apply = on_apply
        self._selected_preset_id: Optional[str] = None

        ctk.CTkLabel(self, text="Presets", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=8, pady=(8, 4))

        self._name = ctk.StringVar(value="Combat")
        self._seconds = ctk.StringVar(value="360")
        self._mode = ctk.StringVar(value="countdown")
        self._repeat = ctk.BooleanVar(value=False)

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkEntry(form, textvariable=self._name, placeholder_text="Preset name").pack(fill="x", padx=6, pady=(6, 4))
        ctk.CTkEntry(form, textvariable=self._seconds, placeholder_text="Duration seconds").pack(fill="x", padx=6, pady=4)
        ctk.CTkSegmentedButton(form, values=["countdown", "stopwatch"], variable=self._mode).pack(fill="x", padx=6, pady=4)
        ctk.CTkCheckBox(form, text="Repeat auto", variable=self._repeat).pack(anchor="w", padx=6, pady=(2, 6))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkButton(buttons, text="Save preset", command=self._save_current).pack(side="left", padx=(0, 4))
        ctk.CTkButton(buttons, text="Load defaults", command=self._load_defaults).pack(side="left", padx=4)
        ctk.CTkButton(buttons, text="Delete", command=self._delete_selected).pack(side="left", padx=4)

        self._list = ctk.CTkTextbox(self, height=160)
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._list.configure(state="disabled")

        self.refresh()

    def refresh(self) -> None:
        presets = self._timer_service.list_presets()
        self._list.configure(state="normal")
        self._list.delete("1.0", "end")
        for preset in presets:
            marker = "*" if preset.id == self._selected_preset_id else " "
            self._list.insert(
                "end",
                f"{marker} {preset.id[:8]} | {preset.name} | {preset.mode} | {int(preset.duration)}s | repeat={preset.repeat}\n",
            )
        self._list.configure(state="disabled")

    def _save_current(self) -> None:
        try:
            duration = max(0.0, float(self._seconds.get() or 0))
        except Exception:
            duration = 0.0
        preset = self._timer_service.save_preset(
            name=self._name.get().strip() or "Preset",
            mode=self._mode.get(),
            duration=duration,
            repeat=bool(self._repeat.get()),
        )
        self._selected_preset_id = preset.id
        self.refresh()

    def _load_defaults(self) -> None:
        for name, duration, mode, repeat in self.DEFAULT_PRESETS:
            self._timer_service.save_preset(name=name, mode=mode, duration=duration, repeat=repeat)
        self.refresh()

    def _delete_selected(self) -> None:
        if not self._selected_preset_id:
            presets = self._timer_service.list_presets()
            if presets:
                self._selected_preset_id = presets[-1].id
        if self._selected_preset_id:
            self._timer_service.delete_preset(self._selected_preset_id)
            self._selected_preset_id = None
            self.refresh()

    def apply_first(self) -> None:
        presets = self._timer_service.list_presets()
        if not presets:
            return
        self._on_apply(presets[0])
