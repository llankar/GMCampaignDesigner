from modules.scenarios.gm_screen.virtual_desk.zone_helpers import (
    apply_tab_zone_metadata,
    sanitize_tab_zone,
)


def test_sanitize_tab_zone_falls_back_to_center_for_invalid_values():
    assert sanitize_tab_zone("RIGHT") == "right"
    assert sanitize_tab_zone("unknown") == "center"
    assert sanitize_tab_zone(None, fallback="invalid") == "center"


def test_apply_tab_zone_metadata_sets_zone_and_state():
    meta = {}
    assert apply_tab_zone_metadata(meta, "bottom") == "bottom"
    assert meta["ui_zone"] == "bottom"
    assert meta["ui_state"] == "docked"

    assert apply_tab_zone_metadata(meta, "oops") == "center"
    assert meta["ui_zone"] == "center"
    assert meta["ui_state"] == "normal"
