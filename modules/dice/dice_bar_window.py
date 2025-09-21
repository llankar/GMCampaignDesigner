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
HISTORY_PLACEHOLDER = "History empty"


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
        self.separate_var = tk.BooleanVar(value=False)
        self.result_var = tk.StringVar(value="Enter a dice formula and roll.")
        self.history_var = tk.StringVar(value=HISTORY_PLACEHOLDER)

        self._content_frame: ctk.CTkFrame | None = None
        self._content_grid_options: dict[str, object] | None = None
        self._collapse_button: ctk.CTkButton | None = None
        self._history_menu: ctk.CTkOptionMenu | None = None
        self._result_label: ctk.CTkLabel | None = None
        self._formula_entry: ctk.CTkEntry | None = None
        self._is_collapsed = False

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

        container = ctk.CTkFrame(self, corner_radius=0, fg_color="#101a2a")
        container.grid(row=0, column=0, sticky="nsew", padx=2, pady=(0, 2))
        container.grid_columnconfigure(0, weight=0)
        container.grid_columnconfigure(1, weight=0)
        container.grid_columnconfigure(2, weight=1)

        handle = ctk.CTkLabel(container, text="🎲", width=32, font=("Segoe UI", 18))
        handle.grid(row=0, column=0, padx=(10, 4), pady=0, sticky="w")
        handle.bind("<ButtonPress-1>", self._on_drag_start)
        handle.bind("<B1-Motion>", self._on_drag_motion)
        handle.bind("<ButtonRelease-1>", self._on_drag_end)

        collapse_button = ctk.CTkButton(
            container, text="▼", width=26, height=28, command=self._toggle_collapsed
        )
        collapse_button.grid(row=0, column=1, padx=(0, 6), pady=0, sticky="nsw")
        self._collapse_button = collapse_button

        content = ctk.CTkFrame(container, corner_radius=0, fg_color="transparent")
        self._content_grid_options = {"row": 0, "column": 2, "padx": (0, 10), "pady": 0, "sticky": "nsew"}
        content.grid(**self._content_grid_options)
        content.grid_columnconfigure(0, weight=2)
        content.grid_columnconfigure(1, weight=0)
        content.grid_columnconfigure(2, weight=0)
        content.grid_columnconfigure(3, weight=0)
        content.grid_columnconfigure(4, weight=0)
        content.grid_columnconfigure(5, weight=3)
        content.grid_columnconfigure(6, weight=2)
        content.grid_columnconfigure(7, weight=0)
        content.grid_columnconfigure(8, weight=0)
        self._content_frame = content

        entry = ctk.CTkEntry(content, textvariable=self.formula_var, width=260, height=30)
        entry.grid(row=0, column=0, padx=(4, 6), pady=0, sticky="ew")
        entry.bind("<Return>", lambda _event: self.roll())
        self._formula_entry = entry

        explode_box = ctk.CTkCheckBox(
            content,
            text="Explode",
            variable=self.exploding_var,
            checkbox_height=18,
        )
        explode_box.grid(row=0, column=1, padx=4, pady=0, sticky="w")

        separate_box = ctk.CTkCheckBox(
            content,
            text="Separate",
            variable=self.separate_var,
            checkbox_height=18,
        )
        separate_box.grid(row=0, column=2, padx=4, pady=0, sticky="w")

        roll_button = ctk.CTkButton(content, text="Roll", width=70, height=30, command=self.roll)
        roll_button.grid(row=0, column=3, padx=4, pady=0, sticky="ew")

        preset_frame = ctk.CTkFrame(content, fg_color="transparent")
        preset_frame.grid(row=0, column=4, padx=6, pady=0, sticky="w")
        for idx, faces in enumerate(SUPPORTED_DICE_SIZES):
            button = ctk.CTkButton(
                preset_frame,
                text=f"d{faces}",
                width=48,
                height=30,
                command=lambda f=faces: self._append_die(f),
            )
            button.grid(row=0, column=idx, padx=2, pady=0)

        result_label = ctk.CTkLabel(
            content,
            textvariable=self.result_var,
            anchor="w",
            font=("Segoe UI", 14, "bold"),
        )
        result_label.grid(row=0, column=5, padx=6, pady=0, sticky="ew")
        result_label.bind("<ButtonPress-1>", self._on_drag_start)
        result_label.bind("<B1-Motion>", self._on_drag_motion)
        result_label.bind("<ButtonRelease-1>", self._on_drag_end)
        self._result_label = result_label

        history_menu = ctk.CTkOptionMenu(
            content,
            variable=self.history_var,
            values=[HISTORY_PLACEHOLDER],
            command=self._on_history_selected,
            width=240,
            height=30,
        )
        history_menu.grid(row=0, column=6, padx=6, pady=0, sticky="ew")
        history_menu.configure(state="disabled")
        self._history_menu = history_menu

        clear_button = ctk.CTkButton(content, text="Clear", width=70, height=30, command=self._clear_history)
        clear_button.grid(row=0, column=7, padx=6, pady=0, sticky="ew")

        close_button = ctk.CTkButton(content, text="✕", width=32, height=30, command=self._on_close)
        close_button.grid(row=0, column=8, padx=(6, 8), pady=0, sticky="e")

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

        display_text, history_text = self._format_roll_output(result, separate)
        self.result_var.set(display_text)
        self._append_history_entry(history_text)

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

    def _format_roll_output(
        self, result: dice_engine.RollResult, separate: bool
    ) -> Tuple[str, str]:
        canonical = result.canonical()
        modifier = result.modifier
        total = result.total

        def highlight(value: int | str) -> str:
            return f"⟦{value}⟧"

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
                    parts.append(f"{label}:[{values}] = {highlight(chain.total)}")
                else:
                    parts.append(f"{label} = {highlight(chain.total)}")
            if modifier:
                parts.append(f"mod {modifier:+d}")
            breakdown = " | ".join(parts) if parts else "0"
            base_text = f"{canonical} -> {breakdown}"
            total_text = f"Total = {highlight(total)}"
            display_text = f"{base_text} | {total_text}" if base_text else total_text
            history_text = display_text
            return display_text, history_text

        summary_parts: List[str] = []
        for summary in result.face_summaries:
            values = summary.display_values
            if not values:
                continue
            summary_parts.append(f"{summary.base_count}d{summary.faces}:[{', '.join(values)}]")
        if modifier:
            summary_parts.append(f"mod {modifier:+d}")
        breakdown = " | ".join(summary_parts) if summary_parts else "0"
        display_text = f"{canonical} -> {breakdown} = {highlight(total)}"
        return display_text, display_text

    def _append_history_entry(self, text: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {text}"
        self._history.append(entry)
        self._update_history_menu()

    def _clear_history(self) -> None:
        self._history.clear()
        self._update_history_menu()
        self.result_var.set("History cleared. Ready for new rolls.")

    def _update_history_menu(self) -> None:
        if self._history_menu is None:
            return
        entries = list(self._history)
        if entries:
            display_entries = list(reversed(entries))
            self._history_menu.configure(values=display_entries)
            self._history_menu.configure(state="normal")
            self.history_var.set(display_entries[0])
        else:
            self._history_menu.configure(values=[HISTORY_PLACEHOLDER])
            self._history_menu.configure(state="disabled")
            self.history_var.set(HISTORY_PLACEHOLDER)

    def _on_history_selected(self, choice: str) -> None:
        if not choice or choice == HISTORY_PLACEHOLDER:
            return
        try:
            close_idx = choice.index("] ")
            remainder = choice[close_idx + 2 :]
        except ValueError:
            remainder = choice
        canonical = remainder.split(" ->", 1)[0].strip()
        if canonical:
            self.formula_var.set(canonical)
        self.result_var.set(choice)
        try:
            self.clipboard_clear()
            self.clipboard_append(choice)
        except Exception:
            pass

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
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        try:
            self.update_idletasks()
        except Exception:
            pass

        if self._is_collapsed:
            min_height = 32
            target = self._collapse_button or self
        else:
            min_height = 40
            target = self._content_frame or self

        requested = int(self.winfo_reqheight() or 0)
        try:
            target_height = int(target.winfo_reqheight() or 0)
        except Exception:
            target_height = 0
        if target_height:
            requested = max(requested, target_height)
        height = max(min_height, requested)
        x = 0
        y = max(screen_height - height, 0)

        audio_window = getattr(self.master, "audio_bar_window", None)
        if audio_window is not None:
            try:
                if audio_window.winfo_exists():
                    audio_window.update_idletasks()
                    is_mapped = bool(getattr(audio_window, "winfo_ismapped", lambda: True)())
                    if is_mapped:
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
                        spacing = 8
                        y = max(audio_y - height - spacing, 0)
            except Exception:
                pass

        self.geometry(f"{screen_width}x{height}+{x}+{y}")

    def _show_error(self, message: str) -> None:
        self.result_var.set(f"⚠️ {message}")

    def _toggle_collapsed(self) -> None:
        self._is_collapsed = not self._is_collapsed
        frame = self._content_frame
        if frame is not None:
            if self._is_collapsed:
                frame.grid_remove()
            else:
                options = self._content_grid_options or {}
                if options:
                    frame.grid(**options)
                else:
                    frame.grid(row=0, column=2, padx=(0, 12), pady=2, sticky="nsew")
        self._update_collapse_button()
        self.after(0, self._apply_geometry)

    def _update_collapse_button(self) -> None:
        if self._collapse_button is None:
            return
        self._collapse_button.configure(text="▲" if self._is_collapsed else "▼")

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
