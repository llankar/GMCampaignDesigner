from modules.ui.ambiance import monitor


def test_select_target_monitor_uses_secondary(monkeypatch):
    monkeypatch.setattr(monitor, "_get_monitors", lambda: [(0, 0, 1920, 1080), (1920, 0, 1280, 1024)])

    selected = monitor.select_target_monitor()

    assert (selected.x, selected.y, selected.width, selected.height) == (1920, 0, 1280, 1024)
    assert selected.is_secondary is True


def test_select_target_monitor_single_screen_without_fallback(monkeypatch):
    monkeypatch.setattr(monitor, "_get_monitors", lambda: [(0, 0, 1920, 1080)])

    try:
        monitor.select_target_monitor(allow_single_screen_fallback=False)
    except monitor.MonitorSelectionError as exc:
        assert "un seul écran" in str(exc)
    else:
        raise AssertionError("Expected MonitorSelectionError")


def test_select_target_monitor_uses_preferred_index(monkeypatch):
    monkeypatch.setattr(
        monitor,
        "_get_monitors",
        lambda: [(0, 0, 1920, 1080), (1920, 0, 1280, 1024), (3200, 0, 1600, 900)],
    )

    selected = monitor.select_target_monitor(preferred_index=2)

    assert (selected.x, selected.y, selected.width, selected.height) == (3200, 0, 1600, 900)
    assert selected.is_secondary is True
