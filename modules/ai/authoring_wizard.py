import re
import json
import customtkinter as ctk
from tkinter import messagebox

from modules.ai.factory import create_ai_client
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

def _parse_json_relaxed(s: str):
    if not s:
        raise RuntimeError("Empty AI response")
    s = s.strip()
    # Remove markdown fences if present
    if s.startswith("```"):
        s = re.sub(r"^```(json)?", "", s, flags=re.IGNORECASE).strip()
        s = s.rstrip("`").strip()
    # Try direct
    try:
        return json.loads(s)
    except Exception:
        pass
    # Find first JSON object or array
    start = None
    for i, ch in enumerate(s):
        if ch in '{[':
            start = i
            break
    if start is not None:
        tail = s[start:]
        for j in range(len(tail), max(len(tail) - 2000, 0), -1):
            chunk = tail[:j]
            try:
                return json.loads(chunk)
            except Exception:
                continue
    raise RuntimeError("Failed to parse JSON from AI response")


class AuthoringWizardView(ctk.CTkFrame):
    """AI-assisted authoring for NPCs and Scenarios with presets and checks."""

    def __init__(self, parent):
        super().__init__(parent)
        # Data access
        self.npcs = GenericModelWrapper("npcs")
        self.scenarios = GenericModelWrapper("scenarios")
        self.places = GenericModelWrapper("places")
        self.factions = GenericModelWrapper("factions")
        self.infos = GenericModelWrapper("informations")
        self.ai = create_ai_client()
        # Keep last generated structured data so we can save/check while
        # displaying a human-friendly text view in the UI.
        self._last_npc_data = None
        self._last_scenario_data = None

        # Presets
        self.tones = [
            "Neutral GM", "Noir", "Heroic High Fantasy", "Grimdark", "Whimsical", "Pulp Adventure", "Urban Fantasy"
        ]
        self.styles = [
            "Concise", "Evocative", "Procedural GM Notes", "Flowery Prose", "Rules-Light", "Investigation"
        ]
        self.tone_var = ctk.StringVar(value=self.tones[0])
        self.style_var = ctk.StringVar(value=self.styles[2])
        self.use_lore_var = ctk.BooleanVar(value=True)

        self._build_layout()

    # UI -----------------------------------------------------------------
    def _build_layout(self):
        # Presets bar
        bar = ctk.CTkFrame(self)
        bar.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(bar, text="Tone:").pack(side="left")
        ctk.CTkOptionMenu(bar, values=self.tones, variable=self.tone_var, width=180).pack(side="left", padx=6)
        ctk.CTkLabel(bar, text="Style:").pack(side="left")
        ctk.CTkOptionMenu(bar, values=self.styles, variable=self.style_var, width=200).pack(side="left", padx=6)
        ctk.CTkCheckBox(bar, text="Use Lore Context", variable=self.use_lore_var).pack(side="left", padx=12)

        # Tabs
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_npc = self.tabs.add("NPC")
        self.tab_scenario = self.tabs.add("Scenario")
        self.tab_beats = self.tabs.add("Beats")

        self._build_tab_npc(self.tab_npc)
        self._build_tab_scenario(self.tab_scenario)
        self._build_tab_beats(self.tab_beats)

    def select_for(self, entity_type: str):
        """Select default tab based on entity type (e.g., 'npcs' or 'scenarios')."""
        et = (entity_type or "").lower()
        if et == "npcs":
            try:
                self.tabs.set("NPC")
            except Exception:
                pass
        elif et == "scenarios":
            try:
                self.tabs.set("Scenario")
            except Exception:
                pass
        else:
            try:
                self.tabs.set("Beats")
            except Exception:
                pass

    def _build_tab_npc(self, tab):
        form = ctk.CTkFrame(tab)
        form.pack(fill="x", padx=6, pady=6)

        self.npc_name = ctk.StringVar()
        self.npc_role = ctk.StringVar()
        self.npc_faction = ctk.StringVar()
        self.npc_location = ctk.StringVar()
        self.npc_genre = ctk.StringVar(value="Urban Fantasy")

        def row(label, var):
            r = ctk.CTkFrame(form)
            r.pack(fill="x", pady=4)
            ctk.CTkLabel(r, text=label, width=120, anchor="w").pack(side="left")
            ctk.CTkEntry(r, textvariable=var).pack(side="left", fill="x", expand=True)
        row("Name", self.npc_name)
        row("Role/Archetype", self.npc_role)
        row("Faction", self.npc_faction)
        row("Primary Location", self.npc_location)
        row("Genre", self.npc_genre)

        btns = ctk.CTkFrame(tab)
        btns.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkButton(btns, text="Generate NPC", command=self.generate_npc).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Consistency Check", command=self.check_npc_consistency).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Save to DB", command=self.save_npc).pack(side="left", padx=4)

        self.npc_output = ctk.CTkTextbox(tab, wrap="word")
        self.npc_output.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_tab_scenario(self, tab):
        form = ctk.CTkFrame(tab)
        form.pack(fill="x", padx=6, pady=6)

        self.sc_title = ctk.StringVar()
        self.sc_premise = ctk.StringVar()
        self.sc_theme = ctk.StringVar()
        self.sc_antagonist = ctk.StringVar()

        def row(label, var):
            r = ctk.CTkFrame(form)
            r.pack(fill="x", pady=4)
            ctk.CTkLabel(r, text=label, width=120, anchor="w").pack(side="left")
            ctk.CTkEntry(r, textvariable=var).pack(side="left", fill="x", expand=True)
        row("Title", self.sc_title)
        row("Premise", self.sc_premise)
        row("Theme", self.sc_theme)
        row("Antagonist", self.sc_antagonist)

        btns = ctk.CTkFrame(tab)
        btns.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkButton(btns, text="Generate Scenario", command=self.generate_scenario).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Consistency Check", command=self.check_scenario_consistency).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Save to DB", command=self.save_scenario).pack(side="left", padx=4)

        self.sc_output = ctk.CTkTextbox(tab, wrap="word")
        self.sc_output.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_tab_beats(self, tab):
        split = ctk.CTkFrame(tab)
        split.pack(fill="both", expand=True, padx=6, pady=6)

        left = ctk.CTkFrame(split)
        right = ctk.CTkFrame(split)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(left, text="Beat (short sentence/idea)").pack(anchor="w")
        self.beat_input = ctk.CTkTextbox(left, wrap="word", height=160)
        self.beat_input.pack(fill="both", expand=True)
        ctk.CTkButton(left, text="Expand Beat", command=self.expand_beat).pack(pady=6)

        ctk.CTkLabel(right, text="Expanded Scene").pack(anchor="w")
        self.beat_output = ctk.CTkTextbox(right, wrap="word")
        self.beat_output.pack(fill="both", expand=True)

    # Lore ---------------------------------------------------------------
    def _lore_digest(self, max_chars: int = 2000) -> str:
        def take(items, key, n):
            vals = []
            for it in items[:n]:
                v = it.get(key)
                if isinstance(v, dict):
                    text = v.get("text", "")
                else:
                    text = str(v) if v is not None else ""
                vals.append(text)
            return vals

        npc_items = self.npcs.load_items()
        place_items = self.places.load_items()
        faction_items = self.factions.load_items()
        info_items = self.infos.load_items()

        npc_lines = []
        for it in npc_items[:20]:
            name = it.get("Name", "?")
            role = it.get("Role", "")
            facs = it.get("Factions", [])
            if isinstance(facs, str):
                try:
                    facs = json.loads(facs)
                except Exception:
                    facs = []
            npc_lines.append(f"- {name}: {role} | Factions: {', '.join(facs or [])}")

        place_lines = [f"- {it.get('Name','?')}: {self._short(it.get('Description',''))}" for it in place_items[:15]]
        fac_lines = [f"- {it.get('Name','?')}" for it in faction_items[:20]]
        info_lines = [f"- {self._short(it.get('Information',''))}" for it in info_items[:20]]

        parts = [
            "Lore Summary:",
            "NPCs:\n" + "\n".join(npc_lines),
            "Places:\n" + "\n".join(place_lines),
            "Factions:\n" + "\n".join(fac_lines),
            "Facts:\n" + "\n".join(info_lines),
        ]
        digest = "\n\n".join(parts)
        if len(digest) > max_chars:
            digest = digest[:max_chars] + "..."
        return digest

    @staticmethod
    def _short(val, n=120):
        if isinstance(val, dict):
            text = val.get("text", "")
        else:
            text = str(val) if val is not None else ""
        text = text.replace("\n", " ").strip()
        return text if len(text) <= n else text[:n] + "..."

    # AI calls -----------------------------------------------------------
    def _system_hdr(self):
        return (
            f"You are an expert RPG design assistant. Tone: {self.tone_var.get()}. "
            f"Style: {self.style_var.get()}. Be coherent and concise for GMs."
        )

    def _with_lore(self, prompt: str) -> str:
        if not self.use_lore_var.get():
            return prompt
        return f"{prompt}\n\n{self._lore_digest()}"

    def _chat_json(self, user_prompt: str) -> dict:
        messages = [
            {"role": "system", "content": self._system_hdr() + " Return strict JSON only."},
            {"role": "user", "content": user_prompt},
        ]
        resp = self.ai.chat(messages)
        try:
            return _parse_json_relaxed(resp)
        except Exception as e:
            messagebox.showerror("AI JSON Error", f"Failed to parse JSON: {e}\nRaw: {resp[:5000]}")
            return {}

    def _chat_text(self, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": self._system_hdr() + " Return plain text."},
            {"role": "user", "content": user_prompt},
        ]
        return self.ai.chat(messages)

    # -------- Formatting helpers (text view) --------
    def _format_kv(self, key, value):
        text = self._as_text(value).strip()
        return f"{key}:\n{text}\n" if text else ""

    def _format_list(self, title, items):
        if not items:
            return ""
        lines = []
        for it in items:
            if isinstance(it, dict):
                # Try common keys
                name = it.get("Name") or it.get("Title") or it.get("text") or str(it)
                lines.append(f"- {self._as_text(name)}")
            else:
                lines.append(f"- {self._as_text(it)}")
        return f"{title}:\n" + "\n".join(lines) + "\n"

    def _format_npc_text(self, data: dict) -> str:
        parts = []
        parts.append(self._format_kv("Name", data.get("Name")))
        parts.append(self._format_kv("Role", data.get("Role")))
        parts.append(self._format_kv("Description", data.get("Description")))
        parts.append(self._format_kv("Background", data.get("Background")))
        parts.append(self._format_kv("Personality", data.get("Personality")))
        parts.append(self._format_kv("Motivation", data.get("Motivation")))
        parts.append(self._format_kv("Quote", data.get("Quote")))
        parts.append(self._format_kv("Roleplaying Cues", data.get("RoleplayingCues")))
        parts.append(self._format_list("Traits", data.get("Traits") or []))
        parts.append(self._format_list("Factions", data.get("Factions") or []))
        parts.append(self._format_kv("Secrets", data.get("Secrets")))
        return "\n".join(p for p in parts if p).strip() + "\n"

    def _format_scenario_text(self, data: dict) -> str:
        parts = []
        parts.append(self._format_kv("Title", data.get("Title")))
        parts.append(self._format_kv("Summary", data.get("Summary")))
        parts.append(self._format_kv("Secrets", data.get("Secrets")))
        # Scenes may be list[str|dict]
        scenes = []
        for sc in data.get("Scenes") or []:
            if isinstance(sc, dict):
                scenes.append(self._as_text(sc.get("text") or sc))
            else:
                scenes.append(self._as_text(sc))
        parts.append(self._format_list("Scenes", scenes))
        parts.append(self._format_list("NPCs", data.get("NPCs") or []))
        parts.append(self._format_list("Places", data.get("Places") or []))
        parts.append(self._format_list("Factions", data.get("Factions") or []))
        return "\n".join(p for p in parts if p).strip() + "\n"

    # NPC generation -----------------------------------------------------
    @staticmethod
    def _as_text(val):
        """Coerce arbitrary value to displayable text."""
        if val is None:
            return ""
        if isinstance(val, list):
            # join lists as bullet-like lines
            return "\n".join(str(x) for x in val if x is not None)
        if isinstance(val, dict):
            # if dict has text, prefer it; else stringify
            return str(val.get("text", "")) if "text" in val else str(val)
        return str(val)

    def generate_npc(self):
        name = (self.npc_name.get() or "Unnamed").strip()
        role = self.npc_role.get().strip()
        faction = self.npc_faction.get().strip()
        location = self.npc_location.get().strip()
        genre = self.npc_genre.get().strip()

        schema = {
            "Name": name,
            "Role": role,
            "Description": "",
            "Background": "",
            "Personality": "",
            "Motivation": "",
            "Quote": "",
            "RoleplayingCues": "",
            "Traits": [],
            "Factions": [faction] if faction else [],
            "Secrets": "",
        }
        prompt = (
            f"Draft an NPC for a {genre} campaign. Name: {name}. Role: {role}. "
            f"Faction: {faction or 'None'}. Primary Location: {location or 'Unknown'}.\n"
            f"Return JSON with keys: {list(schema.keys())}. Keep fields under 150-250 words, traits as short strings."
        )
        data = self._chat_json(self._with_lore(prompt))
        if not data:
            return
        # Merge defaults
        for k in schema:
            data.setdefault(k, schema[k])
        # Keep structured result for saving/checking, but show human text
        self._last_npc_data = data
        self.npc_output.delete("1.0", "end")
        self.npc_output.insert("1.0", self._format_npc_text(data))

    def check_npc_consistency(self):
        # Prefer the last structured data; allow JSON pasted by power users as fallback
        data = self._last_npc_data
        if not isinstance(data, dict):
            try:
                data = _parse_json_relaxed(self.npc_output.get("1.0", "end").strip())
            except Exception:
                data = None
        if not isinstance(data, dict):
            messagebox.showerror("No Data", "Please generate an NPC first.")
            return
        issues = []
        # Factions exist?
        known_factions = {it.get("Name") for it in self.factions.load_items()}
        for f in data.get("Factions", []) or []:
            if f and f not in known_factions:
                issues.append(f"Unknown faction: {f}")
        # Basic duplication check
        existing = {it.get("Name") for it in self.npcs.load_items()}
        if data.get("Name") in existing:
            issues.append(f"NPC name already exists: {data.get('Name')}")
        if not issues:
            messagebox.showinfo("Consistency", "No immediate issues found.")
        else:
            messagebox.showwarning("Consistency Issues", "\n".join(issues))

    def save_npc(self):
        data = self._last_npc_data
        if not isinstance(data, dict):
            try:
                data = _parse_json_relaxed(self.npc_output.get("1.0", "end").strip())
            except Exception:
                data = None
        if not isinstance(data, dict):
            messagebox.showerror("No Data", "Please generate an NPC first.")
            return
        # Map to DB schema used by GenericListView templates
        item = {
            "Name": self._as_text(data.get("Name", "Unnamed")),
            "Role": self._as_text(data.get("Role", "")),
            "Description": {"text": self._as_text(data.get("Description", "")), "formatting": {"bold":[],"italic":[],"underline":[],"left":[],"center":[],"right":[]}},
            "Background": self._as_text(data.get("Background", "")),
            "Personality": self._as_text(data.get("Personality", "")),
            "Motivation": self._as_text(data.get("Motivation", "")),
            "Secret": {"text": self._as_text(data.get("Secrets", "")), "formatting": {"bold":[],"italic":[],"underline":[],"left":[],"center":[],"right":[]}},
            "Quote": self._as_text(data.get("Quote", "")),
            "RoleplayingCues": self._as_text(data.get("RoleplayingCues", "")),
            "Traits": data.get("Traits", []),
            "Factions": data.get("Factions", []),
            "Portrait": "",
        }
        items = self.npcs.load_items()
        # Replace if same name else append
        found = False
        for i, it in enumerate(items):
            if it.get("Name") == item["Name"]:
                items[i] = item
                found = True
                break
        if not found:
            items.append(item)
        self.npcs.save_items(items)
        messagebox.showinfo("Saved", f"NPC '{item['Name']}' saved to DB.")

    # Scenario generation -----------------------------------------------
    def generate_scenario(self):
        title = (self.sc_title.get() or "Untitled").strip()
        premise = self.sc_premise.get().strip()
        theme = self.sc_theme.get().strip()
        antagonist = self.sc_antagonist.get().strip()

        schema = {
            "Title": title,
            "Summary": "",
            "Secrets": "",
            "Scenes": [],
            "NPCs": [],
            "Places": [],
            "Factions": [],
        }
        prompt = (
            f"Draft a playable scenario outline. Title: {title}. Premise: {premise}. "
            f"Theme: {theme}. Antagonist: {antagonist or 'Unknown'}.\n"
            f"Return JSON with keys: {list(schema.keys())}.\n"
            f"- Summary: 2-4 paragraphs.\n- Secrets: GM-only twists.\n- Scenes: up to 5 short beats.\n"
            f"- NPCs: up to 4 names only.\n- Places: up to 4 names only.\n- Factions: names only."
        )
        data = self._chat_json(self._with_lore(prompt))
        if not data:
            return
        # Enforce caps on generated lists
        if isinstance(data.get("NPCs"), list):
            data["NPCs"] = data["NPCs"][:4]
        if isinstance(data.get("Places"), list):
            data["Places"] = data["Places"][:4]
        if isinstance(data.get("Scenes"), list):
            data["Scenes"] = data["Scenes"][:5]
        for k in schema:
            data.setdefault(k, schema[k])
        self._last_scenario_data = data
        self.sc_output.delete("1.0", "end")
        self.sc_output.insert("1.0", self._format_scenario_text(data))

    def check_scenario_consistency(self):
        data = self._last_scenario_data
        if not isinstance(data, dict):
            try:
                data = _parse_json_relaxed(self.sc_output.get("1.0", "end").strip())
            except Exception:
                data = None
        if not isinstance(data, dict):
            messagebox.showerror("No Data", "Please generate a scenario first.")
            return
        issues = []
        known_places = {it.get("Name") for it in self.places.load_items()}
        for p in data.get("Places", []) or []:
            if p and p not in known_places:
                issues.append(f"Unknown place: {p}")
        known_factions = {it.get("Name") for it in self.factions.load_items()}
        for f in data.get("Factions", []) or []:
            if f and f not in known_factions:
                issues.append(f"Unknown faction: {f}")
        if not issues:
            messagebox.showinfo("Consistency", "No immediate issues found.")
        else:
            messagebox.showwarning("Consistency Issues", "\n".join(issues))

    def save_scenario(self):
        data = self._last_scenario_data
        if not isinstance(data, dict):
            try:
                data = _parse_json_relaxed(self.sc_output.get("1.0", "end").strip())
            except Exception:
                data = None
        if not isinstance(data, dict):
            messagebox.showerror("No Data", "Please generate a scenario first.")
            return
        # Enforce caps again on save
        if isinstance(data.get("NPCs"), list):
            data["NPCs"] = data["NPCs"][:4]
        if isinstance(data.get("Places"), list):
            data["Places"] = data["Places"][:4]
        if isinstance(data.get("Scenes"), list):
            data["Scenes"] = data["Scenes"][:5]

        item = {
            "Title": self._as_text(data.get("Title", "Untitled")),
            "Summary": {"text": self._as_text(data.get("Summary", "")), "formatting": {"bold":[],"italic":[],"underline":[],"left":[],"center":[],"right":[]}},
            "Secrets": {"text": self._as_text(data.get("Secrets", "")), "formatting": {"bold":[],"italic":[],"underline":[],"left":[],"center":[],"right":[]}},
            "Places": data.get("Places", []),
            "NPCs": data.get("NPCs", []),
            "Factions": data.get("Factions", []),
            "Scenes": data.get("Scenes", []),
        }
        items = self.scenarios.load_items()
        # Replace if same Title else append
        found = False
        for i, it in enumerate(items):
            if it.get("Title") == item["Title"]:
                items[i] = item
                found = True
                break
        if not found:
            items.append(item)
        self.scenarios.save_items(items)
        messagebox.showinfo("Saved", f"Scenario '{item['Title']}' saved to DB.")

    # Beats --------------------------------------------------------------
    def expand_beat(self):
        beat = self.beat_input.get("1.0", "end").strip()
        if not beat:
            messagebox.showwarning("No Beat", "Enter a short beat to expand.")
            return
        prompt = (
            "Expand the following GM beat into a short playable scene (6-10 lines), "
            "including sensory details and possible player choices. Keep it system-agnostic.\n\nBeat:\n" + beat
        )
        text = self._chat_text(self._with_lore(prompt))
        self.beat_output.delete("1.0", "end")
        self.beat_output.insert("1.0", text.strip())
