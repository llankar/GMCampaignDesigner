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
    entities_visited: int = 0
    references_checked: int = 0
    elapsed_seconds: float = 0.0

    @classmethod
    def from_summary(cls, summary: ValidationWizardSummary) -> "ValidationSummaryCounts":
        """Build visible counters from the wizard summary."""

        handled = summary.resolved + summary.skipped_session
        return cls(
            corrected=summary.resolved,
            ignored=summary.skipped_session,
            remaining=max(summary.total_issues - handled, 0),
            entities_visited=summary.metrics.entities_visited,
            references_checked=summary.metrics.references_checked,
            elapsed_seconds=summary.metrics.elapsed_seconds,
        )

    @property
    def no_entities_found(self) -> bool:
        """Return whether the scan found no entities or references at all."""

        return self.entities_visited == 0 and self.references_checked == 0


class ValidationSummaryDialog:
    """CustomTkinter dialog showing issue and non-issue validation metrics."""

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
        window.geometry("500x360")
        window.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            window,
            text=self.title,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(
            window,
            text=self._status_message(),
            wraplength=440,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 16))

        issue_counters = ctk.CTkFrame(window)
        issue_counters.grid(row=2, column=0, sticky="ew", padx=20, pady=4)
        for column in range(3):
            issue_counters.grid_columnconfigure(column, weight=1)

        self._render_counter(
            ctk, issue_counters, 0, "Corrigés", self.counts.corrected
        )
        self._render_counter(ctk, issue_counters, 1, "Ignorés", self.counts.ignored)
        self._render_counter(
            ctk, issue_counters, 2, "Restants", self.counts.remaining
        )

        metrics = ctk.CTkFrame(window)
        metrics.grid(row=3, column=0, sticky="ew", padx=20, pady=(12, 4))
        for column in range(3):
            metrics.grid_columnconfigure(column, weight=1)

        self._render_counter(
            ctk, metrics, 0, "Entités visitées", self.counts.entities_visited
        )
        self._render_counter(
            ctk, metrics, 1, "Références vérifiées", self.counts.references_checked
        )
        self._render_counter(
            ctk, metrics, 2, "Temps écoulé", _format_elapsed(self.counts.elapsed_seconds)
        )

        ctk.CTkButton(window, text="Fermer", command=self.close).grid(
            row=4, column=0, sticky="e", padx=20, pady=(18, 20)
        )
        return self

    def close(self) -> None:
        """Close the summary dialog if it is open."""

        if self.window is not None:
            self.window.destroy()
            self.window = None

    def _status_message(self) -> str:
        if self.counts.no_entities_found:
            return f"{self.message}\n\n⚠️ No entities found under selected campaign."
        return self.message

    @staticmethod
    def _render_counter(ctk: Any, parent: Any, column: int, label: str, value: Any) -> None:
        cell = ctk.CTkFrame(parent)
        cell.grid(row=0, column=column, sticky="nsew", padx=4, pady=4)
        cell.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cell,
            text=str(value),
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, pady=(12, 2))
        ctk.CTkLabel(cell, text=label).grid(row=1, column=0, pady=(0, 12))


def _format_elapsed(seconds: float) -> str:
    if seconds < 1:
        return "<1 s"
    return f"{seconds:.1f} s"


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
