"""Regression tests for calendar dock lifecycle."""

from types import SimpleNamespace

import main_window
from main_window import MainWindow


class _FakeDock:
    def __init__(self, *, exists=True, mapped=True):
        """Initialize the _FakeDock instance."""
        self._exists = exists
        self._mapped = mapped
        self.selected_date = "2026-03-22"
        self.grid_remove_called = 0
        self.grid_called = 0
        self.selected_date_events = None
        self.upcoming_events = None
        self.month_event_map = None

    def winfo_exists(self):
        """Handle winfo exists."""
        return self._exists

    def winfo_ismapped(self):
        """Handle winfo ismapped."""
        return self._mapped

    def winfo_manager(self):
        """Handle winfo manager."""
        return "grid" if self._mapped else ""

    def grid_remove(self):
        """Handle grid remove."""
        self.grid_remove_called += 1
        self._mapped = False

    def grid(self):
        """Handle grid."""
        self.grid_called += 1
        self._mapped = True

    def set_selected_date_events(self, selected_date, events):
        """Set selected date events."""
        self.selected_date_events = (selected_date, events)

    def set_upcoming_events(self, events):
        """Set upcoming events."""
        self.upcoming_events = events

    def set_month_event_map(self, month_event_map):
        """Set month event map."""
        self.month_event_map = month_event_map


class _FakeButton:
    def __init__(self):
        """Initialize the _FakeButton instance."""
        self.text = None

    def configure(self, **kwargs):
        """Handle configure."""
        self.text = kwargs.get("text", self.text)


class _FakeWidget:
    def __init__(self):
        """Initialize the _FakeWidget instance."""
        self.destroy_called = 0

    def destroy(self):
        """Handle destroy."""
        self.destroy_called += 1


class _FakeContentFrame:
    def __init__(self, children):
        """Initialize the _FakeContentFrame instance."""
        self._children = list(children)
        self.grid_rowconfigure_calls = []
        self.grid_columnconfigure_calls = []
        self.pack_configure_calls = []

    def winfo_children(self):
        """Handle winfo children."""
        return list(self._children)

    def grid_rowconfigure(self, row, **kwargs):
        """Handle grid row configure."""
        self.grid_rowconfigure_calls.append((row, kwargs))

    def grid_columnconfigure(self, column, **kwargs):
        """Handle grid column configure."""
        self.grid_columnconfigure_calls.append((column, kwargs))

    def pack_configure(self, **kwargs):
        """Handle pack configure."""
        self.pack_configure_calls.append(kwargs)


class _FakeInnerFrame:
    def __init__(self):
        """Initialize the _FakeInnerFrame instance."""
        self.destroyed_children = []
        self.grid_forget_called = 0
        self.grid_calls = []
        self.grid_rowconfigure_calls = []
        self.grid_columnconfigure_calls = []

    def winfo_children(self):
        """Handle winfo children."""
        return []

    def grid_forget(self):
        """Handle grid forget."""
        self.grid_forget_called += 1

    def grid(self, **kwargs):
        """Handle grid."""
        self.grid_calls.append(kwargs)

    def grid_rowconfigure(self, row, **kwargs):
        """Handle grid row configure."""
        self.grid_rowconfigure_calls.append((row, kwargs))

    def grid_columnconfigure(self, column, **kwargs):
        """Handle grid column configure."""
        self.grid_columnconfigure_calls.append((column, kwargs))


class _FakeSidebarFrame(_FakeWidget):
    def __init__(self, *, mapped=True):
        """Initialize the _FakeSidebarFrame instance."""
        super().__init__()
        self._mapped = mapped
        self.pack_called = 0
        self.pack_forget_called = 0

    def winfo_ismapped(self):
        """Handle winfo ismapped."""
        return self._mapped

    def winfo_manager(self):
        """Handle winfo manager."""
        return "pack" if self._mapped else ""

    def pack(self, **kwargs):
        """Handle pack."""
        self.pack_called += 1
        self._mapped = True

    def pack_forget(self):
        """Handle pack forget."""
        self.pack_forget_called += 1
        self._mapped = False


class _FakeBannerFrame(_FakeSidebarFrame):
    """Fake banner frame with grid visibility tracking."""

    def __init__(self, *, mapped=True):
        """Initialize the _FakeBannerFrame instance."""
        super().__init__(mapped=mapped)
        self.grid_called = 0
        self.grid_remove_called = 0

    def grid(self, **kwargs):
        """Handle grid."""
        self.grid_called += 1
        self._mapped = True

    def grid_remove(self):
        """Handle grid remove."""
        self.grid_remove_called += 1
        self._mapped = False


class _FakeMenuBarFrame(_FakeSidebarFrame):
    """Fake menu bar frame with pack visibility tracking."""


class _FakeToplevel:
    """Fake detached window with geometry and lifecycle tracking."""

    def __init__(self, *args, **kwargs):
        """Initialize the _FakeToplevel instance."""
        self.title_text = None
        self.geometry_calls = []
        self.minsize_calls = []
        self.lift_calls = 0
        self.focus_force_calls = 0
        self.attributes_calls = []
        self.protocol_callbacks = {}
        self.after_idle_callbacks = []
        self.destroy_calls = 0
        self._exists = True

    def winfo_exists(self):
        """Handle winfo exists."""
        return self._exists

    def winfo_screenwidth(self):
        """Handle winfo screenwidth."""
        return 1920

    def winfo_screenheight(self):
        """Handle winfo screenheight."""
        return 1080

    def title(self, value):
        """Handle title."""
        self.title_text = value

    def geometry(self, value):
        """Handle geometry."""
        self.geometry_calls.append(value)

    def minsize(self, width, height):
        """Handle minsize."""
        self.minsize_calls.append((width, height))

    def lift(self):
        """Handle lift."""
        self.lift_calls += 1

    def focus_force(self):
        """Handle focus force."""
        self.focus_force_calls += 1

    def attributes(self, *args):
        """Handle attributes."""
        self.attributes_calls.append(args)

    def after_idle(self, callback):
        """Handle after idle."""
        self.after_idle_callbacks.append(callback)

    def protocol(self, name, callback):
        """Handle protocol."""
        self.protocol_callbacks[name] = callback

    def destroy(self):
        """Handle destroy."""
        self.destroy_calls += 1
        self._exists = False


class _FakeFrame:
    """Fake frame container for detached GM Table content."""

    def __init__(self, *args, **kwargs):
        """Initialize the _FakeFrame instance."""
        self.pack_calls = []

    def pack(self, **kwargs):
        """Handle pack."""
        self.pack_calls.append(kwargs)


class _FakeGMTableView:
    """Fake GM Table view mounted inside the detached window."""

    def __init__(self, master, *, scenario_item, root_app):
        """Initialize the _FakeGMTableView instance."""
        self.master = master
        self.scenario_item = scenario_item
        self.root_app = root_app
        self.pack_calls = []
        self.after_idle_callbacks = []
        self.log_workspace_opened_calls = 0

    def pack(self, **kwargs):
        """Handle pack."""
        self.pack_calls.append(kwargs)

    def after_idle(self, callback):
        """Handle after idle."""
        self.after_idle_callbacks.append(callback)

    def log_workspace_opened(self):
        """Handle log workspace opened."""
        self.log_workspace_opened_calls += 1


def test_open_gm_table_launches_detached_window_without_clearing_main_content(monkeypatch):
    """GM Table should open in its own window and leave the main app alone."""
    window = MainWindow.__new__(MainWindow)
    scenario = {"Title": "Storm Front"}
    window.entity_wrappers = {"scenarios": SimpleNamespace(load_items=lambda: [scenario])}
    window._gm_table_window = None
    window._gm_mode = False
    window.current_gm_table = None
    window.clear_current_content_called = False

    def _clear_current_content():
        """Fail if the main content is cleared for GM Table."""
        window.clear_current_content_called = True
        raise AssertionError("clear_current_content should not be called")

    window.clear_current_content = _clear_current_content

    import modules.scenarios.gm_table_view as gm_table_view_module

    monkeypatch.setattr(main_window.ctk, "CTkToplevel", _FakeToplevel)
    monkeypatch.setattr(main_window.ctk, "CTkFrame", _FakeFrame)
    monkeypatch.setattr(gm_table_view_module, "GMTableView", _FakeGMTableView)

    gm_window = MainWindow.open_gm_table(window, scenario_name="Storm Front")

    assert gm_window is window._gm_table_window
    assert window._gm_mode is False
    assert window.clear_current_content_called is False
    assert gm_window.title_text == "GM Table - Storm Front"
    assert gm_window.geometry_calls[-1] == "1920x1080+0+0"
    assert gm_window.minsize_calls[-1] == (1600, 900)
    assert gm_window.lift_calls == 1
    assert gm_window.focus_force_calls == 1
    assert gm_window.attributes_calls[0] == ("-topmost", True)
    assert window.current_gm_table.scenario_item == scenario
    assert window.current_gm_table.root_app is window
    assert window.current_gm_table.pack_calls == [{"fill": "both", "expand": True}]
    assert window.current_gm_table.after_idle_callbacks[0] == window.current_gm_table.log_workspace_opened

    gm_window.after_idle_callbacks[0]()
    assert gm_window.attributes_calls[-1] == ("-topmost", False)
    window.current_gm_table.after_idle_callbacks[0]()
    assert window.current_gm_table.log_workspace_opened_calls == 1


def test_open_gm_table_reuses_an_existing_detached_window(monkeypatch):
    """Opening GM Table twice should focus the existing window."""
    window = MainWindow.__new__(MainWindow)
    scenario = {"Title": "Storm Front"}
    window.entity_wrappers = {"scenarios": SimpleNamespace(load_items=lambda: [scenario])}
    window._gm_table_window = _FakeToplevel()
    window._gm_table_window._gm_table_scenario_name = "Storm Front"
    window.current_gm_table = _FakeGMTableView(None, scenario_item=scenario, root_app=window)
    window._gm_mode = False

    import modules.scenarios.gm_table_view as gm_table_view_module

    monkeypatch.setattr(
        main_window.ctk,
        "CTkToplevel",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should reuse existing GM Table window")),
    )
    monkeypatch.setattr(main_window.ctk, "CTkFrame", _FakeFrame)
    monkeypatch.setattr(gm_table_view_module, "GMTableView", _FakeGMTableView)

    gm_window = MainWindow.open_gm_table(window, scenario_name="Storm Front")

    assert gm_window is window._gm_table_window
    assert gm_window.lift_calls == 1
    assert gm_window.focus_force_calls == 1
    assert gm_window.geometry_calls == []
    assert gm_window.minsize_calls == []
    assert window.current_gm_table.scenario_item == scenario


def test_gm_table_window_close_clears_tracked_references(monkeypatch):
    """Closing the detached GM Table should drop the window references."""
    window = MainWindow.__new__(MainWindow)
    scenario = {"Title": "Storm Front"}
    window.entity_wrappers = {"scenarios": SimpleNamespace(load_items=lambda: [scenario])}
    window._gm_table_window = None
    window.current_gm_table = None
    window._gm_mode = False

    import modules.scenarios.gm_table_view as gm_table_view_module

    monkeypatch.setattr(main_window.ctk, "CTkToplevel", _FakeToplevel)
    monkeypatch.setattr(main_window.ctk, "CTkFrame", _FakeFrame)
    monkeypatch.setattr(gm_table_view_module, "GMTableView", _FakeGMTableView)

    gm_window = MainWindow.open_gm_table(window, scenario_name="Storm Front")
    close_callback = gm_window.protocol_callbacks["WM_DELETE_WINDOW"]

    close_callback()

    assert gm_window.destroy_calls == 1
    assert window._gm_table_window is None
    assert window.current_gm_table is None


def test_get_gm_table_window_clears_dead_reference():
    """Dead detached GM Table windows should be forgotten immediately."""
    window = MainWindow.__new__(MainWindow)
    gm_table_view = object()
    window._gm_table_window = _FakeToplevel()
    window._gm_table_window._exists = False
    window.current_gm_table = gm_table_view

    assert MainWindow._get_gm_table_window(window) is None
    assert window._gm_table_window is None
    assert window.current_gm_table is None


def test_toggle_calendar_dock_ignores_destroyed_widget():
    """Verify that toggle calendar dock ignores destroyed widget."""
    window = MainWindow.__new__(MainWindow)
    window.calendar_dock = _FakeDock(exists=False)
    window.calendar_dock_toggle_btn = _FakeButton()
    window._calendar_dock_visible = True

    MainWindow._toggle_calendar_dock(window)

    assert window._calendar_dock_visible is False
    assert window.calendar_dock_toggle_btn.text == "Calendar ▶"


def test_refresh_calendar_dock_skips_destroyed_widget():
    """Verify that refresh calendar dock skips destroyed widget."""
    window = MainWindow.__new__(MainWindow)
    window.calendar_dock = _FakeDock(exists=False)
    window._calendar_dock_visible = True

    MainWindow._refresh_calendar_dock(window, "2026-03-22")

    assert window._calendar_dock_visible is False


def test_clear_current_content_preserves_calendar_dock():
    """Verify that clear current content preserves calendar dock."""
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
    gm_table_view = object()
    window.current_gm_table = gm_table_view
    window._gm_table_window = _FakeToplevel()
    window._teardown_whiteboard_controller = lambda: None

    MainWindow.clear_current_content(window)

    assert dynamic_widget.destroy_called == 1
    assert window.inner_content_frame.grid_forget_called == 1
    assert window._gm_mode is False
    assert window.current_gm_view is None
    assert window.current_gm_table is gm_table_view
