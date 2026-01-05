import customtkinter as ctk

from modules.helpers.logging_helper import log_module_import
from modules.ui.gm_screen.inspector_panel import InspectorPanel
from modules.ui.gm_screen.navigation_panel import NavigationPanel
from modules.ui.gm_screen.workspace_panel import WorkspacePanel


class GMScreenShell(ctk.CTkFrame):
    def __init__(
        self,
        master,
        scenario_item: dict,
        entity_wrappers: dict,
        open_entity_callback,
        open_entity_list_callback=None,
        on_scene_selected=None,
        on_edit_current_entity=None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(0, weight=1, minsize=220)
        self.grid_columnconfigure(1, weight=3)
        self.grid_columnconfigure(2, weight=1, minsize=220)
        self.grid_rowconfigure(0, weight=1)

        self.navigation_panel = NavigationPanel(
            self,
            scenario_item=scenario_item,
            entity_wrappers=entity_wrappers,
            open_entity_callback=open_entity_callback,
            open_entity_list_callback=open_entity_list_callback,
            on_scene_selected=on_scene_selected,
        )
        self.navigation_panel.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        self.workspace_panel = WorkspacePanel(self)
        self.workspace_panel.grid(row=0, column=1, sticky="nsew", padx=4, pady=8)

        self.inspector_panel = InspectorPanel(self, on_edit_current_entity=on_edit_current_entity)
        self.inspector_panel.grid(row=0, column=2, sticky="nsew", padx=(4, 8), pady=8)


log_module_import(__name__)
