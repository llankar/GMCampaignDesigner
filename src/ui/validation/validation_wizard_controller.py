"""State controller for the interactive reference validation wizard.

The controller is intentionally UI-agnostic: dialogs, CustomTkinter views, or
other front-ends render the returned steps and feed the selected GM actions back
through :meth:`submit_action`.  This keeps the workflow deterministic and easy to
test while the mutation work remains delegated to ``ReferenceFixService``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import monotonic
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from modules.helpers.tk_text_safety import (
    LABEL_DISPLAY_LIMIT,
    LONGFORM_DISPLAY_LIMIT,
    safe_display_text,
)
from src.services import ReferenceActionResult, ReferenceFixService, SessionIgnoreStore
from src.ui.validation.labels import (
    ENTITY_CREATION_PENDING_MESSAGE,
    ENTITY_CREATION_REQUESTED_MESSAGE,
    ISSUE_IGNORED_MESSAGE,
    ISSUE_REFERENCE_MESSAGE,
    REFERENCE_NOT_FOUND_ACTION_MESSAGE,
    REFERENCE_NOT_FOUND_RESUME_MESSAGE,
    RESUME_NO_ENTITY_MESSAGE,
    UNKNOWN_ACTION_MESSAGE,
    VALIDATION_CANCELED_MESSAGE,
    VALIDATION_COMPLETED_MESSAGE,
)
from src.ui.validation.messages import format_hierarchy_issue_message
from src.validation import IssueType, ValidationIssue
from src.validation.reference_validator import EntityRecord, ReferenceRecord

ReferenceResolver = Callable[[ValidationIssue], ReferenceRecord | None]


class ValidationWizardAction(str, Enum):
    """Actions that can be selected by the GM for the current issue."""

    ATTACH = "attach"
    REMAP = "remap"
    REMOVE = "remove"
    CREATE_ENTITY = "create_entity"
    LINK_CREATED = "link_created"
    SKIP_SESSION = "skip_session"
    CANCEL = "cancel"


class ValidationWizardStatus(str, Enum):
    """High-level state returned to the UI layer after every transition."""

    SHOW_ISSUE = "show_issue"
    AWAITING_GM_ACTION = "awaiting_gm_action"
    AWAITING_ENTITY_CREATION = "awaiting_entity_creation"
    COMPLETED = "completed"
    CANCELED = "canceled"
    ACTION_FAILED = "action_failed"
    SETUP_FAILED = "setup_failed"


@dataclass(frozen=True)
class ValidationWizardIssue:
    """Pair one displayed validation issue with its mutable reference record.

    ``ValidationIssue`` is the user-facing problem emitted by validation;
    ``ReferenceRecord`` is the mutable location required by
    ``ReferenceFixService`` to apply the chosen fix.
    """

    issue: ValidationIssue
    reference: ReferenceRecord | None = None
    target: EntityRecord | None = None


@dataclass(frozen=True)
class ValidationWizardProgress:
    """Progress metadata for the currently displayed issue."""

    current_index: int
    visible_total: int
    raw_total: int


@dataclass(frozen=True)
class ValidationWizardMetrics:
    """Non-issue counters captured during a validation run."""

    entities_visited: int = 0
    references_checked: int = 0
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class ValidationWizardSummary:
    """Deterministic summary emitted when the wizard finishes or is canceled."""

    total_issues: int
    resolved: int = 0
    skipped_session: int = 0
    canceled: bool = False
    metrics: ValidationWizardMetrics = field(default_factory=ValidationWizardMetrics)
    changes_applied: tuple[str, ...] = field(default_factory=tuple)
    messages: tuple[str, ...] = field(default_factory=tuple)

    @property
    def completed(self) -> bool:
        """Return ``True`` when the wizard reached a normal, non-canceled end."""

        return not self.canceled


@dataclass(frozen=True)
class ValidationWizardSetupFailure:
    """Actionable setup error that prevents a validation scan from running."""

    title: str
    message: str


@dataclass(frozen=True)
class ValidationWizardStep:
    """Current step returned to the UI after a controller transition."""

    status: ValidationWizardStatus
    issue: ValidationIssue | None = None
    progress: ValidationWizardProgress | None = None
    summary: ValidationWizardSummary | None = None
    action_result: ReferenceActionResult | None = None
    setup_failure: ValidationWizardSetupFailure | None = None
    message: str = ""


def validation_setup_failed_step(title: str, message: str) -> ValidationWizardStep:
    """Return a terminal step for invalid setup/input before a scan is executed."""

    failure = ValidationWizardSetupFailure(title=title, message=message)
    return ValidationWizardStep(
        status=ValidationWizardStatus.SETUP_FAILED,
        setup_failure=failure,
        message=message,
    )


@dataclass(frozen=True)
class ValidationWizardActionRequest:
    """Payload submitted by the UI when the GM chooses an action."""

    action: ValidationWizardAction | str
    target: EntityRecord | dict[str, Any] | str | None = None
    created_entity: EntityRecord | dict[str, Any] | None = None
    attach_to_source: bool = True


class ValidationWizardPresenter(Protocol):
    """Optional UI callback contract used by the controller."""

    def show_issue(self, step: ValidationWizardStep) -> None:
        """Render the issue and wait for a subsequent GM action."""

    def show_summary(self, summary: ValidationWizardSummary) -> None:
        """Render the final summary."""


class ValidationWizardController:
    """Coordinate interactive validation fixes issue by issue.

    The controller takes an ordered issue list, skips anything ignored by the
    session store, exposes the first visible issue, then waits for the UI to call
    :meth:`submit_action`.  Successful mutating actions are delegated to
    ``ReferenceFixService`` and the controller advances to the next visible
    issue.  ``CREATE_ENTITY`` pauses the workflow so an entity editor can open;
    :meth:`resume_after_entity_creation` links the created entity and continues.
    """

    def __init__(
        self,
        issues: Iterable[ValidationIssue | ValidationWizardIssue],
        *,
        campaign: Mapping[str, Any],
        reference_fix_service: ReferenceFixService | None = None,
        ignore_store: SessionIgnoreStore | None = None,
        reference_resolver: ReferenceResolver | None = None,
        presenter: ValidationWizardPresenter | None = None,
        metrics: ValidationWizardMetrics | None = None,
        started_at: float | None = None,
    ) -> None:
        self._items = tuple(_coerce_issue_item(issue) for issue in issues)
        self._campaign = dict(campaign)
        self._reference_fix_service = reference_fix_service or ReferenceFixService()
        self._ignore_store = ignore_store or SessionIgnoreStore()
        self._reference_resolver = reference_resolver
        self._presenter = presenter
        self._started_at = started_at if started_at is not None else monotonic()
        self._cursor = -1
        self._summary = ValidationWizardSummary(
            total_issues=len(self._items),
            metrics=metrics or ValidationWizardMetrics(),
        )
        self._awaiting_entity_creation = False
        self._active_step: ValidationWizardStep | None = None

    @property
    def campaign(self) -> Mapping[str, Any]:
        """Return the explicit campaign selected for this validation run."""

        return dict(self._campaign)

    @property
    def summary(self) -> ValidationWizardSummary:
        """Return the current accumulated summary."""

        return self._summary

    @property
    def current_issue(self) -> ValidationIssue | None:
        """Return the currently displayed issue, if any."""

        return self._active_step.issue if self._active_step else None

    def can_attach_current_issue(
        self,
        target: EntityRecord | None = None,
    ) -> bool:
        """Return whether the current issue can attach an existing target."""

        current_item = self._current_item()
        if current_item is None:
            return False
        reference = self._resolve_reference(current_item)
        if reference is None:
            return False
        attach_target = target or current_item.target
        return self._reference_fix_service.can_attach_existing_entity(
            reference,
            attach_target,
        )

    def start(self) -> ValidationWizardStep:
        """Start the wizard at the first non-ignored issue."""

        self._cursor = -1
        self._awaiting_entity_creation = False
        return self._advance_to_next_issue()

    def submit_action(
        self,
        request: ValidationWizardActionRequest | ValidationWizardAction | str,
        *,
        target: EntityRecord | dict[str, Any] | str | None = None,
        created_entity: EntityRecord | dict[str, Any] | None = None,
        attach_to_source: bool = True,
    ) -> ValidationWizardStep:
        """Apply the GM action for the current issue and return the next step."""

        action_request = _coerce_action_request(
            request,
            target=target,
            created_entity=created_entity,
            attach_to_source=attach_to_source,
        )
        action = ValidationWizardAction(action_request.action)

        if action == ValidationWizardAction.CANCEL:
            return self.cancel()
        if self._awaiting_entity_creation:
            if action != ValidationWizardAction.LINK_CREATED:
                return self._action_failed(
                    ENTITY_CREATION_PENDING_MESSAGE
                )
            return self.resume_after_entity_creation(
                action_request.created_entity or action_request.target,
                attach_to_source=action_request.attach_to_source,
            )

        current_item = self._current_item()
        if current_item is None:
            return self._complete()

        if action == ValidationWizardAction.SKIP_SESSION:
            self._ignore_store.ignore(current_item.issue)
            self._summary = _summary_with_skip(
                self._summary,
                ISSUE_IGNORED_MESSAGE.format(
                    referenced_name=current_item.issue.payload.referenced_name
                ),
            )
            return self._advance_to_next_issue()

        if action == ValidationWizardAction.CREATE_ENTITY:
            self._awaiting_entity_creation = True
            step = ValidationWizardStep(
                status=ValidationWizardStatus.AWAITING_ENTITY_CREATION,
                issue=current_item.issue,
                progress=self._progress_for_cursor(),
                message=ENTITY_CREATION_REQUESTED_MESSAGE,
            )
            self._active_step = step
            return step

        reference = self._resolve_reference(current_item)
        if reference is None:
            return self._action_failed(
                REFERENCE_NOT_FOUND_ACTION_MESSAGE
            )

        if action == ValidationWizardAction.ATTACH:
            result = self._reference_fix_service.attach_existing_entity(
                reference,
                _attach_target_for_action(current_item, action_request.target),
            )
        elif action == ValidationWizardAction.REMAP:
            result = self._reference_fix_service.remap_reference(
                reference,
                action_request.target or "",
            )
        elif action == ValidationWizardAction.REMOVE:
            result = self._reference_fix_service.remove_reference(reference)
        elif action == ValidationWizardAction.LINK_CREATED:
            result = self._reference_fix_service.link_created_entity(
                reference,
                action_request.created_entity or action_request.target or {},
                attach_to_source=action_request.attach_to_source,
            )
        else:
            return self._action_failed(UNKNOWN_ACTION_MESSAGE.format(action=action.value))

        return self._handle_action_result(result)

    def resume_after_entity_creation(
        self,
        created_entity: EntityRecord | dict[str, Any] | str | None,
        *,
        attach_to_source: bool = True,
    ) -> ValidationWizardStep:
        """Resume a paused wizard after the entity creation UI returns."""

        current_item = self._current_item()
        if current_item is None:
            return self._complete()
        if created_entity is None:
            return self._action_failed(RESUME_NO_ENTITY_MESSAGE)

        reference = self._resolve_reference(current_item)
        if reference is None:
            return self._action_failed(
                REFERENCE_NOT_FOUND_RESUME_MESSAGE
            )

        result = self._reference_fix_service.link_created_entity(
            reference,
            created_entity,
            attach_to_source=attach_to_source,
        )
        if result.success:
            self._awaiting_entity_creation = False
        return self._handle_action_result(result)

    def cancel(self) -> ValidationWizardStep:
        """Cancel the wizard and return a final canceled summary."""

        self._awaiting_entity_creation = False
        self._summary = _summary_canceled(self._final_summary())
        step = ValidationWizardStep(
            status=ValidationWizardStatus.CANCELED,
            summary=self._summary,
            message=VALIDATION_CANCELED_MESSAGE,
        )
        self._active_step = step
        self._notify_summary(step)
        return step

    def _advance_to_next_issue(self) -> ValidationWizardStep:
        self._awaiting_entity_creation = False
        self._cursor += 1
        while self._cursor < len(self._items):
            item = self._items[self._cursor]
            if not self._ignore_store.is_ignored(item.issue):
                step = ValidationWizardStep(
                    status=ValidationWizardStatus.SHOW_ISSUE,
                    issue=item.issue,
                    progress=self._progress_for_cursor(),
                    message=_format_issue_message(item.issue),
                )
                self._active_step = step
                if self._presenter is not None:
                    self._presenter.show_issue(step)
                return step
            self._cursor += 1
        return self._complete()

    def _complete(self) -> ValidationWizardStep:
        step = ValidationWizardStep(
            status=ValidationWizardStatus.COMPLETED,
            summary=self._final_summary(),
            message=VALIDATION_COMPLETED_MESSAGE,
        )
        self._summary = step.summary or self._summary
        self._active_step = step
        self._notify_summary(step)
        return step

    def _final_summary(self) -> ValidationWizardSummary:
        elapsed = max(
            monotonic() - self._started_at,
            self._summary.metrics.elapsed_seconds,
        )
        return _summary_with_metrics(
            self._summary,
            ValidationWizardMetrics(
                entities_visited=self._summary.metrics.entities_visited,
                references_checked=self._summary.metrics.references_checked,
                elapsed_seconds=elapsed,
            ),
        )

    def _handle_action_result(self, result: ReferenceActionResult) -> ValidationWizardStep:
        if not result.success:
            return self._action_failed(result.ui_message, result)
        self._summary = _summary_with_result(self._summary, result)
        return self._advance_to_next_issue()

    def _action_failed(
        self,
        message: str,
        result: ReferenceActionResult | None = None,
    ) -> ValidationWizardStep:
        current_item = self._current_item()
        step = ValidationWizardStep(
            status=ValidationWizardStatus.ACTION_FAILED,
            issue=current_item.issue if current_item else None,
            progress=self._progress_for_cursor() if current_item else None,
            action_result=result,
            message=message,
        )
        self._active_step = step
        return step

    def _current_item(self) -> ValidationWizardIssue | None:
        if 0 <= self._cursor < len(self._items):
            return self._items[self._cursor]
        return None

    def _resolve_reference(self, item: ValidationWizardIssue) -> ReferenceRecord | None:
        if item.reference is not None:
            return item.reference
        if self._reference_resolver is None:
            return None
        return self._reference_resolver(item.issue)

    def _progress_for_cursor(self) -> ValidationWizardProgress:
        visible_indices = [
            index
            for index, item in enumerate(self._items)
            if not self._ignore_store.is_ignored(item.issue)
        ]
        current_index = (
            visible_indices.index(self._cursor) + 1
            if self._cursor in visible_indices
            else 0
        )
        return ValidationWizardProgress(
            current_index=current_index,
            visible_total=len(visible_indices),
            raw_total=len(self._items),
        )

    def _notify_summary(self, step: ValidationWizardStep) -> None:
        if self._presenter is not None and step.summary is not None:
            self._presenter.show_summary(step.summary)


def resolve_reference_for_issue(
    issue: ValidationIssue,
    references: Sequence[ReferenceRecord],
) -> ReferenceRecord | None:
    """Find the reference record matching a validation issue payload."""

    payload = issue.payload
    for reference in references:
        if (
            reference.source.identifier == payload.source_entity
            and reference.field_name == payload.field
            and reference.reference_value == payload.referenced_name
            and reference.expected_type == payload.expected_type
            and reference.path == tuple(payload.hierarchy_path)
        ):
            return reference
    return None


def resolve_target_for_issue(
    issue: ValidationIssue,
    entities: Sequence[EntityRecord],
) -> EntityRecord | None:
    """Find the target entity record matching an INVALID_HIERARCHY issue."""

    target_path = tuple(issue.payload.target_path)
    if not target_path:
        return None
    for entity in entities:
        if entity.path == target_path:
            return entity
    return None


def _coerce_issue_item(issue: ValidationIssue | ValidationWizardIssue) -> ValidationWizardIssue:
    if isinstance(issue, ValidationWizardIssue):
        return issue
    return ValidationWizardIssue(issue=issue)


def _coerce_action_request(
    request: ValidationWizardActionRequest | ValidationWizardAction | str,
    *,
    target: EntityRecord | dict[str, Any] | str | None,
    created_entity: EntityRecord | dict[str, Any] | None,
    attach_to_source: bool,
) -> ValidationWizardActionRequest:
    if isinstance(request, ValidationWizardActionRequest):
        return request
    return ValidationWizardActionRequest(
        action=request,
        target=target,
        created_entity=created_entity,
        attach_to_source=attach_to_source,
    )


def _attach_target_for_action(
    current_item: ValidationWizardIssue,
    target: EntityRecord | dict[str, Any] | str | None,
) -> EntityRecord | None:
    if isinstance(target, EntityRecord):
        return target
    return current_item.target


def _summary_with_metrics(
    summary: ValidationWizardSummary,
    metrics: ValidationWizardMetrics,
) -> ValidationWizardSummary:
    return ValidationWizardSummary(
        total_issues=summary.total_issues,
        resolved=summary.resolved,
        skipped_session=summary.skipped_session,
        canceled=summary.canceled,
        metrics=metrics,
        changes_applied=summary.changes_applied,
        messages=summary.messages,
    )


def _summary_with_result(
    summary: ValidationWizardSummary,
    result: ReferenceActionResult,
) -> ValidationWizardSummary:
    return ValidationWizardSummary(
        total_issues=summary.total_issues,
        resolved=summary.resolved + 1,
        skipped_session=summary.skipped_session,
        canceled=summary.canceled,
        metrics=summary.metrics,
        changes_applied=summary.changes_applied + result.changes_applied,
        messages=summary.messages + ((result.ui_message,) if result.ui_message else ()),
    )


def _summary_with_skip(summary: ValidationWizardSummary, message: str) -> ValidationWizardSummary:
    return ValidationWizardSummary(
        total_issues=summary.total_issues,
        resolved=summary.resolved,
        skipped_session=summary.skipped_session + 1,
        canceled=summary.canceled,
        metrics=summary.metrics,
        changes_applied=summary.changes_applied,
        messages=summary.messages + (message,),
    )


def _summary_canceled(summary: ValidationWizardSummary) -> ValidationWizardSummary:
    return ValidationWizardSummary(
        total_issues=summary.total_issues,
        resolved=summary.resolved,
        skipped_session=summary.skipped_session,
        canceled=True,
        metrics=summary.metrics,
        changes_applied=summary.changes_applied,
        messages=summary.messages + (VALIDATION_CANCELED_MESSAGE,),
    )


def _format_issue_message(issue: ValidationIssue) -> str:
    if issue.issue_type == IssueType.INVALID_HIERARCHY:
        return safe_display_text(
            format_hierarchy_issue_message(issue),
            max_chars=LONGFORM_DISPLAY_LIMIT,
        )

    payload = issue.payload
    return safe_display_text(
        ISSUE_REFERENCE_MESSAGE.format(
            issue_type=issue.issue_type.value,
            source_entity=safe_display_text(
                payload.source_entity,
                max_chars=LABEL_DISPLAY_LIMIT,
            ),
            field=safe_display_text(payload.field, max_chars=LABEL_DISPLAY_LIMIT),
            referenced_name=safe_display_text(
                payload.referenced_name,
                max_chars=LABEL_DISPLAY_LIMIT,
            ),
            expected_type=safe_display_text(
                payload.expected_type,
                max_chars=LABEL_DISPLAY_LIMIT,
            ),
        ),
        max_chars=LONGFORM_DISPLAY_LIMIT,
    )
