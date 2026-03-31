"""Utilities for window components random content generation."""

from modules.generic.editor.window_context import *


class GenericEditorWindowRandomContentGeneration:
    def generate_secret_text(self):
        """
        Reads three text files from the assets folder:
        - Secret truths.txt
        - Secret origins.txt
        - Secret consequences.txt
        Each file is expected to contain approximately 100 elements (one per line).
        The function randomly selects one line from each file in the order:
        Secret truths, then Secret origins, then Secret consequences.
        The final string is then inserted into the 'Secrets' text widget.
        """
        try:
            # Determine the absolute path to your assets folder (assumed to be in the same directory as this module).
            current_dir = os.path.dirname(os.path.abspath(__file__))
            assets_folder = os.path.join(current_dir, "assets")

            # Define the full paths of the required files.
            files = {
                "truths" : "assets/Secret truths.txt",
                "origins" : "assets/Secret origins.txt",
                "consequences" : "assets/Secret consequences.txt"
            }

            selected_lines = {}
            # Process each file.
            for key, filepath in files.items():
                # Process each (key, filepath) from files.items().
                if not os.path.exists(filepath):
                    raise FileNotFoundError(f"File not found: {filepath}")
                with open(filepath, "r", encoding="utf-8") as f:
                    # Read all non-empty lines.
                    lines = [line.strip() for line in f if line.strip()]
                # Debug: Uncomment the next line if you want to print how many lines were found.
                # print(f"File {filepath} has {len(lines)} valid lines.")
                if not lines:
                    raise ValueError(f"No valid lines found in {filepath}.")
                selected_lines[key] = random.choice(lines)

            # Compose the final secret in the order: truths, origins, consequences.
            output_line = " ".join([
                selected_lines["truths"],
                selected_lines["origins"],
                selected_lines["consequences"]
            ])

            # Insert the generated secret into the Secrets field's text widget.
            secrets_editor = self.field_widgets.get("Secrets")
            if secrets_editor:
                secrets_editor.text_widget.delete("1.0", "end")
                secrets_editor.text_widget.insert("1.0", output_line)
            else:
                raise ValueError("Secrets field editor not found.")

        except Exception as e:
            messagebox.showerror("Error generating secret", str(e))
    def generate_npc(self):
            """
            Generates random NPC data by:
            - Filling the Appearance, Background, Personality, and Quirks fields using the corresponding asset files:
                npc_appearance.txt, npc_background.txt, npc_personality.txt, npc_quirks.txt
            - Filling the NPC's Secret field by reading from:
                npc_secret_implication.txt, npc_secret_motive.txt, npc_secret_origin.txt, npc_secret_detail.txt
            Updates both the underlying data model (self.item) and the UI widgets.
            """
            try:
                # Determine the absolute path of the assets folder.
                current_dir = os.path.dirname(os.path.abspath(__file__))
                assets_folder = os.path.join(current_dir, "assets")

                # Define a helper function to pick a random line from a given file.
                def pick_random_line(filepath):
                    """Handle pick random line."""
                    if not os.path.exists(filepath):
                        raise FileNotFoundError(f"File not found: {filepath}")
                    with open(filepath, "r", encoding="utf-8") as f:
                        lines = [line.strip() for line in f if line.strip()]
                    if not lines:
                        raise ValueError(f"No valid lines found in {filepath}.")
                    return random.choice(lines)

                # Generate basic NPC fields.
                npc_fields = {
                    "Description": "assets/npc_appearance.txt",
                    "Background": "assets/npc_background.txt",
                    "Personality": "assets/npc_personality.txt",
                    "RoleplayingCues": "assets/npc_quirks.txt"
                }
                for field, path in npc_fields.items():
                    # Process each (field, path) from npc_fields.items().
                    value = pick_random_line(path)
                    self.item[field] = value
                    widget = self.field_widgets.get(field)
                    if widget:
                        if hasattr(widget, "text_widget"):
                            widget.text_widget.delete("1.0", "end")
                            widget.text_widget.insert("1.0", value)
                        else:
                            widget.delete(0, "end")
                            widget.insert(0, value)

                # Generate the NPC secret.
                secret_files = {
                    "Implication": "assets/npc_secret_implication.txt",
                    "Motive": "assets/npc_secret_motive.txt",
                    "Origin": "assets/npc_secret_origin.txt",
                    "Detail": "assets/npc_secret_detail.txt"
                }
                secret_parts = []
                for key, path in secret_files.items():
                    secret_parts.append(pick_random_line(path))
                secret_text = " ".join(secret_parts)
                self.item["Secret"] = secret_text
                secret_widget = self.field_widgets.get("Secret")
                if secret_widget:
                    if hasattr(secret_widget, "text_widget"):
                        secret_widget.text_widget.delete("1.0", "end")
                        secret_widget.text_widget.insert("1.0", secret_text)
                    else:
                        secret_widget.delete(0, "end")
                        secret_widget.insert(0, secret_text)

            except Exception as e:
                messagebox.showerror("Error generating NPC", str(e))
    def generate_scenario(self):
        """Handle generate scenario."""
        try:
            # Keep generate scenario resilient if this step fails.
            self.generate_scenario_description()
            self.generate_secret_text()

            npcs_list = load_npcs_list()
            creatures_list = load_creatures_list()
            places_list = load_places_list()

            selected_npcs = random.sample(npcs_list, 3) if len(npcs_list) >= 3 else npcs_list
            selected_places = random.sample(places_list, 3) if len(places_list) >= 3 else places_list
            selected_creatures = random.sample(creatures_list, 3) if len(creatures_list) >= 3 else creatures_list
            # Random selections chosen and applied to UI
            self.item["NPCs"] = selected_npcs
            self.item["Places"] = selected_places
            self.item["Creatures"] = selected_creatures
            # --- NPCs ---
            npc_widgets = self.field_widgets.get("NPCs", [])
            add_npc_combobox = self.field_widgets.get("NPCs_add_combobox")
            while len(npc_widgets) < 3:
                # Keep looping while len(npc_widgets) < 3.
                add_npc_combobox()
                npc_widgets = self.field_widgets["NPCs"]  # Update after adding new combobox

            for i, widget in enumerate(npc_widgets[:3]):
                widget.configure(state="normal")
                widget.delete(0, "end")
                widget.insert(0, selected_npcs[i])
                widget.configure(state="readonly")
            # --- Creatures ---
            creature_widgets = self.field_widgets.get("Creatures", [])
            add_creatures_combobox = self.field_widgets.get("Creatures_add_combobox")
            while len(creature_widgets) < 3:
                # Keep looping while len(creature_widgets) < 3.
                add_creatures_combobox()
                creature_widgets = self.field_widgets["Creatures"]  # Update after adding new combobox

            for i, widget in enumerate(creature_widgets[:3]):
                widget.configure(state="normal")
                widget.delete(0, "end")
                widget.insert(0, selected_creatures[i])
                widget.configure(state="readonly")
            # --- Places ---
            place_widgets = self.field_widgets.get("Places", [])
            add_place_combobox = self.field_widgets.get("Places_add_combobox")
            while len(place_widgets) < 3:
                # Keep looping while len(place_widgets) < 3.
                add_place_combobox()
                place_widgets = self.field_widgets["Places"]  # Update after adding new combobox

            for i, widget in enumerate(place_widgets[:3]):
                widget.configure(state="normal")
                widget.delete(0, "end")
                widget.insert(0, selected_places[i])
                widget.configure(state="readonly")

        except Exception as e:
            messagebox.showerror("Error generating scenario", str(e))
    def generate_scenario_description(self):
        """
        Reads four text files from the assets folder:
        - Inciting Incidents.txt
        - Antagonists.txt
        - Objectives.txt
        - Settings.txt
        Each file contains ~100 elements (one per line). This function randomly selects one line
        from each file and constructs a single-line description in the order:
        Inciting Incident, Antagonists, Objectives, Settings.
        The output is then inserted into the 'Summary' (scenario description) text widget.
        """
        try:
            # Define the file paths for each category.
            files = {
                "inciting": "assets/Inciting Incidents.txt",
                "antagonists": "assets/Antagonists.txt",
                "objectives": "assets/Objectives.txt",
                "settings": "assets/Settings.txt"
            }

            # Read all non-empty lines from each file and roll for a random element.
            selected_lines = {}
            for key, filepath in files.items():
                # Process each (key, filepath) from files.items().
                with open(filepath, "r", encoding="utf-8") as f:
                    # Read non-empty stripped lines.
                    lines = [line.strip() for line in f if line.strip()]
                if not lines:
                    raise ValueError(f"No valid lines found in {filepath}.")
                selected_lines[key] = random.choice(lines)

            # Compose the final description line from the selected lines.
            # The order is: Inciting Incident, Antagonists, Objectives, Settings.
            output_line = " ".join([
                selected_lines["inciting"],
                selected_lines["antagonists"],
                selected_lines["objectives"],
                selected_lines["settings"]
            ])

            # Insert the one-line result into the 'Summary' field's text widget.
            summary_editor = self.field_widgets.get("Summary")
            if summary_editor:
                summary_editor.text_widget.delete("1.0", "end")
                summary_editor.text_widget.insert("1.0", output_line)
            else:
                raise ValueError("Summary field editor not found.")

        except Exception as e:
            messagebox.showerror("Error generating description", str(e))
