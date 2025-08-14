import re
import time
import os, ctypes
from ctypes import wintypes
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import copy
from PIL import Image, ImageTk
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.ui.image_viewer import show_portrait
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.window_helper import position_window_at_top
from modules.scenarios.gm_screen_view import GMScreenView
import shutil

PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
MAX_PORTRAIT_SIZE = (1024, 1024)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def sanitize_id(s):
    return re.sub(r'[^a-zA-Z0-9]+', '_', str(s)).strip('_')

def unique_iid(tree, base_id):
    """Return a unique iid for the given treeview based on base_id."""
    iid = base_id
    counter = 1
    while tree.exists(iid):
        counter += 1
        iid = f"{base_id}_{counter}"
    return iid

class _ToolTip:
    """Simple tooltip for a Treeview showing full cell text on hover."""
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.text = ""
        widget.bind("<Motion>", self._on_motion)
        widget.bind("<Leave>", self._on_leave)

    def _on_motion(self, event):
        rowid = self.widget.identify_row(event.y)
        colid = self.widget.identify_column(event.x)
        if rowid and colid:
            if colid == "#0":
                txt = self.widget.item(rowid, "text")
            else:
                txt = self.widget.set(rowid, colid)
        else:
            txt = ""
        if txt and txt != self.text:
            self.text = txt
            self._show(event.x_root + 20, event.y_root + 10, txt)
        elif not txt:
            self._hide()

    def _on_leave(self, _):
        self._hide()

    def _show(self, x, y, text):
        self._hide()
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            wraplength=400
        )
        label.pack(ipadx=1)
        self.tipwindow = tw

    def _hide(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
            self.text = ""

class GenericListView(ctk.CTkFrame):
    def __init__(self, master, model_wrapper, template, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.model_wrapper = model_wrapper
        self.template = template
        os.makedirs(PORTRAIT_FOLDER, exist_ok=True)

        self.items = self.model_wrapper.load_items()
        self.filtered_items = list(self.items)

        self.group_column = ConfigHelper.get(
            "ListGrouping", self.model_wrapper.entity_type, fallback=None
        )

        self.unique_field = next(
            (f["name"] for f in self.template["fields"] if f["name"] != "Portrait"),
            None
        )
        self.columns = [
            f["name"] for f in self.template["fields"]
            if f["name"] not in ("Portrait", self.unique_field)
        ]

        # --- Search bar ---
        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", padx=(5,45), pady=5)
        ctk.CTkLabel(search_frame, text="Search:").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        search_entry.bind("<Return>", lambda e: self.filter_items(self.search_var.get()))
        ctk.CTkButton(search_frame, text="Filter",
            command=lambda: self.filter_items(self.search_var.get()))\
        .pack(side="left", padx=5)
        ctk.CTkButton(search_frame, text="Add",
            command=self.add_item)\
        .pack(side="left", padx=5)
        if self.model_wrapper.entity_type == "maps":
            ctk.CTkButton(search_frame, text="Import Directory",
                          command=self.import_map_directory)\
                .pack(side="left", padx=5)
        ctk.CTkButton(search_frame, text="Group By",
            command=self.choose_group_column)\
        .pack(side="left", padx=5)

        # --- Treeview setup ---
        tree_frame = ctk.CTkFrame(self, fg_color="#2B2B2B")
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Custom.Treeview",
                        background="#2B2B2B",
                        fieldbackground="#2B2B2B",
                        foreground="white",
                        rowheight=25,
                        font=("Segoe UI", 10, "bold"))
        style.configure("Custom.Treeview.Heading",
                        background="#2B2B2B",
                        foreground="white",
                        font=("Segoe UI", 10, "bold"))
        style.map("Custom.Treeview",
                background=[("selected", "#2B2B2B")])

        self.tree = ttk.Treeview(
            tree_frame,
            columns=self.columns,
            show="tree headings",
            selectmode="browse",
            style="Custom.Treeview"
        )
        # Unique field column
        self.tree.heading("#0", text=self.unique_field,
                        command=lambda: self.sort_column(self.unique_field))
        self.tree.column("#0", width=180, anchor="w")
        # Other columns
        for col in self.columns:
            self.tree.heading(col, text=col,
                            command=lambda c=col: self.sort_column(c))
            self.tree.column(col, width=150, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<ButtonPress-1>", self.on_tree_click)
        self.tree.bind("<B1-Motion>", self.on_tree_drag)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_drop)
        self.tree.bind("<Control-c>", lambda e: self.copy_item(self.tree.focus()))
        self.tree.bind("<Control-v>", lambda e: self.paste_item(self.tree.focus() or None))
        self.copied_item = None
        self.dragging_iid = None

        self._tooltip = _ToolTip(self.tree)

        self.refresh_list()
    
    def show_portrait_window(self, iid):
        item = next((it for it in self.filtered_items
                    if sanitize_id(str(it.get(self.unique_field, ""))) == iid),
                    None)
        if not item:
            messagebox.showerror("Error", "Item not found.")
            return
        path = item.get("Portrait", "")
        title = str(item.get(self.unique_field, ""))
        # Delegate to our new helper
        show_portrait(path, title)

    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        self.batch_index = 0
        self.batch_size = 50
        if self.group_column:
            self.insert_grouped_items()
        else:
            self.insert_next_batch()

    def on_tree_click(self, event):
        if self.group_column or self.filtered_items != self.items:
            self.dragging_iid = None
            return
        self.dragging_iid = self.tree.identify_row(event.y)
        self.start_index = self.tree.index(self.dragging_iid) if self.dragging_iid else None

    def on_tree_drag(self, event):
        pass

    def on_tree_drop(self, event):
        if not self.dragging_iid:
            return
        if self.group_column or self.filtered_items != self.items:
            self.dragging_iid = None
            return
        target_iid = self.tree.identify_row(event.y)
        if not target_iid:
            target_index = len(self.tree.get_children()) - 1
        else:
            target_index = self.tree.index(target_iid)
        if target_index > self.start_index:
            target_index -= 1
        self.tree.move(self.dragging_iid, '', target_index)
        id_map = {sanitize_id(str(it.get(self.unique_field, ""))): idx for idx, it in enumerate(self.items)}
        old_index = id_map.get(self.dragging_iid)
        if old_index is not None:
            item = self.items.pop(old_index)
            self.items.insert(target_index, item)
            self.filtered_items = list(self.items)
            self.model_wrapper.save_items(self.items)
        self.dragging_iid = None

    def copy_item(self, iid):
        item = next((it for it in self.items if sanitize_id(str(it.get(self.unique_field, ""))) == iid), None)
        if item:
            self.copied_item = copy.deepcopy(item)

    def paste_item(self, iid=None):
        if not self.copied_item:
            return
        new_item = copy.deepcopy(self.copied_item)
        base_name = f"{new_item.get(self.unique_field, '')} Copy"
        existing = {sanitize_id(str(it.get(self.unique_field, ""))) for it in self.items}
        new_name = base_name
        counter = 1
        while sanitize_id(new_name) in existing:
            counter += 1
            new_name = f"{base_name} {counter}"
        new_item[self.unique_field] = new_name
        if iid:
            index = next((i for i, it in enumerate(self.items) if sanitize_id(str(it.get(self.unique_field, ""))) == iid), len(self.items)) + 1
        else:
            index = len(self.items)
        self.items.insert(index, new_item)
        self.model_wrapper.save_items(self.items)
        self.filter_items(self.search_var.get())

    def insert_next_batch(self):
        end = min(self.batch_index + self.batch_size, len(self.filtered_items))
        for i in range(self.batch_index, end):
            item = self.filtered_items[i]
            raw = item.get(self.unique_field, "")
            if isinstance(raw, dict):
                raw = raw.get("text", "")
            base_id = sanitize_id(raw or f"item_{int(time.time()*1000)}")
            iid = unique_iid(self.tree, base_id)
            name_text = self.clean_value(item.get(self.unique_field, ""))
            vals = tuple(self.clean_value(item.get(c, "")) for c in self.columns)
            try:
                self.tree.insert("", "end", iid=iid, text=name_text, values=vals)
            except Exception as e:
                print("[ERROR] inserting item:", e, iid, vals)
        self.batch_index = end
        if end < len(self.filtered_items):
            self.after(50, self.insert_next_batch)

    def insert_grouped_items(self):
        grouped = {}
        for item in self.filtered_items:
            key = self.clean_value(item.get(self.group_column, "")) or "Unknown"
            grouped.setdefault(key, []).append(item)

        for group_val in sorted(grouped.keys()):
            base_group_id = sanitize_id(f"group_{group_val}")
            group_id = unique_iid(self.tree, base_group_id)
            self.tree.insert("", "end", iid=group_id, text=group_val, open=False)
            for item in grouped[group_val]:
                raw = item.get(self.unique_field, "")
                if isinstance(raw, dict):
                    raw = raw.get("text", "")
                base_iid = sanitize_id(raw or f"item_{int(time.time()*1000)}")
                iid = unique_iid(self.tree, base_iid)
                name_text = self.clean_value(item.get(self.unique_field, ""))
                vals = tuple(self.clean_value(item.get(c, "")) for c in self.columns)
                try:
                    self.tree.insert(group_id, "end", iid=iid, text=name_text, values=vals)
                except Exception as e:
                    print("[ERROR] inserting item:", e, iid, vals)

    def clean_value(self, val):
        if val is None:
            return ""
        if isinstance(val, dict):
            return self.clean_value(val.get("text", ""))
        if isinstance(val, list):
            return ", ".join(self.clean_value(v) for v in val if v is not None)
        return str(val).replace("{", "").replace("}", "").strip()

    def sort_column(self, column_name):
        if not hasattr(self, "sort_directions"):
            self.sort_directions = {}
        asc = self.sort_directions.get(column_name, True)
        self.sort_directions[column_name] = not asc
        self.filtered_items.sort(
            key=lambda x: str(x.get(column_name, "")),
            reverse=not asc
        )
        self.refresh_list()

    def on_double_click(self, event):
        iid = self.tree.focus()
        if not iid:
            return
        item = next((it for it in self.filtered_items
                    if sanitize_id(str(it.get(self.unique_field, ""))) == iid),
                    None)
        if item:
            editor = GenericEditorWindow(
                self.master, item, self.template,
                self.model_wrapper, creation_mode=False
            )
            self.master.wait_window(editor)
            if getattr(editor, "saved", False):
                self.model_wrapper.save_items(self.items)
                self.refresh_list()

    def on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        # only show portrait if the item actually has one
        item = next((it for it in self.filtered_items
                    if sanitize_id(str(it.get(self.unique_field, ""))) == iid),
                    None)
        campaign_dir = ConfigHelper.get_campaign_dir()
        portrait_path = item.get("Portrait", "") if item else ""
        if portrait_path:
            portrait_path= os.path.join(campaign_dir, portrait_path)
            has_portrait = bool(portrait_path and os.path.isabs(portrait_path))
        else:
            has_portrait = False

        menu = tk.Menu(self, tearoff=0)
        if self.model_wrapper.entity_type == "scenarios":
            menu.add_command(
                label="Open in GM Screen",
                command=lambda: self.open_in_gm_screen(iid)
            )
        if has_portrait:
            menu.add_command(
                label="Show Portrait",
                command=lambda: self.show_portrait_window(iid)
            )
        menu.add_command(
            label="Copy",
            command=lambda: self.copy_item(iid)
        )
        menu.add_command(
            label="Paste",
            state=(tk.NORMAL if self.copied_item else tk.DISABLED),
            command=lambda: self.paste_item(iid)
        )
        menu.add_command(
            label="Delete",
            command=lambda: self.delete_item(iid)
        )
        menu.post(event.x_root, event.y_root)
    
    def delete_item(self, iid):
        self.items = [it for it in self.items
                    if sanitize_id(str(it.get(self.unique_field, ""))) != iid]
        self.model_wrapper.save_items(self.items)
        self.filter_items(self.search_var.get())

    def open_in_gm_screen(self, iid):
        item = next(
            (it for it in self.filtered_items
             if sanitize_id(str(it.get(self.unique_field, ""))) == iid),
            None
        )
        if not item:
            messagebox.showerror("Error", "Scenario not found.")
            return

        window = ctk.CTkToplevel(self)
        title = item.get("Title", item.get("Name", "Scenario"))
        window.title(f"Scenario: {title}")
        
        window.geometry("1920x1080+0+0")
        view = GMScreenView(window, scenario_item=item)
        view.pack(fill="both", expand=True)

    def add_item(self):
        new = {}
        if self.open_editor(new, True):
            self.items.append(new)
            self.model_wrapper.save_items(self.items)
            self.filter_items(self.search_var.get())

    def open_editor(self, item, creation_mode=False):
        ed = GenericEditorWindow(
            self.master, item, self.template,
            self.model_wrapper, creation_mode
        )
        self.master.wait_window(ed)
        return getattr(ed, "saved", False)

    def filter_items(self, query):
        q = query.strip().lower()
        if q:
            self.filtered_items = [
                it for it in self.items
                if any(q in self.clean_value(v).lower() for v in it.values())
            ]
        else:
            self.filtered_items = list(self.items)
        self.refresh_list()

    def add_items(self, items):
        added = 0
        for itm in items:
            nid = sanitize_id(str(itm.get(self.unique_field, "")))
            if not any(sanitize_id(str(i.get(self.unique_field, ""))) == nid
                    for i in self.items):
                self.items.append(itm)
                added += 1
        if added:
            self.model_wrapper.save_items(self.items)
            self.filter_items(self.search_var.get())

    def import_map_directory(self):
        dir_path = filedialog.askdirectory(title="Select Map Image Directory")
        if not dir_path:
            return

        supported = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
        new_items = []
        for filename in os.listdir(dir_path):
            src = os.path.join(dir_path, filename)
            if not os.path.isfile(src):
                continue
            if not filename.lower().endswith(supported):
                continue
            name, _ = os.path.splitext(filename)
            image_path = self._copy_map_image(src, name)
            item = {
                "Name": name,
                "Description": "",
                "Image": image_path,
                "FogMaskPath": "",
                "Tokens": "[]",
                "token_size": 0,
                "pan_x": 0,
                "pan_y": 0,
                "zoom": 1.0,
            }
            new_items.append(item)

        if new_items:
            self.add_items(new_items)
            messagebox.showinfo("Import Complete", f"Imported {len(new_items)} maps from directory.")
        else:
            messagebox.showwarning("No Images Found", "No supported image files were found in the selected directory.")

    def _copy_map_image(self, src_path, image_name):
        campaign_dir = ConfigHelper.get_campaign_dir()
        image_folder = os.path.join(campaign_dir, "assets", "images", "map_images")
        os.makedirs(image_folder, exist_ok=True)
        ext = os.path.splitext(src_path)[-1].lower()
        safe_name = image_name.replace(" ", "_")
        dest_filename = f"{safe_name}_{int(time.time()*1000)}{ext}"
        dest_path = os.path.join(image_folder, dest_filename)
        shutil.copy(src_path, dest_path)
        return os.path.join("assets/images/map_images", dest_filename)

    def choose_group_column(self):
        options = [self.unique_field] + [c for c in self.columns if c != self.unique_field]
        top = ctk.CTkToplevel(self)
        top.title("Group By")
        var = ctk.StringVar(value=self.group_column or options[0])
        ctk.CTkLabel(top, text="Select grouping column:").pack(padx=10, pady=10)
        menu = ctk.CTkOptionMenu(top, values=options, variable=var)
        menu.pack(padx=10, pady=5)

        def confirm():
            self.group_column = var.get()
            ConfigHelper.set("ListGrouping", self.model_wrapper.entity_type, self.group_column)
            top.destroy()
            self.refresh_list()

        ctk.CTkButton(top, text="OK", command=confirm).pack(pady=10)
        top.transient(self.master)
        top.lift()
        top.focus_force()
        
