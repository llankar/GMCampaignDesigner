from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable, List, Mapping, Pattern, Sequence, Tuple

from modules.dice import dice_engine
from modules.dice import dice_preferences
from modules.helpers import system_config as system_config_helper
from modules.helpers.logging_helper import log_debug, log_module_import, log_warning

log_module_import(__name__)


@dataclass(frozen=True)
class ParsedDifficulty:
    """Descriptor for a system-supplied difficulty roll button."""

    label: str
    formula: str
    descriptor: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"label": self.label, "formula": self.formula}
        if self.descriptor:
            data["descriptor"] = self.descriptor
        if self.notes:
            data["notes"] = self.notes
        return data


@dataclass
class ParsedAction:
    """Lightweight container describing a parsed inline combat action."""

    label: str
    attack_bonus: str | None
    attack_roll_formula: str | None
    damage_formula: str | None
    notes: str | None
    span: Tuple[int, int]
    source: str
    display_text: str
    attack_span: Tuple[int, int] | None
    damage_span: Tuple[int, int] | None
    difficulties: Tuple[ParsedDifficulty, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "attack_bonus": self.attack_bonus,
            "attack_roll_formula": self.attack_roll_formula,
            "damage_formula": self.damage_formula,
            "notes": self.notes,
            "range": self.span,
            "source": self.source,
            "display_text": self.display_text,
            "attack_span": self.attack_span,
            "damage_span": self.damage_span,
            "difficulties": [difficulty.to_dict() for difficulty in self.difficulties],
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


FALLBACK_ACTION_PATTERN = re.compile(
    r"(?P<label>[A-Za-zÀ-ÖØ-öø-ÿ'’()\-\/ ]{2,}?)\s+"
    r"(?P<attack>[+-]\d{1,3})\s+DM\s+"
    r"(?P<damage>[^\s,;:.]+(?:\s+[a-zà-öø-ÿ'’()\-\/]+)*)",
)


@dataclass(frozen=True)
class _DifficultyPattern:
    group: str | None = None
    label: str | None = None
    template: str | None = None
    formula: str | None = None
    descriptor: str | None = None
    notes_group: str | None = None


@dataclass(frozen=True)
class _ActionPattern:
    regex: Pattern[str]
    label_group: str | None
    attack_group: str | None
    damage_group: str | None
    notes_group: str | None
    difficulties: Tuple[_DifficultyPattern, ...]
    source: str


_PATTERN_CACHE_SLUG: str | None = None
_PATTERN_CACHE: Tuple[_ActionPattern, ...] = tuple()


def _coerce_group_name(value: Any, default: str | None) -> str | None:
    if value is None:
        return default
    if value is False:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _parse_regex_flags(metadata: Mapping[str, Any]) -> int:
    flags = 0
    ignore_case = metadata.get("ignore_case")
    if ignore_case is None or bool(ignore_case):
        flags |= re.IGNORECASE
    if metadata.get("multiline"):
        flags |= re.MULTILINE
    if metadata.get("dotall"):
        flags |= re.DOTALL
    raw_flags = metadata.get("flags")
    if isinstance(raw_flags, str):
        raw_flags = [raw_flags]
    if isinstance(raw_flags, Sequence):
        for flag_name in raw_flags:
            try:
                flag_value = getattr(re, str(flag_name).upper())
            except AttributeError:
                continue
            if isinstance(flag_value, int):
                flags |= flag_value
    return flags


def _parse_difficulty_specs(raw: Any) -> Tuple[_DifficultyPattern, ...]:
    if not isinstance(raw, Sequence):
        return tuple()
    specs: List[_DifficultyPattern] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        group = _coerce_group_name(entry.get("group"), None)
        label = entry.get("label") or entry.get("name")
        template = entry.get("template") or entry.get("formula_template")
        formula = entry.get("formula")
        descriptor = entry.get("descriptor")
        notes_group = _coerce_group_name(entry.get("notes_group"), None)
        specs.append(
            _DifficultyPattern(
                group=group,
                label=str(label).strip() if isinstance(label, str) and label else None,
                template=str(template).strip() if isinstance(template, str) and template else None,
                formula=str(formula).strip() if isinstance(formula, str) and formula else None,
                descriptor=str(descriptor).strip() if isinstance(descriptor, str) and descriptor else None,
                notes_group=notes_group,
            )
        )
    return tuple(spec for spec in specs if spec.group or spec.template or spec.formula or spec.label)


def _build_action_patterns(config) -> Tuple[_ActionPattern, ...]:
    patterns: List[_ActionPattern] = []
    if config:
        for entry in config.analyzer_patterns:
            metadata = dict(entry.metadata) if entry.metadata else {}
            try:
                regex = re.compile(entry.pattern, _parse_regex_flags(metadata))
            except re.error as exc:
                log_warning(
                    f"Ignoring analyzer pattern '{entry.name}': {exc}",
                    func_name="dice_markup._build_action_patterns",
                )
                continue
            patterns.append(
                _ActionPattern(
                    regex=regex,
                    label_group=_coerce_group_name(metadata.get("label_group"), "label"),
                    attack_group=_coerce_group_name(metadata.get("attack_group"), "attack"),
                    damage_group=_coerce_group_name(metadata.get("damage_group"), "damage"),
                    notes_group=_coerce_group_name(metadata.get("notes_group"), None),
                    difficulties=_parse_difficulty_specs(metadata.get("difficulties")),
                    source=entry.name,
                )
            )
    if not patterns:
        patterns.append(
            _ActionPattern(
                regex=FALLBACK_ACTION_PATTERN,
                label_group="label",
                attack_group="attack",
                damage_group="damage",
                notes_group=None,
                difficulties=tuple(),
                source="fallback",
            )
        )
    return tuple(patterns)


def _get_action_patterns() -> Tuple[_ActionPattern, ...]:
    global _PATTERN_CACHE_SLUG, _PATTERN_CACHE
    config = system_config_helper.get_current_system_config()
    slug = getattr(config, "slug", None)
    if slug != _PATTERN_CACHE_SLUG:
        _PATTERN_CACHE = _build_action_patterns(config)
        _PATTERN_CACHE_SLUG = slug
    return _PATTERN_CACHE


def invalidate_action_pattern_cache() -> None:
    """Clear any cached analyzer patterns so they reload on next access."""

    global _PATTERN_CACHE_SLUG, _PATTERN_CACHE
    _PATTERN_CACHE_SLUG = None
    _PATTERN_CACHE = tuple()


def _canonicalize_formula_text(value: str | None) -> str | None:
    return dice_preferences.canonicalize_formula(value)


def _build_template_context(
    attack_bonus: str | None,
    attack_roll: str | None,
    *,
    value: Any = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    bonus = (attack_bonus or "").strip()
    sign = bonus[0] if bonus and bonus[0] in "+-" else "+"
    bonus_value = bonus.lstrip("+-")
    base_roll = (attack_roll or "").strip()
    context: dict[str, str] = {
        "attack_bonus": bonus,
        "bonus": bonus,
        "bonus_value": bonus_value,
        "sign": sign,
        "attack_roll": base_roll,
        "base": base_roll,
        "value": str(value).strip() if value is not None else "",
    }
    if extra:
        for key, data in extra.items():
            if isinstance(data, str) and key not in context:
                context[key] = data
    return context


def _resolve_default_difficulties(
    attack_bonus: str | None,
    attack_roll: str | None,
) -> Tuple[ParsedDifficulty, ...]:
    difficulties: List[ParsedDifficulty] = []
    for entry in dice_preferences.get_difficulty_definitions():
        label_source = entry.get("label") or entry.get("name")
        label = str(label_source).strip() if isinstance(label_source, str) else ""
        template = entry.get("template") or entry.get("formula_template")
        formula_text = entry.get("formula")
        context = _build_template_context(attack_bonus, attack_roll, extra=entry)
        if isinstance(template, str) and template:
            try:
                formula_text = template.format(**context)
            except Exception:
                formula_text = template
        canonical = _canonicalize_formula_text(formula_text)
        if canonical is None:
            continue
        descriptor = entry.get("descriptor")
        notes = entry.get("notes")
        difficulties.append(
            ParsedDifficulty(
                label=label or "Difficulty",
                formula=canonical,
                descriptor=str(descriptor).strip() if isinstance(descriptor, str) and descriptor else None,
                notes=str(notes).strip() if isinstance(notes, str) and notes else None,
            )
        )
    return tuple(_deduplicate_difficulties(difficulties))


def _build_pattern_difficulties(
    match: re.Match[str],
    pattern: _ActionPattern,
    attack_bonus: str | None,
    attack_roll: str | None,
) -> Tuple[ParsedDifficulty, ...]:
    results: List[ParsedDifficulty] = []
    for spec in pattern.difficulties:
        value = None
        if spec.group:
            try:
                value = match.group(spec.group)
            except IndexError:
                value = None
        value_text = str(value).strip() if value is not None else ""
        context = _build_template_context(attack_bonus, attack_roll, value=value_text)
        formula_text = spec.formula
        if spec.template:
            try:
                formula_text = spec.template.format(**context)
            except Exception:
                formula_text = spec.template
        canonical = _canonicalize_formula_text(formula_text)
        if canonical is None:
            continue
        notes = None
        if spec.notes_group:
            try:
                notes_value = match.group(spec.notes_group)
            except IndexError:
                notes_value = None
            if notes_value:
                notes = str(notes_value).strip()
        descriptor = spec.descriptor
        results.append(
            ParsedDifficulty(
                label=str(spec.label or value_text or "Difficulty"),
                formula=canonical,
                descriptor=str(descriptor).strip() if isinstance(descriptor, str) and descriptor else None,
                notes=notes,
            )
        )
    return tuple(results)


def _deduplicate_difficulties(
    difficulties: Iterable[ParsedDifficulty],
) -> Tuple[ParsedDifficulty, ...]:
    unique: dict[Tuple[str, str], ParsedDifficulty] = {}
    ordered: List[ParsedDifficulty] = []
    for difficulty in difficulties:
        key = (difficulty.label, difficulty.formula)
        if key in unique:
            continue
        unique[key] = difficulty
        ordered.append(difficulty)
    return tuple(ordered)


def _combine_difficulties(
    *groups: Iterable[ParsedDifficulty],
) -> Tuple[ParsedDifficulty, ...]:
    combined: List[ParsedDifficulty] = []
    for group in groups:
        combined.extend(list(group))
    return _deduplicate_difficulties(combined)


def _spans_overlap(left: Tuple[int, int], right: Tuple[int, int]) -> bool:
    return not (left[1] <= right[0] or right[1] <= left[0])


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
    current_offset = 0

    log_debug(
        f"parse_inline_actions - starting parse: length={length}",
        func_name="dice_markup.parse_inline_actions",
    )

    while cursor < length:
        start = text.find("[", cursor)
        if start == -1:
            trailing = text[cursor:]
            cleaned_segments.append(trailing)
            current_offset += len(trailing)
            log_debug(
                "parse_inline_actions - no more segments found; appended trailing text",
                func_name="dice_markup.parse_inline_actions",
            )
            break

        prefix = text[cursor:start]
        cleaned_segments.append(prefix)
        current_offset += len(prefix)
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
            current_offset += len(segment)
            break

        inner = text[start + 1 : end]
        log_debug(
            f"parse_inline_actions - found segment: span=({start}, {end + 1}) raw='{inner}'",
            func_name="dice_markup.parse_inline_actions",
        )
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
            current_offset += len(segment)
            cursor = end + 1
            continue

        action, error, replacement = _parse_segment(inner, segment_span, base_offset=current_offset)
        if error is not None:
            log_debug(
                f"parse_inline_actions - segment error: {error.message}",
                func_name="dice_markup.parse_inline_actions",
            )
            errors.append(error)
            log_warning(error.message, func_name="dice_markup.parse_inline_actions")
            fallback = text[start : end + 1]
            cleaned_segments.append(fallback)
            current_offset += len(fallback)
        elif action is not None:
            actions.append(action)
            replacement = replacement or ""
            cleaned_segments.append(replacement)
            current_offset += len(replacement)
            log_debug(
                "parse_inline_actions - segment parsed successfully; replacement length="
                f"{len(replacement)} span={action.span} display='{action.display_text}'",
                func_name="dice_markup.parse_inline_actions",
            )
        else:
            fallback = text[start : end + 1]
            cleaned_segments.append(fallback)
            current_offset += len(fallback)
            log_debug(
                "parse_inline_actions - segment ignored (no actionable content)",
                func_name="dice_markup.parse_inline_actions",
            )
        cursor = end + 1

    cleaned_text = "".join(cleaned_segments)

    if not actions:
        inferred = _infer_actions_from_plain_text(cleaned_text)
        if inferred:
            actions.extend(inferred)
    log_debug(
        f"parse_inline_actions - completed: actions={len(actions)} errors={len(errors)} cleaned_length={len(cleaned_text)}",
        func_name="dice_markup.parse_inline_actions",
    )
    return cleaned_text, [action.to_dict() for action in actions], [err.to_dict() for err in errors]


def _parse_segment(
    segment: str,
    span: Tuple[int, int],
    *,
    base_offset: int,
) -> tuple[ParsedAction | None, ParsedError | None, str | None]:
    trimmed = segment.strip()
    if not trimmed:
        return None, ParsedError(
            message="Dice markup is empty.",
            span=span,
            segment=f"[{segment}]",
        ), None

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
            return None, damage_error, None
    elif dm_damage_text:
        damage_formula_text, notes, damage_error = _extract_damage(dm_damage_text, span, segment)
        if damage_error is not None:
            return None, damage_error, None

    if attack_bonus_text is None and damage_formula_text is None:
        # Treat segments that don't contain an attack bonus or damage formula as
        # plain text. This allows large blocks of narrative text with only a
        # handful of embedded combat actions to validate successfully – parsing
        # should only fail when no actions are detected at all.
        return None, None, None

    label = label_text or "Action"
    display_text, attack_span, damage_span = _format_action_display(
        label=label,
        attack_bonus=attack_bonus_text,
        damage_formula=damage_formula_text,
        notes=notes,
        base_offset=base_offset,
    )

    difficulties = _resolve_default_difficulties(attack_bonus_text, attack_roll)

    action = ParsedAction(
        label=label,
        attack_bonus=attack_bonus_text,
        attack_roll_formula=attack_roll,
        damage_formula=damage_formula_text,
        notes=notes,
        span=span,
        source=f"[{segment}]",
        display_text=display_text,
        attack_span=attack_span,
        damage_span=damage_span,
        difficulties=difficulties,
    )
    return action, None, display_text


def _format_action_display(
    *,
    label: str,
    attack_bonus: str | None,
    damage_formula: str | None,
    notes: str | None,
    base_offset: int,
) -> tuple[str, Tuple[int, int] | None, Tuple[int, int] | None]:
    parts: List[str] = []
    attack_span: Tuple[int, int] | None = None
    damage_span: Tuple[int, int] | None = None

    current_length = 0

    def append(text: str) -> None:
        nonlocal current_length
        parts.append(text)
        current_length += len(text)

    def add_separator() -> None:
        if current_length > 0:
            append(" • ")

    label_text = str(label or "").strip()
    if label_text:
        append(label_text)

    if attack_bonus:
        add_separator()
        attack_text = f"Attack {attack_bonus.strip()}"
        start = current_length
        append(attack_text)
        attack_span = (base_offset + start, base_offset + current_length)

    if damage_formula:
        add_separator()
        damage_text = f"Damage {damage_formula.strip()}"
        if notes:
            damage_text = f"{damage_text} {notes.strip()}"
        start = current_length
        append(damage_text)
        damage_span = (base_offset + start, base_offset + current_length)
    elif notes:
        add_separator()
        append(notes.strip())

    display = "".join(parts)
    log_debug(
        "_format_action_display - constructed display="
        f"'{display}' attack_span={attack_span} damage_span={damage_span} base_offset={base_offset}",
        func_name="dice_markup._format_action_display",
    )
    if not display:
        display = label_text

    return display, attack_span, damage_span


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
        parsed = dice_engine.parse_formula(
            stripped, supported_faces=dice_preferences.get_supported_faces()
        )
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
    return dice_preferences.make_attack_roll_formula(attack_bonus)


def _coerce_text(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, dict):
        text = raw.get("text", "")
        return str(text or "")
    return str(raw)


def _infer_actions_from_plain_text(text: str) -> list[ParsedAction]:
    matches: List[tuple[int, re.Match[str], _ActionPattern]] = []
    for pattern in _get_action_patterns():
        for match in pattern.regex.finditer(text):
            matches.append((match.start(), match, pattern))

    matches.sort(key=lambda item: (item[0], item[1].end()))
    inferred_actions: List[ParsedAction] = []
    used_spans: List[Tuple[int, int]] = []

    for _start, match, pattern in matches:
        span = match.span()
        if any(_spans_overlap(span, other) for other in used_spans):
            continue
        action = _build_action_from_match(match, pattern)
        if action is None:
            continue
        inferred_actions.append(action)
        used_spans.append(span)

    return inferred_actions


def _build_action_from_match(match: re.Match[str], pattern: _ActionPattern) -> ParsedAction | None:
    segment_source = match.group(0)
    span = match.span()

    label_source = match.group(pattern.label_group) if pattern.label_group else segment_source
    label = str(label_source or "").strip()
    label = label.strip(" .:;•-")
    if not label:
        return None

    attack_bonus: str | None = None
    if pattern.attack_group:
        try:
            attack_source = match.group(pattern.attack_group) or ""
        except IndexError:
            attack_source = ""
        attack_bonus = _try_parse_formula(attack_source, force_sign=True)

    attack_roll = _make_attack_roll_formula(attack_bonus) if attack_bonus else None

    damage_formula: str | None = None
    notes: str | None = None
    if pattern.damage_group:
        try:
            damage_source = match.group(pattern.damage_group) or ""
        except IndexError:
            damage_source = ""
        damage_formula, notes, damage_error = _extract_damage(damage_source.strip(), span, segment_source)
        if damage_error is not None:
            return None

    if pattern.notes_group:
        try:
            extra_notes = match.group(pattern.notes_group)
        except IndexError:
            extra_notes = None
        if extra_notes:
            extra_text = str(extra_notes).strip()
            if extra_text:
                notes = f"{notes} {extra_text}".strip() if notes else extra_text

    difficulties = _combine_difficulties(
        _build_pattern_difficulties(match, pattern, attack_bonus, attack_roll),
        _resolve_default_difficulties(attack_bonus, attack_roll),
    )

    if attack_bonus is None and damage_formula is None and not difficulties:
        return None

    display_text, attack_span, damage_span = _format_action_display(
        label=label,
        attack_bonus=attack_bonus,
        damage_formula=damage_formula,
        notes=notes,
        base_offset=match.start(),
    )

    return ParsedAction(
        label=label,
        attack_bonus=attack_bonus,
        attack_roll_formula=attack_roll,
        damage_formula=damage_formula,
        notes=notes,
        span=span,
        source=segment_source,
        display_text=display_text,
        attack_span=attack_span,
        damage_span=damage_span,
        difficulties=difficulties,
    )
