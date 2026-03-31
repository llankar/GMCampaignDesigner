"""Regression tests for character creation prowess points."""

from modules.pcs.character_creation.prowess import calculate_feat_points_from_options


def test_calculate_feat_points_sums_all_flat_option_costs():
    """Verify that calculate feat points sums all flat option costs."""
    options = ["Perce Armure", "Durée étendue"]
    assert calculate_feat_points_from_options(options) == 2


def test_calculate_feat_points_single_option_costs_one_point():
    """Verify that calculate feat points single option costs one point."""
    options = ["Perce Armure"]
    assert calculate_feat_points_from_options(options) == 1


def test_calculate_feat_points_parses_variable_and_fixed_costs_from_options():
    """Verify that calculate feat points parses variable and fixed costs from options."""
    options = [
        "Bonus dommages : 3 pt (+7)",
        "Perce Armure",
        "Durée étendue : 2 pt",
    ]
    assert calculate_feat_points_from_options(options) == 6
