"""Helpers for preparing AI model selector options."""

from __future__ import annotations


def unique_model_names(*model_groups: list[str] | tuple[str, ...]) -> list[str]:
    """Return non-empty model names without duplicates, preserving order."""
    names: list[str] = []
    for models in model_groups:
        for model in models:
            normalized = str(model or "").strip()
            if normalized and normalized not in names:
                names.append(normalized)
    return names


def build_ai_model_options(
    *,
    configured_model: str,
    last_used_model: str | None,
    discovered_models: list[str] | tuple[str, ...],
    current_model: str | None = None,
) -> tuple[list[str], str]:
    """Build selector options and selected model from config and discovery results."""
    fallback_model = str(last_used_model or configured_model or "").strip()
    configured_model = str(configured_model or "").strip()
    current_model = str(current_model or "").strip()

    options = unique_model_names(
        [current_model],
        [fallback_model],
        list(discovered_models),
        [configured_model],
    )
    selected_model = (
        current_model if current_model in options else options[0] if options else ""
    )
    return options, selected_model
