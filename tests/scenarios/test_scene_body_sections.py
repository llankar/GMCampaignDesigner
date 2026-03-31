"""Regression tests for scene body sections."""

from modules.scenarios.widgets.scene_body_sections import _build_hero_text, _compute_wraplength


def test_build_hero_text_keeps_full_intro_without_truncation():
    """Verify that build hero text keeps full intro without truncation."""
    long_intro = (
        "Le shérif de Millfield, stupéfait par les révélations concernant la société secrète Eon, "
        "décide immédiatement de mettre en place une enquête. "
        "Il rassemble ses hommes les plus compétents et prépare une stratégie complète pour infiltrer le quartier souterrain."
    )

    assert _build_hero_text(long_intro, []) == long_intro


def test_compute_wraplength_reserves_right_side_gutter():
    """Verify that compute wraplength reserves right side gutter."""
    # 320px container with 12px left/right padding keeps a safety gutter
    # so the last characters of wrapped lines remain visible.
    assert _compute_wraplength(320, horizontal_padding=12, min_wrap=220) == 286


def test_compute_wraplength_honors_minimum_for_small_containers():
    """Verify that compute wraplength honors minimum for small containers."""
    assert _compute_wraplength(120, horizontal_padding=12, min_wrap=220) == 220
