import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


CLIMAX_STRUCTURES = [
    {
        "name": "Showdown of Champions",
        "summary": "Face the antagonist head-on with allies providing tactical support.",
        "beats": [
            "Gather intelligence on the villain's final gambit.",
            "Breach the antagonist's stronghold with help from allies.",
            "Duel the antagonist while allies neutralize key threats.",
            "Resolve lingering threads and cement the campaign's legacy.",
        ],
    },
    {
        "name": "Race Against Cataclysm",
        "summary": "Stop a world-altering ritual or doomsday device before it is unleashed.",
        "beats": [
            "Identify the final ritual site and the stakes of failure.",
            "Overcome layered defenses while time rapidly runs out.",
            "Disrupt the ritual amid chaotic backlash and hard choices.",
            "Decide how to handle the fallout and surviving villains.",
        ],
    },
    {
        "name": "Siege of the Sanctuary",
        "summary": "Defend a beloved location from overwhelming enemy forces.",
        "beats": [
            "Prepare fortifications and rally allied forces.",
            "Withstand the first enemy assault to learn their tactics.",
            "Counterattack a hidden commander or siege engine.",
            "End the siege with a dramatic sacrifice or decisive strike.",
        ],
    },
    {
        "name": "Coup of Shadows",
        "summary": "Expose and dismantle a conspiracy that turns allies against each other.",
        "beats": [
            "Unmask conspirators embedded within trusted ranks.",
            "Flip a key traitor or faction before the final betrayal.",
            "Confront the mastermind in a realm of shifting allegiances.",
            "Rebuild trust and reshape the political order going forward.",
        ],
    },
]

CALLBACK_TACTICS = [
    "Invoke a treasured NPC's past aid to inspire the heroes.",
    "Reveal that an earlier side quest artifact is the ritual's key.",
    "Have a redeemed villain return to settle an old debt.",
    "Tie the finale to an unresolved mystery from the campaign's first act.",
    "Let a fallen ally's message resurface at the pivotal moment.",
]

STAKE_ESCALATIONS = [
    "Raise the threat from local devastation to global upheaval.",
    "Force the heroes to choose between victory and saving innocents.",
    "Reveal the antagonist serves an even darker patron.",
    "Introduce collateral damage that jeopardizes allied factions.",
    "Twist the battlefield into a volatile, reality-warping arena.",
]


class EpicFinalePlannerWindow(ctk.CTkToplevel):
    """Modal window helping the GM craft a finale using campaign entities."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Epic Finale Planner")
        self.geometry("960x720")
        self.minsize(800, 640)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        self.generated_scenario = None

        self._load_entities()
        self._build_widgets()
        self._refresh_parameter_suggestions()

    # ------------------------------------------------------------------
    def _load_entities(self):
        self.factions = self._load_table("factions")
        self.npcs = self._load_table("npcs")
        self.places = self._load_table("places")
        self.scenarios = self._load_table("scenarios")

    # ------------------------------------------------------------------
    @staticmethod
    def _load_table(table_name):
        try:
            wrapper = GenericModelWrapper(table_name)
            return wrapper.load_items()
        except Exception:
            return []

    # ------------------------------------------------------------------
    def _build_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        selector_frame = ctk.CTkFrame(self)
        selector_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20, 10))
        selector_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self.climax_var = ctk.StringVar(value=CLIMAX_STRUCTURES[0]["name"])
        self.callback_var = ctk.StringVar(value=CALLBACK_TACTICS[0])
        self.escalation_var = ctk.StringVar(value=STAKE_ESCALATIONS[0])
        self.antagonist_var = ctk.StringVar()
        self.ally_var = ctk.StringVar()
        self.location_var = ctk.StringVar()

        # Dropdown helpers
        ctk.CTkLabel(selector_frame, text="Climax Structure:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkOptionMenu(selector_frame, variable=self.climax_var,
                          values=[item["name"] for item in CLIMAX_STRUCTURES]).grid(row=0, column=1, columnspan=2, sticky="ew", padx=10, pady=5)

        ctk.CTkLabel(selector_frame, text="Main Antagonist (NPC):").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        antagonist_options = self._build_option_list(self.npcs)
        ctk.CTkOptionMenu(selector_frame, variable=self.antagonist_var,
                          values=antagonist_options).grid(row=1, column=1, sticky="ew", padx=10, pady=5)
        self.antagonist_var.set(antagonist_options[0])

        ctk.CTkLabel(selector_frame, text="Allied Faction:").grid(row=1, column=2, sticky="w", padx=10, pady=5)
        ally_options = self._build_option_list(self.factions)
        ctk.CTkOptionMenu(selector_frame, variable=self.ally_var,
                          values=ally_options).grid(row=1, column=3, sticky="ew", padx=10, pady=5)
        self.ally_var.set(ally_options[0])

        ctk.CTkLabel(selector_frame, text="Battlefield / Signature Place:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        location_options = self._build_option_list(self.places)
        ctk.CTkOptionMenu(selector_frame, variable=self.location_var,
                          values=location_options).grid(row=2, column=1, sticky="ew", padx=10, pady=5)
        self.location_var.set(location_options[0])

        ctk.CTkLabel(selector_frame, text="Callback Tactic:").grid(row=2, column=2, sticky="w", padx=10, pady=5)
        ctk.CTkOptionMenu(selector_frame, variable=self.callback_var,
                          values=CALLBACK_TACTICS).grid(row=2, column=3, sticky="ew", padx=10, pady=5)

        ctk.CTkLabel(selector_frame, text="Stakes Escalation:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkOptionMenu(selector_frame, variable=self.escalation_var,
                          values=STAKE_ESCALATIONS).grid(row=3, column=1, sticky="ew", padx=10, pady=5)

        ctk.CTkLabel(selector_frame, text="Finale Title:").grid(row=3, column=2, sticky="w", padx=10, pady=5)
        self.title_var = ctk.StringVar()
        ctk.CTkEntry(selector_frame, textvariable=self.title_var).grid(row=3, column=3, sticky="ew", padx=10, pady=5)

        button_row = ctk.CTkFrame(selector_frame, fg_color="transparent")
        button_row.grid(row=4, column=0, columnspan=4, sticky="ew", padx=10, pady=(10, 0))
        button_row.columnconfigure((0, 1), weight=1)

        self.generate_btn = ctk.CTkButton(button_row, text="Generate Finale Outline", command=self.generate_outline)
        self.generate_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.save_btn = ctk.CTkButton(button_row, text="Add Finale to Database", command=self.save_to_db, state="disabled")
        self.save_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ctk.CTkLabel(body, text="Campaign Parameters").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        ctk.CTkLabel(body, text="Finale Preview").grid(row=0, column=1, sticky="w", padx=10, pady=(10, 5))

        self.parameter_box = ctk.CTkTextbox(body, height=260, wrap="word")
        self.parameter_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.parameter_box.configure(state="disabled")

        self.preview_box = ctk.CTkTextbox(body, wrap="word")
        self.preview_box.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)
        self.preview_box.configure(state="disabled")

    # ------------------------------------------------------------------
    def _build_option_list(self, items):
        names = [self._format_name(item) for item in items if self._format_name(item)]
        if not names:
            names = ["None"]
        else:
            names.insert(0, "None")
        return names

    # ------------------------------------------------------------------
    @staticmethod
    def _format_name(item):
        return item.get("Title") or item.get("Name") or item.get("label")

    # ------------------------------------------------------------------
    def _refresh_parameter_suggestions(self):
        lines = []
        lines.append("Potential Antagonists:")
        if self.npcs:
            for npc in self.npcs[:8]:
                lines.append(f" • {self._format_name(npc)}")
        else:
            lines.append(" • No NPCs in current campaign database.")

        lines.append("\nAllied Factions:")
        if self.factions:
            for faction in self.factions[:8]:
                lines.append(f" • {self._format_name(faction)}")
        else:
            lines.append(" • No factions available.")

        lines.append("\nSignature Locations:")
        if self.places:
            for place in self.places[:8]:
                lines.append(f" • {self._format_name(place)}")
        else:
            lines.append(" • No places recorded in database.")

        lines.append("\nExisting Scenario Threads:")
        if self.scenarios:
            for scenario in self.scenarios[:8]:
                lines.append(f" • {scenario.get('Title')}")
        else:
            lines.append(" • No existing scenarios to reference.")

        text = "\n".join(lines)
        self.parameter_box.configure(state="normal")
        self.parameter_box.delete("1.0", tk.END)
        self.parameter_box.insert("1.0", text)
        self.parameter_box.configure(state="disabled")

    # ------------------------------------------------------------------
    def generate_outline(self):
        climax_name = self.climax_var.get()
        climax = next((item for item in CLIMAX_STRUCTURES if item["name"] == climax_name), None)
        if not climax:
            messagebox.showerror("Missing Data", "Select a climax structure before generating.")
            return

        antagonist = self._clean_selection(self.antagonist_var.get())
        ally = self._clean_selection(self.ally_var.get())
        location = self._clean_selection(self.location_var.get())
        callback = self.callback_var.get()
        escalation = self.escalation_var.get()

        title = self.title_var.get().strip()
        if not title:
            title = self._default_title(climax_name, location)
            self.title_var.set(title)

        summary_lines = [
            f"Structure: {climax_name}",
            f"Antagonist: {antagonist or 'Unspecified'}",
            f"Allied Support: {ally or 'Unspecified'}",
            f"Location: {location or 'To Be Determined'}",
            f"Stakes Escalation: {escalation}",
            f"Callback: {callback}",
        ]

        scenes = []
        for idx, beat in enumerate(climax["beats"], start=1):
            beat_text = beat
            if antagonist and "antagonist" in beat.lower():
                beat_text = beat_text.replace("the antagonist", antagonist)
                beat_text = beat_text.replace("antagonist", antagonist)
            if ally and any(token in beat.lower() for token in ("allies", "allied")):
                beat_text = beat_text.replace("allied forces", ally)
                beat_text = beat_text.replace("allies", ally)
                beat_text = beat_text.replace("allied", ally)
            if location and any(token in beat.lower() for token in ("stronghold", "site", "battleground")):
                beat_text = beat_text.replace("stronghold", location)
                beat_text = beat_text.replace("ritual site", location)
                beat_text = beat_text.replace("battlefield", location)
                beat_text = beat_text.replace("battleground", location)
            scenes.append(f"Scene {idx}: {beat_text}")

        secrets = [
            escalation,
            callback,
        ]

        scenario = {
            "Title": title,
            "Summary": "\n".join(summary_lines),
            "Secrets": "\n".join(secrets),
            "Scenes": scenes,
            "Places": [location] if location else [],
            "NPCs": [antagonist] if antagonist else [],
            "Creatures": [],
            "Factions": [ally] if ally else [],
            "Objects": [],
        }

        self.generated_scenario = scenario
        self._display_preview(scenario)
        self.save_btn.configure(state="normal")

    # ------------------------------------------------------------------
    @staticmethod
    def _clean_selection(value):
        if not value or value == "None":
            return ""
        return value

    # ------------------------------------------------------------------
    @staticmethod
    def _default_title(climax_name, location):
        base = climax_name
        if location:
            base = f"{climax_name} at {location}"
        return base

    # ------------------------------------------------------------------
    def _display_preview(self, scenario):
        lines = [scenario["Title"], "", scenario["Summary"], "", "Scenes:"]
        for scene in scenario["Scenes"]:
            lines.append(f" - {scene}")
        lines.append("")
        lines.append("Secrets:")
        for secret in scenario["Secrets"].split("\n"):
            lines.append(f" - {secret}")

        preview = "\n".join(lines)
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", tk.END)
        self.preview_box.insert("1.0", preview)
        self.preview_box.configure(state="disabled")

    # ------------------------------------------------------------------
    def save_to_db(self):
        if not self.generated_scenario:
            messagebox.showwarning("No Finale", "Generate a finale outline first.")
            return

        title = self.generated_scenario.get("Title", "").strip()
        if not title:
            messagebox.showwarning("Missing Title", "Provide a title for the finale before saving.")
            return

        wrapper = GenericModelWrapper("scenarios")
        existing = wrapper.load_items()
        if any(item.get("Title") == title for item in existing):
            messagebox.showwarning("Duplicate Title", f"A scenario titled '{title}' already exists.")
            return

        try:
            wrapper.save_items([self.generated_scenario], replace=False)
        except Exception as exc:
            messagebox.showerror("Database Error", f"Failed to save finale: {exc}")
            return

        messagebox.showinfo("Finale Saved", f"Finale '{title}' added to database.")
        self.save_btn.configure(state="disabled")
