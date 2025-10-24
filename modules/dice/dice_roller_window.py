import tkinter as tk
import time
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set

import customtkinter as ctk
from modules.helpers import theme_manager
from tkinter import messagebox
import numpy as np
from matplotlib import cm

try:
    from scipy.spatial import ConvexHull
except ImportError:  # pragma: no cover - scipy is listed in requirements, but fall back gracefully
    ConvexHull = None

from modules.helpers.window_helper import position_window_at_top
from modules.helpers.logging_helper import log_module_import
from modules.dice import dice_engine
from modules.dice import dice_preferences

log_module_import(__name__)

@dataclass(frozen=True)
class DiceModel:
    vertices: np.ndarray
    faces: List[np.ndarray]
    label_offset: float


def _normalize_vertices(vertices: np.ndarray) -> np.ndarray:
    max_norm = np.max(np.linalg.norm(vertices, axis=1))
    if max_norm == 0:
        return vertices.copy()
    return vertices / max_norm


def _convex_faces(vertices: np.ndarray) -> List[np.ndarray]:
    if ConvexHull is None:
        raise RuntimeError("scipy is required to build 3D dice models.")
    hull = ConvexHull(vertices)
    return [face for face in hull.simplices]


def _make_model(vertices: List[Tuple[float, float, float]], predefined_faces: List[List[int]] | None = None) -> DiceModel:
    verts = _normalize_vertices(np.array(vertices, dtype=float))
    if predefined_faces:
        faces = [np.array(face, dtype=int) for face in predefined_faces]
    else:
        faces = _convex_faces(verts)
    radius = np.max(np.linalg.norm(verts, axis=1)) or 1.0
    label_offset = radius + 0.35
    return DiceModel(vertices=verts, faces=faces, label_offset=label_offset)


def _cube_vertices() -> List[Tuple[float, float, float]]:
    return [
        (-1, -1, -1),
        (1, -1, -1),
        (1, 1, -1),
        (-1, 1, -1),
        (-1, -1, 1),
        (1, -1, 1),
        (1, 1, 1),
        (-1, 1, 1),
    ]


def _tetra_vertices() -> List[Tuple[float, float, float]]:
    return [
        (1, 1, 1),
        (-1, -1, 1),
        (-1, 1, -1),
        (1, -1, -1),
    ]


def _octa_vertices() -> List[Tuple[float, float, float]]:
    return [
        (1, 0, 0),
        (-1, 0, 0),
        (0, 1, 0),
        (0, -1, 0),
        (0, 0, 1),
        (0, 0, -1),
    ]


def _trapezohedron_vertices() -> List[Tuple[float, float, float]]:
    vertices: List[Tuple[float, float, float]] = [(0.0, 0.0, 1.15), (0.0, 0.0, -1.15)]
    upper_height = 0.45
    lower_height = -0.45
    radius = 0.94
    for i in range(5):
        angle = 2 * np.pi * i / 5
        vertices.append((radius * np.cos(angle), radius * np.sin(angle), upper_height))
    for i in range(5):
        angle = 2 * np.pi * (i + 0.5) / 5
        vertices.append((radius * np.cos(angle), radius * np.sin(angle), lower_height))
    return vertices


def _d10_faces() -> List[List[int]]:
    faces: List[List[int]] = []
    for i in range(5):
        ui = 2 + i
        ui_next = 2 + ((i + 1) % 5)
        li = 7 + i
        li_next = 7 + ((i + 1) % 5)
        faces.append([0, ui, li, ui_next])
        faces.append([1, li, ui_next, li_next])
    return faces


def _dodecahedron_vertices() -> List[Tuple[float, float, float]]:
    phi = (1 + np.sqrt(5)) / 2
    inv_phi = 1 / phi
    vertices: List[Tuple[float, float, float]] = []
    for x in (-1, 1):
        for y in (-1, 1):
            for z in (-1, 1):
                vertices.append((x, y, z))
    for combo in (
        (0, inv_phi, phi),
        (inv_phi, phi, 0),
        (phi, 0, inv_phi),
    ):
        for sx in (1, -1):
            for sy in (1, -1):
                vertices.append((combo[0] * sx, combo[1] * sy, combo[2]))
                vertices.append((combo[0] * sx, combo[1] * sy, -combo[2]))
    unique: List[Tuple[float, float, float]] = []
    seen: Set[Tuple[float, float, float]] = set()
    for vertex in vertices:
        key = (round(vertex[0], 6), round(vertex[1], 6), round(vertex[2], 6))
        if key in seen:
            continue
        seen.add(key)
        unique.append(vertex)
    return unique


def _icosahedron_vertices() -> List[Tuple[float, float, float]]:
    phi = (1 + np.sqrt(5)) / 2
    vertices = []
    for signs in ((1, 0, phi), (-1, 0, phi), (1, 0, -phi), (-1, 0, -phi)):
        vertices.append(signs)
    for signs in ((0, phi, 1), (0, -phi, 1), (0, phi, -1), (0, -phi, -1)):
        vertices.append(signs)
    for signs in ((phi, 1, 0), (-phi, 1, 0), (phi, -1, 0), (-phi, -1, 0)):
        vertices.append(signs)
    return vertices


_PREDEFINED_FACES: Dict[int, List[List[int]]] = {
    4: [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]],
    6: [
        [0, 1, 2, 3],
        [4, 5, 6, 7],
        [0, 1, 5, 4],
        [2, 3, 7, 6],
        [1, 2, 6, 5],
        [4, 7, 3, 0],
    ],
    8: [
        [0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4],
        [0, 2, 5], [2, 1, 5], [1, 3, 5], [3, 0, 5],
    ],
    10: _d10_faces(),
    12: [
        [11, 9, 2, 19, 0],
        [6, 12, 14, 2, 9],
        [2, 14, 3, 18, 19],
        [8, 10, 1, 18, 3],
        [5, 13, 15, 1, 10],
        [1, 15, 0, 19, 18],
        [16, 17, 4, 13, 5],
        [4, 17, 6, 9, 11],
        [13, 4, 11, 0, 15],
        [17, 16, 7, 12, 6],
        [7, 16, 5, 10, 8],
        [12, 7, 8, 3, 14],
    ],
    20: [
        [6, 2, 8],
        [3, 6, 9],
        [3, 6, 2],
        [1, 0, 5],
        [10, 2, 8],
        [10, 0, 5],
        [10, 0, 8],
        [4, 0, 8],
        [4, 6, 9],
        [4, 6, 8],
        [4, 1, 0],
        [4, 1, 9],
        [11, 1, 9],
        [11, 3, 9],
        [11, 1, 5],
        [7, 10, 5],
        [7, 3, 2],
        [7, 10, 2],
        [7, 11, 3],
        [7, 11, 5],
    ],
}



def _build_dice_models() -> Dict[int, DiceModel]:
    models: Dict[int, DiceModel] = {}
    models[4] = _make_model(_tetra_vertices(), _PREDEFINED_FACES.get(4))
    models[6] = _make_model(_cube_vertices(), _PREDEFINED_FACES.get(6))
    models[8] = _make_model(_octa_vertices(), _PREDEFINED_FACES.get(8))
    models[10] = _make_model(_trapezohedron_vertices(), _PREDEFINED_FACES.get(10))
    models[12] = _make_model(_dodecahedron_vertices(), _PREDEFINED_FACES.get(12))
    models[20] = _make_model(_icosahedron_vertices(), _PREDEFINED_FACES.get(20))
    return models


DICE_MODELS = _build_dice_models()


class DiceRollerWindow(ctk.CTkToplevel):

    def __init__(self, master: ctk.CTk):
        super().__init__(master)
        self.title("Dice Roller")
        self.geometry("1280x760")
        self.minsize(1200, 760)
        position_window_at_top(self)
        self.configure(bg="#0e1621")

        self._colormap = cm.get_cmap("plasma")
        self._animation_job: str | None = None
        self._animation_state: dict | None = None
        self._base_dice_scale = 2.4
        self.dice_scale = 1.0
        self._last_dice_sequence: List[Dict[str, object]] = []
        self._preset_segmented: ctk.CTkSegmentedButton | None = None
        self._supported_faces: Tuple[int, ...] = tuple(sorted(DICE_MODELS.keys()))
        self._dice_choices: Tuple[str, ...] = tuple(f"d{faces}" for faces in self._supported_faces)

        default_choice = self._dice_choices[0] if self._dice_choices else "d20"
        self.dice_selection_var = ctk.StringVar(value=default_choice)
        self.dice_count_var = ctk.IntVar(value=1)
        self.formula_var = ctk.StringVar(value="")
        self.exploding_var = ctk.BooleanVar(value=False)
        self.separate_var = ctk.BooleanVar(value=False)

        self._build_layout()
        self.refresh_system_settings(initial=True)

        self.bind("<Return>", lambda _event: self.roll_dice())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def refresh_system_settings(self, *, initial: bool = False) -> None:
        """Reload dice presets and default formulas for the active system."""

        faces = tuple(face for face in dice_preferences.get_supported_faces() if face in DICE_MODELS)
        if not faces:
            faces = tuple(sorted(DICE_MODELS.keys()))

        if faces != self._supported_faces:
            self._supported_faces = faces
            self._dice_choices = tuple(f"d{face}" for face in faces)
            segmented = self._preset_segmented
            if segmented is not None:
                try:
                    segmented.configure(values=self._dice_choices)
                except Exception:
                    pass
            current_choice = self.dice_selection_var.get()
            if current_choice not in self._dice_choices and self._dice_choices:
                self.dice_selection_var.set(self._dice_choices[0])

        if not self._dice_choices:
            self._dice_choices = tuple(f"d{face}" for face in faces)

        if self._preset_segmented is not None and getattr(self._preset_segmented, "_buttons_dict", None):
            # Rebind double-clicks in case widgets were recreated by configure.
            self.after_idle(self._setup_preset_double_clicks)

        default_formula = dice_preferences.get_rollable_default_formula()
        if initial or not self.formula_var.get().strip():
            self.formula_var.set(default_formula)

    # -----------------
    # Layout & UI setup
    # -----------------
    def _build_layout(self) -> None:
        tokens = theme_manager.get_tokens()
        container = ctk.CTkFrame(self, fg_color=tokens.get("panel_bg"))
        container.pack(fill="both", expand=True, padx=12, pady=12)

        controls_frame = ctk.CTkFrame(container, fg_color=tokens.get("panel_alt_bg"), corner_radius=14)
        controls_frame.pack(side="left", fill="y", padx=(12, 8), pady=12)
        controls_frame.pack_propagate(False)
        controls_frame.configure(width=280)

        ctk.CTkLabel(
            controls_frame,
            text="Dice Presets",
            font=("Segoe UI", 16, "bold"),
        ).pack(pady=(18, 10))

        segmented = ctk.CTkSegmentedButton(
            controls_frame,
            values=self._dice_choices,
            variable=self.dice_selection_var,
            command=self._on_choice,
        )
        segmented.pack(fill="x", padx=16)
        self._preset_segmented = segmented
        self._setup_preset_double_clicks()

        count_frame = ctk.CTkFrame(controls_frame, fg_color=tokens.get("panel_bg"))
        count_frame.pack(fill="x", padx=16, pady=(24, 8))
        ctk.CTkLabel(count_frame, text="Number of dice", anchor="w").pack(fill="x", pady=(6, 2))
        slider = ctk.CTkSlider(
            count_frame,
            from_=1,
            to=10,
            number_of_steps=9,
            command=self._on_slider,
        )
        slider.set(self.dice_count_var.get())
        slider.pack(fill="x")
        self.count_value_label = ctk.CTkLabel(count_frame, text="1", font=("Segoe UI", 14, "bold"))
        self.count_value_label.pack(pady=(6, 0))

        builder_frame = ctk.CTkFrame(controls_frame, fg_color=tokens.get("panel_bg"))
        builder_frame.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            builder_frame,
            text="Double-click a preset to add",
            anchor="w",
        ).pack(fill="x", padx=4, pady=(8, 4))
        ctk.CTkButton(
            builder_frame,
            text="Clear Formula",
            fg_color=tokens.get("accent_button_fg"),
            hover_color=tokens.get("accent_button_hover"),
            command=self._clear_formula,
        ).pack(fill="x", pady=(0, 8))

        toggle_frame = ctk.CTkFrame(controls_frame, fg_color=tokens.get("panel_bg"))
        toggle_frame.pack(fill="x", padx=16, pady=(4, 4))
        ctk.CTkCheckBox(
            toggle_frame,
            text="Exploding dice (reroll max)",
            variable=self.exploding_var
        ).pack(fill="x", pady=(6, 2))
        ctk.CTkCheckBox(
            toggle_frame,
            text="Show per-die results",
            variable=self.separate_var
        ).pack(fill="x", pady=(0, 6))

        formula_frame = ctk.CTkFrame(controls_frame, fg_color=tokens.get("panel_bg"))
        formula_frame.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(formula_frame, text="Dice Formula", anchor="w").pack(fill="x", pady=(6, 2))
        self.formula_entry = ctk.CTkEntry(formula_frame, textvariable=self.formula_var)
        self.formula_entry.pack(fill="x", padx=4, pady=(0, 6))
        self.formula_entry.bind("<Return>", lambda _event: self.roll_dice())
        ctk.CTkLabel(
            formula_frame,
            text="Examples: 1d6 + 1d8, 4d12 + 3d8 + 2",
            font=("Segoe UI", 12),
            anchor="w",
            text_color="#b0bfd4",
            wraplength=220,
            justify="left",
        ).pack(fill="x", padx=4, pady=(0, 6))

        buttons_frame = ctk.CTkFrame(controls_frame, fg_color="#111c2a")
        buttons_frame.pack(fill="x", padx=16, pady=(12, 8))
        ctk.CTkButton(buttons_frame, text="Roll Formula", command=self.roll_dice).pack(fill="x", pady=(8, 4))
        ctk.CTkButton(
            buttons_frame,
            text="Clear History",
            fg_color="#303c5a",
            command=self._clear_history,
        ).pack(fill="x", pady=(0, 8))
        plot_wrapper = ctk.CTkFrame(container, fg_color="#111c2a", corner_radius=14)
        plot_wrapper.pack(side="left", fill="both", expand=True, padx=(8, 12), pady=12)
        self.plot_frame = plot_wrapper

        self.result_title = ctk.CTkLabel(
            plot_wrapper,
            text="Roll Result",
            font=("Segoe UI", 18, "bold"),
        )
        self.result_title.pack(pady=(12, 4))

        self.result_display = ctk.CTkTextbox(
            plot_wrapper,
            height=72,
            wrap="word",
            font=("Segoe UI", 16, "bold"),
            activate_scrollbars=False,
        )
        self.result_display.pack(fill="x", padx=16, pady=(0, 16))
        self.result_display.tag_config("result_highlight", foreground="#ffd166")
        self.result_display.configure(state="disabled")
        self._set_result_text("Build a dice formula and roll!")

        self.dice_canvas = tk.Canvas(plot_wrapper, bg="#111c2a", highlightthickness=0)
        self.dice_canvas.pack(fill="both", expand=True)
        self.dice_canvas.bind("<Configure>", lambda _e: self._render_dice(self._last_dice_sequence))

        history_wrapper = ctk.CTkFrame(plot_wrapper, fg_color="#101b2c", corner_radius=12)
        history_wrapper.pack(fill="x", padx=16, pady=(12, 16))

        ctk.CTkLabel(
            history_wrapper,
            text="History",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(12, 4), padx=12, anchor="w")

        self.history_box = ctk.CTkTextbox(history_wrapper, height=120, activate_scrollbars=False)
        self.history_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.history_box.configure(state="disabled")

    # -----------------
    def _set_result_text(self, text: str, highlights: List[Tuple[int, int]] | None = None) -> None:
        box = self.result_display
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", text)
        box.tag_remove("result_highlight", "1.0", "end")
        if highlights:
            for start, end in highlights:
                if end <= start:
                    continue
                box.tag_add("result_highlight", f"1.0+{start}c", f"1.0+{end}c")
        box.configure(state="disabled")

    def _on_choice(self, _value: str) -> None:
        choice = self.dice_selection_var.get()
        self._set_result_text(f"Selected {choice}. Double-click the preset to add it.")

    def _setup_preset_double_clicks(self) -> None:
        segmented = self._preset_segmented
        if segmented is None:
            return
        buttons = getattr(segmented, "_buttons_dict", {})
        for value, button in buttons.items():
            try:
                button.bind("<Double-Button-1>", lambda _event, v=value: self._handle_preset_double_click(v))
            except Exception:
                continue

    def _handle_preset_double_click(self, value: str) -> None:
        if value:
            self.dice_selection_var.set(value)
        try:
            self._add_to_formula()
        except ValueError as exc:
            messagebox.showerror("Invalid Formula", str(exc))

    def _on_slider(self, value: float) -> None:
        count = int(round(value))
        self.dice_count_var.set(count)
        self.count_value_label.configure(text=str(count))

    def _clear_formula(self) -> None:
        self.formula_var.set("")
        self._set_result_text("Formula cleared. Build a new roll.")

    # -----------------
    # Formula helpers
    # -----------------
    def _add_to_formula(self) -> None:
        faces = int(self.dice_selection_var.get()[1:])
        count = max(1, self.dice_count_var.get())
        fragment = f"{count}d{faces}"
        current = self.formula_var.get().strip()
        combined = fragment if not current else f"{current} + {fragment}"
        supported_faces = dice_preferences.get_supported_faces()
        try:
            parsed = dice_engine.parse_formula(combined, supported_faces=supported_faces)
        except dice_engine.FormulaError as exc:
            messagebox.showerror("Invalid Formula", str(exc))
            return
        self.formula_var.set(parsed.canonical())
        self._set_result_text(f"Added {fragment} to formula.")

    # -----------------
    # Rolling & history
    # -----------------
    def roll_dice(self) -> None:
        formula_text = self.formula_var.get()
        supported_faces = dice_preferences.get_supported_faces()
        try:
            parsed = dice_engine.parse_formula(formula_text, supported_faces=supported_faces)
        except dice_engine.FormulaError as exc:
            messagebox.showerror("Invalid Formula", str(exc))
            return

        exploding = bool(self.exploding_var.get())
        separate = bool(self.separate_var.get())

        try:
            result = dice_engine.roll_parsed_formula(parsed, explode=exploding)
        except dice_engine.DiceEngineError as exc:
            messagebox.showerror("Invalid Formula", str(exc))
            return

        canonical = result.canonical()
        self.formula_var.set(canonical)

        base_counts = dict(result.parsed.dice)
        modifier = result.modifier
        total = result.total

        grouped_display: Dict[int, List[str]] = {
            summary.faces: list(summary.display_values)
            for summary in result.face_summaries
        }
        grouped_totals: Dict[int, int] = {
            summary.faces: summary.total for summary in result.face_summaries
        }

        breakdown_parts: List[str] = []
        for summary in result.face_summaries:
            values = summary.display_values
            if not values:
                continue
            breakdown_parts.append(
                f"{summary.base_count}d{summary.faces}: [{', '.join(values)}]"
            )
        if modifier:
            breakdown_parts.append(f"modifier {modifier:+d}")
        breakdown_text = " | ".join(breakdown_parts) if breakdown_parts else "0"

        highlight_spans: List[Tuple[int, int]] = []
        if separate:
            segments: List[str] = []
            for summary in result.face_summaries:
                values = summary.display_values
                if not values:
                    continue
                segment = (
                    f"{summary.base_count}d{summary.faces}:[{', '.join(values)}] = {summary.total}"
                )
                segments.append(segment)
            if modifier:
                segments.append(f"modifier {modifier:+d}")
            if segments:
                result_text_parts: List[str] = []
                cumulative_length = 0
                for segment in segments:
                    if result_text_parts:
                        result_text_parts.append(" | ")
                        cumulative_length += 3
                    start_index = cumulative_length
                    result_text_parts.append(segment)
                    cumulative_length += len(segment)
                    if "=" in segment:
                        eq_pos = segment.rfind("=")
                        after_eq = segment[eq_pos + 1:]
                        trimmed = after_eq.lstrip()
                        offset = len(after_eq) - len(trimmed)
                        highlight_start = start_index + eq_pos + 1 + offset
                        highlight_end = start_index + len(segment)
                        highlight_spans.append((highlight_start, highlight_end))
                result_text = "".join(result_text_parts)
            else:
                result_text = canonical
        else:
            result_text = f"{canonical} => {breakdown_text} = {total}"
            token = f"= {total}"
            idx = result_text.rfind(token)
            if idx != -1:
                highlight_start = idx + len("= ")
                highlight_end = highlight_start + len(str(total))
                highlight_spans.append((highlight_start, highlight_end))

        self._set_result_text(result_text, highlight_spans)
        self._append_history(
            canonical,
            grouped_display,
            base_counts,
            grouped_totals,
            modifier,
            total,
            separate,
        )
        dice_sequence = self._build_render_sequence(result)
        self._last_dice_sequence = dice_sequence
        self._render_dice(dice_sequence)

    def _build_render_sequence(self, result: dice_engine.RollResult) -> List[Dict[str, object]]:
        sequence: List[Dict[str, object]] = []
        group_index = 0
        for chain in result.chains:
            chain_entries: List[Dict[str, object]] = []
            for roll in chain.rolls:
                display_value = f"{roll.value}{'!' if roll.exploded else ''}"
                chain_entries.append(
                    {
                        "faces": chain.faces,
                        "value": roll.value,
                        "exploded": roll.exploded,
                        "display": display_value,
                        "group": group_index,
                        "chain_end": False,
                    }
                )
            if chain_entries:
                chain_entries[-1]["chain_end"] = True
                sequence.extend(chain_entries)
                group_index += 1
        return sequence

    def _clear_history(self) -> None:
        self.history_box.configure(state="normal")
        self.history_box.delete("1.0", "end")
        self.history_box.configure(state="disabled")
        self._set_result_text("History cleared. Ready for new rolls.")

    def _append_history(self, canonical: str, grouped: Dict[int, List[str]], base_counts: Dict[int, int], grouped_totals: Dict[int, int], modifier: int, total: int, separate: bool) -> None:
        timestamp = time.strftime("%H:%M:%S")
        breakdown_parts: List[str] = []
        for faces in sorted(grouped):
            values = grouped[faces]
            base = base_counts.get(faces, len(values))
            segment = f"{base}d{faces}:[{', '.join(values)}]"
            if separate:
                segment += f"={grouped_totals.get(faces, 0)}"
            breakdown_parts.append(segment)
        if modifier:
            breakdown_parts.append(f"mod {modifier:+d}")
        breakdown_text = " | ".join(breakdown_parts) if breakdown_parts else canonical
        entry = f"[{timestamp}] {canonical} -> {breakdown_text} = {total}"
        self.history_box.configure(state="normal")
        self.history_box.insert("end", entry)
        self.history_box.see("end")
        self.history_box.configure(state="disabled")

    # -----------------
    # Animation helpers
    # -----------------
    # Animation helpers
    # -----------------
    def _render_dice(self, dice_sequence: List[Dict[str, object]]) -> None:
        if not hasattr(self, "dice_canvas"):
            return
        canvas = self.dice_canvas
        try:
            canvas.delete("dice")
        except Exception:
            return

        self._last_dice_sequence = list(dice_sequence or [])
        if not dice_sequence:
            return

        width = max(int(canvas.winfo_width() or 0), 200)
        height = max(int(canvas.winfo_height() or 0), 200)

        scale, raw_factor = self._effective_scale()
        max_radius = min(width, height) * 0.45
        base_size = self._base_dice_scale * 18.0 * (raw_factor ** 0.55)
        base_size = max(24.0, min(base_size, max_radius))

        base_spacing = base_size * 1.9
        explosion_gap = base_size * 0.95
        chain_gap = base_size * 2.15

        positions: List[float] = []
        cursor = 0.0
        previous_group = None
        for die in dice_sequence:
            positions.append(cursor)
            step = base_spacing
            if die.get("exploded"):
                step += explosion_gap
            if previous_group is not None and die.get("group") != previous_group:
                step += chain_gap
            if die.get("chain_end"):
                step += chain_gap
            cursor += step
            previous_group = die.get("group")

        horizontal_padding = base_size * 0.8
        row_limit = max(base_spacing, width - 2 * horizontal_padding)

        rows: List[List[int]] = []
        current_row: List[int] = []
        row_start_pos = 0.0
        for idx, pos in enumerate(positions):
            if not current_row:
                current_row = [idx]
                row_start_pos = pos
                continue
            proposed_width = pos - row_start_pos + base_spacing
            if proposed_width > row_limit:
                rows.append(current_row)
                current_row = [idx]
                row_start_pos = pos
            else:
                current_row.append(idx)
        if current_row:
            rows.append(current_row)

        centers_by_index: Dict[int, float] = {}
        for row_indices in rows:
            if not row_indices:
                continue
            row_positions = [positions[i] for i in row_indices]
            if len(row_positions) == 1:
                row_midpoint = row_positions[0]
            else:
                row_midpoint = (row_positions[0] + row_positions[-1]) / 2.0
            for idx in row_indices:
                centers_by_index[idx] = positions[idx] - row_midpoint

        row_count = len(rows)
        if row_count == 0:
            return

        base_row_height = max(base_size * 1.8, 72.0)
        top_padding = base_size * 1.35
        bottom_padding = base_size * 1.6
        row_height = base_row_height
        if row_count > 1:
            max_block_height = max(0.0, height - top_padding - bottom_padding)
            needed_height = base_row_height * (row_count - 1)
            if needed_height > max_block_height and (row_count - 1) > 0:
                row_height = max(base_size * 1.3, max_block_height / (row_count - 1))

        block_height = row_height * (row_count - 1)
        start_y = max(top_padding, (height - block_height) / 2.0)
        max_end = height - bottom_padding
        if start_y + block_height > max_end:
            start_y = max(top_padding, max_end - block_height)

        center_x = width / 2.0
        text_offset = base_size * 1.05
        font_size = int(max(14, base_size * 0.45))

        for row_idx, row_indices in enumerate(rows):
            y = start_y + row_idx * row_height
            for idx in row_indices:
                die = dice_sequence[idx]
                faces = int(die.get("faces", 6))
                value = die.get("value", 0)
                display = die.get("display") or str(value)
                rgba = self._color_for_value(faces, value)
                offset_x = centers_by_index.get(idx, 0.0)

                x = center_x + offset_x
                self._draw_die_shape(canvas, x, y, base_size, faces, rgba, value)
                canvas.create_text(
                    x,
                    y - text_offset,
                    text=display,
                    fill="white",
                    font=("Segoe UI", font_size, "bold"),
                    tags="dice",
                )

    def _effective_scale(self) -> Tuple[float, float]:
        try:
            factor = float(self.dice_scale)
        except Exception:
            factor = 1.0
        factor = max(0.1, factor)
        return self._base_dice_scale * factor, factor

    def _draw_die_shape(self, canvas: tk.Canvas, x: float, y: float, size: float, faces: int, rgba: Tuple[float, float, float, float], value: int | None = None) -> None:
        base_hex = self._rgba_to_hex(rgba)
        darker = self._rgba_to_hex(rgba, 0.7)
        lighter = self._rgba_to_hex(rgba, 1.25)

        model = DICE_MODELS.get(faces)
        if model is not None:
            if self._draw_polyhedral_die(canvas, x, y, size, model, rgba, faces, value=value):
                return

        if faces == 4:
            self._draw_tetra_die(canvas, x, y, size, lighter, base_hex, darker)
        elif faces == 6:
            self._draw_cube_die(canvas, x, y, size, lighter, base_hex, darker)
        elif faces == 8:
            self._draw_octa_die(canvas, x, y, size, lighter, base_hex, darker)
        elif faces == 10:
            self._draw_trapezohedron_die(canvas, x, y, size, base_hex, darker)
        elif faces == 12:
            self._draw_dodeca_die(canvas, x, y, size, lighter, base_hex, darker)
        elif faces == 20:
            self._draw_icosa_die(canvas, x, y, size, lighter, base_hex, darker)
        else:
            sides = max(3, min(12, faces))
            self._draw_regular_polygon(canvas, x, y, size, sides, base_hex, darker)

    def _draw_polyhedral_die(self, canvas: tk.Canvas, x: float, y: float, size: float, model: DiceModel, rgba: Tuple[float, float, float, float], faces: int, value: int | None = None) -> bool:
        try:
            rotation = self._polyhedron_rotation(faces, value)
            rotated = model.vertices.dot(rotation.T)
            scale = size * 0.95
            projected = np.empty_like(rotated)
            projected[:, 0] = x + rotated[:, 0] * scale
            projected[:, 1] = y - rotated[:, 1] * scale
            projected[:, 2] = rotated[:, 2]

            base_rgb = np.clip(np.array(rgba[:3]), 0.0, 1.0)
            outline_rgb = np.clip(base_rgb * 0.45, 0.0, 1.0)
            outline_hex = self._rgb_to_hex(tuple(outline_rgb.tolist()))

            light_dir = np.array([0.3, 0.6, 1.0])
            light_dir /= np.linalg.norm(light_dir)
            view_dir = np.array([0.0, 0.0, 1.0])

            faces_to_draw: List[Tuple[float, List[Tuple[float, float]], str]] = []
            for face_indices in model.faces:
                indices = [int(i) for i in face_indices]
                if len(indices) < 3:
                    continue
                v0 = rotated[indices[0]]
                v1 = rotated[indices[1]]
                v2 = rotated[indices[2]]
                normal = np.cross(v1 - v0, v2 - v0)
                norm_len = float(np.linalg.norm(normal))
                if norm_len == 0.0:
                    continue
                normal_unit = normal / norm_len
                facing = float(np.dot(normal_unit, view_dir))
                if facing <= 0.0:
                    continue
                diffuse = max(0.0, float(np.dot(normal_unit, light_dir)))
                shade = 0.30 + 0.70 * diffuse
                face_rgb = np.clip(base_rgb * shade, 0.0, 1.0)
                polygon = [(float(projected[i, 0]), float(projected[i, 1])) for i in indices]
                avg_depth = float(np.mean(rotated[indices, 2]))
                faces_to_draw.append((avg_depth, polygon, self._rgb_to_hex(tuple(face_rgb.tolist()))))

            if not faces_to_draw:
                return False

            faces_to_draw.sort(key=lambda entry: entry[0])
            for _depth, polygon, fill_hex in faces_to_draw:
                coords: List[float] = []
                for px, py in polygon:
                    coords.extend((px, py))
                canvas.create_polygon(coords, fill=fill_hex, outline=outline_hex, width=1.4, tags="dice")
            return True
        except Exception:
            return False

    def _polyhedron_rotation(self, faces: int, value: int | None = None) -> np.ndarray:
        presets = {
            4: (32.0, -24.0, -26.0, 0.6),
            6: (32.0, -28.0, 18.0, 0.6),
            8: (30.0, -28.0, 12.0, 0.6),
            10: (48.0, -34.0, 18.0, 0.0),
            12: (26.0, -18.0, 18.0, 0.4),
            20: (24.0, -6.0, 4.0, 0.0),
        }
        tilt_x_deg, tilt_y_deg, base_spin_deg, jitter_scale = presets.get(faces, (32.0, -28.0, 15.0, 0.5))

        jitter_deg = 0.0
        if value is not None and jitter_scale:
            jitter_deg = ((value * 37) % 40 - 20) * float(jitter_scale)

        tilt_x = math.radians(tilt_x_deg)
        tilt_y = math.radians(tilt_y_deg)
        spin_z = math.radians(base_spin_deg + jitter_deg)

        cosx = math.cos(tilt_x)
        sinx = math.sin(tilt_x)
        cosy = math.cos(tilt_y)
        siny = math.sin(tilt_y)
        cosz = math.cos(spin_z)
        sinz = math.sin(spin_z)

        rx = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, cosx, -sinx],
                [0.0, sinx, cosx],
            ]
        )
        ry = np.array(
            [
                [cosy, 0.0, siny],
                [0.0, 1.0, 0.0],
                [-siny, 0.0, cosy],
            ]
        )
        rz = np.array(
            [
                [cosz, -sinz, 0.0],
                [sinz, cosz, 0.0],
                [0.0, 0.0, 1.0],
            ]
        )
        return rz @ ry @ rx

    def _rgb_to_hex(self, rgb: Tuple[float, float, float]) -> str:
        r = max(0, min(255, int(round(float(rgb[0]) * 255))))
        g = max(0, min(255, int(round(float(rgb[1]) * 255))))
        b = max(0, min(255, int(round(float(rgb[2]) * 255))))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw_tetra_die(self, canvas: tk.Canvas, x: float, y: float, size: float, top: str, left: str, right: str) -> None:
        apex = (x, y - size * 0.9)
        left_mid = (x - size * 0.9, y + size * 0.35)
        right_mid = (x + size * 0.9, y + size * 0.35)
        bottom = (x, y + size * 0.95)

        canvas.create_polygon(
            [apex[0], apex[1], right_mid[0], right_mid[1], left_mid[0], left_mid[1]],
            fill=top,
            outline="#091624",
            tags="dice",
        )
        canvas.create_polygon(
            [apex[0], apex[1], left_mid[0], left_mid[1], bottom[0], bottom[1]],
            fill=left,
            outline="#091624",
            tags="dice",
        )
        canvas.create_polygon(
            [apex[0], apex[1], bottom[0], bottom[1], right_mid[0], right_mid[1]],
            fill=right,
            outline="#091624",
            tags="dice",
        )

    def _draw_cube_die(self, canvas: tk.Canvas, x: float, y: float, size: float, top: str, right: str, left: str) -> None:
        top_poly = [
            x,
            y - size * 0.75,
            x + size * 0.74,
            y - size * 0.38,
            x,
            y,
            x - size * 0.74,
            y - size * 0.38,
        ]
        right_poly = [
            x,
            y,
            x + size * 0.74,
            y - size * 0.38,
            x + size * 0.74,
            y + size * 0.55,
            x,
            y + size * 0.98,
        ]
        left_poly = [
            x,
            y,
            x - size * 0.74,
            y - size * 0.38,
            x - size * 0.74,
            y + size * 0.55,
            x,
            y + size * 0.98,
        ]
        canvas.create_polygon(top_poly, fill=top, outline="#091624", tags="dice")
        canvas.create_polygon(right_poly, fill=right, outline="#091624", tags="dice")
        canvas.create_polygon(left_poly, fill=left, outline="#091624", tags="dice")

    def _draw_octa_die(self, canvas: tk.Canvas, x: float, y: float, size: float, top: str, base: str, bottom: str) -> None:
        top_poly = [
            x,
            y - size,
            x + size * 0.8,
            y,
            x,
            y + size * 0.25,
            x - size * 0.8,
            y,
        ]
        bottom_poly = [
            x - size * 0.8,
            y,
            x,
            y + size * 0.25,
            x + size * 0.8,
            y,
            x,
            y + size * 1.15,
        ]
        canvas.create_polygon(top_poly, fill=top, outline="#091624", tags="dice")
        canvas.create_polygon(bottom_poly, fill=bottom, outline="#091624", tags="dice")
        canvas.create_polygon(
            [x - size * 0.8, y, x, y + size * 0.25, x, y + size * 1.15, x - size * 0.8, y],
            fill=base,
            outline="#091624",
            tags="dice",
        )
        canvas.create_polygon(
            [x + size * 0.8, y, x, y + size * 0.25, x, y + size * 1.15, x + size * 0.8, y],
            fill=self._rgba_to_hex((0.05, 0.08, 0.12, 1.0), 1.0),
            outline="#091624",
            tags="dice",
        )


    def _draw_trapezohedron_die(self, canvas: tk.Canvas, x: float, y: float, size: float, fill_hex: str, outline_hex: str) -> None:
        top_apex = (x, y - size * 0.92)
        bottom_apex = (x, y + size * 0.92)

        top_ring = []
        bottom_ring = []
        for i in range(5):
            angle = -math.pi / 2 + 2 * math.pi * i / 5
            top_ring.append((
                x + size * 0.62 * math.cos(angle),
                y - size * 0.18 + size * 0.32 * math.sin(angle),
            ))
            bottom_angle = angle + math.pi / 5
            bottom_ring.append((
                x + size * 0.68 * math.cos(bottom_angle),
                y + size * 0.26 + size * 0.36 * math.sin(bottom_angle),
            ))

        bottom_fill = self._shade_hex(fill_hex, 0.58)
        for i in range(5):
            nxt = (i + 1) % 5
            polygon = [bottom_apex, bottom_ring[nxt], bottom_ring[i]]
            canvas.create_polygon(
                self._flatten_points(polygon),
                fill=bottom_fill,
                outline=outline_hex,
                tags="dice",
            )

        for i in range(5):
            phase = -math.pi / 2 + 2 * math.pi * i / 5
            shade = 0.78 + 0.18 * math.cos(phase)
            face_fill = self._shade_hex(fill_hex, shade)
            polygon = [top_apex, top_ring[i], bottom_ring[i], bottom_apex]
            canvas.create_polygon(
                self._flatten_points(polygon),
                fill=face_fill,
                outline=outline_hex,
                tags="dice",
            )

        top_fill = self._shade_hex(fill_hex, 1.08)
        for i in range(5):
            nxt = (i + 1) % 5
            polygon = [top_apex, top_ring[i], top_ring[nxt]]
            canvas.create_polygon(
                self._flatten_points(polygon),
                fill=top_fill,
                outline=outline_hex,
                tags="dice",
            )

    def _draw_dodeca_die(self, canvas: tk.Canvas, x: float, y: float, size: float, top_hex: str, side_hex: str, bottom_hex: str) -> None:
        outline = "#091624"
        top_points = self._regular_polygon_coords(x, y - size * 0.55, size * 0.45, 5, rotation=-math.pi / 2)
        upper_ring = self._regular_polygon_coords(x, y - size * 0.1, size * 0.7, 5, rotation=-math.pi / 2)
        lower_ring = self._regular_polygon_coords(x, y + size * 0.25, size * 0.7, 5, rotation=-math.pi / 2 + math.pi / 5)
        bottom_points = self._regular_polygon_coords(x, y + size * 0.65, size * 0.45, 5, rotation=-math.pi / 2 + math.pi / 5)

        canvas.create_polygon(self._flatten_points(top_points), fill=top_hex, outline=outline, tags="dice")

        for i in range(5):
            next_idx = (i + 1) % 5
            upper_face = [top_points[i], upper_ring[i], upper_ring[next_idx], top_points[next_idx]]
            canvas.create_polygon(self._flatten_points(upper_face), fill=side_hex, outline=outline, tags="dice")

        belt_shade = self._shade_hex(side_hex, 0.9)
        for i in range(5):
            next_idx = (i + 1) % 5
            belt_face = [upper_ring[i], lower_ring[i], lower_ring[next_idx], upper_ring[next_idx]]
            canvas.create_polygon(self._flatten_points(belt_face), fill=belt_shade, outline=outline, tags="dice")

        lower_shade = self._shade_hex(bottom_hex, 0.85)
        for i in range(5):
            next_idx = (i + 1) % 5
            lower_face = [lower_ring[i], bottom_points[i], bottom_points[next_idx], lower_ring[next_idx]]
            canvas.create_polygon(self._flatten_points(lower_face), fill=lower_shade, outline=outline, tags="dice")

        bottom_fill = self._shade_hex(bottom_hex, 0.7)
        canvas.create_polygon(self._flatten_points(bottom_points), fill=bottom_fill, outline=outline, tags="dice")

    def _draw_icosa_die(self, canvas: tk.Canvas, x: float, y: float, size: float, top_hex: str, side_hex: str, bottom_hex: str) -> None:
        outline = "#091624"
        top_apex = (x, y - size * 0.95)
        bottom_apex = (x, y + size * 0.95)

        upper_ring: List[Tuple[float, float]] = []
        lower_ring: List[Tuple[float, float]] = []
        for i in range(5):
            angle = -math.pi / 2 + 2 * math.pi * i / 5
            upper_ring.append((
                x + size * 0.6 * math.cos(angle),
                y - size * 0.25 + size * 0.35 * math.sin(angle),
            ))
            lower_angle = angle + math.pi / 5
            lower_ring.append((
                x + size * 0.68 * math.cos(lower_angle),
                y + size * 0.25 + size * 0.4 * math.sin(lower_angle),
            ))

        for i in range(5):
            next_idx = (i + 1) % 5
            face = [top_apex, upper_ring[i], upper_ring[next_idx]]
            canvas.create_polygon(self._flatten_points(face), fill=top_hex, outline=outline, tags="dice")

        mid_fill = side_hex
        mid_shade = self._shade_hex(side_hex, 0.85)
        for i in range(5):
            next_idx = (i + 1) % 5
            face_one = [upper_ring[i], lower_ring[i], upper_ring[next_idx]]
            canvas.create_polygon(self._flatten_points(face_one), fill=mid_fill, outline=outline, tags="dice")
            face_two = [upper_ring[next_idx], lower_ring[i], lower_ring[next_idx]]
            canvas.create_polygon(self._flatten_points(face_two), fill=mid_shade, outline=outline, tags="dice")

        bottom_fill = self._shade_hex(bottom_hex, 0.8)
        for i in range(5):
            next_idx = (i + 1) % 5
            face = [bottom_apex, lower_ring[next_idx], lower_ring[i]]
            canvas.create_polygon(self._flatten_points(face), fill=bottom_fill, outline=outline, tags="dice")


    def _flatten_points(self, coords: List[Tuple[float, float]]) -> List[float]:
        flat: List[float] = []
        for px, py in coords:
            flat.extend([px, py])
        return flat

    def _draw_pent_trapezohedron(self, canvas: tk.Canvas, x: float, y: float, size: float, fill_hex: str, outline_hex: str) -> None:
        outline = outline_hex
        top_coords = self._regular_polygon_coords(x, y - size * 0.35, size * 0.58, 5, rotation=-math.pi / 2)
        bottom_coords = self._regular_polygon_coords(x, y + size * 0.45, size * 0.52, 5, rotation=-math.pi / 2 + math.pi / 5)

        for i in range(5):
            next_idx = (i + 1) % 5
            quad = [
                top_coords[i],
                bottom_coords[i],
                bottom_coords[next_idx],
                top_coords[next_idx],
            ]
            phase = 2 * math.pi * i / 5.0
            shade_factor = 0.86 + 0.12 * math.cos(phase)
            canvas.create_polygon(
                self._flatten_points(quad),
                fill=self._shade_hex(fill_hex, shade_factor),
                outline=outline,
                tags="dice",
            )

        canvas.create_polygon(
            self._flatten_points(top_coords),
            fill=self._shade_hex(fill_hex, 1.08),
            outline=outline,
            tags="dice",
        )
        canvas.create_polygon(
            self._flatten_points(bottom_coords),
            fill=self._shade_hex(fill_hex, 0.72),
            outline=outline,
            tags="dice",
        )

    def _draw_regular_polygon(self, canvas: tk.Canvas, x: float, y: float, radius: float, sides: int, fill_hex: str, outline_hex: str) -> None:
        points = self._regular_polygon_points(x, y, radius, sides)
        canvas.create_polygon(points, fill=fill_hex, outline=outline_hex, width=2, tags="dice")
        inner = self._regular_polygon_points(x, y - radius * 0.08, radius * 0.6, sides, rotation=math.pi / sides)
        canvas.create_polygon(inner, fill=self._shade_hex(fill_hex, 1.15), outline="", tags="dice")

    def _regular_polygon_points(self, x: float, y: float, radius: float, sides: int, rotation: float = 0.0) -> List[float]:
        coords = self._regular_polygon_coords(x, y, radius, sides, rotation=rotation)
        points: List[float] = []
        for px, py in coords:
            points.extend([px, py])
        return points

    def _regular_polygon_coords(self, x: float, y: float, radius: float, sides: int, rotation: float = 0.0) -> List[Tuple[float, float]]:
        coords: List[Tuple[float, float]] = []
        for i in range(sides):
            angle = rotation + math.pi / 2 - 2 * math.pi * i / sides
            px = x + radius * math.cos(angle)
            py = y - radius * math.sin(angle)
            coords.append((px, py))
        return coords

    def _rgba_to_hex(self, rgba: Tuple[float, float, float, float], multiplier: float = 1.0) -> str:
        r = max(0.0, min(1.0, rgba[0] * multiplier))
        g = max(0.0, min(1.0, rgba[1] * multiplier))
        b = max(0.0, min(1.0, rgba[2] * multiplier))
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    def _shade_hex(self, hex_color: str, factor: float) -> str:
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"
    def _color_for_value(self, faces: int, value: int) -> Tuple[float, float, float, float]:
        if faces <= 1:
            return 0.6, 0.2, 0.8, 1.0
        normalized = max(0.0, min(1.0, (value - 1) / (faces - 1)))
        rgba = self._colormap(normalized)
        return rgba[0], rgba[1], rgba[2], 0.95

    # -----------------
    # Lifecycle helpers
    # -----------------
    def _on_close(self) -> None:
        if self._animation_job:
            try:
                self.after_cancel(self._animation_job)
            except Exception:
                pass
        self.destroy()

    def show(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(400, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def withdraw(self) -> None:  # pragma: no cover - handled by Tk
        super().withdraw()
























