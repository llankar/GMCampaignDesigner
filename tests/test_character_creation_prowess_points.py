from modules.pcs.character_creation.prowess import calculate_feat_points_from_options


def test_calculate_feat_points_first_option_is_free_for_flat_options():
    options = ["Perce Armure", "Durée étendue"]
    assert calculate_feat_points_from_options(options) == 1


def test_calculate_feat_points_parses_variable_and_fixed_costs_from_options():
    options = [
        "Bonus dommages : 3 pt (+7)",
        "Perce Armure",
        "Durée étendue : 2 pt",
    ]
    assert calculate_feat_points_from_options(options) == 5
