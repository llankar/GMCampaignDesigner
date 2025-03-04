import customtkinter as ctk
from .factions_list_view import FactionsListView

class FactionsListWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Manage Factions")
        self.geometry("1000x600")
        self.transient(master)
        self.lift()
        self.focus_force()

        self.list_view = FactionsListView(self)
        self.list_view.pack(fill="both", expand=True)
