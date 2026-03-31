"""UI helpers for campaign generator."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict

from .exporters import export_to_docx
from .services import GENERATOR_FUNCTIONS, append_scenario_to_json_file

class CampaignGeneratorApp(tk.Tk):
    """Main application window for generating campaigns."""

    def __init__(self) -> None:
        """Initialize the CampaignGeneratorApp instance."""
        super().__init__()
        self.title("Scenario Generator")
        # Set a sensible default window size; allow resizing
        self.geometry("1920x1080+0+0")
        self.minsize(500, 500)
        # Primary background colour for a dark theme
        self.configure(bg="#2c3e50")
        # Use a ttk style for a modern appearance
        self.style = ttk.Style(self)
        # 'clam' theme provides good contrast
        self.style.theme_use("clam")
        # General typography for labels and buttons
        self.style.configure(
            "TLabel",
            background="#2c3e50",
            foreground="white",
            font=("Helvetica", 12),
        )
        # Buttons are styled with a slightly lighter background and white text
        self.style.configure(
            "TButton",
            font=("Helvetica", 12, "bold"),
            padding=6,
            foreground="white",
            background="#3498db",
        )
        # Menu buttons (used by OptionMenu) share similar styling
        self.style.configure(
            "TMenubutton",
            font=("Helvetica", 12),
            background="#34495e",
            foreground="white",
            padding=4,
        )
        # Selected setting variable
        self.setting_var = tk.StringVar(value="Fantasy")
        # Setup UI widgets
        self._create_widgets()
        # Placeholder for campaign data
        self.current_campaign: Dict[str, str] | None = None

    def _create_widgets(self) -> None:
        """Create widgets."""
        # Header label
        header = ttk.Label(
            self,
            text="Scenario Generator",
            font=("Helvetica", 20, "bold"),
            foreground="white",
            background="#2c3e50",
        )
        header.pack(pady=(15, 5))

        # Frame for controls
        top_frame = ttk.Frame(self, padding="10 10 10 10")
        top_frame.pack(fill="x")
        # Setting selection
        ttk.Label(top_frame, text="Select Setting:").pack(side="left")
        settings = list(GENERATOR_FUNCTIONS.keys())
        self.option_menu = ttk.OptionMenu(top_frame, self.setting_var, settings[0], *settings)
        self.option_menu.pack(side="left", padx=10)
        # Generate button
        generate_button = ttk.Button(
            top_frame,
            text="Generate",
            command=self.generate_campaign,
        )
        generate_button.pack(side="left", padx=10)
        # Export button
        self.export_button = ttk.Button(
            top_frame,
            text="Export to DOCX",
            command=self.export_campaign,
        )
        self.export_button.pack(side="left", padx=10)
        self.export_button.state(["disabled"])  # Disabled until campaign generated

        # Export to JSON button
        self.export_json_button = ttk.Button(
            top_frame,
            text="Export to JSON",
            command=self.export_campaign_json,
        )
        self.export_json_button.pack(side="left", padx=10)
        self.export_json_button.state(["disabled"])  # Disabled until campaign generated
        # Results display area using canvas and cards
        self.results_frame = ttk.Frame(self)
        self.results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        # Canvas for scrollable area
        self.canvas = tk.Canvas(
            self.results_frame,
            bg="#2c3e50",
            highlightthickness=0,
        )
        self.scrollbar = ttk.Scrollbar(
            self.results_frame,
            orient="vertical",
            command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        # Frame inside canvas to hold cards
        self.cards_frame = tk.Frame(self.canvas, bg="#2c3e50")
        self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        # Configure resizing
        self.cards_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

    def generate_campaign(self) -> None:
        """Generate and display a campaign for the selected setting."""
        setting = self.setting_var.get()
        try:
            generate_func = GENERATOR_FUNCTIONS[setting]
            campaign = generate_func()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate campaign: {e}")
            return
        self.current_campaign = campaign
        # Clear existing cards
        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        # Create a card for each entry
        for key, value in campaign.items():
            # Process each (key, value) from campaign.items().
            card = tk.Frame(self.cards_frame, bg="#34495e", bd=1, relief="ridge")
            title_label = tk.Label(
                card,
                text=key,
                bg="#34495e",
                fg="#ecf0f1",
                font=("Helvetica", 14, "bold"),
            )
            desc_label = tk.Label(
                card,
                text=value,
                bg="#34495e",
                fg="#bdc3c7",
                wraplength=1700,
                justify="left",
                font=("Helvetica", 11),
            )
            title_label.pack(anchor="w", padx=8, pady=(4, 0))
            desc_label.pack(anchor="w", padx=8, pady=(0, 6))
            card.pack(fill="x", expand=True, padx=5, pady=5)
        # Enable export button
        self.export_button.state(["!disabled"])
        self.export_json_button.state(["!disabled"])

    def export_campaign(self) -> None:
        """Export campaign."""
        if not self.current_campaign:
            messagebox.showwarning("No Campaign", "Please generate a campaign first.")
            return
        # Ask user where to save the docx
        filename = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word Document", "*.docx")],
            title="Save Campaign as DOCX",
            initialfile="campaign.docx",
        )
        if not filename:
            return  # Cancelled
        try:
            export_to_docx(self.current_campaign, filename)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export DOCX: {e}")
            return
        messagebox.showinfo("Export Successful", f"Campaign saved to {filename}")

    def export_campaign_json(self) -> None:
        """Export the current campaign to a JSON file using the legacy payload format."""
        if not self.current_campaign:
            messagebox.showwarning("No Campaign", "Please generate a campaign first.")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Save Campaign as JSON",
            initialfile="campaign.json",
        )
        if not filename:
            return
        try:
            append_scenario_to_json_file(self.current_campaign, filename)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save JSON: {e}")
            return
        messagebox.showinfo("Export Successful", f"Campaign saved to {filename}")
