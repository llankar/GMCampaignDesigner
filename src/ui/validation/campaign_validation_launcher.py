"""UI entry point for campaign hierarchy validation."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable, Mapping, Sequence

from modules.helpers.logging_helper import log_exception, log_info
from src.ui.validation.campaign_arc_hierarchy import build_campaign_arc_nodes
from src.ui.validation.campaign_scenario_hierarchy import (
    attach_referenced_scenarios_to_arcs,
    build_scenario_reference_index,
)
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
from src.ui.validation.dialogs.invalid_hierarchy_dialog import (
    InvalidHierarchyDialogConfig,
    open_invalid_hierarchy_dialog,
)
from src.ui.validation.dialogs.validation_summary_dialog import (
    open_validation_summary_dialog,
)
from src.ui.validation.labels import (
    CAMPAIGN_DATA_UNAVAILABLE_MESSAGE,
    CAMPAIGN_DATA_UNAVAILABLE_TITLE,
    CAMPAIGN_REQUIRED_MESSAGE,
    CAMPAIGN_REQUIRED_TITLE,
    HIERARCHY_CONSISTENCY_TITLE,
    IGNORE_ISSUE_PROMPT,
    TECHNICAL_DETAIL_LABEL,
    VALIDATION_IMPOSSIBLE_TITLE,
    VALIDATION_UNAVAILABLE_MESSAGE,
    VALIDATION_UNAVAILABLE_TITLE,
)
from src.ui.validation.progress import ValidationScanProgress
from src.ui.validation.validation_wizard_controller import (
    ValidationWizardAction,
    ValidationWizardController,
    ValidationWizardIssue,
    ValidationWizardMetrics,
    ValidationWizardStatus,
    ValidationWizardStep,
    resolve_reference_for_issue,
    resolve_target_for_issue,
    validation_setup_failed_step,
)
from src.validation import (
    IssueType,
    ReferenceValidationResult,
    normalize_validator_reference_fields,
    validate_reference_graph,
)

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

    def __init__(
        self, app: Any, *, campaign_selector: CampaignSelector | None = None
    ) -> None:
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
                    CAMPAIGN_DATA_UNAVAILABLE_TITLE,
                    CAMPAIGN_DATA_UNAVAILABLE_MESSAGE,
                )
                self._handle_step(None, step)
                return None

            selected_campaign = self._resolve_campaign_selection(
                campaign, entity_wrappers
            )
            if selected_campaign is None:
                step = validation_setup_failed_step(
                    CAMPAIGN_REQUIRED_TITLE,
                    CAMPAIGN_REQUIRED_MESSAGE,
                )
                self._handle_step(None, step)
                return None

            started_at = monotonic()
            progress = ValidationScanProgress(self.app).show("Scanning arcs...")
            hierarchy = build_campaign_validation_hierarchy(
                entity_wrappers,
                selected_campaign,
                progress=progress,
            )
            progress.set_phase("Checking references...")
            graph = validate_reference_graph(hierarchy, campaign=selected_campaign.item)
            controller = ValidationWizardController(
                _wizard_items(graph),
                campaign=selected_campaign.item,
                reference_resolver=lambda issue: resolve_reference_for_issue(
                    issue, graph.references
                ),
                metrics=ValidationWizardMetrics(
                    entities_visited=len(graph.entities),
                    references_checked=len(graph.references),
                ),
                started_at=started_at,
            )
            _log_validation_diagnostics(graph)
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
                VALIDATION_UNAVAILABLE_TITLE,
                f"{VALIDATION_UNAVAILABLE_MESSAGE}\n\n{TECHNICAL_DETAIL_LABEL}: {exc}",
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

            title = (
                step.setup_failure.title
                if step.setup_failure
                else VALIDATION_IMPOSSIBLE_TITLE
            )
            messagebox.showerror(title, step.message)
            return

        if step.status == ValidationWizardStatus.COMPLETED:
            if step.summary is not None:
                open_validation_summary_dialog(self.app, step.summary)
            return

        if step.status == ValidationWizardStatus.CANCELED:
            if step.summary is not None:
                open_validation_summary_dialog(
                    self.app,
                    step.summary,
                    message=step.message,
                )
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

        if step.issue.issue_type == IssueType.INVALID_HIERARCHY:
            from tkinter import messagebox

            if messagebox.askyesno(
                HIERARCHY_CONSISTENCY_TITLE,
                f"{step.message}\n\n{IGNORE_ISSUE_PROMPT}",
            ):
                next_step = run.controller.submit_action(
                    ValidationWizardAction.SKIP_SESSION
                )
                self._handle_step(run, next_step)
                return

            open_invalid_hierarchy_dialog(
                self.app,
                run.controller,
                step,
                reference=resolve_reference_for_issue(
                    step.issue, run.graph.references
                ),
                target=resolve_target_for_issue(step.issue, run.graph.entities),
                config=InvalidHierarchyDialogConfig(
                    on_step=lambda next_step: self._handle_step(run, next_step)
                ),
            )
            return

        from tkinter import messagebox

        messagebox.showwarning(HIERARCHY_CONSISTENCY_TITLE, step.message)


def load_campaign_options(
    entity_wrappers: Mapping[str, Any],
) -> tuple[CampaignSelectorOption, ...]:
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
    root: dict[str, Any] = normalize_validator_reference_fields(
        "campaign", selected.item
    )
    root["type"] = "campaign"
    root["entity_type"] = "campaign"
    root["id"] = selected.campaign_id
    root["name"] = selected.label
    root["arcs"] = build_campaign_arc_nodes(selected.item.get("Arcs"))
    scenario_nodes = _load_scenario_nodes(entity_wrappers, progress=progress)
    attach_referenced_scenarios_to_arcs(
        root["arcs"], build_scenario_reference_index(scenario_nodes)
    )
    root["entities"] = []
    entities = root["entities"]

    for slug in sorted(entity_wrappers):
        if slug in {"campaigns", "scenarios"}:
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
            f"with {len(root['arcs'])} arcs, "
            f"{sum(len(arc.get('scenarios', ())) for arc in root['arcs'])} "
            f"arc scenarios, and {len(entities)} entities"
        ),
        func_name="src.ui.validation.campaign_validation_launcher.build_campaign_validation_hierarchy",
    )
    return root


def _load_scenario_nodes(
    entity_wrappers: Mapping[str, Any],
    *,
    progress: ValidationScanProgress | None = None,
) -> tuple[dict[str, Any], ...]:
    """Load and normalize all scenarios for arc-local hierarchy attachment."""

    wrapper = entity_wrappers.get("scenarios")
    if wrapper is None:
        return ()
    if progress is not None:
        progress.set_phase(_scan_phase_for_slug("scenarios"))
    return tuple(
        _normalize_entity_node("scenarios", item, index)
        for index, item in enumerate(_safe_load_items(wrapper))
        if isinstance(item, Mapping)
    )


def _log_validation_diagnostics(graph: ReferenceValidationResult) -> None:
    """Log validator-owned traversal diagnostics for QA and troubleshooting."""

    diagnostics = graph.diagnostics
    log_info(
        (
            "Campaign validation graph diagnostics: "
            f"{graph.debug_summary}; "
            f"entities_visited={len(graph.entities)}; "
            f"references_checked={len(graph.references)}"
        ),
        func_name="src.ui.validation.campaign_validation_launcher.CampaignHierarchyValidationLauncher.launch",
    )
    log_info(
        (
            "Campaign validation visited nodes: "
            f"campaigns={diagnostics.visited_campaigns}; "
            f"arcs={diagnostics.visited_arcs}; "
            f"scenarios={diagnostics.visited_scenarios}; "
            f"references={diagnostics.visited_references}"
        ),
        func_name="src.ui.validation.campaign_validation_launcher.CampaignHierarchyValidationLauncher.launch",
    )


def _wizard_items(
    graph: ReferenceValidationResult,
) -> tuple[ValidationWizardIssue, ...]:
    return tuple(
        ValidationWizardIssue(
            issue=issue,
            reference=resolve_reference_for_issue(issue, graph.references),
            target=resolve_target_for_issue(issue, graph.entities),
        )
        for issue in graph.issues
    )


def _scan_phase_for_slug(slug: str) -> str:
    if slug == "arcs":
        return "Scanning arcs..."
    if slug == "scenarios":
        return "Scanning scenarios..."
    return f"Scanning {slug.replace('_', ' ')}..."


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


def _normalize_entity_node(
    slug: str, item: Mapping[str, Any], index: int
) -> dict[str, Any]:
    entity_type = _singular_entity_type(slug)
    node = normalize_validator_reference_fields(entity_type, item)
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
