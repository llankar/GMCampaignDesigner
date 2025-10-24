import customtkinter as ctk
from typing import Callable, List

from modules.helpers.config_helper import ConfigHelper
import configparser
import os
from modules.helpers.logging_helper import log_module_import, log_info, log_warning

log_module_import(__name__)


# Supported theme keys
THEME_DEFAULT = "default"
THEME_MEDIEVAL = "medieval"
THEME_SF = "sf"

_THEME_LISTENERS: List[Callable[[str], None]] = []


def get_theme() -> str:
    """Return the current UI theme key, preferring campaign-local settings.

    Order of precedence:
    1) Campaign settings.ini -> [UI] theme
    2) Global config/config.ini -> [UI] theme
    3) Built-in default
    """
    # Try campaign-local settings first
    try:
        cfg = ConfigHelper.load_campaign_config()
        if cfg is not None and cfg.has_section("UI") and cfg.has_option("UI", "theme"):
            theme = (cfg.get("UI", "theme") or THEME_DEFAULT)
        else:
            theme = ConfigHelper.get("UI", "theme", fallback=THEME_DEFAULT) or THEME_DEFAULT
    except Exception:
        theme = ConfigHelper.get("UI", "theme", fallback=THEME_DEFAULT) or THEME_DEFAULT
    theme = theme.strip().lower()
    if theme not in {THEME_DEFAULT, THEME_MEDIEVAL, THEME_SF}:
        theme = THEME_DEFAULT
    return theme


def apply_theme(theme: str | None = None) -> None:
    """Apply the CustomTkinter color palette for the given theme key.

    Uses built-in CustomTkinter themes for simplicity. Can be swapped to
    custom JSON files later if desired.
    """
    key = (theme or get_theme()).strip().lower()
    try:
        # Keep appearance Dark by default; only adjust color palette here.
        # Map our logical themes to CustomTkinter built-in palettes.
        if key == THEME_MEDIEVAL:
            # Slightly deeper tones feel more "old world"
            ctk.set_default_color_theme("dark-blue")
        elif key == THEME_SF:
            # Brighter, neon-ish palette
            ctk.set_default_color_theme("green")
        else:
            ctk.set_default_color_theme("blue")
        log_info(f"Applied UI theme: {key}", func_name="theme_manager.apply_theme")
    except Exception as exc:
        log_warning(
            f"Failed to apply theme '{key}': {exc}",
            func_name="theme_manager.apply_theme",
        )


def set_theme(theme: str) -> None:
    """Persist and apply a new theme for the current campaign, then notify listeners."""
    key = (theme or THEME_DEFAULT).strip().lower()
    if key not in {THEME_DEFAULT, THEME_MEDIEVAL, THEME_SF}:
        key = THEME_DEFAULT
    # Persist to campaign-local settings.ini so theme follows the DB
    try:
        path = ConfigHelper.get_campaign_settings_path()
        cfg = configparser.ConfigParser()
        if os.path.exists(path):
            cfg.read(path)
        if not cfg.has_section("UI"):
            cfg.add_section("UI")
        cfg.set("UI", "theme", key)
        with open(path, "w", encoding="utf-8") as f:
            cfg.write(f)
        try:
            # Hint ConfigHelper cache to refresh on next read
            ConfigHelper._campaign_mtime = os.path.getmtime(path)
            ConfigHelper._campaign_config = cfg
        except Exception:
            pass
    except Exception:
        # Even if persisting fails, still attempt to apply
        pass
    apply_theme(key)
    for cb in list(_THEME_LISTENERS):
        try:
            cb(key)
        except Exception:
            pass


def get_tokens(theme: str | None = None) -> dict:
    """Return app color tokens that we use where CTk's palette isn't enough.

    These are intentionally minimal; expand as needed.
    """
    key = (theme or get_theme()).strip().lower()
    if key == THEME_MEDIEVAL:
        # Warmer, wood-and-brass inspired palette
        return {
            "sidebar_header_bg": "#5a3e2b",  # deep wood brown
            "button_fg": "#8b5a2b",         # saddle brown
            "button_hover": "#6e4521",      # darker on hover
            "button_border": "#6e4521",
            # Panels (e.g., dice roller)
            "panel_bg": "#2e241a",
            "panel_alt_bg": "#362a1e",
            "accent_button_fg": "#5a3e2b",
            "accent_button_hover": "#4a321f",
        }
    if key == THEME_SF:
        return {
            "sidebar_header_bg": "#126b33",  # green accent band
            "button_fg": "#11a054",
            "button_hover": "#0d7b40",
            "button_border": "#0d7b40",
            "panel_bg": "#0f1a12",
            "panel_alt_bg": "#13261a",
            "accent_button_fg": "#155f3a",
            "accent_button_hover": "#114f30",
        }
    # default
    return {
        "sidebar_header_bg": "#0b3d6e",  # original blue band
        "button_fg": "#0077CC",
        "button_hover": "#005fa3",
        "button_border": "#005fa3",
        "panel_bg": "#111c2a",
        "panel_alt_bg": "#132133",
        "accent_button_fg": "#303c5a",
        "accent_button_hover": "#253149",
    }


def register_theme_change_listener(callback: Callable[[str], None]) -> Callable[[], None]:
    """Register a callback invoked with the new theme key after changes.

    Returns an unsubscribe function.
    """
    _THEME_LISTENERS.append(callback)

    def _unsub() -> None:
        try:
            _THEME_LISTENERS.remove(callback)
        except ValueError:
            pass

    return _unsub
