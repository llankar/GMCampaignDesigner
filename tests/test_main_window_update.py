from pathlib import Path
import sys
import types


def _ensure_module(name: str, module: types.ModuleType) -> None:
    sys.modules.setdefault(name, module)


if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.post = lambda *args, **kwargs: None
    requests_stub.get = lambda *args, **kwargs: None
    _ensure_module("requests", requests_stub)

if "winsound" not in sys.modules:
    winsound_stub = types.ModuleType("winsound")
    winsound_stub.PlaySound = lambda *args, **kwargs: None
    winsound_stub.SND_FILENAME = 0
    winsound_stub.SND_ASYNC = 0
    winsound_stub.SND_LOOP = 0
    winsound_stub.SND_PURGE = 0
    _ensure_module("winsound", winsound_stub)

if "fitz" not in sys.modules:
    fitz_stub = types.ModuleType("fitz")
    fitz_stub.open = lambda *args, **kwargs: None
    _ensure_module("fitz", fitz_stub)

if "pypdf" not in sys.modules:
    pypdf_stub = types.ModuleType("pypdf")

    class _Reader:
        def __init__(self, *args, **kwargs):
            pass

    class _Writer:
        def __init__(self, *args, **kwargs):
            pass

    pypdf_stub.PdfReader = _Reader
    pypdf_stub.PdfWriter = _Writer
    _ensure_module("pypdf", pypdf_stub)

if "screeninfo" not in sys.modules:
    screeninfo_stub = types.ModuleType("screeninfo")

    class _Monitor:
        width = 1920
        height = 1080

    screeninfo_stub.get_monitors = lambda: [_Monitor()]
    _ensure_module("screeninfo", screeninfo_stub)

if "flask" not in sys.modules:
    flask_stub = types.ModuleType("flask")

    class _Flask:
        def __init__(self, *args, **kwargs):
            pass

        def route(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def run(self, *args, **kwargs):
            pass

    flask_stub.Flask = _Flask
    flask_stub.send_file = lambda *args, **kwargs: b""
    flask_stub.request = types.SimpleNamespace(args={})
    _ensure_module("flask", flask_stub)

if "werkzeug" not in sys.modules:
    werkzeug_stub = types.ModuleType("werkzeug")
    werkzeug_serving_stub = types.ModuleType("werkzeug.serving")
    werkzeug_serving_stub.make_server = lambda *args, **kwargs: types.SimpleNamespace(
        serve_forever=lambda: None,
        shutdown=lambda: None,
    )
    werkzeug_stub.serving = werkzeug_serving_stub
    _ensure_module("werkzeug", werkzeug_stub)
    _ensure_module("werkzeug.serving", werkzeug_serving_stub)


def _stub_submodule(module_name: str, **attrs) -> None:
    module = types.ModuleType(module_name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[module_name] = module


_stub_submodule("modules.dice.dice_roller_window", DiceRollerWindow=type("DiceRollerWindow", (), {}))
_stub_submodule("modules.dice.dice_bar_window", DiceBarWindow=type("DiceBarWindow", (), {}))

try:
    import customtkinter  # type: ignore
except ModuleNotFoundError:
    ctk_stub = types.ModuleType("customtkinter")

    class _Widget:
        def __init__(self, *args, **kwargs):
            pass

        def pack(self, *args, **kwargs):
            pass

        def grid(self, *args, **kwargs):
            pass

        def place(self, *args, **kwargs):
            pass

        def configure(self, *args, **kwargs):
            pass

        def destroy(self):
            pass

        def winfo_exists(self):
            return False

        def grab_set(self):
            pass

        def grab_release(self):
            pass

        def focus_force(self):
            pass

        def lift(self):
            pass

        def geometry(self, *args, **kwargs):
            pass

        def minsize(self, *args, **kwargs):
            pass

        def attributes(self, *args, **kwargs):
            pass

        def title(self, *args, **kwargs):
            pass

        def resizable(self, *args, **kwargs):
            pass

        def transient(self, *args, **kwargs):
            pass

        def protocol(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

    class _Var:
        def __init__(self, value=None):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    ctk_stub.CTk = _Widget
    ctk_stub.CTkToplevel = _Widget
    ctk_stub.CTkLabel = _Widget
    ctk_stub.CTkFrame = _Widget
    ctk_stub.CTkButton = _Widget
    ctk_stub.CTkEntry = _Widget
    ctk_stub.CTkTextbox = _Widget
    ctk_stub.CTkScrollableFrame = _Widget
    ctk_stub.CTkProgressBar = _Widget
    ctk_stub.CTkOptionMenu = _Widget
    ctk_stub.CTkImage = _Widget
    ctk_stub.CTkComboBox = _Widget
    ctk_stub.CTkCheckBox = _Widget
    ctk_stub.CTkSwitch = _Widget
    ctk_stub.CTkSegmentedButton = _Widget
    ctk_stub.CTkCanvas = _Widget
    ctk_stub.StringVar = _Var
    ctk_stub.BooleanVar = _Var
    ctk_stub.IntVar = _Var
    ctk_stub.DoubleVar = _Var
    ctk_stub.set_appearance_mode = lambda *args, **kwargs: None
    ctk_stub.set_default_color_theme = lambda *args, **kwargs: None
    ctk_stub.CTkFont = _Widget
    ctk_stub.CTkScrollbar = _Widget
    ctk_stub.__getattr__ = lambda name: _Widget
    _ensure_module("customtkinter", ctk_stub)

try:
    from PIL import Image  # type: ignore
except ModuleNotFoundError:
    pil_module = types.ModuleType("PIL")
    pil_image_module = types.ModuleType("PIL.Image")

    class _Image:
        def __init__(self, *args, **kwargs):
            pass

        def resize(self, *args, **kwargs):
            return self

        @property
        def size(self):
            return (0, 0)

        def copy(self):
            return self

        def convert(self, *_args, **_kwargs):
            return self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Resampling:
        LANCZOS = object()

    pil_image_module.Resampling = _Resampling
    pil_image_module.open = lambda *args, **kwargs: _Image()
    pil_image_module.Image = _Image
    pil_image_module.LANCZOS = _Resampling.LANCZOS
    pil_module.Image = pil_image_module

    pil_imageops_module = types.ModuleType("PIL.ImageOps")
    pil_imageops_module.exif_transpose = lambda image: image
    pil_imageops_module.contain = lambda image, size, resampling: image

    pil_imagetk_module = types.ModuleType("PIL.ImageTk")

    class _PhotoImage:
        def __init__(self, *args, **kwargs):
            pass

    pil_imagetk_module.PhotoImage = _PhotoImage

    pil_imagedraw_module = types.ModuleType("PIL.ImageDraw")

    class _Draw:
        def __init__(self, *args, **kwargs):
            pass

    pil_imagedraw_module.Draw = _Draw

    pil_imagegrab_module = types.ModuleType("PIL.ImageGrab")
    pil_imagegrab_module.grab = lambda *args, **kwargs: _Image()

    pil_imagefilter_module = types.ModuleType("PIL.ImageFilter")

    class _GaussianBlur:
        def __init__(self, *args, **kwargs):
            pass

    pil_imagefilter_module.GaussianBlur = _GaussianBlur

    pil_module.ImageOps = pil_imageops_module
    pil_module.ImageTk = pil_imagetk_module
    pil_module.ImageGrab = pil_imagegrab_module
    pil_module.ImageDraw = pil_imagedraw_module
    pil_module.ImageFilter = pil_imagefilter_module

    _ensure_module("PIL", pil_module)
    _ensure_module("PIL.Image", pil_image_module)
    _ensure_module("PIL.ImageOps", pil_imageops_module)
    _ensure_module("PIL.ImageTk", pil_imagetk_module)
    _ensure_module("PIL.ImageGrab", pil_imagegrab_module)
    _ensure_module("PIL.ImageDraw", pil_imagedraw_module)
    _ensure_module("PIL.ImageFilter", pil_imagefilter_module)

try:
    from docx import Document  # type: ignore
except ModuleNotFoundError:
    docx_module = types.ModuleType("docx")

    class _Document:
        def __init__(self, *args, **kwargs):
            pass

    docx_module.Document = _Document
    _ensure_module("docx", docx_module)

import pytest
from packaging.version import Version

import main_window
from modules.helpers import update_helper


class _DummyApp:
    def __init__(self):
        self.worker_result = None

    def _run_progress_task(self, title, worker, success_message, detail_builder=None):
        # Execute the worker immediately to capture its arguments
        self.worker_result = worker(lambda *_args, **_kwargs: None)
        if detail_builder:
            detail_builder(self.worker_result)


def test_begin_update_download_uses_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    candidate = update_helper.UpdateCandidate(
        version=Version("2.0.0"),
        tag="v2.0.0",
        asset_url="https://example.invalid/asset.zip",
        asset_name="asset.zip",
        asset_size=123,
        release_notes="",
        channel="stable",
    )

    stage_root = tmp_path / "stage"
    payload_root = tmp_path / "payload"
    stage_root.mkdir()
    payload_root.mkdir()

    monkeypatch.setattr(sys, "frozen", False, raising=False)

    monkeypatch.setattr(
        update_helper,
        "prepare_staging_area",
        lambda *_args, **_kwargs: (stage_root, payload_root),
    )

    captured_install_root: dict[str, Path] = {}

    class _Process:
        pid = 42

    def _fake_launch_installer(
        payload_root_arg,
        *,
        install_root,
        restart_target,
        wait_for_pid,
        preserve,
        cleanup_root,
    ):
        captured_install_root["value"] = Path(install_root)
        return _Process()

    monkeypatch.setattr(update_helper, "launch_installer", _fake_launch_installer)

    app = _DummyApp()
    bound_method = main_window.MainWindow._begin_update_download.__get__(app, _DummyApp)
    bound_method(candidate)

    assert captured_install_root["value"] == Path(main_window.__file__).resolve().parent
