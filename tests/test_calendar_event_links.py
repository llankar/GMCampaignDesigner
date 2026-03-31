"""Regression tests for calendar event links."""

from main_window import MainWindow


class _MemoryWrapper:
    def __init__(self):
        """Initialize the _MemoryWrapper instance."""
        self.items = []

    def save_item(self, item, key_field="Name"):
        """Save item."""
        key = item.get(key_field)
        for index, existing in enumerate(self.items):
            if existing.get(key_field) == key:
                self.items[index] = dict(item)
                return
        self.items.append(dict(item))

    def load_items(self):
        """Load items."""
        return [dict(item) for item in self.items]


def test_calendar_event_preserves_extended_links():
    """Verify that calendar event preserves extended links."""
    window = MainWindow.__new__(MainWindow)
    wrapper = _MemoryWrapper()
    window.entity_wrappers = {"events": wrapper}
    window._calendar_events_cache = None
    window._invalidate_calendar_events_cache = lambda: setattr(window, "_calendar_events_cache", None)
    window._refresh_calendar_dock = lambda *_args, **_kwargs: None

    created = MainWindow._create_calendar_event(
        window,
        {
            "title": "Ambush at the Gate",
            "date": "2026-03-15",
            "start_time": "20:00",
            "type": "Battle",
            "status": "Planned",
            "NPCs": ["Captain Elra"],
            "Villains": ["Lord Ash"],
            "Creatures": ["Hell Hound"],
            "Objects": ["Gate Key"],
            "Factions": ["Gate Cult"],
            "Bases": ["Outer Bastion"],
            "Maps": ["North Gate"],
            "Clues": ["Broken Seal"],
        },
    )

    assert created["Villains"] == ["Lord Ash"]
    assert created["Creatures"] == ["Hell Hound"]
    assert created["Objects"] == ["Gate Key"]
    assert created["Factions"] == ["Gate Cult"]
    assert created["Bases"] == ["Outer Bastion"]
    assert created["Maps"] == ["North Gate"]
    assert created["Clues"] == ["Broken Seal"]

    stored = wrapper.load_items()[0]
    assert stored["Villains"] == ["Lord Ash"]
    assert stored["Creatures"] == ["Hell Hound"]
    assert stored["Objects"] == ["Gate Key"]
    assert stored["Factions"] == ["Gate Cult"]
    assert stored["Bases"] == ["Outer Bastion"]
    assert stored["Maps"] == ["North Gate"]
    assert stored["Clues"] == ["Broken Seal"]

    events = MainWindow._collect_calendar_events(window)
    assert events[0]["Villains"] == ["Lord Ash"]
    assert events[0]["Creatures"] == ["Hell Hound"]
    assert events[0]["Objects"] == ["Gate Key"]
    assert events[0]["Factions"] == ["Gate Cult"]
    assert events[0]["Bases"] == ["Outer Bastion"]
    assert events[0]["Maps"] == ["North Gate"]
    assert events[0]["Clues"] == ["Broken Seal"]
