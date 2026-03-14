from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from modules.generic.generic_model_wrapper import GenericModelWrapper


@dataclass(frozen=True)
class CampaignToneContract:
    """Normalized style constraints extracted from a campaign entity."""

    campaign_name: str
    genre: str
    tone: str
    setting: str

    def has_constraints(self) -> bool:
        return any([self.genre, self.tone, self.setting])


_STATUS_PRIORITY = {
    "in progress": 0,
    "running": 0,
    "active": 0,
    "planned": 1,
    "paused": 2,
    "completed": 3,
    "done": 3,
}


def load_campaign_tone_contract(*, db_path: str | None = None) -> CampaignToneContract | None:
    """Load the best candidate campaign and derive a tone contract from it."""

    wrapper = GenericModelWrapper("campaigns", db_path=db_path)
    try:
        campaigns = wrapper.load_items()
    except Exception:
        return None

    selected = _pick_campaign(campaigns)
    if not selected:
        return None

    contract = CampaignToneContract(
        campaign_name=_clean_text(selected.get("Name")),
        genre=_clean_text(selected.get("Genre")),
        tone=_clean_text(selected.get("Tone")),
        setting=_clean_text(selected.get("Setting")),
    )
    return contract if contract.has_constraints() else None


def format_tone_contract_guidance(contract: CampaignToneContract) -> str:
    """Build a compact prompt section enforcing campaign style constraints."""

    lines = ["Campaign tone contract (must be respected):"]
    if contract.campaign_name:
        lines.append(f"- Campaign: {contract.campaign_name}")
    if contract.genre:
        lines.append(f"- Genre: {contract.genre}")
    if contract.tone:
        lines.append(f"- Tone: {contract.tone}")
    if contract.setting:
        lines.append(f"- Setting: {contract.setting}")
    lines.append("- Keep generated content stylistically consistent with these constraints.")
    lines.append("- Avoid introducing genre, mood, or world assumptions that conflict with the contract.")
    return "\n".join(lines)


def _pick_campaign(campaigns: Iterable[dict]) -> Optional[dict]:
    candidates = [entry for entry in campaigns if isinstance(entry, dict)]
    if not candidates:
        return None

    with_constraints = [entry for entry in candidates if _has_contract_fields(entry)]
    ranked_source = with_constraints or candidates

    ranked = sorted(
        ranked_source,
        key=lambda item: (
            _status_rank(item.get("Status")),
            0 if _clean_text(item.get("StartDate")) else 1,
            _clean_text(item.get("Name")).lower(),
        ),
    )
    return ranked[0] if ranked else None


def _has_contract_fields(campaign: dict) -> bool:
    return any(
        _clean_text(campaign.get(field_name))
        for field_name in ("Genre", "Tone", "Setting")
    )


def _status_rank(raw_status: object) -> int:
    normalized = _clean_text(raw_status).lower()
    return _STATUS_PRIORITY.get(normalized, 50)


def _clean_text(raw_value: object) -> str:
    if raw_value is None:
        return ""
    return str(raw_value).strip()
