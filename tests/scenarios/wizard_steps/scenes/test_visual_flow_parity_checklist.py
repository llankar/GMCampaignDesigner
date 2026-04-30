from modules.scenarios.wizard_steps.scenes.visual_flow.commands import (
    make_create_link_command,
    make_delete_node_command,
    make_update_link_command,
)
from modules.scenarios.wizard_steps.scenes.visual_flow.interactions import (
    normalise_link_selection,
    normalise_single_selection,
    resolve_link_target,
    should_open_context_menu,
)


def test_parity_selection_semantics_are_exclusive():
    node_id, link_id = normalise_single_selection("n1")
    assert node_id == "n1"
    assert link_id is None

    node_id, link_id = normalise_link_selection("l1")
    assert node_id is None
    assert link_id == "l1"


def test_parity_context_menu_click_timing():
    assert should_open_context_menu(3, 0.0, 0.1)
    assert not should_open_context_menu(3, 0.0, 0.5)
    assert not should_open_context_menu(1, 0.0, 0.1)


def test_parity_link_drag_target_resolution():
    assert resolve_link_target("a", ["", "a", "b"]) == "b"
    assert resolve_link_target("a", ["a", ""]) is None


def test_parity_delete_update_command_contracts_undo_ready():
    delete_cmd = make_delete_node_command(node_id="a", removed_node={"id": "a"}, removed_links=[{"id": "a-b"}])
    assert delete_cmd.changed is True
    assert delete_cmd.before["node"]["id"] == "a"

    update_cmd = make_update_link_command(link_id="a-b", before={"label": "A"}, after={"label": "B"})
    assert update_cmd.changed is True
    assert update_cmd.before["link_id"] == "a-b"

    create_cmd = make_create_link_command(source_id="a", target_id="b", link_payload={"id": "a-b"})
    assert create_cmd.changed is True
    assert create_cmd.after["target"] == "b"
