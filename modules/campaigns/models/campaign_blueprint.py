from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CampaignArc:
    """Internal arc representation stored inside the campaign entity payload."""

    name: str
    summary: str = ""
    objective: str = ""
    status: str = "Planned"
    scenarios: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "objective": self.objective,
            "status": self.status,
            "scenarios": [s for s in self.scenarios if s],
        }


@dataclass
class CampaignBlueprint:
    """DTO used by the campaign wizard before persistence."""

    name: str
    logline: str = ""
    genre: str = ""
    tone: str = ""
    setting: str = ""
    status: str = "Planned"
    start_date: str = ""
    end_date: str = ""
    main_objective: str = ""
    stakes: str = ""
    themes: list[str] = field(default_factory=list)
    notes: str = ""
    arcs: list[CampaignArc] = field(default_factory=list)

    def to_entity_payload(self) -> dict[str, Any]:
        arc_data = [arc.as_dict() for arc in self.arcs]
        linked_scenarios: list[str] = []
        for arc in arc_data:
            for title in arc.get("scenarios", []):
                if title and title not in linked_scenarios:
                    linked_scenarios.append(title)

        return {
            "Name": self.name,
            "Logline": self.logline,
            "Genre": self.genre,
            "Tone": self.tone,
            "Setting": self.setting,
            "Status": self.status,
            "StartDate": self.start_date,
            "EndDate": self.end_date,
            "MainObjective": self.main_objective,
            "Stakes": self.stakes,
            "Themes": [theme for theme in self.themes if theme],
            "Arcs": arc_data,
            "LinkedScenarios": linked_scenarios,
            "Notes": self.notes,
        }
