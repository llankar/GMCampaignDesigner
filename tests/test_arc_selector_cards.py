from modules.campaigns.ui.graphical_display.arc_selector import (
    ArcCardColors,
    ArcCardPayload,
    calculate_arc_card_metrics,
    draw_arc_card,
    scenario_count_label,
    truncate_to_width,
)


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def create_rectangle(self, *args, **kwargs):
        self.calls.append(("rectangle", args, kwargs))

    def create_polygon(self, *args, **kwargs):
        self.calls.append(("polygon", args, kwargs))

    def create_text(self, *args, **kwargs):
        self.calls.append(("text", args, kwargs))


def test_scenario_count_label_pluralizes_cleanly():
    assert scenario_count_label(0) == "0 scenarios"
    assert scenario_count_label(1) == "1 scenario"
    assert scenario_count_label(3) == "3 scenarios"


def test_truncate_to_width_uses_single_ellipsis():
    assert truncate_to_width("Short", 12) == "Short"
    assert truncate_to_width("Welcome to the common rooms", 18) == "Welcome to the..."


def test_draw_arc_card_keeps_status_and_count_separate():
    canvas = FakeCanvas()
    metrics = calculate_arc_card_metrics(10, 16, 210, 104)
    colors = ArcCardColors(
        fill="#111",
        outline="#222",
        title="#eee",
        eyebrow="#8fb0dd",
        meta="#aaa",
        status_text="#000",
        status_fill="#60a5fa",
        progress_track="#333",
        progress_fill="#60a5fa",
        accent="#60a5fa",
    )
    payload = ArcCardPayload(
        index=0,
        name="Welcome to the common rooms with a long descriptive title",
        status="Planned",
        scenario_count=10,
        completed_scenarios=0,
    )

    draw_arc_card(canvas, metrics, payload, colors, tags=("arc:0",))

    text_values = [kwargs["text"] for kind, _args, kwargs in canvas.calls if kind == "text"]
    assert "ARC 1" in text_values
    assert "Planned" in text_values
    assert "10 scenarios" in text_values
    assert any(value.startswith("Welcome to") and value.endswith("...") for value in text_values)
