"""UI entry point for campaign hierarchy validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from modules.helpers.logging_helper import log_exception, log_info
from src.ui.validation.dialogs.ambiguous_reference_dialog import (
    AmbiguousReferenceDialogConfig,
    open_ambiguous_reference_dialog,
)
from src.ui.validation.dialogs.missing_reference_dialog import (
    MissingReferenceDialogConfig,
    open_missing_reference_dialog,
)
from src.ui.validation.dialogs.validation_summary_dialog import open_validation_summary_dialog
from src.ui.validation.validation_wizard_controller import (
    ValidationWizardAction,
    ValidationWizardController,
    ValidationWizardIssue,
    ValidationWizardStatus,
    ValidationWizardStep,
    resolve_reference_for_issue,
)
from src.validation import IssueType, ReferenceValidationResult, validate_reference_graph


@dataclass(frozen=True)
class CampaignValidationRun:
    """Objects created for one campaign validation launch."""

    graph: ReferenceValidationResult
    controller: ValidationWizardController
    first_step: ValidationWizardStep


class CampaignHierarchyValidationLauncher:
    """Instantiate the hierarchy validator and drive the validation wizard UI."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self._active_run: CampaignValidationRun | None = None

    @property
    def active_run(self) -> CampaignValidationRun | None:
        """Return the most recent validation run, if any."""

        return self._active_run

    def launch(self) -> CampaignValidationRun | None:
        """Validate the current campaign hierarchy and start the wizard controller."""

        try:
            hierarchy = build_campaign_validation_hierarchy(
                getattr(self.app, "entity_wrappers", {}) or {}
            )
            graph = validate_reference_graph(hierarchy)
            controller = ValidationWizardController(
                _wizard_items(graph),
                reference_resolver=lambda issue: resolve_reference_for_issue(issue, graph.references),
            )
            first_step = controller.start()
            run = CampaignValidationRun(graph=graph, controller=controller, first_step=first_step)
            self._active_run = run
            self._handle_step(run, first_step)
            return run
        except Exception as exc:
            log_exception(
                f"Failed to run hierarchy validation: {exc}",
                func_name="src.ui.validation.campaign_validation_launcher.CampaignHierarchyValidationLauncher.launch",
            )
            from tkinter import messagebox

            messagebox.showerror(
                "Validation indisponible",
                f"Impossible de vérifier la cohérence hiérarchique :\n{exc}",
            )
            return None

    def _handle_step(self, run: CampaignValidationRun, step: ValidationWizardStep) -> None:
        if step.status in {ValidationWizardStatus.COMPLETED, ValidationWizardStatus.CANCELED}:
            if step.summary is not None:
                open_validation_summary_dialog(self.app, step.summary)
            return

        if step.status == ValidationWizardStatus.ACTION_FAILED:
            from tkinter import messagebox

            messagebox.showwarning("Validation", step.message)
            return

        if step.issue is None:
            return

        if step.issue.issue_type == IssueType.MISSING_REFERENCE:
            open_missing_reference_dialog(
                self.app,
                run.controller,
                step,
                reference=resolve_reference_for_issue(step.issue, run.graph.references),
                config=MissingReferenceDialogConfig(
                    on_step=lambda next_step: self._handle_step(run, next_step)
                ),
            )
            return

        if step.issue.issue_type == IssueType.AMBIGUOUS_REFERENCE:
            open_ambiguous_reference_dialog(
                self.app,
                run.controller,
                step.issue,
                config=AmbiguousReferenceDialogConfig(
                    on_step=lambda next_step: self._handle_step(run, next_step)
                ),
            )
            return

        from tkinter import messagebox

        if messagebox.askyesno(
            "Cohérence hiérarchique",
            f"{step.message}\n\nIgnorer cette anomalie pour cette session ?",
        ):
            next_step = run.controller.submit_action(ValidationWizardAction.SKIP_SESSION)
            self._handle_step(run, next_step)


def build_campaign_validation_hierarchy(entity_wrappers: Mapping[str, Any]) -> dict[str, Any]:
    """Build a validator-friendly hierarchy from the app's model wrappers."""

    root: dict[str, Any] = {
        "type": "campaign",
        "id": "current-campaign",
        "name": "Current Campaign",
        "entities": [],
    }
    entities = root["entities"]

    for slug in sorted(entity_wrappers):
        wrapper = entity_wrappers[slug]
        for index, item in enumerate(_safe_load_items(wrapper)):
            if not isinstance(item, Mapping):
                continue
            entities.append(_normalize_entity_node(slug, item, index))

    log_info(
        f"Built validation hierarchy with {len(entities)} entities",
        func_name="src.ui.validation.campaign_validation_launcher.build_campaign_validation_hierarchy",
    )
    return root


def _wizard_items(graph: ReferenceValidationResult) -> tuple[ValidationWizardIssue, ...]:
    return tuple(
        ValidationWizardIssue(
            issue=issue,
            reference=resolve_reference_for_issue(issue, graph.references),
        )
        for issue in graph.issues
    )


def _safe_load_items(wrapper: Any) -> Sequence[Any]:
    try:
        items = wrapper.load_items()
    except Exception as exc:
        log_exception(
            f"Unable to load items for validation from {getattr(wrapper, 'entity_type', '?')}: {exc}",
            func_name="src.ui.validation.campaign_validation_launcher._safe_load_items",
        )
        return ()
    return items if isinstance(items, Sequence) and not isinstance(items, (str, bytes, bytearray)) else ()


def _normalize_entity_node(slug: str, item: Mapping[str, Any], index: int) -> dict[str, Any]:
    node = dict(item)
    entity_type = _singular_entity_type(slug)
    identifier = _identifier_for(node, slug, index)
    node.setdefault("type", entity_type)
    node.setdefault("entity_type", entity_type)
    node.setdefault("id", identifier)
    node.setdefault("name", _display_name_for(node, identifier))
    return node


def _singular_entity_type(slug: str) -> str:
    overrides = {
        "campaigns": "campaign",
        "scenarios": "scenario",
        "places": "location",
        "npcs": "npc",
        "pcs": "pc",
    }
    if slug in overrides:
        return overrides[slug]
    if slug.endswith("ies"):
        return f"{slug[:-3]}y"
    if slug.endswith("s"):
        return slug[:-1]
    return slug


def _identifier_for(item: Mapping[str, Any], slug: str, index: int) -> str:
    for key in ("id", "uuid", "slug", "key", "Name", "name", "Title", "title"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return f"{slug}-{index}"


def _display_name_for(item: Mapping[str, Any], fallback: str) -> str:
    for key in ("Name", "name", "Title", "title", "Label", "label"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return fallback
