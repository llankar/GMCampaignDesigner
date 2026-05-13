from modules.campaigns.ui.graphical_display.arc_selector import (
    ArcCardColors,
    ArcCardPayload,
    calculate_arc_card_metrics,
    draw_arc_card,
    scenario_count_label,
    title_limit_for_card_width,
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


def test_title_limit_for_card_width_matches_arc_card_content_area():
    assert title_limit_for_card_width(236) == 24
    assert title_limit_for_card_width(150) == 14


def test_draw_arc_card_keeps_status_and_count_separate():
    canvas = FakeCanvas()
    metrics = calculate_arc_card_metrics(10, 16, 236, 104)
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
        name="Welcome to the Commonwealth",
        status="Planned",
        scenario_count=10,
        completed_scenarios=0,
    )

    draw_arc_card(canvas, metrics, payload, colors, tags=("arc:0",))

    text_calls = [(args, kwargs) for kind, args, kwargs in canvas.calls if kind == "text"]
    text_values = [kwargs["text"] for _args, kwargs in text_calls]
    assert "ARC 1" in text_values
    assert "Planned" in text_values
    assert "10 scenarios" in text_values
    assert "Welcome to the Common..." in text_values

    title_call = next(
        (args, kwargs)
        for args, kwargs in text_calls
        if kwargs["text"] == "Welcome to the Common..."
    )
    scenario_count_call = next(
        (args, kwargs)
        for args, kwargs in text_calls
        if kwargs["text"] == "10 scenarios"
    )

    assert title_call is not scenario_count_call
    assert title_call[1]["anchor"] == "nw"
    assert scenario_count_call[1]["anchor"] == "w"
    assert scenario_count_call[0][1] - title_call[0][1] >= 24
