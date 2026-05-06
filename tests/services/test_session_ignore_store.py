"""Regression tests for session-only ignored validation issues."""

from src.services import SessionIgnoreStore, issue_key
from src.validation import validate_references


def _missing_issue():
    hierarchy = {"type": "campaign", "id": "C1", "arc_refs": ["Missing Arc"]}
    return validate_references(hierarchy, campaign={"id": "sample"})[0]


def test_session_ignore_store_filters_ignored_issues_without_persistence_contract():
    issue = _missing_issue()
    store = SessionIgnoreStore()

    key = store.ignore(issue)

    assert key == issue_key(issue)
    assert store.is_ignored(issue) is True
    assert store.visible_issues([issue]) == ()
    assert len(store) == 1

    fresh_store = SessionIgnoreStore()
    assert fresh_store.is_ignored(issue) is False
    assert fresh_store.visible_issues([issue]) == (issue,)


def test_session_ignore_store_can_unignore_and_clear():
    issue = _missing_issue()
    store = SessionIgnoreStore()
    store.ignore(issue)

    assert store.unignore(issue) is True
    assert store.unignore(issue) is False
    assert store.is_ignored(issue) is False

    store.ignore(issue)
    store.clear()
    assert len(store) == 0
