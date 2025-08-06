import customtkinter as ctk
import os
from tkinter import messagebox
from PIL import Image
from customtkinter import CTkLabel, CTkImage
from modules.helpers.text_helpers import format_longtext
from modules.helpers.config_helper import ConfigHelper

PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
MAX_PORTRAIT_SIZE = (64, 64)

class EntitySelectionDialog(ctk.CTkToplevel):
    def __init__(self, master, entity_type, model_wrapper, template, on_entity_selected):
        super().__init__(master)
        self.title(f"Select {entity_type}")

        # Center the window on the screen.
        width = 1200
        height = 800
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.transient(master)  # Stay on top of the master window
        self.grab_set()         # Block background clicks
        self.focus_force()      # Focus on the dialog

        self.entity_type = entity_type
        self.model_wrapper = model_wrapper
        self.template = template
        self.on_entity_selected = on_entity_selected

        self.items = self.model_wrapper.load_items()
        self.filtered_items = self.items.copy()

        self.image_cache = {}

        os.makedirs(PORTRAIT_FOLDER, exist_ok=True)

        self.search_var = ctk.StringVar()

        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(search_frame, text=f"Search {entity_type}:").pack(side="left", padx=5)
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        search_entry.bind("<KeyRelease>", lambda event: self.filter_items())

        self.table_frame = ctk.CTkScrollableFrame(self)
        self.table_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.headers = []
        self.has_portrait = any(f["name"] == "Portrait" for f in self.template["fields"])
        if self.has_portrait:
            self.headers.append("Portrait")

        self.headers += [f["name"] for f in self.template["fields"] if f["name"] != "Portrait"]

        self.create_table_header()
        self.refresh_list()

        ctk.CTkButton(self, text="Open Selected", command=self.open_selected).pack(side="bottom", pady=5)

    def create_table_header(self):
        for col_index, header_text in enumerate(self.headers):
            header_button = ctk.CTkButton(
                self.table_frame, text=header_text, anchor="w",
                command=lambda c=header_text: self.sort_column(c)
            )
            header_button.grid(row=0, column=col_index, sticky="ew", padx=5, pady=2)

    def refresh_list(self):
        for child in self.table_frame.winfo_children():
            if int(child.grid_info()["row"]) > 0:
                child.destroy()

        for row_index, item in enumerate(self.filtered_items, start=1):
            self.create_item_row(item, row_index)

    def create_item_row(self, item, row_index):
        col_index = 0

        if self.has_portrait:
            portrait_path = item.get("Portrait", "")
            if portrait_path and os.path.exists(portrait_path):
                if portrait_path not in self.image_cache:
                    img = Image.open(portrait_path)
                    img.thumbnail(MAX_PORTRAIT_SIZE)
                    ctk_img = CTkImage(light_image=img, dark_image=img, size=MAX_PORTRAIT_SIZE)
                    self.image_cache[portrait_path] = ctk_img

                portrait_label = CTkLabel(self.table_frame, text="", image=self.image_cache[portrait_path])
            else:
                portrait_label = ctk.CTkLabel(self.table_frame, text="[No Image]")

            portrait_label.grid(row=row_index, column=col_index, padx=5, pady=2)
            portrait_label.bind("<Button-1>", lambda e, i=item: self.select_entity(i))
            col_index += 1

        for field in self.template["fields"]:
            if field["name"] == "Portrait":
                continue

            value = item.get(field["name"], "")
            if field.get("type") == "longtext":
                value = format_longtext(value, max_length=200)
            label = ctk.CTkLabel(self.table_frame, text=value, anchor="w")
            label.grid(row=row_index, column=col_index, sticky="w", padx=5, pady=2)
            label.bind("<Button-1>", lambda e, i=item: self.select_entity(i))
            col_index += 1

    def filter_items(self):
        query = self.search_var.get().strip().lower()
        self.filtered_items = [
            i for i in self.items if any(query in str(v).lower() for v in i.values())
        ]
        self.refresh_list()

    def sort_column(self, column):
        self.filtered_items.sort(key=lambda x: str(x.get(column, "")).lower())
        self.refresh_list()

    def select_entity(self, item):
        self.on_entity_selected(item)
        self.destroy()

    def open_selected(self):
        if self.filtered_items:
            self.select_entity(self.filtered_items[0])
        else:
            messagebox.showwarning("No Selection", f"No {self.entity_type} available to select.")