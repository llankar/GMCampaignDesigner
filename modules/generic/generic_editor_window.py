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
from tkinter import filedialog,  messagebox
from modules.helpers.swarmui_helper import get_available_models
from modules.helpers.config_helper import ConfigHelper
from modules.generic.generic_model_wrapper import GenericModelWrapper
import tkinter as tk
import random
from modules.helpers.text_helpers import format_longtext
import json

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
            elif field["name"] in ["NPCs", "Places", "Factions", "Objects", "Creatures", "PCs"]:
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

        # extra buttons for Summary/Secrets…
        if field["name"] == "Summary":
            ctk.CTkButton(
                self.scroll_frame, text="Random Summary",
                command=self.generate_scenario_description
            ).pack(pady=5)
        if field["name"] == "Secrets":
            ctk.CTkButton(
                self.scroll_frame, text="Generate Secret",
                command=self.generate_secret_text
            ).pack(pady=5)

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
        if field["name"] == "PCs":
            options_list = load_pcs_list()
            label_text = "Add PC"
        elif field["name"] == "NPCs":
            options_list = load_npcs_list()
            label_text = "Add NPC"
        elif field["name"] == "Places":
            options_list = load_places_list()
            label_text = "Add Place"
        elif field["name"] == "Factions":
            options_list = load_factions_list()
            label_text = "Add Faction"
        elif field["name"] == "Objects":
            options_list = load_objects_list()
            label_text = "Add Object"
        elif field["name"] == "Creatures":
            options_list = load_creatures_list()
            label_text = "Add Creature"
        else:
            options_list = []
            label_text = f"Add {field['name']}"

        initial_values = self.item.get(field["name"]) or []

        def remove_this(row, entry_widget):
            row.destroy()
            combobox_list.remove(entry_widget)

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

        for value in initial_values:
            add_combobox(value)

        add_button = ctk.CTkButton(container, text=label_text, command=add_combobox)
        add_button.pack(anchor="w", pady=2)

        # Save widgets clearly
        self.field_widgets[field["name"]] = combobox_list
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

        if self.model_wrapper.entity_type== 'npcs':
            ctk.CTkButton(action_bar, text='Generate NPC', command=self.generate_npc).pack(side='left', padx=5)
    
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
            elif field["name"] in ["Places", "NPCs", "Factions", "Objects", "Creatures", "PCs"]:	
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
        ctk.CTkButton(button_frame, text="Create Portrait with description", command=self.create_portrait_with_swarmui).pack(side="left", padx=5)

        self.field_widgets[field["name"]] = self.portrait_path
    
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
        self.field_widgets[field["name"]] = self.image_path

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
                "images": 1,  # Only one portrait needed
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

            # Step 3: Download the first generated image
            image_url = f"{SWARM_API_URL}/{images[0]}"
            downloaded_image = requests.get(image_url)
            if downloaded_image.status_code != 200:
                messagebox.showerror("Error", "Failed to download the generated image.")
                return

            # Step 4: Save the image locally and update the NPC's Portrait field
            output_filename = f"{npc_name.replace(' ', '_')}_portrait.png"
            with open(output_filename, "wb") as f:
                f.write(downloaded_image.content)

            # Associate the generated portrait with the NPC data.
            self.portrait_path = self.copy_and_resize_portrait(output_filename)
            self.portrait_label.configure(text=os.path.basename(self.portrait_path))
            #copy the outputfilename file to the assets/generated folder
            GENERATED_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "generated")
            os.makedirs(GENERATED_FOLDER, exist_ok=True)
            shutil.copy(output_filename, os.path.join(GENERATED_FOLDER, output_filename))
            os.remove(output_filename)  # Delete the original image file
            # messagebox.showinfo("Success", f"Portrait saved as {output_filename} and associated with the NPC.")

            # Optional: Update the portrait display in the UI.
            # For example, if you have a portrait label (self.portrait_label), reload the image:
            # from PIL import ImageTk, Image
            # img = Image.open(output_filename).resize((64, 64))
            # self.portrait_image = ctk.CTkImage(light_image=img, size=(64, 64))
            # self.portrait_label.configure(image=self.portrait_image, text="")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

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
    
    