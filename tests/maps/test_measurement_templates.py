from modules.maps.measurement.templates import build_measurement_item, render_measurement_on_canvas


class FakeCanvas:
    def __init__(self):
        self.ovals = []
        self._next_id = 1

    def _id(self):
        canvas_id = self._next_id
        self._next_id += 1
        return canvas_id

    def create_oval(self, *coords, **kwargs):
        self.ovals.append({"coords": coords, "kwargs": kwargs})
        return self._id()

    def create_text(self, *args, **kwargs):
        return self._id()

    def bbox(self, _text_id):
        return (0, 0, 40, 20)

    def create_rectangle(self, *args, **kwargs):
        return self._id()

    def tag_lower(self, *_args, **_kwargs):
        return None


def _identity_world_to_screen(x, y):
    return x, y


def test_circle_measurement_renders_outline_without_fill():
    canvas = FakeCanvas()
    item = build_measurement_item("circle", (100, 100), (150, 100))

    render_measurement_on_canvas(canvas, item, _identity_world_to_screen)

    assert canvas.ovals[0]["kwargs"]["fill"] == ""
    assert canvas.ovals[0]["kwargs"]["stipple"] == ""
    assert canvas.ovals[0]["kwargs"]["outline"] == "#45B7FF"


def test_aura_measurement_keeps_translucent_fill():
    canvas = FakeCanvas()
    item = build_measurement_item("aura", (100, 100), (150, 100))

    render_measurement_on_canvas(canvas, item, _identity_world_to_screen)

    assert canvas.ovals[0]["kwargs"]["fill"] == "#45B7FF"
    assert canvas.ovals[0]["kwargs"]["stipple"] == "gray25"
