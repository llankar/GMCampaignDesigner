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


def test_validation_summary_counts_include_non_issue_metrics():
    from src.ui.validation import ValidationWizardMetrics

    summary = ValidationWizardSummary(
        total_issues=0,
        metrics=ValidationWizardMetrics(
            entities_visited=7,
            references_checked=12,
            elapsed_seconds=1.25,
        ),
    )

    counts = ValidationSummaryCounts.from_summary(summary)

    assert counts.entities_visited == 7
    assert counts.references_checked == 12
    assert counts.elapsed_seconds == 1.25
    assert counts.no_entities_found is False


def test_validation_summary_counts_warn_when_scan_found_nothing():
    summary = ValidationWizardSummary(total_issues=0)

    counts = ValidationSummaryCounts.from_summary(summary)

    assert counts.no_entities_found is True
