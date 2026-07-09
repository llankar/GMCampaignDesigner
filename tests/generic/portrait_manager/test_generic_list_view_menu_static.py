from pathlib import Path

SOURCE = Path("modules/generic/generic_list_view.py").read_text()

def test_scenario_context_menu_contains_generate_portraits_only_in_scenario_branch():
    scenario_branch = SOURCE.split('if self.model_wrapper.entity_type == "scenarios":', 1)[1].split('if item:', 1)[0]
    non_scenario_prefix = SOURCE.split('if self.model_wrapper.entity_type == "scenarios":', 1)[0]
    assert 'label="Generate Portraits..."' in scenario_branch
    assert 'open_scenario_portrait_manager(iid)' in scenario_branch
    assert 'Generate Portraits...' not in non_scenario_prefix
