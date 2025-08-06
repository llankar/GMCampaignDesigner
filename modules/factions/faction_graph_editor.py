# modules/factions/faction_graph_editor.py

import os, math
import customtkinter as ctk
from tkinter import filedialog, messagebox, Menu, ttk
from PIL import Image, ImageTk
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.generic.generic_model_wrapper import GenericModelWrapper

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class FactionGraphEditor(ctk.CTkFrame):
    def __init__(self, master, faction_wrapper: GenericModelWrapper, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.faction_wrapper = faction_wrapper
        self.graph = {"nodes": [], "links": []}
        self.node_positions = {}      # tag → (x,y)
        self.node_rects    = {}      # tag → canvas rect id
        self.link_items    = {}      # (f1,f2) → {"line":…, "text":…}

        # canvas + scrollbars
        self.canvas = ctk.CTkCanvas(self, bg="#2B2B2B", highlightthickness=0)
        hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        vbar = ttk.Scrollbar(self, orient="vertical",   command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        hbar.grid(row=2, column=0, sticky="ew")
        vbar.grid(row=1, column=1, sticky="ns")
        self.grid_rowconfigure(1, weight=1); self.grid_columnconfigure(0, weight=1)

        # event bindings
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.do_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Button-3>", self.on_right_click)

        # toolbar
        self._dragging = None
        self.init_toolbar()
        self.draw_graph()

    def init_toolbar(self):
        bar = ctk.CTkFrame(self)
        bar.grid(row=0, column=0, columnspan=2, pady=5, sticky="ew")
        ctk.CTkButton(bar, text="Add Faction", command=self.add_faction).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Add Link",    command=self.start_link).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Save",        command=self.save_graph).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Load",        command=self.load_graph).pack(side="left", padx=4)

    def add_faction(self):
        # choose faction from list
        template = {"fields":[{"name":"Name","type":"text"}]}
        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Faction")
        dialog.geometry("1200x800")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()
        lst = GenericListSelectionView(dialog, "Factions", self.faction_wrapper, template,
                                    on_select_callback=lambda et,name: self._on_faction_chosen(name, dialog))
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.focus_force()
        lst.pack(fill="both", expand=True)
        dialog.wait_window()

    def _on_faction_chosen(self, name, dialog):
        dialog.destroy()
        self.pending_node = name
        # next click places it
        self.canvas.bind("<Button-1>", self.place_node)

    def place_node(self, evt):
        x = self.canvas.canvasx(evt.x); y = self.canvas.canvasy(evt.y)
        tag = f"faction_{self.pending_node.replace(' ','_')}"
        if tag in (n["tag"] for n in self.graph["nodes"]):
            messagebox.showinfo("Exists", f"'{self.pending_node}' already placed.")
        else:
            self.graph["nodes"].append({"name":self.pending_node,"x":x,"y":y,"tag":tag})
            self.node_positions[tag] = (x,y)
        # restore drag binding
        self.canvas.unbind("<Button-1>")
        self.canvas.bind("<Button-1>", self.start_drag)
        self.draw_graph()

    def start_link(self):
        self.canvas.bind("<Button-1>", self._pick_link_start)

    def _pick_link_start(self, evt):
        x,y = self.canvas.canvasx(evt.x), self.canvas.canvasy(evt.y)
        item = self.canvas.find_closest(x,y)
        tags = self.canvas.gettags(item)
        self.link_start = next((t for t in tags if t.startswith("faction_")),None)
        if self.link_start:
            self.canvas.bind("<Button-1>", self._pick_link_end)

    def _pick_link_end(self, evt):
        x,y = self.canvas.canvasx(evt.x), self.canvas.canvasy(evt.y)
        item = self.canvas.find_closest(x,y)
        tags = self.canvas.gettags(item)
        end = next((t for t in tags if t.startswith("faction_")),None)
        if end and end!=self.link_start:
            txt = ctk.CTkInputDialog(text="Link label?", title="Relation").get_input()
            self.graph["links"].append({
                "from":self.link_start,"to":end,"text":txt or ""
            })
        # restore drag
        self.canvas.unbind("<Button-1>")
        self.canvas.bind("<Button-1>", self.start_drag)
        self.draw_graph()

    def draw_graph(self):
        self.canvas.delete("all")
        # links first
        for link in self.graph["links"]:
            x1,y1 = self.node_positions.get(link["from"],(0,0))
            x2,y2 = self.node_positions.get(link["to"],  (0,0))
            line = self.canvas.create_line(x1,y1,x2,y2, fill="#5BB8FF", tags="link")
            mx,my = (x1+x2)/2,(y1+y2)/2
            text = self.canvas.create_text(mx,my,text=link["text"], fill="white", tags="link_text")
            self.link_items[(link["from"],link["to"])] = {"line":line,"text":text}
        # then nodes
        for node in self.graph["nodes"]:
            tag = node["tag"]
            x,y = self.node_positions[tag]
            w,h = 120,40
            rect = self.canvas.create_rectangle(
                x-w/2,y-h/2,x+w/2,y+h/2,
                fill="#4477AA", tags=(tag,)
            )
            self.canvas.create_text(x,y,text=node["name"], fill="white", font=("Arial",10,"bold"), tags=(tag,))
            self.node_rects[tag] = rect
        # update scrollregion
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(bbox[0]-50,bbox[1]-50,bbox[2]+50,bbox[3]+50))

    # --- dragging support ---
    def start_drag(self, evt):
        x,y = self.canvas.canvasx(evt.x), self.canvas.canvasy(evt.y)
        item = self.canvas.find_closest(x,y)
        tags = self.canvas.gettags(item)
        self._drag_tag = next((t for t in tags if t.startswith("faction_")),None)
        if self._drag_tag:
            self._drag_start = (x,y)

    def do_drag(self, evt):
        if not hasattr(self,"_drag_tag") or not self._drag_tag: return
        x,y = self.canvas.canvasx(evt.x), self.canvas.canvasy(evt.y)
        dx,dy = x-self._drag_start[0], y-self._drag_start[1]
        for obj in self.canvas.find_withtag(self._drag_tag):
            self.canvas.move(obj, dx, dy)
        ox,oy = self.node_positions[self._drag_tag]
        self.node_positions[self._drag_tag] = (ox+dx, oy+dy)
        self._drag_start=(x,y)
        # move related links
        for (f1,f2),ids in self.link_items.items():
            if f1==self._drag_tag or f2==self._drag_tag:
                x1,y1 = self.node_positions[f1]; x2,y2 = self.node_positions[f2]
                self.canvas.coords(ids["line"], x1,y1,x2,y2)
                mx,my = (x1+x2)/2,(y1+y2)/2
                self.canvas.coords(ids["text"], mx,my)

    def end_drag(self, evt):
        self._drag_tag=None

    # --- right-click menu to delete ---
    def on_right_click(self, evt):
        x,y = self.canvas.canvasx(evt.x), self.canvas.canvasy(evt.y)
        item = self.canvas.find_closest(x,y)
        tags = self.canvas.gettags(item)
        node = next((t for t in tags if t.startswith("faction_")),None)
        if node:
            menu = Menu(self.canvas, tearoff=0)
            menu.add_command(label="Delete Faction", command=lambda: self._delete_node(node))
            menu.post(evt.x_root, evt.y_root)

    def _delete_node(self, tag):
        name = tag.replace("faction_","").replace("_"," ")
        self.graph["nodes"] = [n for n in self.graph["nodes"] if n["tag"]!=tag]
        self.graph["links"] = [l for l in self.graph["links"]
                                if l["from"]!=tag and l["to"]!=tag]
        self.node_positions.pop(tag,None)
        self.draw_graph()
    def get_state(self):
        return {
            "graph": self.graph.copy(),
            "node_positions": self.node_positions.copy(),
            # include any other state needed
        }

    def set_state(self, state):
        self.graph = state.get("graph", {}).copy()
        self.node_positions = state.get("node_positions", {}).copy()
        self.draw_graph()  # Refresh the drawing
    # --- save / load ---
    def save_graph(self):
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if not path: return
        # sync positions
        for n in self.graph["nodes"]:
            n["x"],n["y"] = self.node_positions[n["tag"]]
        with open(path,"w", encoding="utf-8") as f:
            import json; json.dump(self.graph,f,indent=2)

    def load_graph(self):
        path = filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if not path: return
        import json
        self.graph = json.load(open(path,encoding="utf-8"))
        self.node_positions = {n["tag"]:(n["x"],n["y"]) for n in self.graph["nodes"]}
        self.draw_graph()