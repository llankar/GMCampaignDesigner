from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Tuple

from modules.dice import dice_engine
from modules.helpers.logging_helper import log_module_import, log_warning

log_module_import(__name__)


@dataclass(frozen=True)
class ParsedAction:
    """Lightweight container describing a parsed inline combat action."""

    label: str
    attack_bonus: str | None
    attack_roll_formula: str | None
    damage_formula: str | None
    notes: str | None
    span: Tuple[int, int]
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "attack_bonus": self.attack_bonus,
            "attack_roll_formula": self.attack_roll_formula,
            "damage_formula": self.damage_formula,
            "notes": self.notes,
            "range": self.span,
            "source": self.source,
        }


@dataclass(frozen=True)
class ParsedError:
    """Structured representation of a validation issue in inline markup."""

    message: str
    span: Tuple[int, int]
    segment: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "range": self.span,
            "segment": self.segment,
        }


def parse_inline_actions(raw_text: Any) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract inline combat actions from a block of text.

    Returns a tuple ``(display_text, actions, errors)`` where ``display_text`` is the
    original text with markup removed, ``actions`` is a list of dictionaries describing
    parsed actions, and ``errors`` captures any validation issues encountered.
    """

    text = _coerce_text(raw_text)
    if not text:
        return "", [], []

    cleaned_segments: List[str] = []
    actions: List[ParsedAction] = []
    errors: List[ParsedError] = []

    cursor = 0
    length = len(text)

    while cursor < length:
        start = text.find("[", cursor)
        if start == -1:
            cleaned_segments.append(text[cursor:])
            break

        cleaned_segments.append(text[cursor:start])
        end = text.find("]", start + 1)
        if end == -1:
            segment = text[start:]
            error = ParsedError(
                message="Unclosed dice markup segment.",
                span=(start, length),
                segment=segment,
            )
            errors.append(error)
            log_warning(error.message, func_name="dice_markup.parse_inline_actions")
            cleaned_segments.append(segment)
            break

        inner = text[start + 1 : end]
        segment_span = (start, end + 1)
        if "[" in inner:
            segment = text[start : end + 1]
            error = ParsedError(
                message="Nested '[' detected inside dice markup. Escape or remove nested brackets.",
                span=segment_span,
                segment=segment,
            )
            errors.append(error)
            log_warning(error.message, func_name="dice_markup.parse_inline_actions")
            cleaned_segments.append(segment)
            cursor = end + 1
            continue

        action, error = _parse_segment(inner, segment_span)
        if error is not None:
            errors.append(error)
            log_warning(error.message, func_name="dice_markup.parse_inline_actions")
            cleaned_segments.append(text[start : end + 1])
        elif action is not None:
            actions.append(action)
            replacement = action.label
            if action.notes:
                replacement = f"{replacement} ({action.notes})"
            cleaned_segments.append(replacement)
        else:
            cleaned_segments.append(text[start : end + 1])
        cursor = end + 1

    cleaned_text = "".join(cleaned_segments)
    return cleaned_text, [action.to_dict() for action in actions], [err.to_dict() for err in errors]


def _parse_segment(segment: str, span: Tuple[int, int]) -> tuple[ParsedAction | None, ParsedError | None]:
    trimmed = segment.strip()
    if not trimmed:
        return None, ParsedError(
            message="Dice markup is empty.",
            span=span,
            segment=f"[{segment}]",
        )

    if "|" in trimmed:
        left, right = trimmed.split("|", 1)
    else:
        left, right = trimmed, ""

    left_without_dm, dm_damage_text = _split_dm_damage(left)
    label_text, attack_bonus_text, attack_roll = _extract_label_and_attack(left_without_dm.strip())

    damage_formula_text: str | None = None
    notes: str | None = None
    if right.strip():
        damage_formula_text, notes, damage_error = _extract_damage(right.strip(), span, segment)
        if damage_error is not None:
            return None, damage_error
    elif dm_damage_text:
        damage_formula_text, notes, damage_error = _extract_damage(dm_damage_text, span, segment)
        if damage_error is not None:
            return None, damage_error

    if attack_bonus_text is None and damage_formula_text is None:
        # Treat segments that don't contain an attack bonus or damage formula as
        # plain text. This allows large blocks of narrative text with only a
        # handful of embedded combat actions to validate successfully – parsing
        # should only fail when no actions are detected at all.
        return None, None

    label = label_text or "Action"
    return (
        ParsedAction(
            label=label,
            attack_bonus=attack_bonus_text,
            attack_roll_formula=attack_roll,
            damage_formula=damage_formula_text,
            notes=notes,
            span=span,
            source=f"[{segment}]",
        ),
        None,
    )


def _extract_label_and_attack(left: str) -> tuple[str, str | None, str | None]:
    if not left:
        return "", None, None

    tokens = left.split()
    attack_bonus_text: str | None = None
    attack_roll_formula: str | None = None
    label = left

    if tokens:
        candidate = tokens[-1]
        parsed_bonus = _try_parse_formula(candidate, force_sign=True)
        if parsed_bonus is not None:
            attack_bonus_text = parsed_bonus
            label = left[: left.rfind(candidate)].strip()
            attack_roll_formula = _make_attack_roll_formula(parsed_bonus)

    return label, attack_bonus_text, attack_roll_formula


def _extract_damage(right: str, span: Tuple[int, int], segment: str) -> tuple[str | None, str | None, ParsedError | None]:
    if not right:
        return None, None, None

    formula_part = right
    notes_part: str | None = None
    if " " in right:
        first, remainder = right.split(" ", 1)
        if remainder.strip():
            formula_part = first
            notes_part = remainder.strip()

    trimmed_formula = formula_part.strip()
    normalized: str | None = None

    if trimmed_formula and trimmed_formula.startswith("+") and "d" not in trimmed_formula.lower():
        bonus_text = _try_parse_formula(trimmed_formula, force_sign=True)
        if bonus_text is not None:
            normalized = _make_attack_roll_formula(bonus_text)

    if normalized is None:
        normalized = _try_parse_formula(formula_part, force_sign=False)

    if normalized is None:
        return None, None, ParsedError(
            message=f"Invalid damage formula '{formula_part}'.",
            span=span,
            segment=f"[{segment}]",
        )

    return normalized, notes_part, None


def _split_dm_damage(text: str) -> tuple[str, str | None]:
    tokens = text.split()
    if not tokens:
        return text, None

    for idx, token in enumerate(tokens):
        if token.upper() == "DM":
            attack_tokens = tokens[:idx]
            damage_tokens = tokens[idx + 1 :]
            attack_part = " ".join(attack_tokens).strip()
            damage_part = " ".join(damage_tokens).strip() or None
            return attack_part, damage_part

    return text, None


def _try_parse_formula(formula: str, *, force_sign: bool) -> str | None:
    stripped = formula.strip()
    if not stripped:
        return None
    try:
        parsed = dice_engine.parse_formula(stripped)
    except dice_engine.FormulaError:
        return None
    return _format_parsed_formula(parsed, force_sign=force_sign)


def _format_parsed_formula(parsed: dice_engine.ParsedFormula, *, force_sign: bool) -> str:
    dice_segments: List[str] = []
    for faces in sorted(parsed.dice):
        count = parsed.dice[faces]
        if count == 1:
            dice_segments.append(f"1d{faces}")
        else:
            dice_segments.append(f"{count}d{faces}")

    modifier = parsed.modifier
    if dice_segments:
        parts = ["+".join(dice_segments)]
        if modifier:
            if modifier > 0:
                parts.append(f"+{modifier}")
            else:
                parts.append(str(modifier))
        return "".join(parts)

    if modifier > 0:
        return f"+{modifier}" if force_sign else str(modifier)
    if modifier < 0:
        return str(modifier)
    return "+0" if force_sign else "0"


def _make_attack_roll_formula(attack_bonus: str) -> str:
    normalized = attack_bonus.strip()
    if not normalized:
        return "1d20"
    if "d" in normalized.lower():
        return normalized
    if normalized[0] not in "+-":
        normalized = f"+{normalized}"
    return f"1d20{normalized}"


def _coerce_text(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, dict):
        text = raw.get("text", "")
        return str(text or "")
    return str(raw)
