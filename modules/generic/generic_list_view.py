import json
import re
import time
import os
import threading
import customtkinter as ctk
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog
import copy
from PIL import Image
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.ui.image_viewer import show_portrait
from modules.ui.second_screen_display import show_entity_on_second_screen
from modules.helpers.config_helper import ConfigHelper
from modules.audio.entity_audio import (
    get_entity_audio_value,
    play_entity_audio,
    stop_entity_audio,
)
from modules.scenarios.gm_screen_view import GMScreenView
from modules.scenarios.gm_layout_manager import GMScreenLayoutManager
from modules.ai.authoring_wizard import AuthoringWizardView
from modules.ai.local_ai_client import LocalAIClient
import shutil
from modules.helpers.template_loader import load_template
from modules.helpers.logging_helper import (
    log_debug,
    log_function,
    log_info,
    log_methods,
    log_warning,
    log_module_import,
)
from modules.generic.object_shelf_view import ObjectShelfView

log_module_import(__name__)

PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

SCENARIO_LINK_FIELDS = {
    "npcs": "NPCs",
    "creatures": "Creatures",
    "factions": "Factions",
    "places": "Places",
    "objects": "Objects",
}

GM_SCREEN_ENTITY_TYPES = {
    "scenarios": "Scenarios",
    "pcs": "PCs",
    "npcs": "NPCs",
    "creatures": "Creatures",
    "factions": "Factions",
    "places": "Places",
    "objects": "Objects",
    "clues": "Clues",
    "informations": "Informations",
}

ENTITY_DISPLAY_LABELS = {
    "scenarios": "Scenarios",
    "pcs": "PCs",
    "npcs": "NPCs",
    "creatures": "Creatures",
    "factions": "Factions",
    "places": "Places",
    "objects": "Objects",
    "clues": "Clues",
    "informations": "Informations",
    "maps": "Maps",
}

OBJECT_CATEGORY_ALLOWED = [
    "Weapon",
    "Armor",
    "Shield",
    "Ammunition",
    "Tool",
    "Kit",
    "Resource",
    "Food",
    "Drink",
    "Healing",
    "Potion",
    "Drug",
    "Magic Item",
    "Accessory",
    "Jewelry",
    "Clothing",
    "Scroll",
    "Wand",
    "Staff",
    "Ring",
    "Wondrous Item",
    "Explosive",
    "Poison",
    "Consumable",
    "Container",
    "Trinket",
    "Miscellaneous",
]


AI_CATEGORIZE_BATCH_SIZE = 20


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
    def __init__(self, widget, text_resolver=None):
        self.widget = widget
        self.tipwindow = None
        self.text = ""
        self.text_resolver = text_resolver
        widget.bind("<Motion>", self._on_motion)
        widget.bind("<Leave>", self._on_leave)

    def _on_motion(self, event):
        rowid = self.widget.identify_row(event.y)
        colid = self.widget.identify_column(event.x)
        if rowid and colid:
            if callable(self.text_resolver):
                txt = self.text_resolver(rowid, colid)
            elif colid == "#0":
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
        self.selected_iids = set()
        self._base_to_iids = {}
        self._suppress_tree_select_event = False
        self.grid_cards = []
        self.copied_items = []
        self.ai_categorize_button = None
        self._ai_categorize_running = False

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
        self._search_frame_pack_kwargs = {"fill": "x", "padx": (5, 45), "pady": 5}
        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.pack(**self._search_frame_pack_kwargs)
        ctk.CTkLabel(self.search_frame, text="Search:").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(self.search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=5)
        search_entry.bind("<Return>", lambda e: self.filter_items(self.search_var.get()))
        ctk.CTkButton(self.search_frame, text="Filter",
            command=lambda: self.filter_items(self.search_var.get()))\
        .pack(side="left", padx=5)
        ctk.CTkButton(self.search_frame, text="Add",
            command=self.add_item)\
        .pack(side="left", padx=5)
        ctk.CTkButton(self.search_frame, text="Merge Duplicates",
            command=self.merge_duplicate_entities)\
        .pack(side="left", padx=5)
        if self.model_wrapper.entity_type == "objects":
            self.ai_categorize_button = ctk.CTkButton(
                self.search_frame,
                text="AI Categorize",
                command=self.ai_categorize_objects,
            )
            self.ai_categorize_button.pack(side="left", padx=5)
        if self.model_wrapper.entity_type == "maps":
            ctk.CTkButton(self.search_frame, text="Import Directory",
                          command=self.import_map_directory)\
                .pack(side="left", padx=5)
        if self.model_wrapper.entity_type in ("npcs", "scenarios"):
            ctk.CTkButton(self.search_frame, text="AI Wizard",
                          command=self.open_ai_wizard)\
                .pack(side="left", padx=5)
        ctk.CTkButton(self.search_frame, text="Group By",
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

        self.shelf_view = None
        if self.model_wrapper.entity_type == "objects":
            self.shelf_view = ObjectShelfView(self, OBJECT_CATEGORY_ALLOWED)

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
        style.map(
            "Custom.Treeview",
            background=[("selected", "#FFFFFF")],
            foreground=[("selected", "#000000")],
            focuscolor=[("selected", "white"), ("!selected", "")],
            focusthickness=[("selected", 1), ("!selected", 0)],
        )

        self.tree = ttk.Treeview(
            self.tree_frame,
            columns=self.columns,
            show="tree headings",
            selectmode="extended",
            style="Custom.Treeview"
        )
        self._last_tree_selection = set()
        self._tree_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self._ellipsis = "..."
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
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_selection_changed)
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
        self.tree.tag_configure("selected_row", background="#FFFFFF", foreground="#000000")

        self.row_color_section = f"RowColors_{self.model_wrapper.entity_type}"
        self.row_colors = {}
        cfg = ConfigHelper.load_campaign_config()
        if cfg.has_section(self.row_color_section):
            self.row_colors = dict(cfg.items(self.row_color_section))

        self._cell_texts = {}
        self._tooltip = _ToolTip(self.tree, self._get_cell_text)

        self.footer_frame = ctk.CTkFrame(self)
        self.footer_frame.pack(fill="x", padx=5, pady=(0, 5))
        self.count_label = ctk.CTkLabel(self.footer_frame, text="")
        self.count_label.pack(side="left", padx=5)
        self.selection_label = ctk.CTkLabel(self.footer_frame, text="")
        self.selection_label.pack(side="left", padx=5)
        self.bulk_action_button = ctk.CTkButton(
            self.footer_frame,
            text="Bulk Actions",
            command=self._open_bulk_menu,
            state=tk.DISABLED,
        )
        self.bulk_action_button.pack(side="right", padx=5, pady=5)
        self.view_toggle_frame = ctk.CTkFrame(
            self.footer_frame, fg_color="transparent"
        )
        self.view_toggle_frame.pack(side="right", padx=5, pady=5)
        self.view_toggle_buttons = {}
        self._create_view_toggle_button("list", "List")
        self._create_view_toggle_button("grid", "Grid")
        if self.model_wrapper.entity_type == "objects":
            self._create_view_toggle_button("shelf", "Shelf")

        self.view_mode = "list"

        self.refresh_list()
        self._update_view_toggle_state()

    def _hide_search_frame(self):
        if getattr(self, "search_frame", None) and self.search_frame.winfo_manager():
            self.search_frame.pack_forget()

    def _show_search_frame(self):
        if getattr(self, "search_frame", None) and not self.search_frame.winfo_manager():
            kwargs = dict(self._search_frame_pack_kwargs)
            if hasattr(self, "tree_frame"):
                kwargs["before"] = self.tree_frame
            self.search_frame.pack(**kwargs)

    def reload_from_db(self):
        """Reload items from the model wrapper and refresh the view."""
        log_info(
            f"Reloading {self.model_wrapper.entity_type} list from database",
            func_name="GenericListView.reload_from_db",
        )
        self.items = self.model_wrapper.load_items()
        self.filtered_items = list(self.items)
        self.selected_iids.clear()
        self.refresh_list()
        self._update_bulk_controls()

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
        self._last_tree_selection = set()
        self._cell_texts.clear()
        self._base_to_iids = {}
        self.batch_index = 0
        self.batch_size = 50
        if self.group_column:
            self.insert_grouped_items()
        else:
            self.insert_next_batch()
        if self.view_mode == "grid":
            self.populate_grid()
        elif self.view_mode == "shelf" and self.shelf_view:
            self.shelf_view.populate()
        self.update_entity_count()
        self._apply_selection_to_tree()
        self._refresh_grid_selection()
        if self.shelf_view:
            self.shelf_view.refresh_selection()
        self._update_bulk_controls()

    def update_entity_count(self):
        total = len(self.filtered_items)
        overall = len(self.items)
        text = f"Displaying {total} of {overall} entities"
        self.count_label.configure(text=text)
        if self.shelf_view:
            self.shelf_view.update_summary()

    def _create_view_toggle_button(self, mode, label):
        if getattr(self, "view_toggle_frame", None) is None:
            return
        button = ctk.CTkButton(
            self.view_toggle_frame,
            text=label,
            command=lambda m=mode: self._set_view_mode(m),
            corner_radius=16,
            width=90,
            fg_color="#2F2F2F",
            hover_color="#1F6AA5",
            border_width=1,
            border_color="#1F6AA5",
        )
        button.pack(side="left", padx=4)
        self.view_toggle_buttons[mode] = button

    def _set_view_mode(self, mode):
        if mode == self.view_mode:
            return
        if mode == "grid":
            self.show_grid_view()
        elif mode == "shelf":
            self.show_shelf_view()
        else:
            self.show_list_view()

    def _update_view_toggle_state(self):
        for mode, button in self.view_toggle_buttons.items():
            if not button or not button.winfo_exists():
                continue
            if mode == self.view_mode:
                button.configure(state=tk.DISABLED, fg_color="#1F6AA5")
            else:
                button.configure(state=tk.NORMAL, fg_color="#2F2F2F")

    def show_grid_view(self):
        if self.view_mode == "grid" and self.grid_frame.winfo_manager():
            return
        self.view_mode = "grid"
        self._show_search_frame()
        self.tree_frame.pack_forget()
        self.grid_frame.pack(
            fill="both", expand=True, padx=5, pady=5, before=self.footer_frame
        )
        if self.shelf_view:
            self.shelf_view.hide()
        self.populate_grid()
        self._refresh_grid_selection()
        self.update_entity_count()
        self._update_view_toggle_state()

    def show_list_view(self):
        if self.view_mode == "list" and self.tree_frame.winfo_manager():
            return
        self.view_mode = "list"
        self._show_search_frame()
        self.grid_frame.pack_forget()
        self.tree_frame.pack(
            fill="both", expand=True, padx=5, pady=5, before=self.footer_frame
        )
        if self.shelf_view:
            self.shelf_view.hide()
        self.update_entity_count()
        self._update_view_toggle_state()

    def show_shelf_view(self):
        if not self.shelf_view or not self.shelf_view.is_available():
            return
        if self.view_mode == "shelf" and self.shelf_view.is_visible():
            return
        self.view_mode = "shelf"
        self._hide_search_frame()
        self.tree_frame.pack_forget()
        self.grid_frame.pack_forget()
        self.shelf_view.show(before_widget=self.footer_frame)
        self.shelf_view.populate()
        self.shelf_view.refresh_selection()
        self.shelf_view.start_visibility_monitor()
        self.update_entity_count()
        self._update_view_toggle_state()

    def populate_grid(self):
        if not hasattr(self, "grid_container"):
            return
        for child in self.grid_container.winfo_children():
            child.destroy()
        self.grid_images.clear()
        self.grid_cards = []
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
            card = ctk.CTkFrame(
                self.grid_container,
                corner_radius=8,
                fg_color="#1E1E1E",
                border_width=1,
                border_color="#1E1E1E",
            )
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

            def bind_select(widget):
                widget.bind("<Button-1>", lambda e, it=item: self.on_grid_click(e, it))

            bind_select(image_label)
            bind_select(card)
            bind_select(name_label)
            base_id = self._get_base_id(item)
            if base_id:
                self.grid_cards.append({"base_id": base_id, "card": card})

    def on_grid_click(self, _event, item):
        self.toggle_item_selection(item)

    def toggle_item_selection(self, item):
        base_id = self._get_base_id(item)
        if not base_id:
            return
        if base_id in self.selected_iids:
            self.selected_iids.remove(base_id)
        else:
            self.selected_iids.add(base_id)
        self._apply_selection_to_tree()
        self._update_bulk_controls()
        self._refresh_grid_selection()
        if self.shelf_view:
            self.shelf_view.refresh_selection()

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
        """Copy the currently selected items or the provided iid."""
        selection = list(self.tree.selection())
        if selection:
            try:
                selection.sort(key=self.tree.index)
            except tk.TclError:
                pass
        elif iid:
            selection = [iid]
        else:
            selection = []

        copied = []
        for selected_iid in selection:
            item, _ = self._find_item_by_iid(selected_iid)
            if item:
                copied.append(copy.deepcopy(item))

        self.copied_items = copied

    def paste_item(self, iid=None):
        if not self.copied_items:
            return
        existing = {
            sanitize_id(str(it.get(self.unique_field, ""))).lower()
            for it in self.items
        }

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

        insert_index = index
        for original in self.copied_items:
            new_item = copy.deepcopy(original)
            base_value = new_item.get(self.unique_field, "")
            if isinstance(base_value, dict):
                base_value = base_value.get("text", "")
            base_name = f"{base_value} Copy".strip()
            if not base_name.strip():
                base_name = "Copy"
            new_name = base_name
            counter = 1
            while sanitize_id(new_name).lower() in existing:
                counter += 1
                new_name = f"{base_name} {counter}"
            new_item[self.unique_field] = new_name
            existing.add(sanitize_id(new_name).lower())
            self.items.insert(insert_index, new_item)
            insert_index += 1

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
            name_text = self._format_cell("#0", item.get(self.unique_field, ""), iid)
            vals = tuple(
                self._format_cell(c, item.get(c, ""), iid) for c in self.columns
            )
            try:
                self.tree.insert("", "end", iid=iid, text=name_text, values=vals)
                color = self.row_colors.get(base_id)
                if color:
                    self.tree.item(iid, tags=(f"color_{color}",))
                self._register_tree_iid(base_id, iid)
                if base_id in self.selected_iids:
                    self.tree.selection_add(iid)
            except Exception as e:
                print("[ERROR] inserting item:", e, iid, vals)
        self.batch_index = end
        if end < len(self.filtered_items):
            self.after(50, self.insert_next_batch)
        self._update_tree_selection_tags()

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
                name_text = self._format_cell("#0", item.get(self.unique_field, ""), iid)
                vals = tuple(
                    self._format_cell(c, item.get(c, ""), iid) for c in self.columns
                )
                try:
                    self.tree.insert(group_id, "end", iid=iid, text=name_text, values=vals)
                    color = self.row_colors.get(base_iid)
                    if color:
                        self.tree.item(iid, tags=(f"color_{color}",))
                    self._register_tree_iid(base_iid, iid)
                    if base_iid in self.selected_iids:
                        self.tree.selection_add(iid)
                except Exception as e:
                    print("[ERROR] inserting item:", e, iid, vals)
        self._update_tree_selection_tags()

    def clean_value(self, val):
        if val is None:
            return ""
        if isinstance(val, dict):
            return self.clean_value(val.get("text", ""))
        if isinstance(val, list):
            return ", ".join(self.clean_value(v) for v in val if v is not None)
        return str(val).replace("{", "").replace("}", "").strip()

    def _normalize_unique_value(self, value):
        if value is None:
            return ""
        if isinstance(value, dict):
            value = value.get("text", "")
        elif isinstance(value, (list, tuple, set)):
            value = " ".join(str(v) for v in value)
        return str(value).strip().lower()

    def _merge_duplicate_group(self, group):
        base = copy.deepcopy(group[0])
        for item in group[1:]:
            for field, value in item.items():
                existing = base.get(field)
                base[field] = self._merge_field_value(existing, value)
        return base

    def _merge_field_value(self, existing, new):
        if self._is_empty_value(existing):
            return copy.deepcopy(new)
        if self._is_empty_value(new):
            return existing

        if isinstance(existing, dict) and isinstance(new, dict):
            merged = copy.deepcopy(existing)
            for key, value in new.items():
                if key in merged:
                    merged[key] = self._merge_field_value(merged[key], value)
                else:
                    merged[key] = copy.deepcopy(value)
            return merged

        if isinstance(existing, list) and isinstance(new, list):
            merged_list = list(existing)
            for item in new:
                if item not in merged_list:
                    merged_list.append(item)
            return merged_list

        if isinstance(existing, set) and isinstance(new, set):
            return existing | new

        if isinstance(existing, tuple) and isinstance(new, tuple):
            merged_items = list(existing)
            for item in new:
                if item not in merged_items:
                    merged_items.append(item)
            return tuple(merged_items)

        if isinstance(existing, (int, float)) and isinstance(new, (int, float)):
            if existing == 0 and new != 0:
                return new
            return existing

        if isinstance(existing, str) and isinstance(new, str):
            existing_clean = existing.strip()
            new_clean = new.strip()
            if not existing_clean:
                return new
            if not new_clean:
                return existing
            existing_parts = [part.strip() for part in existing.splitlines() if part.strip()]
            if any(part.lower() == new_clean.lower() for part in existing_parts):
                return existing
            if existing.endswith("\n") or not existing:
                return existing + new
            return f"{existing}\n{new}"

        if existing == new:
            return existing

        return existing

    def _is_empty_value(self, value):
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) == 0
        return False

    def _normalize_column_id(self, column_id):
        """Translate Treeview #n identifiers into configured column names."""
        if column_id == "#0":
            return column_id
        if column_id and column_id.startswith("#"):
            try:
                index = int(column_id[1:]) - 1
            except ValueError:
                return column_id
            columns = self.tree["columns"]
            if 0 <= index < len(columns):
                return columns[index]
        return column_id

    def _get_cell_text(self, iid, column_id):
        column_key = self._normalize_column_id(column_id)
        if (iid, column_key) in self._cell_texts:
            return self._cell_texts[(iid, column_key)]
        if column_key == "#0":
            return self.tree.item(iid, "text")
        return self.tree.set(iid, column_key)

    def _format_cell(self, column_id, value, iid=None):
        """Prepare a value for display in the tree, truncating if needed."""
        text = self.clean_value(value)
        if iid is not None:
            self._cell_texts[(iid, column_id)] = text
        return self._truncate_text(text, column_id)

    def _truncate_text(self, text, column_id):
        if not text:
            return ""
        try:
            width = self.tree.column(column_id, "width")
        except Exception:
            width = 0
        if width <= 0:
            return text

        available = max(width - 12, 0)
        if self._tree_font.measure(text) <= available:
            return text

        ellipsis_width = self._tree_font.measure(self._ellipsis)
        if ellipsis_width >= available:
            return self._ellipsis if ellipsis_width <= width else ""

        truncated = []
        current_width = 0
        for char in text:
            char_width = self._tree_font.measure(char)
            if current_width + char_width > available - ellipsis_width:
                break
            truncated.append(char)
            current_width += char_width
        return "".join(truncated) + self._ellipsis

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
        iid = self.tree.identify_row(event.y)
        if not iid:
            # Fallback to the active selection or current focus
            selection = self.tree.selection()
            iid = selection[0] if selection else self.tree.focus()
        if not iid:
            return
        # Ensure the identified row becomes the active selection for consistent focus behaviour
        self.tree.selection_set(iid)
        self.tree.focus(iid)
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
        current = set(self.tree.selection())
        if iid not in current:
            self.tree.selection_set(iid)
        else:
            self.tree.focus(iid)
        self._show_item_menu(iid, event)

    def _show_item_menu(self, iid, event):
        item, base_id = self._find_item_by_iid(iid)
        campaign_dir = ConfigHelper.get_campaign_dir()
        portrait_path = item.get("Portrait", "") if item else ""
        if portrait_path:
            if not os.path.isabs(portrait_path):
                portrait_path = os.path.join(campaign_dir, portrait_path)
            has_portrait = os.path.exists(portrait_path)
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
            state=(tk.NORMAL if self.copied_items else tk.DISABLED),
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
        return get_entity_audio_value(item)

    def play_item_audio(self, item):
        audio_value = self._get_audio_value(item)
        if not audio_value:
            messagebox.showinfo("Audio", "No audio file configured for this entry.")
            return
        name = str(item.get(self.unique_field, "Entity"))
        if not play_entity_audio(audio_value, entity_label=name):
            messagebox.showwarning("Audio", f"Unable to play audio for {name}.")

    def delete_item(self, iid):
        targets = self._resolve_action_target_bases(iid)
        if not targets:
            return
        log_info(
            f"Deleting {self.model_wrapper.entity_type} items: {targets}",
            func_name="GenericListView.delete_item",
        )
        for base_id in targets:
            if base_id in self.row_colors:
                self._save_row_color(base_id, None)
        remaining = [
            it for it in self.items
            if self._get_base_id(it) not in targets
        ]
        removed_any = len(remaining) != len(self.items)
        if removed_any:
            self.items = remaining
        self.selected_iids.difference_update(targets)
        if removed_any:
            self.model_wrapper.save_items(self.items)
            self._save_list_order()
            self.filter_items(self.search_var.get())
        else:
            self._apply_selection_to_tree()
            self._refresh_grid_selection()
            if self.shelf_view:
                self.shelf_view.refresh_selection()
            self._update_bulk_controls()

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

    def merge_duplicate_entities(self):
        func_name = "GenericListView.merge_duplicate_entities"
        if not self.unique_field:
            messagebox.showwarning(
                "Merge Duplicates",
                "Unable to merge entities because no unique field is defined.",
            )
            return

        name_groups = {}
        order = []
        for item in self.items:
            key = self._normalize_unique_value(item.get(self.unique_field))
            if not key:
                continue
            if key not in name_groups:
                name_groups[key] = []
                order.append(key)
            name_groups[key].append(item)

        duplicates = {k: name_groups[k] for k in order if len(name_groups[k]) > 1}
        if not duplicates:
            messagebox.showinfo("Merge Duplicates", "No duplicate entities were found.")
            return

        total_items = sum(len(group) for group in duplicates.values())
        if not messagebox.askyesno(
            "Merge Duplicates",
            f"Found {total_items} duplicate entries across {len(duplicates)} names. "
            "Merge them into single entities?",
        ):
            return

        log_info(
            f"Merging {total_items} duplicate entries across {len(duplicates)} groups",
            func_name=func_name,
        )

        merged_groups = {key: self._merge_duplicate_group(group) for key, group in duplicates.items()}

        new_items = []
        processed = set()
        for item in self.items:
            key = self._normalize_unique_value(item.get(self.unique_field))
            if key in merged_groups:
                if key in processed:
                    continue
                new_items.append(merged_groups[key])
                processed.add(key)
            else:
                new_items.append(item)

        removed_count = total_items - len(duplicates)
        self.items = new_items
        self.model_wrapper.save_items(self.items)
        self._save_list_order()
        self.filter_items(self.search_var.get())
        messagebox.showinfo(
            "Merge Complete",
            f"Merged {len(duplicates)} groups and removed {removed_count} duplicate entries.",
        )

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

    def _set_ai_categorize_running(self, running: bool):
        self._ai_categorize_running = running
        if self.ai_categorize_button:
            if running:
                self.ai_categorize_button.configure(state="disabled", text="AI Categorizing...")
            else:
                self.ai_categorize_button.configure(state="normal", text="AI Categorize")

    def _normalize_ai_excerpt(self, value, limit: int = 320) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            for key in ("text", "value", "content", "description"):
                inner = value.get(key)
                if isinstance(inner, str) and inner.strip():
                    value = inner
                    break
            else:
                try:
                    value = json.dumps(value, ensure_ascii=False)
                except Exception:
                    value = str(value)
        elif isinstance(value, list):
            joined = ", ".join(str(v) for v in value if v)
            value = joined
        text = str(value)
        text = re.sub(r"\s+", " ", text).strip()
        if limit and len(text) > limit:
            text = text[:limit].rstrip() + "..."
        return text

    def _build_ai_categorization_payload(self, items):
        payload = []
        name_map = {}
        existing_categories = set()
        for item in items:
            name = str(item.get("Name") or item.get(self.unique_field) or "").strip()
            if not name:
                continue
            entry = {"Name": name}
            desc = self._normalize_ai_excerpt(item.get("Description"))
            if desc:
                entry["Description"] = desc
            stats = self._normalize_ai_excerpt(item.get("Stats"))
            if stats:
                entry["Stats"] = stats
            existing = str(item.get("Category") or "").strip()
            if existing:
                entry["ExistingCategory"] = existing
                existing_categories.add(existing)
            payload.append(entry)
            key = name.casefold()
            name_map.setdefault(key, []).append(item)
        return payload, name_map, sorted(existing_categories)

    def _request_ai_category_assignments(self, payload, existing_categories):
        log_info(
            f"Requesting AI categorization for {len(payload)} objects",
            func_name="GenericListView._request_ai_category_assignments",
        )
        client = LocalAIClient()
        allowed_text = ", ".join(OBJECT_CATEGORY_ALLOWED)
        existing_text = ", ".join(existing_categories) if existing_categories else "None"
        objects_json = json.dumps(payload, ensure_ascii=False, indent=2)
        user_content = (
            "Classify each tabletop RPG object into concise categories chosen from the allowed list.\n"
            "Select a concise set (ideally 5-12) of categories that best match these objects.\n"
            "Every object must receive exactly one category. If it contains a creature name, it's Food, If nothing fits, use 'Miscellaneous'.\n"
            "Do not invent categories outside the allowed list.\n"
            f"Allowed categories: {allowed_text}.\n"
            f"Existing campaign categories: {existing_text}.\n\n"
            "Return STRICT JSON with keys 'allowed_categories' and 'assignments'.\n"
            "'allowed_categories' must list every category you actually used.\n"
            "'assignments' must be an array containing one entry per object with keys 'Name' and 'Category'.\n\n"
            f"Objects to classify:\n{objects_json}"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a meticulous tabletop RPG quartermaster who maintains an organized equipment catalogue."
                ),
            },
            {"role": "user", "content": user_content},
        ]
        raw = client.chat(messages, timeout=240)
        log_debug(
            f"AI categorization raw response type: {type(raw).__name__}",
            func_name="GenericListView._request_ai_category_assignments",
        )
        preview = raw.strip().replace("\r", " ").replace("\n", " ") if isinstance(raw, str) else str(raw)
        if len(preview) > 500:
            preview = preview[:497] + "..."
        log_info(
            f"AI categorization response preview: {preview}",
            func_name="GenericListView._request_ai_category_assignments",
        )
        try:
            data = LocalAIClient._parse_json_safe(raw)
        except Exception as exc:
            raise RuntimeError(f"AI returned invalid JSON: {exc}. Raw: {raw[:500]}")

        assignments_raw = None
        allowed_from_ai = None

        def _salvage_assignment_list_from_text(text):
            if not isinstance(text, str):
                return None
            pattern = re.compile(
                r"\"(?:Name|name|Item|item)\"\s*:\s*\"([^\"]+)\"[^{}]*?\"(?:Category|category|Type|type)\"\s*:\s*\"([^\"]+)\"",
                re.DOTALL,
            )
            salvaged = []
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                category = match.group(2).strip()
                if not name:
                    continue
                salvaged.append({"Name": name, "Category": category})
            if salvaged:
                log_warning(
                    f"Salvaged {len(salvaged)} assignment(s) from raw text fallback.",
                    func_name="GenericListView._request_ai_category_assignments",
                )
            return salvaged or None

        def _coerce_assignment_list(value):
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                converted = []
                for key, entry in value.items():
                    if isinstance(entry, dict):
                        converted.append(entry)
                        continue
                    if not isinstance(key, str):
                        continue
                    converted.append({"Name": key, "Category": entry})
                log_debug(
                    f"Coerced dict assignments into {len(converted)} entries",
                    func_name="GenericListView._request_ai_category_assignments",
                )
                return converted
            if isinstance(value, str):
                try:
                    parsed = LocalAIClient._parse_json_safe(value)
                except Exception as parse_exc:
                    log_warning(
                        f"Failed to parse string assignments: {parse_exc}",
                        func_name="GenericListView._request_ai_category_assignments",
                    )
                    return None
                coerced = _coerce_assignment_list(parsed)
                if isinstance(coerced, list):
                    log_debug(
                        f"Parsed string assignments into {len(coerced)} entries",
                        func_name="GenericListView._request_ai_category_assignments",
                    )
                return coerced
            return None

        def _extract_field(value, candidate_keys):
            """Recursively locate a field in arbitrarily nested AI responses."""

            seen = set()

            def _inner(current):
                obj_id = id(current)
                if obj_id in seen:
                    return None
                seen.add(obj_id)

                if isinstance(current, dict):
                    for key in candidate_keys:
                        if key in current and current[key] is not None:
                            return current[key]
                    for nested in current.values():
                        found = _inner(nested)
                        if found is not None:
                            return found
                    return None
                if isinstance(current, list):
                    for item in current:
                        found = _inner(item)
                        if found is not None:
                            return found
                    return None
                if isinstance(current, str):
                    try:
                        parsed = LocalAIClient._parse_json_safe(current)
                    except Exception:
                        return None
                    return _inner(parsed)
                return None

            return _inner(value)

        if isinstance(data, dict):
            assignments_raw = _extract_field(data, ("assignments", "Assignments", "items", "Items"))
            allowed_from_ai = _extract_field(data, ("allowed_categories", "AllowedCategories"))
        elif isinstance(data, list):
            # Some local models skip the envelope and return the assignments list directly.
            assignments_raw = data
        else:
            raise RuntimeError("AI response was not a JSON object.")

        if assignments_raw is None and isinstance(raw, str):
            assignments_raw = _extract_field(raw, ("assignments", "Assignments", "items", "Items"))
        if allowed_from_ai is None and isinstance(raw, str):
            allowed_from_ai = _extract_field(raw, ("allowed_categories", "AllowedCategories"))
        if not isinstance(assignments_raw, list):
            assignments_raw = _coerce_assignment_list(assignments_raw)
        if not isinstance(assignments_raw, list):
            salvage_source = raw if isinstance(raw, str) else json.dumps(data, ensure_ascii=False)
            salvaged = _salvage_assignment_list_from_text(salvage_source)
            if isinstance(salvaged, list):
                assignments_raw = salvaged
            else:
                log_warning(
                    f"Unexpected assignments payload type: {type(assignments_raw).__name__}",
                    func_name="GenericListView._request_ai_category_assignments",
                )
                assignments_raw = []
        allowed_lookup = {c.casefold(): c for c in OBJECT_CATEGORY_ALLOWED}
        allowed_lookup.setdefault("miscellaneous", "Miscellaneous")
        used_categories = []
        if isinstance(allowed_from_ai, dict):
            allowed_from_ai = [str(val) for val in allowed_from_ai.values() if isinstance(val, str)]
        if isinstance(allowed_from_ai, str):
            try:
                parsed = LocalAIClient._parse_json_safe(allowed_from_ai)
                allowed_from_ai = parsed if isinstance(parsed, list) else None
            except Exception as exc:
                log_warning(
                    f"Failed to parse allowed_categories string: {exc}",
                    func_name="GenericListView._request_ai_category_assignments",
                )
        if isinstance(allowed_from_ai, list):
            seen_used = set()
            for cat in allowed_from_ai:
                if not isinstance(cat, str):
                    continue
                key = cat.strip()
                if not key:
                    continue
                resolved = allowed_lookup.get(key.casefold())
                if not resolved:
                    for ak, av in allowed_lookup.items():
                        if ak in key.casefold():
                            resolved = av
                            break
                if not resolved:
                    resolved = allowed_lookup.get("miscellaneous")
                if resolved and resolved.casefold() not in seen_used:
                    used_categories.append(resolved)
                    seen_used.add(resolved.casefold())
        assignments = {}
        for entry in assignments_raw:
            if not isinstance(entry, dict):
                continue
            name = entry.get("Name") or entry.get("name") or entry.get("Item") or entry.get("item")
            category = entry.get("Category") or entry.get("category") or entry.get("Type") or entry.get("type")
            if not isinstance(name, str):
                continue
            name_key = name.strip()
            if not name_key:
                continue
            resolved_category = None
            if isinstance(category, str):
                cat_key = category.strip()
                if cat_key:
                    resolved_category = allowed_lookup.get(cat_key.casefold())
                    if not resolved_category:
                        for ak, av in allowed_lookup.items():
                            if ak in cat_key.casefold():
                                resolved_category = av
                                break
            if not resolved_category:
                resolved_category = allowed_lookup.get("miscellaneous")
            assignments[name_key.casefold()] = resolved_category
        if not assignments:
            log_warning(
                "AI did not return any usable assignments; continuing without updates.",
                func_name="GenericListView._request_ai_category_assignments",
            )
        for cat in assignments.values():
            if cat and cat not in used_categories:
                used_categories.append(cat)
        return assignments, used_categories

    def ai_categorize_objects(self):
        if self.model_wrapper.entity_type != "objects":
            return
        if self._ai_categorize_running:
            return
        items = self.model_wrapper.load_items()
        if not items:
            messagebox.showinfo("AI Categorize", "No objects available to categorize.")
            return
        payload, name_map, existing_categories = self._build_ai_categorization_payload(items)
        if not payload:
            messagebox.showinfo("AI Categorize", "Objects require a name before they can be categorized.")
            return
        if not messagebox.askyesno(
            "AI Categorize",
            "Contact the local AI to classify every object and update the Category field?",
        ):
            return

        current_query = self.search_var.get()
        self._set_ai_categorize_running(True)

        def worker():
            assignments = {}
            used_categories = []
            used_seen = set()
            try:
                batch_size = max(1, AI_CATEGORIZE_BATCH_SIZE)
                total = len(payload)
                total_batches = (total + batch_size - 1) // batch_size
                for index, start in enumerate(range(0, total, batch_size), start=1):
                    end = start + batch_size
                    batch_payload = payload[start:end]
                    batch_existing = sorted(set(existing_categories + used_categories))
                    log_info(
                        f"AI categorization batch {index}/{total_batches} for {len(batch_payload)} object(s)",
                        func_name="GenericListView.ai_categorize_objects",
                    )
                    batch_assignments, batch_used = self._request_ai_category_assignments(
                        batch_payload,
                        batch_existing,
                    )
                    assignments.update(batch_assignments)
                    for cat in batch_used:
                        if not isinstance(cat, str):
                            continue
                        key = cat.casefold()
                        if key in used_seen:
                            continue
                        used_seen.add(key)
                        used_categories.append(cat)
            except Exception as exc:
                log_warning(
                    f"AI categorization failed: {exc}",
                    func_name="GenericListView.ai_categorize_objects",
                )
                error_message = str(exc)
                self.after(
                    0,
                    lambda msg=error_message: messagebox.showerror(
                        "AI Categorize", f"Failed to categorize objects: {msg}"
                    ),
                )
                return

            def apply_results():
                updated = 0
                missing = []
                seen_missing = set()
                for entry in payload:
                    name = entry["Name"]
                    key = name.casefold()
                    targets = name_map.get(key, [])
                    if not targets:
                        continue
                    category = assignments.get(key)
                    if not category:
                        if key not in seen_missing:
                            missing.append(name)
                            seen_missing.add(key)
                        continue
                    for item in targets:
                        if item.get("Category") != category:
                            item["Category"] = category
                            updated += 1
                if updated:
                    try:
                        self.model_wrapper.save_items(items)
                    except Exception as save_exc:
                        messagebox.showerror("AI Categorize", f"Failed to save categories: {save_exc}")
                        return
                    self.items = self.model_wrapper.load_items()
                    self.filter_items(current_query)
                summary = []
                if updated:
                    summary.append(f"Updated categories for {updated} object(s).")
                else:
                    summary.append("No object categories were changed.")
                if used_categories:
                    unique_cats = []
                    seen = set()
                    for cat in used_categories:
                        if not isinstance(cat, str):
                            continue
                        if cat.casefold() in seen:
                            continue
                        unique_cats.append(cat)
                        seen.add(cat.casefold())
                    if unique_cats:
                        summary.append("Categories used: " + ", ".join(unique_cats))
                if missing:
                    preview = ", ".join(missing[:5])
                    if len(missing) > 5:
                        preview += ", ..."
                    summary.append(f"No category returned for: {preview}")
                messagebox.showinfo("AI Categorize", "\n".join(summary))

            self.after(0, apply_results)

        def run():
            try:
                worker()
            finally:
                self.after(0, lambda: self._set_ai_categorize_running(False))

        threading.Thread(target=run, daemon=True).start()

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

    def _resolve_action_target_bases(self, iid):
        """Return base ids targeted by a row-level action."""
        _, base_id = self._find_item_by_iid(iid)
        if not base_id:
            base_id = (iid or "").lower()
        if not base_id:
            return []
        if base_id in self.selected_iids:
            if len(self.selected_iids) > 1:
                return sorted(self.selected_iids)
            return [base_id]
        return [base_id]

    def _register_tree_iid(self, base_id, iid):
        if not base_id:
            return
        entries = self._base_to_iids.setdefault(base_id, [])
        if iid not in entries:
            entries.append(iid)

    def _apply_selection_to_tree(self):
        if not hasattr(self, "tree"):
            return
        visible = set(self._base_to_iids.keys())
        if visible:
            self.selected_iids = {base_id for base_id in self.selected_iids if base_id in visible}
        else:
            self.selected_iids = set()
        self._suppress_tree_select_event = True
        desired = []
        try:
            for base_id in self.selected_iids:
                desired.extend(self._base_to_iids.get(base_id, []))
            if desired:
                self.tree.selection_set(desired)
            else:
                self.tree.selection_remove(self.tree.selection())
        finally:
            self._suppress_tree_select_event = False
        self._update_tree_selection_tags(desired)

    def _on_tree_selection_changed(self, _event=None):
        if self._suppress_tree_select_event:
            return
        selected = set()
        current_selection = self.tree.selection()
        for iid in current_selection:
            _, base_id = self._find_item_by_iid(iid)
            if base_id:
                selected.add(base_id)
        self.selected_iids = selected
        if current_selection:
            focus_iid = self.tree.focus()
            if focus_iid not in current_selection:
                self.tree.focus(current_selection[0])
        self._update_tree_selection_tags(current_selection)
        self._update_bulk_controls()
        self._refresh_grid_selection()
        if self.shelf_view:
            self.shelf_view.refresh_selection()

    def _update_tree_selection_tags(self, selection=None):
        if not hasattr(self, "tree"):
            return
        if selection is None:
            selection = self.tree.selection()
        selection_set = {iid for iid in selection if self.tree.exists(iid)}
        removed = self._last_tree_selection - selection_set
        added = selection_set - self._last_tree_selection
        for iid in removed:
            self._remove_selection_tag(iid)
        for iid in added:
            self._apply_selection_tag(iid)
        self._last_tree_selection = selection_set

    def _apply_selection_tag(self, iid):
        if not self.tree.exists(iid):
            return
        current_tags = list(self.tree.item(iid, "tags") or ())
        if "selected_row" not in current_tags:
            current_tags.append("selected_row")
            self.tree.item(iid, tags=tuple(current_tags))

    def _remove_selection_tag(self, iid):
        if not self.tree.exists(iid):
            return
        current_tags = [t for t in (self.tree.item(iid, "tags") or ()) if t != "selected_row"]
        self.tree.item(iid, tags=tuple(current_tags))

    def _refresh_grid_selection(self):
        if not getattr(self, "grid_cards", None):
            return
        for info in self.grid_cards:
            card = info.get("card")
            base_id = info.get("base_id")
            self._set_grid_card_selected(card, base_id in self.selected_iids)

    def _set_grid_card_selected(self, card, selected):
        if not card or not card.winfo_exists():
            return
        if selected:
            card.configure(border_color="#1F6AA5", border_width=3)
        else:
            card.configure(border_color="#1E1E1E", border_width=1)

    def _update_bulk_controls(self):
        count = len(self.selected_iids)
        if count:
            self.selection_label.configure(text=f"{count} selected")
            self.bulk_action_button.configure(state=tk.NORMAL)
        else:
            self.selection_label.configure(text="")
            self.bulk_action_button.configure(state=tk.DISABLED)

    def _get_display_label(self):
        return ENTITY_DISPLAY_LABELS.get(
            self.model_wrapper.entity_type,
            self.model_wrapper.entity_type.replace("_", " ").title(),
        )

    def _format_entity_noun(self, count):
        label = self._get_display_label()
        if count == 1 and label.endswith("s"):
            return label[:-1]
        return label

    def _find_item_by_base_id(self, base_id):
        for item in self.items:
            if self._get_base_id(item) == base_id:
                return item
        return None

    def _open_bulk_menu(self):
        if not self.selected_iids:
            messagebox.showinfo("Bulk Actions", "Select at least one item to continue.")
            return
        menu = tk.Menu(self, tearoff=0)
        link_supported = self.model_wrapper.entity_type in SCENARIO_LINK_FIELDS
        menu.add_command(
            label="Link to Scenario...",
            command=self._bulk_link_to_scenario,
            state=tk.NORMAL if link_supported else tk.DISABLED,
        )
        gm_supported = self.model_wrapper.entity_type in GM_SCREEN_ENTITY_TYPES
        menu.add_command(
            label="Add to GM Screen...",
            command=self._bulk_add_to_gm_screen,
            state=tk.NORMAL if gm_supported else tk.DISABLED,
        )
        try:
            menu.tk_popup(
                self.bulk_action_button.winfo_rootx(),
                self.bulk_action_button.winfo_rooty() + self.bulk_action_button.winfo_height(),
            )
        finally:
            menu.grab_release()

    def _bulk_link_to_scenario(self):
        field_name = SCENARIO_LINK_FIELDS.get(self.model_wrapper.entity_type)
        if not field_name:
            messagebox.showinfo(
                "Bulk Actions",
                "Linking to scenarios is not supported for this entity type.",
            )
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Scenario")
        dialog.geometry("1200x800")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        wrapper = GenericModelWrapper("scenarios")
        template = load_template("scenarios")

        def _close_dialog():
            if dialog.winfo_exists():
                try:
                    dialog.grab_release()
                except Exception:
                    pass
                dialog.destroy()

        def _on_select(_entity_type, name):
            _close_dialog()
            if name:
                self._apply_bulk_link_to_scenario(name, field_name)

        view = GenericListSelectionView(
            dialog,
            "Scenarios",
            wrapper,
            template,
            on_select_callback=_on_select,
        )
        view.pack(fill="both", expand=True)
        dialog.focus_force()
        dialog.protocol("WM_DELETE_WINDOW", _close_dialog)
        dialog.wait_window(dialog)

    def _apply_bulk_link_to_scenario(self, scenario_name, field_name):
        wrapper = GenericModelWrapper("scenarios")
        scenarios = wrapper.load_items()
        scenario = next(
            (
                it
                for it in scenarios
                if str(it.get("Title") or it.get("Name") or "").strip() == scenario_name
            ),
            None,
        )
        if not scenario:
            messagebox.showerror("Scenario Not Found", f"Scenario '{scenario_name}' was not found.")
            return

        current = list(scenario.get(field_name) or [])
        added = 0
        for base_id in sorted(self.selected_iids):
            item = self._find_item_by_base_id(base_id)
            if not item:
                continue
            value = self.clean_value(item.get(self.unique_field, "")) or ""
            if not value or value in current:
                continue
            current.append(value)
            added += 1

        if added:
            scenario[field_name] = current
            wrapper.save_items(scenarios)
            noun = self._format_entity_noun(added)
            messagebox.showinfo(
                "Scenarios",
                f"Added {added} {noun} to scenario '{scenario_name}'.",
            )
        else:
            messagebox.showinfo(
                "Scenarios",
                "All selected items are already linked to the scenario.",
            )

    def _bulk_add_to_gm_screen(self):
        gm_type = GM_SCREEN_ENTITY_TYPES.get(self.model_wrapper.entity_type)
        if not gm_type:
            messagebox.showinfo(
                "Bulk Actions",
                "Adding to the GM Screen is not supported for this entity type.",
            )
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Scenario")
        dialog.geometry("1200x800")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        wrapper = GenericModelWrapper("scenarios")
        template = load_template("scenarios")

        def _close_dialog():
            if dialog.winfo_exists():
                try:
                    dialog.grab_release()
                except Exception:
                    pass
                dialog.destroy()

        def _on_select(_entity_type, name):
            _close_dialog()
            if name:
                self._apply_bulk_add_to_gm_screen(name, gm_type)

        view = GenericListSelectionView(
            dialog,
            "Scenarios",
            wrapper,
            template,
            on_select_callback=_on_select,
        )
        view.pack(fill="both", expand=True)
        dialog.focus_force()
        dialog.protocol("WM_DELETE_WINDOW", _close_dialog)
        dialog.wait_window(dialog)

    def _apply_bulk_add_to_gm_screen(self, scenario_name, gm_type):
        manager = GMScreenLayoutManager()
        existing_default = manager.get_scenario_default(scenario_name)
        layout_name = existing_default
        layout = manager.get_layout(layout_name) if layout_name else None
        created_layout = False
        if layout is None:
            layout_name = layout_name or f"Auto: {scenario_name}"
            layout = manager.get_layout(layout_name)
            if layout is None:
                layout = {"scenario": scenario_name, "tabs": [], "active": None}
                created_layout = True

        tabs = layout.setdefault("tabs", [])
        scenario_tab_added = False
        if not any(
            tab.get("kind") == "entity"
            and tab.get("entity_type") == "Scenarios"
            and str(tab.get("entity_name")) == scenario_name
            for tab in tabs
        ):
            tabs.insert(
                0,
                {
                    "kind": "entity",
                    "entity_type": "Scenarios",
                    "entity_name": scenario_name,
                    "title": scenario_name,
                },
            )
            scenario_tab_added = True

        added = 0
        for base_id in sorted(self.selected_iids):
            item = self._find_item_by_base_id(base_id)
            if not item:
                continue
            entity_name = self.clean_value(item.get(self.unique_field, "")) or ""
            if not entity_name:
                continue
            exists = any(
                tab.get("kind") == "entity"
                and tab.get("entity_type") == gm_type
                and str(tab.get("entity_name")) == entity_name
                for tab in tabs
            )
            if exists:
                continue
            tabs.append(
                {
                    "kind": "entity",
                    "entity_type": gm_type,
                    "entity_name": entity_name,
                    "title": entity_name,
                }
            )
            added += 1

        changed = added > 0 or scenario_tab_added or created_layout
        if changed:
            layout["scenario"] = scenario_name
            manager.save_layout(layout_name, layout)
            if existing_default is None:
                manager.set_scenario_default(scenario_name, layout_name)
            if added:
                noun = self._format_entity_noun(added)
                messagebox.showinfo(
                    "GM Screen",
                    f"Added {added} {noun} to GM Screen layout '{layout_name}' for '{scenario_name}'.",
                )
            elif scenario_tab_added:
                messagebox.showinfo(
                    "GM Screen",
                    f"Scenario '{scenario_name}' is now pinned in GM Screen layout '{layout_name}'.",
                )
            else:
                messagebox.showinfo(
                    "GM Screen",
                    f"Initialized GM Screen layout '{layout_name}' for '{scenario_name}'.",
                )
        else:
            messagebox.showinfo(
                "GM Screen",
                "All selected items are already present in the GM Screen layout.",
            )

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
        targets = self._resolve_action_target_bases(iid)
        if not targets:
            return
        affected_tree_iids = set()
        for base_id in targets:
            tree_iids = self._base_to_iids.get(base_id, [])
            if color_name:
                for tree_iid in tree_iids:
                    self.tree.item(tree_iid, tags=(f"color_{color_name}",))
            else:
                for tree_iid in tree_iids:
                    self.tree.item(tree_iid, tags=())
            affected_tree_iids.update(tree_iids)
            self._save_row_color(base_id, color_name)
        self.selected_iids.difference_update(targets)
        if affected_tree_iids:
            self.tree.selection_remove(*affected_tree_iids)
        self.tree.focus("")
        self._apply_selection_to_tree()
        self._refresh_grid_selection()
        self._update_bulk_controls()

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
        
