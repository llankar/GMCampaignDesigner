import logging
import os
import inspect
import sys
import threading
import traceback
from functools import wraps
from typing import Any, Callable, TypeVar, cast, Optional

F = TypeVar("F", bound=Callable[..., Any])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_LOGGER: Optional[logging.Logger] = None
_LAST_CONFIG: Optional[tuple[Any, ...]] = None
_LOGGER_ENABLED: bool = False
_ACTIVE_LOG_PATH: Optional[str] = None


def _resolve_log_path(directory: str, filename: str) -> str:
    resolved_dir = _resolve_directory(directory)
    os.makedirs(resolved_dir, exist_ok=True)
    if os.path.isabs(filename):
        return filename
    return os.path.join(resolved_dir, filename)


def _append_fallback_error_log(message: str, *, exc_info: bool = False) -> None:
    """Write critical diagnostics even when regular logging is disabled."""
    from modules.helpers.config_helper import ConfigHelper

    try:
        directory = ConfigHelper.get("Logging", "directory", fallback="logs") or "logs"
        filename = ConfigHelper.get("Logging", "filename", fallback="gmcampaigndesigner.log") or "gmcampaigndesigner.log"
        log_path = _resolve_log_path(directory, filename)
    except Exception:
        fallback_dir = os.path.join(PROJECT_ROOT, "logs")
        os.makedirs(fallback_dir, exist_ok=True)
        log_path = os.path.join(fallback_dir, "gmcampaigndesigner.log")

    try:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(f"[FALLBACK][ERROR] {message}\n")
            if exc_info:
                handle.write("".join(traceback.format_exc()))
                handle.write("\n")
    except Exception:
        pass


def _resolve_directory(directory: str) -> str:
    directory = directory or "logs"
    if os.path.isabs(directory):
        return directory
    return os.path.join(PROJECT_ROOT, directory)


def _refresh_logger() -> logging.Logger:
    global _LOGGER, _LAST_CONFIG, _LOGGER_ENABLED, _ACTIVE_LOG_PATH

    from modules.helpers.config_helper import ConfigHelper

    enabled = ConfigHelper.getboolean("Logging", "enabled", fallback=False)
    directory = ConfigHelper.get("Logging", "directory", fallback="logs") or "logs"
    filename = ConfigHelper.get("Logging", "filename", fallback="gmcampaigndesigner.log") or "gmcampaigndesigner.log"
    level_name = ConfigHelper.get("Logging", "level", fallback="INFO") or "INFO"

    config_signature = (enabled, directory, filename, level_name)

    if _LOGGER is None:
        _LOGGER = logging.getLogger("GMCampaignDesigner")
        _LOGGER.propagate = False

    if config_signature != _LAST_CONFIG:
        _LAST_CONFIG = config_signature

        for handler in list(_LOGGER.handlers):
            if getattr(handler, "_gmc_handler", False):
                _LOGGER.removeHandler(handler)

        _ACTIVE_LOG_PATH = None

        if enabled:
            log_path = _resolve_log_path(directory, filename)

            level = getattr(logging, str(level_name).upper(), logging.INFO)

            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
            )
            file_handler._gmc_handler = True  # type: ignore[attr-defined]
            file_handler._gmc_path = log_path  # type: ignore[attr-defined]
            _LOGGER.addHandler(file_handler)
            _LOGGER.setLevel(level)
            _ACTIVE_LOG_PATH = log_path

            _LOGGER.info("logging_helper.configure - Logging enabled. Writing to %s", log_path)
        else:
            null_handler = logging.NullHandler()
            null_handler._gmc_handler = True  # type: ignore[attr-defined]
            _LOGGER.addHandler(null_handler)
            _LOGGER.setLevel(logging.CRITICAL)

    _LOGGER_ENABLED = enabled
    return _LOGGER


def ensure_logger() -> tuple[logging.Logger, bool]:
    logger = _refresh_logger()
    return logger, _LOGGER_ENABLED


def is_logging_enabled() -> bool:
    _, enabled = ensure_logger()
    return enabled


def get_active_log_path() -> Optional[str]:
    return _ACTIVE_LOG_PATH


def _determine_caller(extra_depth: int = 0) -> str:
    frame = inspect.currentframe()
    target = frame
    try:
        depth = 2 + max(extra_depth, 0)
        for _ in range(depth):
            if target is None:
                break
            target = target.f_back

        if target is None:
            return "unknown"

        module = target.f_globals.get("__name__", "")
        name = target.f_code.co_name
        return f"{module}.{name}" if module else name
    finally:
        del frame
        del target


def _log(level: int, message: str, *, func_name: Optional[str] = None, extra_depth: int = 0, exc_info: bool = False) -> None:
    logger, enabled = ensure_logger()
    if not enabled:
        return

    name = func_name or _determine_caller(extra_depth)
    if exc_info:
        logger.log(level, "%s - %s", name, message, exc_info=True)
    else:
        logger.log(level, "%s - %s", name, message)


def log_debug(message: str, *, func_name: Optional[str] = None) -> None:
    _log(logging.DEBUG, message, func_name=func_name)


def log_info(message: str, *, func_name: Optional[str] = None) -> None:
    _log(logging.INFO, message, func_name=func_name)


def log_warning(message: str, *, func_name: Optional[str] = None) -> None:
    _log(logging.WARNING, message, func_name=func_name)


def log_error(message: str, *, func_name: Optional[str] = None) -> None:
    logger, enabled = ensure_logger()
    if enabled:
        name = func_name or _determine_caller()
        logger.error("%s - %s", name, message)
        return

    name = func_name or _determine_caller()
    _append_fallback_error_log(f"{name} - {message}")


def log_exception(message: str, *, func_name: Optional[str] = None) -> None:
    logger, enabled = ensure_logger()
    name = func_name or _determine_caller()
    if enabled:
        logger.exception("%s - %s", name, message)
        return
    _append_fallback_error_log(f"{name} - {message}", exc_info=True)


def _handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    log_error(f"Uncaught exception: {exc_value}", func_name="global.excepthook")
    _append_fallback_error_log(
        "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)).rstrip()
    )


def _handle_thread_exception(args: threading.ExceptHookArgs) -> None:
    log_error(
        f"Unhandled thread exception in {args.thread.name if args.thread else 'unknown-thread'}: {args.exc_value}",
        func_name="global.threading_excepthook",
    )
    _append_fallback_error_log(
        "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)).rstrip()
    )


def install_global_exception_hooks() -> None:
    sys.excepthook = _handle_uncaught_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = _handle_thread_exception




def log_module_import(module_name: Optional[str] = None) -> None:
    name = module_name or _determine_caller(extra_depth=1)
    _log(logging.INFO, "module import", func_name=name)

def log_function(func: F) -> F:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger, enabled = ensure_logger()
        if not enabled:
            return func(*args, **kwargs)

        func_name = func.__qualname__
        _log(logging.INFO, "started", func_name=func_name)
        try:
            result = func(*args, **kwargs)
            _log(logging.DEBUG, "completed", func_name=func_name)
            return result
        except Exception as exc:
            logger.exception("%s - failed: %s", func_name, exc)
            raise

    return cast(F, wrapper)


def log_methods(cls: type) -> type:
    for name, attr in list(cls.__dict__.items()):
        if name.startswith("__"):
            continue

        if isinstance(attr, staticmethod):
            original = attr.__func__
            setattr(cls, name, staticmethod(log_function(original)))
        elif isinstance(attr, classmethod):
            original = attr.__func__
            setattr(cls, name, classmethod(log_function(original)))
        elif callable(attr):
            setattr(cls, name, log_function(attr))

    return cls


def initialize_logging() -> bool:
    logger, enabled = ensure_logger()
    if not enabled:
        return False
    if _ACTIVE_LOG_PATH:
        logger.info("logging_helper.initialize - Logging ready at %s", _ACTIVE_LOG_PATH)
    else:
        logger.info("logging_helper.initialize - Logging ready")
    return True


__all__ = [
    "ensure_logger",
    "get_active_log_path",
    "initialize_logging",
    "install_global_exception_hooks",
    "is_logging_enabled",
    "log_debug",
    "log_error",
    "log_exception",
    "log_function",
    "log_module_import",
    "log_info",
    "log_methods",
    "log_warning",
]
