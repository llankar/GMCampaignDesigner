import re
import os
import json
import customtkinter as ctk
from tkinter import messagebox, filedialog
import threading
from modules.helpers.text_helpers import format_longtext, ai_text_to_rtf_json
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.ai.local_ai_client import LocalAIClient
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_methods,
    log_warning,
    log_module_import,
)

log_module_import(__name__)

# Default formatting object.
default_formatting = {
    "bold": [],
    "italic": [],
    "underline": [],
    "left": [],
    "center": [],
    "right": []
}

@log_function
def remove_emojis(text):
    emoji_pattern = re.compile("[" 
                               u"\U0001F600-\U0001F64F"  
                               u"\U0001F300-\U0001F5FF"  
                               u"\U0001F680-\U0001F6FF"  
                               u"\U0001F1E0-\U0001F1FF"  
                               u"\U00002702-\U000027B0"  
                               u"\U000024C2-\U0001F251"
                               "]+", flags=re.UNICODE)
    cleaned = emoji_pattern.sub(r'', text)
   #logging.debug("Emojis removed.")
    return cleaned

@log_function
def parse_json_relaxed(s: str):
    """Try to parse JSON from a possibly noisy AI response (module-level helper)."""
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
        # Try progressively trimming
        for j in range(len(tail), max(len(tail)-2000, 0), -1):
            chunk = tail[:j]
            try:
                return json.loads(chunk)
            except Exception:
                continue
    raise RuntimeError("Failed to parse JSON from AI response")

@log_function
def import_formatted_scenario(text):
    # Remove emojis.
    cleaned_text = remove_emojis(text)
   #logging.info("Cleaned text (first 200 chars): %s", cleaned_text[:200])
    
    # --- Extract Basic Scenario Info ---
    title_match = re.search(r'^Scenario Title:\s*(.+)$', cleaned_text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Unnamed Scenario"
   #logging.info("Parsed Title: %s", title)
    
    # Extract Introduction.
    intro_match = re.search(
        r'(?i)(?:^|\n)\s*Introduction\s*:?\s*(.*?)(?=\n\s*(?:Tied Player Characters:|Main Locations|ðŸ“ Main Locations|Key NPCs|NPCs))',
        cleaned_text,
        re.DOTALL
    )
    introduction = intro_match.group(1).strip() if intro_match else ""
   #logging.info("Parsed Introduction (first 100 chars): %s", introduction[:100])
    
    # --- Extract Places ---
    locations = []
    loc_split = re.split(r'(?mi)^\s*(?:Main Locations|ðŸ“ Main Locations).*$', cleaned_text, maxsplit=1)
    if len(loc_split) > 1:
        remainder = loc_split[1]
        npc_index = remainder.find("Key NPCs")
        if npc_index == -1:
            npc_index = remainder.find("NPCs")
        if npc_index >= 0:
            locs_text = remainder[:npc_index].strip()
        else:
            locs_text = remainder.strip()
       #logging.info("Extracted Places section (first 200 chars): %s", locs_text[:200])
        loc_entries = re.split(r'(?m)^\d+\.\s+', locs_text)
        for entry in loc_entries:
            entry = entry.strip()
            if not entry:
                continue
            lines = entry.splitlines()
            name_line = lines[0].strip()
            parts = re.split(r'\s*[-â€“]\s*', name_line)
            loc_name = parts[0].strip()
            description = ""
            current_section = None
            for line in lines[1:]:
                line = line.strip()
                if line.startswith("Description:"):
                    current_section = "description"
                    description = line[len("Description:"):].strip()
                else:
                    if current_section == "description":
                        description += " " + line
            locations.append({
                "Name": loc_name,
                "Description": description.strip()
            })
    
    # --- Extract NPCs ---
    npcs = []
    npc_split = re.split(r'(?mi)^\s*(?:[^\w\s]*\s*)?(?:Key NPCs|NPCs)\s*:?.*$', cleaned_text, maxsplit=1)
    if len(npc_split) > 1:
        npc_text = npc_split[1].strip()
        #logging.info("Extracted NPCs section (first 200 chars): %s", npc_text[:200])
        npc_entries = re.split(r'(?m)^\d+\.\s+', npc_text)
        if npc_entries and not npc_entries[0].strip():
            npc_entries = npc_entries[1:]
        for entry in npc_entries:
            entry = entry.strip()
            if not entry:
                continue
            lines = entry.splitlines()
            header = lines[0].strip()
            if "â€“" in header:
                parts = re.split(r'\s*[-â€“]\s*', header)
                npc_name = parts[0].strip()
                npc_role = parts[1].strip() if len(parts) > 1 else ""
            else:
                npc_name = header
                npc_role = ""
            appearance = ""
            background = ""
            secret = ""
            current_section = None
            for line in lines[1:]:
                line = line.strip()
                if line.startswith("Appearance:"):
                    current_section = "appearance"
                    appearance = line[len("Appearance:"):].strip()
                elif line.startswith("Background:"):
                    current_section = "background"
                    background = line[len("Background:"):].strip()
                elif line.startswith("Savage Fate Stats:"):
                    current_section = "stats"
                    secret = line[len("Savage Fate Stats:"):].strip()
                elif line.startswith("Stunt:"):
                    current_section = "stunt"
                    secret += " " + line[len("Stunt:"):].strip()
                else:
                    if current_section == "appearance":
                        appearance += " " + line
                    elif current_section == "background":
                        background += " " + line
                    elif current_section in ["stats", "stunt"]:
                        secret += " " + line
            combined_desc = (appearance + " " + background).strip()
            npc_obj = {
                "Name": npc_name,
                "Role": npc_role,
                "Description": {
                    "text": combined_desc,
                    "formatting": default_formatting
                },
                "Secret": {
                    "text": secret.strip(),
                    "formatting": default_formatting
                },
                "Factions": [],
                "Portrait": ""
            }
            npcs.append(npc_obj)
           #logging.info("Parsed NPC: %s; Role: %s; Desc snippet: %s; Secret snippet: %s", 
           #               npc_name, npc_role, combined_desc[:60], secret.strip()[:60])
    
    # --- Build Scenario Entity ---
    scenario_entity = {
        "Title": title,
        "Summary": {
            "text": introduction,
            "formatting": default_formatting
        },
        "Secrets": {
            "text": "",
            "formatting": default_formatting
        },
        "Places": [loc["Name"] for loc in locations],
        "NPCs": [npc["Name"] for npc in npcs]
    }
   #logging.info("Built scenario entity: %s", scenario_entity)
    
    # --- Save to the Database using Wrappers (append new records) ---
    scenario_wrapper = GenericModelWrapper("scenarios")
    places_wrapper = GenericModelWrapper("places")
    npcs_wrapper = GenericModelWrapper("npcs")
    
    existing_scenarios = scenario_wrapper.load_items()
    existing_places = places_wrapper.load_items()
    existing_npcs = npcs_wrapper.load_items()
    
    combined_scenarios = existing_scenarios + [scenario_entity]
    combined_places = existing_places + locations
    combined_npcs = existing_npcs + npcs
    
    scenario_wrapper.save_items(combined_scenarios)
    places_wrapper.save_items(combined_places)
    npcs_wrapper.save_items(combined_npcs)
    
   #logging.info("Scenario imported successfully using the database (appended to existing data)!")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CLASS: ScenarioImportWindow
# A window that allows users to paste scenario text for import.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@log_methods
class ScenarioImportWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Import Formatted Scenario")
        self.geometry("600x600")
        self.transient(master)  # Stay on top of the master window
        self.grab_set()         # Block background clicks
        self.focus_force()      # Focus on the dialog
        
        instruction_label = ctk.CTkLabel(self, text="Paste scenario text or import a PDF:")
        instruction_label.pack(pady=(10, 0), padx=10)
        
        # Create a CTkTextbox with a dark background and white text.
        self.scenario_textbox = ctk.CTkTextbox(self, wrap="word", height=400, fg_color="#2B2B2B", text_color="white")
        self.scenario_textbox.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Buttons row
        btn_row = ctk.CTkFrame(self)
        btn_row.pack(fill="x", padx=10, pady=(0,10))
        self.btn_import_pdf = ctk.CTkButton(btn_row, text="Import PDF via AI", command=self.import_pdf_via_ai)
        self.btn_import_pdf.pack(side="left", padx=5)
        self.btn_ai_parse_text = ctk.CTkButton(btn_row, text="AI Parse Text", command=self.ai_parse_textarea)
        self.btn_ai_parse_text.pack(side="left", padx=5)
        self.btn_save_pasted = ctk.CTkButton(btn_row, text="Save Pasted Scenario", command=self.import_scenario)
        self.btn_save_pasted.pack(side="right", padx=5)

        # Status / progress row
        status_row = ctk.CTkFrame(self)
        status_row.pack(fill="x", padx=10, pady=(0,10))
        self.progress = ctk.CTkProgressBar(status_row, mode="indeterminate")
        self.progress.pack(fill="x", side="left", expand=True)
        self.status_label = ctk.CTkLabel(status_row, text="Idle")
        self.status_label.pack(side="right", padx=(8,0))
        
    def import_scenario(self):
        log_info("Importing scenario from JSON", func_name="ScenarioImportWindow.import_scenario")
        scenario_text = self.scenario_textbox.get("1.0", "end-1c")
        try:
            self._set_status("Importing pasted scenario...")
            self._busy(True)
            import_formatted_scenario(scenario_text)
            messagebox.showinfo("Success", "Scenario imported successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Error importing scenario:\n{str(e)}")
        finally:
            self._busy(False)
            self._set_status("Idle")

    # -------------------------
    # AI-powered PDF import
    # -------------------------
    def import_pdf_via_ai(self):
        log_info("Importing scenario PDF via AI", func_name="ScenarioImportWindow.import_pdf_via_ai")
        try:
            pdf_path = filedialog.askopenfilename(
                title="Select Scenario PDF",
                filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
            )
            if not pdf_path:
                return
            self._set_status("Preparing import...")
            self._busy(True)
            def worker():
                try:
                    self._set_status("Extracting PDF text...")
                    text = self._extract_pdf_text(pdf_path)
                    if not text or len(text.strip()) < 50:
                        self._warn("Empty PDF", "Could not extract meaningful text from the PDF.")
                        return
                    self._ai_extract_and_import(text, source_label=os.path.basename(pdf_path))
                except Exception as e:
                    self._error("AI PDF Import Error", str(e))
                finally:
                    self._busy(False)
                    self._set_status("Idle")
            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            messagebox.showerror("AI PDF Import Error", str(e))

    def ai_parse_textarea(self):
        log_info("Parsing scenario text via AI", func_name="ScenarioImportWindow.ai_parse_textarea")
        text = self.scenario_textbox.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("No Text", "Please paste scenario text first.")
            return
        try:
            self._set_status("Preparing AI parse...")
            self._busy(True)
            def worker():
                try:
                    self._ai_extract_and_import(text, source_label="Pasted Text")
                except Exception as e:
                    self._error("AI Parse Error", str(e))
                finally:
                    self._busy(False)
                    self._set_status("Idle")
            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            messagebox.showerror("AI Parse Error", str(e))

    # --- Helpers ---
    def _extract_pdf_text(self, path: str) -> str:
        """Attempt to extract text from PDF using available backends."""
        # Try PyPDF2 / pypdf
        try:
            try:
                import PyPDF2 as pypdf
            except Exception:
                import pypdf as pypdf  # type: ignore
            text = []
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    try:
                        text.append(page.extract_text() or "")
                    except Exception:
                        continue
            return "\n".join(text)
        except Exception:
            pass
        
    def _ai_extract_and_import(self, raw_text: str, source_label: str = ""):
        log_info(f"Running AI extraction for {source_label or 'input'}", func_name="ScenarioImportWindow._ai_extract_and_import")
        """
        Multi-phase AI extraction to improve depth, especially Scenario Summary and Scenes.

        Phases:
          1) Outline: Title, concise Summary draft, scene stubs (title + gist), referenced names.
          2) Expand Summary: richer GM-facing summary (2–4 paragraphs).
          3) Expand Scenes: detailed scene texts per stub.
          4) Entities: structured NPCs/Creatures/Places/Factions.
        Then merge into the database.
        """
        self._set_status("Analyzing text with AI (phase 1/4)...")
        self._busy(True)

        # DB wrappers
        creatures_wrapper = GenericModelWrapper("creatures")
        npcs_wrapper = GenericModelWrapper("npcs")
        places_wrapper = GenericModelWrapper("places")
        scenarios_wrapper = GenericModelWrapper("scenarios")

        # Pull a few existing creature stats as examples
        existing_creatures = creatures_wrapper.load_items()
        stats_examples = []
        for row in existing_creatures:
            st = row.get("Stats")
            if isinstance(st, dict):
                st = st.get("text", "")
            if isinstance(st, str) and st.strip():
                stats_examples.append({
                    "Name": row.get("Name", ""),
                    "Type": row.get("Type", ""),
                    "Stats": st.strip()
                })
            if len(stats_examples) >= 3:
                break

        client = LocalAIClient()

        # -------- Phase 1: Outline --------
        outline_schema = {
            "Title": "text",
            "Summary": "short text (3-5 sentences)",
            "Scenes": [{"Title": "text", "Gist": "1-3 sentences"}],
            "NPCs": ["Name"],
            "Places": ["Name"]
        }
        prompt_outline = (
            "You are an assistant that extracts a high-level scenario outline from RPG source text.\n"
            "Return STRICT JSON only, no prose.\n\n"
            f"Source: {source_label}\n"
            "JSON schema:\n" + json.dumps(outline_schema, ensure_ascii=False, indent=2) + "\n\n"
            "Notes: Use only info from the text. If uncertain, omit.\n"
            "Now outline this text:\n" + raw_text[:50000]
        )
        outline_raw = client.chat([
            {"role": "system", "content": "Extract concise scenario outlines as strict JSON."},
            {"role": "user", "content": prompt_outline}
        ])
        outline = parse_json_relaxed(outline_raw)
        if not isinstance(outline, dict):
            raise RuntimeError("AI did not return a JSON object for outline")

        title = outline.get("Title") or "Unnamed Scenario"
        summary_draft = outline.get("Summary") or ""
        outline_scenes = outline.get("Scenes") or []

        # -------- Phase 2: Expand Summary --------
        self._set_status("Analyzing text with AI (phase 2/4)...")
        prompt_summary = (
            "Rewrite the following scenario summary into a richer, evocative, GM-friendly 2–4 paragraph summary.\n"
            "- Keep it consistent with the source text.\n"
            "- Avoid rules jargon.\n"
            "Return PLAIN TEXT only.\n\n"
            f"Title: {title}\n"
            "Current summary:\n" + (summary_draft or "")
        )
        summary_expanded = client.chat([
            {"role": "system", "content": "You write compelling GM-facing RPG summaries. Return plain text."},
            {"role": "user", "content": prompt_summary}
        ])
        # Clean potential code fences/backticks
        if summary_expanded and summary_expanded.strip().startswith("```"):
            summary_expanded = re.sub(r"^```(?:[a-zA-Z]+)?", "", summary_expanded, flags=re.IGNORECASE).strip().rstrip("`").strip()
        summary_expanded = summary_expanded.strip()

        # -------- Phase 3: Expand Scenes --------
        self._set_status("Analyzing text with AI (phase 3/4)...")
        scenes_schema = {"Scenes": [{"Title": "text", "Text": "multi-paragraph detailed scene"}]}
        prompt_scenes = (
            "Using the outline below and the source text, produce detailed scene writeups.\n"
            "For each scene, include a 1–2 paragraph overview plus bullet points for: key beats, conflicts/obstacles, clues/hooks, transitions, important locations, and involved NPCs.\n"
            "Return STRICT JSON only with this schema:\n" + json.dumps(scenes_schema, ensure_ascii=False, indent=2) + "\n\n"
            f"Title: {title}\n"
            "Outline scenes:\n" + json.dumps(outline_scenes, ensure_ascii=False, indent=2) + "\n\n"
            "Source excerpt (may be truncated):\n" + raw_text[:50000]
        )
        scenes_raw = client.chat([
            {"role": "system", "content": "Expand scene stubs into detailed, game-usable scenes as strict JSON."},
            {"role": "user", "content": prompt_scenes}
        ])
        scenes_obj = parse_json_relaxed(scenes_raw)
        if not isinstance(scenes_obj, dict) or not isinstance(scenes_obj.get("Scenes"), list):
            raise RuntimeError("AI did not return a JSON object with Scenes")
        scenes_expanded_list = []
        for sc in scenes_obj.get("Scenes", []) or []:
            if isinstance(sc, dict):
                txt = sc.get("Text") or ""
                if isinstance(txt, dict) and "text" in txt:
                    txt = txt.get("text", "")
                scenes_expanded_list.append(ai_text_to_rtf_json(str(txt).strip()))

        # -------- Phase 4: Entities (NPCs/Creatures/Places/Factions) --------
        self._set_status("Analyzing text with AI (phase 4/4)...")
        entities_schema = {
            "npcs": [
                {"Name": "text", "Role": "text", "Description": "longtext", "Secret": "longtext", "Factions": ["Name"], "Portrait": "text(optional)"}
            ],
            "creatures": [
                {"Name": "text", "Type": "text", "Description": "longtext", "Weakness": "longtext", "Powers": "longtext", "Stats": "longtext", "Background": "longtext"}
            ],
            "places": [
                {"Name": "text", "Description": "longtext", "Secrets": "longtext(optional)"}
            ],
            "factions": [
                {"Name": "text", "Description": "longtext(optional)"}
            ]
        }
        prompt_entities = (
            "Extract RPG entities from the text. Output STRICT JSON only, matching the schema below.\n"
            "If stats are present (even from other systems), convert into concise creature 'Stats' similar to examples. Do not invent facts.\n\n"
            "Schema:\n" + json.dumps(entities_schema, ensure_ascii=False, indent=2) + "\n\n"
            "Examples of desired 'Stats' formatting from the active DB:\n" + json.dumps(stats_examples, ensure_ascii=False, indent=2) + "\n\n"
            "Text to analyze (may be truncated):\n" + raw_text[:50000]
        )
        entities_raw = client.chat([
            {"role": "system", "content": "Extract structured entities (NPCs, creatures, places, factions) as strict JSON."},
            {"role": "user", "content": prompt_entities}
        ])
        entities = parse_json_relaxed(entities_raw)
        if not isinstance(entities, dict):
            raise RuntimeError("AI did not return a JSON object for entities")

        # ---------- Merge into DB ----------
        def to_longtext(val):
            if isinstance(val, dict) and "text" in val:
                return val
            return ai_text_to_rtf_json(str(val) if val is not None else "")

        # Scenario
        self._set_status("Merging scenarios into database...")
        current_scenarios = scenarios_wrapper.load_items()
        scenario_item = {
            "Title": title,
            "Summary": to_longtext(summary_expanded or summary_draft or ""),
            "Secrets": to_longtext(""),
            "Scenes": scenes_expanded_list,
            "Places": entities.get("places", []) and [p.get("Name", "") for p in entities.get("places", []) if isinstance(p, dict)] or (outline.get("Places") or []),
            "NPCs": entities.get("npcs", []) and [n.get("Name", "") for n in entities.get("npcs", []) if isinstance(n, dict)] or (outline.get("NPCs") or []),
            "Creatures": [c.get("Name", "") for c in entities.get("creatures", []) if isinstance(c, dict)],
            "Factions": [f.get("Name", "") for f in entities.get("factions", []) if isinstance(f, dict)],
            "Objects": []
        }
        scenarios_wrapper.save_items(current_scenarios + [scenario_item])

        # NPCs
        self._set_status("Merging NPCs into database...")
        if isinstance(entities.get("npcs"), list):
            current_items = npcs_wrapper.load_items()
            new_items = []
            for n in entities.get("npcs"):
                if not isinstance(n, dict):
                    continue
                item = {
                    "Name": n.get("Name", "Unnamed"),
                    "Role": n.get("Role", ""),
                    "Description": to_longtext(n.get("Description", "")),
                    "Secret": to_longtext(n.get("Secret", "")),
                    "Quote": n.get("Quote"),
                    "RoleplayingCues": to_longtext(n.get("RoleplayingCues", "None")),
                    "Personality": to_longtext(n.get("Personality", "None")),
                    "Motivation": to_longtext(n.get("Motivation", "None")),
                    "Background": to_longtext(n.get("Background", "None")),
                    "Traits": to_longtext(n.get("Traits", "None")),
                    "Genre": n.get("Genre", ""),
                    "Factions": n.get("Factions", []),
                    "Objects": n.get("Objects", []),
                    "Portrait": n.get("Portrait", "")
                }
                new_items.append(item)
            npcs_wrapper.save_items(current_items + new_items)

        # Creatures
        self._set_status("Merging creatures into database...")
        if isinstance(entities.get("creatures"), list):
            current_items = creatures_wrapper.load_items()
            new_items = []
            for c in entities.get("creatures"):
                if not isinstance(c, dict):
                    continue
                stats_val = c.get("Stats", "")
                stats_norm = stats_val if (isinstance(stats_val, dict) and "text" in stats_val) else to_longtext(stats_val)
                item = {
                    "Name": c.get("Name", "Unnamed"),
                    "Type": c.get("Type", ""),
                    "Description": to_longtext(c.get("Description", "")),
                    "Weakness": to_longtext(c.get("Weakness", "")),
                    "Powers": to_longtext(c.get("Powers", "")),
                    "Stats": stats_norm,
                    "Background": to_longtext(c.get("Background", "")),
                    "Genre": c.get("Genre", "Modern Fantasy"),
                    "Portrait": c.get("Portrait", "")
                }
                new_items.append(item)
            creatures_wrapper.save_items(current_items + new_items)

        # Places
        self._set_status("Merging places into database...")
        if isinstance(entities.get("places"), list):
            current_items = places_wrapper.load_items()
            new_items = []
            for p in entities.get("places"):
                if not isinstance(p, dict):
                    continue
                item = {
                    "Name": p.get("Name", "Unnamed"),
                    "Description": to_longtext(p.get("Description", "")),
                    "NPCs": p.get("NPCs", []),
                    "PlayerDisplay": p.get("PlayerDisplay", False),
                    "Secrets": to_longtext(p.get("Secrets", "")),
                    "Portrait": p.get("Portrait", "")
                }
                new_items.append(item)
            places_wrapper.save_items(current_items + new_items)

        messagebox.showinfo("Imported", "AI multi-phase import completed and merged into the database.")
        self._set_status("Import complete.")
        self.after(2000, lambda: self._set_status("Idle"))
        self._busy(False)
    # --- UI helpers ---
    def _set_status(self, text: str):
        log_info(f"Import status: {message}", func_name="ScenarioImportWindow._set_status")
        def _do():
            try:
                self.status_label.configure(text=text)
            except Exception:
                pass
        self.after(0, _do)

    def _busy(self, on: bool):
        def _do():
            try:
                if on:
                    self.progress.start()
                else:
                    self.progress.stop()
                # Toggle buttons
                state = "disabled" if on else "normal"
                for b in (self.btn_import_pdf, self.btn_ai_parse_text, self.btn_save_pasted):
                    try:
                        b.configure(state=state)
                    except Exception:
                        pass
            except Exception:
                pass
        self.after(0, _do)

    def _info(self, title: str, msg: str):
        self.after(0, lambda: messagebox.showinfo(title, msg))

    def _warn(self, title: str, msg: str):
        self.after(0, lambda: messagebox.showwarning(title, msg))

    def _error(self, title: str, msg: str):
        self.after(0, lambda: messagebox.showerror(title, msg))

