"""Targeted tests for GM Table entity panels."""

from __future__ import annotations

from types import SimpleNamespace

import modules.generic.entity_detail_factory as entity_detail_factory
import modules.scenarios.gm_table_view as gm_table_view_module
from modules.scenarios.gm_table.workspace import resolve_default_panel_size
from modules.scenarios.gm_table_view import GMTableView


def test_resolve_default_panel_size_prefers_large_scenario_panels() -> None:
    """Scenario panels should open larger than generic entity panels."""
    scenario_size = resolve_default_panel_size("entity", {"entity_type": "Scenarios"})
    npc_size = resolve_default_panel_size("entity", {"entity_type": "NPCs"})

    assert scenario_size == (920, 680)
    assert scenario_size[0] > npc_size[0]
    assert scenario_size[1] > npc_size[1]


def test_resolve_default_panel_size_opens_objects_readably() -> None:
    """Object panels need room for description and stats text."""
    object_size = resolve_default_panel_size("entity", {"entity_type": "Objects"})
    npc_size = resolve_default_panel_size("entity", {"entity_type": "NPCs"})

    assert object_size == (960, 700)
    assert object_size[0] > npc_size[0]
    assert object_size[1] > npc_size[1]


def test_load_entity_item_accepts_title_or_name_case_insensitively() -> None:
    """Scenario lookups should work with legacy Name-only records too."""
    view = GMTableView.__new__(GMTableView)
    view.wrappers = {
        "Scenarios": SimpleNamespace(
            load_items=lambda: [
                {"Title": "Night Run"},
                {"Name": "Legacy Case"},
            ]
        )
    }

    titled = GMTableView._load_entity_item(view, "Scenarios", "night run")
    legacy = GMTableView._load_entity_item(view, "Scenarios", "legacy case")

    assert titled["Title"] == "Night Run"
    assert legacy["Name"] == "Legacy Case"


def test_open_entity_panel_only_grows_existing_panel_when_needed() -> None:
    """Reopening an entity should preserve a readable user-sized panel."""
    captured = []
    workspace = SimpleNamespace(
        serialize=lambda: {
            "panels": [
                {
                    "panel_id": "panel-42",
                    "kind": "entity",
                    "state": {
                        "entity_type": "Scenarios",
                        "entity_name": "Night Run",
                    },
                }
            ]
        },
        bring_to_front=lambda panel_id: captured.append(("front", panel_id)),
        ensure_panel_minimum_size=lambda panel_id, width, height: captured.append(
            ("ensure", panel_id, width, height)
        ),
    )
    view = GMTableView.__new__(GMTableView)
    view.workspace = workspace
    view._load_entity_item = lambda _entity_type, _name: {"Title": "Night Run"}
    view._preferred_entity_geometry = lambda _entity_type: {"width": 920, "height": 680}

    GMTableView.open_entity_panel(view, "Scenarios", "Night Run")

    assert captured == [
        ("front", "panel-42"),
        ("ensure", "panel-42", 920, 680),
    ]


def test_open_entity_panel_reuses_information_panel_with_title_canonicalization() -> (
    None
):
    """Informations panels should dedupe across Title/Name aliases."""
    captured = []
    workspace = SimpleNamespace(
        serialize=lambda: {
            "panels": [
                {
                    "panel_id": "panel-info",
                    "kind": "entity",
                    "state": {
                        "entity_type": "Informations",
                        "entity_name": "Secret Dossier",
                    },
                }
            ]
        },
        bring_to_front=lambda panel_id: captured.append(("front", panel_id)),
        ensure_panel_minimum_size=lambda panel_id, width, height: captured.append(
            ("ensure", panel_id, width, height)
        ),
    )
    view = GMTableView.__new__(GMTableView)
    view.workspace = workspace
    view._load_entity_item = lambda _entity_type, _name: {
        "Title": "Secret Dossier",
        "Name": "Old Note",
    }
    view._preferred_entity_geometry = lambda _entity_type: {"width": 760, "height": 580}
    view._create_panel = lambda *args, **kwargs: captured.append(
        ("create", args, kwargs)
    )

    GMTableView.open_entity_panel(view, "Informations", "Old Note")

    assert captured == [
        ("front", "panel-info"),
        ("ensure", "panel-info", 760, 580),
    ]


def test_open_entity_panel_uses_useful_geometry_for_new_scenario_panel() -> None:
    """Fresh scenario panels should be created at a readable size."""
    captured = {}
    view = GMTableView.__new__(GMTableView)
    view.workspace = SimpleNamespace()
    view._find_existing_entity_panel = lambda _entity_type, _name, **_kwargs: None
    view._load_entity_item = lambda _entity_type, _name: {"Name": "Legacy Case"}
    view._preferred_entity_geometry = lambda _entity_type: {"width": 920, "height": 680}

    def _capture(kind, title, state, *, geometry=None):
        captured["kind"] = kind
        captured["title"] = title
        captured["state"] = state
        captured["geometry"] = geometry
        return "panel-new"

    view._create_panel = _capture

    GMTableView.open_entity_panel(view, "Scenarios", "Legacy Case")

    assert captured["kind"] == "entity"
    assert captured["title"] == "Scenario: Legacy Case"
    assert captured["state"] == {
        "entity_type": "Scenarios",
        "entity_name": "Legacy Case",
    }
    assert captured["geometry"] == {"width": 920, "height": 680}


def test_open_entity_panel_creates_attachmentless_entities_without_popup(
    monkeypatch,
) -> None:
    """Normal entity opens should not require attachments or show attachment popups."""
    captured = {}
    view = GMTableView.__new__(GMTableView)
    view.workspace = SimpleNamespace()
    view._find_existing_entity_panel = lambda _entity_type, _name, **_kwargs: None
    view._load_entity_item = lambda _entity_type, _name: {"Name": "No Media"}
    view._preferred_entity_geometry = lambda _entity_type: {"width": 760, "height": 580}

    def _capture(kind, title, state, *, geometry=None):
        captured["kind"] = kind
        captured["title"] = title
        captured["state"] = state
        captured["geometry"] = geometry
        return "panel-new"

    view._create_panel = _capture
    monkeypatch.setattr(
        gm_table_view_module, "entity_has_attachments", lambda _item: False
    )
    monkeypatch.setattr(
        gm_table_view_module.messagebox,
        "showinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("normal entity opens must not show an attachment popup")
        ),
    )

    GMTableView.open_entity_panel(view, "NPCs", "No Media")

    assert captured["kind"] == "entity"
    assert captured["title"] == "NPC: No Media"
    assert captured["state"] == {"entity_type": "NPCs", "entity_name": "No Media"}
    assert captured["geometry"] == {"width": 760, "height": 580}


def test_open_entity_panel_sets_attachment_only_only_when_explicit_with_attachments(
    monkeypatch,
) -> None:
    """Attachment-only state is opt-in and requires at least one linked attachment."""
    created_states = []
    view = GMTableView.__new__(GMTableView)
    view.workspace = SimpleNamespace()
    view._find_existing_entity_panel = lambda _entity_type, _name, **_kwargs: None
    view._load_entity_item = lambda _entity_type, name: {"Name": name}
    view._preferred_entity_geometry = lambda _entity_type: {"width": 760, "height": 580}
    view._create_panel = (
        lambda _kind, _title, state, *, geometry=None: created_states.append(state)
        or f"panel-{len(created_states)}"
    )

    monkeypatch.setattr(
        gm_table_view_module, "entity_has_attachments", lambda _item: True
    )
    GMTableView.open_entity_panel(view, "NPCs", "Has Media")

    monkeypatch.setattr(
        gm_table_view_module, "entity_has_attachments", lambda _item: False
    )
    GMTableView.open_entity_panel(
        view, "NPCs", "Requested Missing Media", attachment_only=True
    )

    monkeypatch.setattr(
        gm_table_view_module, "entity_has_attachments", lambda _item: True
    )
    GMTableView.open_entity_panel(
        view, "NPCs", "Requested Has Media", attachment_only=True
    )

    assert created_states == [
        {"entity_type": "NPCs", "entity_name": "Has Media"},
        {"entity_type": "NPCs", "entity_name": "Requested Missing Media"},
        {
            "entity_type": "NPCs",
            "entity_name": "Requested Has Media",
            "attachment_only": True,
        },
    ]


def test_build_entity_content_calls_detail_factory(monkeypatch) -> None:
    """Entity content should be built through the shared detail factory."""
    captured = {}

    class _DummyFrame:
        def grid(self, **kwargs):
            captured["grid"] = kwargs

    def _fake_factory(entity_type, item, *, master, open_entity_callback, **kwargs):
        captured["entity_type"] = entity_type
        captured["item"] = item
        captured["master"] = master
        captured["callback"] = open_entity_callback
        captured["kwargs"] = kwargs
        return _DummyFrame()

    view = GMTableView.__new__(GMTableView)
    expected_item = {"Title": "Night Run"}
    view._load_entity_item = lambda _entity_type, _name: expected_item

    def callback(*args, **kwargs):
        return None

    view.open_entity_panel = callback
    host = object()

    monkeypatch.setattr(
        gm_table_view_module, "create_entity_detail_frame", _fake_factory
    )

    frame = GMTableView._build_entity_content(
        view,
        host,
        {"entity_type": "Scenarios", "entity_name": "Night Run"},
    )

    assert isinstance(frame, _DummyFrame)
    assert captured["entity_type"] == "Scenarios"
    assert captured["item"] is expected_item
    assert captured["master"] is host
    assert captured["callback"] is callback
    assert captured["kwargs"] == {"spotlight_only": True}
    assert captured["grid"] == {"row": 0, "column": 0, "sticky": "nsew"}


def test_build_object_entity_content_uses_scrollable_full_detail(monkeypatch) -> None:
    """Object shelf panels should expose text fields, not only the image spotlight."""
    captured = {}

    class _DummyFrame:
        def __init__(self) -> None:
            self.pack_calls = []

        def pack(self, **kwargs):
            self.pack_calls.append(kwargs)

    scroll_host = object()

    def _fake_scroll_host(host):
        captured["scroll_parent"] = host
        return scroll_host

    def _fake_factory(entity_type, item, *, master, open_entity_callback, **kwargs):
        captured["entity_type"] = entity_type
        captured["item"] = item
        captured["master"] = master
        captured["callback"] = open_entity_callback
        captured["kwargs"] = kwargs
        return _DummyFrame()

    view = GMTableView.__new__(GMTableView)
    expected_item = {"Name": "Assault Rifle", "Description": "Readable text"}
    view._load_entity_item = lambda _entity_type, _name: expected_item

    def callback(*args, **kwargs):
        return None

    view.open_entity_panel = callback
    host = object()

    monkeypatch.setattr(gm_table_view_module, "build_scroll_host", _fake_scroll_host)
    monkeypatch.setattr(
        gm_table_view_module, "create_entity_detail_frame", _fake_factory
    )

    frame = GMTableView._build_entity_content(
        view,
        host,
        {"entity_type": "Objects", "entity_name": "Assault Rifle"},
    )

    assert isinstance(frame, _DummyFrame)
    assert captured["scroll_parent"] is host
    assert captured["entity_type"] == "Objects"
    assert captured["item"] is expected_item
    assert captured["master"] is scroll_host
    assert captured["callback"] is callback
    assert captured["kwargs"] == {"spotlight_only": False}
    assert frame.pack_calls == [{"fill": "both", "expand": True}]


def test_build_entity_content_with_attachments_hides_portrait_spotlight(
    monkeypatch,
) -> None:
    """Attachment-backed evidence cards should show attachments without an empty portrait panel."""
    captured = {}

    class _DummyWidget:
        def __init__(self, *args, **kwargs) -> None:
            captured.setdefault("gallery_kwargs", kwargs)
            self.pack_calls = []

        def pack(self, **kwargs):
            self.pack_calls.append(kwargs)

    scroll_host = object()

    def _fake_scroll_host(host):
        captured["scroll_parent"] = host
        return scroll_host

    def _fake_factory(entity_type, item, *, master, open_entity_callback, **kwargs):
        captured["entity_type"] = entity_type
        captured["item"] = item
        captured["master"] = master
        captured["callback"] = open_entity_callback
        captured["kwargs"] = kwargs
        return _DummyWidget()

    view = GMTableView.__new__(GMTableView)
    expected_item = {
        "Name": "Corporations Informations",
        "Attachment": "assets/corp.png",
    }
    view._load_entity_item = lambda _entity_type, _name: expected_item

    def callback(*args, **kwargs):
        return None

    view.open_entity_panel = callback
    host = SimpleNamespace(
        grid_rowconfigure=lambda *args, **kwargs: captured.setdefault(
            "row", (args, kwargs)
        ),
        grid_columnconfigure=lambda *args, **kwargs: captured.setdefault(
            "column", (args, kwargs)
        ),
    )

    monkeypatch.setattr(gm_table_view_module, "build_scroll_host", _fake_scroll_host)
    monkeypatch.setattr(gm_table_view_module, "GMTableAttachmentGallery", _DummyWidget)
    attachment = object()
    monkeypatch.setattr(
        gm_table_view_module,
        "collect_entity_attachments",
        lambda _item: [attachment],
    )
    monkeypatch.setattr(
        gm_table_view_module, "create_entity_detail_frame", _fake_factory
    )

    frame = GMTableView._build_entity_content(
        view,
        host,
        {"entity_type": "Informations", "entity_name": "Corporations Informations"},
    )

    assert frame is scroll_host
    assert captured["entity_type"] == "Informations"
    assert captured["item"] is expected_item
    assert captured["master"] is scroll_host
    assert captured["callback"] is callback
    assert captured["kwargs"] == {"spotlight_only": False, "show_spotlight": False}
    assert captured["gallery_kwargs"] == {"attachments": [attachment]}


def test_context_menu_handler_resolution_is_safe_without_gm_screen_api() -> None:
    """GM Table hosts without a context-menu API should not crash the detail factory."""

    class _HostWithoutMenu:
        pass

    class _HostWithMenu:
        def _show_context_menu(self, _event):
            return None

    assert (
        entity_detail_factory._resolve_context_menu_handler(_HostWithoutMenu()) is None
    )
    assert callable(
        entity_detail_factory._resolve_context_menu_handler(_HostWithMenu())
    )


def test_context_menu_binding_helpers_skip_hosts_without_menu_api(monkeypatch) -> None:
    """Context-menu binding should be a no-op for GM Table style hosts."""

    class _DummyWidget:
        def __init__(self) -> None:
            self.bind_calls = []

        def bind(self, sequence, callback) -> None:
            self.bind_calls.append((sequence, callback))

    class _HostWithMenu:
        def _show_context_menu(self, _event):
            return None

    recursive_calls = []
    widget = _DummyWidget()

    monkeypatch.setattr(
        entity_detail_factory,
        "bind_context_menu_recursively",
        lambda target, callback: recursive_calls.append((target, callback)),
    )

    assert entity_detail_factory._bind_host_context_menu(widget, object()) is None
    assert widget.bind_calls == []

    assert (
        entity_detail_factory._bind_host_context_menu_recursively(widget, object())
        is None
    )
    assert recursive_calls == []

    handler = entity_detail_factory._bind_host_context_menu(widget, _HostWithMenu())
    assert callable(handler)
    assert widget.bind_calls[-2][0] == "<Button-3>"
    assert widget.bind_calls[-1][0] == "<Control-Button-1>"

    recursive_handler = entity_detail_factory._bind_host_context_menu_recursively(
        widget,
        _HostWithMenu(),
    )
    assert callable(recursive_handler)
    assert recursive_calls[-1][0] is widget


def test_handle_add_option_routes_handouts_to_scenario_selection() -> None:
    """Add menu handouts option should ask which scenario powers the panel."""
    captured = []
    view = GMTableView.__new__(GMTableView)
    view._open_scenario_selection_for_panel = lambda panel_kind: captured.append(
        panel_kind
    )

    GMTableView._handle_add_option(view, "Handouts")

    assert captured == ["handouts"]


def test_mount_panel_content_builds_handouts_page(monkeypatch) -> None:
    """Handouts panel should mount the dedicated handouts page."""
    captured = {}

    class _DummyHandoutsPage:
        def __init__(self, parent, **kwargs) -> None:
            captured["parent"] = parent
            captured["kwargs"] = kwargs

    monkeypatch.setattr(gm_table_view_module, "GMTableHandoutsPage", _DummyHandoutsPage)

    view = GMTableView.__new__(GMTableView)
    view._load_scenario_item = lambda scenario_name: {"Title": scenario_name}
    view.wrappers = {"NPCs": object()}
    view.map_wrapper = object()
    definition = gm_table_view_module.PanelDefinition(
        panel_id="panel-handouts",
        kind="handouts",
        title="Handouts",
        state={"scenario_name": "Night Run", "query": "map"},
    )

    mounted = GMTableView._mount_panel_content(view, object(), definition)

    assert isinstance(mounted, _DummyHandoutsPage)
    assert captured["kwargs"]["scenario_name"] == "Night Run"
    assert captured["kwargs"]["scenario_item"] == {"Title": "Night Run"}
    assert captured["kwargs"]["initial_state"] == {
        "scenario_name": "Night Run",
        "query": "map",
    }


def test_restore_or_seed_layout_restores_annotation_only_desks() -> None:
    """Saved desk text/drawings should restore even when no panels are present."""
    layout = {
        "desk_annotations": [
            {"type": "text", "x": 20, "y": 40, "text": "Clue here"},
            {"type": "stroke", "points": [(1, 2), (3, 4)]},
        ],
        "panels": [],
    }
    restored = []
    seeded = []
    view = GMTableView.__new__(GMTableView)
    view.table_id = "table_1"
    view.layout_store = SimpleNamespace(get_table_layout=lambda _table_id: layout)
    view._filter_attachmentless_entity_panels = lambda saved_layout: saved_layout
    view.workspace = SimpleNamespace(
        restore=lambda saved_layout: restored.append(saved_layout)
    )
    view._seed_default_panels = lambda: seeded.append(True)

    GMTableView._restore_or_seed_layout(view)

    assert restored == [layout]
    assert seeded == []
    assert view._workspace_loaded is True


def test_has_saved_workspace_content_includes_desk_annotations() -> None:
    """Annotation-only layouts should count as restorable table content."""
    assert GMTableView._has_saved_workspace_content(
        {"desk_annotations": [{"type": "text"}]}
    )
    assert not GMTableView._has_saved_workspace_content(
        {"desk_annotations": [], "panels": []}
    )


def test_seed_default_panels_opens_table_level_panels() -> None:
    """Starter tabletop should not bind the primary table identity to a scenario."""
    captured = []
    view = GMTableView.__new__(GMTableView)
    view.table_id = "table_1"
    view.table_name = "Main"
    view._create_panel = lambda kind, title, state, *, geometry=None: captured.append(
        (kind, title, state, geometry)
    )

    GMTableView._seed_default_panels(view)

    assert captured == [
        (
            "campaign_dashboard",
            "Campaign Dashboard",
            {},
            {"x": 24, "y": 24, "width": 900, "height": 700},
        ),
        (
            "note",
            "Main Notes",
            {"text": ""},
            {"x": 948, "y": 24, "width": 520, "height": 520},
        ),
    ]


def test_seed_default_panels_keeps_secondary_tables_lightweight() -> None:
    """Secondary tables should not start with the campaign dashboard."""
    captured = []
    view = GMTableView.__new__(GMTableView)
    view.table_id = "table_2"
    view.table_name = "Table2"
    view._create_panel = lambda kind, title, state, *, geometry=None: captured.append(
        (kind, title, state, geometry)
    )

    GMTableView._seed_default_panels(view)

    assert captured == [
        (
            "note",
            "Table2 Notes",
            {
                "text": (
                    "Use this side table for notes, maps, handouts, "
                    "or temporary planning."
                )
            },
            {"x": 24, "y": 24, "width": 520, "height": 360},
        ),
    ]


def test_focus_or_open_map_tool_panel_reuses_existing_panel_for_active_scene() -> None:
    """Map Tool quick action should focus the existing panel and retarget it to the active map."""
    opened = []
    payload = SimpleNamespace(open_map_by_name=lambda map_name: opened.append(map_name))
    workspace = SimpleNamespace(
        get_active_panel_id=lambda **_kwargs: "scene-panel",
        get_panel_definition=lambda panel_id: SimpleNamespace(
            kind="world_map" if panel_id == "scene-panel" else "map_tool"
        ),
        get_panel_payload=lambda panel_id: (
            SimpleNamespace(current_map_name="Harbor")
            if panel_id == "scene-panel"
            else payload
        ),
        list_panels=lambda **kwargs: (
            [{"panel_id": "tool-panel", "payload": payload}]
            if kwargs.get("kinds") == {"map_tool"}
            else []
        ),
        bring_to_front=lambda panel_id: opened.append(f"front:{panel_id}"),
    )
    view = GMTableView.__new__(GMTableView)
    view.scenario = {}
    view.workspace = workspace

    panel_id = GMTableView._focus_or_open_map_tool_panel(view)

    assert panel_id == "tool-panel"
    assert opened == ["front:tool-panel", "Harbor"]


def test_resolve_tabletop_context_queries_panel_list_once_when_no_active_panel() -> (
    None
):
    """Fallback panel lookup should not repeat the same list_panels query."""
    list_calls: list[dict[str, object]] = []
    payload = SimpleNamespace()
    workspace = SimpleNamespace(
        get_active_panel_id=lambda **_kwargs: None,
        list_panels=lambda **kwargs: (
            list_calls.append(kwargs)
            or [{"panel_id": "tool-panel", "payload": payload}]
        ),
        get_panel_definition=lambda _panel_id: SimpleNamespace(kind="map_tool"),
        get_panel_payload=lambda _panel_id: payload,
    )
    view = GMTableView.__new__(GMTableView)
    view.workspace = workspace

    panel_id, kind, resolved_payload = GMTableView._resolve_tabletop_context(view)

    assert panel_id == "tool-panel"
    assert kind == "map_tool"
    assert resolved_payload is payload
    assert list_calls == [
        {"kinds": gm_table_view_module.MAP_PANEL_KINDS, "include_minimized": True}
    ]


def test_open_player_view_uses_active_world_map_payload() -> None:
    """Player View should route directly to the focused world map panel."""
    calls = []
    payload = SimpleNamespace(open_player_display=lambda: calls.append("player"))
    workspace = SimpleNamespace(
        get_active_panel_id=lambda **_kwargs: "scene-panel",
        get_panel_definition=lambda _panel_id: SimpleNamespace(kind="world_map"),
        get_panel_payload=lambda _panel_id: payload,
        list_panels=lambda **_kwargs: [],
    )
    view = GMTableView.__new__(GMTableView)
    view.scenario = {}
    view.workspace = workspace

    GMTableView._open_player_view_for_active_panel(view)

    assert calls == ["player"]


def test_apply_fog_action_routes_to_active_map_panel() -> None:
    """Fog quick actions should target the active map-capable payload."""
    calls = []
    payload = SimpleNamespace(
        _set_fog=lambda mode: calls.append(("mode", mode)),
        clear_fog=lambda: calls.append(("clear",)),
        reset_fog=lambda: calls.append(("reset",)),
        undo_fog=lambda: calls.append(("undo",)),
    )
    workspace = SimpleNamespace(
        get_active_panel_id=lambda **_kwargs: "tool-panel",
        get_panel_definition=lambda _panel_id: SimpleNamespace(kind="map_tool"),
        get_panel_payload=lambda _panel_id: payload,
        list_panels=lambda **_kwargs: [],
    )
    view = GMTableView.__new__(GMTableView)
    view.workspace = workspace
    view.scenario = {}

    GMTableView._apply_fog_action(view, "add_rect")
    GMTableView._apply_fog_action(view, "clear")
    GMTableView._apply_fog_action(view, "reset")
    GMTableView._apply_fog_action(view, "undo")

    assert calls == [
        ("mode", "add_rect"),
        ("clear",),
        ("reset",),
        ("undo",),
    ]


def test_add_menu_options_include_object_shelf_static() -> None:
    """GM Table add-menu declaration should expose the shared object shelf."""
    options_source = gm_table_view_module.GMTableView.__init__.__code__.co_consts

    assert "Object Shelf" in options_source


def test_handle_add_option_routes_object_shelf_panel_creation() -> None:
    """Add menu object shelf option should spawn an object shelf panel."""
    captured = []
    view = GMTableView.__new__(GMTableView)
    view._create_panel = lambda kind, title, state: captured.append(
        (kind, title, state)
    )

    GMTableView._handle_add_option(view, "Object Shelf")

    assert captured == [("object_shelf", "Object Shelf", {})]


def test_mount_panel_content_builds_object_shelf_page(monkeypatch) -> None:
    """Object shelf panels should mount through the shared shelf builder."""
    captured = {}

    class _DummyHostedPage:
        def __init__(self, parent, *, builder, **kwargs) -> None:
            captured["parent"] = parent
            captured["builder"] = builder
            captured["kwargs"] = kwargs

    monkeypatch.setattr(gm_table_view_module, "GMTableHostedPage", _DummyHostedPage)
    monkeypatch.setattr(
        gm_table_view_module,
        "create_object_shelf_panel",
        lambda host, open_entity_callback=None: {
            "host": host,
            "callback": open_entity_callback,
        },
    )

    view = GMTableView.__new__(GMTableView)
    view.open_entity_panel = object()
    definition = gm_table_view_module.PanelDefinition(
        panel_id="panel-shelf",
        kind="object_shelf",
        title="Object Shelf",
        state={},
    )

    mounted = GMTableView._mount_panel_content(view, object(), definition)
    built = captured["builder"]("host-frame")

    assert isinstance(mounted, _DummyHostedPage)
    assert built == {"host": "host-frame", "callback": view.open_entity_panel}


def test_hosted_page_grids_unmounted_widget_payload() -> None:
    """Hosted page should mount widgets returned ungridded by builders."""
    from modules.scenarios.gm_table.pages import GMTableHostedPage

    class _Payload:
        def __init__(self) -> None:
            self.manager = ""
            self.grid_calls = []

        def winfo_manager(self):
            return self.manager

        def grid(self, **kwargs):
            self.grid_calls.append(kwargs)
            self.manager = "grid"

    page = GMTableHostedPage.__new__(GMTableHostedPage)
    payload = _Payload()
    page._payload = payload

    GMTableHostedPage._grid_payload_if_needed(page)

    assert payload.grid_calls == [{"row": 0, "column": 0, "sticky": "nsew"}]


def test_hosted_page_keeps_already_managed_payload_in_place() -> None:
    """Hosted page should not re-layout widgets that builders already mounted."""
    from modules.scenarios.gm_table.pages import GMTableHostedPage

    class _Payload:
        def __init__(self) -> None:
            self.grid_calls = []

        def winfo_manager(self):
            return "pack"

        def grid(self, **kwargs):
            self.grid_calls.append(kwargs)

    page = GMTableHostedPage.__new__(GMTableHostedPage)
    payload = _Payload()
    page._payload = payload

    GMTableHostedPage._grid_payload_if_needed(page)

    assert payload.grid_calls == []


def test_filter_attachmentless_entity_panels_preserves_normal_entity_panels() -> None:
    """Only attachment-only entity panels should be eligible for attachment filtering."""
    view = GMTableView.__new__(GMTableView)
    view._load_entity_item = lambda _entity_type, _name: {"Name": "No Media"}
    layout = {
        "panels": [
            {
                "panel_id": "normal-entity",
                "kind": "entity",
                "state": {"entity_type": "NPCs", "entity_name": "No Media"},
            },
            {
                "panel_id": "attachment-gallery",
                "kind": "entity",
                "state": {
                    "entity_type": "NPCs",
                    "entity_name": "No Media",
                    "attachment_only": True,
                },
            },
        ]
    }

    filtered = GMTableView._filter_attachmentless_entity_panels(view, layout)

    assert [panel["panel_id"] for panel in filtered["panels"]] == ["normal-entity"]


def test_filter_attachmentless_entity_panels_keeps_missing_entities_for_fallback() -> (
    None
):
    """Missing saved entities should remain so the unavailable fallback can explain it."""
    view = GMTableView.__new__(GMTableView)

    def _missing(_entity_type, _name):
        raise KeyError("missing")

    view._load_entity_item = _missing
    layout = {
        "panels": [
            {
                "panel_id": "missing-gallery",
                "kind": "entity",
                "state": {
                    "entity_type": "NPCs",
                    "entity_name": "Gone",
                    "attachment_only": True,
                },
            }
        ]
    }

    filtered = GMTableView._filter_attachmentless_entity_panels(view, layout)

    assert filtered["panels"] == layout["panels"]


def test_resolve_default_panel_size_supports_container_window() -> None:
    """Container windows should open large enough to organize nested windows."""
    assert resolve_default_panel_size("container_window") == (820, 580)


def test_resolve_default_panel_size_supports_container_internal_panels() -> None:
    """Container workspace cards should restore at their compact intended sizes."""
    assert resolve_default_panel_size("container_card") == (360, 260)
    assert resolve_default_panel_size("container_note") == (420, 300)


def test_container_window_counts_existing_panels_without_serializing() -> None:
    """Adding container content should avoid serializing every nested payload."""
    from modules.scenarios.gm_table.container_window import GMTableContainerPage

    captured = []

    class _Workspace:
        def list_panels(self, *, kinds=None, include_minimized=True):
            assert kinds == {"container_card"}
            assert include_minimized is True
            return [{"panel_id": "one"}, {"panel_id": "two"}]

        def serialize(self):  # pragma: no cover - should not be reached
            raise AssertionError("add_window should not serialize workspace state")

        def add_panel(self, definition, *, geometry=None):
            captured.append(
                (definition.kind, definition.title, definition.state, geometry)
            )

    page = GMTableContainerPage.__new__(GMTableContainerPage)
    page.workspace = _Workspace()

    GMTableContainerPage.add_window(page)

    assert captured == [
        (
            "container_card",
            "Window 3",
            {"body": "Use this card to group related GM table material."},
            {"width": 360, "height": 260},
        )
    ]


def test_container_note_counts_existing_panels_without_serializing() -> None:
    """Adding container notes should avoid serializing every nested payload."""
    from modules.scenarios.gm_table.container_window import GMTableContainerPage

    captured = []

    class _Workspace:
        def list_panels(self, *, kinds=None, include_minimized=True):
            assert kinds == {"container_note"}
            assert include_minimized is True
            return [{"panel_id": "note-one"}]

        def serialize(self):  # pragma: no cover - should not be reached
            raise AssertionError("add_note should not serialize workspace state")

        def add_panel(self, definition, *, geometry=None):
            captured.append(
                (definition.kind, definition.title, definition.state, geometry)
            )

    page = GMTableContainerPage.__new__(GMTableContainerPage)
    page.workspace = _Workspace()

    GMTableContainerPage.add_note(page)

    assert captured == [
        ("container_note", "Note 2", {"text": ""}, {"width": 420, "height": 300})
    ]


def test_container_window_restores_explicitly_empty_layout_without_seeding() -> None:
    """A saved empty nested layout should not recreate starter cards on reload."""
    from modules.scenarios.gm_table.container_window import (
        CONTAINER_LAYOUT_STATE_KEY,
        GMTableContainerPage,
    )

    calls = []
    page = GMTableContainerPage.__new__(GMTableContainerPage)
    page._initial_state = {CONTAINER_LAYOUT_STATE_KEY: {"panels": []}}
    page.workspace = SimpleNamespace(
        restore=lambda layout: calls.append(("restore", layout))
    )
    page.add_window = lambda **kwargs: calls.append(("window", kwargs))
    page.add_note = lambda **kwargs: calls.append(("note", kwargs))

    GMTableContainerPage._restore_or_seed_layout(page)

    assert calls == [("restore", {"panels": []})]


def test_container_add_panel_menu_routes_choice_to_nested_workspace() -> None:
    """Container Add Panel should add main-table panel types to the nested workspace."""
    from modules.scenarios.gm_table.container_window import GMTableContainerPage

    calls = []
    workspace = object()
    page = GMTableContainerPage.__new__(GMTableContainerPage)
    page.workspace = workspace
    page._on_add_panel = lambda option, target_workspace: calls.append(
        (option, target_workspace)
    )

    GMTableContainerPage._handle_add_panel_option(page, "Random Tables")

    assert calls == [("Random Tables", workspace)]


def test_container_mounts_main_table_panel_types_with_shared_builder() -> None:
    """Container workspaces should render non-container panel definitions via GM Table builder."""
    from modules.scenarios.gm_table.container_window import GMTableContainerPage

    parent = object()
    definition = gm_table_view_module.PanelDefinition(
        panel_id="panel-random-tables",
        kind="random_tables",
        title="Random Tables",
        state={},
    )
    rendered = object()
    page = GMTableContainerPage.__new__(GMTableContainerPage)
    page._panel_builder = lambda host, panel_definition: (
        host,
        panel_definition,
        rendered,
    )

    mounted = GMTableContainerPage._mount_container_panel(page, parent, definition)

    assert mounted == (parent, definition, rendered)


def test_handle_add_option_creates_container_window_panel() -> None:
    """Add menu container option should create the nested workspace panel."""
    captured = []
    view = GMTableView.__new__(GMTableView)
    view._create_panel = lambda kind, title, state: captured.append(
        (kind, title, state)
    )

    GMTableView._handle_add_option(view, "Container Window")

    assert captured == [("container_window", "Container Window", {})]


def test_mount_panel_content_builds_container_window(monkeypatch) -> None:
    """Container panel should mount the modular nested workspace page."""
    captured = {}

    class _DummyContainerPage:
        def __init__(self, parent, **kwargs) -> None:
            captured["parent"] = parent
            captured["kwargs"] = kwargs

    monkeypatch.setattr(
        gm_table_view_module, "GMTableContainerPage", _DummyContainerPage
    )

    view = GMTableView.__new__(GMTableView)
    view._persist_layout = lambda: None
    definition = gm_table_view_module.PanelDefinition(
        panel_id="panel-container",
        kind="container_window",
        title="Container Window",
        state={"container_layout": {"panels": []}},
    )

    mounted = GMTableView._mount_panel_content(view, object(), definition)

    assert isinstance(mounted, _DummyContainerPage)
    assert captured["kwargs"]["initial_state"] == {"container_layout": {"panels": []}}
    assert captured["kwargs"]["on_layout_changed"] == view._persist_layout


def test_open_or_focus_scenario_board_reuses_existing_panel() -> None:
    """Scenario Board helper should avoid duplicate panels for the same scenario."""
    calls = []
    workspace = SimpleNamespace(
        serialize=lambda: {
            "panels": [
                {
                    "panel_id": "board-1",
                    "kind": "scenario_board",
                    "state": {"scenario_name": "Night Run"},
                }
            ]
        },
        bring_to_front=lambda panel_id: calls.append(("front", panel_id)),
        ensure_panel_minimum_size=lambda panel_id, width, height: calls.append(
            ("ensure", panel_id, width, height)
        ),
    )
    view = GMTableView.__new__(GMTableView)
    view.workspace = workspace

    panel_id = GMTableView.open_or_focus_scenario_board(view, "night run")

    assert panel_id == "board-1"
    assert calls == [("front", "board-1"), ("ensure", "board-1", 900, 680)]


def test_launch_scenario_bundle_opens_maps_and_entities() -> None:
    """Launching a resolved bundle should route through deduplicating helpers."""
    calls = []
    view = GMTableView.__new__(GMTableView)
    view.open_or_focus_map_panel = lambda name=None: calls.append(("map", name))
    view.open_or_focus_world_map = lambda name=None: calls.append(("world", name))
    view.open_or_focus_entity_panel = lambda entity_type, name: calls.append(
        (entity_type, name)
    )
    bundle = gm_table_view_module.ScenarioBundle(
        scenario_title="Night Run",
        scene_title="Cold Open",
        npcs=("Fixer",),
        villains=("Boss",),
        places=("Docks",),
        maps=("Docks Map",),
        world_maps=("City Map",),
    )

    GMTableView.launch_scenario_bundle(view, bundle)

    assert calls == [
        ("map", "Docks Map"),
        ("world", "City Map"),
        ("NPCs", "Fixer"),
        ("Villains", "Boss"),
        ("Places", "Docks"),
    ]
