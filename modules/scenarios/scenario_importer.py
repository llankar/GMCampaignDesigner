import re
import os
import json
import customtkinter as ctk
from tkinter import messagebox, filedialog
import threading
from modules.helpers.text_helpers import format_longtext
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.ai.local_ai_client import LocalAIClient


# Default formatting object.
default_formatting = {
    "bold": [],
    "italic": [],
    "underline": [],
    "left": [],
    "center": [],
    "right": []
}

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
        r'(?i)(?:^|\n)\s*Introduction\s*:?\s*(.*?)(?=\n\s*(?:Tied Player Characters:|Main Locations|📍 Main Locations|Key NPCs|NPCs))',
        cleaned_text,
        re.DOTALL
    )
    introduction = intro_match.group(1).strip() if intro_match else ""
   #logging.info("Parsed Introduction (first 100 chars): %s", introduction[:100])
    
    # --- Extract Places ---
    locations = []
    loc_split = re.split(r'(?mi)^\s*(?:Main Locations|📍 Main Locations).*$', cleaned_text, maxsplit=1)
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
            parts = re.split(r'\s*[-–]\s*', name_line)
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
            if "–" in header:
                parts = re.split(r'\s*[-–]\s*', header)
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

# ─────────────────────────────────────────────────────────────────────────
# CLASS: ScenarioImportWindow
# A window that allows users to paste scenario text for import.
# ─────────────────────────────────────────────────────────────────────────
class ScenarioImportWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Import Formatted Scenario")
        self.geometry("600x600")
        
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
        # Try pdfminer.six
        try:
            from pdfminer.high_level import extract_text as pdfminer_extract
            return pdfminer_extract(path) or ""
        except Exception:
            pass
        # Try PyMuPDF
        try:
            import fitz  # PyMuPDF
            text = []
            with fitz.open(path) as doc:
                for page in doc:
                    text.append(page.get_text("text"))
            return "\n".join(text)
        except Exception:
            pass
        raise RuntimeError("No PDF text extractor available. Install 'pypdf' or 'pdfminer.six' or 'pymupdf'.")

    def _ai_extract_and_import(self, raw_text: str, source_label: str = ""):
        """
        Use LocalAI to extract scenarios/NPCs/creatures/places from text and merge into DB.
        """
        self._set_status("Analyzing text with AI...")
        self._busy(True)
        # Load examples from current DB to guide formatting (esp. creature Stats)
        creatures_wrapper = GenericModelWrapper("creatures")
        npcs_wrapper = GenericModelWrapper("npcs")
        places_wrapper = GenericModelWrapper("places")
        scenarios_wrapper = GenericModelWrapper("scenarios")

        existing_creatures = creatures_wrapper.load_items()
        stats_examples = []
        for row in existing_creatures:
            st = row.get("Stats")
            # Normalize longtext object or raw string
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

        # Build instruction and schema
        schema_hint = {
            "scenarios": [
                {
                    "Title": "text",
                    "Summary": "longtext",
                    "Secrets": "longtext",
                    "Scenes": ["longtext"],
                    "Places": ["Name"],
                    "NPCs": ["Name"],
                    "Creatures": ["Name"],
                    "Factions": ["Name"]
                }
            ],
            "npcs": [
                {
                    "Name": "text",
                    "Role": "text",
                    "Description": "longtext",
                    "Secret": "longtext",
                    "Factions": ["Name"],
                    "Portrait": "text(optional)"
                }
            ],
            "creatures": [
                {
                    "Name": "text",
                    "Type": "text",
                    "Description": "longtext",
                    "Weakness": "longtext",
                    "Powers": "longtext",
                    "Stats": "longtext",
                    "Background": "longtext"
                }
            ],
            "places": [
                {
                    "Name": "text",
                    "Description": "longtext",
                    "Secrets": "longtext(optional)"
                }
            ],
            "factions": [
                {"Name": "text", "Description": "longtext(optional)"}
            ]
        }

        prompt = (
            "You extract structured scenario data from RPG source text. "
            "Output STRICT JSON only, no prose, matching the provided schema.\n\n"
            f"Source: {source_label}\n"
            "Schema (field types):\n" + json.dumps(schema_hint, ensure_ascii=False, indent=2) + "\n\n"
            "Guidance: If stats are present in the text (even from other systems), convert them into concise Dresden-style creature 'Stats' similar to examples.\n"
            "Examples of desired 'Stats' formatting from the active DB (do not invent values not in text, interpolate reasonably):\n" + json.dumps(stats_examples, ensure_ascii=False, indent=2) + "\n\n"
            "Now extract from this text:\n" + raw_text[:12000]  # cap to keep prompt reasonable
        )

        client = LocalAIClient()
        ai_response = client.chat([
            {"role": "system", "content": "You convert RPG book text into JSON game data."},
            {"role": "user", "content": prompt}
        ])

        data = self._parse_json_relaxed(ai_response)
        if not isinstance(data, dict):
            self._busy(False)
            self._set_status("Idle")
            raise RuntimeError("AI did not return a JSON object")

        # Normalize and merge into DB
        def to_longtext(val):
            if isinstance(val, dict) and "text" in val:
                return val  # already longtext object
            return {"text": str(val) if val is not None else "", "formatting": default_formatting}

        # Scenarios
        self._set_status("Merging scenarios into database...")
        if "scenarios" in data and isinstance(data["scenarios"], list):
            current_items = scenarios_wrapper.load_items()
            new_items = []
            for s in data["scenarios"]:
                if not isinstance(s, dict):
                    continue
                item = {
                    "Title": s.get("Title", "Unnamed Scenario"),
                    "Summary": to_longtext(s.get("Summary", "")),
                    "Secrets": to_longtext(s.get("Secrets", "")),
                    "Scenes": s.get("Scenes", []),
                    "Places": s.get("Places", []),
                    "NPCs": s.get("NPCs", []),
                    "Creatures": s.get("Creatures", []),
                    "Factions": s.get("Factions", []),
                    "Objects": s.get("Objects", []),
                }
                new_items.append(item)
            scenarios_wrapper.save_items(current_items + new_items)

        # NPCs
        self._set_status("Merging NPCs into database...")
        if "npcs" in data and isinstance(data["npcs"], list):
            current_items = npcs_wrapper.load_items()
            new_items = []
            for n in data["npcs"]:
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
        if "creatures" in data and isinstance(data["creatures"], list):
            current_items = creatures_wrapper.load_items()
            new_items = []
            for c in data["creatures"]:
                if not isinstance(c, dict):
                    continue
                stats_val = c.get("Stats", "")
                if isinstance(stats_val, dict) and "text" in stats_val:
                    stats_norm = stats_val
                else:
                    stats_norm = to_longtext(stats_val)
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
        if "places" in data and isinstance(data["places"], list):
            current_items = places_wrapper.load_items()
            new_items = []
            for p in data["places"]:
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

        messagebox.showinfo("Imported", "AI import completed and merged into the database.")
        self._set_status("Import complete.")
        self.after(2000, lambda: self._set_status("Idle"))
        self._busy(False)

    def _parse_json_relaxed(self, s: str):
        """Try to parse JSON from a possibly noisy AI response."""
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

    # --- UI helpers ---
    def _set_status(self, text: str):
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
