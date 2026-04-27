from modules.ui.ambiance.monitor_selector import normalize_target_monitor


def test_primary_monitor_index_zero_is_valid() -> None:
    target, warning = normalize_target_monitor(0, 1)
    assert target == 0
    assert warning is None


def test_secondary_falls_back_when_unavailable() -> None:
    target, warning = normalize_target_monitor(1, 1)
    assert target == 0
    assert warning == "Secondary monitor not detected, using primary monitor."


def test_invalid_index_falls_back_to_primary() -> None:
    target, warning = normalize_target_monitor(-3, 2)
    assert target == 0
    assert warning == "Invalid monitor index, using primary monitor."
