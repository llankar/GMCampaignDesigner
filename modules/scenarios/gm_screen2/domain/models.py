"""Immutable domain models for GM Screen 2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ScenarioSummary:
    """High-level scenario identity used by screen state and selection flows."""

    scenario_id: str
    title: str
    summary: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PanelPayload:
    """Normalized payload rendered by a specific panel."""

    panel_id: str
    title: str
    content_blocks: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScenarioFilter:
    """Filter options applied to scenario or panel content."""

    query: str = ""
    tags: tuple[str, ...] = ()
    include_completed: bool = True


@dataclass(frozen=True, slots=True)
class LayoutPreset:
    """Persisted layout metadata for desktop arrangements."""

    name: str
    split_ratios: tuple[float, ...]
    visible_panels: tuple[str, ...]
    pinned_blocks: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScenarioPanelBundle:
    """Collection of panel payloads for the currently active scenario."""

    scenario: ScenarioSummary
    panels: Mapping[str, PanelPayload]
    available_tabs: Sequence[str]
