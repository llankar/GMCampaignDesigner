import customtkinter as ctk
import tkinter as tk
from .scenarios_model import load_scenarios, save_scenarios, load_template
from .scenario_editor_view import EditScenarioWindow
import uuid

def format_longtext(value, max_length=50):
    if len(value) > max_length:
        return value[:max_length] + "..."
    return value

class ScenarioWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Scenario Management")
        
        self.minsize(1280, 720)
        self.transient(master)
        self.lift()
        self.focus_force()

        self.items = load_scenarios()
        self.template = load_template()
        self.fields = [field["name"] for field in self.template["fields"]]
        self.current_sort = {"column": None, "reverse": False}

        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", padx=10, pady=5)

        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search Scenario")
        self.search_entry.pack(side="left", expand=True, fill="x", padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self.filter_items())

        add_button = ctk.CTkButton(search_frame, text="Add Scenario", command=self.add_item)
        add_button.pack(side="right", padx=5)

        self.table_frame = ctk.CTkFrame(self)
        self.table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.create_table_header()
        self.load_item_list()

    def create_table_header(self):
        for col, field in enumerate(self.fields):
            header = ctk.CTkButton(self.table_frame, text=field, command=lambda c=col: self.sort_by_column(c))
            header.grid(row=0, column=col, sticky="ew", padx=5, pady=2)

    def sort_by_column(self, col):
        field = self.fields[col]
        reverse = not self.current_sort.get("reverse", False)
        self.items.sort(key=lambda x: str(x.get(field, "")).lower(), reverse=reverse)
        self.current_sort = {"column": col, "reverse": reverse}
        self.load_item_list()

    def load_item_list(self):
        for widget in self.table_frame.winfo_children():
            if int(widget.grid_info().get("row", 0)) > 0:
                widget.destroy()

        if not self.items:
            ctk.CTkLabel(self.table_frame, text=f"No Scenarios found.").grid(row=1, column=0, columnspan=len(self.fields), pady=5)
        else:
            for row, item in enumerate(self.items, start=1):
                self.create_item_row(item, row)

    def create_item_row(self, item, row):
        for col, field in enumerate(self.fields):
            value = item.get(field, "")
            field_def = next((f for f in self.template["fields"] if f["name"] == field), None)
            if field_def and field_def["type"] == "longtext":
                value = format_longtext(value, max_length=50)

            cell = ctk.CTkLabel(self.table_frame, text=value, anchor="w", justify="left")
            cell.grid(row=row, column=col, sticky="w", padx=5, pady=2)
            cell.bind("<Button-1>", lambda event, i=item: self.edit_item(i))

    def add_item(self):
        new_item = {"id": str(uuid.uuid4())}
        for field in self.template["fields"]:
            new_item[field["name"]] = field.get("default", "")
        editor = EditScenarioWindow(self, new_item, creation_mode=True)
        self.wait_window(editor)
        if editor.saved:
            self.items.append(new_item)
            save_scenarios(self.items)
            self.load_item_list()

    def edit_item(self, item):
        editor = EditScenarioWindow(self, item)
        self.wait_window(editor)
        if editor.saved:
            save_scenarios(self.items)
            self.load_item_list()

    def filter_items(self):
        query = self.search_entry.get().lower()
        self.items = [i for i in load_scenarios() if any(query in str(v).lower() for v in i.values())]
        self.load_item_list()