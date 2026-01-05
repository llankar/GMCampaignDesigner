import customtkinter as ctk

from modules.helpers.logging_helper import log_module_import


class WorkspacePanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.tab_bar_container = ctk.CTkFrame(self, height=60)
        self.tab_bar_container.pack(side="top", fill="x")

        self.content_area = ctk.CTkFrame(self)
        self.content_area.pack(fill="both", expand=True)


log_module_import(__name__)
