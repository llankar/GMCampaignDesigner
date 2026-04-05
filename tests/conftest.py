"""Shared pytest fixtures and test helpers."""

from __future__ import annotations

import sys
import types


def _ensure_module(name: str, module: types.ModuleType) -> None:
    """Ensure module."""
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
            """Initialize the _Reader instance."""
            pass

    class _Writer:
        def __init__(self, *args, **kwargs):
            """Initialize the _Writer instance."""
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
            """Initialize the _Flask instance."""
            self.logger = types.SimpleNamespace(setLevel=lambda *a, **k: None)

        def route(self, *args, **kwargs):
            """Handle route."""
            def decorator(func):
                """Handle decorator."""
                return func

            return decorator

        def register_blueprint(self, *args, **kwargs):
            """Register blueprint."""
            pass

        def run(self, *args, **kwargs):
            """Run the operation."""
            pass

    class _Blueprint:
        def __init__(self, *args, **kwargs):
            """Initialize the _Blueprint instance."""
            pass

        def route(self, *args, **kwargs):
            """Handle route."""
            def decorator(func):
                """Handle decorator."""
                return func

            return decorator

    class _Response:
        def __init__(self, response=None, mimetype=None, headers=None, status=None):
            """Initialize the _Response instance."""
            self.response = response
            self.mimetype = mimetype
            self.headers = headers or {}
            self.status = status

    flask_stub.Flask = _Flask
    flask_stub.Blueprint = _Blueprint
    flask_stub.Response = _Response
    flask_stub.jsonify = lambda *args, **kwargs: args[0] if args else kwargs
    flask_stub.render_template_string = lambda template, **context: template
    flask_stub.send_from_directory = lambda *args, **kwargs: b""
    flask_stub.send_file = lambda *args, **kwargs: b""
    flask_stub.request = types.SimpleNamespace(
        args={},
        form={},
        json=None,
        headers={},
        get_json=lambda silent=False: None,
    )
    _ensure_module("flask", flask_stub)

if "werkzeug" not in sys.modules:
    werkzeug_stub = types.ModuleType("werkzeug")
    werkzeug_serving_stub = types.ModuleType("werkzeug.serving")

    class _WSGIRequestHandler:
        def log(self, *args, **kwargs):
            """Handle log."""
            pass

    werkzeug_serving_stub.WSGIRequestHandler = _WSGIRequestHandler
    werkzeug_serving_stub.make_server = lambda *args, **kwargs: types.SimpleNamespace(
        serve_forever=lambda: None,
        shutdown=lambda: None,
    )
    werkzeug_stub.serving = werkzeug_serving_stub
    _ensure_module("werkzeug", werkzeug_stub)
    _ensure_module("werkzeug.serving", werkzeug_serving_stub)


def _stub_submodule(module_name: str, **attrs) -> None:
    """Internal helper for stub submodule."""
    module = types.ModuleType(module_name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules.setdefault(module_name, module)


_stub_submodule("modules.dice.dice_roller_window", DiceRollerWindow=type("DiceRollerWindow", (), {}))
_stub_submodule("modules.dice.dice_bar_window", DiceBarWindow=type("DiceBarWindow", (), {}))

try:
    import customtkinter  # type: ignore # noqa: F401
except ModuleNotFoundError:
    ctk_stub = types.ModuleType("customtkinter")

    class _Widget:
        def __init__(self, *args, **kwargs):
            """Initialize the _Widget instance."""
            pass

        def pack(self, *args, **kwargs):
            """Pack the operation."""
            pass

        def grid(self, *args, **kwargs):
            """Handle grid."""
            pass

        def place(self, *args, **kwargs):
            """Handle place."""
            pass

        def pack_forget(self, *args, **kwargs):
            """Pack forget."""
            pass

        def grid_forget(self, *args, **kwargs):
            """Handle grid forget."""
            pass

        def grid_remove(self, *args, **kwargs):
            """Handle grid remove."""
            pass

        def grid_columnconfigure(self, *args, **kwargs):
            """Handle grid columnconfigure."""
            pass

        def grid_rowconfigure(self, *args, **kwargs):
            """Handle grid rowconfigure."""
            pass

        def configure(self, *args, **kwargs):
            """Handle configure."""
            pass

        def bind(self, *args, **kwargs):
            """Bind the operation."""
            pass

        def bind_all(self, *args, **kwargs):
            """Bind all."""
            pass

        def after(self, *args, **kwargs):
            """Handle after."""
            pass

        def after_idle(self, *args, **kwargs):
            """Handle after idle."""
            pass

        def after_cancel(self, *args, **kwargs):
            """Handle after cancel."""
            pass

        def destroy(self):
            """Handle destroy."""
            pass

        def winfo_exists(self):
            """Handle winfo exists."""
            return False

        def winfo_children(self):
            """Handle winfo children."""
            return []

        def winfo_toplevel(self):
            """Handle winfo toplevel."""
            return self

        def grab_set(self):
            """Handle grab set."""
            pass

        def grab_release(self):
            """Handle grab release."""
            pass

        def focus_force(self):
            """Handle focus force."""
            pass

        def lift(self):
            """Handle lift."""
            pass

        def geometry(self, *args, **kwargs):
            """Handle geometry."""
            pass

        def minsize(self, *args, **kwargs):
            """Handle minsize."""
            pass

        def attributes(self, *args, **kwargs):
            """Handle attributes."""
            pass

        def title(self, *args, **kwargs):
            """Handle title."""
            pass

        def resizable(self, *args, **kwargs):
            """Handle resizable."""
            pass

        def transient(self, *args, **kwargs):
            """Handle transient."""
            pass

        def protocol(self, *args, **kwargs):
            """Handle protocol."""
            pass

        def set(self, *args, **kwargs):
            """Set the operation."""
            pass

    class _Var:
        def __init__(self, value=None):
            """Initialize the _Var instance."""
            self._value = value

        def get(self):
            """Return the operation."""
            return self._value

        def set(self, value):
            """Set the operation."""
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
    ctk_stub.CTkRadioButton = _Widget
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
    from PIL import Image  # type: ignore # noqa: F401
except ModuleNotFoundError:
    pil_module = types.ModuleType("PIL")
    pil_image_module = types.ModuleType("PIL.Image")

    class _Image:
        def __init__(self, *args, **kwargs):
            """Initialize the _Image instance."""
            pass

        def resize(self, *args, **kwargs):
            """Handle resize."""
            return self

        @property
        def size(self):
            """Handle size."""
            return (0, 0)

        def copy(self):
            """Copy the operation."""
            return self

        def convert(self, *_args, **_kwargs):
            """Handle convert."""
            return self

        def __enter__(self):
            """Enter the context manager scope."""
            return self

        def __exit__(self, exc_type, exc, tb):
            """Exit the context manager scope."""
            return False

    class _Resampling:
        LANCZOS = object()

    pil_image_module.Resampling = _Resampling
    pil_image_module.open = lambda *args, **kwargs: _Image()
    pil_image_module.Image = _Image
    pil_image_module.LANCZOS = _Resampling.LANCZOS
    pil_module.Image = pil_image_module
    pil_module.UnidentifiedImageError = OSError

    pil_imageops_module = types.ModuleType("PIL.ImageOps")
    pil_imageops_module.exif_transpose = lambda image: image
    pil_imageops_module.contain = lambda image, size, resampling: image

    pil_imagetk_module = types.ModuleType("PIL.ImageTk")

    class _PhotoImage:
        def __init__(self, *args, **kwargs):
            """Initialize the _PhotoImage instance."""
            pass

    pil_imagetk_module.PhotoImage = _PhotoImage

    pil_imagedraw_module = types.ModuleType("PIL.ImageDraw")

    class _Draw:
        def __init__(self, *args, **kwargs):
            """Initialize the _Draw instance."""
            pass

    pil_imagedraw_module.Draw = _Draw

    pil_imagegrab_module = types.ModuleType("PIL.ImageGrab")
    pil_imagegrab_module.grab = lambda *args, **kwargs: _Image()

    pil_imagefilter_module = types.ModuleType("PIL.ImageFilter")

    class _GaussianBlur:
        def __init__(self, *args, **kwargs):
            """Initialize the _GaussianBlur instance."""
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
    from docx import Document  # type: ignore # noqa: F401
except ModuleNotFoundError:
    docx_module = types.ModuleType("docx")

    class _Document:
        def __init__(self, *args, **kwargs):
            """Initialize the _Document instance."""
            pass

    docx_module.Document = _Document
    _ensure_module("docx", docx_module)
