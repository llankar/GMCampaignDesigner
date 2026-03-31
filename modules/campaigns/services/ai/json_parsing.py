"""Utilities for AI json parsing."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from .constraints import minimum_scenarios_per_arc


class ArcGenerationValidationError(RuntimeError):
    """Raised when AI-generated arc payloads do not match the expected schema."""


def parse_json_relaxed(text: str) -> Any:
    """Parse JSON from an AI response that may include code fences or extra text."""

    if not text:
        raise ArcGenerationValidationError("Empty AI response")

    candidate = str(text).strip().lstrip("﻿")
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate, flags=re.IGNORECASE).strip()
        candidate = candidate.rstrip("`").strip()

    try:
        return json.loads(candidate)
    except Exception:
        pass

    extracted = _extract_embedded_json(candidate)
    if extracted is not None:
        return extracted

    raise ArcGenerationValidationError("Failed to parse JSON from AI response")


def _extract_embedded_json(candidate: str) -> Any | None:
    """Extract embedded JSON."""
    decoder = json.JSONDecoder()

    for idx, char in enumerate(candidate):
        # Process each (idx, char) from enumerate(candidate).
        if char not in "[{":
            continue

        try:
            payload, _ = decoder.raw_decode(candidate[idx:])
            return payload
        except Exception:
            continue

    return None


def normalize_arc_generation_payload(payload: Any, available_scenarios: set[str] | None = None) -> dict[str, Any]:
    """Validate and normalize an AI campaign-arc payload into predictable structures."""

    if not isinstance(payload, dict):
        raise ArcGenerationValidationError("AI arc generation must return a JSON object")

    campaign = payload.get("campaign") or {}
    if not isinstance(campaign, dict):
        raise ArcGenerationValidationError("The 'campaign' field must be a JSON object")

    threads = _normalize_threads(payload.get("threads") or payload.get("campaign_threads") or [])
    arcs = _normalize_arcs(payload.get("arcs") or [], available_scenarios=available_scenarios)

    if not arcs:
        raise ArcGenerationValidationError("The AI response must contain at least one arc")

    return {
        "campaign": {
            "name": _clean_text(campaign.get("name")),
            "summary": _clean_text(campaign.get("summary")),
            "objective": _clean_text(campaign.get("objective")),
            "coherence_notes": _clean_text(campaign.get("coherence_notes")),
        },
        "threads": threads,
        "arcs": arcs,
    }


def _normalize_threads(raw_threads: Any) -> list[dict[str, Any]]:
    """Normalize threads."""
    if not isinstance(raw_threads, list):
        raise ArcGenerationValidationError("The 'threads' field must be a JSON array")

    normalized: list[dict[str, Any]] = []
    for raw_thread in raw_threads:
        # Process each raw_thread from raw_threads.
        if not isinstance(raw_thread, dict):
            continue
        name = _clean_text(raw_thread.get("name"))
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "summary": _clean_text(raw_thread.get("summary")),
                "arcs": [_clean_text(value) for value in (raw_thread.get("arcs") or []) if _clean_text(value)],
            }
        )
    return normalized


def _normalize_arcs(raw_arcs: Any, available_scenarios: set[str] | Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """Normalize arcs."""
    if not isinstance(raw_arcs, list):
        raise ArcGenerationValidationError("The 'arcs' field must be a JSON array")

    normalized: list[dict[str, Any]] = []
    canonical_titles, scenario_lookup = _build_scenario_lookup(available_scenarios)
    total_available = len(canonical_titles) if canonical_titles is not None else None
    min_required = minimum_scenarios_per_arc(total_available)
    for index, raw_arc in enumerate(raw_arcs, start=1):
        # Process each (index, raw_arc) from enumerate(raw_arcs, start=1).
        if not isinstance(raw_arc, dict):
            continue
        name = _clean_text(raw_arc.get("name"))
        if not name:
            raise ArcGenerationValidationError(f"Arc #{index} is missing a name")

        scenarios = _normalize_scenarios(raw_arc.get("scenarios") or [], index=index, min_required=min_required)
        if scenario_lookup is not None:
            # Handle the branch where scenario lookup is available.
            resolved_scenarios: list[str] = []
            unknown: list[str] = []
            for title in scenarios:
                # Process each title from scenarios.
                canonical_title = _resolve_scenario_title(title, scenario_lookup)
                if canonical_title is None:
                    unknown.append(title)
                    continue
                if canonical_title not in resolved_scenarios:
                    resolved_scenarios.append(canonical_title)
            if unknown:
                raise ArcGenerationValidationError(
                    f"Arc '{name}' references unknown scenarios: {', '.join(unknown)}"
                )
            scenarios = resolved_scenarios

        normalized.append(
            {
                "name": name,
                "summary": _clean_text(raw_arc.get("summary")),
                "objective": _clean_text(raw_arc.get("objective")),
                "status": _clean_text(raw_arc.get("status")) or "Planned",
                "thread": _clean_text(raw_arc.get("thread")),
                "scenarios": scenarios,
            }
        )
    return normalized


def _normalize_scenarios(raw_scenarios: Any, index: int, *, min_required: int) -> list[str]:
    """Normalize scenarios."""
    if isinstance(raw_scenarios, str):
        scenarios = [part.strip() for part in raw_scenarios.split(",") if part.strip()]
    elif isinstance(raw_scenarios, list):
        scenarios = [_clean_text(item) for item in raw_scenarios if _clean_text(item)]
    else:
        raise ArcGenerationValidationError(f"Arc #{index} has an invalid 'scenarios' field")

    deduped: list[str] = []
    for scenario in scenarios:
        if scenario not in deduped:
            deduped.append(scenario)

    if len(deduped) < min_required:
        raise ArcGenerationValidationError(
            f"Arc #{index} must contain at least {min_required} connected scenarios"
        )

    return deduped


def _clean_text(value: Any) -> str:
    """Internal helper for clean text."""
    return str(value or "").strip()


def _build_scenario_lookup(available_scenarios: set[str] | Mapping[str, str] | None) -> tuple[set[str] | None, dict[str, str] | None]:
    """Build scenario lookup."""
    if available_scenarios is None:
        return None, None

    canonical_titles: set[str] = set()
    lookup: dict[str, str] = {}
    if isinstance(available_scenarios, Mapping):
        items = available_scenarios.items()
    else:
        items = ((title, title) for title in available_scenarios)

    for alias, canonical in items:
        # Process each (alias, canonical) from items.
        canonical_title = _clean_text(canonical)
        alias_title = _clean_text(alias) or canonical_title
        if not canonical_title:
            continue
        canonical_titles.add(canonical_title)
        for candidate in {canonical_title, alias_title}:
            # Process each candidate from {canonical_title, alias_title}.
            normalized_candidate = _normalize_title_token(candidate)
            if normalized_candidate:
                lookup[normalized_candidate] = canonical_title

    return canonical_titles, lookup


def _resolve_scenario_title(title: str, scenario_lookup: dict[str, str]) -> str | None:
    """Resolve scenario title."""
    normalized_title = _normalize_title_token(title)
    if not normalized_title:
        return None
    direct_match = scenario_lookup.get(normalized_title)
    if direct_match:
        return direct_match

    for delimiter in (":", " - ", " – ", " — ", " —", " –", "-"):
        # Process each delimiter from (':', ' - ', ' – ', ' — ', ' —', ' –', '-').
        if delimiter not in title:
            continue
        prefix = _clean_text(title.split(delimiter, 1)[0])
        prefix_match = scenario_lookup.get(_normalize_title_token(prefix))
        if prefix_match:
            return prefix_match

    for normalized_candidate, canonical_title in scenario_lookup.items():
        # Process each (normalized_candidate, canonical_title) from scenario_lookup.items().
        if len(normalized_candidate) < 8:
            continue
        if normalized_title.startswith(normalized_candidate):
            return canonical_title

    return None


def _normalize_title_token(value: Any) -> str:
    """Normalize title token."""
    cleaned = unicodedata.normalize("NFKD", _clean_text(value))
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned = cleaned.casefold()
    cleaned = cleaned.replace("’", "'").replace("`", "'")
    cleaned = re.sub(r"[^\w\s']+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
