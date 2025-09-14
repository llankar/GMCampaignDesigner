import customtkinter as ctk
import os
import requests 
import subprocess
import time
import shutil
from modules.helpers import text_helpers
from modules.helpers.rich_text_editor import RichTextEditor
from modules.helpers.window_helper import position_window_at_top
from PIL import Image, ImageTk
from PIL import ImageGrab
from tkinter import filedialog,  messagebox
from modules.helpers.swarmui_helper import get_available_models
from modules.helpers.config_helper import ConfigHelper
from modules.generic.generic_model_wrapper import GenericModelWrapper
import tkinter as tk
import random
from modules.helpers.text_helpers import format_longtext
from modules.helpers.text_helpers import ai_text_to_rtf_json
from modules.ai.local_ai_client import LocalAIClient
import json
from io import BytesIO

SWARMUI_PROCESS = None

class CustomDropdown(ctk.CTkToplevel):
    def __init__(self, master, options, command, width=None, max_height=300, **kwargs):
        """
        master      – parent widget (usually the root or your main window)
        options     – list of strings
        command     – callback(value) when the user selects
        width       – desired pixel width (defaults to master widget’s width)
        max_height  – maximum pixel height
        """
        super().__init__(master, **kwargs)
        self.command         = command
        self.all_options     = list(options)
        self.filtered_options= list(options)
        self.max_height      = max_height
        self.overrideredirect(True)

        # ─── Search Entry ─────────────────────────────────────────────────────
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.entry = ctk.CTkEntry(self, textvariable=self.search_var,
                                placeholder_text="Search…")
        self.entry.pack(fill="x", padx=5, pady=(5, 0))
        self.entry.bind("<Return>", lambda e: self._on_activate(e))
        self.entry.focus_set()
       
        # ─── Listbox + Scrollbar ─────────────────────────────────────────────
        container = tk.Frame(self)
        container.pack(fill="both", expand=True, padx=5, pady=5)
        self.listbox = tk.Listbox(container, exportselection=False)
        self.scroll  = tk.Scrollbar(container, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=self.scroll.set)

        # let python size the listbox for us, then enforce max_height below
        self.listbox.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")

        # ─── Now populate & size ────────────────────────────────────────────
        self._populate_options()
        self.update_idletasks()  # make sure all req sizes are calculated

        # determine final geometry
        final_w = width or master.winfo_width()
        total_req_h = self.winfo_reqheight()
        final_h = min(total_req_h, self.max_height)

        # master = the widget you clicked on (you should pass its .winfo_toplevel())
        # you still need to set x,y yourself in open_dropdown:
        self.geometry(f"{final_w}x{final_h}")

        # ensure clicks in entry/listbox don't close us
        self.grab_set()

        # ─── Event Bindings ────────────────────────────────────────────────
        self.listbox.bind("<Double-Button-1>", self._on_activate)
        self.listbox.bind("<Return>",         self._on_activate)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.listbox.bind(seq, self._on_mousewheel)

        for widget in (self, self.entry, self.listbox):
            widget.bind("<Escape>", lambda e: self.destroy())
        self.after_idle(lambda: self.entry.focus_set())

        self.after_idle(lambda: self.bind("<FocusOut>", self._on_focus_out))
        self.listbox.bind("<Return>", self._on_activate)
        self.entry.bind("<Down>", lambda e: self.listbox.focus_set())
                        
    def _populate_options(self):
        self.listbox.delete(0, tk.END)
        for opt in self.filtered_options:
            self.listbox.insert(tk.END, opt)
        if self.filtered_options:
            self.listbox.selection_set(0)

    def _on_search_change(self, *args):
        q = self.search_var.get().lower()
        if q:
            self.filtered_options = [o for o in self.all_options if q in o.lower()]
        else:
            self.filtered_options = list(self.all_options)
        self._populate_options()
        # after filter, we could also dynamically resize height if you like

    def _on_activate(self, event):
        sel = self.listbox.curselection()
        if not sel: return
        value = self.filtered_options[sel[0]]
        self.command(value)
        self.destroy()

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.listbox.yview_scroll(-1, "units")
        else:
            self.listbox.yview_scroll(1,  "units")

    def _on_focus_out(self, event):
        # if the new focus is still inside our Toplevel, do nothing
        new = self.focus_get()
        if new and str(new).startswith(str(self)):
            return
        self.destroy()

def load_entities_list(entity_type):
    """
    Creates a model wrapper for the given entity type, fetches all
    database records, and returns a list of names.

    Args:
        entity_type (str): The type of entity to load (e.g., "npcs", "factions").

    Returns:
        list: A list of names for the given entity, or an empty list on error.
    """
    try:
        wrapper = GenericModelWrapper(entity_type)
        entities = wrapper.load_items() # Assumes get_all() returns a list of dictionaries.
        # Each record is expected to have a "Name" key:
        return [entity.get("Name", "Unnamed") for entity in entities]
    except Exception as e:
        # Log error if needed:
        print(f"Error loading {entity_type}: {e}")
        return []

def load_factions_list():
    return load_entities_list("factions")

def load_npcs_list():
    return load_entities_list("npcs")
def load_pcs_list():
    return load_entities_list("pcs")
def load_places_list():
    return load_entities_list("places")

def load_objects_list():
    return load_entities_list("objects")

def load_creatures_list():
    return load_entities_list("creatures")

"""
A customizable editor window for creating and editing generic items with dynamic field generation.

This class provides a flexible Tkinter-based editor that can dynamically generate input fields
based on a provided template. It supports various field types including text entries, long text
fields, dynamic combobox lists, and portrait selection/generation.

Key features:
- Dynamic field generation from a template
- Support for rich text editing
- Ability to generate random scenario descriptions and secrets
- Portrait selection and AI-assisted portrait generation
- Customizable action bar with save, cancel, and scenario generation options

Args:
    master (tk.Tk): The parent window
    item (dict): The item being edited
    template (dict): A template defining the structure of the item
    creation_mode (bool, optional): Whether the window is in item creation mode. Defaults to False.
"""
class GenericEditorWindow(ctk.CTkToplevel):
    def __init__(self, master, item, template, model_wrapper, creation_mode=False):
        super().__init__(master)
        self.item = item
        self.template = template
        self.saved = False
        self.model_wrapper = model_wrapper
        self.field_widgets = {}
        
        self.transient(master)
        self.lift()
        self.grab_set()
        self.focus_force()
        self.bind("<Escape>", lambda e: self.destroy())
        item_type = self.model_wrapper.entity_type.capitalize()[:-1]  # "npcs" → "Npc"
        self.title(f"Create {item_type}" if creation_mode else f"Edit {item_type}")

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True)

        self.scroll_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Reorder fields so that "Portrait" comes first ---
        fields = self.template["fields"]
        portrait_field = None
        image_field = None
        other_fields = []
        for field in fields:
            if field["name"] == "Portrait":
                portrait_field = field
            elif field["name"] == "Image":
                image_field = field
            else:
                other_fields.append(field)
        if portrait_field:
            ctk.CTkLabel(self.scroll_frame, text=portrait_field["name"]).pack(pady=(5, 0), anchor="w")
            self.create_portrait_field(portrait_field)
        if image_field:
            ctk.CTkLabel(self.scroll_frame, text=image_field["name"]).pack(pady=(5, 0), anchor="w")
            self.create_image_field(image_field)

        for field in other_fields:
            if (field["name"] == "FogMaskPath" or field["name"] == "Tokens" or field["name"] == "token_size"):
                continue
            if (field["name"] == "Image"):
                continue
            ctk.CTkLabel(self.scroll_frame, text=field["name"]).pack(pady=(5, 0), anchor="w")
            if field["type"] == "list_longtext":
                self.create_dynamic_longtext_list(field)
            elif field["type"] == "longtext":
                self.create_longtext_field(field)
            elif field["name"] in ["NPCs", "Places", "Factions", "Objects", "Creatures", "PCs"] or \
                 (field.get("type") == "list" and field.get("linked_type")):
                self.create_dynamic_combobox_list(field)
            elif field["type"] == "boolean":
                self.create_boolean_field(field)
            elif field["type"] == "file":
                self.create_file_field(field)
            else:
                self.create_text_entry(field)
                

        self.create_action_bar()

        # Instead of a fixed geometry, update layout and compute the required size.
        self.update_idletasks()
        req_width = self.winfo_reqwidth()
        req_height = self.winfo_reqheight()
        # Enforce a minimum size if needed.
        min_width, min_height = 1000, 1050
        if req_width < min_width:
            req_width = min_width
        if req_height < min_height:
            req_height = min_height
        self.geometry(f"{req_width}x{req_height}")
        self.minsize(req_width, req_height)

        # Optionally, adjust window position.
        position_window_at_top(self)
        # Lazy AI client init
        self._ai_client = None

    def _get_ai(self):
        if self._ai_client is None:
            self._ai_client = LocalAIClient()
        return self._ai_client
    def _make_richtext_editor(self, parent, initial_text, hide_toolbar=True):
        """
        Shared initialization for any RichTextEditor-based field.
        Returns the editor instance.
        """
        editor = RichTextEditor(parent)
        editor.text_widget.configure(
            bg="#2B2B2B", fg="white", insertbackground="white"
        )
        # Load data (dict or raw string)

        data = initial_text
        if not isinstance(data, dict):
            try:
                data = json.loads(data)
            except Exception:
                data = {"text": str(initial_text or "")}
                
        editor.load_text_data(data)
        # Toolbar toggle
        if hide_toolbar:
            editor.toolbar.pack_forget()
            editor.text_widget.bind(
                "<FocusIn>",
                lambda e: editor.toolbar.pack(fill="x", before=editor.text_widget, pady=2)
            )
            editor.text_widget.bind(
                "<FocusOut>",
                lambda e: editor.toolbar.pack_forget()
            )
        editor.pack(fill="x", pady=5)
        return editor

    def create_longtext_field(self, field):
        raw = self.item.get(field["name"], "")
        editor = self._make_richtext_editor(self.scroll_frame, raw)
        self.field_widgets[field["name"]] = editor

        # Place action buttons for this field on one row
        btn_row = ctk.CTkFrame(self.scroll_frame)
        btn_row.pack(fill="x", pady=5)

        # extra buttons for Summary/Secrets…
        if field["name"] == "Summary":
            ctk.CTkButton(
                btn_row, text="Random Summary",
                command=self.generate_scenario_description
            ).pack(side="left", padx=5, pady=5)
            ctk.CTkButton(
                btn_row, text="AI Draft Summary",
                command=lambda fn=field["name"]: self.ai_draft_field(fn)
            ).pack(side="left", padx=5, pady=5)
        if field["name"] == "Secrets":
            ctk.CTkButton(
                btn_row, text="Generate Secret",
                command=self.generate_secret_text
            ).pack(side="left", padx=5, pady=5)
            ctk.CTkButton(
                btn_row, text="AI Draft Secret",
                command=lambda fn=field["name"]: self.ai_draft_field(fn)
            ).pack(side="left", padx=5, pady=5)

        # Add AI draft for NPC/Creature Description
        if (
            field["name"] == "Description"
            and self.model_wrapper
            and getattr(self.model_wrapper, "entity_type", "") in ("npcs", "creatures")
        ):
            ctk.CTkButton(
                btn_row, text="AI Draft Description",
                command=lambda fn=field["name"]: self.ai_draft_field(fn)
            ).pack(side="left", padx=5, pady=5)

        # Generic AI improvement button for any long text field
        ctk.CTkButton(
            btn_row, text=f"AI Improve {field['name']}",
            command=lambda fn=field["name"]: self.ai_improve_field(fn)
        ).pack(side="left", padx=5, pady=5)

    def create_dynamic_longtext_list(self, field):
        container = ctk.CTkFrame(self.scroll_frame)
        container.pack(fill="x", pady=5)

        editors = []

        def add_scene(initial_text=""):
            row = ctk.CTkFrame(container)
            row.pack(fill="x", pady=(0, 5))
            ctk.CTkLabel(row, text=f"Scene {len(editors)+1}").pack(anchor="w")
            
            # here’s the only duplication left:
            rte = self._make_richtext_editor(row, initial_text, hide_toolbar=True)

            # Remove button
            btn = ctk.CTkButton(
                row, text="– Remove", width=80,
                command=lambda: (row.destroy(), editors.remove(rte))
            )
            btn.pack(anchor="e", pady=(2, 0))

            editors.append(rte)

        # pre-populate
        scenes_data = self.item.get(field["name"]) # Get the raw value first
        # If the key exists and its value is None, or if the key doesn't exist (though .get would give default),
        # ensure we iterate over an empty list to prevent TypeError.
        # The original .get(field["name"], []) only helps if the key is missing, not if value is None.
        if scenes_data is None:
            scenes_data = []
        
        for scene in scenes_data:
            add_scene(scene)
        # add-new button
        ctk.CTkButton(
            container, text="+ Add Scene", command=add_scene
        ).pack(anchor="w", pady=(5, 0))

        self.field_widgets[field["name"]] = editors
        self.field_widgets[f"{field['name']}_container"] = container
        self.field_widgets[f"{field['name']}_add_scene"] = add_scene
    
    def create_file_field(self, field):
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.pack(fill="x", pady=5)

        # load existing attachment name (if any)
        self.attachment_filename = self.item.get(field["name"], "")
        label_text = os.path.basename(self.attachment_filename) or "[No Attachment]"

        self.attach_label = ctk.CTkLabel(frame, text=label_text)
        self.attach_label.pack(side="left", padx=5)

        ctk.CTkButton(
            frame,
            text="Browse Attachment",
            command=self.select_attachment
        ).pack(side="left", padx=5)

        # placeholder so save() sees the key
        self.field_widgets[field["name"]] = None

    def select_attachment(self):
        file_path = filedialog.askopenfilename(
            title="Select Attachment",
            filetypes=[("All Files", "*.*")]
        )
        if not file_path:
            return

        # ensure upload folder
        campaign_dir = ConfigHelper.get_campaign_dir()
        upload_folder = os.path.join(campaign_dir, "assets", "uploads")
        os.makedirs(upload_folder, exist_ok=True)

        # copy into uploads/
        filename = os.path.basename(file_path)
        dest = os.path.join(upload_folder, filename)
        try:
            shutil.copy(file_path, dest)
            self.attachment_filename = filename
            self.attach_label.configure(text=filename)
        except Exception as e:
            messagebox.showerror("Error", f"Could not copy file:\n{e}")
    
    def create_boolean_field(self, field):
        # Define the two possible dropdown options.
        options = ["True", "False"]
        # Retrieve the stored value (default to "False" if not found).
        stored_value = self.item.get(field["name"], "False")
        # Convert stored_value to a string "True" or "False":
        if isinstance(stored_value, bool):
            initial_value = "True" if stored_value else "False"
        else:
            initial_value = "True" if (str(stored_value).lower() == "true" or stored_value ==1) else "False"
        # Create a StringVar with the initial value.
        var = ctk.StringVar(value=initial_value)
        # Create the OptionMenu (dropdown) using customtkinter.
        option_menu = ctk.CTkOptionMenu(self.scroll_frame, variable=var, values=options)
        option_menu.pack(fill="x", pady=5)
        # Save the widget and its StringVar for later retrieval.
        self.field_widgets[field["name"]] = (option_menu, var)

    
    
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
        try:
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


    def on_combo_mousewheel(self, event, combobox):
        # Get the current selection and available options.
        options = combobox.cget("values")
        if not options:
            return
        current_val = combobox.get()
        try:
            idx = options.index(current_val)
        except ValueError:
            idx = 0

        # Determine scroll direction.
        if event.num == 4 or event.delta > 0:
            # Scroll up: go to previous option.
            new_idx = max(0, idx - 1)
        elif event.num == 5 or event.delta < 0:
            # Scroll down: go to next option.
            new_idx = min(len(options) - 1, idx + 1)
        else:
            new_idx = idx

        combobox.set(options[new_idx])
    
    def create_dynamic_combobox_list(self, field):
        container = ctk.CTkFrame(self.scroll_frame)
        container.pack(fill="x", pady=5)

        combobox_list = []
        combobox_vars = []
        # Prefer explicit linked_type when provided (for custom fields)
        linked = (field.get("linked_type") or "").strip()
        fname = field.get("name")
        if linked == "PCs" or fname == "PCs":
            options_list = load_pcs_list()
            label_text = f"Add {linked or 'PC'}"
        elif linked == "NPCs" or fname == "NPCs":
            options_list = load_npcs_list()
            label_text = f"Add {linked or 'NPC'}"
        elif linked == "Places" or fname == "Places":
            options_list = load_places_list()
            label_text = f"Add {linked or 'Place'}"
        elif linked == "Factions" or fname == "Factions":
            options_list = load_factions_list()
            label_text = f"Add {linked or 'Faction'}"
        elif linked == "Objects" or fname == "Objects":
            options_list = load_objects_list()
            label_text = f"Add {linked or 'Object'}"
        elif linked == "Creatures" or fname == "Creatures":
            options_list = load_creatures_list()
            label_text = f"Add {linked or 'Creature'}"
        else:
            options_list = []
            label_text = f"Add {fname}"

        initial_values = self.item.get(field["name"]) or []

        def remove_this(row, entry_widget):
            row.destroy()
            try:
                idx = combobox_list.index(entry_widget)
                combobox_list.pop(idx)
                if idx < len(combobox_vars):
                    combobox_vars.pop(idx)
            except ValueError:
                pass

        def open_dropdown(widget, var):
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height()
            dropdown = CustomDropdown(
                widget.winfo_toplevel(),
                options=options_list,
                command=lambda v: var.set(v),
                width=widget.winfo_width(),
                max_height=200
            )
            dropdown.geometry(f"{widget.winfo_width()}x{dropdown.winfo_reqheight()}+{x}+{y}")
            dropdown.lift()
            dropdown.grab_set()

            # move keyboard focus into the search box immediately
            dropdown.entry.focus_set()

        def add_combobox(initial_value=None):
            row = ctk.CTkFrame(container)
            row.pack(fill="x", pady=2)

            var = ctk.StringVar()
            entry = ctk.CTkEntry(row, textvariable=var, state="readonly")
            entry.pack(side="left", expand=True, fill="x")

            # open the dropdown on click *or* focus for EVERY dynamic combobox:
            entry.bind("<Button-1>",  lambda e, w=entry, v=var: open_dropdown(w, v))

            if initial_value and initial_value in options_list:
                var.set(initial_value)
            elif options_list:
                var.set(options_list[0])

            btn = ctk.CTkButton(row, text="▼", width=30, command=lambda: open_dropdown(entry, var))
            btn.pack(side="left", padx=5)

            remove_btn = ctk.CTkButton(row, text="-", width=30, command=lambda: remove_this(row, entry))
            remove_btn.pack(side="left", padx=5)

            combobox_list.append(entry)
            combobox_vars.append(var)

        for value in initial_values:
            add_combobox(value)

        add_button = ctk.CTkButton(container, text=label_text, command=add_combobox)
        add_button.pack(anchor="w", pady=2)

        # Save widgets clearly
        self.field_widgets[field["name"]] = combobox_list
        self.field_widgets[f"{field['name']}_vars"] = combobox_vars
        self.field_widgets[f"{field['name']}_container"] = container
        self.field_widgets[f"{field['name']}_add_combobox"] = add_combobox



    def create_text_entry(self, field):
        entry = ctk.CTkEntry(self.scroll_frame)
        value = self.item.get(field["name"], "")
        if value:
            entry.insert(0, self.item.get(field["name"], ""))
        entry.pack(fill="x", pady=5)
        self.field_widgets[field["name"]] = entry

    def create_action_bar(self):
        action_bar = ctk.CTkFrame(self.main_frame)
        action_bar.pack(fill="x", pady=5)

        ctk.CTkButton(action_bar, text="Cancel", command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(action_bar, text="Save", command=self.save).pack(side="right", padx=5)
        if self.model_wrapper.entity_type== 'scenarios':
            ctk.CTkButton(action_bar, text='Generate Scenario', command=self.generate_scenario).pack(side='left', padx=5)
            ctk.CTkButton(action_bar, text='AI Generate Scenario', command=self.ai_generate_full_scenario).pack(side='left', padx=5)

        if self.model_wrapper.entity_type== 'npcs':
            ctk.CTkButton(action_bar, text='Generate NPC', command=self.generate_npc).pack(side='left', padx=5)
            ctk.CTkButton(action_bar, text='AI Generate NPC', command=self.ai_generate_full_npc).pack(side='left', padx=5)

        if self.model_wrapper.entity_type== 'creatures':
            ctk.CTkButton(action_bar, text='AI Generate Creature', command=self.ai_generate_full_creature).pack(side='left', padx=5)
    
    # === Sauvegarde ===
    def save(self):
        for field in self.template["fields"]:
            if field["name"] in ["FogMaskPath", "Tokens", "token_size"]:
                continue
            widget = self.field_widgets[field["name"]]
            if field["type"] == "list_longtext":
                # grab each editor’s serialized data
                self.item[field["name"]] = [
                    rte.get_text_data() if hasattr(rte, "get_text_data")
                                        else rte.text_widget.get("1.0","end-1c")
                for rte in widget
                ]
            elif field["type"] == "longtext":
                data = widget.get_text_data()
                if isinstance(data, dict) and not data.get("text", "").strip():
                    self.item[field["name"]] = ""
                else:
                    self.item[field["name"]] = data
            elif field["name"] in ["Places", "NPCs", "Factions", "Objects", "Creatures", "PCs"] or \
                 (field.get("type") == "list" and field.get("linked_type")):
                self.item[field["name"]] = [cb.get() for cb in widget if cb.get()]
            elif field["type"] == "file":
                # store the filename (not full path) into the model
                self.item[field["name"]] = getattr(self, "attachment_filename", "")
            elif field["name"] == "Portrait":
                self.item[field["name"]] = self.portrait_path
            elif field["name"] == "Image":
                self.item[field["name"]] = self.image_path
            elif field["type"] == "boolean":
                # widget is stored as (option_menu, StringVar); convert to Boolean.
                self.item[field["name"]] = True if widget[1].get() == "True" else False
            else:
                self.item[field["name"]] = widget.get()
        self.saved = True
        self.destroy()

    def create_portrait_field(self, field):
        # Create a main frame for the portrait field
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.pack(fill="x", pady=5)

        campaign_dir = ConfigHelper.get_campaign_dir()
        portrait_path = self.item.get("Portrait", "")
        image_frame = ctk.CTkFrame(frame)
        image_frame.pack(fill="x", pady=5)
        if portrait_path == "" or portrait_path is None:
            self.portrait_label = ctk.CTkLabel(image_frame, text="[No Image]")
            self.portrait_path= "[No Image]"
        else:
            self.portrait_path= os.path.join(campaign_dir, portrait_path)
            # Create a separate frame for the image and center it
            if self.portrait_path and os.path.exists(self.portrait_path):
                image = Image.open(self.portrait_path).resize((256, 256))
                self.portrait_image = ctk.CTkImage(light_image=image, size=(256, 256))
                self.portrait_label = ctk.CTkLabel(image_frame, image=self.portrait_image, text="")
            else:
                self.portrait_label = ctk.CTkLabel(image_frame, text="[No Image]")
            
            # Pack without specifying a side to center the widget
        self.portrait_label.pack(pady=5)
        
        # Create a frame for the buttons and pack them (they'll appear below the centered image)
        button_frame = ctk.CTkFrame(frame)
        button_frame.pack(pady=5)
        
        ctk.CTkButton(button_frame, text="Select Portrait", command=self.select_portrait).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Paste Portrait", command=self.paste_portrait_from_clipboard).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Create Portrait with description", command=self.create_portrait_with_swarmui).pack(side="left", padx=5)

        self.field_widgets[field["name"]] = self.portrait_path

    def paste_portrait_from_clipboard(self):
        """Paste image from clipboard and set as entity portrait.
        Supports images directly or image file paths in clipboard (Windows).
        """
        try:
            data = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Unable to access clipboard: {e}")
            return

        if data is None:
            messagebox.showinfo("Paste Portrait", "No image found in clipboard.")
            return

        # If clipboard contains a list of file paths, try first valid image path
        if isinstance(data, list):
            for path in data:
                try:
                    if os.path.isfile(path):
                        self.portrait_path = self.copy_and_resize_portrait(path)
                        self.portrait_label.configure(text=os.path.basename(self.portrait_path))
                        return
                except Exception:
                    continue
            messagebox.showinfo("Paste Portrait", "Clipboard has file paths but none are valid images.")
            return

        # If clipboard contains a PIL Image
        if isinstance(data, Image.Image):
            try:
                campaign_dir = ConfigHelper.get_campaign_dir()
                portrait_folder = os.path.join(campaign_dir, "assets", "portraits")
                os.makedirs(portrait_folder, exist_ok=True)

                base_name = (self.item.get("Name") or "Unnamed").replace(" ", "_")
                dest_filename = f"{base_name}_{id(self)}.png"
                dest_path = os.path.join(portrait_folder, dest_filename)

                # Convert to RGB to ensure PNG save works for all modes
                img = data
                if img.mode in ("P", "RGBA"):
                    img = img.convert("RGB")

                # Save directly to destination
                img.save(dest_path, format="PNG")

                # Store relative path used by the app
                self.portrait_path = os.path.join("assets/portraits/", dest_filename)
                self.portrait_label.configure(text=os.path.basename(self.portrait_path))
                return
            except Exception as e:
                messagebox.showerror("Paste Portrait", f"Failed to paste image: {e}")
                return

        messagebox.showinfo("Paste Portrait", "Clipboard content is not an image.")
    
    def create_image_field(self, field):
        # Create a main frame for the image field
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.pack(fill="x", pady=5)

        campaign_dir = ConfigHelper.get_campaign_dir()
        image_path = self.item.get("Image", "")
        # Create a separate frame for the image and center it
        image_frame = ctk.CTkFrame(frame)
        image_frame.pack(fill="x", pady=5)
        if image_path == "" or image_path is None:
            self.image_label = ctk.CTkLabel(image_frame, text="[No Image]")
            self.image_path= "[No Image]"
        else:
            self.image_path= os.path.join(campaign_dir, image_path)
            
            if self.image_path and os.path.exists(self.image_path):
                image = Image.open(self.image_path).resize((256, 256))
                self.image_image = ctk.CTkImage(light_image=image, size=(256, 256))
                self.image_label = ctk.CTkLabel(image_frame, image=self.image_image, text="")
            else:
                self.image_label = ctk.CTkLabel(image_frame, text="[No Image]")

        # Pack without specifying a side to center the widget
        self.image_label.pack(pady=5)

        # Create a frame for the buttons and pack them (they'll appear below the centered image)
        button_frame = ctk.CTkFrame(frame)
        button_frame.pack(pady=5)

        ctk.CTkButton(button_frame, text="Select Image", command=self.select_image).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Paste Image", command=self.paste_image_from_clipboard).pack(side="left", padx=5)
        self.field_widgets[field["name"]] = self.image_path

    def paste_image_from_clipboard(self):
        """Paste image from clipboard and set as entity image (map image).
        Supports images directly or image file paths in clipboard (Windows/macOS).
        """
        try:
            data = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Unable to access clipboard: {e}")
            return

        if data is None:
            messagebox.showinfo("Paste Image", "No image found in clipboard.")
            return

        # If clipboard contains a list of file paths, try first valid image path
        if isinstance(data, list):
            for path in data:
                try:
                    if os.path.isfile(path):
                        self.image_path = self.copy_and_resize_image(path)
                        self.image_label.configure(text=os.path.basename(self.image_path))
                        return
                except Exception:
                    continue
            messagebox.showinfo("Paste Image", "Clipboard has file paths but none are valid images.")
            return

        # If clipboard contains a PIL Image
        if isinstance(data, Image.Image):
            try:
                campaign_dir = ConfigHelper.get_campaign_dir()
                image_folder = os.path.join(campaign_dir, "assets", "images", "map_images")
                os.makedirs(image_folder, exist_ok=True)

                base_name = (self.item.get("Name") or "Unnamed").replace(" ", "_")
                dest_filename = f"{base_name}_{id(self)}.png"
                dest_path = os.path.join(image_folder, dest_filename)

                # Convert to RGB to ensure PNG save works for all modes
                img = data
                if img.mode in ("P", "RGBA"):
                    img = img.convert("RGB")

                # Save directly to destination
                img.save(dest_path, format="PNG")

                # Store relative path used by the app
                self.image_path = os.path.join("assets/images/map_images/", dest_filename)
                self.image_label.configure(text=os.path.basename(self.image_path))
                return
            except Exception as e:
                messagebox.showerror("Paste Image", f"Failed to paste image: {e}")
                return

        messagebox.showinfo("Paste Image", "Clipboard content is not an image.")

    def launch_swarmui(self):
        global SWARMUI_PROCESS
        # Retrieve the SwarmUI path from config.ini
        swarmui_path = ConfigHelper.get("Paths", "swarmui_path", fallback=r"E:\SwarmUI\SwarmUI")
        # Build the command by joining the path with the batch file name
        SWARMUI_CMD = os.path.join(swarmui_path, "launch-windows.bat")
        env = os.environ.copy()
        env.pop('VIRTUAL_ENV', None)
        if SWARMUI_PROCESS is None or SWARMUI_PROCESS.poll() is not None:
            try:
                SWARMUI_PROCESS = subprocess.Popen(
                    SWARMUI_CMD,
                    shell=True,
                    cwd=swarmui_path,
                    env=env
                )
                # Wait a little for the process to initialize.
                time.sleep(120.0)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to launch SwarmUI: {e}")

    def cleanup_swarmui(self):
        """
        Terminate the SwarmUI process if it is running.
        """
        global SWARMUI_PROCESS
        if SWARMUI_PROCESS is not None and SWARMUI_PROCESS.poll() is None:
            SWARMUI_PROCESS.terminate()

    def create_portrait_with_swarmui(self):
      
        self.launch_swarmui()
        # Ask for model
        model_options = get_available_models()
        if not model_options:
            messagebox.showerror("Error", "No models available in SwarmUI models folder.")
            return

        # Pop-up to select model
        top = ctk.CTkToplevel(self)
        top.title("Select AI Model")
        top.geometry("400x200")
        top.transient(self)
        top.grab_set()

        model_var = ctk.StringVar(value=model_options[0])
        last_model = ConfigHelper.get("LastUsed", "model", fallback=None)
        
        if last_model in model_options:
            selected_model = ctk.StringVar(value=last_model)
        else:
            selected_model = ctk.StringVar(value=model_options[0])
        ctk.CTkLabel(top, text="Select AI Model for this NPC:").pack(pady=20)
        ctk.CTkOptionMenu(top, values=model_options, variable=selected_model).pack(pady=10)

        def on_confirm():
            top.destroy()
            ConfigHelper.set("LastUsed", "model", selected_model.get())
            self.generate_portrait(selected_model.get())
        ctk.CTkButton(top, text="Generate", command=on_confirm).pack(pady=10)

    def generate_portrait(self, selected_model):
        """
        Generates a portrait image using the SwarmUI API and associates the resulting
        image with the current NPC by updating its 'Portrait' field.
        """
        SWARM_API_URL = "http://127.0.0.1:7801"  # Change if needed
        try:
            # Step 1: Obtain a new session from SwarmUI
            session_url = f"{SWARM_API_URL}/API/GetNewSession"
            session_response = requests.post(session_url, json={}, headers={"Content-Type": "application/json"})
            session_data = session_response.json()
            session_id = session_data.get("session_id")
            if not session_id:
                messagebox.showerror("Error", "Failed to obtain session ID from Swarm API.")
                return

            # Build a prompt based on the current NPC's data (you can enhance this as needed)
            npc_name = self.item.get("Name", "Unknown")
            npc_role = self.item.get("Role", "Unknown")
            npc_faction = self.item.get("Factions", "Unknown")
            npc_object = self.item.get("Objects", "Unknown")
            npc_desc = self.item.get("Description", "Unknown") 
            npc_desc =  text_helpers.format_longtext(npc_desc)
            npc_desc = f"{npc_desc} {npc_role} {npc_faction} {npc_object}"
            prompt = f"{npc_desc}"

            # Step 2: Define image generation parameters
            prompt_data = {
                "session_id": session_id,
                "images": 6,  # Generate multiple candidates
                "prompt": prompt,
                "negativeprompt": "blurry, low quality, comics style, mangastyle, paint style, watermark, ugly, monstrous, too many fingers, too many legs, too many arms, bad hands, unrealistic weapons, bad grip on equipment, nude",
                "model": selected_model,
                "width": 1024,
                "height": 1024,
                "cfgscale": 9,
                "steps": 20,
                "seed": -1
            }
            generate_url = f"{SWARM_API_URL}/API/GenerateText2Image"
            image_response = requests.post(generate_url, json=prompt_data, headers={"Content-Type": "application/json"})
            image_data = image_response.json()

            images = image_data.get("images")
            if not images or len(images) == 0:
                messagebox.showerror("Error", "Image generation failed. Check API response.")
                return

            # Step 3: Download all generated images into memory
            thumbs = []
            images_bytes = []
            for rel_path in images:
                try:
                    url = f"{SWARM_API_URL}/{rel_path}"
                    resp = requests.get(url)
                    if resp.status_code == 200:
                        images_bytes.append(resp.content)
                        img = Image.open(BytesIO(resp.content)).convert("RGB")
                        thumb = img.copy()
                        thumb.thumbnail((256, 256))
                        thumbs.append(thumb)
                except Exception:
                    continue

            if not thumbs:
                messagebox.showerror("Error", "Failed to download generated images.")
                return

            # Step 4: Let user choose one of the 6 images
            chosen_index = self._show_image_selection_window(thumbs)
            if chosen_index is None or chosen_index < 0 or chosen_index >= len(images_bytes):
                return  # User cancelled

            chosen_bytes = images_bytes[chosen_index]

            # Step 5: Save the chosen image locally and update the NPC's Portrait field
            output_filename = f"{npc_name.replace(' ', '_')}_portrait.png"
            with open(output_filename, "wb") as f:
                f.write(chosen_bytes)

            # Associate the selected portrait with the NPC data.
            self.portrait_path = self.copy_and_resize_portrait(output_filename)
            self.portrait_label.configure(text=os.path.basename(self.portrait_path))

            # Copy the original generated file to assets/generated and delete local temp
            GENERATED_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "generated")
            os.makedirs(GENERATED_FOLDER, exist_ok=True)
            shutil.copy(output_filename, os.path.join(GENERATED_FOLDER, output_filename))
            os.remove(output_filename)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    def _show_image_selection_window(self, pil_images):
        """
        Display a modal window with thumbnails side by side for the user to choose.
        Returns the selected index, or None if cancelled.
        """
        if not pil_images:
            return None

        top = ctk.CTkToplevel(self)
        top.title("Choose a Portrait")
        top.transient(self)
        top.grab_set()

        # Container frame
        container = ctk.CTkFrame(top)
        container.pack(padx=10, pady=10, fill="both", expand=True)

        # Keep CTkImage references to avoid GC
        ctk_images = []
        selected = {"idx": None}

        def on_choose(i):
            selected["idx"] = i
            top.destroy()

        # Layout: 3 columns x 2 rows (up to 6 images)
        cols = 6 if len(pil_images) <= 6 else 6
        # Place horizontally side by side if <= 6
        for i, img in enumerate(pil_images[:6]):
            cimg = ctk.CTkImage(light_image=img, size=(256, 256))
            ctk_images.append(cimg)
            btn = ctk.CTkButton(container, image=cimg, text="", width=260, height=260,
                                command=lambda idx=i: on_choose(idx))
            btn.grid(row=0, column=i, padx=5, pady=5)

        # Cancel button
        cancel_btn = ctk.CTkButton(top, text="Cancel", command=lambda: (setattr(selected, "idx", None), top.destroy()))
        # Workaround: setattr on dict won't work; override with lambda capturing selected
        def _cancel():
            selected["idx"] = None
            top.destroy()
        cancel_btn.configure(command=_cancel)
        cancel_btn.pack(pady=5)

        # Size window to fit thumbnails in a row
        top.update_idletasks()
        total_w = min(6, len(pil_images)) * (260 + 10) + 20
        total_h = 320
        try:
            top.geometry(f"{total_w}x{total_h}")
        except Exception:
            pass

        top.wait_window()
        return selected["idx"]

    def select_portrait(self):
        file_path = filedialog.askopenfilename(
            title="Select Portrait Image",
            filetypes=[
                ("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp"),
                ("PNG Files", "*.png"),
                ("JPEG Files", "*.jpg;*.jpeg"),
                ("GIF Files", "*.gif"),
                ("Bitmap Files", "*.bmp"),
                ("WebP Files", "*.webp"),
                ("All Files", "*.*")
            ]
        )

        if file_path:
            self.portrait_path = self.copy_and_resize_portrait(file_path)
            self.portrait_label.configure(text=os.path.basename(self.portrait_path))
    
    def select_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp"),
                ("PNG Files", "*.png"),
                ("JPEG Files", "*.jpg;*.jpeg"),
                ("GIF Files", "*.gif"),
                ("Bitmap Files", "*.bmp"),
                ("WebP Files", "*.webp"),
                ("All Files", "*.*")
            ]
        )

        if file_path:
            self.image_path = self.copy_and_resize_image(file_path)
            self.image_label.configure(text=os.path.basename(self.image_path))

    def copy_and_resize_image(self, src_path):
        campaign_dir = ConfigHelper.get_campaign_dir()
        IMAGE_FOLDER = os.path.join(campaign_dir, "assets", "images", "map_images")
        MAX_IMAGE_SIZE = (1920, 1080)

        os.makedirs(IMAGE_FOLDER, exist_ok=True)

        image_name = self.item.get("Name", "Unnamed").replace(" ", "_")
        ext = os.path.splitext(src_path)[-1].lower()
        dest_filename = f"{image_name}_{id(self)}{ext}"
        dest_path = os.path.join(IMAGE_FOLDER, dest_filename)
        dest_path_short= os.path.join("assets/images/map_images/", dest_filename)
        shutil.copy(src_path, dest_path)

        return dest_path_short

    def copy_and_resize_portrait(self, src_path):
        campaign_dir = ConfigHelper.get_campaign_dir()
        PORTRAIT_FOLDER = os.path.join(campaign_dir, "assets", "portraits")
        MAX_PORTRAIT_SIZE = (1024, 1024)

        os.makedirs(PORTRAIT_FOLDER, exist_ok=True)

        npc_name = self.item.get("Name", "Unnamed").replace(" ", "_")
        ext = os.path.splitext(src_path)[-1].lower()
        dest_filename = f"{npc_name}_{id(self)}{ext}"
        dest_path = os.path.join(PORTRAIT_FOLDER, dest_filename)
        dest_path_short= os.path.join("assets/portraits/", dest_filename)
        shutil.copy(src_path, dest_path)
        
        return dest_path_short
    
    # ---------------- AI helpers (gpt-oss / OpenAI-compatible) ----------------
    def _field_text(self, field_name):
        widget = self.field_widgets.get(field_name)
        if hasattr(widget, "text_widget"):
            return widget.text_widget.get("1.0", "end").strip()
        return str(self.item.get(field_name, ""))

    def _set_field_text(self, field_name, text):
        widget = self.field_widgets.get(field_name)
        if hasattr(widget, "text_widget"):
            # Try to interpret AI markdown-like formatting into RTF-JSON
            try:
                rtf = ai_text_to_rtf_json(text)
                widget.load_text_data(rtf)
            except Exception:
                widget.text_widget.delete("1.0", "end")
                widget.text_widget.insert("1.0", text)
        else:
            # Fallback: create_text_entry stored Entry
            try:
                widget.delete(0, "end")
                widget.insert(0, text)
            except Exception:
                self.item[field_name] = text

    def ai_improve_field(self, field_name):
        try:
            current = self._field_text(field_name)
            context_name = self.item.get("Name") or self.item.get("Title") or self.model_wrapper.entity_type
            # Load templates from config with sensible fallbacks
            default_system = (
                "You are a helpful RPG assistant. Improve the given text for use in a campaign manager adding details and flavor. "
                "Keep it concise, evocative, and suitable for GMs. Return plain text only."
            )
            default_user = "Entity: {context_name}\nField: {field_name}\nText to improve:\n{current}"

            system_tpl = ConfigHelper.get("AI_PROMPTS", "improve_system", fallback=default_system)
            user_tpl = ConfigHelper.get("AI_PROMPTS", "improve_user", fallback=default_user)
            # Allow \n sequences in config to mean newlines
            if isinstance(system_tpl, str):
                system_tpl = system_tpl.replace("\\n", "\n")
            if isinstance(user_tpl, str):
                user_tpl = user_tpl.replace("\\n", "\n")

            # Safe formatting of the user template
            fmt_values = {
                "context_name": context_name,
                "field_name": field_name,
                "current": current,
            }
            try:
                user = user_tpl.format(**fmt_values)
            except Exception:
                user = default_user.format(**fmt_values)
            system = system_tpl
            content = self._get_ai().chat([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ])
            if content:
                self._set_field_text(field_name, content)
        except Exception as e:
            messagebox.showerror("AI Error", f"Failed to improve {field_name}: {e}")

    def ai_draft_field(self, field_name):
        try:
            context_name = self.item.get("Name") or self.item.get("Title") or self.model_wrapper.entity_type
            # Build a lightweight context from common fields if present
            hints = []
            for key in ("NPCs", "Places", "Creatures", "Factions", "Genre", "Tags", "Objectives"):
                val = self.item.get(key)
                if val:
                    hints.append(f"{key}: {val}")
            joined_hints = "\n".join(hints)
            # Load templates from config with sensible fallbacks
            default_system = (
                "You are a helpful RPG assistant. Draft a compelling field for a campaign item. "
                "Write 1-3 short paragraphs. Return plain text only."
            )
            default_user = (
                "Entity: {context_name}\n"
                "Target field: {field_name}\n"
                "Hints (optional):\n{joined_hints}\n"
                "Draft the field content now."
            )

            system_tpl = ConfigHelper.get("AI_PROMPTS", "draft_system", fallback=default_system)
            user_tpl = ConfigHelper.get("AI_PROMPTS", "draft_user", fallback=default_user)
            # Allow \n sequences in config to mean newlines
            if isinstance(system_tpl, str):
                system_tpl = system_tpl.replace("\\n", "\n")
            if isinstance(user_tpl, str):
                user_tpl = user_tpl.replace("\\n", "\n")

            fmt_values = {
                "context_name": context_name,
                "field_name": field_name,
                "joined_hints": joined_hints,
            }
            try:
                user = user_tpl.format(**fmt_values)
            except Exception:
                user = default_user.format(**fmt_values)
            system = system_tpl
            content = self._get_ai().chat([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ])
            if content:
                self._set_field_text(field_name, content)
        except Exception as e:
            messagebox.showerror("AI Error", f"Failed to draft {field_name}: {e}")

    
    # ----------------------
    # AI Full Generators
    # ----------------------
    def _infer_theme(self, entity_type: str) -> str:
        """Infer a coarse genre/theme string from existing entities of given type."""
        try:
            wrapper = GenericModelWrapper(entity_type)
            items = wrapper.load_items()
        except Exception:
            items = []

        # Preferred explicit fields
        text_fields_priority = ["Genre", "Tags", "Summary", "Description", "Background", "Traits", "Role"]

        corpus = []
        for it in items or []:
            for f in text_fields_priority:
                v = it.get(f)
                if not v:
                    continue
                if isinstance(v, (list, tuple)):
                    corpus.append(" ".join(map(str, v)))
                else:
                    corpus.append(str(v))
        blob = ("\n".join(corpus)).lower()

        # Keyword buckets
        buckets = {
            "medieval fantasy": ["sword", "castle", "knight", "dragon", "elf", "dwarf", "orc", "medieval", "fantasy", "wizard", "mage", "kingdom"],
            "science fiction": ["spaceship", "alien", "planet", "space", "laser", "android", "cyber", "sci-fi", "sci fi", "future", "futuristic", "ai", "robot"],
            "modern": ["modern", "contemporary", "police", "detective", "city", "gun", "phone", "internet", "corporate"],
            "cyberpunk": ["cyberpunk", "neon", "megacorp", "augment", "hacker", "netrunner"],
            "post-apocalyptic": ["post-apocalyptic", "wasteland", "radiation", "zombie", "collapse", "ruins"],
            "horror": ["eldritch", "cthulhu", "haunted", "vampire", "werewolf", "ghost", "horror"],
            "urban fantasy": ["urban fantasy", "occult", "supernatural", "modern magic", "secret society"],
            "steampunk": ["steampunk", "goggles", "airship", "clockwork", "victorian", "steam"],
            "space opera": ["fleet", "galactic", "empire", "hyperspace", "warp", "starship"],
        }

        scores = {k: 0 for k in buckets}
        for theme, kws in buckets.items():
            for kw in kws:
                if kw in blob:
                    scores[theme] += 1

        # Also check for explicit mentions of the theme names
        for theme in list(buckets.keys()):
            if theme in blob:
                scores[theme] += 2

        best = max(scores.items(), key=lambda x: x[1]) if scores else ("", 0)
        if best[1] == 0:
            return "generic"
        return best[0]

    def ai_generate_full_scenario(self):
        try:
            theme = self._infer_theme("scenarios")

            # 1) Pick and apply linked entities first (so the AI can use them)
            npcs_list = load_npcs_list()
            creatures_list = load_creatures_list()
            places_list = load_places_list()
            factions_list = load_factions_list()
            objects_list = load_objects_list()

            selected_npcs = random.sample(npcs_list, 3) if len(npcs_list) >= 3 else npcs_list
            selected_places = random.sample(places_list, 3) if len(places_list) >= 3 else places_list
            selected_creatures = random.sample(creatures_list, 3) if len(creatures_list) >= 3 else creatures_list
            selected_factions = random.sample(factions_list, 2) if len(factions_list) >= 2 else factions_list
            selected_objects = random.sample(objects_list, 2) if len(objects_list) >= 2 else objects_list

            # Initial random picks are applied to UI lists

            # Save to self.item
            if selected_npcs is not None:
                self.item["NPCs"] = selected_npcs
            if selected_places is not None:
                self.item["Places"] = selected_places
            if selected_creatures is not None:
                self.item["Creatures"] = selected_creatures
            if selected_factions is not None:
                self.item["Factions"] = selected_factions
            if selected_objects is not None:
                self.item["Objects"] = selected_objects

            # Helper to shrink extra rows for a list of CTkEntry widgets
            def _shrink_widget_list(key, new_size):
                try:
                    lst = self.field_widgets.get(key, []) or []
                    if len(lst) > new_size:
                        for w in lst[new_size:]:
                            try:
                                w.master.destroy()
                            except Exception:
                                pass
                        lst = lst[:new_size]
                        self.field_widgets[key] = lst
                        # keep vars list in sync
                        vkey = f"{key}_vars"
                        vars_list = self.field_widgets.get(vkey, [])
                        if vars_list and len(vars_list) > new_size:
                            self.field_widgets[vkey] = vars_list[:new_size]
                except Exception:
                    pass

            # Update widgets for each list type
            # NPCs
            try:
                npc_widgets = self.field_widgets.get("NPCs", [])
                npc_vars = self.field_widgets.get("NPCs_vars", [])
                add_npc_combobox = self.field_widgets.get("NPCs_add_combobox")
                while len(npc_widgets) < len(selected_npcs) and callable(add_npc_combobox):
                    add_npc_combobox()
                    npc_widgets = self.field_widgets.get("NPCs", [])
                    npc_vars = self.field_widgets.get("NPCs_vars", [])
                _shrink_widget_list("NPCs", len(selected_npcs))
                npc_widgets = self.field_widgets.get("NPCs", [])
                npc_vars = self.field_widgets.get("NPCs_vars", [])
                for i in range(min(len(npc_widgets), len(selected_npcs))):
                    try:
                        npc_vars[i].set(selected_npcs[i])
                    except Exception:
                        widget = npc_widgets[i]
                        widget.configure(state="normal")
                        widget.delete(0, "end")
                        widget.insert(0, selected_npcs[i])
                        widget.configure(state="readonly")
            except Exception:
                pass
            # Creatures
            try:
                creature_widgets = self.field_widgets.get("Creatures", [])
                creature_vars = self.field_widgets.get("Creatures_vars", [])
                add_creatures_combobox = self.field_widgets.get("Creatures_add_combobox")
                while len(creature_widgets) < len(selected_creatures) and callable(add_creatures_combobox):
                    add_creatures_combobox()
                    creature_widgets = self.field_widgets.get("Creatures", [])
                    creature_vars = self.field_widgets.get("Creatures_vars", [])
                _shrink_widget_list("Creatures", len(selected_creatures))
                creature_widgets = self.field_widgets.get("Creatures", [])
                creature_vars = self.field_widgets.get("Creatures_vars", [])
                for i in range(min(len(creature_widgets), len(selected_creatures))):
                    try:
                        creature_vars[i].set(selected_creatures[i])
                    except Exception:
                        widget = creature_widgets[i]
                        widget.configure(state="normal")
                        widget.delete(0, "end")
                        widget.insert(0, selected_creatures[i])
                        widget.configure(state="readonly")
            except Exception:
                pass
            # Places
            try:
                place_widgets = self.field_widgets.get("Places", [])
                place_vars = self.field_widgets.get("Places_vars", [])
                add_place_combobox = self.field_widgets.get("Places_add_combobox")
                while len(place_widgets) < len(selected_places) and callable(add_place_combobox):
                    add_place_combobox()
                    place_widgets = self.field_widgets.get("Places", [])
                    place_vars = self.field_widgets.get("Places_vars", [])
                _shrink_widget_list("Places", len(selected_places))
                place_widgets = self.field_widgets.get("Places", [])
                place_vars = self.field_widgets.get("Places_vars", [])
                for i in range(min(len(place_widgets), len(selected_places))):
                    try:
                        place_vars[i].set(selected_places[i])
                    except Exception:
                        widget = place_widgets[i]
                        widget.configure(state="normal")
                        widget.delete(0, "end")
                        widget.insert(0, selected_places[i])
                        widget.configure(state="readonly")
            except Exception:
                pass
            # Factions
            try:
                faction_widgets = self.field_widgets.get("Factions", [])
                faction_vars = self.field_widgets.get("Factions_vars", [])
                add_faction_combobox = self.field_widgets.get("Factions_add_combobox")
                while len(faction_widgets) < len(selected_factions) and callable(add_faction_combobox):
                    add_faction_combobox()
                    faction_widgets = self.field_widgets.get("Factions", [])
                    faction_vars = self.field_widgets.get("Factions_vars", [])
                _shrink_widget_list("Factions", len(selected_factions))
                faction_widgets = self.field_widgets.get("Factions", [])
                faction_vars = self.field_widgets.get("Factions_vars", [])
                for i in range(min(len(faction_widgets), len(selected_factions))):
                    try:
                        faction_vars[i].set(selected_factions[i])
                    except Exception:
                        widget = faction_widgets[i]
                        widget.configure(state="normal")
                        widget.delete(0, "end")
                        widget.insert(0, selected_factions[i])
                        widget.configure(state="readonly")
            except Exception:
                pass
            # Objects
            try:
                object_widgets = self.field_widgets.get("Objects", [])
                object_vars = self.field_widgets.get("Objects_vars", [])
                add_object_combobox = self.field_widgets.get("Objects_add_combobox")
                while len(object_widgets) < len(selected_objects) and callable(add_object_combobox):
                    add_object_combobox()
                    object_widgets = self.field_widgets.get("Objects", [])
                    object_vars = self.field_widgets.get("Objects_vars", [])
                _shrink_widget_list("Objects", len(selected_objects))
                object_widgets = self.field_widgets.get("Objects", [])
                object_vars = self.field_widgets.get("Objects_vars", [])
                for i in range(min(len(object_widgets), len(selected_objects))):
                    try:
                        object_vars[i].set(selected_objects[i])
                    except Exception:
                        widget = object_widgets[i]
                        widget.configure(state="normal")
                        widget.delete(0, "end")
                        widget.insert(0, selected_objects[i])
                        widget.configure(state="readonly")
            except Exception:
                pass

            # 2) Read back values actually present in the UI, to ensure prompt matches what user sees
            def _read_list_from_widgets(name):
                try:
                    widgets = self.field_widgets.get(name, [])
                    vals = []
                    for w in widgets:
                        try:
                            v = w.get()
                        except Exception:
                            v = None
                        if v:
                            vals.append(v)
                    return vals
                except Exception:
                    return []

            # Ensure UI has applied changes, then read exact values from widgets
            try:
                self.update_idletasks()
            except Exception:
                pass
            selected_npcs = _read_list_from_widgets("NPCs")
            selected_places = _read_list_from_widgets("Places")
            selected_creatures = _read_list_from_widgets("Creatures")
            selected_factions = _read_list_from_widgets("Factions")
            selected_objects = _read_list_from_widgets("Objects")
            # At this point, values reflect the on-screen selections

            # 3) Build a context block describing these selected entities for coherence
            def _plain_text(val):
                try:
                    if isinstance(val, dict):
                        return str(val.get("text", ""))
                    return str(val)
                except Exception:
                    return ""

            def _summarize(record, wanted_fields):
                parts = []
                for f in wanted_fields:
                    v = record.get(f)
                    if not v:
                        continue
                    s = _plain_text(v).strip()
                    if not s:
                        continue
                    parts.append(f"{f}: {s[:220]}")
                return ", ".join(parts) or "(no details)"

            def _index_items(entity_type):
                try:
                    items = GenericModelWrapper(entity_type).load_items()
                except Exception:
                    items = []
                by_name = {}
                for it in items:
                    nm = it.get("Name") or it.get("Title")
                    if nm:
                        by_name[str(nm)] = it
                return by_name

            ctx_lines = []
            # Index maps for lookups
            idx_npcs = _index_items("npcs")
            idx_places = _index_items("places")
            idx_creatures = _index_items("creatures")
            idx_factions = _index_items("factions")
            idx_objects = _index_items("objects")

            if selected_npcs:
                ctx_lines.append("NPCs:")
                for n in selected_npcs:
                    rec = idx_npcs.get(n, {})
                    ctx_lines.append(f"- {n}: " + _summarize(rec, ["Role","Description","Background","Traits","Motivation","Personality","RoleplayingCues"]))
            if selected_places:
                ctx_lines.append("Places:")
                for n in selected_places:
                    rec = idx_places.get(n, {})
                    ctx_lines.append(f"- {n}: " + _summarize(rec, ["Description","Secrets"]))
            if selected_creatures:
                ctx_lines.append("Creatures:")
                for n in selected_creatures:
                    rec = idx_creatures.get(n, {})
                    ctx_lines.append(f"- {n}: " + _summarize(rec, ["Type","Description","Powers","Weakness","Background"]))
            if selected_factions:
                ctx_lines.append("Factions:")
                for n in selected_factions:
                    rec = idx_factions.get(n, {})
                    ctx_lines.append(f"- {n}: " + _summarize(rec, ["Description","Secrets"]))
            if selected_objects:
                ctx_lines.append("Objects:")
                for n in selected_objects:
                    rec = idx_objects.get(n, {})
                    ctx_lines.append(f"- {n}: " + _summarize(rec, ["Description","Secrets"]))
            entities_context = "\n".join(ctx_lines)

            # 4) Gather sample titles/summaries (optional flavor only)
            try:
                samples = GenericModelWrapper("scenarios").load_items()
            except Exception:
                samples = []
            examples = []
            for it in samples[:5]:
                t = it.get("Title") or it.get("Name")
                s = it.get("Summary") or it.get("Description")
                if t:
                    examples.append(f"- {t}: {str(s)[:140] if s else ''}")
            examples_text = "\n".join(examples)

            system = (
                "You are an RPG scenario generator. Produce concise, game-ready content. "
                "Write evocative but brief prose. Return ONLY compact JSON without code fences."
            )
            user = (
                f"Theme: {theme}\n"
                f"Use EXACTLY these selected entities (names must match; do not rename or invent new proper nouns):\n{', '.join(selected_npcs or [])} | {', '.join(selected_places or [])} | {', '.join(selected_creatures or [])} | {', '.join(selected_factions or [])} | {', '.join(selected_objects or [])}\n\n"
                f"Entity details for coherence:\n{entities_context}\n\n"
                f"Existing examples (optional):\n{examples_text}\n\n"
                "Task: Generate a scenario object with fields:\n"
                "{\n"
                "  \"Title\": string,\n"
                "  \"Summary\": string (1-3 short paragraphs, Markdown allowed),\n"
                "  \"Secrets\": string (a single compact secret),\n"
                "  \"Scenes\": [string, ...] (3-5 concise scene beats; reference the selected entities by NAME)\n"
                "}\n"
                "Constraints: Integrate the selected entities coherently. No extra keys. No code blocks. Keep within ~600 words."
            )
            # Build prompt and call AI
            content = self._get_ai().chat([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ])
            data = None
            try:
                data = LocalAIClient._parse_json_safe(content)
            except Exception:
                # If not JSON, fallback: put entire text into Summary
                data = {"Title": "Generated Scenario", "Summary": content, "Secrets": "", "Scenes": []}

            # Apply fields
            title = data.get("Title") or self.item.get("Title")
            if title:
                self._set_field_text("Title", str(title))

            summary = data.get("Summary")
            if summary:
                self._set_field_text("Summary", str(summary))

            secrets = data.get("Secrets")
            if secrets:
                self._set_field_text("Secrets", str(secrets))

            scenes = data.get("Scenes") or []
            if isinstance(scenes, (list, tuple)):
                editors = self.field_widgets.get("Scenes", [])
                add_scene = self.field_widgets.get("Scenes_add_scene")
                # Grow to needed count
                while len(editors) < len(scenes) and callable(add_scene):
                    add_scene("")
                    editors = self.field_widgets.get("Scenes", [])
                # Shrink extra
                if len(editors) > len(scenes):
                    for ed in editors[len(scenes):]:
                        try:
                            ed.master.destroy()
                        except Exception:
                            pass
                    editors = editors[:len(scenes)]
                    self.field_widgets["Scenes"] = editors
                # Populate content
                for ed, sc in zip(editors, scenes):
                    try:
                        ed.load_text_data(ai_text_to_rtf_json(str(sc)))
                    except Exception:
                        ed.text_widget.delete("1.0", "end")
                        ed.text_widget.insert("1.0", str(sc))

            # End-of-function: UI lists remain as displayed

        except Exception as e:
            messagebox.showerror("AI Error", f"Failed to generate scenario: {e}")

    def ai_generate_full_npc(self):
        try:
            theme = self._infer_theme("npcs")
            # Gather sample names/roles
            try:
                samples = GenericModelWrapper("npcs").load_items()
            except Exception:
                samples = []
            examples = []
            for it in samples[:8]:
                n = it.get("Name")
                r = it.get("Role") or it.get("Traits")
                if n:
                    examples.append(f"- {n}{' ('+r+')' if r else ''}")
            examples_text = "\n".join(examples)

            system = (
                "You are an RPG NPC generator. Produce concise, game-usable material. "
                "Return ONLY compact JSON without code fences."
            )
            user = (
                f"Theme: {theme}\n"
                f"Existing NPCs (optional):\n{examples_text}\n\n"
                "Task: Generate an NPC object with fields:\n"
                "{\n"
                "  \"Name\": string,\n"
                "  \"Role\": string,\n"
                "  \"Description\": string (1 short paragraph, Markdown allowed),\n"
                "  \"Secret\": string,\n"
                "  \"Quote\": string,\n"
                "  \"RoleplayingCues\": string,\n"
                "  \"Personality\": string,\n"
                "  \"Motivation\": string,\n"
                "  \"Background\": string,\n"
                "  \"Traits\": string,\n"
                "  \"Genre\": string\n"
                "}\n"
                "Constraints: No extra keys. No code blocks. Keep within ~400 words."
            )
            # Build prompt and call AI
            content = self._get_ai().chat([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ])
            try:
                data = LocalAIClient._parse_json_safe(content)
            except Exception:
                data = {"Name": "Generated NPC", "Description": content, "Genre": theme}

            # Apply simple text fields
            for key in ("Name", "Role", "Quote", "Genre"):
                val = data.get(key)
                if val:
                    self._set_field_text(key, str(val))

            # Apply longtext fields
            for key in ("Description", "Secret", "RoleplayingCues", "Personality", "Motivation", "Background", "Traits"):
                val = data.get(key)
                if val:
                    self._set_field_text(key, str(val))

        except Exception as e:
            messagebox.showerror("AI Error", f"Failed to generate NPC: {e}")

    def ai_generate_full_creature(self):
        try:
            # Prefer explicit Genre from existing creatures; fallback to inferred theme
            try:
                existing = GenericModelWrapper("creatures").load_items() or []
            except Exception:
                existing = []

            genre_counts = {}
            for it in existing:
                g = (it.get("Genre") or "").strip()
                if not g:
                    continue
                genre_counts[g] = genre_counts.get(g, 0) + 1

            if genre_counts:
                # Pick the most common explicit Genre
                theme = max(genre_counts.items(), key=lambda kv: kv[1])[0]
            else:
                theme = self._infer_theme("creatures")

            # Gather sample names/types for context
            samples = existing
            examples = []
            for it in samples[:8]:
                n = it.get("Name")
                t = it.get("Type")
                if n:
                    examples.append(f"- {n}{' ('+t+')' if t else ''}")
            examples_text = "\n".join(examples)

            # Extract representative Stats examples to enforce format consistency
            stats_examples = []
            for it in existing:
                s = it.get("Stats")
                if not s:
                    continue
                if isinstance(s, dict):
                    s = s.get("text", "")
                s = str(s).strip()
                if not s:
                    continue
                if 20 <= len(s) <= 1200:
                    stats_examples.append(s)
                if len(stats_examples) >= 3:
                    break
            stats_examples_text = "\n\n---\n\n".join(stats_examples) if stats_examples else ""
            stats_block = (
                f"Stats Format Examples (match structure and labels):\n---\n{stats_examples_text}\n---\n\n"
                if stats_examples_text else ""
            )

            system = (
                "You are an RPG creature/monster generator. Produce concise, game-usable material. "
                "Return ONLY compact JSON without code fences."
            )
            user = (
                f"Theme/Genre: {theme}\n"
                f"Existing Creatures (optional):\n{examples_text}\n\n"
                f"{stats_block}"
                "Task: Generate a Creature object with fields:\n"
                "{\n"
                "  \"Name\": string,\n"
                "  \"Type\": string,\n"
                "  \"Description\": string (1 short paragraph, Markdown allowed),\n"
                "  \"Weakness\": string,\n"
                "  \"Powers\": string,\n"
                "  \"Stats\": string (follow the above template),\n"
                "  \"Background\": string,\n"
                "  \"Genre\": string\n"
                "}\n"
                "Constraints: No extra keys. No code blocks. Keep within ~300-400 words."
            )
            # Build prompt and call AI
            content = self._get_ai().chat([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ])
            try:
                data = LocalAIClient._parse_json_safe(content)
            except Exception:
                data = {"Name": "Generated Creature", "Description": content, "Genre": theme}

            # Ensure Genre coherence if model omitted it
            if not data.get("Genre"):
                data["Genre"] = theme

            # Apply simple text fields
            for key in ("Name", "Type", "Genre"):
                val = data.get(key)
                if val:
                    self._set_field_text(key, str(val))

            # Apply longtext fields
            for key in ("Description", "Weakness", "Powers", "Stats", "Background"):
                val = data.get(key)
                if val:
                    self._set_field_text(key, str(val))

        except Exception as e:
            messagebox.showerror("AI Error", f"Failed to generate Creature: {e}")
