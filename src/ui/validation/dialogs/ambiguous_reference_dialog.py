"""Dialog for resolving an ambiguous-reference validation issue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from src.ui.validation.labels import (
    AMBIGUOUS_REFERENCE_MESSAGE,
    AMBIGUOUS_REFERENCE_TITLE,
    CANDIDATE_UNAVAILABLE_MESSAGE,
    CHOOSE_LEFT_LABEL,
    CHOOSE_RIGHT_LABEL,
    IGNORE_LABEL,
    NO_KEY_INFO_MESSAGE,
    NO_OTHER_CANDIDATE_SELECTOR_MESSAGE,
    PATH_LABEL,
    TAGS_LABEL,
    TYPE_LABEL,
    VIEW_OTHER_CANDIDATES_LABEL,
)
from src.ui.validation.validation_wizard_controller import (
    ValidationWizardAction,
    ValidationWizardActionRequest,
    ValidationWizardController,
    ValidationWizardStep,
)
from src.validation import IssueType, ValidationIssue
from src.validation.reference_validator import EntityRecord

CandidateInput = EntityRecord | Mapping[str, Any] | str
CandidateProvider = Callable[[ValidationIssue], Sequence[CandidateInput]]
StepCallback = Callable[[ValidationWizardStep], None]
ErrorCallback = Callable[[str], None]
OtherCandidatesCallback = Callable[
    [ValidationIssue, Sequence["AmbiguousReferenceCandidate"]], None
]


class DialogWindow(Protocol):
    """Tiny window contract used to keep callbacks testable."""

    def destroy(self) -> None:
        """Close the dialog."""


@dataclass(frozen=True)
class AmbiguousReferenceCandidate:
    """Display + remap data for one ambiguous target candidate."""

    identifier: str
    name: str
    entity_type: str
    hierarchy_path: tuple[str, ...] = ()
    description: str = ""
    tags: tuple[str, ...] = ()
    target: CandidateInput | None = None

    @property
    def display_name(self) -> str:
        """Return the user-facing name, falling back to the identifier."""

        return self.name or self.identifier

    @property
    def display_path(self) -> str:
        """Return a compact hierarchical path for the candidate card."""

        return " › ".join(self.hierarchy_path) if self.hierarchy_path else "—"

    @property
    def key_infos(self) -> tuple[str, ...]:
        """Return description/tags lines available for the candidate."""

        infos: list[str] = []
        if self.description:
            infos.append(self.description)
        if self.tags:
            infos.append(f"{TAGS_LABEL}: {', '.join(self.tags)}")
        return tuple(infos)

    @property
    def remap_target(self) -> str:
        """Return the chosen identifier sent to the controller for remapping."""

        return self.identifier


@dataclass(frozen=True)
class AmbiguousReferenceDialogConfig:
    """Dependencies and callbacks for :class:`AmbiguousReferenceDialog`."""

    candidates: Sequence[CandidateInput] = ()
    candidate_provider: CandidateProvider | None = None
    on_show_other_candidates: OtherCandidatesCallback | None = None
    on_step: StepCallback | None = None
    on_error: ErrorCallback | None = None


class AmbiguousReferenceDialog:
    """Resolve an ambiguous reference by choosing one of two candidates.

    The dialog shows the first two candidates side by side and delegates the
    selected candidate to ``ValidationWizardController`` with a REMAP action so
    the reference is rewritten immediately.
    """

    def __init__(
        self,
        master: Any,
        controller: ValidationWizardController,
        issue: ValidationIssue,
        *,
        config: AmbiguousReferenceDialogConfig | None = None,
    ) -> None:
        if issue.issue_type != IssueType.AMBIGUOUS_REFERENCE:
            raise ValueError("AmbiguousReferenceDialog only handles ambiguous references")

        self.master = master
        self.controller = controller
        self.issue = issue
        self.config = config or AmbiguousReferenceDialogConfig()
        self.window: DialogWindow | None = None
        self.last_step: ValidationWizardStep | None = None
        self.selected_identifier: str | None = None
        self._candidates = tuple(
            _candidate_from_input(candidate)
            for candidate in self._candidate_inputs()
        )

    @property
    def candidates(self) -> tuple[AmbiguousReferenceCandidate, ...]:
        """Return normalized candidates available to the dialog."""

        return self._candidates

    @property
    def displayed_candidates(self) -> tuple[AmbiguousReferenceCandidate, ...]:
        """Return the two candidates rendered side by side."""

        return self._candidates[:2]

    def show(self) -> "AmbiguousReferenceDialog":
        """Create and display the CustomTkinter dialog window."""

        import customtkinter as ctk

        window = ctk.CTkToplevel(self.master)
        self.window = window
        window.title(AMBIGUOUS_REFERENCE_TITLE)
        window.transient(self.master)
        window.grab_set()
        window.geometry("760x460")
        window.grid_columnconfigure(0, weight=1)

        payload = self.issue.payload
        ctk.CTkLabel(
            window,
            text=AMBIGUOUS_REFERENCE_TITLE,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(
            window,
            text=AMBIGUOUS_REFERENCE_MESSAGE.format(
                referenced_name=payload.referenced_name,
                expected_type=payload.expected_type,
            ),
            wraplength=700,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 16))

        cards = ctk.CTkFrame(window)
        cards.grid(row=2, column=0, sticky="nsew", padx=20, pady=8)
        cards.grid_columnconfigure(0, weight=1)
        cards.grid_columnconfigure(1, weight=1)
        for index, candidate in enumerate(self.displayed_candidates):
            self._render_candidate_card(ctk, cards, candidate, index)

        actions = ctk.CTkFrame(window)
        actions.grid(row=3, column=0, sticky="ew", padx=20, pady=(12, 20))
        for index in range(4):
            actions.grid_columnconfigure(index, weight=1)

        ctk.CTkButton(actions, text=CHOOSE_LEFT_LABEL, command=self.choose_left).grid(
            row=0, column=0, sticky="ew", padx=4, pady=4
        )
        ctk.CTkButton(actions, text=CHOOSE_RIGHT_LABEL, command=self.choose_right).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4
        )
        ctk.CTkButton(
            actions,
            text=VIEW_OTHER_CANDIDATES_LABEL,
            command=self.show_other_candidates,
        ).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        ctk.CTkButton(actions, text=IGNORE_LABEL, command=self.ignore).grid(
            row=0, column=3, sticky="ew", padx=4, pady=4
        )
        return self

    def choose_left(self) -> ValidationWizardStep | None:
        """Choose the left candidate and remap immediately."""

        return self.choose_candidate(0)

    def choose_right(self) -> ValidationWizardStep | None:
        """Choose the right candidate and remap immediately."""

        return self.choose_candidate(1)

    def choose_candidate(self, index: int) -> ValidationWizardStep | None:
        """Submit the selected candidate identifier to the controller."""

        if index < 0 or index >= len(self.displayed_candidates):
            self._publish_error(CANDIDATE_UNAVAILABLE_MESSAGE)
            return None

        candidate = self.displayed_candidates[index]
        self.selected_identifier = candidate.identifier
        return self._submit(
            ValidationWizardActionRequest(
                ValidationWizardAction.REMAP,
                target=candidate.remap_target,
            )
        )

    def show_other_candidates(self) -> None:
        """Notify the host that a broader candidate picker should be shown."""

        if self.config.on_show_other_candidates is None:
            self._publish_error(NO_OTHER_CANDIDATE_SELECTOR_MESSAGE)
            return
        self.config.on_show_other_candidates(self.issue, self.candidates)

    def ignore(self) -> ValidationWizardStep:
        """Ignore the ambiguous reference for this session."""

        return self._submit(ValidationWizardAction.SKIP_SESSION)

    def _candidate_inputs(self) -> Sequence[CandidateInput]:
        if self.config.candidate_provider is not None:
            candidates = self.config.candidate_provider(self.issue)
        else:
            candidates = self.config.candidates
        if candidates:
            return candidates
        return tuple(self.issue.payload.candidates)

    def _render_candidate_card(
        self,
        ctk: Any,
        parent: Any,
        candidate: AmbiguousReferenceCandidate,
        column: int,
    ) -> None:
        card = ctk.CTkFrame(parent)
        card.grid(row=0, column=column, sticky="nsew", padx=6, pady=6)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text=candidate.display_name,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        ctk.CTkLabel(card, text=f"{TYPE_LABEL}: {candidate.entity_type or '—'}", anchor="w").grid(
            row=1, column=0, sticky="ew", padx=12, pady=2
        )
        ctk.CTkLabel(
            card,
            text=f"{PATH_LABEL}: {candidate.display_path}",
            wraplength=320,
            justify="left",
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=2)
        infos = candidate.key_infos or (NO_KEY_INFO_MESSAGE,)
        ctk.CTkLabel(
            card,
            text="\n".join(infos),
            wraplength=320,
            justify="left",
            anchor="w",
        ).grid(row=3, column=0, sticky="ew", padx=12, pady=(8, 12))

    def _submit(
        self,
        request: ValidationWizardActionRequest | ValidationWizardAction,
    ) -> ValidationWizardStep:
        step = self.controller.submit_action(request)
        return self._publish_step(step)

    def _publish_step(self, step: ValidationWizardStep) -> ValidationWizardStep:
        self.last_step = step
        if self.config.on_step is not None:
            self.config.on_step(step)
        if self.window is not None:
            self.window.destroy()
            self.window = None
        return step

    def _publish_error(self, message: str) -> None:
        if self.config.on_error is not None:
            self.config.on_error(message)


def open_ambiguous_reference_dialog(
    master: Any,
    controller: ValidationWizardController,
    issue: ValidationIssue,
    *,
    config: AmbiguousReferenceDialogConfig | None = None,
) -> AmbiguousReferenceDialog:
    """Construct and show an ambiguous-reference dialog."""

    return AmbiguousReferenceDialog(master, controller, issue, config=config).show()


def _candidate_from_input(candidate: CandidateInput) -> AmbiguousReferenceCandidate:
    if isinstance(candidate, AmbiguousReferenceCandidate):
        return candidate
    if isinstance(candidate, EntityRecord):
        return AmbiguousReferenceCandidate(
            identifier=candidate.identifier,
            name=candidate.label,
            entity_type=candidate.entity_type,
            hierarchy_path=candidate.path,
            description=_read_mapping_text(candidate.node, ("description", "Description")),
            tags=_coerce_tags(_read_mapping_value(candidate.node, ("tags", "Tags"))),
            target=candidate,
        )
    if isinstance(candidate, Mapping):
        identifier = _first_text(candidate, ("id", "uuid", "slug", "key", "identifier"))
        name = _first_text(candidate, ("name", "Name", "title", "Title", "label", "Label"))
        entity_type = _first_text(candidate, ("entity_type", "type", "kind", "category"))
        return AmbiguousReferenceCandidate(
            identifier=identifier or name,
            name=name or identifier,
            entity_type=entity_type,
            hierarchy_path=_coerce_path(
                _read_mapping_value(candidate, ("path", "hierarchy_path", "target_path"))
            ),
            description=_read_mapping_text(candidate, ("description", "Description")),
            tags=_coerce_tags(_read_mapping_value(candidate, ("tags", "Tags"))),
            target=candidate,
        )
    return _candidate_from_string(candidate)


def _candidate_from_string(candidate: str) -> AmbiguousReferenceCandidate:
    value = str(candidate).strip()
    typed_part, _, path_part = value.partition("@")
    entity_type, separator, identifier = typed_part.partition(":")
    if not separator:
        entity_type = ""
        identifier = typed_part
    path = tuple(part.strip() for part in path_part.split(">") if part.strip())
    return AmbiguousReferenceCandidate(
        identifier=identifier.strip(),
        name=identifier.strip(),
        entity_type=entity_type.strip(),
        hierarchy_path=path,
        target=identifier.strip(),
    )


def _first_text(candidate: Mapping[str, Any], keys: Sequence[str]) -> str:
    return str(_read_mapping_value(candidate, keys) or "").strip()


def _read_mapping_text(candidate: Mapping[str, Any], keys: Sequence[str]) -> str:
    return str(_read_mapping_value(candidate, keys) or "").strip()


def _read_mapping_value(candidate: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in candidate:
            return candidate[key]
    return None


def _coerce_path(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        separator = "›" if "›" in value else ">"
        return tuple(part.strip() for part in value.split(separator) if part.strip())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return (str(value).strip(),)


def _coerce_tags(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(tag.strip() for tag in value.split(",") if tag.strip())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(str(tag).strip() for tag in value if str(tag).strip())
    return (str(value).strip(),)
