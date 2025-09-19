import logging
import os
import inspect
from functools import wraps
from typing import Any, Callable, TypeVar, cast, Optional

from modules.helpers.config_helper import ConfigHelper


F = TypeVar("F", bound=Callable[..., Any])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_LOGGER: Optional[logging.Logger] = None
_LAST_CONFIG: Optional[tuple[Any, ...]] = None
_LOGGER_ENABLED: bool = False
_ACTIVE_LOG_PATH: Optional[str] = None


def _resolve_directory(directory: str) -> str:
    directory = directory or "logs"
    if os.path.isabs(directory):
        return directory
    return os.path.join(PROJECT_ROOT, directory)


def _refresh_logger() -> logging.Logger:
    global _LOGGER, _LAST_CONFIG, _LOGGER_ENABLED, _ACTIVE_LOG_PATH

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
            resolved_dir = _resolve_directory(directory)
            os.makedirs(resolved_dir, exist_ok=True)

            if os.path.isabs(filename):
                log_path = filename
            else:
                log_path = os.path.join(resolved_dir, filename)

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
    _log(logging.ERROR, message, func_name=func_name)


def log_exception(message: str, *, func_name: Optional[str] = None) -> None:
    logger, enabled = ensure_logger()
    if not enabled:
        return
    name = func_name or _determine_caller()
    logger.exception("%s - %s", name, message)


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
    "is_logging_enabled",
    "log_debug",
    "log_error",
    "log_exception",
    "log_function",
    "log_info",
    "log_methods",
    "log_warning",
]

