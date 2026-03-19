from __future__ import annotations

from modules.campaigns.models.campaign_blueprint import CampaignArc, CampaignBlueprint
from modules.campaigns.shared.arc_status import canonicalize_arc_status


REQUIRED_FIELD = "name"


def build_campaign_payload(form_data: dict, arcs_data: list[dict]) -> dict:
    """Build a validated campaign payload suitable for GenericModelWrapper.save_item."""

    campaign_name = (form_data.get("name") or "").strip()
    if not campaign_name:
        raise ValueError("Campaign name is required")

    arcs: list[CampaignArc] = []
    for raw_arc in arcs_data:
        arc_name = (raw_arc.get("name") or "").strip()
        if not arc_name:
            continue
        raw_scenarios = raw_arc.get("scenarios") or []
        if isinstance(raw_scenarios, str):
            raw_scenarios = [s.strip() for s in raw_scenarios.split(",")]
        arcs.append(
            CampaignArc(
                name=arc_name,
                summary=(raw_arc.get("summary") or "").strip(),
                objective=(raw_arc.get("objective") or "").strip(),
                status=canonicalize_arc_status(raw_arc.get("status")),
                thread=(raw_arc.get("thread") or "").strip(),
                scenarios=[s.strip() for s in raw_scenarios if str(s).strip()],
            )
        )

    blueprint = CampaignBlueprint(
        name=campaign_name,
        logline=(form_data.get("logline") or "").strip(),
        genre=(form_data.get("genre") or "").strip(),
        tone=(form_data.get("tone") or "").strip(),
        setting=(form_data.get("setting") or "").strip(),
        status=(form_data.get("status") or "Planned").strip() or "Planned",
        start_date=(form_data.get("start_date") or "").strip(),
        end_date=(form_data.get("end_date") or "").strip(),
        main_objective=(form_data.get("main_objective") or "").strip(),
        stakes=(form_data.get("stakes") or "").strip(),
        themes=_split_lines(form_data.get("themes") or ""),
        notes=(form_data.get("notes") or "").strip(),
        arcs=arcs,
    )
    return blueprint.to_entity_payload()


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in str(value).splitlines() if line.strip()]
