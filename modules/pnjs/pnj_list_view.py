import customtkinter as ctk
from modules.pnjs.pnjs_model import load_npcs, save_npcs, load_template
from modules.pnjs.pnj_editor_view import EditNPCWindow
import uuid

class NPCWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("NPC Management")
        
        self.minsize(1280, 720)

        self.transient(master)
        self.lift()
        self.focus_force()

        self.npcs = load_npcs()
        self.template = load_template()
        self.fields = [field["name"] for field in self.template["fields"]]
        self.current_sort = {"column": None, "reverse": False}

        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", padx=10, pady=5)

        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search NPC")
        self.search_entry.pack(side="left", expand=True, fill="x", padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self.filter_npcs())

        add_button = ctk.CTkButton(search_frame, text="Add NPC", command=self.add_npc)
        add_button.pack(side="right", padx=5)

        self.table_frame = ctk.CTkFrame(self)
        self.table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.create_table_header()
        self.load_npc_list()

    def create_table_header(self):
        for col, field_name in enumerate(self.fields):
            header = ctk.CTkButton(self.table_frame, text=field_name, command=lambda c=col: self.sort_by_column(c))
            header.grid(row=0, column=col, sticky="ew", padx=5, pady=2)

    def sort_by_column(self, col):
        field_name = self.fields[col]
        reverse = not self.current_sort.get("reverse", False)

        self.npcs.sort(key=lambda x: x.get(field_name, "").lower(), reverse=reverse)
        self.current_sort = {"column": col, "reverse": reverse}
        self.load_npc_list()

    def load_npc_list(self):
        for widget in self.table_frame.winfo_children():
            if int(widget.grid_info().get("row", 0)) > 0:
                widget.destroy()

        if not self.npcs:
            ctk.CTkLabel(self.table_frame, text="No NPC found.").grid(row=1, column=0, columnspan=len(self.fields), pady=5)
        else:
            for row, npc in enumerate(self.npcs, start=1):
                self.create_npc_row(npc, row)

    def create_npc_row(self, npc, row):
        for col, field_name in enumerate(self.fields):
            value = npc.get(field_name, "N/A")

            field_def = next((f for f in self.template["fields"] if f["name"] == field_name), None)
            is_longtext = field_def and field_def["type"] == "longtext"

            if is_longtext:
                # On limite la largeur, et on force le wrap automatique
                cell = ctk.CTkLabel(self.table_frame, text=value, anchor="w", justify="left")
                cell.grid(row=row, column=col, sticky="w", padx=5, pady=2)
                cell.configure(wraplength=250)  # Ajuste la largeur de colonne ici
            else:
                cell = ctk.CTkLabel(self.table_frame, text=value, anchor="w", justify="left")
                cell.grid(row=row, column=col, sticky="w", padx=5, pady=2)

            cell.bind("<Button-1>", lambda event, npc_id=npc["id"]: self.edit_npc(npc_id))

    def add_npc(self):
        template = load_template()
        new_npc = {"id": str(uuid.uuid4())}
        for field in template["fields"]:
            new_npc[field["name"]] = field["default"]

        editor = EditNPCWindow(self, new_npc, creation_mode=True)
        self.wait_window(editor)

        if save_factions:
            self.npcs.append(new_npc)
            save_npcs(self.npcs)
            self.load_npc_list()

    def edit_npc(self, npc_id):
        npc = next((n for n in self.npcs if n["id"] == npc_id), None)
        if npc:
            editor = EditNPCWindow(self, npc)
            self.wait_window(editor)
            if editor.saved:
                save_npcs(self.npcs)
                self.load_npc_list()

    def filter_npcs(self):
        query = self.search_entry.get().lower()
        self.npcs = [npc for npc in load_npcs() if any(query in str(v).lower() for v in npc.values())]
        self.load_npc_list()
