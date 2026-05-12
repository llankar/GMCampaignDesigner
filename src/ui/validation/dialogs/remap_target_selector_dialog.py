"""Selector dialog for choosing a missing-reference remap target."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from modules.helpers.tk_text_safety import (
    LABEL_DISPLAY_LIMIT,
    LONGFORM_DISPLAY_LIMIT,
    safe_display_text,
)
from src.ui.validation.labels import (
    CANCEL_LABEL,
    CHOOSE_REMAP_TARGET_MESSAGE,
    CHOOSE_REMAP_TARGET_TITLE,
    NO_REMAP_TARGETS_MESSAGE,
    REMAP_LABEL,
)
from src.validation.reference_validator import EntityRecord


@dataclass(frozen=True)
class RemapTargetOption:
    """One compatible entity that can replace a missing reference."""

    entity: EntityRecord

    @property
    def display_text(self) -> str:
        """Return a stable user-facing label for dropdowns and lists."""

        label = safe_display_text(self.entity.label, max_chars=LABEL_DISPLAY_LIMIT)
        identifier = safe_display_text(
            self.entity.identifier,
            max_chars=LABEL_DISPLAY_LIMIT,
        )
        path = " > ".join(self.entity.path)
        path_text = safe_display_text(path, max_chars=LONGFORM_DISPLAY_LIMIT)
        if label == identifier:
            main_text = label
        else:
            main_text = f"{label} ({identifier})"
        if path_text:
            return safe_display_text(
                f"{main_text} — {path_text}",
                max_chars=LONGFORM_DISPLAY_LIMIT,
            )
        return safe_display_text(main_text, max_chars=LONGFORM_DISPLAY_LIMIT)


class RemapTargetSelectorDialog:
    """Blocking CustomTkinter dialog that returns the selected remap target."""

    def __init__(self, master: Any, targets: Sequence[RemapTargetOption]) -> None:
        self.master = master
        self.targets = tuple(targets)
        self.selected_target: EntityRecord | None = None
        self.window: Any | None = None
        self._selected_text: Any | None = None
        self._remap_button: Any | None = None
        self._display_to_target = _display_index(self.targets)

    def show(self) -> EntityRecord | None:
        """Open the modal selector and return the chosen target, or ``None``."""

        import customtkinter as ctk

        window = ctk.CTkToplevel(self.master)
        self.window = window
        window.title(CHOOSE_REMAP_TARGET_TITLE)
        window.transient(self.master)
        window.grab_set()
        window.geometry("560x280")
        window.grid_columnconfigure(0, weight=1)
        window.protocol("WM_DELETE_WINDOW", self.cancel)

        ctk.CTkLabel(
            window,
            text=CHOOSE_REMAP_TARGET_TITLE,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        if self.targets:
            ctk.CTkLabel(
                window,
                text=CHOOSE_REMAP_TARGET_MESSAGE,
                wraplength=500,
                justify="left",
            ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 14))
            self._selected_text = ctk.StringVar(value="")
            dropdown = ctk.CTkOptionMenu(
                window,
                values=tuple(self._display_to_target),
                variable=self._selected_text,
                command=self._on_selection_changed,
            )
            dropdown.grid(row=2, column=0, sticky="ew", padx=20, pady=4)
        else:
            ctk.CTkLabel(
                window,
                text=NO_REMAP_TARGETS_MESSAGE,
                wraplength=500,
                justify="left",
            ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 14))

        actions = ctk.CTkFrame(window)
        actions.grid(row=3, column=0, sticky="e", padx=20, pady=(22, 20))
        self._remap_button = ctk.CTkButton(
            actions,
            text=REMAP_LABEL,
            command=self.remap,
            state="disabled",
        )
        self._remap_button.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(actions, text=CANCEL_LABEL, command=self.cancel).grid(
            row=0,
            column=1,
        )

        window.wait_window()
        return self.selected_target

    def _on_selection_changed(self, selected_text: str) -> None:
        if self._remap_button is not None:
            state = "normal" if selected_text in self._display_to_target else "disabled"
            self._remap_button.configure(state=state)

    def remap(self) -> None:
        """Accept the current selection and close the dialog."""

        selected_text = (
            self._selected_text.get() if self._selected_text is not None else ""
        )
        selected_target = self._display_to_target.get(selected_text)
        if selected_target is None:
            return
        self.selected_target = selected_target.entity
        self._close()

    def cancel(self) -> None:
        """Abort remapping without choosing a target."""

        self.selected_target = None
        self._close()

    def _close(self) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None


def open_remap_target_selector_dialog(
    master: Any,
    targets: Sequence[RemapTargetOption],
) -> EntityRecord | None:
    """Open the dedicated remap target selector dialog."""

    return RemapTargetSelectorDialog(master, targets).show()


def _display_index(
    targets: Sequence[RemapTargetOption],
) -> dict[str, RemapTargetOption]:
    display_to_target: dict[str, RemapTargetOption] = {}
    for index, target in enumerate(targets, start=1):
        display_text = target.display_text
        if display_text in display_to_target:
            display_text = safe_display_text(
                f"{display_text} #{index}",
                max_chars=LONGFORM_DISPLAY_LIMIT,
            )
        display_to_target[display_text] = target
    return display_to_target
