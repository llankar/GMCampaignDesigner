import re
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from modules.helpers.logging_helper import log_module_import
from modules.scenarios.scenario_builder_wizard import (
    EntityLinkingStep,
    ReviewStep,
    ScenarioBuilderWizard,
    ScenesPlanningStep,
    WizardStep,
)

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
    {
        "name": "Heist of the Fallen Star",
        "summary": "Steal back a world-shaping artifact before the villain can wield it.",
        "beats": [
            "Discover the artifact's secret vault and its layered defenses.",
            "Infiltrate the gala front to bypass arcane security unnoticed.",
            "Seize the Fallen Star amid betrayals and shifting alliances.",
            "Escape the collapsing vault and decide who safeguards the prize.",
        ],
    },
    {
        "name": "Trial of the Ascendant",
        "summary": "Navigate divine judgment that will anoint or destroy the heroes' champion.",
        "beats": [
            "Interpret omens to prepare for the coming celestial tribunal.",
            "Face avatars of past deeds who argue for the heroes' unworthiness.",
            "Champion undergoes the trial by cosmic ordeal before assembled pantheons.",
            "Accept the verdict and channel newfound power into the campaign's destiny.",
        ],
    },
    {
        "name": "Reckoning at the Fractured Gate",
        "summary": "Seal a planar rupture before it unravels reality across every realm.",
        "beats": [
            "Stabilize the gate long enough to learn the rupture's true cause.",
            "Coordinate allied mages to anchor the battlefield against planar tides.",
            "Battle manifestations of the breach while reversing the cascade.",
            "Choose which realm remains linked as the gate snaps shut forever.",
        ],
    },
    {
        "name": "Rebellion of the Broken Crown",
        "summary": "Lead a populist uprising that topples a tyrant's empire in one decisive strike.",
        "beats": [
            "Rally splintered cells with a unifying call to storm the capital.",
            "Sabotage the crown's war machine to level the playing field.",
            "Topple the tyrant in a duel before the eyes of liberated citizens.",
            "Found a new order that honors the sacrifices of the rebellion.",
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


class FinaleBlueprintStep(WizardStep):
    """Wizard step for composing an epic finale outline before refinement."""

    def __init__(self, master, wizard):
        super().__init__(master)
        self.wizard = wizard
        self.generated_scenario = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        selector_frame = ctk.CTkFrame(self)
        selector_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20, 10))
        selector_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.climax_var = ctk.StringVar(value=CLIMAX_STRUCTURES[0]["name"])
        self.callback_var = ctk.StringVar(value=CALLBACK_TACTICS[0])
        self.escalation_var = ctk.StringVar(value=STAKE_ESCALATIONS[0])
        self.location_var = ctk.StringVar()
        self.title_var = ctk.StringVar()
        self.entity_selectors = {}

        ctk.CTkLabel(selector_frame, text="Climax Structure:").grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        ctk.CTkOptionMenu(
            selector_frame,
            variable=self.climax_var,
            values=[item["name"] for item in CLIMAX_STRUCTURES],
        ).grid(row=0, column=1, columnspan=2, sticky="ew", padx=10, pady=5)

        ctk.CTkLabel(selector_frame, text="Antagonists:").grid(
            row=1, column=0, sticky="w", padx=10, pady=5
        )
        self._create_entity_selector(
            selector_frame,
            row=1,
            column=1,
            key="antagonists",
            button_text="Add Antagonist",
        )

        ctk.CTkLabel(selector_frame, text="Allied Factions:").grid(
            row=1, column=2, sticky="w", padx=10, pady=5
        )
        self._create_entity_selector(
            selector_frame,
            row=1,
            column=3,
            key="allied_factions",
            button_text="Add Faction",
        )

        ctk.CTkLabel(selector_frame, text="Battlefield / Signature Place:").grid(
            row=2, column=0, sticky="w", padx=10, pady=5
        )
        self.location_menu = ctk.CTkOptionMenu(
            selector_frame, variable=self.location_var, values=["None"]
        )
        self.location_menu.grid(row=2, column=1, sticky="ew", padx=10, pady=5)

        ctk.CTkLabel(selector_frame, text="Supporting NPC Allies:").grid(
            row=2, column=2, sticky="w", padx=10, pady=5
        )
        self._create_entity_selector(
            selector_frame,
            row=2,
            column=3,
            key="npc_allies",
            button_text="Add NPC Ally",
        )

        ctk.CTkLabel(selector_frame, text="Callback Tactic:").grid(
            row=3, column=0, sticky="w", padx=10, pady=5
        )
        ctk.CTkOptionMenu(
            selector_frame,
            variable=self.callback_var,
            values=CALLBACK_TACTICS,
        ).grid(row=3, column=1, sticky="ew", padx=10, pady=5)

        ctk.CTkLabel(selector_frame, text="Stakes Escalation:").grid(
            row=3, column=2, sticky="w", padx=10, pady=5
        )
        ctk.CTkOptionMenu(
            selector_frame,
            variable=self.escalation_var,
            values=STAKE_ESCALATIONS,
        ).grid(row=3, column=3, sticky="ew", padx=10, pady=5)

        ctk.CTkLabel(selector_frame, text="Finale Title:").grid(
            row=4, column=0, sticky="w", padx=10, pady=5
        )
        ctk.CTkEntry(selector_frame, textvariable=self.title_var).grid(
            row=4, column=1, columnspan=3, sticky="ew", padx=10, pady=5
        )

        button_row = ctk.CTkFrame(selector_frame, fg_color="transparent")
        button_row.grid(row=5, column=0, columnspan=4, sticky="ew", padx=10, pady=(10, 0))
        button_row.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            button_row,
            text="Generate Finale Outline",
            command=self.generate_outline,
        ).grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(body, text="Campaign Parameters").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 5)
        )
        ctk.CTkLabel(body, text="Finale Preview").grid(
            row=0, column=1, sticky="w", padx=10, pady=(10, 5)
        )

        self.parameter_box = ctk.CTkTextbox(body, height=260, wrap="word")
        self.parameter_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.parameter_box.configure(state="disabled")

        self.preview_box = ctk.CTkTextbox(body, wrap="word")
        self.preview_box.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)
        self.preview_box.configure(state="disabled")

        self._refresh_entities()
        self._refresh_parameter_suggestions()

    # ------------------------------------------------------------------
    def _create_entity_selector(self, parent, row, column, key, button_text):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid(row=row, column=column, sticky="nsew", padx=10, pady=5)
        container.grid_columnconfigure(0, weight=1)

        rows_container = ctk.CTkFrame(container, fg_color="transparent")
        rows_container.grid(row=0, column=0, columnspan=2, sticky="nsew")
        rows_container.grid_columnconfigure(0, weight=1)

        selector = {
            "frame": container,
            "rows": [],
            "vars": [],
            "menus": [],
            "options": ["None"],
            "rows_container": rows_container,
        }

        def remove_row(row_frame, var):
            row_frame.destroy()
            if var in selector["vars"]:
                idx = selector["vars"].index(var)
                selector["vars"].pop(idx)
                selector["menus"].pop(idx)
                selector["rows"].pop(idx)

        def add_row(initial_value=None):
            options = selector["options"] or ["None"]
            row_frame = ctk.CTkFrame(rows_container, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            row_frame.columnconfigure(0, weight=1)

            var = ctk.StringVar()
            menu = ctk.CTkOptionMenu(row_frame, variable=var, values=options)
            menu.grid(row=0, column=0, sticky="ew")

            remove_btn = ctk.CTkButton(
                row_frame,
                text="-",
                width=30,
                command=lambda rf=row_frame, v=var: remove_row(rf, v),
            )
            remove_btn.grid(row=0, column=1, padx=5)

            if initial_value and initial_value in options:
                var.set(initial_value)
            else:
                var.set(options[0])

            selector["rows"].append(row_frame)
            selector["vars"].append(var)
            selector["menus"].append(menu)

        add_button = ctk.CTkButton(container, text=button_text, command=add_row)
        add_button.grid(row=1, column=0, sticky="w", pady=(5, 0))

        selector["add_button"] = add_button
        selector["add_row"] = add_row

        self.entity_selectors[key] = selector

    # ------------------------------------------------------------------
    def _refresh_entities(self):
        def safe_load(wrapper):
            try:
                return wrapper.load_items()
            except Exception:
                return []

        self.npcs = safe_load(self.wizard.npc_wrapper) or []
        self.factions = safe_load(self.wizard.faction_wrapper) or []
        self.places = safe_load(self.wizard.place_wrapper) or []
        self.scenarios = safe_load(self.wizard.scenario_wrapper) or []

        location_options = self._build_option_list(self.places)

        self.location_menu.configure(values=location_options)

        if self.location_var.get() not in location_options:
            self.location_var.set(location_options[0])

        self._update_entity_selector("antagonists", self._get_selector_items("antagonists"))
        self._update_entity_selector("allied_factions", self._get_selector_items("allied_factions"))
        self._update_entity_selector("npc_allies", self._get_selector_items("npc_allies"))

    # ------------------------------------------------------------------
    def _get_selector_items(self, key):
        if key == "antagonists":
            return list(self.npcs) + list(self.factions)
        if key == "allied_factions":
            return list(self.factions)
        if key == "npc_allies":
            return list(self.npcs)
        return []

    # ------------------------------------------------------------------
    def _update_entity_selector(self, key, items):
        selector = self.entity_selectors.get(key)
        if not selector:
            return

        names = self._build_name_list(items)
        if names:
            options = ["None"] + names
        else:
            options = ["None"]

        selector["options"] = options

        for menu, var in zip(selector["menus"], selector["vars"]):
            menu.configure(values=options)
            if var.get() not in options:
                var.set(options[0])

    # ------------------------------------------------------------------
    def _ensure_selector_option(self, selector, value):
        if not value:
            return
        options = selector.get("options") or ["None"]
        if value not in options:
            options = options + [value]
            selector["options"] = options
            for menu in selector["menus"]:
                menu.configure(values=options)

    # ------------------------------------------------------------------
    def _set_entity_selector_values(self, key, values):
        selector = self.entity_selectors.get(key)
        if not selector:
            return

        self._clear_entity_selector(key)

        for value in values or []:
            self._ensure_selector_option(selector, value)
            selector["add_row"](value)

    # ------------------------------------------------------------------
    def _clear_entity_selector(self, key):
        selector = self.entity_selectors.get(key)
        if not selector:
            return

        for row in selector["rows"]:
            row.destroy()

        selector["rows"].clear()
        selector["vars"].clear()
        selector["menus"].clear()

    # ------------------------------------------------------------------
    def _collect_entity_selector_values(self, key):
        selector = self.entity_selectors.get(key)
        if not selector:
            return []

        values = []
        for var in selector["vars"]:
            value = (var.get() or "").strip()
            if value and value != "None":
                values.append(value)
        return self._deduplicate_preserve_order(values)

    # ------------------------------------------------------------------
    def _build_name_list(self, items):
        names = []
        for item in items or []:
            name = self._format_name(item)
            if name:
                names.append(name)
        return self._deduplicate_preserve_order(names)

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
        if not isinstance(item, dict):
            return None
        return item.get("Title") or item.get("Name") or item.get("label")

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_list(text):
        if not text:
            return []
        if isinstance(text, list):
            return [item for item in text if item]
        if not isinstance(text, str):
            return []
        tokens = re.split(r"[\n,;]", text)
        cleaned = [token.strip() for token in tokens]
        return [token for token in cleaned if token]

    # ------------------------------------------------------------------
    @staticmethod
    def _deduplicate_preserve_order(items):
        seen = set()
        ordered = []
        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered

    # ------------------------------------------------------------------
    @staticmethod
    def _format_scene_entities(scene):
        def normalise(values):
            if not values:
                return []
            if isinstance(values, (list, tuple)):
                return [value for value in values if value]
            if isinstance(values, str):
                return [value.strip() for value in values.split(",") if value.strip()]
            return []

        def join(values):
            return ", ".join(values) if values else "None"

        npcs = normalise(scene.get("NPCs")) if isinstance(scene, dict) else []
        factions = normalise(scene.get("Factions")) if isinstance(scene, dict) else []
        places = normalise(scene.get("Places")) if isinstance(scene, dict) else []
        creatures = normalise(scene.get("Creatures")) if isinstance(scene, dict) else []

        return [
            f"    NPCs: {join(npcs)}",
            f"    Factions: {join(factions)}",
            f"    Places: {join(places)}",
            f"    Creatures: {join(creatures)}",
        ]

    # ------------------------------------------------------------------
    def _refresh_parameter_suggestions(self):
        lines = ["Potential Antagonists:"]
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

        lines.append("\nNPC Allies:")
        if self.npcs:
            for npc in self.npcs[:8]:
                lines.append(f" • {self._format_name(npc)}")
        else:
            lines.append(" • No NPC allies recorded.")

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
    def load_state(self, state):  # pragma: no cover - UI synchronization
        self._refresh_entities()
        self._refresh_parameter_suggestions()

        config = (state or {}).get("_finale_config", {})
        self._set_if_available(self.climax_var, config.get("climax"), [c["name"] for c in CLIMAX_STRUCTURES])
        self._set_if_available(self.callback_var, config.get("callback"), CALLBACK_TACTICS)
        self._set_if_available(self.escalation_var, config.get("escalation"), STAKE_ESCALATIONS)
        self._set_entity_selector_values(
            "antagonists", self._parse_list(config.get("antagonists") or config.get("antagonist"))
        )
        self._set_entity_selector_values(
            "allied_factions", self._parse_list(config.get("allied_factions") or config.get("ally"))
        )
        self._set_entity_selector_values(
            "npc_allies", self._parse_list(config.get("npc_allies") or config.get("npc_allies_list"))
        )
        self._set_if_available(self.location_var, config.get("location"), self.location_menu.cget("values"))

        title = (state or {}).get("Title", "")
        self.title_var.set(title)
        self.generated_scenario = None
        self._display_preview_from_state(state)

    # ------------------------------------------------------------------
    @staticmethod
    def _set_if_available(var, value, options):
        if not value:
            return
        if isinstance(options, tuple):
            options = list(options)
        if value in options:
            var.set(value)

    # ------------------------------------------------------------------
    def save_state(self, state):  # pragma: no cover - UI synchronization
        if state is None:
            return False

        config = {
            "climax": self.climax_var.get(),
            "callback": self.callback_var.get(),
            "escalation": self.escalation_var.get(),
            "antagonists": self._collect_entity_selector_values("antagonists"),
            "allied_factions": self._collect_entity_selector_values("allied_factions"),
            "npc_allies": self._collect_entity_selector_values("npc_allies"),
            "location": self.location_var.get(),
        }
        state["_finale_config"] = config

        title = self.title_var.get().strip()
        if title:
            state["Title"] = title

        if self.generated_scenario is not None:
            self._apply_scenario_to_state(state, self.generated_scenario)
            self.generated_scenario = None
            return True

        if not state.get("Scenes"):
            messagebox.showwarning(
                "Generate Finale",
                "Generate a finale outline before proceeding to the next step.",
            )
            return False

        return True

    # ------------------------------------------------------------------
    def generate_outline(self):  # pragma: no cover - UI interaction
        scenario = self._build_scenario_from_config()
        if scenario is None:
            return
        self.generated_scenario = scenario
        self.title_var.set(scenario["Title"])
        self._display_preview(scenario)

    # ------------------------------------------------------------------
    def _build_scenario_from_config(self):
        climax_name = self.climax_var.get()
        climax = next((item for item in CLIMAX_STRUCTURES if item["name"] == climax_name), None)
        if not climax:
            messagebox.showerror("Missing Data", "Select a climax structure before generating.")
            return None

        antagonists = self._collect_entity_selector_values("antagonists")
        allied_factions = self._collect_entity_selector_values("allied_factions")
        npc_allies = self._collect_entity_selector_values("npc_allies")
        location = self._clean_selection(self.location_var.get())
        callback = self.callback_var.get()
        escalation = self.escalation_var.get()

        title = self.title_var.get().strip()
        if not title:
            title = self._default_title(climax_name, location)

        primary_antagonist = antagonists[0] if antagonists else ""
        primary_ally = allied_factions[0] if allied_factions else ""

        summary_lines = [
            f"Structure: {climax_name}",
            f"Antagonists: {', '.join(antagonists) if antagonists else 'Unspecified'}",
            f"Allied Factions: {', '.join(allied_factions) if allied_factions else 'Unspecified'}",
            f"NPC Allies: {', '.join(npc_allies) if npc_allies else 'Unspecified'}",
            f"Location: {location or 'To Be Determined'}",
            f"Stakes Escalation: {escalation}",
            f"Callback: {callback}",
        ]

        scenes = []
        aggregated_npcs = []
        aggregated_factions = []

        callback_scene_index = self._select_callback_scene_index(climax["beats"])
        escalation_scene_index = self._select_escalation_scene_index(
            climax["beats"], callback_scene_index
        )

        callback_sentence = f"Callback Beat: {callback}"
        escalation_sentence = f"Escalation Beat: {escalation}"

        for idx, beat in enumerate(climax["beats"], start=1):
            beat_text = self._personalise_beat(beat, primary_antagonist, primary_ally, location)
            scene_title = self._scene_title(idx, beat_text)
            scene_npcs, scene_factions = self._infer_scene_participants(
                beat,
                antagonists,
                npc_allies,
                allied_factions,
            )

            scene_index = idx - 1
            guidance_sentences = []
            if scene_index == callback_scene_index:
                guidance_sentences.append(callback_sentence)
            if scene_index == escalation_scene_index:
                guidance_sentences.append(escalation_sentence)

            if guidance_sentences:
                beat_text = self._append_guidance_sentences(beat_text, guidance_sentences)

            aggregated_npcs.extend(scene_npcs)
            aggregated_factions.extend(scene_factions)
            scenes.append(
                {
                    "Title": scene_title,
                    "Summary": beat_text,
                    "Text": beat_text,
                    "SceneType": "Auto",
                    "NPCs": scene_npcs,
                    "Places": [location] if location else [],
                    "Creatures": [],
                    "Maps": [],
                    "Factions": scene_factions,
                }
            )

        secrets = [escalation, callback]

        scenario = {
            "Title": title,
            "Summary": "\n".join(summary_lines),
            "Secrets": "\n".join(secrets),
            "Scenes": scenes,
            "Places": [location] if location else [],
            "NPCs": self._deduplicate_preserve_order(aggregated_npcs or (antagonists + npc_allies)),
            "Creatures": [],
            "Factions": self._deduplicate_preserve_order(aggregated_factions or allied_factions),
            "Objects": [],
        }

        return scenario

    # ------------------------------------------------------------------
    @staticmethod
    def _scene_title(index, beat_text):
        headline = beat_text.split(".")[0].strip()
        if not headline:
            headline = f"Phase {index}"
        if len(headline) > 60:
            headline = headline[:57] + "..."
        return f"Phase {index}: {headline}"

    # ------------------------------------------------------------------
    @staticmethod
    def _personalise_beat(beat, antagonist, ally, location):
        beat_text = beat
        if antagonist and "antagonist" in beat.lower():
            beat_text = beat_text.replace("the antagonist", antagonist)
            beat_text = beat_text.replace("antagonist", antagonist)
        if ally and any(token in beat.lower() for token in ("allies", "allied")):
            beat_text = beat_text.replace("allied forces", ally)
            beat_text = beat_text.replace("allies", ally)
            beat_text = beat_text.replace("allied", ally)
        if location and any(
            token in beat.lower() for token in ("stronghold", "site", "battleground", "battlefield")
        ):
            beat_text = beat_text.replace("stronghold", location)
            beat_text = beat_text.replace("ritual site", location)
            beat_text = beat_text.replace("battlefield", location)
            beat_text = beat_text.replace("battleground", location)
        return beat_text

    # ------------------------------------------------------------------
    @staticmethod
    def _append_guidance_sentences(base_text, sentences):
        text = base_text.rstrip()
        if text and text[-1] not in ".!?":
            text += "."
        appended = " ".join(sentences)
        return f"{text} {appended}" if text else appended

    # ------------------------------------------------------------------
    @staticmethod
    def _select_callback_scene_index(beats):
        if not beats:
            return -1

        keywords = (
            "duel",
            "confront",
            "counterattack",
            "disrupt",
            "flip",
            "defend",
            "breach",
            "ritual",
        )
        for index in range(len(beats) - 2, -1, -1):
            beat_lower = beats[index].lower()
            if any(keyword in beat_lower for keyword in keywords):
                return index

        if len(beats) >= 2:
            return len(beats) - 2
        return 0

    # ------------------------------------------------------------------
    @staticmethod
    def _select_escalation_scene_index(beats, callback_index):
        if not beats:
            return -1

        final_index = len(beats) - 1
        if final_index != callback_index:
            return final_index

        if final_index - 1 >= 0:
            return final_index - 1
        return final_index

    # ------------------------------------------------------------------
    def _infer_scene_participants(self, beat, antagonists, npc_allies, allied_factions):
        beat_lower = (beat or "").lower()

        def name_in_text(name):
            if not name:
                return False
            return name.lower() in beat_lower

        antagonist_keywords = {
            "antagonist",
            "villain",
            "enemy",
            "mastermind",
            "traitor",
            "opponent",
            "conspirator",
            "commander",
        }
        ally_keywords = {
            "allies",
            "ally",
            "allied",
            "support",
            "reinforcement",
            "reinforcements",
            "defenders",
            "friends",
            "aid",
            "backup",
            "supporting",
            "supporters",
            "forces",
            "army",
            "squad",
            "faction",
        }
        faction_keywords = {
            "faction",
            "coalition",
            "order",
            "guild",
            "clan",
            "alliance",
            "cabal",
            "council",
            "forces",
        }

        include_antagonists = bool(antagonists) and (
            any(keyword in beat_lower for keyword in antagonist_keywords)
            or any(name_in_text(name) for name in antagonists)
        )
        include_allies = bool(npc_allies) and (
            any(keyword in beat_lower for keyword in ally_keywords)
            or any(name_in_text(name) for name in npc_allies)
        )
        include_factions = bool(allied_factions) and (
            any(keyword in beat_lower for keyword in faction_keywords)
            or any(name_in_text(name) for name in allied_factions)
            or include_allies
        )

        scene_npcs = []
        scene_factions = []
        if include_antagonists:
            scene_npcs.extend(antagonists)
        if include_allies:
            scene_npcs.extend(npc_allies)
        if include_factions:
            scene_factions.extend(allied_factions)

        scene_npcs = self._deduplicate_preserve_order(scene_npcs)
        scene_factions = self._deduplicate_preserve_order(scene_factions)
        return scene_npcs, scene_factions

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
    def _apply_scenario_to_state(self, state, scenario):
        state["Title"] = scenario["Title"]
        state["Summary"] = scenario["Summary"]
        state["Secrets"] = scenario["Secrets"]
        state["Secret"] = scenario["Secrets"]
        state["Scenes"] = scenario["Scenes"]
        state["_SceneLayout"] = []
        state["Places"] = scenario["Places"]
        state["NPCs"] = scenario["NPCs"]
        state["Creatures"] = scenario["Creatures"]
        state["Factions"] = scenario["Factions"]
        state["Objects"] = scenario["Objects"]

    # ------------------------------------------------------------------
    def _display_preview(self, scenario):
        lines = [scenario["Title"], "", scenario["Summary"], "", "Scenes:"]
        for scene in scenario["Scenes"]:
            lines.append(f" - {scene.get('Title')}: {scene.get('Summary')}")
            lines.extend(self._format_scene_entities(scene))
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
    def _display_preview_from_state(self, state):
        if not state:
            self.preview_box.configure(state="normal")
            self.preview_box.delete("1.0", tk.END)
            self.preview_box.configure(state="disabled")
            return

        summary = state.get("Summary") or ""
        secrets = state.get("Secrets") or ""
        scenes = state.get("Scenes") or []

        lines = [state.get("Title", ""), "", summary, "", "Scenes:"]
        if scenes:
            for scene in scenes:
                if isinstance(scene, dict):
                    lines.append(f" - {scene.get('Title', 'Scene')}: {scene.get('Summary', '')}")
                    lines.extend(self._format_scene_entities(scene))
                else:
                    lines.append(f" - {scene}")
        else:
            lines.append(" - (No scenes generated yet)")

        lines.append("")
        lines.append("Secrets:")
        if secrets:
            for secret in secrets.split("\n"):
                lines.append(f" - {secret}")
        else:
            lines.append(" - (None)")

        preview = "\n".join(lines)
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", tk.END)
        self.preview_box.insert("1.0", preview)
        self.preview_box.configure(state="disabled")


class EpicFinalePlannerWizard(ScenarioBuilderWizard):
    """Scenario builder variant tailored for planning epic finales."""

    def __init__(self, master, on_saved=None, *, initial_scenario=None):
        super().__init__(master, on_saved=on_saved, initial_scenario=initial_scenario)
        self.title("Epic Finale Planner")
        self.geometry("1500x900")

    # ------------------------------------------------------------------
    def _create_steps(self):  # pragma: no cover - UI layout
        entity_wrappers = {
            "npcs": self.npc_wrapper,
            "places": self.place_wrapper,
            "factions": self.faction_wrapper,
            "creatures": self.creature_wrapper,
            "objects": self.object_wrapper,
            "maps": self.map_wrapper,
        }

        planning_step = ScenesPlanningStep(
            self.step_container,
            {
                key: wrapper
                for key, wrapper in entity_wrappers.items()
                if key in ("npcs", "creatures", "places", "maps")
            },
            scenario_wrapper=self.scenario_wrapper,
        )

        self.steps = [
            ("Finale Blueprint", FinaleBlueprintStep(self.step_container, self)),
            ("Visual Builder", planning_step),
            ("Entity Linking", EntityLinkingStep(self.step_container, entity_wrappers)),
            ("Review", ReviewStep(self.step_container)),
        ]

        for _, frame in self.steps:
            frame.grid(row=0, column=0, sticky="nsew")

        for _, frame in self.steps:
            if hasattr(frame, "set_state_binding"):
                frame.set_state_binding(self.wizard_state, self._on_wizard_state_changed)
