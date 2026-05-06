"""Summary dialog for campaign hierarchy validation runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.ui.validation.validation_wizard_controller import ValidationWizardSummary


@dataclass(frozen=True)
class ValidationSummaryCounts:
    """Counters displayed at the end of a validation wizard run."""

    corrected: int = 0
    ignored: int = 0
    remaining: int = 0

    @classmethod
    def from_summary(cls, summary: ValidationWizardSummary) -> "ValidationSummaryCounts":
        """Build visible counters from the wizard summary."""

        handled = summary.resolved + summary.skipped_session
        return cls(
            corrected=summary.resolved,
            ignored=summary.skipped_session,
            remaining=max(summary.total_issues - handled, 0),
        )


class ValidationSummaryDialog:
    """CustomTkinter dialog showing corrected, ignored and remaining issues."""

    def __init__(
        self,
        master: Any,
        counts: ValidationSummaryCounts,
        *,
        title: str = "Résumé de validation",
        message: str = "Vérification de cohérence hiérarchique terminée.",
    ) -> None:
        self.master = master
        self.counts = counts
        self.title = title
        self.message = message
        self.window: Any | None = None

    def show(self) -> "ValidationSummaryDialog":
        """Create and display the validation summary window."""

        import customtkinter as ctk

        window = ctk.CTkToplevel(self.master)
        self.window = window
        window.title(self.title)
        window.transient(self.master)
        window.grab_set()
        window.geometry("420x260")
        window.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            window,
            text=self.title,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(
            window,
            text=self.message,
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 16))

        counters = ctk.CTkFrame(window)
        counters.grid(row=2, column=0, sticky="ew", padx=20, pady=4)
        for column in range(3):
            counters.grid_columnconfigure(column, weight=1)

        self._render_counter(ctk, counters, 0, "Corrigés", self.counts.corrected)
        self._render_counter(ctk, counters, 1, "Ignorés", self.counts.ignored)
        self._render_counter(ctk, counters, 2, "Restants", self.counts.remaining)

        ctk.CTkButton(window, text="Fermer", command=self.close).grid(
            row=3, column=0, sticky="e", padx=20, pady=(18, 20)
        )
        return self

    def close(self) -> None:
        """Close the summary dialog if it is open."""

        if self.window is not None:
            self.window.destroy()
            self.window = None

    @staticmethod
    def _render_counter(ctk: Any, parent: Any, column: int, label: str, value: int) -> None:
        cell = ctk.CTkFrame(parent)
        cell.grid(row=0, column=column, sticky="nsew", padx=4, pady=4)
        cell.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cell,
            text=str(value),
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, pady=(12, 2))
        ctk.CTkLabel(cell, text=label).grid(row=1, column=0, pady=(0, 12))


def open_validation_summary_dialog(
    master: Any,
    summary: ValidationWizardSummary,
    *,
    title: str = "Résumé de validation",
    message: str = "Vérification de cohérence hiérarchique terminée.",
) -> ValidationSummaryDialog:
    """Open a validation summary dialog from a wizard summary."""

    return ValidationSummaryDialog(
        master,
        ValidationSummaryCounts.from_summary(summary),
        title=title,
        message=message,
    ).show()
