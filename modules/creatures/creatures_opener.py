import customtkinter as ctk
from tkinter import messagebox

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.template_loader import load_template
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

def open_creature_editor_window(creature_name):
    """
    Opens the specified NPC in a new GenericEditorWindow,
    completely detached from the scenario/tabs system.
    """
    # 1. Load the NPC data from the "creatures" file.
    creature_wrapper = GenericModelWrapper("creatures")
    items = creature_wrapper.load_items()
    creature_item = next((i for i in items if i.get("Name") == creature_name), None)
    if not creature_item:
        messagebox.showerror("Error", f"NPC '{creature_name}' not found.")
        return

    # 2. Load the NPC template
    creature_template = load_template("creaturess")

    # 3. Import GenericEditorWindow locally to avoid circular imports
    

    # 4. Create the editor window
    #    GenericEditorWindow is itself a Toplevel, so we can pass None or any master.
    editor_window = GenericEditorWindow(None, creature_item, creature_template, creature_wrapper)
    # Optionally, wait for the window to close:
    # editor_window.wait_window()
