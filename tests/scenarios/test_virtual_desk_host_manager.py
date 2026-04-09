from modules.scenarios.gm_screen.virtual_desk.host_manager import VirtualDeskHostManager


class _FakeFrame:
    def __init__(self, should_fail=False):
        self.pack_calls = []
        self.should_fail = should_fail

    def pack_forget(self):
        self.pack_calls.append(("forget", None))

    def pack(self, **kwargs):
        if self.should_fail and kwargs.get("in_") != "center_host":
            raise RuntimeError("simulated pack failure")
        self.pack_calls.append(("pack", kwargs))


def test_move_content_frame_uses_requested_host_when_available():
    manager = VirtualDeskHostManager({"center": "center_host", "right": "right_host", "bottom": "bottom_host"})
    frame = _FakeFrame()

    zone = manager.move_content_frame(frame, "right")

    assert zone == "right"
    assert frame.pack_calls[-1] == ("pack", {"in_": "right_host", "fill": "both", "expand": True})


def test_move_content_frame_falls_back_to_center_on_error():
    manager = VirtualDeskHostManager({"center": "center_host", "right": "right_host"})
    frame = _FakeFrame(should_fail=True)

    zone = manager.move_content_frame(frame, "right")

    assert zone == "center"
    assert frame.pack_calls[-1] == ("pack", {"in_": "center_host", "fill": "both", "expand": True})


def test_resolve_zone_returns_center_for_unknown_or_missing_zone():
    manager = VirtualDeskHostManager({"center": "center_host", "bottom": "bottom_host"})
    assert manager.resolve_zone("unknown") == "center"
    assert manager.resolve_zone("right") == "center"
