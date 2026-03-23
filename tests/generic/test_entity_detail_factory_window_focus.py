import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path("modules/generic/entity_detail_factory.py")


class _DummyFrame:
    def __init__(self, *args, **kwargs):
        self.pack_calls = []

    def pack(self, *args, **kwargs):
        self.pack_calls.append((args, kwargs))


class _DummyWindow:
    instances = []

    def __init__(self, parent=None, *args, **kwargs):
        self.parent = parent
        self.calls = []
        self._exists = True
        _DummyWindow.instances.append(self)

    def title(self, value):
        self.calls.append(("title", value))

    def geometry(self, value):
        self.calls.append(("geometry", value))

    def minsize(self, width, height):
        self.calls.append(("minsize", width, height))

    def configure(self, **kwargs):
        self.calls.append(("configure", kwargs))

    def transient(self, parent):
        self.calls.append(("transient", parent))

    def deiconify(self):
        self.calls.append(("deiconify",))

    def lift(self):
        self.calls.append(("lift",))

    def focus_force(self):
        self.calls.append(("focus_force",))

    def attributes(self, name, value):
        self.calls.append(("attributes", name, value))

    def after_idle(self, callback, *args, **kwargs):
        self.calls.append(("after_idle",))
        callback(*args, **kwargs)

    def protocol(self, name, callback):
        self.calls.append(("protocol", name))
        self._close_callback = callback

    def destroy(self):
        self.calls.append(("destroy",))
        self._exists = False

    def winfo_exists(self):
        return self._exists

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080


class _DummyScrollableFrame(_DummyFrame):
    pass


class _Wrapper:
    def load_item_by_key(self, name, key_field="Name"):
        return {key_field: name, "Name": name}


class _Master:
    def __init__(self):
        self.top = object()

    def winfo_toplevel(self):
        return self.top


class _MessageBox:
    def showerror(self, *args, **kwargs):
        raise AssertionError(f"Unexpected error dialog: {args!r} {kwargs!r}")


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


def _load_module():
    _DummyWindow.instances.clear()
    ctk_module = types.ModuleType("customtkinter")
    ctk_module.CTkToplevel = _DummyWindow
    ctk_module.CTkScrollableFrame = _DummyScrollableFrame
    ctk_module.CTkFrame = _DummyFrame
    ctk_module.CTkLabel = _DummyFrame
    ctk_module.CTkImage = _DummyFrame
    ctk_module.CTkTextbox = _DummyFrame
    sys.modules["customtkinter"] = ctk_module

    pil_module = types.ModuleType("PIL")
    pil_image_module = types.ModuleType("PIL.Image")
    pil_module.Image = pil_image_module
    sys.modules["PIL"] = pil_module
    sys.modules["PIL.Image"] = pil_image_module

    _stub_module(
        "modules.helpers.text_helpers",
        deserialize_possible_json=lambda value: value,
        format_longtext=lambda value, max_length=200: str(value),
        format_multiline_text=lambda value: str(value),
    )
    _stub_module("modules.helpers.rtf_rendering", render_rtf_to_text_widget=lambda *args, **kwargs: None)
    _stub_module("modules.helpers.template_loader", load_template=lambda *args, **kwargs: {})
    _stub_module("modules.generic.generic_model_wrapper", GenericModelWrapper=lambda *args, **kwargs: None)
    _stub_module("modules.helpers.portrait_helper", primary_portrait=lambda *args, **kwargs: None, resolve_portrait_path=lambda *args, **kwargs: None)
    _stub_module("modules.ui.image_viewer", show_portrait=lambda *args, **kwargs: None)
    _stub_module("modules.ui.tooltip", ToolTip=type("ToolTip", (), {}))
    _stub_module("modules.generic.generic_editor_window", GenericEditorWindow=type("GenericEditorWindow", (), {}))
    _stub_module("modules.helpers.config_helper", ConfigHelper=type("ConfigHelper", (), {}))
    _stub_module(
        "modules.audio.entity_audio",
        get_entity_audio_value=lambda *args, **kwargs: None,
        play_entity_audio=lambda *args, **kwargs: None,
        resolve_audio_path=lambda *args, **kwargs: None,
        stop_entity_audio=lambda *args, **kwargs: None,
    )
    _stub_module("modules.books.book_viewer", open_book_viewer=lambda *args, **kwargs: None)
    _stub_module(
        "modules.helpers.logging_helper",
        log_function=lambda func: func,
        log_info=lambda *args, **kwargs: None,
        log_warning=lambda *args, **kwargs: None,
        log_module_import=lambda *args, **kwargs: None,
    )
    _stub_module("modules.scenarios.scene_flow_viewer", create_scene_flow_frame=lambda *args, **kwargs: None)
    _stub_module("modules.scenarios.widgets.scene_body_sections", build_scene_body_sections=lambda *args, **kwargs: None)
    _stub_module("modules.ui.vertical_section_tabs", VerticalSectionTabs=type("VerticalSectionTabs", (), {}))
    _stub_module("modules.events.ui.shared.related_events_panel", RelatedEventsPanel=type("RelatedEventsPanel", (), {}))
    _stub_module(
        "modules.generic.entities.linking",
        resolve_entity_label=lambda entity_type: entity_type.rstrip("s"),
        resolve_entity_slug=lambda entity_type: entity_type.lower(),
    )

    module_name = "tests._entity_detail_factory_focus"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    module._open_entity_windows.clear()
    module.messagebox = _MessageBox()
    module._wrapper_for = lambda entity_type: _Wrapper()
    module.create_entity_detail_frame = lambda *args, **kwargs: _DummyFrame()
    return module


def test_open_entity_tab_makes_new_window_topmost_relative_to_master():
    module = _load_module()
    master = _Master()

    module.open_entity_tab("NPCs", "Aelwyn", master)

    window = _DummyWindow.instances[-1]
    assert window.parent is master.top
    assert ("geometry", "1920x1080+0+0") in window.calls
    assert ("minsize", 1000, 600) in window.calls
    assert ("transient", master.top) in window.calls
    assert ("lift",) in window.calls
    assert ("focus_force",) in window.calls
    assert ("attributes", "-topmost", True) in window.calls
    assert ("attributes", "-topmost", False) in window.calls


def test_open_entity_tab_refocuses_existing_window_instead_of_creating_a_second_one():
    module = _load_module()
    master = _Master()

    module.open_entity_tab("NPCs", "Aelwyn", master)
    first_window = _DummyWindow.instances[-1]
    initial_count = len(_DummyWindow.instances)
    first_window.calls.clear()

    module.open_entity_tab("NPCs", "Aelwyn", master)

    assert len(_DummyWindow.instances) == initial_count
    assert ("transient", master.top) in first_window.calls
    assert ("deiconify",) in first_window.calls
    assert ("lift",) in first_window.calls
    assert ("focus_force",) in first_window.calls
    assert ("attributes", "-topmost", True) in first_window.calls
