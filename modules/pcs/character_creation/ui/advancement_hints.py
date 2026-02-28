"""Hint labels for advancement choice details in character creation UI."""

from __future__ import annotations


ADVANCEMENT_DETAILS_HINTS = {
    "skill_improvement": "Saisir 2 compétences favorites ou 1 non-favorite, séparées par virgule.",
}


def details_hint_for_advancement(advancement_type: str) -> str:
    """Return the contextual hint text shown below an advancement details field."""

    return ADVANCEMENT_DETAILS_HINTS.get((advancement_type or "").strip(), "")
