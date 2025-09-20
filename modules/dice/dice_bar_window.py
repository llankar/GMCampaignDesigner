"""Always-on-top dice bar that reuses the shared dice engine."""

from __future__ import annotations

import time
import tkinter as tk
from collections import deque
from typing import Deque, List, Tuple

import customtkinter as ctk

from modules.dice import dice_engine
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

SUPPORTED_DICE_SIZES: Tuple[int, ...] = dice_engine.DEFAULT_DICE_SIZES


class DiceBarWindow(ctk.CTkToplevel):
    """Compact dice roller that mirrors the behaviour of the full window."""

    HISTORY_LIMIT = 10

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.overrideredirect(True)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color="#111c2a")

        self._drag_offset: Tuple[int, int] | None = None
        self._history: Deque[str] = deque(maxlen=self.HISTORY_LIMIT)

        self.formula_var = tk.StringVar(value="1d20")
        self.exploding_var = tk.BooleanVar(value=False)
        self.result_var = tk.StringVar(value="Enter a dice formula and roll.")

        self._history_box: ctk.CTkTextbox | None = None
        self._result_label: ctk.CTkLabel | None = None
        self._formula_entry: ctk.CTkEntry | None = None

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

        container = ctk.CTkFrame(self, corner_radius=12, fg_color="#101a2a")
        container.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        container.grid_columnconfigure(1, weight=1)
        container.grid_columnconfigure(2, weight=0)
        container.grid_columnconfigure(3, weight=0)
        container.grid_columnconfigure(4, weight=0)

        handle = ctk.CTkLabel(container, text="🎲", width=28, font=("Segoe UI", 18))
        handle.grid(row=0, column=0, padx=(10, 4), pady=6, sticky="w")
        handle.bind("<ButtonPress-1>", self._on_drag_start)
        handle.bind("<B1-Motion>", self._on_drag_motion)
        handle.bind("<ButtonRelease-1>", self._on_drag_end)

        entry = ctk.CTkEntry(container, textvariable=self.formula_var, width=220)
        entry.grid(row=0, column=1, padx=4, pady=6, sticky="ew")
        entry.bind("<Return>", lambda _event: self.roll())
        self._formula_entry = entry

        explode_box = ctk.CTkCheckBox(
            container,
            text="Explode",
            variable=self.exploding_var,
        )
        explode_box.grid(row=0, column=2, padx=4, pady=6, sticky="w")

        roll_button = ctk.CTkButton(container, text="Roll", width=70, command=self.roll)
        roll_button.grid(row=0, column=3, padx=4, pady=6, sticky="ew")

        close_button = ctk.CTkButton(container, text="✕", width=32, command=self._on_close)
        close_button.grid(row=0, column=4, padx=(4, 10), pady=6, sticky="e")

        preset_frame = ctk.CTkFrame(container, fg_color="#0f1725")
        preset_frame.grid(row=1, column=0, columnspan=5, padx=10, pady=(0, 6), sticky="ew")
        for idx, faces in enumerate(SUPPORTED_DICE_SIZES):
            button = ctk.CTkButton(
                preset_frame,
                text=f"d{faces}",
                width=52,
                command=lambda f=faces: self._append_die(f),
            )
            button.grid(row=0, column=idx, padx=3, pady=4)

        result_label = ctk.CTkLabel(
            container,
            textvariable=self.result_var,
            anchor="w",
            wraplength=420,
            font=("Segoe UI", 14, "bold"),
        )
        result_label.grid(row=2, column=0, columnspan=4, padx=(12, 4), pady=(4, 2), sticky="ew")
        result_label.bind("<ButtonPress-1>", self._on_drag_start)
        result_label.bind("<B1-Motion>", self._on_drag_motion)
        result_label.bind("<ButtonRelease-1>", self._on_drag_end)
        self._result_label = result_label

        clear_button = ctk.CTkButton(container, text="Clear", width=60, command=self._clear_history)
        clear_button.grid(row=2, column=4, padx=(4, 12), pady=(4, 2), sticky="e")

        history_box = ctk.CTkTextbox(container, height=90, activate_scrollbars=False, wrap="word")
        history_box.grid(row=3, column=0, columnspan=5, padx=12, pady=(0, 10), sticky="nsew")
        history_box.configure(state="disabled")
        history_box.bind("<ButtonPress-1>", self._on_drag_start)
        history_box.bind("<B1-Motion>", self._on_drag_motion)
        history_box.bind("<ButtonRelease-1>", self._on_drag_end)
        self._history_box = history_box

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

        try:
            result = dice_engine.roll_parsed_formula(parsed, explode=bool(self.exploding_var.get()))
        except dice_engine.DiceEngineError as exc:
            self._show_error(str(exc))
            return

        canonical = result.canonical()
        self.formula_var.set(canonical)

        summary_parts: List[str] = []
        for summary in result.face_summaries:
            values = summary.display_values
            if not values:
                continue
            summary_parts.append(f"{summary.base_count}d{summary.faces}:[{', '.join(values)}]")
        if result.modifier:
            summary_parts.append(f"mod {result.modifier:+d}")
        breakdown = " | ".join(summary_parts) if summary_parts else "0"

        total = result.total
        self.result_var.set(f"{canonical} = {total}")
        self._append_history_entry(canonical, breakdown, total)

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

    def _append_history_entry(self, canonical: str, breakdown: str, total: int) -> None:
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {canonical} -> {breakdown} = {total}"
        self._history.append(entry)
        if self._history_box is None:
            return
        self._history_box.configure(state="normal")
        self._history_box.delete("1.0", "end")
        for line in self._history:
            self._history_box.insert("end", line + "\n")
        self._history_box.configure(state="disabled")
        self._history_box.see("end")

    def _clear_history(self) -> None:
        self._history.clear()
        if self._history_box is not None:
            self._history_box.configure(state="normal")
            self._history_box.delete("1.0", "end")
            self._history_box.configure(state="disabled")
        self.result_var.set("History cleared. Ready for new rolls.")

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
        except Exception:
            pass

    def _apply_geometry(self) -> None:
        width, height = 560, 180
        screen_width = self.winfo_screenwidth()
        x = max(screen_width - width - 60, 40)
        y = 60
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _show_error(self, message: str) -> None:
        self.result_var.set(f"⚠️ {message}")

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
