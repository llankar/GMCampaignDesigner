"""Always-on-top dice bar that reuses the shared dice engine."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import List, Tuple

import customtkinter as ctk
from modules.helpers import theme_manager

from modules.dice import dice_engine
from modules.dice import dice_preferences
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

INTER_BAR_GAP = 0
HEIGHT_PADDING = 10


@dataclass(frozen=True)
class TextSegment:
    """Represents a portion of result text and its emphasis preference."""

    text: str
    emphasize: bool = False


@dataclass(frozen=True)
class ResultChip:
    """Visual token representing one portion of a dice roll breakdown."""

    title: str
    detail: str
    total: str
    highlight: bool = False


@dataclass(frozen=True)
class FormattedRoll:
    """Container for the textual and visual representation of a roll."""

    segments: List[TextSegment]
    total_text: str
    header: str
    chips: List[ResultChip]


class DiceBarWindow(ctk.CTkToplevel):
    """Compact dice roller that mirrors the behaviour of the full window."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.overrideredirect(True)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self._drag_offset: Tuple[int, int] | None = None

        self.formula_var = tk.StringVar(value="")
        self.exploding_var = tk.BooleanVar(value=False)
        self.separate_var = tk.BooleanVar(value=False)
        self.result_var = tk.StringVar(value="Enter a dice formula and roll.")
        self.total_var = tk.StringVar(value="")

        self._bar_frame: ctk.CTkFrame | None = None
        self._content_frame: ctk.CTkFrame | None = None
        self._content_grid_options: dict[str, object] | None = None
        self._collapse_button: ctk.CTkButton | None = None
        self._result_container: ctk.CTkFrame | None = None
        self._formula_entry: ctk.CTkEntry | None = None
        self._is_collapsed = False
        self._total_label: ctk.CTkLabel | None = None
        self._total_prefix_label: ctk.CTkLabel | None = None

        self._expanded_height_hint: int | None = None
        self._collapsed_height_hint: int | None = None

        self._supported_faces: Tuple[int, ...] = tuple()
        self._last_system_default: str = ""
        self._last_roll_options: Tuple[bool, bool] = (False, False)
        self._preset_frame: ctk.CTkFrame | None = None

        self._result_normal_font = ctk.CTkFont(size=16)
        self._result_emphasis_font = ctk.CTkFont(size=18, weight="bold")
        self._result_header_font = ctk.CTkFont(size=13, weight="bold")
        self._result_detail_font = ctk.CTkFont(size=14)
        self._chip_total_font = ctk.CTkFont(size=18, weight="bold")

        self._build_ui()
        self.refresh_system_settings(initial=True)
        self._capture_height_hint(collapsed=False)
        self._set_collapsed(True)
        self._capture_height_hint(collapsed=True)
        self._apply_geometry()

        self.bind("<Escape>", lambda _event: self._on_close())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        tokens = theme_manager.get_tokens()
        bar = ctk.CTkFrame(self, corner_radius=0, fg_color=tokens.get("panel_bg"))
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
            width=16,
            fg_color=tokens.get("button_fg"),
            command=self._toggle_collapsed,
        )
        collapse_button.grid(row=0, column=0, padx=(4, 6), pady=4, sticky="nsw")
        self._collapse_button = collapse_button

        content = ctk.CTkFrame(bar, corner_radius=0, fg_color=tokens.get("panel_alt_bg"))
        self._content_grid_options = {"row": 0, "column": 1, "padx": 0, "pady": 0, "sticky": "nsew"}
        content.grid(**self._content_grid_options)
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=0)
        content.grid_columnconfigure(2, weight=0)
        content.grid_columnconfigure(3, weight=0)
        content.grid_columnconfigure(4, weight=0)
        content.grid_columnconfigure(5, weight=0)
        content.grid_columnconfigure(6, weight=1)
        content.grid_columnconfigure(7, weight=0)
        content.grid_rowconfigure(0, weight=1)
        self._content_frame = content

        entry = ctk.CTkEntry(content, textvariable=self.formula_var, width=200, height=30)
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
        preset_frame.grid(row=0, column=5, padx=(6, 4), pady=4, sticky="w")
        self._preset_frame = preset_frame

        result_frame = ctk.CTkFrame(content, fg_color="transparent")
        result_frame.grid(row=0, column=6, padx=(6, 4), pady=4, sticky="ew")
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_columnconfigure(1, weight=0)

        result_container = ctk.CTkFrame(result_frame, fg_color="transparent")
        result_container.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        result_container.grid_columnconfigure(0, weight=1)
        self._register_drag_target(result_container)
        self._result_container = result_container

        total_container = ctk.CTkFrame(result_frame, fg_color="transparent")
        total_container.grid(row=0, column=1, padx=(8, 0), sticky="e")
        total_container.grid_columnconfigure(0, weight=0)
        total_container.grid_columnconfigure(1, weight=0)
        self._register_drag_target(total_container)

        total_prefix = ctk.CTkLabel(
            total_container,
            text="Total",
            font=self._result_normal_font,
            anchor="e",
            justify="right",
        )
        total_prefix.grid(row=0, column=0, padx=(0, 6), sticky="e")
        self._register_drag_target(total_prefix)
        self._total_prefix_label = total_prefix

        total_label = ctk.CTkLabel(
            total_container,
            textvariable=self.total_var,
            font=self._result_emphasis_font,
            anchor="e",
            justify="right",
        )
        total_label.grid(row=0, column=1, sticky="e")
        self._register_drag_target(total_label)
        self._total_label = total_label

        self._set_total_text(self.total_var.get())

        self._display_segments([TextSegment(self.result_var.get())])

        close_button = ctk.CTkButton(content, text="✕", width=32, height=30, command=self._on_close)
        close_button.grid(row=0, column=7, padx=(4, 8), pady=4, sticky="e")

        self._update_collapse_button()

        if self._formula_entry is not None:
            self.after(0, self._formula_entry.focus_set)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def roll(self) -> None:
        formula_text = self.formula_var.get()
        supported_faces = self._supported_faces or dice_preferences.get_supported_faces()
        try:
            parsed = dice_engine.parse_formula(formula_text, supported_faces=supported_faces)
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

        formatted = self._format_roll_output(result, separate)
        self._display_segments(
            formatted.segments,
            header=formatted.header,
            chips=formatted.chips,
        )
        self._set_total_text(formatted.total_text)

    def _append_die(self, faces: int) -> None:
        fragment = f"1d{faces}"
        current = self.formula_var.get().strip()
        combined = fragment if not current else f"{current} + {fragment}"
        supported_faces = self._supported_faces or dice_preferences.get_supported_faces()
        try:
            parsed = dice_engine.parse_formula(combined, supported_faces=supported_faces)
        except dice_engine.FormulaError as exc:
            self._show_error(str(exc))
            return
        self.formula_var.set(parsed.canonical())
        self._display_segments([TextSegment(f"Added {fragment} to formula.")])
        self._set_total_text("")

    def _clear_formula(self) -> None:
        self.formula_var.set("")
        self._display_segments([TextSegment("Formula cleared.")])
        self._set_total_text("")
        if self._formula_entry is not None:
            self._formula_entry.focus_set()

    def refresh_system_settings(self, *, initial: bool = False) -> None:
        """Reload system-dependent dice presets and default formula."""

        faces = dice_preferences.get_supported_faces()
        if faces != self._supported_faces:
            self._supported_faces = faces
            self._rebuild_preset_buttons()

        default_formula = dice_preferences.get_rollable_default_formula()
        current = self.formula_var.get().strip()
        if initial or not current or current == self._last_system_default:
            self.formula_var.set(default_formula)
        self._last_system_default = default_formula

        roll_options = dice_preferences.get_default_roll_options()
        defaults = (bool(roll_options.get("explode")), bool(roll_options.get("separate")))
        if initial or defaults != self._last_roll_options:
            self.exploding_var.set(defaults[0])
            self.separate_var.set(defaults[1])
        self._last_roll_options = defaults

    def _rebuild_preset_buttons(self) -> None:
        frame = self._preset_frame
        if frame is None or not frame.winfo_exists():
            return
        for child in list(frame.winfo_children()):
            try:
                child.destroy()
            except tk.TclError:
                pass
        tokens = theme_manager.get_tokens()
        for idx, faces in enumerate(self._supported_faces):
            button = ctk.CTkButton(
                frame,
                text=f"d{faces}",
                width=48,
                height=30,
                command=lambda f=faces: self._append_die(f),
                fg_color=tokens.get("accent_button_fg"),
                hover_color=tokens.get("accent_button_hover"),
            )
            button.grid(row=0, column=idx, padx=2, pady=0)

    def _format_roll_output(
        self, result: dice_engine.RollResult, separate: bool
    ) -> FormattedRoll:
        canonical = result.canonical()
        modifier = result.modifier
        total = result.total

        header = f"{canonical} →" if canonical else "Last Roll"
        segments: List[TextSegment] = []
        if canonical:
            canonical_text = f"{canonical} -> "
            segments.append(TextSegment(canonical_text))

        chips: List[ResultChip] = []

        if separate:
            parts: List[List[TextSegment]] = []
            counters: dict[int, int] = {}
            for chain in result.chains:
                counters[chain.faces] = counters.get(chain.faces, 0) + 1
                label = f"d{chain.faces}"
                if result.parsed.dice.get(chain.faces, 0) > 1:
                    label = f"{label}#{counters[chain.faces]}"
                values = ", ".join(chain.display_values)
                prefix = f"{label}:[{values}] " if values else f"{label} "
                parts.append(
                    [TextSegment(prefix), TextSegment(str(chain.total), emphasize=True)]
                )
                chips.append(
                    ResultChip(
                        title=label,
                        detail=values or "—",
                        total=str(chain.total),
                        highlight=True,
                    )
                )
            if modifier:
                mod_text = f"mod {modifier:+d}"
                parts.append([TextSegment(mod_text)])
                chips.append(
                    ResultChip(
                        title="Modifier",
                        detail="Adjustment",
                        total=f"{modifier:+d}",
                        highlight=False,
                    )
                )
            breakdown_segments = self._join_parts(parts)
            segments.extend(breakdown_segments)
            if not breakdown_segments:
                segments.append(TextSegment("0", emphasize=True))
            if not chips:
                chips.append(
                    ResultChip(title="Result", detail="—", total=str(total), highlight=True)
                )
            return FormattedRoll(segments=segments, total_text=f"{total}", header=header, chips=chips)

        parts: List[List[TextSegment]] = []
        for summary in result.face_summaries:
            values = summary.display_values
            detail = ", ".join(values) if values else "—"
            if values:
                prefix = f"{summary.base_count}d{summary.faces}:[{', '.join(values)}] "
            else:
                prefix = f"{summary.base_count}d{summary.faces} "
            parts.append(
                [TextSegment(prefix), TextSegment(str(summary.total), emphasize=True)]
            )
            chips.append(
                ResultChip(
                    title=f"{summary.base_count}d{summary.faces}",
                    detail=detail,
                    total=str(summary.total),
                    highlight=True,
                )
            )
        if modifier:
            mod_text = f"mod {modifier:+d}"
            parts.append([TextSegment(mod_text)])
            chips.append(
                ResultChip(
                    title="Modifier",
                    detail="Adjustment",
                    total=f"{modifier:+d}",
                    highlight=False,
                )
            )
        breakdown_segments = self._join_parts(parts)
        segments.extend(breakdown_segments)
        if not breakdown_segments:
            segments.append(TextSegment("0", emphasize=True))
        if not chips:
            chips.append(ResultChip(title="Result", detail="—", total=str(total), highlight=True))
        return FormattedRoll(segments=segments, total_text=f"{total}", header=header, chips=chips)

    def _join_parts(self, parts: List[List[TextSegment]]) -> List[TextSegment]:
        segments: List[TextSegment] = []
        for index, part in enumerate(parts):
            if index:
                segments.append(TextSegment(" | "))
            segments.extend(part)
        return segments

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
                width = max(40, int(target.winfo_reqwidth() + 8))
                height_source = target
                if self._collapsed_height_hint is None and height_source is not None:
                    try:
                        measured = int(height_source.winfo_reqheight() or 0)
                    except Exception:
                        measured = 0
                    if measured:
                        self._collapsed_height_hint = measured
            else:
                width = self.winfo_screenwidth()
                height_source = self._bar_frame or self
                if self._expanded_height_hint is None and height_source is not None:
                    try:
                        measured = int(height_source.winfo_reqheight() or 0)
                    except Exception:
                        measured = 0
                    if measured:
                        self._expanded_height_hint = measured
            if self._is_collapsed:
                base_height = self._collapsed_height_hint
            else:
                base_height = self._expanded_height_hint
            if not base_height:
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
        self._display_segments([TextSegment(f"⚠️ {message}")])
        self._set_total_text("")

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

    def _display_segments(
        self,
        segments: List[TextSegment],
        *,
        header: str | None = None,
        chips: List[ResultChip] | None = None,
    ) -> None:
        self.result_var.set("".join(segment.text for segment in segments))

        container = self._result_container
        if container is None:
            return

        for child in container.winfo_children():
            child.destroy()

        container.grid_columnconfigure(0, weight=1)
        for index in range(3):
            container.grid_rowconfigure(index, weight=0)

        if chips:
            tokens = theme_manager.get_tokens()
            base_color = tokens.get("panel_alt_bg", "#132133")
            accent_color = tokens.get("accent_button_fg", "#2d3a57")
            accent_border = tokens.get("accent_button_hover", accent_color)
            border_color = tokens.get("button_border", "#1f2a3d")
            muted_text = "#9fb2ce"

            row = 0
            if header:
                header_label = ctk.CTkLabel(
                    container,
                    text=header,
                    font=self._result_header_font,
                    text_color=muted_text,
                    anchor="w",
                    justify="left",
                )
                header_label.grid(row=row, column=0, sticky="w", pady=(0, 4))
                self._register_drag_target(header_label)
                row += 1

            chips_frame = ctk.CTkFrame(container, fg_color="transparent")
            chips_frame.grid(row=row, column=0, sticky="w")
            self._register_drag_target(chips_frame)

            for index, chip in enumerate(chips):
                fg_color = accent_color if chip.highlight else base_color
                chip_border = accent_border if chip.highlight else border_color
                card = ctk.CTkFrame(
                    chips_frame,
                    corner_radius=10,
                    fg_color=fg_color,
                    border_width=1,
                    border_color=chip_border,
                )
                card.pack(side="left", padx=(0 if index == 0 else 8, 0), pady=4)
                self._register_drag_target(card)

                title_color = "#eef4ff" if chip.highlight else muted_text
                detail_color = "#f7faff" if chip.highlight else "#d3dced"
                total_color = "#ffffff" if chip.highlight else "#f1f5ff"

                title_label = ctk.CTkLabel(
                    card,
                    text=chip.title.upper(),
                    font=self._result_header_font,
                    text_color=title_color,
                    anchor="w",
                    justify="left",
                )
                title_label.pack(anchor="w", padx=14, pady=(10, 2))
                self._register_drag_target(title_label)

                detail_text = chip.detail.strip() or "—"
                detail_label = ctk.CTkLabel(
                    card,
                    text=detail_text,
                    font=self._result_detail_font,
                    text_color=detail_color,
                    anchor="w",
                    justify="left",
                )
                detail_label.pack(anchor="w", padx=14)
                self._register_drag_target(detail_label)

                total_label = ctk.CTkLabel(
                    card,
                    text=f"= {chip.total}",
                    font=self._chip_total_font,
                    text_color=total_color,
                    anchor="w",
                    justify="left",
                )
                total_label.pack(anchor="w", padx=14, pady=(6, 10))
                self._register_drag_target(total_label)
            self.after_idle(self._apply_geometry)
            return

        if not segments:
            return

        existing_columns, _ = container.grid_size()
        for column in range(existing_columns):
            container.grid_columnconfigure(column, weight=0)

        column_index = 0
        for segment in segments:
            if not segment.text:
                continue
            label = ctk.CTkLabel(
                container,
                text=segment.text,
                font=self._result_emphasis_font if segment.emphasize else self._result_normal_font,
                anchor="w",
                justify="left",
            )
            label.grid(row=0, column=column_index, padx=(0 if column_index == 0 else 4, 0), sticky="w")
            self._register_drag_target(label)
            column_index += 1

        container.grid_columnconfigure(column_index, weight=1)

        self.after_idle(self._apply_geometry)

    def _register_drag_target(self, widget: tk.Widget) -> None:
        widget.bind("<ButtonPress-1>", self._on_drag_start)
        widget.bind("<B1-Motion>", self._on_drag_motion)
        widget.bind("<ButtonRelease-1>", self._on_drag_end)

    def _set_total_text(self, text: str) -> None:
        self.total_var.set(text)
        prefix = self._total_prefix_label
        if prefix is not None:
            prefix.configure(text="Total" if text else "")

    def _capture_height_hint(self, *, collapsed: bool) -> None:
        try:
            self.update_idletasks()
            if collapsed:
                target = self._collapse_button or self
                if target is not None:
                    measured = int(target.winfo_reqheight() or 0)
                    if measured:
                        self._collapsed_height_hint = measured
            else:
                source = self._bar_frame or self
                if source is not None:
                    measured = int(source.winfo_reqheight() or 0)
                    if measured:
                        self._expanded_height_hint = measured
        except Exception:
            pass

