"""Regression tests for validator similarity matching."""

from src.validation import (
    SimilarityCandidate,
    SimilarityDecision,
    SimilarityMatcherConfig,
    match_reference,
    normalize_similarity_text,
    score_similarity,
)
from src.validation.reference_validator import EntityRecord


def test_normalize_similarity_text_removes_case_accents_punctuation_and_extra_spaces():
    assert normalize_similarity_text("  Épée-du Roi!!!  ") == "epee du roi"


def test_score_similarity_returns_full_score_after_cosmetic_normalization():
    assert score_similarity("L'Épée du Roi", "l epee du roi") == 1.0


def test_match_reference_filters_expected_type_before_scoring_and_sorts_results():
    candidates = [
        SimilarityCandidate(entity_type="npc", identifier="mara", label="Mara Jade"),
        SimilarityCandidate(
            entity_type="place",
            identifier="mara-shrine",
            label="Mara Shrine",
        ),
        SimilarityCandidate(entity_type="npc", identifier="marra", label="Mara Jadde"),
    ]

    result = match_reference("Mara Jade", "npc", candidates)

    assert result.decision == SimilarityDecision.STRONG_MATCH
    assert [match.candidate.entity_type for match in result.matches] == ["npc", "npc"]
    assert [match.candidate.identifier for match in result.matches] == ["mara", "marra"]
    assert result.matches[0].score >= result.matches[1].score


def test_match_reference_marks_close_high_scores_as_ambiguous():
    candidates = [
        SimilarityCandidate(entity_type="scenario", identifier="s1", label="Dawnspire Heist"),
        SimilarityCandidate(entity_type="scenario", identifier="s2", label="Dawnspire Feast"),
    ]

    result = match_reference(
        "Dawnspire Hest",
        "scenario",
        candidates,
        config=SimilarityMatcherConfig(
            strong_match_threshold=0.85,
            ambiguity_threshold=0.70,
            ambiguity_margin=0.12,
        ),
    )

    assert result.decision == SimilarityDecision.AMBIGUOUS
    assert [match.candidate.identifier for match in result.matches] == ["s1", "s2"]


def test_match_reference_returns_no_match_below_ambiguity_threshold():
    result = match_reference(
        "Completely Different",
        "arc",
        [SimilarityCandidate(entity_type="arc", identifier="a1", label="Quiet Road")],
        config=SimilarityMatcherConfig(ambiguity_threshold=0.80),
    )

    assert result.decision == SimilarityDecision.NO_MATCH


def test_match_reference_accepts_validator_entity_records_as_candidates():
    entity = EntityRecord(
        entity_type="npc",
        identifier="captain-voss",
        label="Captain Voss",
        node={},
        path=("npc:captain-voss",),
        parent_path=(),
        parent_type=None,
        parent_identifier=None,
        order=0,
    )

    result = match_reference("Captain Vos", "npc", [entity])

    assert result.decision == SimilarityDecision.STRONG_MATCH
    assert result.best_match is not None
    assert result.best_match.candidate.payload is entity
