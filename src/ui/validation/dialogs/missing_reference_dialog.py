"""Dialog for resolving one missing-reference validation issue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from src.ui.validation.labels import (
    CREATE_LABEL,
    IGNORE_LABEL,
    MISSING_REFERENCE_MESSAGE,
    MISSING_REFERENCE_TITLE,
    NO_REMAP_TARGET_SELECTOR_MESSAGE,
    REMAP_LABEL,
    REMAPPING_UNAVAILABLE_TITLE,
    REMOVE_LABEL,
)
from src.ui.validation.validation_wizard_controller import (
    ValidationWizardAction,
    ValidationWizardActionRequest,
    ValidationWizardController,
    ValidationWizardStep,
)
from src.validation import IssueType, ValidationIssue
from src.validation.reference_validator import EntityRecord, ReferenceRecord

from .generic_editor_launcher import (
    GenericEditorLauncher,
    creation_request_from_issue,
)

RemapTarget = EntityRecord | dict[str, Any] | str
RemapTargetProvider = Callable[[ValidationIssue], RemapTarget | None]
StepCallback = Callable[[ValidationWizardStep], None]
ErrorCallback = Callable[[str], None]


class DialogWindow(Protocol):
    """Tiny window contract used to keep callbacks testable."""

    def destroy(self) -> None:
        """Close the dialog."""


@dataclass(frozen=True)
class MissingReferenceDialogConfig:
    """Dependencies and callbacks for :class:`MissingReferenceDialog`."""

    generic_editor_launcher: GenericEditorLauncher | None = None
    remap_target_provider: RemapTargetProvider | None = None
    on_step: StepCallback | None = None
    on_error: ErrorCallback | None = None


class MissingReferenceDialog:
    """Resolve a missing reference with create, remap, remove, or ignore actions.

    The dialog delegates mutations to ``ValidationWizardController``.  The
    ``Create`` action opens the Generic Editor for the issue expected type with
    the referenced value pre-filled as the entity name.  When the editor saves,
    the created entity is returned to the controller so it can auto-link the
    original reference.
    """

    def __init__(
        self,
        master: Any,
        controller: ValidationWizardController,
        issue: ValidationIssue,
        *,
        reference: ReferenceRecord | None = None,
        config: MissingReferenceDialogConfig | None = None,
    ) -> None:
        if issue.issue_type != IssueType.MISSING_REFERENCE:
            raise ValueError("MissingReferenceDialog only handles missing references")

        self.master = master
        self.controller = controller
        self.issue = issue
        self.reference = reference
        self.config = config or MissingReferenceDialogConfig()
        self.generic_editor_launcher = (
            self.config.generic_editor_launcher or GenericEditorLauncher()
        )
        self.window: DialogWindow | None = None
        self.last_step: ValidationWizardStep | None = None
        self.last_created_entity: dict[str, Any] | None = None

    def show(self) -> "MissingReferenceDialog":
        """Create and display the CustomTkinter dialog window."""

        import customtkinter as ctk

        window = ctk.CTkToplevel(self.master)
        self.window = window
        window.title(MISSING_REFERENCE_TITLE)
        window.transient(self.master)
        window.grab_set()
        window.geometry("560x320")
        window.grid_columnconfigure(0, weight=1)

        payload = self.issue.payload
        ctk.CTkLabel(
            window,
            text=MISSING_REFERENCE_TITLE,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(
            window,
            text=MISSING_REFERENCE_MESSAGE.format(
                referenced_name=payload.referenced_name,
                expected_type=payload.expected_type,
                source_entity=payload.source_entity,
            ),
            wraplength=500,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 16))

        actions = ctk.CTkFrame(window)
        actions.grid(row=2, column=0, sticky="ew", padx=20, pady=8)
        for index in range(4):
            actions.grid_columnconfigure(index, weight=1)

        ctk.CTkButton(
            actions, text=CREATE_LABEL, command=self.create_via_generic_editor
        ).grid(
            row=0, column=0, sticky="ew", padx=4, pady=4
        )
        ctk.CTkButton(actions, text=REMAP_LABEL, command=self.remap).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4
        )
        ctk.CTkButton(actions, text=REMOVE_LABEL, command=self.remove_reference).grid(
            row=0, column=2, sticky="ew", padx=4, pady=4
        )
        ctk.CTkButton(actions, text=IGNORE_LABEL, command=self.ignore).grid(
            row=0, column=3, sticky="ew", padx=4, pady=4
        )
        return self

    def create_via_generic_editor(self) -> ValidationWizardStep | None:
        """Open Generic Editor and auto-link the saved entity through controller."""

        paused_step = self._submit(ValidationWizardAction.CREATE_ENTITY, close=False)
        request = creation_request_from_issue(self.issue, self.reference)
        result = self.generic_editor_launcher.create_entity(self.master, request)
        if result is None:
            return paused_step

        self.last_created_entity = result.entity
        linked_step = self.controller.resume_after_entity_creation(result.entity)
        return self._publish_step(linked_step, close=True)

    def remap(self) -> ValidationWizardStep | None:
        """Ask the host for a target and remap the missing reference to it."""

        if self.config.remap_target_provider is None:
            self._publish_error(NO_REMAP_TARGET_SELECTOR_MESSAGE)
            return None

        target = self.config.remap_target_provider(self.issue)
        if target is None:
            return None
        return self._submit(
            ValidationWizardActionRequest(ValidationWizardAction.REMAP, target=target)
        )

    def remove_reference(self) -> ValidationWizardStep:
        """Remove the missing reference from its source."""

        return self._submit(ValidationWizardAction.REMOVE)

    def ignore(self) -> ValidationWizardStep:
        """Ignore the missing reference for the current validation session."""

        return self._submit(ValidationWizardAction.SKIP_SESSION)

    def _submit(
        self,
        request: ValidationWizardActionRequest | ValidationWizardAction,
        *,
        close: bool = True,
    ) -> ValidationWizardStep:
        step = self.controller.submit_action(request)
        return self._publish_step(step, close=close)

    def _publish_step(
        self,
        step: ValidationWizardStep,
        *,
        close: bool,
    ) -> ValidationWizardStep:
        self.last_step = step
        if self.config.on_step is not None:
            self.config.on_step(step)
        if close:
            self.close()
        return step

    def _publish_error(self, message: str) -> None:
        if self.config.on_error is not None:
            self.config.on_error(message)
            return

        from tkinter import messagebox

        messagebox.showwarning(REMAPPING_UNAVAILABLE_TITLE, message)

    def close(self) -> None:
        """Close the dialog window if it has been displayed."""

        if self.window is not None:
            self.window.destroy()
            self.window = None


def open_missing_reference_dialog(
    master: Any,
    controller: ValidationWizardController,
    step: ValidationWizardStep,
    *,
    reference: ReferenceRecord | None = None,
    config: MissingReferenceDialogConfig | None = None,
) -> MissingReferenceDialog:
    """Open a dialog for a wizard step carrying a missing-reference issue."""

    if step.issue is None:
        raise ValueError("Cannot open a missing-reference dialog without an issue")
    return MissingReferenceDialog(
        master,
        controller,
        step.issue,
        reference=reference,
        config=config,
    ).show()
