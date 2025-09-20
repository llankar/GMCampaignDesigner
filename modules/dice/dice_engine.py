"""Non-UI dice rolling engine with reusable parsing and roll helpers."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Tuple

from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

DEFAULT_DICE_SIZES: Tuple[int, ...] = (4, 6, 8, 10, 12, 20)


class DiceEngineError(Exception):
    """Base class for dice engine related errors."""


class FormulaError(ValueError, DiceEngineError):
    """Raised when a dice formula cannot be parsed."""


class RollError(DiceEngineError):
    """Raised when a roll cannot be completed."""


@dataclass(frozen=True)
class ParsedFormula:
    """Immutable representation of a parsed dice formula."""

    dice: Mapping[int, int]
    modifier: int = 0

    def __post_init__(self) -> None:
        normalized = {int(faces): int(count) for faces, count in dict(self.dice).items() if int(count) != 0}
        object.__setattr__(self, "dice", MappingProxyType(normalized))

    @property
    def total_dice(self) -> int:
        return sum(self.dice.values())

    def canonical(self) -> str:
        return format_formula(self.dice, self.modifier)


@dataclass(frozen=True)
class DieRoll:
    """Represents the outcome of a single die throw."""

    value: int
    exploded: bool = False


@dataclass(frozen=True)
class DieRollChain:
    """Represents the sequence of rolls for a single die, including explosions."""

    faces: int
    rolls: Tuple[DieRoll, ...]

    @property
    def total(self) -> int:
        return sum(roll.value for roll in self.rolls)

    @property
    def display_values(self) -> Tuple[str, ...]:
        return tuple(f"{roll.value}{'!' if roll.exploded else ''}" for roll in self.rolls)


@dataclass(frozen=True)
class FaceRollSummary:
    """Aggregated results for all dice of the same size in a roll."""

    faces: int
    base_count: int
    rolls: Tuple[DieRoll, ...]

    @property
    def total(self) -> int:
        return sum(roll.value for roll in self.rolls)

    @property
    def display_values(self) -> Tuple[str, ...]:
        return tuple(f"{roll.value}{'!' if roll.exploded else ''}" for roll in self.rolls)


@dataclass(frozen=True)
class RollResult:
    """Structured outcome of evaluating a parsed dice formula."""

    parsed: ParsedFormula
    chains: Tuple[DieRollChain, ...]
    face_summaries: Tuple[FaceRollSummary, ...]
    subtotal: int
    total: int

    @property
    def modifier(self) -> int:
        return self.parsed.modifier

    def canonical(self) -> str:
        return self.parsed.canonical()

    def totals_by_face(self) -> Mapping[int, int]:
        return {summary.faces: summary.total for summary in self.face_summaries}

    def display_values_by_face(self) -> Mapping[int, Tuple[str, ...]]:
        return {summary.faces: summary.display_values for summary in self.face_summaries}


def parse_formula(formula: str, *, supported_faces: Iterable[int] | None = None) -> ParsedFormula:
    """Parse a textual dice formula into a :class:`ParsedFormula`."""

    cleaned = formula.replace(" ", "").lower()
    if not cleaned:
        raise FormulaError("Please provide a dice formula.")

    allowed_faces = set(int(face) for face in supported_faces) if supported_faces is not None else None

    tokens: list[tuple[str, str]] = []
    current = ""
    sign = "+"
    for char in cleaned:
        if char in "+-":
            if current:
                tokens.append((sign, current))
                current = ""
            sign = char
        else:
            current += char
    if current:
        tokens.append((sign, current))

    dice: dict[int, int] = {}
    modifier = 0
    seen_dice_segment = False

    for sign, token in tokens:
        if not token:
            raise FormulaError("Formula contains an empty segment.")
        if "d" in token:
            count_str, _, faces_str = token.partition("d")
            if not faces_str:
                raise FormulaError("Missing die size in formula.")
            try:
                count = int(count_str) if count_str else 1
            except ValueError as exc:  # pragma: no cover - defensive
                raise FormulaError(str(exc)) from None
            try:
                faces = int(faces_str)
            except ValueError as exc:  # pragma: no cover - defensive
                raise FormulaError(str(exc)) from None
            if allowed_faces is not None and faces not in allowed_faces:
                raise FormulaError(f"d{faces} is not supported.")
            if count <= 0:
                raise FormulaError("Dice count must be positive.")
            sign_multiplier = -1 if sign == "-" else 1
            dice[faces] = dice.get(faces, 0) + sign_multiplier * count
            seen_dice_segment = True
        else:
            try:
                value = int(token)
            except ValueError as exc:  # pragma: no cover - defensive
                raise FormulaError(str(exc)) from None
            sign_multiplier = -1 if sign == "-" else 1
            modifier += sign_multiplier * value

    dice = {faces: count for faces, count in dice.items() if count != 0}
    for faces, count in dice.items():
        if count < 0:
            raise FormulaError(f"Negative dice counts detected for d{faces}.")

    if not dice and seen_dice_segment:
        raise FormulaError("All dice cancelled out. Adjust the formula.")

    return ParsedFormula(dice=dice, modifier=modifier)


def format_formula(dice: Mapping[int, int], modifier: int) -> str:
    """Return a canonical textual representation for a dice formula."""

    parts: list[str] = []
    for faces in sorted(dice):
        count = dice[faces]
        if count <= 0:
            continue
        token = f"{count}d{faces}" if count != 1 else f"1d{faces}"
        parts.append(token)
    if modifier:
        sign = "+" if modifier > 0 else "-"
        parts.append(f"{sign} {abs(modifier)}")
    if not parts:
        return "0"
    formatted = " + ".join(parts)
    return formatted.replace("+ -", "- ")


def roll_parsed_formula(
    parsed: ParsedFormula,
    *,
    explode: bool = False,
    rng: random.Random | None = None,
) -> RollResult:
    """Roll an already parsed formula and return a :class:`RollResult`."""

    if parsed.total_dice <= 0:
        raise RollError("Please include at least one die in the formula.")

    generator = rng or random
    if not hasattr(generator, "randint"):
        raise TypeError("rng must provide a randint method.")

    chains: list[DieRollChain] = []
    per_face_rolls: dict[int, list[DieRoll]] = defaultdict(list)

    for faces in sorted(parsed.dice):
        count = parsed.dice[faces]
        for _ in range(count):
            chain_rolls: list[DieRoll] = []
            keep_rolling = True
            while keep_rolling:
                value = generator.randint(1, faces)
                exploded = explode and faces > 1 and value == faces
                die_roll = DieRoll(value=value, exploded=exploded)
                chain_rolls.append(die_roll)
                per_face_rolls[faces].append(die_roll)
                keep_rolling = exploded
            chains.append(DieRollChain(faces=faces, rolls=tuple(chain_rolls)))

    subtotal = sum(chain.total for chain in chains)
    face_summaries = []
    for faces in sorted(parsed.dice):
        rolls = tuple(per_face_rolls.get(faces, ()))
        face_summaries.append(
            FaceRollSummary(
                faces=faces,
                base_count=parsed.dice[faces],
                rolls=rolls,
            )
        )

    total = subtotal + parsed.modifier
    return RollResult(
        parsed=parsed,
        chains=tuple(chains),
        face_summaries=tuple(face_summaries),
        subtotal=subtotal,
        total=total,
    )


def roll_formula(
    formula: str,
    *,
    explode: bool = False,
    supported_faces: Iterable[int] | None = None,
    rng: random.Random | None = None,
) -> RollResult:
    """Convenience helper that parses and rolls a formula in one go."""

    parsed = parse_formula(formula, supported_faces=supported_faces)
    return roll_parsed_formula(parsed, explode=explode, rng=rng)
