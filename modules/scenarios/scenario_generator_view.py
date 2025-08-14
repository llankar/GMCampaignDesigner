
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from campaign_generator import GENERATOR_FUNCTIONS, export_to_docx
from modules.generic.generic_model_wrapper import GenericModelWrapper


class ScenarioGeneratorView(ctk.CTkFrame):
    """Frame embedding the scenario generator inside the main application."""

    def __init__(self, parent):
        super().__init__(parent)

        self.setting_var = ctk.StringVar(value=list(GENERATOR_FUNCTIONS.keys())[0])
        self.title_var = ctk.StringVar(value="")
        self.current_campaign = None

        self._build_widgets()

    # ------------------------------------------------------------------
    def _build_widgets(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top, text="Setting:").pack(side="left")
        ctk.CTkOptionMenu(top, values=list(GENERATOR_FUNCTIONS.keys()),
                          variable=self.setting_var).pack(side="left", padx=5)
        ctk.CTkButton(top, text="Generate", command=self.generate_campaign).pack(side="left", padx=5)


        # Scrollable area for displaying generated scenario cards
        self.results_frame = ctk.CTkScrollableFrame(self, fg_color="#2c3e50")
        self.results_frame.pack(fill="both", expand=True, padx=10, pady=10)

        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(bottom, text="Title:").pack(side="left")
        ctk.CTkEntry(bottom, textvariable=self.title_var).pack(side="left", padx=5, fill="x", expand=True)
        self.export_btn = ctk.CTkButton(bottom, text="Export to DOCX",
                                       command=self.export_docx, state="disabled")
        self.export_btn.pack(side="left", padx=5)
        self.add_btn = ctk.CTkButton(bottom, text="Add to DB",
                                    command=self.add_to_db, state="disabled")
        self.add_btn.pack(side="left", padx=5)

    # ------------------------------------------------------------------
    def generate_campaign(self):
        setting = self.setting_var.get()
        try:
            generator = GENERATOR_FUNCTIONS[setting]
            campaign = generator()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate scenario: {e}")
            return

        self.current_campaign = campaign


        # Clear previous results
        for child in self.results_frame.winfo_children():
            child.destroy()

        # Display each entry as a styled card similar to the original UI
        for key, value in campaign.items():
            card = ctk.CTkFrame(
                self.results_frame,
                fg_color="#34495e",
                corner_radius=4,
            )
            title_lbl = ctk.CTkLabel(
                card,
                text=key,
                text_color="#ecf0f1",
                font=("Helvetica", 16, "bold"),
                anchor="w",
            )
            desc_lbl = ctk.CTkLabel(
                card,
                text=value,
                text_color="#bdc3c7",
                justify="left",
                wraplength=1580,
                font=("Helvetica", 14),
            )
            title_lbl.pack(anchor="w", padx=8, pady=(4, 0))
            desc_lbl.pack(anchor="w", padx=8, pady=(0, 6))
            card.pack(fill="x", expand=True, padx=5, pady=5)

        self.export_btn.configure(state="normal")
        self.add_btn.configure(state="normal")

    # ------------------------------------------------------------------
    def export_docx(self):
        if not self.current_campaign:
            messagebox.showwarning("No Scenario", "Generate a scenario first.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word Document", "*.docx")],
            title="Save Scenario" )
        if not filename:
            return

        try:
            export_to_docx(self.current_campaign, filename)
        except Exception as e:
            messagebox.showerror("Export Error", str(e))
            return

        messagebox.showinfo("Exported", "Scenario exported to DOCX.")

    # ------------------------------------------------------------------
    def add_to_db(self):
        if not self.current_campaign:
            messagebox.showwarning("No Scenario", "Generate a scenario first.")
            return

        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Missing Title", "Please provide a title for the scenario.")
            return

        summary = "\n".join(f"{k}: {v}" for k, v in self.current_campaign.items())
        scenario_entity = {
            "Title": title,
            "Summary": summary,
            "Secrets": "",
            "Places": [],
            "NPCs": [],
            "Objects": [],
        }

        wrapper = GenericModelWrapper("scenarios")
        existing = wrapper.load_items()
        if any(s.get("Title") == title for s in existing):
            messagebox.showwarning("Duplicate Title", f"A scenario titled '{title}' already exists.")
            return

        existing.append(scenario_entity)
        wrapper.save_items(existing)
        messagebox.showinfo("Saved", f"Scenario '{title}' added to database.")

