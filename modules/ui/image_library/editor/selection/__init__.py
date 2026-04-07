"""Selection subsystem for the image editor."""

from modules.ui.image_library.editor.selection.clipboard import SelectionClipboard, SelectionClipboardPayload
from modules.ui.image_library.editor.selection.magic_wand import magic_select_mask
from modules.ui.image_library.editor.selection.selection_model import SelectionModel

__all__ = ["SelectionModel", "SelectionClipboard", "SelectionClipboardPayload", "magic_select_mask"]
