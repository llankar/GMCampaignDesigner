"""Search index support for GM Table panels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PanelSearchResult:
    panel_id: str
    title: str
    kind: str
    text: str
    minimized: bool = False
    locked: bool = False


def _flatten_state_text(value, prefix: str = "") -> list[str]:
    """Return searchable tokens for nested serializable state fields."""
    if isinstance(value, dict):
        parts: list[str] = []
        for key, nested in sorted(value.items()):
            parts.append(str(key))
            parts.extend(_flatten_state_text(nested, str(key)))
        return parts
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for nested in value:
            parts.extend(_flatten_state_text(nested, prefix))
        return parts
    if isinstance(value, (str, int, float, bool)):
        return [prefix, str(value)] if prefix else [str(value)]
    return []


def _state_text(state: dict) -> str:
    return " ".join(part for part in _flatten_state_text(state or {}) if part)


def build_panel_search_index(records: list[dict]) -> list[PanelSearchResult]:
    """Build searchable panel records from workspace list_panels output."""
    results: list[PanelSearchResult] = []
    for record in records:
        definition = record.get("definition")
        if definition is None:
            continue
        state = getattr(definition, "state", {}) or {}
        title = str(getattr(definition, "title", "Panel") or "Panel")
        kind = str(getattr(definition, "kind", "") or "")
        text = " ".join([title, kind, _state_text(state)]).casefold()
        results.append(PanelSearchResult(
            panel_id=str(getattr(definition, "panel_id", "")),
            title=title,
            kind=kind,
            text=text,
            minimized=record.get("layout_mode") == "minimized",
            locked=bool(record.get("locked", state.get("locked"))),
        ))
    return results


def filter_panel_search_index(index: list[PanelSearchResult], query: str) -> list[PanelSearchResult]:
    """Return search results matching every query token."""
    tokens = [token.casefold() for token in str(query or "").split() if token.strip()]
    if not tokens:
        return list(index)
    return [result for result in index if all(token in result.text for token in tokens)]
