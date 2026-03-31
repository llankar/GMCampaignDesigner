"""Opening helpers for villain."""
from tkinter import messagebox

from modules.generic.generic_editor_window import GenericEditorWindow
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_module_import
from modules.helpers.template_loader import load_template

log_module_import(__name__)


def open_villain_editor_window(villain_name):
    """Open villain editor window."""
    villain_wrapper = GenericModelWrapper("villains")
    items = villain_wrapper.load_items()
    villain_item = next((i for i in items if i.get("Name") == villain_name), None)
    if not villain_item:
        messagebox.showerror("Error", f"Villain '{villain_name}' not found.")
        return

    villain_template = load_template("villains")
    key_field = villain_wrapper._infer_key_field()
    original_key_value = villain_item.get(key_field)
    editor_window = GenericEditorWindow(None, villain_item, villain_template, villain_wrapper)
    editor_window.wait_window()

    if getattr(editor_window, "saved", False):
        villain_wrapper.save_item(
            editor_window.item,
            key_field=key_field,
            original_key_value=original_key_value,
        )
