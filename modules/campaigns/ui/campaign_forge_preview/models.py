from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CampaignForgeScenarioPreview:
    arc_name: str
    title: str
    summary: str
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CampaignForgeArcPreview:
    name: str
    objective: str
    thread: str
    status: str
    scenarios: list[CampaignForgeScenarioPreview] = field(default_factory=list)


@dataclass(slots=True)
class ForgeValidationResult:
    global_warnings: list[str] = field(default_factory=list)
    scenario_warnings: dict[tuple[str, str], list[str]] = field(default_factory=dict)
