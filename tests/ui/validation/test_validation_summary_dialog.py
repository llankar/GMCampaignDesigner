"""Tests for validation summary counter calculations."""

from src.ui.validation.dialogs.validation_summary_dialog import ValidationSummaryCounts
from src.ui.validation.validation_wizard_controller import ValidationWizardSummary


def test_validation_summary_counts_expose_corrected_ignored_and_remaining():
    summary = ValidationWizardSummary(total_issues=5, resolved=2, skipped_session=1)

    counts = ValidationSummaryCounts.from_summary(summary)

    assert counts.corrected == 2
    assert counts.ignored == 1
    assert counts.remaining == 2


def test_validation_summary_remaining_never_goes_negative():
    summary = ValidationWizardSummary(total_issues=1, resolved=2, skipped_session=1)

    counts = ValidationSummaryCounts.from_summary(summary)

    assert counts.remaining == 0
