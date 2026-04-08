"""Tab variants and visual helpers for GM screen tabs."""

from __future__ import annotations

from typing import Dict


TAB_CATEGORY_STORY = "story"
TAB_CATEGORY_WORLD = "world"
TAB_CATEGORY_OPS = "ops"
TAB_CATEGORY_DEFAULT = "default"


TAB_VARIANTS: Dict[str, Dict[str, str]] = {
    TAB_CATEGORY_STORY: {
        "active_fg": "#3B1E36",
        "inactive_fg": "#241A23",
        "active_border": "#D946EF",
        "inactive_border": "#4B2A43",
        "active_hover": "#4C2746",
        "inactive_hover": "#2D2230",
        "active_accent": "#F472B6",
        "inactive_accent": "#5B344F",
    },
    TAB_CATEGORY_WORLD: {
        "active_fg": "#1E3A34",
        "inactive_fg": "#1B2624",
        "active_border": "#34D399",
        "inactive_border": "#2C4B45",
        "active_hover": "#254841",
        "inactive_hover": "#20302D",
        "active_accent": "#6EE7B7",
        "inactive_accent": "#355A52",
    },
    TAB_CATEGORY_OPS: {
        "active_fg": "#1E2F46",
        "inactive_fg": "#1A2433",
        "active_border": "#60A5FA",
        "inactive_border": "#2D3F57",
        "active_hover": "#283B57",
        "inactive_hover": "#202B3A",
        "active_accent": "#93C5FD",
        "inactive_accent": "#375071",
    },
    TAB_CATEGORY_DEFAULT: {
        "active_fg": "#2A2A33",
        "inactive_fg": "#1F2229",
        "active_border": "#8B95A7",
        "inactive_border": "#3B4250",
        "active_hover": "#343846",
        "inactive_hover": "#262B36",
        "active_accent": "#B6C2D9",
        "inactive_accent": "#4D5666",
    },
}


def normalize_tab_name(name: str) -> str:
    """Return a lowercase normalized tab name."""
    return " ".join((name or "").strip().lower().split())


def tab_category_for_name(name: str) -> str:
    """Map tab names to a category."""
    normalized = normalize_tab_name(name)
    if any(key in normalized for key in ("scenario", "note", "plot")):
        return TAB_CATEGORY_STORY
    if any(key in normalized for key in ("map", "faction", "place")):
        return TAB_CATEGORY_WORLD
    if any(key in normalized for key in ("timer", "debrief", "capture")):
        return TAB_CATEGORY_OPS
    return TAB_CATEGORY_DEFAULT


def tab_icon_for_name(name: str) -> str:
    """Return an icon for a given tab name."""
    normalized = normalize_tab_name(name)
    if "scenario" in normalized:
        return "🎬"
    if "note" in normalized:
        return "📝"
    if "plot" in normalized:
        return "🎭"
    if "map" in normalized:
        return "🗺"
    if "faction" in normalized:
        return "🏴"
    if "place" in normalized:
        return "📍"
    if "timer" in normalized:
        return "⏱"
    if "debrief" in normalized:
        return "📋"
    if "capture" in normalized:
        return "📸"
    return "◻"


def tab_short_label(name: str) -> str:
    """Build a short label from the tab name."""
    words = [word for word in (name or "").strip().split() if word]
    if not words:
        return "Tab"
    if len(words) == 1:
        return words[0][:11]
    if len(words) == 2:
        return f"{words[0][:8]} {words[1][:8]}".strip()
    return "".join(word[0].upper() for word in words[:3])
