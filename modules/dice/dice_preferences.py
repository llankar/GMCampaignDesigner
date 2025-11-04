"""Helpers that adapt dice behaviour to the active campaign system."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence, Tuple

from modules.dice import dice_engine
from modules.helpers import system_config


def _normalize_face_value(value: Any) -> int | None:
    """Return ``value`` coerced to a positive integer die size when possible."""

    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        lowered = stripped.lower()
        if lowered.startswith("d"):
            lowered = lowered[1:]
        if lowered.isdigit():
            try:
                result = int(lowered, 10)
            except ValueError:
                return None
            return result if result > 0 else None
    return None


def get_supported_faces() -> Tuple[int, ...]:
    """Return the set of dice faces supported by the active system."""

    config = system_config.get_current_system_config()
    faces: list[int] = []
    seen: set[int] = set()
    if config:
        for face in config.supported_faces:
            normalized = _normalize_face_value(face)
            if normalized is None or normalized in seen:
                continue
            seen.add(normalized)
            faces.append(normalized)
    if not faces:
        faces = list(dice_engine.DEFAULT_DICE_SIZES)
    return tuple(faces)


def get_default_formula() -> str:
    """Return the system's default attack formula (raw string)."""

    config = system_config.get_current_system_config()
    if config and config.default_formula:
        return config.default_formula.strip()
    return "1d20"


def canonicalize_formula(formula: str | None) -> str | None:
    """Return a canonical dice formula or ``None`` if the text cannot be parsed."""

    if formula is None:
        return None
    text = str(formula).strip()
    if not text:
        return None
    try:
        parsed = dice_engine.parse_formula(text, supported_faces=get_supported_faces())
    except dice_engine.FormulaError:
        return None
    return parsed.canonical()


def get_rollable_default_formula() -> str:
    """Return a dice formula that is safe to roll for the current system."""

    config = system_config.get_current_system_config()
    forced_defaults = {
        "d20": "1d20",
        "2d20": "2d20",
        "savage_fate": "d6",
    }
    if config:
        forced = forced_defaults.get(config.slug.lower())
        if forced:
            canonical = canonicalize_formula(forced)
            if canonical:
                return canonical
            return forced

    raw_default = get_default_formula()
    sanitized = re.sub(r"\bmod\b", "0", raw_default, flags=re.IGNORECASE)
    sanitized = re.sub(r"(\d+)d[fF]\b", r"\1d6", sanitized)
    sanitized = re.sub(r"\bd[fF]\b", "1d6", sanitized)
    canonical = canonicalize_formula(sanitized)
    if canonical:
        return canonical
    fallback = canonicalize_formula("1d20")
    return fallback or "1d20"


def _dice_roll_config() -> Mapping[str, Any]:
    config = system_config.get_current_system_config()
    if not config:
        return {}
    raw = config.analyzer_config.get("dice")
    if isinstance(raw, Mapping):
        return raw
    return {}


def get_default_roll_options() -> Mapping[str, bool]:
    """Return the default roll option flags for the active system."""

    config = _dice_roll_config()
    explode = bool(config.get("explode", False))
    separate = bool(config.get("separate", False))
    return {"explode": explode, "separate": separate}


def _attack_roll_config() -> Mapping[str, Any]:
    config = system_config.get_current_system_config()
    if not config:
        return {}
    raw = config.analyzer_config.get("attack_roll")
    if isinstance(raw, Mapping):
        return raw
    return {}


def _template_context(*, attack_bonus: str, base: str) -> dict[str, str]:
    stripped = attack_bonus.strip()
    sign = stripped[0] if stripped and stripped[0] in "+-" else "+"
    bonus_value = stripped.lstrip("+-")
    return {
        "attack_bonus": stripped,
        "bonus": stripped,
        "bonus_value": bonus_value,
        "sign": sign,
        "base": base,
    }


def make_attack_roll_formula(attack_bonus: str) -> str:
    """Format an attack roll formula using the active system template."""

    normalized_input = str(attack_bonus or "").strip()
    config = _attack_roll_config()
    base_candidates: Sequence[str | None] = (
        config.get("fallback"),
        config.get("base"),
        config.get("default"),
        get_default_formula(),
        "1d20",
    )

    def _fallback_formula() -> str:
        for candidate in base_candidates:
            canonical = canonicalize_formula(candidate)
            if canonical:
                return canonical
        return "1d20"

    if not normalized_input:
        return _fallback_formula()

    normalized = normalized_input

    try:
        parsed_bonus = dice_engine.parse_formula(
            normalized,
            supported_faces=get_supported_faces(),
        )
    except dice_engine.FormulaError:
        parsed_bonus = None
    else:
        if parsed_bonus.total_dice > 0:
            return parsed_bonus.canonical()
        modifier = parsed_bonus.modifier
        normalized = f"{modifier:+d}" if modifier else ""

    if not normalized:
        return _fallback_formula()

    if "d" in normalized.lower():
        return normalized

    if normalized[0] not in "+-":
        normalized = f"+{normalized}"

    base_formula = None
    for candidate in (config.get("base"), get_default_formula(), "1d20"):
        if isinstance(candidate, str) and candidate.strip():
            base_formula = candidate.strip()
            break
    if not base_formula:
        base_formula = "1d20"

    context = _template_context(attack_bonus=normalized, base=base_formula)

    template = config.get("template")
    if isinstance(template, str) and template.strip():
        try:
            candidate = template.format(**context)
        except Exception:
            candidate = template
        canonical = canonicalize_formula(candidate)
        if canonical:
            return canonical
        return candidate

    if "{bonus" in base_formula:
        try:
            candidate = base_formula.format(**context)
        except Exception:
            candidate = base_formula.replace("{bonus}", normalized)
    else:
        candidate = f"{base_formula}{normalized}"

    canonical = canonicalize_formula(candidate)
    if canonical:
        return canonical
    return candidate


def get_difficulty_definitions() -> Tuple[Mapping[str, Any], ...]:
    """Return static difficulty button definitions from the system config."""

    config = system_config.get_current_system_config()
    if not config:
        return tuple()
    raw = config.analyzer_config.get("difficulty_buttons")
    if isinstance(raw, Sequence):
        return tuple(entry for entry in raw if isinstance(entry, Mapping))
    return tuple()


__all__ = [
    "get_supported_faces",
    "get_default_formula",
    "canonicalize_formula",
    "get_rollable_default_formula",
    "get_default_roll_options",
    "make_attack_roll_formula",
    "get_difficulty_definitions",
]
