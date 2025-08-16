import customtkinter as ctk
import tkinter as tk
import os
import json
from tkinter import filedialog, messagebox
from PIL import Image
from functools import partial
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.text_helpers import format_multiline_text
from customtkinter import CTkLabel, CTkImage
from modules.generic.entity_detail_factory import create_entity_detail_frame
from modules.npcs.npc_graph_editor import NPCGraphEditor
from modules.pcs.pc_graph_editor import PCGraphEditor
from modules.scenarios.scenario_graph_editor import ScenarioGraphEditor
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.config_helper import ConfigHelper
import random

PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
MAX_PORTRAIT_SIZE = (64, 64)  # Thumbnail size for lists

class GMScreenView(ctk.CTkFrame):
    def __init__(self, master, scenario_item, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        # Persistent cache for portrait images
        self.portrait_images = {}
        self.scenario = scenario_item

        # Load your detach and reattach icon files (adjust file paths and sizes as needed)
        self.detach_icon = CTkImage(light_image=Image.open("assets/detach_icon.png"),
                                    dark_image=Image.open("assets/detach_icon.png"),
                                    size=(20, 20))
        self.reattach_icon = CTkImage(light_image=Image.open("assets/reattach_icon.png"),
                                    dark_image=Image.open("assets/reattach_icon.png"),
                                    size=(20, 20))

        self.wrappers = {
            "Scenarios": GenericModelWrapper("scenarios"),
            "Places": GenericModelWrapper("places"),
            "NPCs": GenericModelWrapper("npcs"),
            "PCs": GenericModelWrapper("pcs"),
            "Factions": GenericModelWrapper("factions"),
            "Creatures": GenericModelWrapper("Creatures"),
            "Clues": GenericModelWrapper("Clues"),
            "Informations": GenericModelWrapper("informations"),
            "Objects": GenericModelWrapper("Objects")
        }

        self.templates = {
            "Scenarios": self.load_template("scenarios/scenarios_template.json"),
            "Places": self.load_template("places/places_template.json"),
            "NPCs": self.load_template("npcs/npcs_template.json"),
            "PCs": self.load_template("pcs/pcs_template.json"),
            "Factions": self.load_template("factions/factions_template.json"),
            "Creatures": self.load_template("creatures/creatures_template.json"),
            "Clues": self.load_template("clues/clues_template.json"),
            "Informations": self.load_template("informations/informations_template.json")
        }

        self.tabs = {}
        self.current_tab = None
        self.tab_order = []                  # ← new: keeps track of left-to-right order
        self.dragging = None                 # ← new: holds (tab_name, start_x)

        # A container to hold both the scrollable tab area and the plus button
        self.tab_bar_container = ctk.CTkFrame(self, height=60)
        self.tab_bar_container.pack(side="top", fill="x")

        # The scrollable canvas for tabs
        self.tab_bar_canvas = ctk.CTkCanvas(self.tab_bar_container, height=40, highlightthickness=0, bg="#2B2B2B")
        self.tab_bar_canvas.pack(side="top", fill="x", expand=True)

        # Horizontal scrollbar at the bottom
        self.h_scrollbar = ctk.CTkScrollbar(
            self.tab_bar_container,
            orientation="horizontal",
            command=self.tab_bar_canvas.xview
        )
        self.h_scrollbar.pack(side="bottom", fill="x")

        # The actual frame that holds the tab buttons
        self.tab_bar = ctk.CTkFrame(self.tab_bar_canvas, height=40)
        self.tab_bar_id = self.tab_bar_canvas.create_window((0, 0), window=self.tab_bar, anchor="nw")

        # Connect the scrollbar to the canvas
        self.tab_bar_canvas.configure(xscrollcommand=self.h_scrollbar.set)

        # Update the scroll region when the tab bar resizes
        self.tab_bar.bind("<Configure>", lambda e: self.tab_bar_canvas.configure(
            scrollregion=self.tab_bar_canvas.bbox("all")))

        # The plus button stays on the right side of the container
        self.add_button = ctk.CTkButton(
            self.tab_bar,
            text="+",
            width=40,
            command=self.add_new_tab
        )
        
        self.random_button = ctk.CTkButton(
            self.tab_bar,
            text="?",
            width=40,
            command=self._add_random_entity
        )
        self.random_button.pack(side="left", padx=2, pady=5)
        self.add_button.pack(side="left", padx=2, pady=5)
        self.random_button.pack(side="left", padx=2, pady=5)

        # Main content area for scenario details
        self.content_area = ctk.CTkScrollableFrame(self)
        self.content_area.pack(fill="both", expand=True)
    
        # Example usage: create the first tab from the scenario_item
        scenario_name = scenario_item.get("Title", "Unnamed Scenario")
        frame = create_entity_detail_frame("Scenarios", scenario_item, master=self.content_area, open_entity_callback=self.open_entity_tab)
        
        # Make sure the frame can get focus so the binding works
        self.focus_set()
        self.add_tab(
            scenario_name,
            frame,
            content_factory=lambda master: create_entity_detail_frame("Scenarios", scenario_item, master=master, open_entity_callback=self.open_entity_tab)
        )
        
    
    def open_global_search(self, event=None):
        # Create popup
        popup = ctk.CTkToplevel(self)
        popup.title("Search Entities")
        popup.geometry("400x300")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()

        # 1) Search entry
        entry = ctk.CTkEntry(popup, placeholder_text="Type to search…")
        entry.pack(fill="x", padx=10, pady=(10, 5))
        # focus once window is up
        popup.after(10, lambda: entry.focus_force())

        # 2) Theme colors
        raw_bg    = entry.cget("fg_color")
        raw_txt   = entry.cget("text_color")
        appearance = ctk.get_appearance_mode()    # "Dark" or "Light"
        idx       = 1 if appearance == "Dark" else 0
        bg_list   = raw_bg  if isinstance(raw_bg, (list, tuple))  else raw_bg.split()
        txt_list  = raw_txt if isinstance(raw_txt,(list, tuple)) else raw_txt.split()
        bg_color    = bg_list[idx]
        text_color  = txt_list[idx]
        sel_bg      = "#3a3a3a" if appearance == "Dark" else "#d9d9d9"

        # 3) Listbox for results
        listbox = tk.Listbox(
            popup,
            activestyle="none",
            bg=bg_color,
            fg=text_color,
            highlightbackground=bg_color,
            selectbackground=sel_bg,
            selectforeground=text_color
        )
        listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 4) Navigation: ↓ from entry dives into list
        def dive_into_list(evt):
            if listbox.size() > 0:
                listbox.selection_clear(0, "end")
                listbox.selection_set(0)
                listbox.activate(0)
            listbox.focus_set()
            return "break"
        entry.bind("<Down>", dive_into_list)

        # 5) Prepare storage for (type, name)
        search_map = []

        # 6) Populate & auto-select first
        def populate(initial=False, query=""):
            listbox.delete(0, "end")
            search_map.clear()
            for entity_type, wrapper in self.wrappers.items():
                items = wrapper.load_items()
                key = "Title" if entity_type in ("Scenarios", "Informations") else "Name"
                for item in items:
                    name = item.get(key, "")
                    if initial or query in name.lower():
                        display = f"{entity_type[:-1]}: {name}"
                        listbox.insert("end", display)
                        search_map.append((entity_type, name))
            # auto-select first if present
            if listbox.size() > 0:
                listbox.selection_clear(0, "end")
                listbox.selection_set(0)
                listbox.activate(0)
        # initial fill
        populate(initial=True)

        # 7) Filter on typing
        def on_search(evt):
            q = entry.get().strip().lower()
            populate(initial=False, query=q)
        entry.bind("<KeyRelease>", on_search)

        # 8) Selection handler
        def on_select(evt=None):
            if not search_map:
                return
            idx = listbox.curselection()[0]
            entity_type, name = search_map[idx]
            self.open_entity_tab(entity_type, name)
            popup.destroy()

        # 9) Bind Enter to select from either widget
        entry.bind("<Return>", lambda e: on_select())
        listbox.bind("<Return>", lambda e: on_select())

        # 10) Double-click also selects
        listbox.bind("<Double-Button-1>", on_select)
        
    def load_template(self, filename):
        base_path = os.path.dirname(__file__)
        template_path = os.path.join(base_path, "..", filename)
        with open(template_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def add_tab(self, name, content_frame, content_factory=None):
        tab_frame = ctk.CTkFrame(self.tab_bar)
        tab_frame.pack(side="left", padx=2, pady=5)

        tab_button = ctk.CTkButton(tab_frame, text=name, width=150,
                                   command=lambda: self.show_tab(name))
        tab_button.pack(side="left")

        close_button = ctk.CTkButton(tab_frame, text="❌", width=30,
                                     command=lambda: self.close_tab(name))
        close_button.pack(side="left")

        # Create the detach button and store its reference.
        detach_button = ctk.CTkButton(tab_frame,image=self.detach_icon, text="", width=50,
                                      command=lambda: self.toggle_detach_tab(name))
        detach_button.pack(side="left")

        portrait_label = getattr(content_frame, "portrait_label", None)
        self.tabs[name] = {
            "button_frame": tab_frame,
            "content_frame": content_frame,
            "button": tab_button,
            "detach_button": detach_button,
            "detached": False,
            "window": None,
            "portrait_label": portrait_label,
            "factory": content_factory
        }

        content_frame.pack_forget()
        self.show_tab(name)
        # 1) append to order list
        self.tab_order.append(name)

        # collect ALL the widgets you need to drag
        draggable_widgets = (
            tab_frame,
            tab_button,
            close_button,
            detach_button
        )

        for w in draggable_widgets:
            w.bind("<Button-1>",        lambda e, n=name: self._on_tab_press(e, n))
            w.bind("<B1-Motion>",       lambda e, n=name: self._on_tab_motion(e, n))
            w.bind("<ButtonRelease-1>", lambda e, n=name: self._on_tab_release(e, n))

        self.reposition_add_button()

    def _on_tab_press(self, event, name):
        # 1) Make sure winfo_x/y are up-to-date
        self.tab_bar.update_idletasks()

        # 2) Start drag state
        self.dragging = {"name": name, "start_x": event.x_root}

        # 3) Convert every tab HEADER to place() at its current pixel pos
        for tn in self.tab_order:
            f = self.tabs[tn]["button_frame"]
            fx, fy = f.winfo_x(), f.winfo_y()
            f.pack_forget()
            f.place(in_=self.tab_bar, x=fx, y=fy)

        # 4) Hide the “+” and "?" so it doesn’t get in the way
        self.add_button.pack_forget()
        self.random_button.pack_forget()
        
        # 5) Lift the one we’re dragging above the others
        self.tabs[name]["button_frame"].lift()

    def _on_tab_motion(self, event, name):
        frame = self.tabs[name]["button_frame"]
        rel_x = event.x_root - self.tab_bar.winfo_rootx() - frame.winfo_width() // 2

        # move the dragged tab along with the cursor
        frame.place_configure(x=rel_x)

        # same midpoint-swap logic as before…
        for idx, other in enumerate(self.tab_order):
            if other == name: continue
            of = self.tabs[other]["button_frame"]
            mid = of.winfo_x() + of.winfo_width() // 2

            if rel_x < mid and self.tab_order.index(name) > idx:
                self._trigger_shift(other, dx=frame.winfo_width())
                self._swap_order(name, other)
                break
            if rel_x > mid and self.tab_order.index(name) < idx:
                self._trigger_shift(other, dx=-frame.winfo_width())
                self._swap_order(name, other)
                break
                
    def _trigger_shift(self, other_name, dx):
        oframe = self.tabs[other_name]["button_frame"]
        start = oframe.winfo_x()
        target = start + dx
        self._animate_shift([oframe], [dx])

    def _animate_shift(self, frames, deltas, step=0):
        if step >= 10: return
        for frame, delta in zip(frames, deltas):
            cur = frame.winfo_x()
            frame.place_configure(x=cur + delta/10)
        self.after(20, lambda: self._animate_shift(frames, deltas, step+1))
    
    def _swap_order(self, name, other):
        old = self.tab_order.index(name)
        new = self.tab_order.index(other)
        self.tab_order.pop(old)
        self.tab_order.insert(new, name)

    def _on_tab_release(self, event, name):
        # snap all headers back into pack()
        for tn in self.tab_order:
            f = self.tabs[tn]["button_frame"]
            f.place_forget()
            f.pack(side="left", padx=2, pady=5)

        # **use your helper** to put “+” back in line
        self.reposition_add_button()
        self.tab_bar_canvas.configure(
            scrollregion=self.tab_bar_canvas.bbox("all")
        )
        self.dragging = None

    def toggle_detach_tab(self, name):
        if self.tabs[name]["detached"]:
            self.reattach_tab(name)
            # After reattaching, show the detach icon
            self.tabs[name]["detach_button"].configure(image=self.detach_icon)
        else:
            self.detach_tab(name)
            # When detached, change to the reattach icon
            self.tabs[name]["detach_button"].configure(image=self.reattach_icon)

    def detach_tab(self, name):
        print(f"[DETACH] Start detaching tab: {name}")
        if self.tabs[name].get("detached", False):
            print(f"[DETACH] Tab '{name}' is already detached.")
            return

        # Hide the current content
        old_frame = self.tabs[name]["content_frame"]
        old_frame.pack_forget()

        # Create the Toplevel (hidden briefly)
        detached_window = ctk.CTkToplevel(self)
        detached_window.withdraw()
        detached_window.title(name)
        detached_window.lift()
        detached_window.attributes("-topmost", True)
        detached_window.protocol("WM_DELETE_WINDOW", lambda: None)

        # Build the new content frame
        if name.startswith("Note") and hasattr(old_frame, "text_box"):
            txt = old_frame.text_box.get("1.0", "end-1c")
            new_frame = self.create_note_frame(detached_window, initial_text=txt)
        else:
            factory = self.tabs[name].get("factory")
            new_frame = old_frame if factory is None else factory(detached_window)

        # Pack so children are laid out
        new_frame.pack(fill="both", expand=True)
        new_frame.update_idletasks()

        # If there's a graph editor, restore its state right away
        if hasattr(old_frame, "graph_editor") and hasattr(old_frame.graph_editor, "get_state"):
            state = old_frame.graph_editor.get_state()
            if state and hasattr(new_frame, "graph_editor") and hasattr(new_frame.graph_editor, "set_state"):
                ge = new_frame.graph_editor
                # draw full-size background & links
                ce = ge.canvas
                ce.update_idletasks()
                cfg = type("E", (), {
                    "width":  ce.winfo_width(),
                    "height": ce.winfo_height()
                })()
                ge._on_canvas_configure(cfg)
                ge.set_state(state)

        # Hard-code size for all graph windows
        GRAPH_W, GRAPH_H = 1600, 800
        x_off = getattr(GMScreenView, "detached_count", 0) * (GRAPH_W + 10)
        y_off = 0
        detached_window.geometry(f"{GRAPH_W}x{GRAPH_H}")
        GMScreenView.detached_count = getattr(GMScreenView, "detached_count", 0) + 1

        detached_window.deiconify()
        print(f"[DETACH] Detached window shown at {GRAPH_W}×{GRAPH_H}")

        # Portrait & scenario-graph restoration (unchanged)…
        if hasattr(old_frame, "scenario_graph_editor") and hasattr(old_frame.scenario_graph_editor, "get_state"):
            scen = old_frame.scenario_graph_editor.get_state()
            if scen and hasattr(new_frame, "scenario_graph_editor") and hasattr(new_frame.scenario_graph_editor, "set_state"):
                new_frame.scenario_graph_editor.set_state(scen)

        if hasattr(new_frame, "portrait_label"):
            self.tabs[name]["portrait_label"] = new_frame.portrait_label
        else:
            pl = self.tabs[name].get("portrait_label")
            if pl and pl.winfo_exists():
                key = getattr(pl, "entity_name", None)
                if key in self.portrait_images:
                    lab = ctk.CTkLabel(new_frame, image=self.portrait_images[key], text="")
                    lab.image = self.portrait_images[key]
                    lab.entity_name = key
                    lab.is_portrait = True
                    lab.pack(pady=10)
                    self.tabs[name]["portrait_label"] = lab

        # Mark as detached
        self.tabs[name]["detached"]       = True
        self.tabs[name]["window"]         = detached_window
        self.tabs[name]["content_frame"]  = new_frame
        print(f"[DETACH] Tab '{name}' successfully detached.")


    def create_note_frame(self, master=None, initial_text=""):
        if master is None:
            master = self.content_area
        frame = ctk.CTkFrame(master)
        toolbar = ctk.CTkFrame(frame)
        toolbar.pack(fill="x", padx=5, pady=5)
        save_button = ctk.CTkButton(
            toolbar,
            text="Save Note",
            command=lambda: self.save_note_to_file(frame, f"Note_{len(self.tabs)}")
        )
        save_button.pack(side="right", padx=5)
        text_box = ctk.CTkTextbox(frame, wrap="word", height=500)
        text_box.pack(fill="both", expand=True, padx=10, pady=5)
        text_box.insert("1.0", initial_text)
        frame.text_box = text_box
        return frame


    def reattach_tab(self, name):
        print(f"[REATTACH] Start reattaching tab: {name}")
        # If the tab isn't marked detached, skip
        if not self.tabs[name].get("detached", False):
            print(f"[REATTACH] Tab '{name}' is not detached.")
            return

        # Retrieve the detached window and its content frame
        detached_window = self.tabs[name]["window"]
        current_frame = self.tabs[name]["content_frame"]

        # Preserve graph state if present
        saved_state = None
        if hasattr(current_frame, "graph_editor") and hasattr(current_frame.graph_editor, "get_state"):
            saved_state = current_frame.graph_editor.get_state()
        if hasattr(current_frame, "scenario_graph_editor") and hasattr(current_frame.scenario_graph_editor, "get_state"):
            saved_state = current_frame.scenario_graph_editor.get_state()

        # Special case: Note tabs store their text
        current_text = ""
        if name.startswith("Note") and hasattr(current_frame, "text_box"):
            current_text = current_frame.text_box.get("1.0", "end-1c")

        # Destroy the detached window
        if detached_window:
            detached_window.destroy()
            print("[REATTACH] Detached window destroyed.")

        # Recreate or reuse the content frame
        factory = self.tabs[name].get("factory")
        if factory is None:
            new_frame = current_frame
        else:
            # Note tabs get their text back
            if name.startswith("Note"):
                new_frame = factory(self.content_area, initial_text=current_text)
            else:
                new_frame = factory(self.content_area)

            # Restore NPC-graph state, ensuring the canvas background exists first
            if saved_state and hasattr(new_frame, "graph_editor") and hasattr(new_frame.graph_editor, "set_state"):
                ce = new_frame.graph_editor.canvas
                ce.update_idletasks()
                # Synthesize a Configure event to lay down the background
                cfg = type("E", (), {
                    "width":  ce.winfo_width(),
                    "height": ce.winfo_height()
                })()
                new_frame.graph_editor._on_canvas_configure(cfg)
                new_frame.graph_editor.set_state(saved_state)

            # Restore scenario-graph state if present
            if saved_state and hasattr(new_frame, "scenario_graph_editor") and hasattr(new_frame.scenario_graph_editor, "set_state"):
                new_frame.scenario_graph_editor.set_state(saved_state)

        # Pack and finalize
        new_frame.pack(fill="both", expand=True)
        self.tabs[name]["content_frame"] = new_frame
        self.tabs[name]["detached"] = False
        self.tabs[name]["window"] = None
        self.show_tab(name)
        # Reorder any remaining detached windows
        if hasattr(self, "reorder_detached_windows"):
            self.reorder_detached_windows()
        print(f"[REATTACH] Tab '{name}' reattached successfully.")



    def close_tab(self, name):
        if len(self.tabs) == 1:
            return
        if name in self.tab_order:
            self.tab_order.remove(name)
        if self.tabs[name].get("detached", False) and self.tabs[name].get("window"):
            self.tabs[name]["window"].destroy()
        self.tabs[name]["button_frame"].destroy()
        self.tabs[name]["content_frame"].destroy()
        del self.tabs[name]
        if self.current_tab == name and self.tabs:
            self.show_tab(next(iter(self.tabs)))
        self.reposition_add_button()

    def reposition_add_button(self):
        self.add_button.pack_forget()
        self.random_button.pack_forget()
        if self.tab_order:
            last = self.tabs[self.tab_order[-1]]["button_frame"]
            self.add_button.pack(side="left", padx=2, pady=5, after=last)
            self.random_button.pack(side="left", padx=2, pady=5, after=self.add_button)
        else:
            self.add_button.pack(side="left", padx=2, pady=5)
            self.random_button.pack(side="left", padx=2, pady=5)
    
    def _add_random_entity(self):
        """Pick a random NPC, Creature, Object, Information or Clue and open it.
        """
        types = ["NPCs", "Creatures", "Objects", "Informations", "Clues"]
        etype = random.choice(types)
        wrapper = self.wrappers.get(etype)
        if not wrapper:
            return
        items = wrapper.load_items()
        if not items:
            messagebox.showinfo("Random Entity", f"No items found for {etype}.")
            return
        # decide which key to use
        key = "Title" if etype in ("Scenarios", "Informations") else "Name"
        choice = random.choice(items)
        name = choice.get(key)
        # open it in a new tab
        self.open_entity_tab(etype, name)

    def show_tab(self, name):
        # Hide content for the current tab if it's not detached.
        if self.current_tab and self.current_tab in self.tabs:
            if not self.tabs[self.current_tab]["detached"]:
                self.tabs[self.current_tab]["content_frame"].pack_forget()
            self.tabs[self.current_tab]["button"].configure(fg_color=("gray75", "gray25"))
        self.current_tab = name
        self.tabs[name]["button"].configure(fg_color=("gray55", "gray15"))
        # Only pack the content into the main content area if the tab is not detached.
        if not self.tabs[name]["detached"]:
            self.tabs[name]["content_frame"].pack(fill="both", expand=True)

    def add_new_tab(self):
        # Added "Scenario Graph Editor" to the list of options.
        options = ["Factions", "Places", "NPCs", "PCs", "Creatures","Scenarios", "Clues", "Informations","Note Tab", "NPC Graph", "PC Graph", "Scenario Graph Editor"]
        popup = ctk.CTkToplevel(self)
        popup.title("Create New Tab")
        popup.geometry("300x400")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        popup.focus_force()
        for option in options:
            ctk.CTkButton(popup, text=option,
                        command=lambda o=option: self.open_selection_window(o, popup)).pack(pady=2)

    def open_selection_window(self, entity_type, popup):
        popup.destroy()
        if entity_type == "Note Tab":
            self.add_tab(
                f"Note {len(self.tabs) + 1}",
                self.create_note_frame(),
                content_factory=lambda master, initial_text="": self.create_note_frame(master=master, initial_text=initial_text)
            )
            return
        elif entity_type == "NPC Graph":
            self.add_tab("NPC Graph", self.create_npc_graph_frame(),
                        content_factory=lambda master: self.create_npc_graph_frame(master))
            
            return
        elif entity_type == "PC Graph":
            self.add_tab("PC Graph", self.create_pc_graph_frame(),
                        content_factory=lambda master: self.create_pc_graph_frame(master))
            
            return
        elif entity_type == "Scenario Graph Editor":
            self.add_tab("Scenario Graph Editor", self.create_scenario_graph_frame(),
                        content_factory=lambda master: self.create_scenario_graph_frame(master))
            return

        model_wrapper = self.wrappers[entity_type]
        template = self.templates[entity_type]
        selection_popup = ctk.CTkToplevel(self)
        selection_popup.title(f"Select {entity_type}")
        selection_popup.geometry("1200x800")
        selection_popup.transient(self.winfo_toplevel())
        selection_popup.grab_set()
        selection_popup.focus_force()
        # Use the new GenericListSelectionView (import it accordingly)
        view = GenericListSelectionView(selection_popup, entity_type, model_wrapper, template, self.open_entity_tab)

        view.pack(fill="both", expand=True)


    def open_entity_tab(self, entity_type, name):
        """
        Open a new tab for a specific entity with its details.
        
        Args:
            entity_type (str): The type of entity (e.g., 'Scenarios', 'NPCs', 'Creatures').
            name (str): The name or title of the specific entity to display.
        
        Raises:
            messagebox.showerror: If the specified entity cannot be found in the wrapper.
        
        Creates a new tab with the entity's details using a shared factory function,
        and provides a mechanism to recursively open related entities.
        """
        wrapper = self.wrappers[entity_type]
        items = wrapper.load_items()
        key = "Title" if (entity_type == "Scenarios" or entity_type == "Informations") else "Name"
        item = next((i for i in items if i.get(key) == name), None)
        if not item:
            messagebox.showerror("Error", f"{entity_type[:-1]} '{name}' not found.")
            return
        # Use the shared factory function and pass self.open_entity_tab as the callback.
        frame = create_entity_detail_frame(entity_type, item, master=self.content_area, open_entity_callback=self.open_entity_tab)
        
        self.add_tab(
            name,
            frame,
            content_factory=lambda master: create_entity_detail_frame(entity_type, item, master=master, open_entity_callback=self.open_entity_tab)
        )

    def create_scenario_graph_frame(self, master=None):
        if master is None:
            master = self.content_area
        
        frame = ctk.CTkFrame(master, height=700)
        # Prevent the frame from shrinking to fit its child; allow it to expand fully
        frame.pack_propagate(False)
        # Create a ScenarioGraphEditor widget.
        # Note: Ensure that self.wrappers contains "Scenarios", "NPCs", and "Places" as required.
        scenario_graph_editor = ScenarioGraphEditor(
            frame,
            self.wrappers["Scenarios"],
            self.wrappers["NPCs"],
            self.wrappers["Creatures"],
            self.wrappers["Places"]
        )
        scenario_graph_editor.pack(fill="both", expand=True)
        frame.scenario_graph_editor = scenario_graph_editor  # Optional: store a reference for state management.
        return frame

    def create_entity_frame(self, entity_type, entity, master=None):
        if master is None:
            master = self.content_area
        frame = ctk.CTkFrame(master)
        template = self.templates[entity_type]
        if (entity_type == "NPCs" or entity_type == "PCs" or entity_type == "Creatures" ) and "Portrait" in entity and os.path.exists(entity["Portrait"]):
            img = Image.open(entity["Portrait"])
            img = img.resize((200, 200), Image.Resampling.LANCZOS)
            ctk_image = ctk.CTkImage(light_image=img, size=(200, 200))
            portrait_label = ctk.CTkLabel(frame, image=ctk_image, text="")
            portrait_label.image = ctk_image
            portrait_label.entity_name = entity["Name"]
            portrait_label.is_portrait = True
            self.portrait_images[entity["Name"]] = ctk_image
            portrait_label.pack(pady=10)
            print(f"[DEBUG] Created portrait label for {entity['Name']}: is_portrait={portrait_label.is_portrait}, entity_name={portrait_label.entity_name}")
            frame.portrait_label = portrait_label
        for field in template["fields"]:
            field_name = field["name"]
            field_type = field["type"]
            if (entity_type == "NPCs" or entity_type == "PCs" or entity_type == "Creatures") and field_name == "Portrait":
                continue
            if field_type == "longtext":
                self.insert_longtext(frame, field_name, entity.get(field_name, ""))
            elif field_type == "text":
                self.insert_text(frame, field_name, entity.get(field_name, ""))
            elif field_type == "list":
                linked_type = field.get("linked_type", None)
                if linked_type:
                    self.insert_links(frame, field_name, entity.get(field_name) or [], linked_type)
        return frame
    
    def insert_text(self, parent, header, content):
        label = ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold"))
        label.pack(anchor="w", padx=10)
        box = ctk.CTkTextbox(parent, wrap="word", height=80)
        # Ensure content is a plain string.
        if isinstance(content, dict):
            content = content.get("text", "")
        elif isinstance(content, list):
            content = " ".join(map(str, content))
        else:
            content = str(content)
        # For debugging, you can verify:
        # print("DEBUG: content =", repr(content))

        # Override the insert method to bypass the CTkTextbox wrapper.
        box.insert = box._textbox.insert
        # Now use box.insert normally.
        box.insert("1.0", content)

        box.configure(state="disabled")
        box.pack(fill="x", padx=10, pady=5)
        
    def insert_longtext(self, parent, header, content):
        ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold")).pack(anchor="w", padx=10)
        formatted_text = format_multiline_text(content, max_length=2000)
        box = ctk.CTkTextbox(parent, wrap="word", height=120)
        box.insert("1.0", formatted_text)
        box.configure(state="disabled")
        box.pack(fill="x", padx=10, pady=5)

    def insert_links(self, parent, header, items, linked_type):
        ctk.CTkLabel(parent, text=f"{header}:", font=("Arial", 14, "bold")).pack(anchor="w", padx=10)
        for item in items:
            label = ctk.CTkLabel(parent, text=item, text_color="#00BFFF", cursor="hand2")
            label.pack(anchor="w", padx=10)
            label.bind("<Button-1>", partial(self._on_link_clicked, linked_type, item))

    def _on_link_clicked(self, linked_type, item, event=None):
        self.open_entity_tab(linked_type, item)

    def save_note_to_file(self, note_frame, default_name):
        file_path = filedialog.asksaveasfilename(
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt")],
            title="Save Note As"
        )
        if not file_path:
            return
        content = note_frame.text_box.get("1.0", "end-1c")
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
        messagebox.showinfo("Saved", f"Note saved to {file_path}")
    
    def create_npc_graph_frame(self, master=None):
        if master is None:
            master = self.content_area
        frame = ctk.CTkFrame(master, height=700)
        frame.pack_propagate(False)
        graph_editor = NPCGraphEditor(frame, self.wrappers["NPCs"], self.wrappers["Factions"])
        graph_editor.pack(fill="both", expand=True)
        frame.graph_editor = graph_editor  # Save a reference for state management
        
        return frame
    
    def create_pc_graph_frame(self, master=None):
        if master is None:
            master = self.content_area
        frame = ctk.CTkFrame(master, height=700)
        frame.pack_propagate(False)
        graph_editor = PCGraphEditor(frame, self.wrappers["PCs"], self.wrappers["Factions"])
        graph_editor.pack(fill="both", expand=True)
        frame.graph_editor = graph_editor  # Save a reference for state management
        return frame
    
    def reorder_detached_windows(self):
        screen_width = self.winfo_screenwidth()
        margin = 10  # space between windows and screen edge
        current_x = margin
        current_y = margin
        max_row_height = 0

        for name, tab in self.tabs.items():
            if tab.get("detached") and tab.get("window") is not None:
                window = tab["window"]
                window.update_idletasks()
                req_width = window.winfo_reqwidth()
                req_height = window.winfo_reqheight()
                # If adding this window would go beyond screen width, wrap to next line
                if current_x + req_width + margin > screen_width:
                    current_x = margin
                    current_y += max_row_height + margin
                    max_row_height = 0
                window.geometry(f"{req_width}x{req_height}+{current_x}+{current_y}")
                current_x += req_width + margin
                if req_height > max_row_height:
                    max_row_height = req_height
    def destroy(self):
        # remove our global Ctrl+F handler
        root = self.winfo_toplevel()
        root.unbind_all("<Control-F>")
        # now destroy as usual
        super().destroy()
