"""Always-on-top dice bar that reuses the shared dice engine."""

from __future__ import annotations

import tkinter as tk
from typing import List, Tuple

import customtkinter as ctk

from modules.dice import dice_engine
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

SUPPORTED_DICE_SIZES: Tuple[int, ...] = dice_engine.DEFAULT_DICE_SIZES
INTER_BAR_GAP = 0
HEIGHT_PADDING = 10


class DiceBarWindow(ctk.CTkToplevel):
    """Compact dice roller that mirrors the behaviour of the full window."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.overrideredirect(True)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self._drag_offset: Tuple[int, int] | None = None

        self.formula_var = tk.StringVar(value="1d20")
        self.exploding_var = tk.BooleanVar(value=False)
        self.separate_var = tk.BooleanVar(value=False)
        self.result_var = tk.StringVar(value="Enter a dice formula and roll.")
        self.total_var = tk.StringVar(value="")

        self._bar_frame: ctk.CTkFrame | None = None
        self._content_frame: ctk.CTkFrame | None = None
        self._content_grid_options: dict[str, object] | None = None
        self._collapse_button: ctk.CTkButton | None = None
        self._result_label: ctk.CTkLabel | None = None
        self._formula_entry: ctk.CTkEntry | None = None
        self._is_collapsed = False
        self._total_label: ctk.CTkLabel | None = None

        self._build_ui()
        self._apply_geometry()

        self.bind("<Escape>", lambda _event: self._on_close())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(self, corner_radius=0)
        bar.grid(row=0, column=0, sticky="nsew", padx=8, pady=4)
        bar.grid_columnconfigure(0, weight=0)
        bar.grid_columnconfigure(1, weight=1)
        bar.bind("<ButtonPress-1>", self._on_drag_start)
        bar.bind("<B1-Motion>", self._on_drag_motion)
        bar.bind("<ButtonRelease-1>", self._on_drag_end)
        self._bar_frame = bar

        collapse_button = ctk.CTkButton(
            bar,
            text="◀",
            width=32,
            command=self._toggle_collapsed,
        )
        collapse_button.grid(row=0, column=0, padx=(4, 6), pady=4, sticky="nsw")
        self._collapse_button = collapse_button

        content = ctk.CTkFrame(bar, corner_radius=0)
        self._content_grid_options = {"row": 0, "column": 1, "padx": 0, "pady": 0, "sticky": "nsew"}
        content.grid(**self._content_grid_options)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=0)
        content.grid_columnconfigure(2, weight=0)
        content.grid_columnconfigure(3, weight=0)
        content.grid_columnconfigure(4, weight=0)
        content.grid_columnconfigure(5, weight=1)
        content.grid_columnconfigure(6, weight=0)
        content.grid_rowconfigure(1, weight=0)
        self._content_frame = content

        entry = ctk.CTkEntry(content, textvariable=self.formula_var, width=260, height=30)
        entry.grid(row=0, column=0, padx=(4, 6), pady=4, sticky="ew")
        entry.bind("<Return>", lambda _event: self.roll())
        self._formula_entry = entry

        explode_box = ctk.CTkCheckBox(
            content,
            text="Explode",
            variable=self.exploding_var,
            checkbox_height=18,
        )
        explode_box.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        separate_box = ctk.CTkCheckBox(
            content,
            text="Separate",
            variable=self.separate_var,
            checkbox_height=18,
        )
        separate_box.grid(row=0, column=2, padx=4, pady=4, sticky="w")

        roll_button = ctk.CTkButton(
            content,
            text="Roll",
            width=80,
            height=32,
            command=self.roll,
            fg_color="#2fa572",
            hover_color="#23865a",
            font=("Segoe UI", 14, "bold"),
        )
        roll_button.grid(row=0, column=3, padx=4, pady=4, sticky="ew")

        clear_button = ctk.CTkButton(
            content,
            text="Clear",
            width=70,
            height=32,
            command=self._clear_formula,
        )
        clear_button.grid(row=0, column=4, padx=4, pady=4, sticky="ew")

        preset_frame = ctk.CTkFrame(content, fg_color="transparent")
        preset_frame.grid(row=0, column=5, padx=6, pady=4, sticky="w")
        for idx, faces in enumerate(SUPPORTED_DICE_SIZES):
            button = ctk.CTkButton(
                preset_frame,
                text=f"d{faces}",
                width=48,
                height=30,
                command=lambda f=faces: self._append_die(f),
            )
            button.grid(row=0, column=idx, padx=2, pady=0)

        result_frame = ctk.CTkFrame(content, fg_color="transparent")
        result_frame.grid(row=1, column=0, columnspan=7, padx=(4, 8), pady=(0, 6), sticky="ew")
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_columnconfigure(1, weight=0)

        result_label = ctk.CTkLabel(
            result_frame,
            textvariable=self.result_var,
            anchor="w",
            font=("Segoe UI", 16, "bold"),
            justify="left",
        )
        result_label.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        result_label.bind("<ButtonPress-1>", self._on_drag_start)
        result_label.bind("<B1-Motion>", self._on_drag_motion)
        result_label.bind("<ButtonRelease-1>", self._on_drag_end)
        self._result_label = result_label

        total_label = ctk.CTkLabel(
            result_frame,
            textvariable=self.total_var,
            anchor="e",
            font=("Segoe UI", 16, "bold"),
            justify="right",
        )
        total_label.grid(row=0, column=1, sticky="e")
        total_label.bind("<ButtonPress-1>", self._on_drag_start)
        total_label.bind("<B1-Motion>", self._on_drag_motion)
        total_label.bind("<ButtonRelease-1>", self._on_drag_end)
        self._total_label = total_label

        close_button = ctk.CTkButton(content, text="✕", width=32, height=30, command=self._on_close)
        close_button.grid(row=0, column=6, padx=(6, 8), pady=4, sticky="e")

        self._update_collapse_button()

        if self._formula_entry is not None:
            self.after(0, self._formula_entry.focus_set)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def roll(self) -> None:
        formula_text = self.formula_var.get()
        try:
            parsed = dice_engine.parse_formula(formula_text, supported_faces=SUPPORTED_DICE_SIZES)
        except dice_engine.FormulaError as exc:
            self._show_error(str(exc))
            return

        exploding = bool(self.exploding_var.get())
        separate = bool(self.separate_var.get())

        try:
            result = dice_engine.roll_parsed_formula(parsed, explode=exploding)
        except dice_engine.DiceEngineError as exc:
            self._show_error(str(exc))
            return

        canonical = result.canonical()
        self.formula_var.set(canonical)

        breakdown_text, total_text = self._format_roll_output(result, separate)
        self.result_var.set(breakdown_text)
        self.total_var.set(total_text)

    def _append_die(self, faces: int) -> None:
        fragment = f"1d{faces}"
        current = self.formula_var.get().strip()
        combined = fragment if not current else f"{current} + {fragment}"
        try:
            parsed = dice_engine.parse_formula(combined, supported_faces=SUPPORTED_DICE_SIZES)
        except dice_engine.FormulaError as exc:
            self._show_error(str(exc))
            return
        self.formula_var.set(parsed.canonical())
        self.result_var.set(f"Added {fragment} to formula.")
        self.total_var.set("")

    def _clear_formula(self) -> None:
        self.formula_var.set("")
        self.result_var.set("Formula cleared.")
        self.total_var.set("")
        if self._formula_entry is not None:
            self._formula_entry.focus_set()

    def _format_roll_output(
        self, result: dice_engine.RollResult, separate: bool
    ) -> tuple[str, str]:
        canonical = result.canonical()
        modifier = result.modifier
        total = result.total

        if separate:
            parts: List[str] = []
            counters: dict[int, int] = {}
            for chain in result.chains:
                counters[chain.faces] = counters.get(chain.faces, 0) + 1
                label = f"d{chain.faces}"
                if result.parsed.dice.get(chain.faces, 0) > 1:
                    label = f"{label}#{counters[chain.faces]}"
                values = ", ".join(chain.display_values)
                if values:
                    parts.append(f"{label}:[{values}] RESULT {chain.total}")
                else:
                    parts.append(f"{label} RESULT {chain.total}")
            if modifier:
                parts.append(f"mod {modifier:+d}")
            breakdown = " | ".join(parts) if parts else "0"
            base_text = f"{canonical} -> {breakdown}" if canonical else breakdown
            total_text = f"TOTAL: {total}"
            return base_text, total_text

        summary_parts: List[str] = []
        for summary in result.face_summaries:
            values = summary.display_values
            if not values:
                continue
            summary_parts.append(
                f"{summary.base_count}d{summary.faces}:[{', '.join(values)}] RESULT {summary.total}"
            )
        if modifier:
            summary_parts.append(f"mod {modifier:+d}")
        breakdown = " | ".join(summary_parts) if summary_parts else "0"
        summary_text = f"{canonical} -> {breakdown}" if canonical else breakdown
        return summary_text, f"TOTAL: {total}"

    # ------------------------------------------------------------------
    # Window helpers
    # ------------------------------------------------------------------
    def show(self) -> None:
        try:
            self.deiconify()
            self._apply_geometry()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(250, self._apply_geometry)
        except Exception:
            pass

    def _apply_geometry(self) -> None:
        try:
            self.update_idletasks()
            if self._is_collapsed:
                target = self._collapse_button or self
                width = max(80, int(target.winfo_reqwidth() + 16))
                height_source = target
            else:
                width = self.winfo_screenwidth()
                height_source = self._bar_frame or self
            base_height = height_source.winfo_reqheight() if height_source else 36
            height = max(36, int(base_height + HEIGHT_PADDING))
            screen_height = self.winfo_screenheight()
            y = screen_height - height

            audio_window = getattr(self.master, "audio_bar_window", None)
            if audio_window is not None and audio_window.winfo_exists():
                try:
                    audio_window.update_idletasks()
                    audio_height = int(audio_window.winfo_height() or 0)
                    if audio_height <= 1:
                        geometry = audio_window.geometry()
                        try:
                            size_part = geometry.split("x", 1)[1]
                            height_part = size_part.split("+", 1)[0]
                            audio_height = int(height_part)
                        except (IndexError, ValueError):
                            audio_height = 0
                    audio_y = int(audio_window.winfo_rooty())
                    if audio_y <= 0 and audio_height:
                        audio_y = screen_height - audio_height
                    gap = max(0, INTER_BAR_GAP)
                    y = audio_y - height - gap
                except Exception:
                    pass

            self.geometry(f"{width}x{height}+0+{max(0, y)}")
        except Exception:
            pass

    def _show_error(self, message: str) -> None:
        self.result_var.set(f"⚠️ {message}")
        self.total_var.set("")

    def _toggle_collapsed(self) -> None:
        self._set_collapsed(not self._is_collapsed)

    def _set_collapsed(self, collapsed: bool) -> None:
        if collapsed == self._is_collapsed:
            return
        self._is_collapsed = collapsed
        frame = self._content_frame
        if frame is not None:
            if collapsed:
                frame.grid_remove()
            else:
                options = self._content_grid_options or {}
                if options:
                    frame.grid(**options)
                else:
                    frame.grid(row=0, column=1, padx=0, pady=0, sticky="nsew")
        self._update_collapse_button()
        self._apply_geometry()

    def _update_collapse_button(self) -> None:
        if self._collapse_button is None:
            return
        self._collapse_button.configure(text="▶" if self._is_collapsed else "◀")

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_offset = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _on_drag_motion(self, event: tk.Event) -> None:
        if self._drag_offset is None:
            return
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.geometry(f"+{x}+{y}")

    def _on_drag_end(self, _event: tk.Event) -> None:
        self._drag_offset = None

    def _on_close(self) -> None:
        self.destroy()
