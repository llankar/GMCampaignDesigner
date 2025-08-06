import json
import os
import shutil
import zipfile
from tkinter import filedialog, messagebox
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.config_helper import ConfigHelper

# Define the name for the temporary portraits folder and the relative folder name in the ZIP.
TEMP_PORTRAIT_FOLDER = "temp_portraits"
RELATIVE_PORTRAIT_FOLDER = "portraits"

def preview_and_export_foundry(self):
    """
    Exports scenarios, NPCs, and places into a ZIP archive that contains a JSON file formatted
    for Foundry VTT import and a portraits folder with all the portrait image files.
    
    Each scenario becomes a scene with embedded title, summary, secrets, NPC tokens (with preset positions and color-coded faction borders),
    and clickable markers for linked place scenes. Separate place scenes are also exported.
    
    The portrait fields in the export JSON are set to relative paths like "portraits/filename.png".
    """
    # Load scenarios, NPCs, and places using the existing GenericModelWrapper instances.
    scenario_wrapper = GenericModelWrapper("scenarios")
    scenarios = scenario_wrapper.load_items()
    if not scenarios:
        messagebox.showwarning("No Scenarios", "No scenarios available for export.")
        return

    npc_list = self.npc_wrapper.load_items()
    place_items = {place["Name"]: place for place in self.place_wrapper.load_items()}

    # Build a dictionary for NPCs by name.
    npc_items = {}
    for npc in npc_list:
        npc_items[npc["Name"]] = npc

    # Hard-coded faction color mapping; adjust as needed.
    faction_color_map = {
        "Winter Court": "#00aaff",
        "White Council": "#ffffff",
        "Denarians": "#ff0000",
        "Summer Court": "#ffdd00",
        "Black Court": "#333333",
        "Mortals": "#00ff00",
        "Red Court Remnants": "#ff007f",
        "Outsiders": "#ff00ff",
        "Knights of the Cross": "#cccccc",
        "Spirits of Chicago": "#999999",
        "Wyldfae": "#ff99cc",
        "Spirits": "#aaaaaa"
    }

    # Prepare a temporary folder for portraits.
    os.makedirs(TEMP_PORTRAIT_FOLDER, exist_ok=True)

    # Process NPCs to update their portrait paths:
    for npc in npc_list:
        portrait = npc.get("Portrait", "")
        if portrait:
            # Normalize path separators.
            portrait = portrait.replace("\\", "/")
            if not os.path.isabs(portrait):
                abs_portrait = os.path.join(ConfigHelper.get_campaign_dir(), portrait)
                if os.path.exists(abs_portrait):
                    portrait = abs_portrait
            file_name = os.path.basename(portrait)
            # Copy the portrait file to the temporary folder.
            # Note: You may need to adjust the source path if the portraits are not found relative to the working directory.
            try:
                shutil.copy(portrait, os.path.join(TEMP_PORTRAIT_FOLDER, file_name))
            except Exception as e:
                messagebox.showwarning("Portrait Copy Warning", f"Could not copy portrait for {npc.get('Name', 'Unknown')}: {e}")
            # Set the portrait field to the relative path (inside the ZIP archive).
            npc["Portrait"] = f"{RELATIVE_PORTRAIT_FOLDER}/{file_name}"

    # Build Foundry scenes from scenarios.
    foundry_scenes = []
    for scenario in scenarios:
        scene = {}
        scene["title"] = scenario.get("Title", "Untitled Scenario")
        
        # Preserve rich text formatting by extracting the 'text' field if available.
        summary = scenario.get("Summary", "")
        scene["summary"] = summary.get("text", "") if isinstance(summary, dict) else summary

        secrets = scenario.get("Secrets", "")
        scene["secrets"] = secrets.get("text", "") if isinstance(secrets, dict) else secrets

        # Create NPC tokens for the scenario.
        tokens = []
        for idx, npc_name in enumerate(scenario.get("NPCs", [])):
            npc = npc_items.get(npc_name)
            if npc:
                token = {}
                token["name"] = npc.get("Name", "Unnamed NPC")
                token["role"] = npc.get("Role", "")
                desc = npc.get("Description", "")
                token["description"] = desc.get("text", "") if isinstance(desc, dict) else desc
                token["portrait"] = npc.get("Portrait", "")  # Already updated to relative path
                # Place tokens vertically in a readable order.
                token["x"] = 100
                token["y"] = 100 * (idx + 1)
                # Add faction info and a border color based on the first faction.
                factions_list = npc.get("Factions", [])
                token["factions"] = factions_list
                token["borderColor"] = faction_color_map.get(factions_list[0], "#000000") if factions_list else "#000000"
                tokens.append(token)
        scene["tokens"] = tokens

        # Create clickable markers for places referenced in the scenario.
        markers = []
        for idx, place_name in enumerate(scenario.get("Places", [])):
            place = place_items.get(place_name)
            if place:
                marker = {}
                marker["name"] = place.get("Name", "Unnamed Place")
                marker["description"] = place.get("Description", "")
                # Use a default icon (empty string can be replaced with an actual icon path if desired)
                marker["icon"] = ""
                # Arrange markers horizontally.
                marker["x"] = 100 * (idx + 1)
                marker["y"] = 500  # Fixed y-position for markers
                # Use the place name as the target scene reference.
                marker["targetScene"] = marker["name"]
                markers.append(marker)
        scene["markers"] = markers

        foundry_scenes.append(scene)

    # Export separate place scenes.
    foundry_places = []
    for place in self.place_wrapper.load_items():
        place_scene = {}
        place_scene["title"] = place.get("Name", "Unnamed Place")
        place_scene["description"] = place.get("Description", "")
        # Optionally add an image field if available.
        place_scene["image"] = ""
        foundry_places.append(place_scene)

    # Combine into the final export data structure.
    export_data = {
        "scenes": foundry_scenes,
        "places": foundry_places
    }

    # Ask the user for a file path to save the ZIP archive.
    zip_file_path = filedialog.asksaveasfilename(
        defaultextension=".zip",
        filetypes=[("ZIP Files", "*.zip"), ("All Files", "*.*")],
        title="Save Foundry Export ZIP"
    )
    if not zip_file_path:
        return

    # Write the export JSON to a temporary file.
    temp_json_file = "foundry_export.json"
    with open(temp_json_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)

    # Create a ZIP archive containing the JSON file and the portraits folder.
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add the JSON file at the root of the ZIP.
        zipf.write(temp_json_file, arcname=os.path.basename(temp_json_file))
        # Add the contents of the temporary portraits folder under the "portraits/" directory in the ZIP.
        for root_dir, subdirs, files in os.walk(TEMP_PORTRAIT_FOLDER):
            for file in files:
                file_path = os.path.join(root_dir, file)
                # Create an archive name that places the file in the "portraits" folder.
                arcname = os.path.join(RELATIVE_PORTRAIT_FOLDER, file)
                zipf.write(file_path, arcname=arcname)

    # Clean up the temporary folder and JSON file.
    shutil.rmtree(TEMP_PORTRAIT_FOLDER)
    os.remove(temp_json_file)

    messagebox.showinfo("Export Successful", f"Foundry export ZIP created and saved to:\n{zip_file_path}")
