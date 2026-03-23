import customtkinter as ctk
from tkinter import messagebox
from scenarios.gm_screen_view import GMScreenView
from modules.generic.entity_detail_factory import create_entity_detail_frame
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_module_import,
)

log_module_import(__name__)


def _open_detached_entity_window(entity_type, entity_name, wrapper_name):
    wrapper = GenericModelWrapper(wrapper_name)
    items = wrapper.load_items()
    item = next((entry for entry in items if entry.get("Name") == entity_name), None)
    if not item:
        messagebox.showerror("Error", f"{entity_type[:-1]} '{entity_name}' not found.")
        return

    window = ctk.CTkToplevel()
    window.title(f"{entity_type[:-1]}: {entity_name}")
    window.geometry("800x600")

    dummy_scenario = {"Title": f"Entity: {entity_name}"}
    detail_view = GMScreenView(window, scenario_item=dummy_scenario)
    detail_view.pack(fill="both", expand=True)

    create_entity_detail_frame(
        entity_type,
        item,
        master=detail_view.content_area,
        open_entity_callback=detail_view.open_entity_tab,
    )

@log_function
def open_detached_npc(npc_name):
    log_info(f"Opening detached NPC window: {npc_name}", func_name="open_detached_npc")
    """Open an NPC in a detached window using the shared detail factory UI."""
    _open_detached_entity_window("NPCs", npc_name, "npcs")

@log_function
def open_detached_pc(pc_name):
    log_info(f"Opening detached PC window: {pc_name}", func_name="open_detached_pc")
    """Open a PC in a detached window using the shared detail factory UI."""
    _open_detached_entity_window("PCs", pc_name, "pcs")
