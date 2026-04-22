"""Regression tests for deferred embedded Map Tool opening."""

from __future__ import annotations

import types

import modules.scenarios.gm_screen_view as gm_screen_module
from modules.maps.controllers.display_map_controller import DisplayMapController


class _ParentStub:
    def __init__(self) -> None:
        self.mapped = False
        self.width = 0
        self.height = 0
        self.after_calls: list[tuple[str, int, object]] = []
        self.after_cancelled: list[str] = []

    def after(self, delay: int, callback):
        after_id = f"after-{len(self.after_calls) + 1}"
        self.after_calls.append((after_id, delay, callback))
        return after_id

    def after_cancel(self, after_id: str) -> None:
        self.after_cancelled.append(after_id)

    def winfo_exists(self) -> bool:
        return True

    def winfo_ismapped(self) -> bool:
        return self.mapped

    def update_idletasks(self) -> None:
        pass

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height


class _FrameStub:
    def __init__(self, master=None, **_kwargs) -> None:
        self.master = master

    def pack(self, *args, **kwargs) -> None:
        pass

    def pack_forget(self) -> None:
        pass


def test_display_map_controller_waits_for_visible_stable_host() -> None:
    """Initial embedded map open should wait until the host is mapped and stable."""
    parent = _ParentStub()
    opened: list[tuple[str, bool]] = []

    controller = DisplayMapController.__new__(DisplayMapController)
    controller.parent = parent
    controller._deferred_map_open_name = ""
    controller._deferred_map_open_apply_fit = True
    controller._deferred_map_open_after_id = None
    controller._deferred_map_open_signature = None
    controller.open_map_by_name = lambda map_name, *, apply_fit=True: opened.append((map_name, apply_fit)) or True

    assert controller.open_map_by_name_when_ready("Vault Map") is True
    assert len(parent.after_calls) == 1

    parent.after_calls[-1][2]()
    assert opened == []
    assert len(parent.after_calls) == 2

    parent.mapped = True
    parent.width = 1280
    parent.height = 720

    parent.after_calls[-1][2]()
    assert opened == []
    assert len(parent.after_calls) == 3

    parent.after_calls[-1][2]()
    assert opened == [("Vault Map", True)]
    assert controller._deferred_map_open_name == ""
    assert controller._deferred_map_open_after_id is None


def test_open_map_by_name_cancels_pending_deferred_initial_open() -> None:
    """A successful immediate open must cancel any stale deferred initial-open job."""
    parent = _ParentStub()
    opened: list[tuple[str, str]] = []

    controller = DisplayMapController.__new__(DisplayMapController)
    controller.parent = parent
    controller.current_map = None
    controller.tokens = []
    controller._maps = {"Table Map": {"Name": "Table Map"}}
    controller._deferred_map_open_name = "Vault Map"
    controller._deferred_map_open_apply_fit = True
    controller._deferred_map_open_after_id = "after-stale"
    controller._deferred_map_open_signature = (1280, 720)
    controller._on_display_map = lambda entity_type, map_name: opened.append((entity_type, map_name))

    assert DisplayMapController.open_map_by_name(controller, "Table Map", apply_fit=False) is True
    assert opened == [("maps", "Table Map")]
    assert parent.after_cancelled == ["after-stale"]
    assert controller._deferred_map_open_name == ""
    assert controller._deferred_map_open_after_id is None
    assert controller._deferred_map_open_signature is None


def test_teardown_tab_content_closes_map_tool_controller() -> None:
    """GM screen teardown should cancel map-tool controller jobs before hiding a frame."""
    closed: list[str] = []
    frame = types.SimpleNamespace(
        whiteboard_controller=None,
        map_controller=types.SimpleNamespace(close=lambda: closed.append("map")),
    )
    view = gm_screen_module.GMScreenView.__new__(gm_screen_module.GMScreenView)

    gm_screen_module.GMScreenView._teardown_tab_content(view, frame)

    assert closed == ["map"]


def test_open_map_tool_tab_defers_initial_embedded_map_open(monkeypatch) -> None:
    """GM screen should construct embedded map tabs with deferred initial map opening."""
    created: list[dict[str, object]] = []
    added: dict[str, object] = {}

    class _ControllerStub:
        def __init__(self, parent, maps_wrapper, map_template, **kwargs) -> None:
            created.append(
                {
                    "parent": parent,
                    "maps_wrapper": maps_wrapper,
                    "map_template": map_template,
                    **kwargs,
                }
            )

    monkeypatch.setattr(
        gm_screen_module,
        "ctk",
        types.SimpleNamespace(CTkFrame=_FrameStub),
    )
    monkeypatch.setattr(gm_screen_module, "DisplayMapController", _ControllerStub)
    monkeypatch.setattr(gm_screen_module, "GenericModelWrapper", lambda kind: f"wrapper:{kind}")
    monkeypatch.setattr(gm_screen_module, "load_entity_template", lambda kind: f"template:{kind}")

    view = gm_screen_module.GMScreenView.__new__(gm_screen_module.GMScreenView)
    view._ensure_rich_host = lambda: "rich-host"
    view.add_tab = lambda name, content_frame, content_factory=None, layout_meta=None, activate=True: added.update(
        {
            "name": name,
            "content_frame": content_frame,
            "content_factory": content_factory,
            "layout_meta": layout_meta,
            "activate": activate,
        }
    )

    view.open_map_tool_tab(map_name="Vault Map")

    assert created[0]["initial_map_name"] == "Vault Map"
    assert created[0]["defer_initial_map_until_visible"] is True
    assert added["layout_meta"] == {"kind": "map_tool", "map_name": "Vault Map", "host": "rich"}

    built = added["content_factory"]("factory-host")
    assert isinstance(built, _FrameStub)
    assert created[1]["parent"] is built
    assert created[1]["initial_map_name"] == "Vault Map"
    assert created[1]["defer_initial_map_until_visible"] is True
