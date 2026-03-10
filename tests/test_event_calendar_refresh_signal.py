from types import SimpleNamespace

from modules.generic.generic_list_view import GenericListView


def test_notify_calendar_event_change_calls_main_window_callback():
    calls = []
    view = object.__new__(GenericListView)
    view.model_wrapper = SimpleNamespace(entity_type="events")
    view.winfo_toplevel = lambda: SimpleNamespace(
        notify_calendar_events_changed=lambda target_date=None: calls.append(target_date)
    )

    GenericListView._notify_calendar_event_change(view, {"Date": "2026-03-10"})

    assert calls == ["2026-03-10"]


def test_notify_calendar_event_change_ignores_non_event_entities():
    calls = []
    view = object.__new__(GenericListView)
    view.model_wrapper = SimpleNamespace(entity_type="npcs")
    view.winfo_toplevel = lambda: SimpleNamespace(
        notify_calendar_events_changed=lambda target_date=None: calls.append(target_date)
    )

    GenericListView._notify_calendar_event_change(view, {"Date": "2026-03-10"})

    assert calls == []
