import customtkinter as ctk
from modules.pnjs.pnjs_controller import open_pnj_window
from modules.places.places_controller import open_place_window
from modules.scenarios.scenarios_controller import open_scenario_window
from modules.factions.factions_controller import open_faction_window

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GM Campaign Designer")
        
        self.minsize(1280, 720)

        self.pnj_button = ctk.CTkButton(self, text="Manage NPCs", command=lambda: open_pnj_window(self))
        self.pnj_button.pack(pady=5)

        self.place_button = ctk.CTkButton(self, text="Manage Places", command=lambda: open_place_window(self))
        self.place_button.pack(pady=5)

        self.scenario_button = ctk.CTkButton(self, text="Manage Scenarios", command=lambda: open_scenario_window(self))
        self.scenario_button.pack(pady=5)

        self.faction_button = ctk.CTkButton(self, text="Manage Factions", command=lambda: open_faction_window(self))
        self.faction_button.pack(pady=5)


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = MainWindow()
    app.mainloop()