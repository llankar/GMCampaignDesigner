from main_window import MainWindow


class _FakeDock:
    def __init__(self, *, exists=True):
        self._exists = exists
        self.selected_date = "2026-03-22"
        self.grid_remove_called = 0
        self.grid_called = 0
        self.selected_date_events = None
        self.upcoming_events = None
        self.month_event_map = None

    def winfo_exists(self):
        return self._exists

    def grid_remove(self):
        self.grid_remove_called += 1

    def grid(self):
        self.grid_called += 1

    def set_selected_date_events(self, selected_date, events):
        self.selected_date_events = (selected_date, events)

    def set_upcoming_events(self, events):
        self.upcoming_events = events

    def set_month_event_map(self, month_event_map):
        self.month_event_map = month_event_map


class _FakeButton:
    def __init__(self):
        self.text = None

    def configure(self, **kwargs):
        self.text = kwargs.get("text", self.text)


class _FakeWidget:
    def __init__(self):
        self.destroy_called = 0

    def destroy(self):
        self.destroy_called += 1


class _FakeContentFrame:
    def __init__(self, children):
        self._children = list(children)

    def winfo_children(self):
        return list(self._children)


class _FakeInnerFrame:
    def __init__(self):
        self.destroyed_children = []
        self.grid_forget_called = 0

    def winfo_children(self):
        return []

    def grid_forget(self):
        self.grid_forget_called += 1


def test_toggle_calendar_dock_ignores_destroyed_widget():
    window = MainWindow.__new__(MainWindow)
    window.calendar_dock = _FakeDock(exists=False)
    window.calendar_dock_toggle_btn = _FakeButton()
    window._calendar_dock_visible = True

    MainWindow._toggle_calendar_dock(window)

    assert window._calendar_dock_visible is False
    assert window.calendar_dock_toggle_btn.text == "Calendar ▶"


def test_refresh_calendar_dock_skips_destroyed_widget():
    window = MainWindow.__new__(MainWindow)
    window.calendar_dock = _FakeDock(exists=False)
    window._calendar_dock_visible = True

    MainWindow._refresh_calendar_dock(window, "2026-03-22")

    assert window._calendar_dock_visible is False


def test_clear_current_content_preserves_calendar_dock():
    window = MainWindow.__new__(MainWindow)
    calendar_dock = _FakeDock(exists=True)
    dynamic_widget = _FakeWidget()
    window.calendar_dock = calendar_dock
    window.banner_frame = object()
    window.inner_content_frame = _FakeInnerFrame()
    window.content_frame = _FakeContentFrame([window.banner_frame, window.inner_content_frame, calendar_dock, dynamic_widget])
    window.banner_visible = False
    window._gm_mode = True
    window.current_gm_view = object()
    window._teardown_whiteboard_controller = lambda: None

    MainWindow.clear_current_content(window)

    assert dynamic_widget.destroy_called == 1
    assert window.inner_content_frame.grid_forget_called == 1
    assert window._gm_mode is False
    assert window.current_gm_view is None
