import importlib.util
import sys
import types
from pathlib import Path


sys.modules["customtkinter"] = types.SimpleNamespace(
    CTkFrame=object,
    CTkLabel=object,
    CTkTextbox=object,
    set_default_color_theme=lambda *args, **kwargs: None,
)

MODULE_PATH = Path("modules/campaigns/ui/theme/arc_editor_palette.py")
spec = importlib.util.spec_from_file_location("arc_editor_palette", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)
get_arc_editor_palette = module.get_arc_editor_palette
theme_manager = module.theme_manager


def test_arc_editor_palette_matches_default_theme_tokens():
    palette = get_arc_editor_palette(theme_manager.THEME_DEFAULT)

    assert palette.window_bg == "#10151d"
    assert palette.surface == "#161d27"
    assert palette.accent == theme_manager.get_tokens(theme_manager.THEME_DEFAULT)["button_fg"]
    assert palette.success_hover == theme_manager.get_tokens(theme_manager.THEME_DEFAULT)["button_hover"]


def test_arc_editor_palette_switches_to_medieval_theme():
    palette = get_arc_editor_palette(theme_manager.THEME_MEDIEVAL)

    assert palette.window_bg == "#17120f"
    assert palette.surface == "#211913"
    assert palette.text_primary == "#f7ead8"
    assert palette.accent == theme_manager.get_tokens(theme_manager.THEME_MEDIEVAL)["button_fg"]


def test_arc_editor_palette_switches_to_scifi_theme():
    palette = get_arc_editor_palette(theme_manager.THEME_SF)

    assert palette.window_bg == "#0d1711"
    assert palette.border == "#255641"
    assert palette.text_secondary == "#98cdb0"
    assert palette.accent == theme_manager.get_tokens(theme_manager.THEME_SF)["button_fg"]
