from app.onboarding.tours.new_gm_quickstart_tour import (
    build_new_gm_advanced_steps,
    build_new_gm_mvp_steps,
)


def test_new_gm_mvp_tour_has_5_steps_and_hands_on():
    steps = build_new_gm_mvp_steps()

    assert len(steps) == 5
    assert any(step.id.endswith("hands_on") for step in steps)
    summary = steps[-1]
    assert "Commencer une nouvelle campagne" in summary.description
    assert "Revoir le guide" in summary.description


def test_new_gm_advanced_tour_has_8_steps_and_hands_on():
    steps = build_new_gm_advanced_steps()

    assert len(steps) == 8
    hands_on_step = next(step for step in steps if step.id.endswith("hands_on"))
    assert "Action requise" in hands_on_step.description
