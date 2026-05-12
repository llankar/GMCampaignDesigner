"""Dialog for resolving one invalid-hierarchy validation issue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from modules.helpers.tk_text_safety import LONGFORM_DISPLAY_LIMIT, safe_display_text
from src.ui.validation.labels import (
    ATTACH_LABEL,
    IGNORE_LABEL,
    INVALID_HIERARCHY_ATTACH_REMAP_RESOLUTION_MESSAGE,
    INVALID_HIERARCHY_ATTACH_RESOLUTION_MESSAGE,
    INVALID_HIERARCHY_RESOLUTION_MESSAGE,
    INVALID_HIERARCHY_REMAP_RESOLUTION_MESSAGE,
    INVALID_HIERARCHY_RESOLUTION_TITLE,
    NO_HIERARCHY_REMAP_TARGET_SELECTOR_MESSAGE,
    REMAP_LABEL,
    REMAPPING_UNAVAILABLE_TITLE,
    REMOVE_LABEL,
    STOP_VALIDATION_LABEL,
)
from src.ui.validation.validation_wizard_controller import (
    ValidationWizardAction,
    ValidationWizardActionRequest,
    ValidationWizardController,
    ValidationWizardStep,
)
from src.validation import IssueType, ValidationIssue
from src.validation.reference_validator import EntityRecord, ReferenceRecord

HierarchyRemapTarget = EntityRecord | dict[str, Any] | str
HierarchyRemapTargetProvider = Callable[[ValidationIssue], HierarchyRemapTarget | None]
StepCallback = Callable[[ValidationWizardStep], None]
ErrorCallback = Callable[[str], None]


class DialogWindow(Protocol):
    """Tiny window contract used to keep callbacks testable."""

    def destroy(self) -> None:
        """Close the dialog."""


@dataclass(frozen=True)
class InvalidHierarchyDialogConfig:
    """Dependencies and callbacks for :class:`InvalidHierarchyDialog`."""

    remap_target_provider: HierarchyRemapTargetProvider | None = None
    on_step: StepCallback | None = None
    on_error: ErrorCallback | None = None


class InvalidHierarchyDialog:
    """Resolve an invalid hierarchy reference with supported wizard actions."""

    def __init__(
        self,
        master: Any,
        controller: ValidationWizardController,
        step: ValidationWizardStep,
        *,
        reference: ReferenceRecord | None = None,
        target: EntityRecord | None = None,
        config: InvalidHierarchyDialogConfig | None = None,
    ) -> None:
        if step.issue is None:
            raise ValueError("InvalidHierarchyDialog requires a validation issue")
        if step.issue.issue_type != IssueType.INVALID_HIERARCHY:
            raise ValueError(
                "InvalidHierarchyDialog only handles invalid hierarchy issues"
            )

        self.master = master
        self.controller = controller
        self.step = step
        self.issue = step.issue
        self.reference = reference
        self.target = target
        self.config = config or InvalidHierarchyDialogConfig()
        self.window: DialogWindow | None = None
        self.last_step: ValidationWizardStep | None = None

    @property
    def available_action_labels(self) -> tuple[str, ...]:
        """Return the labels for actions that this dialog can actually submit."""

        return tuple(label for label, _command in self._action_buttons())

    def show(self) -> "InvalidHierarchyDialog":
        """Create and display the CustomTkinter dialog window."""

        import customtkinter as ctk

        window = ctk.CTkToplevel(self.master)
        self.window = window
        window.title(INVALID_HIERARCHY_RESOLUTION_TITLE)
        window.transient(self.master)
        window.grab_set()
        window.geometry("680x360")
        window.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            window,
            text=INVALID_HIERARCHY_RESOLUTION_TITLE,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))
        ctk.CTkLabel(
            window,
            text=self._message_text(),
            wraplength=620,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 16))

        actions = ctk.CTkFrame(window)
        actions.grid(row=2, column=0, sticky="ew", padx=20, pady=(8, 20))
        action_buttons = self._action_buttons()
        for index in range(len(action_buttons)):
            actions.grid_columnconfigure(index, weight=1)

        for index, (label, command) in enumerate(action_buttons):
            ctk.CTkButton(actions, text=label, command=command).grid(
                row=0, column=index, sticky="ew", padx=4, pady=4
            )
        return self

    def attach(self) -> ValidationWizardStep:
        """Attach the existing target under the invalid reference source."""

        return self._submit(
            ValidationWizardActionRequest(
                ValidationWizardAction.ATTACH,
                target=self.target,
            )
        )

    def remap(self) -> ValidationWizardStep | None:
        """Ask the host for a target and remap the invalid hierarchy reference."""

        if self.config.remap_target_provider is None:
            self._publish_error(NO_HIERARCHY_REMAP_TARGET_SELECTOR_MESSAGE)
            return None

        target = self.config.remap_target_provider(self.issue)
        if target is None:
            return None
        return self._submit(
            ValidationWizardActionRequest(ValidationWizardAction.REMAP, target=target)
        )

    def remove_reference(self) -> ValidationWizardStep:
        """Remove the invalid reference from its source field."""

        return self._submit(ValidationWizardAction.REMOVE)

    def ignore(self) -> ValidationWizardStep:
        """Ignore the invalid hierarchy issue for the current validation session."""

        return self._submit(ValidationWizardAction.SKIP_SESSION)

    def stop_validation(self) -> ValidationWizardStep:
        """Stop validation explicitly from the resolution dialog."""

        return self._submit(ValidationWizardAction.CANCEL)

    def close(self) -> None:
        """Close the dialog window without submitting a controller action."""

        if self.window is not None:
            self.window.destroy()
            self.window = None

    def _message_text(self) -> str:
        hint = safe_display_text(
            self.issue.payload.resolution_hint,
            max_chars=LONGFORM_DISPLAY_LIMIT,
        ).strip()
        resolution_message = self._resolution_message()
        parts = [
            safe_display_text(self.step.message, max_chars=LONGFORM_DISPLAY_LIMIT),
            resolution_message,
        ]
        if hint:
            parts.append(hint)
        return safe_display_text(
            "\n\n".join(part for part in parts if part),
            max_chars=LONGFORM_DISPLAY_LIMIT,
        )

    def _action_buttons(self) -> tuple[tuple[str, Callable[[], Any]], ...]:
        buttons: list[tuple[str, Callable[[], Any]]] = []
        if self._can_attach():
            buttons.append((ATTACH_LABEL, self.attach))
        if self._can_remap():
            buttons.append((REMAP_LABEL, self.remap))
        buttons.extend(
            (
                (REMOVE_LABEL, self.remove_reference),
                (IGNORE_LABEL, self.ignore),
                (STOP_VALIDATION_LABEL, self.stop_validation),
            )
        )
        return tuple(buttons)

    def _resolution_message(self) -> str:
        can_attach = self._can_attach()
        can_remap = self._can_remap()
        if can_attach and can_remap:
            return INVALID_HIERARCHY_ATTACH_REMAP_RESOLUTION_MESSAGE
        if can_attach:
            return INVALID_HIERARCHY_ATTACH_RESOLUTION_MESSAGE
        if can_remap:
            return INVALID_HIERARCHY_REMAP_RESOLUTION_MESSAGE
        return INVALID_HIERARCHY_RESOLUTION_MESSAGE

    def _can_attach(self) -> bool:
        return self.controller.can_attach_current_issue(self.target)

    def _can_remap(self) -> bool:
        return self.config.remap_target_provider is not None

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
        self.close()
        return step

    def _publish_error(self, message: str) -> None:
        if self.config.on_error is not None:
            self.config.on_error(message)
            return

        from tkinter import messagebox

        messagebox.showwarning(REMAPPING_UNAVAILABLE_TITLE, message)


def open_invalid_hierarchy_dialog(
    master: Any,
    controller: ValidationWizardController,
    step: ValidationWizardStep,
    *,
    reference: ReferenceRecord | None = None,
    target: EntityRecord | None = None,
    config: InvalidHierarchyDialogConfig | None = None,
) -> InvalidHierarchyDialog:
    """Open a dialog for a wizard step carrying an invalid-hierarchy issue."""

    return InvalidHierarchyDialog(
        master,
        controller,
        step,
        reference=reference,
        target=target,
        config=config,
    ).show()
