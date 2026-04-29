"""Deprecated compatibility layer for graph scenario planner."""
from __future__ import annotations

from warnings import warn

from modules.scenarios.wizard_steps.scenes.graph_mode import GraphModePlanner


class GraphScenarioPlanner(GraphModePlanner):
    """Deprecated alias for :class:`GraphModePlanner`."""

    def __init__(self, master):
        warn(
            "GraphScenarioPlanner is deprecated and will be removed in a future release; "
            "use GraphModePlanner from modules.scenarios.wizard_steps.scenes.graph_mode instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(master)
