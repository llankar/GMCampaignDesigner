"""Declarative models shared by the application menu builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class MenuCommandSpec:
    """One actionable entry in a menu group."""

    label: str
    command: Callable[[], None] | None = None
    shortcut: str = ""
    icon_key: str | None = None
    kind: str = "command"


@dataclass(slots=True)
class MenuGroupSpec:
    """A labelled collection of related menu commands."""

    title: str
    helper: str
    items: list[MenuCommandSpec] = field(default_factory=list)


@dataclass(slots=True)
class TopLevelMenuSpec:
    """A top-level navigation menu and its grouped commands."""

    label: str
    groups: list[MenuGroupSpec] = field(default_factory=list)
