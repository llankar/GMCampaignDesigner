import customtkinter as ctk
from tkinter import messagebox

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.template_loader import load_template
from modules.generic.generic_editor_window import GenericEditorWindow

def open_npc_editor_window(npc_name):
    """
    Opens the specified NPC in a new GenericEditorWindow,
    completely detached from the scenario/tabs system.
    """
    # 1. Load the NPC data from the "npcs" file.
    npc_wrapper = GenericModelWrapper("npcs")
    items = npc_wrapper.load_items()
    npc_item = next((i for i in items if i.get("Name") == npc_name), None)
    if not npc_item:
        messagebox.showerror("Error", f"NPC '{npc_name}' not found.")
        return

    # 2. Load the NPC template
    npc_template = load_template("npcs")

    # 3. Import GenericEditorWindow locally to avoid circular imports
    

    # 4. Create the editor window
    #    GenericEditorWindow is itself a Toplevel, so we can pass None or any master.
    editor_window = GenericEditorWindow(None, npc_item, npc_template, npc_wrapper)
    # Optionally, wait for the window to close:
    # editor_window.wait_window()
