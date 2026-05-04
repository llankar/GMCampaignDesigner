from app.onboarding.tours.new_gm_quickstart_tour import (
    build_new_gm_advanced_steps,
    build_new_gm_mvp_steps,
)


def test_new_gm_mvp_tour_has_5_steps_and_hands_on():
    steps = build_new_gm_mvp_steps()

    assert len(steps) == 26
    assert any(step.id.endswith("create_scenario_for_arc") for step in steps)
    assert any(step.screen == "editor_npcs" and step.target_widget_key == "btn_portrait_add" for step in steps)
    assert any(step.screen == "editor_places" and step.target_widget_key == "btn_portrait_add" for step in steps)
    assert steps[0].target_widget_key == "input_campaign_name"
    assert steps[-1].id == "new_gm_mvp.place_save"


def test_new_gm_advanced_tour_has_8_steps_and_hands_on():
    steps = build_new_gm_advanced_steps()

    assert len(steps) == 6
    assert steps[0].target_widget_key == "btn_new_campaign"
    assert any(step.target_widget_key == "btn_add_arc" for step in steps)
