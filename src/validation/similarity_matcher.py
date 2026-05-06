"""Similarity matching helpers for validator reference resolution.

The module keeps fuzzy matching deterministic and side-effect free so validator
callers can safely use it to propose corrections without mutating campaign data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

_PUNCTUATION_RE = re.compile(r"[\W_]+", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


class SimilarityDecision(str, Enum):
    """Decision bands returned by the similarity matcher."""

    STRONG_MATCH = "STRONG_MATCH"
    AMBIGUOUS = "AMBIGUOUS"
    NO_MATCH = "NO_MATCH"


@dataclass(frozen=True)
class SimilarityMatcherConfig:
    """Thresholds used to classify similarity results.

    Attributes:
        strong_match_threshold: Minimum score for an automatic, high-confidence
            match when no close competitor exists.
        ambiguity_threshold: Minimum score for showing candidates as plausible
            but requiring a human decision.
        ambiguity_margin: Maximum score gap between the two best candidates that
            still counts as ambiguous, even when the best score is strong.
    """

    strong_match_threshold: float = 0.88
    ambiguity_threshold: float = 0.72
    ambiguity_margin: float = 0.05


@dataclass(frozen=True)
class SimilarityCandidate:
    """Minimal candidate shape accepted by validator-facing APIs."""

    entity_type: str
    identifier: str
    label: str = ""
    payload: Any = None

    @property
    def display_name(self) -> str:
        """Return the best user-facing name for this candidate."""

        return self.label or self.identifier


@dataclass(frozen=True)
class SimilarityMatch:
    """Scored candidate returned by the matcher."""

    candidate: SimilarityCandidate
    score: float
    matched_text: str


@dataclass(frozen=True)
class SimilarityMatchResult:
    """Decision and sorted matches for one query."""

    query: str
    expected_type: str
    decision: SimilarityDecision
    matches: tuple[SimilarityMatch, ...] = field(default_factory=tuple)

    @property
    def best_match(self) -> SimilarityMatch | None:
        """Return the top-scoring match, if any."""

        return self.matches[0] if self.matches else None


CandidateInput = Any


def normalize_similarity_text(value: Any) -> str:
    """Normalize text before exact or fuzzy comparison.

    Normalization intentionally removes sources of cosmetic mismatch:
    lowercasing, accents/diacritics, punctuation, and repeated whitespace.
    """

    if value is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value).casefold())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    without_punctuation = _PUNCTUATION_RE.sub(" ", without_accents)
    return _WHITESPACE_RE.sub(" ", without_punctuation).strip()


def score_similarity(left: Any, right: Any) -> float:
    """Return a deterministic proximity score between 0.0 and 1.0."""

    normalized_left = normalize_similarity_text(left)
    normalized_right = normalize_similarity_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def match_reference(
    query: Any,
    expected_type: str,
    candidates: Iterable[CandidateInput],
    *,
    config: SimilarityMatcherConfig | None = None,
    limit: int | None = None,
) -> SimilarityMatchResult:
    """Score candidates of the expected type and return a decision.

    Candidates are filtered by ``expected_type`` before any scoring happens.
    Results are sorted by descending score, then by stable candidate metadata so
    UIs and validators get reproducible ordering.
    """

    active_config = config or SimilarityMatcherConfig()
    normalized_expected_type = normalize_similarity_text(expected_type)
    canonical_query = normalize_similarity_text(query)
    if not canonical_query or not normalized_expected_type:
        return SimilarityMatchResult(
            query=str(query or ""),
            expected_type=normalized_expected_type,
            decision=SimilarityDecision.NO_MATCH,
        )

    all_matches = tuple(
        sorted(
            _iter_scored_matches(canonical_query, normalized_expected_type, candidates),
            key=_match_sort_key,
        )
    )
    decision = classify_similarity_matches(all_matches, config=active_config)
    visible_matches = all_matches
    if limit is not None:
        visible_matches = visible_matches[: max(limit, 0)]

    return SimilarityMatchResult(
        query=str(query),
        expected_type=normalized_expected_type,
        decision=decision,
        matches=visible_matches,
    )


def classify_similarity_matches(
    matches: Sequence[SimilarityMatch],
    *,
    config: SimilarityMatcherConfig | None = None,
) -> SimilarityDecision:
    """Classify sorted matches into strong, ambiguous, or no-match bands."""

    active_config = config or SimilarityMatcherConfig()
    if not matches:
        return SimilarityDecision.NO_MATCH

    best_score = matches[0].score
    if best_score < active_config.ambiguity_threshold:
        return SimilarityDecision.NO_MATCH

    if (
        best_score >= active_config.strong_match_threshold
        and not _has_close_competitor(matches, active_config.ambiguity_margin)
    ):
        return SimilarityDecision.STRONG_MATCH

    return SimilarityDecision.AMBIGUOUS


def _iter_scored_matches(
    normalized_query: str,
    normalized_expected_type: str,
    candidates: Iterable[CandidateInput],
) -> Iterable[SimilarityMatch]:
    for raw_candidate in candidates:
        candidate = coerce_similarity_candidate(raw_candidate)
        if normalize_similarity_text(candidate.entity_type) != normalized_expected_type:
            continue
        scored_options = tuple(
            _score_candidate_text(normalized_query, text)
            for text in _candidate_scored_texts(candidate)
            if normalize_similarity_text(text)
        )
        if not scored_options:
            continue
        matched_text, score = max(
            scored_options,
            key=lambda item: (item[1], normalize_similarity_text(item[0])),
        )
        yield SimilarityMatch(
            candidate=candidate,
            score=score,
            matched_text=matched_text,
        )


def _score_candidate_text(normalized_query: str, text: str) -> tuple[str, float]:
    normalized_text = normalize_similarity_text(text)
    if normalized_text == normalized_query:
        return text, 1.0
    return text, SequenceMatcher(None, normalized_query, normalized_text).ratio()


def coerce_similarity_candidate(candidate: CandidateInput) -> SimilarityCandidate:
    """Convert validator entities, mappings, or custom objects into candidates."""

    if isinstance(candidate, SimilarityCandidate):
        return candidate

    entity_type = _read_candidate_value(candidate, "entity_type")
    identifier = _read_candidate_value(candidate, "identifier")
    label = _read_candidate_value(candidate, "label")
    if not label:
        label = _read_candidate_value(candidate, "name")
    return SimilarityCandidate(
        entity_type=str(entity_type or ""),
        identifier=str(identifier or label or ""),
        label=str(label or ""),
        payload=candidate,
    )


def _read_candidate_value(candidate: CandidateInput, key: str) -> Any:
    if isinstance(candidate, Mapping):
        return candidate.get(key)
    return getattr(candidate, key, None)


def _candidate_scored_texts(candidate: SimilarityCandidate) -> tuple[str, ...]:
    values = (candidate.identifier, candidate.label, candidate.display_name)
    return tuple(dict.fromkeys(value for value in values if value))


def _match_sort_key(match: SimilarityMatch) -> tuple[float, str, str, str]:
    candidate = match.candidate
    return (
        -match.score,
        normalize_similarity_text(candidate.display_name),
        normalize_similarity_text(candidate.identifier),
        normalize_similarity_text(candidate.entity_type),
    )


def _has_close_competitor(
    matches: Sequence[SimilarityMatch],
    ambiguity_margin: float,
) -> bool:
    if len(matches) < 2:
        return False
    return (matches[0].score - matches[1].score) <= ambiguity_margin
