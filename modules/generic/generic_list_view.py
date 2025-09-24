import re
import time
import os
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import copy
from PIL import Image
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.ui.image_viewer import show_portrait
from modules.ui.second_screen_display import show_entity_on_second_screen
from modules.helpers.config_helper import ConfigHelper
from modules.audio.entity_audio import play_entity_audio, stop_entity_audio
from modules.scenarios.gm_screen_view import GMScreenView
from modules.ai.authoring_wizard import AuthoringWizardView
import shutil
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_methods,
    log_warning,
    log_module_import,
)

log_module_import(__name__)

PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

try:
    RESAMPLE_MODE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1 fallback
    RESAMPLE_MODE = Image.LANCZOS


@log_function
def sanitize_id(s):
    return re.sub(r'[^a-zA-Z0-9]+', '_', str(s)).strip('_')

@log_function
def unique_iid(tree, base_id):
    """Return a unique iid for the given treeview based on base_id."""
    iid = base_id
    counter = 1
    while tree.exists(iid):
        counter += 1
        iid = f"{base_id}_{counter}"
    return iid

@log_methods
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

@log_methods
class GenericListView(ctk.CTkFrame):
    def __init__(self, master, model_wrapper, template, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.model_wrapper = model_wrapper
        self.template = template
        self.media_field = self._detect_media_field()
        os.makedirs(PORTRAIT_FOLDER, exist_ok=True)

        self.items = self.model_wrapper.load_items()
        self.filtered_items = list(self.items)

        # Load grouping from campaign-local settings
        cfg_grp = ConfigHelper.load_campaign_config()
        try:
            self.group_column = (
                cfg_grp.get("ListGrouping", self.model_wrapper.entity_type)
                if cfg_grp.has_section("ListGrouping") and cfg_grp.has_option("ListGrouping", self.model_wrapper.entity_type)
                else None
            )
        except Exception:
            self.group_column = None

        skip_for_unique = set()
        if self.media_field:
            skip_for_unique.add(self.media_field)
        self.unique_field = next(
            (f["name"] for f in self.template["fields"] if f["name"] not in skip_for_unique),
            None
        )
        skip_for_columns = {self.media_field, self.unique_field}
        self.columns = [
            f["name"] for f in self.template["fields"]
            if f["name"] not in skip_for_columns
        ]

        # --- Column configuration ---
        self.column_section = f"ColumnSettings_{self.model_wrapper.entity_type}"
        self._load_column_settings()

        # --- Display fields for second screen ---
        self.display_section = f"DisplayFields_{self.model_wrapper.entity_type}"
        self._load_display_fields()

        # --- Load saved list order ---
        self.order_section = f"ListOrder_{self.model_wrapper.entity_type}"
        self._load_list_order()

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
        if self.model_wrapper.entity_type in ("npcs", "scenarios"):
            ctk.CTkButton(search_frame, text="AI Wizard",
                          command=self.open_ai_wizard)\
                .pack(side="left", padx=5)
        ctk.CTkButton(search_frame, text="Group By",
            command=self.choose_group_column)\
        .pack(side="left", padx=5)

        # --- Treeview setup ---
        self.tree_frame = ctk.CTkFrame(self, fg_color="#2B2B2B")
        self.tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)

        self.grid_frame = ctk.CTkFrame(self, fg_color="#2B2B2B")
        self.grid_controls = ctk.CTkFrame(self.grid_frame, fg_color="#2B2B2B")
        self.grid_controls.pack(fill="x", padx=5, pady=(5, 0))
        self.grid_back_button = ctk.CTkButton(
            self.grid_controls,
            text="Back to List View",
            command=self.show_list_view,
        )
        self.grid_back_button.pack(side="left", padx=5, pady=5)
        self.grid_container = ctk.CTkScrollableFrame(
            self.grid_frame, fg_color="#2B2B2B"
        )
        self.grid_container.pack(fill="both", expand=True, padx=5, pady=5)
        self.grid_images = []

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
            self.tree_frame,
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

        self._apply_column_settings()

        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<ButtonPress-1>", self.on_button_press)
        self.tree.bind("<B1-Motion>", self.on_mouse_move)
        self.tree.bind("<ButtonRelease-1>", self.on_button_release)
        self.tree.bind("<Control-c>", lambda e: self.copy_item(self.tree.focus()))
        self.tree.bind("<Control-v>", lambda e: self.paste_item(self.tree.focus() or None))
        self.copied_item = None
        self.dragging_iid = None
        self.dragging_column = None
        # --- Row color setup ---
        self.color_options = {
            "Red": "#FF6666",
            "Orange": "#FFB266",
            "Yellow": "#FFFF66",
            "Green": "#66FF66",
            "Cyan": "#66FFFF",
            "Blue": "#6699FF",
            "Purple": "#CC66FF",
            "Pink": "#FF66CC",
            "Gray": "#CCCCCC",
            "Brown": "#996633",
        }
        for name, hex_color in self.color_options.items():
            self.tree.tag_configure(f"color_{name}", background=hex_color)

        self.row_color_section = f"RowColors_{self.model_wrapper.entity_type}"
        self.row_colors = {}
        cfg = ConfigHelper.load_campaign_config()
        if cfg.has_section(self.row_color_section):
            self.row_colors = dict(cfg.items(self.row_color_section))

        self._tooltip = _ToolTip(self.tree)

        self.footer_frame = ctk.CTkFrame(self)
        self.footer_frame.pack(fill="x", padx=5, pady=(0, 5))
        self.count_label = ctk.CTkLabel(self.footer_frame, text="")
        self.count_label.pack(side="left", padx=5)
        self.grid_toggle_button = ctk.CTkButton(
            self.footer_frame,
            text="Grid View",
            command=self.show_grid_view,
        )
        self.grid_toggle_button.pack(side="right", padx=5, pady=5)

        self.view_mode = "list"

        self.refresh_list()

    def show_portrait_window(self, iid):
        log_info(f"Showing portrait for {self.model_wrapper.entity_type} item: {iid}", func_name="GenericListView.show_portrait_window")
        item, _ = self._find_item_by_iid(iid)
        if not item:
            messagebox.showerror("Error", "Item not found.")
            return
        path = item.get("Portrait", "")
        title = str(item.get(self.unique_field, ""))
        show_portrait(path, title)

    def refresh_list(self):
        log_info(f"Refreshing list for {self.model_wrapper.entity_type}", func_name="GenericListView.refresh_list")
        self.tree.delete(*self.tree.get_children())
        self.batch_index = 0
        self.batch_size = 50
        if self.group_column:
            self.insert_grouped_items()
        else:
            self.insert_next_batch()
        if self.view_mode == "grid":
            self.populate_grid()
        self.update_entity_count()

    def update_entity_count(self):
        total = len(self.filtered_items)
        overall = len(self.items)
        text = f"Displaying {total} of {overall} entities"
        self.count_label.configure(text=text)

    def show_grid_view(self):
        if self.view_mode == "grid":
            return
        self.view_mode = "grid"
        self.tree_frame.pack_forget()
        self.grid_frame.pack(
            fill="both", expand=True, padx=5, pady=5, before=self.footer_frame
        )
        if self.grid_toggle_button.winfo_manager():
            self.grid_toggle_button.pack_forget()
        self.populate_grid()
        self.update_entity_count()

    def show_list_view(self):
        if self.view_mode == "list":
            return
        self.view_mode = "list"
        self.grid_frame.pack_forget()
        self.tree_frame.pack(
            fill="both", expand=True, padx=5, pady=5, before=self.footer_frame
        )
        if not self.grid_toggle_button.winfo_manager():
            self.grid_toggle_button.pack(side="right", padx=5, pady=5)
        self.update_entity_count()

    def populate_grid(self):
        if not hasattr(self, "grid_container"):
            return
        for child in self.grid_container.winfo_children():
            child.destroy()
        self.grid_images.clear()
        columns = 4
        for col in range(columns):
            self.grid_container.grid_columnconfigure(col, weight=1)
        if not self.filtered_items:
            ctk.CTkLabel(self.grid_container, text="No entities to display").grid(
                row=0, column=0, padx=10, pady=10, sticky="w"
            )
            return
        for idx, item in enumerate(self.filtered_items):
            row, col = divmod(idx, columns)
            card = ctk.CTkFrame(self.grid_container, corner_radius=8, fg_color="#1E1E1E")
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            image = self._load_grid_image(item)
            image_label = ctk.CTkLabel(card, text="", image=image)
            image_label.grid(row=0, column=0, padx=10, pady=(10, 5))
            name = self.clean_value(item.get(self.unique_field, "")) or "Unnamed"
            name_label = ctk.CTkLabel(
                card, text=name, justify="center", wraplength=160
            )
            name_label.grid(row=1, column=0, padx=10, pady=(0, 10))

            def bind_open(widget):
                widget.bind("<Double-Button-1>", lambda e, it=item: self._edit_item(it))

            bind_open(image_label)
            bind_open(card)
            bind_open(name_label)

    def _detect_media_field(self):
        fields = self.template.get("fields", []) if isinstance(self.template, dict) else []
        # Prefer explicit image type first.
        for field in fields:
            try:
                field_type = str(field.get("type", "")).strip().lower()
            except AttributeError:
                continue
            if field_type == "image":
                name = field.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        # Build lookup of normalized names so we can match Portrait/Image variants.
        normalized = {}
        for field in fields:
            name = field.get("name") if isinstance(field, dict) else None
            if not isinstance(name, str):
                continue
            stripped = name.strip()
            if not stripped:
                continue
            normalized[stripped.lower()] = stripped
        for key in ("portrait", "image"):
            if key in normalized:
                return normalized[key]
        for key in ("portrait", "image"):
            for lower, original in normalized.items():
                if key in lower:
                    return original
        return None

    def _resolve_media_path(self, media_path):
        if not media_path:
            return None
        if os.path.isabs(media_path) and os.path.exists(media_path):
            return media_path
        candidate = os.path.join(ConfigHelper.get_campaign_dir(), media_path)
        return candidate if os.path.exists(candidate) else None

    def _load_grid_image(self, item):
        media_value = ""
        if self.media_field:
            media_value = item.get(self.media_field, "")
        resolved = self._resolve_media_path(media_value)
        image_obj = None
        if resolved:
            try:
                with Image.open(resolved) as img:
                    image_obj = img.copy()
                image_obj.thumbnail((160, 160), RESAMPLE_MODE)
            except Exception:
                image_obj = None
        if image_obj is None:
            image_obj = Image.new("RGBA", (160, 160), color="#3A3A3A")
        ctk_image = ctk.CTkImage(light_image=image_obj, size=(160, 160))
        self.grid_images.append(ctk_image)
        return ctk_image

    def _edit_item(self, item):
        editor = GenericEditorWindow(
            self.master,
            item,
            self.template,
            self.model_wrapper,
            creation_mode=False,
        )
        self.master.wait_window(editor)
        if getattr(editor, "saved", False):
            self.model_wrapper.save_items(self.items)
            self.refresh_list()

    def on_button_press(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            col = self.tree.identify_column(event.x)
            if col != "#0":
                self.dragging_column = col
            else:
                self.dragging_column = None
        else:
            self.dragging_column = None
            self.on_tree_click(event)

    def on_mouse_move(self, event):
        if self.dragging_column:
            return
        self.on_tree_drag(event)

    def on_button_release(self, event):
        if self.dragging_column:
            target = self.tree.identify_column(event.x)
            if target != self.dragging_column:
                drag_name = self._column_from_ident(self.dragging_column)
                target_name = self._column_from_ident(target)
                if drag_name and drag_name in self.column_order:
                    cols = [c for c in self.column_order if c != drag_name]
                    if target_name in cols:
                        idx = cols.index(target_name)
                        cols.insert(idx, drag_name)
                    else:
                        cols.append(drag_name)
                    self.column_order = cols
                    self._apply_column_settings()
            self.dragging_column = None
        else:
            self.on_tree_drop(event)
        self._save_column_settings()

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
        id_map = {
            sanitize_id(str(it.get(self.unique_field, ""))).lower(): idx
            for idx, it in enumerate(self.items)
        }
        old_index = id_map.get(self.dragging_iid)
        if old_index is not None:
            item = self.items.pop(old_index)
            self.items.insert(target_index, item)
            self.filtered_items = list(self.items)
            self.model_wrapper.save_items(self.items)
            self._save_list_order()
        self.dragging_iid = None

    def copy_item(self, iid):
        item = next(
            (
                it
                for it in self.items
                if sanitize_id(str(it.get(self.unique_field, ""))).lower() == iid
            ),
            None,
        )
        if item:
            self.copied_item = copy.deepcopy(item)

    def paste_item(self, iid=None):
        if not self.copied_item:
            return
        new_item = copy.deepcopy(self.copied_item)
        base_name = f"{new_item.get(self.unique_field, '')} Copy"
        existing = {
            sanitize_id(str(it.get(self.unique_field, ""))).lower()
            for it in self.items
        }
        new_name = base_name
        counter = 1
        while sanitize_id(new_name).lower() in existing:
            counter += 1
            new_name = f"{base_name} {counter}"
        new_item[self.unique_field] = new_name
        if iid:
            index = (
                next(
                    (
                        i
                        for i, it in enumerate(self.items)
                        if sanitize_id(str(it.get(self.unique_field, ""))).lower()
                        == iid
                    ),
                    len(self.items),
                )
                + 1
            )
        else:
            index = len(self.items)
        self.items.insert(index, new_item)
        self.model_wrapper.save_items(self.items)
        self._save_list_order()
        self.filter_items(self.search_var.get())

    def insert_next_batch(self):
        end = min(self.batch_index + self.batch_size, len(self.filtered_items))
        for i in range(self.batch_index, end):
            item = self.filtered_items[i]
            raw = item.get(self.unique_field, "")
            if isinstance(raw, dict):
                raw = raw.get("text", "")
            base_id = sanitize_id(raw or f"item_{int(time.time()*1000)}").lower()
            iid = unique_iid(self.tree, base_id)
            name_text = self.clean_value(item.get(self.unique_field, ""))
            vals = tuple(self.clean_value(item.get(c, "")) for c in self.columns)
            try:
                self.tree.insert("", "end", iid=iid, text=name_text, values=vals)
                color = self.row_colors.get(base_id)
                if color:
                    self.tree.item(iid, tags=(f"color_{color}",))
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
                base_iid = sanitize_id(raw or f"item_{int(time.time()*1000)}").lower()
                iid = unique_iid(self.tree, base_iid)
                name_text = self.clean_value(item.get(self.unique_field, ""))
                vals = tuple(self.clean_value(item.get(c, "")) for c in self.columns)
                try:
                    self.tree.insert(group_id, "end", iid=iid, text=name_text, values=vals)
                    color = self.row_colors.get(base_iid)
                    if color:
                        self.tree.item(iid, tags=(f"color_{color}",))
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
        # Use the row under the mouse to avoid stale focus
        iid = self.tree.identify_row(event.y) or self.tree.focus()
        if not iid:
            return
        item, _ = self._find_item_by_iid(iid)
        if item:
            self._edit_item(item)

    def on_right_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            self._show_columns_menu(event)
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        self._show_item_menu(iid, event)

    def _show_item_menu(self, iid, event):
        item, base_id = self._find_item_by_iid(iid)
        campaign_dir = ConfigHelper.get_campaign_dir()
        portrait_path = item.get("Portrait", "") if item else ""
        if portrait_path:
            portrait_path = os.path.join(campaign_dir, portrait_path)
            has_portrait = bool(portrait_path and os.path.isabs(portrait_path))
        else:
            has_portrait = False

        menu = tk.Menu(self, tearoff=0)
        if self.model_wrapper.entity_type == "scenarios":
            menu.add_command(
                label="Open in GM Screen",
                command=lambda: self.open_in_gm_screen(iid)
            )
        if item:
            menu.add_command(
                label="Display on Second Screen",
                command=lambda: self.display_on_second_screen(iid)
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
        if item:
            color_menu = tk.Menu(menu, tearoff=0)
            for name in self.color_options.keys():
                color_menu.add_command(
                    label=name,
                    command=lambda n=name: self.set_row_color(iid, n)
                )
            color_menu.add_separator()
            color_menu.add_command(
                label="Clear Color",
                command=lambda: self.set_row_color(iid, None)
            )
            menu.add_cascade(label="Row Color", menu=color_menu)
            audio_value = self._get_audio_value(item)
            if audio_value:
                menu.add_separator()
                menu.add_command(
                    label="Play Audio",
                    command=lambda i=item: self.play_item_audio(i)
                )
                menu.add_command(label="Stop Audio", command=stop_entity_audio)
        menu.post(event.x_root, event.y_root)

    def display_on_second_screen(self, iid):
        log_info(f"Displaying {self.model_wrapper.entity_type} on second screen: {iid}", func_name="GenericListView.display_on_second_screen")
        item, _ = self._find_item_by_iid(iid)
        if not item:
            return
        title = str(item.get(self.unique_field, ""))
        fields = list(self.display_fields) if getattr(self, 'display_fields', None) else list(self.columns[:3])
        show_entity_on_second_screen(item=item, title=title, fields=fields)

    def _get_audio_value(self, item):
        if not item:
            return ""
        value = item.get("Audio") or ""
        if isinstance(value, dict):
            return value.get("path") or value.get("text") or ""
        return str(value).strip()

    def play_item_audio(self, item):
        audio_value = self._get_audio_value(item)
        if not audio_value:
            messagebox.showinfo("Audio", "No audio file configured for this entry.")
            return
        name = str(item.get(self.unique_field, "Entity"))
        if not play_entity_audio(audio_value, entity_label=name):
            messagebox.showwarning("Audio", f"Unable to play audio for {name}.")

    def delete_item(self, iid):
        log_info(f"Deleting {self.model_wrapper.entity_type} item: {iid}", func_name="GenericListView.delete_item")
        base_id = iid.lower()
        if base_id in self.row_colors:
            self._save_row_color(base_id, None)
        self.items = [
            it for it in self.items
            if sanitize_id(str(it.get(self.unique_field, ""))).lower() != base_id
        ]
        self.model_wrapper.save_items(self.items)
        self._save_list_order()
        self.filter_items(self.search_var.get())

    def open_in_gm_screen(self, iid):
        log_info(f"Opening {self.model_wrapper.entity_type} in GM screen: {iid}", func_name="GenericListView.open_in_gm_screen")
        item = next(
            (
                it
                for it in self.filtered_items
                if sanitize_id(str(it.get(self.unique_field, ""))).lower() == iid
            ),
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
        log_info(f"Adding new {self.model_wrapper.entity_type} item", func_name="GenericListView.add_item")
        new = {}
        if self.open_editor(new, True):
            self.items.append(new)
            self.model_wrapper.save_items(self.items)
            self._save_list_order()
            self.filter_items(self.search_var.get())

    def open_editor(self, item, creation_mode=False):
        log_info(f"Opening editor for {self.model_wrapper.entity_type} (creation={creation_mode})", func_name="GenericListView.open_editor")
        ed = GenericEditorWindow(
            self.master, item, self.template,
            self.model_wrapper, creation_mode
        )
        self.master.wait_window(ed)
        return getattr(ed, "saved", False)

    def filter_items(self, query):
        log_info(f"Filtering {self.model_wrapper.entity_type} with query: {query}", func_name="GenericListView.filter_items")
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
        log_info(f"Adding batch of {len(items)} items to {self.model_wrapper.entity_type}", func_name="GenericListView.add_items")
        added = 0
        for itm in items:
            nid = sanitize_id(str(itm.get(self.unique_field, ""))).lower()
            if not any(
                sanitize_id(str(i.get(self.unique_field, ""))).lower() == nid
                for i in self.items
            ):
                self.items.append(itm)
                added += 1
        if added:
            self.model_wrapper.save_items(self.items)
            self._save_list_order()
            self.filter_items(self.search_var.get())

    def import_map_directory(self):
        log_info("Importing maps from directory", func_name="GenericListView.import_map_directory")
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
        log_info(f"Selecting group column for {self.model_wrapper.entity_type}", func_name="GenericListView.choose_group_column")
        options = ["None", self.unique_field] + [c for c in self.columns if c != self.unique_field]
        top = ctk.CTkToplevel(self)
        top.title("Group By")
        var = ctk.StringVar(value=self.group_column or "None")
        ctk.CTkLabel(top, text="Select grouping column:").pack(padx=10, pady=10)
        menu = ctk.CTkOptionMenu(top, values=options, variable=var)
        menu.pack(padx=10, pady=5)

        def confirm():
            selection = var.get()
            if selection == "None":
                self.group_column = None
                cfg = ConfigHelper.load_campaign_config()
                if not cfg.has_section("ListGrouping"):
                    cfg.add_section("ListGrouping")
                cfg.set("ListGrouping", self.model_wrapper.entity_type, "")
                with open(ConfigHelper.get_campaign_settings_path(), "w", encoding="utf-8") as f:
                    cfg.write(f)
            else:
                self.group_column = selection
                cfg = ConfigHelper.load_campaign_config()
                if not cfg.has_section("ListGrouping"):
                    cfg.add_section("ListGrouping")
                cfg.set("ListGrouping", self.model_wrapper.entity_type, self.group_column)
                with open(ConfigHelper.get_campaign_settings_path(), "w", encoding="utf-8") as f:
                    cfg.write(f)
            top.destroy()
            self.refresh_list()

        ctk.CTkButton(top, text="OK", command=confirm).pack(pady=10)
        top.transient(self.master)
        top.lift()
        top.focus_force()

    def open_ai_wizard(self):
        log_info(f"Launching AI wizard for {self.model_wrapper.entity_type}", func_name="GenericListView.open_ai_wizard")
        """Open the AI Authoring Wizard in a modal window, scoped to this entity list."""
        top = ctk.CTkToplevel(self)
        top.title("AI Authoring Wizard")
        top.geometry("1000x720")
        top.lift(); top.focus_force(); top.grab_set()
        frame = AuthoringWizardView(top)
        frame.pack(fill="both", expand=True)
        try:
            frame.select_for(self.model_wrapper.entity_type)
        except Exception:
            pass
        def on_close():
            try:
                top.grab_release()
            except Exception:
                pass
            top.destroy()
        top.protocol("WM_DELETE_WINDOW", on_close)

    def _find_item_by_iid(self, iid):
        # Prefer exact match on sanitized ID
        for it in self.filtered_items:
            base_id = self._get_base_id(it)
            if iid == base_id:
                return it, base_id

        # If the iid has a duplicate suffix like "_2", strip it and try again
        m = re.match(r"^(.*)_\d+$", iid or "")
        if m:
            base = m.group(1)
            for it in self.filtered_items:
                if self._get_base_id(it) == base:
                    return it, base

        return None, None

    def _get_base_id(self, item):
        raw = item.get(self.unique_field, "")
        if isinstance(raw, dict):
            raw = raw.get("text", "")
        return sanitize_id(raw).lower()

    def _column_from_ident(self, ident):
        if ident == "#0":
            return None
        try:
            idx = int(ident.replace("#", "")) - 1
        except ValueError:
            return None
        display = list(self.tree["displaycolumns"])
        if 0 <= idx < len(display):
            return display[idx]
        return None

    def _load_column_settings(self):
        cfg = ConfigHelper.load_campaign_config()
        self.column_order = list(self.columns)
        self.hidden_columns = set()
        self.column_widths = {}
        if cfg.has_section(self.column_section):
            order_str = cfg.get(self.column_section, "order", fallback="")
            if order_str:
                loaded = [c for c in order_str.split(",") if c in self.columns]
                for c in self.columns:
                    if c not in loaded:
                        loaded.append(c)
                self.column_order = loaded
            hidden_str = cfg.get(self.column_section, "hidden", fallback="")
            if hidden_str:
                self.hidden_columns = {c for c in hidden_str.split(",") if c in self.columns}
            for col in ["#0"] + self.columns:
                key = f"width_{sanitize_id(col)}"
                w = cfg.get(self.column_section, key, fallback="")
                try:
                    self.column_widths[col] = int(w)
                except ValueError:
                    pass

    def _apply_column_settings(self):
        for col, width in self.column_widths.items():
            try:
                self.tree.column(col, width=width)
            except tk.TclError:
                continue
        display = [c for c in self.column_order if c not in self.hidden_columns]
        self.tree["displaycolumns"] = display

    def _save_column_settings(self):
        cfg = ConfigHelper.load_campaign_config()
        section = self.column_section
        if not cfg.has_section(section):
            cfg.add_section(section)
        cfg.set(section, "order", ",".join(self.column_order))
        cfg.set(section, "hidden", ",".join(self.hidden_columns))
        for col in ["#0"] + list(self.columns):
            key = f"width_{sanitize_id(col)}"
            try:
                width = self.tree.column("#0" if col == "#0" else col, "width")
                cfg.set(section, key, str(width))
            except tk.TclError:
                continue
        with open(ConfigHelper.get_campaign_settings_path(), "w", encoding="utf-8") as f:
            cfg.write(f)
        try:
            ConfigHelper._campaign_mtime = os.path.getmtime(ConfigHelper.get_campaign_settings_path())
        except OSError:
            pass

    def _show_columns_menu(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Columns...", command=self._open_column_chooser)
        menu.add_command(label="Display Fields...", command=self._open_display_fields_chooser)
        menu.post(event.x_root, event.y_root)

    def _open_column_chooser(self):
        top = ctk.CTkToplevel(self)
        top.title("Columns")
        vars = {}
        for col in self.columns:
            var = tk.BooleanVar(value=col not in self.hidden_columns)
            vars[col] = var
            chk = ctk.CTkCheckBox(top, text=col, variable=var)
            chk.pack(anchor="w", padx=10, pady=2)

        def apply():
            self.hidden_columns = {c for c, v in vars.items() if not v.get()}
            self._apply_column_settings()
            self._save_column_settings()
            top.destroy()

        ctk.CTkButton(top, text="OK", command=apply).pack(pady=5)
        top.transient(self.master)
        top.lift()
        top.focus_force()

    def _open_display_fields_chooser(self):
        top = ctk.CTkToplevel(self)
        top.title("Display Fields (Second Screen)")
        vars = {}
        available = list(self.columns)
        # Allow portrait selection as well
        if "Portrait" not in available:
            available_with_portrait = ["Portrait"] + available
        else:
            available_with_portrait = available
        for col in available_with_portrait:
            var = tk.BooleanVar(value=col in getattr(self, 'display_fields', set()))
            vars[col] = var
            chk = ctk.CTkCheckBox(top, text=col, variable=var)
            chk.pack(anchor="w", padx=10, pady=2)

        def apply():
            self.display_fields = {c for c, v in vars.items() if v.get()}
            self._save_display_fields()
            top.destroy()

        ctk.CTkButton(top, text="OK", command=apply).pack(pady=5)
        top.transient(self.master)
        top.lift()
        top.focus_force()

    def _load_list_order(self):
        cfg = ConfigHelper.load_campaign_config()
        self.list_order = {}
        if cfg.has_section(self.order_section):
            for key, val in cfg.items(self.order_section):
                try:
                    self.list_order[key] = int(val)
                except ValueError:
                    continue
        self.items.sort(key=lambda it: self.list_order.get(self._get_base_id(it), float('inf')))
        self.filtered_items = list(self.items)

    def _save_list_order(self):
        cfg = ConfigHelper.load_campaign_config()
        section = self.order_section
        if not cfg.has_section(section):
            cfg.add_section(section)
        else:
            for opt in cfg.options(section):
                cfg.remove_option(section, opt)
        for idx, item in enumerate(self.items):
            cfg.set(section, self._get_base_id(item), str(idx))
        with open(ConfigHelper.get_campaign_settings_path(), "w", encoding="utf-8") as f:
            cfg.write(f)
        try:
            ConfigHelper._campaign_mtime = os.path.getmtime(ConfigHelper.get_campaign_settings_path())
        except OSError:
            pass

    def _load_display_fields(self):
        cfg = ConfigHelper.load_campaign_config()
        self.display_fields = set()
        if cfg.has_section(self.display_section):
            raw = cfg.get(self.display_section, "fields", fallback="")
            if raw:
                self.display_fields = {c for c in raw.split(",") if c}
        if not self.display_fields:
            self.display_fields = set(self.columns[:3])

    def _save_display_fields(self):
        cfg = ConfigHelper.load_campaign_config()
        section = self.display_section
        if not cfg.has_section(section):
            cfg.add_section(section)
        cfg.set(section, "fields", ",".join([c for c in self.display_fields]))
        with open(ConfigHelper.get_campaign_settings_path(), "w", encoding="utf-8") as f:
            cfg.write(f)
        try:
            ConfigHelper._campaign_mtime = os.path.getmtime(ConfigHelper.get_campaign_settings_path())
        except OSError:
            pass

    def set_row_color(self, iid, color_name):
        item, base_id = self._find_item_by_iid(iid)
        if not base_id:
            return
        if color_name:
            self.tree.item(iid, tags=(f"color_{color_name}",))
        else:
            self.tree.item(iid, tags=())
        # Deselect the row so the new color is visible immediately
        self.tree.selection_remove(iid)
        self.tree.focus("")
        self._save_row_color(base_id, color_name)

    def _save_row_color(self, base_id, color_name):
        cfg = ConfigHelper.load_campaign_config()
        section = self.row_color_section
        if not cfg.has_section(section):
            cfg.add_section(section)
        if color_name:
            cfg.set(section, base_id, color_name)
            self.row_colors[base_id] = color_name
        else:
            if cfg.has_option(section, base_id):
                cfg.remove_option(section, base_id)
            self.row_colors.pop(base_id, None)
        with open(ConfigHelper.get_campaign_settings_path(), "w", encoding="utf-8") as f:
            cfg.write(f)
        try:
            ConfigHelper._campaign_mtime = os.path.getmtime(ConfigHelper.get_campaign_settings_path())
        except OSError:
            pass
        
