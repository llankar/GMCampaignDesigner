import tkinter as tk
from modules.ui.image_viewer import show_portrait
from modules.generic.generic_list_selection_view import GenericListSelectionView
from tkinter import messagebox
from modules.helpers.logging_helper import log_module_import
from modules.helpers.portrait_helper import primary_portrait

log_module_import(__name__)

def open_entity_picker(self, entity_type):
    """
    Show a GenericListSelectionView for NPCs or Creatures.
    """
    picker = tk.Toplevel(self.parent)
    picker.title(f"Select {entity_type}")
    picker.geometry("1300x600")
    allow_multi_select = entity_type == "PC"
    view = GenericListSelectionView(
        master=picker,
        entity_type=entity_type,
        model_wrapper=self._model_wrappers[entity_type],
        template=self._templates[entity_type],
        on_select_callback=lambda et, name: self.on_entity_selected(et, name, picker),
        allow_multi_select=allow_multi_select,
        on_multi_select_callback=(
            lambda et, records: self.on_entities_selected(et, records, picker)
            if allow_multi_select
            else None
        ),
    )

    view.pack(fill="both", expand=True)

def on_entity_selected(self, entity_type, entity_name, picker_frame):
    """
    Called when user picks an NPC or Creature in the selection dialog.
    """
    items = self._model_wrappers[entity_type].load_items()
    record = next((item for item in items if item.get("Name") == entity_name), None)
    if not record:
        messagebox.showerror("Selection Error", f"Unable to load {entity_type} '{entity_name}'.")
        return

    _add_entity_record(self, entity_type, record)
    picker_frame.destroy()

def on_entities_selected(self, entity_type, records, picker_frame):
    """Add multiple entities to the map in one action."""
    added_any = False
    for record in records:
        added_any = _add_entity_record(self, entity_type, record) or added_any

    if added_any:
        picker_frame.destroy()

def _extract_portrait_path(record):
    portrait = record.get("Portrait")
    return primary_portrait(portrait)

def _get_entity_display_name(record):
    return record.get("Name") or record.get("Title") or "Unnamed"

def _add_entity_record(self, entity_type, record):
    entity_name = _get_entity_display_name(record)
    path = _extract_portrait_path(record)
    if not path:
        messagebox.showerror("Missing Portrait", f"No portrait image found for '{entity_name}'.")
        return False
    self.add_token(path, entity_type, entity_name, record)
    return True
