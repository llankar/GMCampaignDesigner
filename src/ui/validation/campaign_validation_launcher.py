"""UI entry point for campaign hierarchy validation."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable, Mapping, Sequence

from modules.helpers.logging_helper import log_exception, log_info
from src.ui.validation.dialogs.ambiguous_reference_dialog import (
    AmbiguousReferenceDialogConfig,
    open_ambiguous_reference_dialog,
)
from src.ui.validation.dialogs.campaign_selector_dialog import (
    CampaignSelectorOption,
    open_campaign_selector_dialog,
)
from src.ui.validation.dialogs.missing_reference_dialog import (
    MissingReferenceDialogConfig,
    open_missing_reference_dialog,
)
from src.ui.validation.dialogs.validation_summary_dialog import open_validation_summary_dialog
from src.ui.validation.progress import ValidationScanProgress
from src.ui.validation.validation_wizard_controller import (
    ValidationWizardAction,
    ValidationWizardController,
    ValidationWizardIssue,
    ValidationWizardMetrics,
    ValidationWizardStatus,
    ValidationWizardStep,
    resolve_reference_for_issue,
    validation_setup_failed_step,
)
from src.validation import IssueType, ReferenceValidationResult, validate_reference_graph
from src.validation.hierarchy_rules import FIELD_EXPECTED_TYPES

CampaignSelector = Callable[
    [Any, Sequence[CampaignSelectorOption]],
    CampaignSelectorOption | None,
]


@dataclass(frozen=True)
class CampaignValidationRun:
    """Objects created for one campaign validation launch."""

    campaign: CampaignSelectorOption
    graph: ReferenceValidationResult
    controller: ValidationWizardController
    first_step: ValidationWizardStep


class CampaignHierarchyValidationLauncher:
    """Instantiate the hierarchy validator and drive the validation wizard UI."""

    def __init__(self, app: Any, *, campaign_selector: CampaignSelector | None = None) -> None:
        self.app = app
        self._campaign_selector = campaign_selector or open_campaign_selector_dialog
        self._active_run: CampaignValidationRun | None = None

    @property
    def active_run(self) -> CampaignValidationRun | None:
        """Return the most recent validation run, if any."""

        return self._active_run

    def launch(
        self,
        campaign: Mapping[str, Any] | CampaignSelectorOption | None = None,
    ) -> CampaignValidationRun | None:
        """Validate a selected campaign hierarchy and start the wizard controller.

        Global launchers call this without a campaign, which opens a blocking
        selector dialog. Campaign-screen actions should pass the current
        campaign explicitly.
        """

        progress: ValidationScanProgress | None = None
        try:
            entity_wrappers = self._resolve_entity_wrappers()
            if entity_wrappers is None:
                step = validation_setup_failed_step(
                    "Données de campagne indisponibles",
                    (
                        "Le dépôt de données ou les services d’entités sont introuvables. "
                        "Ouvrez ou rechargez un projet de campagne avant de relancer la validation."
                    ),
                )
                self._handle_step(None, step)
                return None

            selected_campaign = self._resolve_campaign_selection(campaign, entity_wrappers)
            if selected_campaign is None:
                step = validation_setup_failed_step(
                    "Campagne requise",
                    (
                        "Aucune campagne n’a été sélectionnée pour la validation. "
                        "Sélectionnez une campagne active, puis relancez la validation."
                    ),
                )
                self._handle_step(None, step)
                return None

            started_at = monotonic()
            progress = ValidationScanProgress(self.app).show("Scanning arcs…")
            hierarchy = build_campaign_validation_hierarchy(
                entity_wrappers,
                selected_campaign,
                progress=progress,
            )
            progress.set_phase("Checking references…")
            graph = validate_reference_graph(hierarchy, campaign=selected_campaign.item)
            controller = ValidationWizardController(
                _wizard_items(graph),
                campaign=selected_campaign.item,
                reference_resolver=lambda issue: resolve_reference_for_issue(
                    issue, graph.references
                ),
                metrics=ValidationWizardMetrics(
                    entities_visited=_count_flat_entities(hierarchy),
                    references_checked=_count_flat_references(hierarchy),
                ),
                started_at=started_at,
            )
            first_step = controller.start()
            run = CampaignValidationRun(
                campaign=selected_campaign,
                graph=graph,
                controller=controller,
                first_step=first_step,
            )
            self._active_run = run
            if progress is not None:
                progress.close()
                progress = None
            self._handle_step(run, first_step)
            return run
        except Exception as exc:
            if progress is not None:
                progress.close()
            log_exception(
                f"Failed to run hierarchy validation: {exc}",
                func_name="src.ui.validation.campaign_validation_launcher.CampaignHierarchyValidationLauncher.launch",
            )
            step = validation_setup_failed_step(
                "Validation indisponible",
                (
                    "La validation n’a pas pu démarrer à cause d’une erreur d’initialisation. "
                    "Vérifiez que le projet est chargé, puis relancez la validation.\n\n"
                    f"Détail technique : {exc}"
                ),
            )
            self._handle_step(None, step)
            return None

    def _resolve_entity_wrappers(self) -> Mapping[str, Any] | None:
        wrappers = getattr(self.app, "entity_wrappers", None)
        if not isinstance(wrappers, Mapping) or not wrappers:
            return None
        return wrappers

    def _resolve_campaign_selection(
        self,
        campaign: Mapping[str, Any] | CampaignSelectorOption | None,
        entity_wrappers: Mapping[str, Any],
    ) -> CampaignSelectorOption | None:
        if isinstance(campaign, CampaignSelectorOption):
            return campaign
        if campaign is not None:
            return campaign_option_from_item(campaign)

        campaigns = load_campaign_options(entity_wrappers)
        if not campaigns:
            return None
        return self._campaign_selector(self.app, campaigns)

    def _handle_step(
        self,
        run: CampaignValidationRun | None,
        step: ValidationWizardStep,
    ) -> None:
        if step.status == ValidationWizardStatus.SETUP_FAILED:
            from tkinter import messagebox

            title = step.setup_failure.title if step.setup_failure else "Validation impossible"
            messagebox.showerror(title, step.message)
            return

        if step.status == ValidationWizardStatus.COMPLETED:
            if step.summary is not None:
                open_validation_summary_dialog(self.app, step.summary)
            return

        if step.status == ValidationWizardStatus.CANCELED:
            if step.summary is not None:
                open_validation_summary_dialog(self.app, step.summary)
            return

        if step.status == ValidationWizardStatus.ACTION_FAILED:
            from tkinter import messagebox

            messagebox.showwarning("Validation", step.message)
            return

        if step.issue is None or run is None:
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


def load_campaign_options(entity_wrappers: Mapping[str, Any]) -> tuple[CampaignSelectorOption, ...]:
    """Load selectable campaigns from the explicit campaigns wrapper."""

    wrapper = entity_wrappers.get("campaigns")
    if wrapper is None:
        return ()
    return tuple(
        campaign_option_from_item(item)
        for item in _safe_load_items(wrapper)
        if isinstance(item, Mapping)
    )


def campaign_option_from_item(item: Mapping[str, Any]) -> CampaignSelectorOption:
    """Create a selector option preserving the selected campaign object."""

    campaign_id = _identifier_for(item, "campaigns", 0)
    label = _display_name_for(item, campaign_id)
    return CampaignSelectorOption(campaign_id=campaign_id, label=label, item=dict(item))


def build_campaign_validation_hierarchy(
    entity_wrappers: Mapping[str, Any],
    campaign: Mapping[str, Any] | CampaignSelectorOption,
    *,
    progress: ValidationScanProgress | None = None,
) -> dict[str, Any]:
    """Build a validator-friendly hierarchy for one explicitly selected campaign."""

    selected = (
        campaign
        if isinstance(campaign, CampaignSelectorOption)
        else campaign_option_from_item(campaign)
    )
    root: dict[str, Any] = dict(selected.item)
    root["type"] = "campaign"
    root["entity_type"] = "campaign"
    root["id"] = selected.campaign_id
    root["name"] = selected.label
    root["entities"] = []
    entities = root["entities"]

    for slug in sorted(entity_wrappers):
        if slug == "campaigns":
            continue
        if progress is not None:
            progress.set_phase(_scan_phase_for_slug(slug))
        wrapper = entity_wrappers[slug]
        for index, item in enumerate(_safe_load_items(wrapper)):
            if not isinstance(item, Mapping):
                continue
            entities.append(_normalize_entity_node(slug, item, index))

    log_info(
        (
            f"Built validation hierarchy for campaign {selected.campaign_id} "
            f"with {len(entities)} entities"
        ),
        func_name="src.ui.validation.campaign_validation_launcher.build_campaign_validation_hierarchy",
    )
    return root


def _count_flat_entities(hierarchy: Mapping[str, Any]) -> int:
    entities = _flat_entities(hierarchy)
    return len(entities)


def _count_flat_references(hierarchy: Mapping[str, Any]) -> int:
    total = 0
    fields_by_type = _reference_fields_by_entity_type()
    for entity in _flat_entities(hierarchy):
        entity_type = (
            str(entity.get("entity_type") or entity.get("type") or "")
            .strip()
            .lower()
        )
        for field in fields_by_type.get(entity_type, ()):
            if field in entity:
                total += _reference_value_count(entity[field])
    return total


def _flat_entities(hierarchy: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    entities = hierarchy.get("entities", ())
    if not isinstance(entities, Sequence) or isinstance(
        entities, (str, bytes, bytearray)
    ):
        return ()
    return tuple(entity for entity in entities if isinstance(entity, Mapping))


def _reference_fields_by_entity_type() -> dict[str, tuple[str, ...]]:
    by_type: dict[str, list[str]] = {}
    for field_path in FIELD_EXPECTED_TYPES:
        entity_type, field = field_path.split(".", 1)
        by_type.setdefault(entity_type, []).append(field)
    return {entity_type: tuple(fields) for entity_type, fields in by_type.items()}


def _reference_value_count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Mapping):
        return 1
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return sum(1 for item in value if item is not None and str(item).strip())
    return 1 if str(value).strip() else 0


def _wizard_items(graph: ReferenceValidationResult) -> tuple[ValidationWizardIssue, ...]:
    return tuple(
        ValidationWizardIssue(
            issue=issue,
            reference=resolve_reference_for_issue(issue, graph.references),
        )
        for issue in graph.issues
    )


def _scan_phase_for_slug(slug: str) -> str:
    if slug == "arcs":
        return "Scanning arcs…"
    if slug == "scenarios":
        return "Scanning scenarios…"
    return f"Scanning {slug.replace('_', ' ')}…"


def _safe_load_items(wrapper: Any) -> Sequence[Any]:
    try:
        items = wrapper.load_items()
    except Exception as exc:
        log_exception(
            (
                "Unable to load items for validation from "
                f"{getattr(wrapper, 'entity_type', '?')}: {exc}"
            ),
            func_name="src.ui.validation.campaign_validation_launcher._safe_load_items",
        )
        return ()
    if isinstance(items, Sequence) and not isinstance(items, (str, bytes, bytearray)):
        return items
    return ()


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
