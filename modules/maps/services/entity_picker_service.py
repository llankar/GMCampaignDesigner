import tkinter as tk
from modules.ui.image_viewer import show_portrait
from modules.generic.generic_list_selection_view import GenericListSelectionView


def open_entity_picker(self, entity_type):
    """
    Show a GenericListSelectionView for NPCs or Creatures.
    """
    picker = tk.Toplevel(self.parent)
    picker.title(f"Select {entity_type}")
    picker.geometry("1300x600")
    view = GenericListSelectionView(
        master=picker,
        entity_type=entity_type,
        model_wrapper=self._model_wrappers[entity_type],
        template=self._templates[entity_type],
        on_select_callback=lambda et, name: self.on_entity_selected(et, name, picker)
    )

    view.pack(fill="both", expand=True)

def on_entity_selected(self, entity_type, entity_name, picker_frame):
    """
    Called when user picks an NPC or Creature in the selection dialog.
    """
    items = self._model_wrappers[entity_type].load_items()
    selected = next(item for item in items if item.get("Name") == entity_name)
    portrait = selected.get("Portrait")
    if isinstance(portrait, dict):
        path = portrait.get("path") or portrait.get("text")
    else:
        path = portrait
    # find the full creature/NPC record so we can show its fields later
    all_items = self._model_wrappers[entity_type].load_items()
    record = next((i for i in all_items if i.get("Name")==entity_name), {})       
    self.add_token(path, entity_type, entity_name, record)
    picker_frame.destroy()

