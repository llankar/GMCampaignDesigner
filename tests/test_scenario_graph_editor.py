import sys
import types

try:  # pragma: no cover - prefer real module when available
    import customtkinter  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - testing fallback
    class _DummyWidget:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return None

        def pack(self, *args, **kwargs):
            return None

        def grid(self, *args, **kwargs):
            return None

        def place(self, *args, **kwargs):
            return None

        def destroy(self):
            return None

        def configure(self, *args, **kwargs):
            return None

        def bind(self, *args, **kwargs):
            return None

        def after(self, *args, **kwargs):
            return None

        def winfo_width(self):
            return 0

        def winfo_height(self):
            return 0

        def winfo_rootx(self):
            return 0

        def winfo_rooty(self):
            return 0

        def create_window(self, *args, **kwargs):
            return None

        def create_line(self, *args, **kwargs):
            return None

        def create_rectangle(self, *args, **kwargs):
            return None

        def create_text(self, *args, **kwargs):
            return None

        def delete(self, *args, **kwargs):
            return None

        def update(self, *args, **kwargs):
            return None

        def __getattr__(self, _):
            return self._return_none

        def _return_none(self, *args, **kwargs):
            return None

    dummy_ctk = types.SimpleNamespace(
        CTk=_DummyWidget,
        CTkFrame=_DummyWidget,
        CTkButton=_DummyWidget,
        CTkComboBox=_DummyWidget,
        CTkEntry=_DummyWidget,
        CTkTextbox=_DummyWidget,
        CTkCanvas=_DummyWidget,
        CTkLabel=_DummyWidget,
        CTkToplevel=_DummyWidget,
        CTkFont=lambda *args, **kwargs: None,
        set_appearance_mode=lambda *args, **kwargs: None,
    )
    sys.modules["customtkinter"] = dummy_ctk

try:  # pragma: no cover - prefer real pillow when available
    from PIL import Image  # type: ignore  # noqa: F401
    from PIL import ImageTk  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - testing fallback
    class _DummyImageModule(types.SimpleNamespace):
        def open(self, *args, **kwargs):
            return _DummyWidget()

        def new(self, *args, **kwargs):
            return _DummyWidget()

    class _DummyImageTkModule(types.SimpleNamespace):
        PhotoImage = _DummyWidget

    pil_module = types.SimpleNamespace(
        Image=_DummyImageModule(),
        ImageTk=_DummyImageTkModule(),
        ImageGrab=types.SimpleNamespace(grab=lambda *args, **kwargs: _DummyWidget()),
    )
    sys.modules.setdefault("PIL", pil_module)
    sys.modules.setdefault("PIL.Image", pil_module.Image)
    sys.modules.setdefault("PIL.ImageTk", pil_module.ImageTk)
    sys.modules.setdefault("PIL.ImageGrab", pil_module.ImageGrab)

sys.modules.setdefault("requests", types.SimpleNamespace())
sys.modules.setdefault("winsound", types.SimpleNamespace(Beep=lambda *args, **kwargs: None, PlaySound=lambda *args, **kwargs: None))

from modules.scenarios.scenario_graph_editor import ScenarioGraphEditor


def _make_editor():
    return ScenarioGraphEditor.__new__(ScenarioGraphEditor)


def test_summarize_scene_text_handles_rtf_json_mapping():
    editor = _make_editor()

    lines, truncated = editor._summarize_scene_text(
        {
            "text": "Les habitants de Clairval se tournent vers vous.",
            "formatting": {"bold": [], "italic": []},
        }
    )

    assert not truncated
    assert any("Clairval" in line for line in lines)
    assert all("{" not in line for line in lines)


def test_summarize_scene_text_handles_rich_text_value():
    editor = _make_editor()

    class DummyRichText:
        def __init__(self, text):
            self.text = text

    lines, truncated = editor._summarize_scene_text(DummyRichText("A bold plan unfolds."))

    assert not truncated
    assert lines[0].startswith("A bold plan")


def test_summarize_scene_text_parses_python_literal_payload():
    editor = _make_editor()

    raw_value = "{'text': 'Investigate the well before dawn.', 'formatting': {'bold': []}}"

    lines, truncated = editor._summarize_scene_text(raw_value)

    assert not truncated
    assert any("Investigate the well" in line for line in lines)
