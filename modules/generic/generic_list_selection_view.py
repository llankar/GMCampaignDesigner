import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import time
import re
import os
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

class GenericListSelectionView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        entity_type,
        model_wrapper,
        template,
        on_select_callback=None,
        *args,
        allow_multi_select=False,
        on_multi_select_callback=None,
        **kwargs,
    ):
        super().__init__(master, *args, **kwargs)
        self.entity_type = entity_type
        self.model_wrapper = model_wrapper
        self.template = template
        self.on_select_callback = on_select_callback
        self.on_multi_select_callback = on_multi_select_callback
        self.allow_multi_select = allow_multi_select

        # Load items and prepare columns
        self.items = self.model_wrapper.load_items()
        self.filtered_items = self.items.copy()
        # Use the first field that is not "Portrait" as the unique field
        self.unique_field = next((f["name"] for f in self.template["fields"] if f["name"] != "Portrait"), None)
        # Extra columns: all fields except "Portrait" and the unique field
        self.columns = [
            f["name"]
            for f in self.template["fields"]
            if f["name"] not in ["Portrait", self.unique_field]
        ]

        # --- Create Search Bar ---
        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(search_frame, text="Search:").pack(side="left", padx=5)
        self.search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        search_entry.bind("<KeyRelease>", lambda event: self.filter_items())

        # --- Create a container for the Treeview with a dark background ---
        tree_frame = ctk.CTkFrame(self, fg_color="#2B2B2B")
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Create a local ttk style for the Treeview ---
        style = ttk.Style(self)
        style.theme_use("clam")
        body_font = ("Segoe UI", 11)
        heading_font = ("Segoe UI", 12, "bold")
        style.configure(
            "Custom.Treeview",
            background="#2B2B2B",
            fieldbackground="#2B2B2B",
            foreground="white",
            rowheight=30,
            font=body_font,
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#2B2B2B",
            foreground="white",
            font=heading_font,
        )
        style.map("Custom.Treeview", background=[("selected", "#2B2B2B")])

        # --- Create the Treeview using the custom style ---
        self.tree = ttk.Treeview(
            tree_frame,
            columns=self.columns,
            show="tree headings",
            selectmode="extended" if self.allow_multi_select else "browse",
            style="Custom.Treeview",
        )
        # Make header clicks sort the column
        self.tree.heading(
            "#0",
            text=self.unique_field,
            command=lambda c=self.unique_field: self.sort_column(c),
        )
        self.tree.column("#0", width=240, minwidth=180, anchor="w", stretch=True)
        for col in self.columns:
            self.tree.heading(
                col,
                text=col,
                command=lambda c=col: self.sort_column(c),
            )
            self.tree.column(col, width=160, minwidth=120, anchor="w", stretch=True)

        # --- Add vertical and horizontal scrollbars ---
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")

        # --- Pack the Treeview ---
        self.tree.pack(fill="both", expand=True)

        self.selection_indicator_image = tk.PhotoImage(width=4, height=30)
        self.selection_indicator_image.put("#FFFFFF", to=(0, 0, 4, 30))
        self._indicator_item_ids = set()
        self.item_by_id = {}

        # Bind double-click event and initial refresh
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select_change)
        self.refresh_list()

        button_label = "Add Selected" if self.allow_multi_select else "Open Selected"
        ctk.CTkButton(self, text=button_label, command=self.open_selected).pack(
            side="bottom", pady=5
        )

        # --- Center the window if master is a Toplevel ---
        if isinstance(self.master, tk.Toplevel):
            self.master.update_idletasks()
            min_width, min_height = 1100, 720
            width = max(self.master.winfo_width(), self.master.winfo_reqwidth(), min_width)
            height = max(self.master.winfo_height(), self.master.winfo_reqheight(), min_height)
            screen_width = self.master.winfo_screenwidth()
            screen_height = self.master.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.master.geometry(f"{int(width)}x{int(height)}+{int(x)}+{int(y)}")
            self.master.minsize(min_width, min_height)

    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        self.item_by_id = {}
        for item in self.filtered_items:
            # For the unique field (usually "Name")
            raw_val = self._clean_value(item.get(self.unique_field, ""))
            base_id = self.sanitize_id(raw_val or f"item_{int(time.time()*1000)}")
            iid = base_id
            suffix = 1
            while iid in self.item_by_id:
                iid = f"{base_id}_{suffix}"
                suffix += 1

            values = [self._clean_value(item.get(col, "")) for col in self.columns]
            self.tree.insert("", "end", iid=iid, text=raw_val, values=values)
            self.item_by_id[iid] = item

        self._clear_selection_indicator()

    def sort_column(self, column_name):
        # Initialize sort directions dict on first use
        if not hasattr(self, "sort_directions"):
            self.sort_directions = {}

        # Toggle sort order: True=ascending, False=descending
        asc = self.sort_directions.get(column_name, True)
        self.sort_directions[column_name] = not asc

        # Perform the in-place sort on filtered_items
        self.filtered_items.sort(
            key=lambda item: str(item.get(column_name, "") or "").lower(),
            reverse=not asc,
        )

        # Refresh the Treeview to reflect the new order
        self.refresh_list()

    def filter_items(self):
        query = self.search_var.get().strip().lower()
        if not query:
            self.filtered_items = self.items.copy()
        else:
            self.filtered_items = [
                item for item in self.items if any(query in str(v).lower() for v in item.values())
            ]
        self.refresh_list()

    def on_double_click(self, event):
        # Prefer the row under the cursor; fall back to focus
        item_id = self.tree.identify_row(event.y) or self.tree.focus()
        if not item_id:
            return
        selected_item = self.item_by_id.get(item_id)
        if selected_item and self.on_select_callback:
            entity_name = selected_item.get("Name", selected_item.get("Title", "Unnamed"))
            self.on_select_callback(self.entity_type, entity_name)

    def open_selected(self):
        selection_ids = list(self.tree.selection())

        if self.allow_multi_select:
            if not selection_ids:
                messagebox.showwarning("No Selection", f"No {self.entity_type} selected.")
                return

            selected_items = [self.item_by_id.get(iid) for iid in selection_ids if iid in self.item_by_id]
            selected_items = [item for item in selected_items if item]
            if not selected_items:
                messagebox.showwarning("No Selection", f"No {self.entity_type} available to select.")
                return

            if self.on_multi_select_callback:
                self.on_multi_select_callback(self.entity_type, selected_items)
            elif self.on_select_callback:
                for item in selected_items:
                    entity_name = item.get("Name", item.get("Title", "Unnamed"))
                    self.on_select_callback(self.entity_type, entity_name)
            return

        if selection_ids:
            selected_item = self.item_by_id.get(selection_ids[0])
            if selected_item:
                self.select_entity(selected_item)
                return

        if self.filtered_items:
            # Open the first item by default
            self.select_entity(self.filtered_items[0])
        else:
            messagebox.showwarning("No Selection", f"No {self.entity_type} available to select.")

    def select_entity(self, item):
        self.on_select_callback(self.entity_type, item.get("Name", item.get("Title", "Unnamed")))
        self.destroy()

    def _clean_value(self, val):
        if val is None:
            return ""
        if isinstance(val, dict):
            if "text" in val:
                return self._clean_value(val.get("text", ""))
            if "Label" in val or "label" in val:
                label = val.get("Label", val.get("label", ""))
                return str(label).strip()
            if "Path" in val or "path" in val:
                start = val.get("StartPage") or val.get("start_page")
                end = val.get("EndPage") or val.get("end_page")
                if isinstance(val.get("page_range"), (list, tuple)) and len(val["page_range"]) >= 2:
                    start = start or val["page_range"][0]
                    end = end or val["page_range"][1]
                label = None
                if start and end and start != end:
                    label = f"pp. {start}-{end}"
                elif start:
                    label = f"p. {start}"
                return label or os.path.basename(str(val.get("Path") or val.get("path") or ""))
            return ", ".join(self._clean_value(v) for v in val.values())
        if isinstance(val, list):
            return ", ".join(self._clean_value(v) for v in val if v is not None)
        return str(val).replace("{", "").replace("}", "").strip()

    def sanitize_id(self, s):
        return re.sub(r'[^a-zA-Z0-9]+', '_', str(s)).strip('_')

    def _on_tree_select_change(self, _event=None):
        current_ids = set(self.tree.selection())
        to_clear = self._indicator_item_ids - current_ids
        for iid in list(to_clear):
            if self.tree.exists(iid):
                self.tree.item(iid, image="")
        for iid in current_ids:
            if self.tree.exists(iid):
                self.tree.item(iid, image=self.selection_indicator_image)
        self._indicator_item_ids = current_ids

    def _clear_selection_indicator(self):
        for iid in list(self._indicator_item_ids):
            if self.tree.exists(iid):
                self.tree.item(iid, image="")
        self._indicator_item_ids = set()
