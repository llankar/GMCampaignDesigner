import re
import os
import customtkinter as ctk
from tkinter import messagebox, filedialog
import threading
from modules.helpers.text_helpers import ai_text_to_rtf_json
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.ai.local_ai_client import LocalAIClient
from modules.helpers.importing.merge_helper import merge_with_confirmation
from modules.helpers.importing.pdf_hash_tracker import PDFHashTracker
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_methods,
    log_warning,
    log_module_import,
)
from modules.helpers.pdf_review_dialog import PDFReviewDialog
from modules.scenarios.processing.chunking import summarize_chunks
from modules.scenarios.processing.ai_scenario_importer import (
    extract_entities,
    expand_scenes,
    expand_summary,
    request_outline,
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
    
    combined_scenarios = merge_with_confirmation(
        existing_scenarios,
        [scenario_entity],
        key_field="Title",
        entity_label="scenarios",
    )
    combined_places = merge_with_confirmation(
        existing_places,
        locations,
        key_field="Name",
        entity_label="places",
    )
    combined_npcs = merge_with_confirmation(
        existing_npcs,
        npcs,
        key_field="Name",
        entity_label="NPCs",
    )

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
        self.multiple_scenarios_var = ctk.BooleanVar(value=False)
        self.chk_multiple_scenarios = ctk.CTkCheckBox(
            btn_row,
            text="Multiple scenarios",
            variable=self.multiple_scenarios_var,
        )
        self.chk_multiple_scenarios.pack(side="left", padx=5)
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

            pdf_hash = None
            previous_record = None
            try:
                pdf_hash = PDFHashTracker.compute_hash(pdf_path)
                previous_record = PDFHashTracker.get_record(pdf_hash)
                if previous_record:
                    imported_when = previous_record.get("timestamp", "an earlier session")
                    imported_from = previous_record.get("path", pdf_path)
                    should_continue = messagebox.askyesno(
                        "PDF Already Imported",
                        "This PDF appears to have been imported before.\n\n"
                        f"Source: {imported_from}\n"
                        f"When: {imported_when}\n\n"
                        "Import it again?",
                    )
                    if not should_continue:
                        self._set_status("Import cancelled (duplicate PDF).")
                        return
            except Exception as exc:
                log_warning(
                    f"Unable to check PDF hash: {exc}",
                    func_name="ScenarioImportWindow.import_pdf_via_ai",
                )

            self._set_status("Preparing import...")
            self._busy(True)

            def worker():
                try:
                    self._set_status("Extracting PDF text...")
                    pages = self._extract_pdf_text(pdf_path)
                    if not pages or not any(page.strip() for page in pages):
                        self._warn("Empty PDF", "Could not extract meaningful text from the PDF.")
                        return
                    selected_text = self._review_extracted_pages(pages, os.path.basename(pdf_path))
                    if not selected_text:
                        return
                    multiple_scenarios = bool(self.multiple_scenarios_var.get())
                    self._ai_extract_and_import(
                        selected_text,
                        source_label=os.path.basename(pdf_path),
                        multiple_scenarios=multiple_scenarios,
                    )
                    if pdf_hash:
                        PDFHashTracker.record_import(pdf_hash, pdf_path)
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
                    multiple_scenarios = bool(self.multiple_scenarios_var.get())
                    self._ai_extract_and_import(
                        text,
                        source_label="Pasted Text",
                        multiple_scenarios=multiple_scenarios,
                    )
                except Exception as e:
                    self._error("AI Parse Error", str(e))
                finally:
                    self._busy(False)
                    self._set_status("Idle")
            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            messagebox.showerror("AI Parse Error", str(e))

    # --- Helpers ---
    def _extract_pdf_text(self, path: str) -> list[str]:
        """Attempt to extract text from PDF using available backends."""
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
            return text
        except Exception:
            pass

    def _review_extracted_pages(self, pages: list[str], source_name: str) -> str | None:
        selection: dict[str, str | None] = {"text": None}
        event = threading.Event()

        def _open_dialog():
            dialog = PDFReviewDialog(self, pages, title=f"Review {source_name}")
            self.wait_window(dialog)
            chosen = dialog.selected_pages
            selection["text"] = "\n".join(chosen) if chosen else None
            event.set()

        self.after(0, _open_dialog)
        event.wait()
        return selection["text"]
        
    def _ai_extract_and_import(self, raw_text: str, source_label: str = "", multiple_scenarios: bool = False):
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

        # -------- Pre-processing: chunking & summarization --------
        self._set_status("Summarizing source text chunks...")
        stitched_summary, chunk_metadata = summarize_chunks(
            raw_text,
            client,
            source_label or "Unknown",
            max_tokens=900,
        )
        if stitched_summary:
            compressed_context = (
                "Chunked summaries with token ranges (for traceability):\n" + stitched_summary
            )
        else:
            compressed_context = raw_text[:50000]
        chunk_range_hint = "\n".join(
            [
                f"- {entry['label']} tokens {entry['start_token']}-{entry['end_token']}"
                for entry in chunk_metadata
            ]
        )

        self._set_status("Analyzing text with AI (phase 1/4)...")
        outlines = request_outline(
            client,
            compressed_context,
            chunk_range_hint,
            source_label or "Unknown",
            multiple_scenarios,
        )
        if not outlines:
            raise RuntimeError("AI did not return any scenarios to import")

        total_scenarios = len(outlines)
        for idx, outline in enumerate(outlines, start=1):
            title = outline.get("Title") or f"Unnamed Scenario {idx}"
            summary_draft = outline.get("Summary") or ""
            outline_scenes = outline.get("Scenes") or []

            self._set_status(f"Analyzing text with AI (phase 2/4, scenario {idx}/{total_scenarios})...")
            summary_expanded = expand_summary(
                client,
                title,
                summary_draft,
                compressed_context,
                chunk_range_hint,
            )

            self._set_status(f"Analyzing text with AI (phase 3/4, scenario {idx}/{total_scenarios})...")
            scenes_expanded_text = expand_scenes(
                client,
                title,
                outline_scenes,
                compressed_context,
                chunk_range_hint,
            )
            scenes_expanded_list = [ai_text_to_rtf_json(text) for text in scenes_expanded_text]

            self._set_status(f"Analyzing text with AI (phase 4/4, scenario {idx}/{total_scenarios})...")
            entities = extract_entities(
                client,
                compressed_context,
                chunk_range_hint,
                stats_examples,
            )

            def to_longtext(val):
                if isinstance(val, dict) and "text" in val:
                    return val
                return ai_text_to_rtf_json(str(val) if val is not None else "")

            # Scenario
            self._set_status(f"Merging scenarios into database ({idx}/{total_scenarios})...")
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
            merged_scenarios = merge_with_confirmation(
                current_scenarios,
                [scenario_item],
                key_field="Title",
                entity_label="scenarios",
            )
            scenarios_wrapper.save_items(merged_scenarios)

            # NPCs
            self._set_status(f"Merging NPCs into database ({idx}/{total_scenarios})...")
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
                merged_npcs = merge_with_confirmation(
                    current_items,
                    new_items,
                    key_field="Name",
                    entity_label="NPCs",
                )
                npcs_wrapper.save_items(merged_npcs)

            # Creatures
            self._set_status(f"Merging creatures into database ({idx}/{total_scenarios})...")
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
            self._set_status(f"Merging places into database ({idx}/{total_scenarios})...")
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
                merged_places = merge_with_confirmation(
                    current_items,
                    new_items,
                    key_field="Name",
                    entity_label="places",
                )
                places_wrapper.save_items(merged_places)

        messagebox.showinfo("Imported", "AI multi-phase import completed and merged into the database.")
        self._set_status("Import complete.")
        self.after(2000, lambda: self._set_status("Idle"))
        self._busy(False)
    # --- UI helpers ---
    def _set_status(self, text: str):
        # Log the provided status text (fix NameError from 'message')
        log_info(f"Import status: {text}", func_name="ScenarioImportWindow._set_status")
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
                for b in (
                    self.btn_import_pdf,
                    self.btn_ai_parse_text,
                    self.btn_save_pasted,
                    self.chk_multiple_scenarios,
                ):
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
