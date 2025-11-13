import json
import re
import time
import os
import sys
import subprocess
import threading
from collections import OrderedDict
import ast
import customtkinter as ctk
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog, simpledialog
import copy
from PIL import Image
from modules.generic.generic_editor_window import GenericEditorWindow
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.ui.image_viewer import show_portrait
from modules.ui.second_screen_display import show_entity_on_second_screen
from modules.helpers.config_helper import ConfigHelper
from modules.helpers import theme_manager
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
from modules.books.book_importer import (
    extract_text_from_book,
    prepare_books_from_directory,
    prepare_books_from_files,
)
from modules.books.book_viewer import open_book_viewer
from modules.books.pdf_processing import (
    export_pdf_page_range,
    get_pdf_page_count,
)
from modules.helpers.logging_helper import (
    log_debug,
    log_function,
    log_info,
    log_methods,
    log_warning,
    log_module_import,
)
from modules.objects.object_shelf_canvas_view import ObjectShelfView
from modules.objects.object_constants import OBJECT_CATEGORY_ALLOWED

log_module_import(__name__)

PORTRAIT_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "portraits")
ctk.set_appearance_mode("Dark")
theme_manager.apply_theme(theme_manager.get_theme())

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
    "books": "Books",
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
    "books": "Books",
}

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
        if self.model_wrapper.entity_type == "books":
            lightweight_columns = [
                "Title",
                "Subject",
                "Game",
                "Folder",
                "Tags",
                "PageCount",
                "Notes",
                "Attachment",
            ]
            self.columns = [c for c in self.columns if c in lightweight_columns]
            if "Excerpts" not in self.columns:
                self.columns.append("Excerpts")

        self._link_column = None
        self._tree_columns = list(self.columns)
        self._linked_rows = {}
        self._link_targets = {}
        self._link_children = {}
        self._auto_expanded_rows = set()
        self._pinned_linked_rows = set()
        self._link_toggle_in_progress = False

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
        if self.model_wrapper.entity_type == "books":
            ctk.CTkButton(
                self.search_frame,
                text="Import PDFs…",
                command=self.import_books_from_files_dialog,
            ).pack(side="left", padx=5)
            ctk.CTkButton(
                self.search_frame,
                text="Import Folder…",
                command=self.import_books_from_directory_dialog,
            ).pack(side="left", padx=5)
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
            columns=self._tree_columns,
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

        if self._link_column:
            self.tree.heading(self._link_column, text="")
            self.tree.column(
                self._link_column,
                width=30,
                minwidth=24,
                anchor="center",
                stretch=False,
            )

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
                try:
                    manager = self.tree_frame.winfo_manager()
                except Exception:
                    manager = ""
                if manager:
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
        self._linked_rows.clear()
        self._link_targets.clear()
        self._link_children.clear()
        self._auto_expanded_rows.clear()
        self._pinned_linked_rows.clear()
        self._base_to_iids = {}
        self.batch_index = 0
        total_items = len(self.filtered_items)
        if total_items > 1000:
            self.batch_size = 500
        elif total_items > 600:
            self.batch_size = 300
        elif total_items > 300:
            self.batch_size = 200
        elif total_items > 150:
            self.batch_size = 100
        else:
            self.batch_size = 50
        self._default_batch_size = self.batch_size
        self._first_batch_size = min(50, self.batch_size)
        self.batch_size = self._first_batch_size
        self._first_batch_pending = self._default_batch_size != self._first_batch_size and total_items > self._first_batch_size
        self._batch_delay_ms = 50
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
                widget.bind(
                    "<Double-Button-1>",
                    lambda e, it=item: self.open_book(it)
                    if self.model_wrapper.entity_type == "books"
                    else self._edit_item(it),
                )

            bind_open(image_label)
            bind_open(card)
            bind_open(name_label)

            def bind_select(widget):
                widget.bind("<Button-1>", lambda e, it=item: self.on_grid_click(e, it))

            bind_select(image_label)
            bind_select(card)
            bind_select(name_label)
            if self.model_wrapper.entity_type == "books":
                summary = self._summarize_book_excerpts(item)
                if summary:
                    summary_label = ctk.CTkLabel(
                        card,
                        text=summary,
                        justify="center",
                        wraplength=160,
                        font=("Segoe UI", 10),
                    )
                    summary_label.grid(row=2, column=0, padx=10, pady=(0, 5))
                    bind_select(summary_label)
                    bind_open(summary_label)
                    excerpt_button = ctk.CTkButton(
                        card,
                        text="Open Excerpts",
                        width=140,
                        command=lambda it=item, widget=card: self._show_book_excerpts_menu(it, widget),
                    )
                    excerpt_button.grid(row=3, column=0, padx=10, pady=(0, 10))
                else:
                    hint_label = ctk.CTkLabel(
                        card,
                        text="No excerpts",
                        font=("Segoe UI", 9, "italic"),
                    )
                    hint_label.grid(row=2, column=0, padx=10, pady=(0, 10))
                    bind_select(hint_label)
                    bind_open(hint_label)
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
        column = self._normalize_column_id(self.tree.identify_column(event.x))
        row = self.tree.identify_row(event.y)
        if self._link_column and column == self._link_column and row:
            if self._linked_rows.get(row):
                self.tree.selection_set(row)
                self.tree.focus(row)
                self._link_toggle_in_progress = True
                try:
                    self._toggle_linked_rows(row)
                finally:
                    self._link_toggle_in_progress = False
            self.dragging_iid = None
            return
        if self.group_column or self.filtered_items != self.items:
            self.dragging_iid = None
            return
        self.dragging_iid = row
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
            linked = self._collect_linked_entities(item)
            self._linked_rows[iid] = linked
            self._link_children.pop(iid, None)
            self._auto_expanded_rows.discard(iid)
            self._pinned_linked_rows.discard(iid)
            vals = []
            if self._link_column:
                vals.append("+" if linked else "")
            vals.extend(
                self._format_cell(c, self._get_display_value(item, c), iid) for c in self.columns
            )
            try:
                self.tree.insert("", "end", iid=iid, text=name_text, values=tuple(vals))
                color = self.row_colors.get(base_id)
                if color:
                    self.tree.item(iid, tags=(f"color_{color}",))
                self._register_tree_iid(base_id, iid)
                if base_id in self.selected_iids:
                    self.tree.selection_add(iid)
            except Exception as e:
                print("[ERROR] inserting item:", e, iid, vals)
        self.batch_index = end
        if getattr(self, "_first_batch_pending", False):
            self.batch_size = getattr(self, "_default_batch_size", self.batch_size)
            self._first_batch_pending = False
        if end < len(self.filtered_items):
            delay = getattr(self, "_batch_delay_ms", 50)
            try:
                delay = max(1, int(delay))
            except (TypeError, ValueError):
                delay = 50
            self.after(delay, self.insert_next_batch)
        self._update_tree_selection_tags()

    def insert_grouped_items(self):
        grouped = {}
        for item in self.filtered_items:
            key = self.clean_value(item.get(self.group_column, "")) or "Unknown"
            grouped.setdefault(key, []).append(item)

        for group_val in sorted(grouped.keys()):
            base_group_id = sanitize_id(f"group_{group_val}")
            group_id = unique_iid(self.tree, base_group_id)
            self.tree.insert(
                "",
                "end",
                iid=group_id,
                text=group_val,
                values=self._blank_row_values(),
                open=False,
            )
            for item in grouped[group_val]:
                raw = item.get(self.unique_field, "")
                if isinstance(raw, dict):
                    raw = raw.get("text", "")
                base_iid = sanitize_id(raw or f"item_{int(time.time()*1000)}").lower()
                iid = unique_iid(self.tree, base_iid)
                name_text = self._format_cell("#0", item.get(self.unique_field, ""), iid)
                linked = self._collect_linked_entities(item)
                self._linked_rows[iid] = linked
                self._link_children.pop(iid, None)
                self._auto_expanded_rows.discard(iid)
                self._pinned_linked_rows.discard(iid)
                vals = []
                if self._link_column:
                    vals.append("+" if linked else "")
                vals.extend(
                    self._format_cell(c, self._get_display_value(item, c), iid) for c in self.columns
                )
                try:
                    self.tree.insert(group_id, "end", iid=iid, text=name_text, values=tuple(vals))
                    color = self.row_colors.get(base_iid)
                    if color:
                        self.tree.item(iid, tags=(f"color_{color}",))
                    self._register_tree_iid(base_iid, iid)
                    if base_iid in self.selected_iids:
                        self.tree.selection_add(iid)
                except Exception as e:
                    print("[ERROR] inserting item:", e, iid, vals)
        self._update_tree_selection_tags()

    def _collect_linked_entities(self, item):
        result = OrderedDict()
        fields = self.template.get("fields", []) if isinstance(self.template, dict) else []
        if not isinstance(fields, list):
            return result

        label_to_slug = {label: slug for slug, label in ENTITY_DISPLAY_LABELS.items()}
        normalized_labels = {label.lower(): slug for label, slug in label_to_slug.items()}

        for field in fields:
            if not isinstance(field, dict):
                continue
            field_type = str(field.get("type", "")).strip().lower()
            if field_type not in {"list", "list_longtext"}:
                continue

            if field_type == "list_longtext" and not field.get("linked_type"):
                # Long-text lists without an explicit linked type (e.g. scenario scenes)
                # represent inline content rather than linked entities. These should not
                # appear as expandable rows in the tree view.
                continue

            linked_label = str(field.get("linked_type", "")).strip()
            field_label = str(field.get("label") or field.get("name") or "").strip()

            slug = None
            if linked_label:
                candidate = linked_label.lower()
                if candidate in ENTITY_DISPLAY_LABELS:
                    slug = candidate
                else:
                    slug = label_to_slug.get(linked_label) or normalized_labels.get(candidate)
                    if not slug:
                        slug = candidate
            elif field_label:
                slug = label_to_slug.get(field_label) or normalized_labels.get(field_label.lower())
                if not slug and field_label:
                    slug = field_label.replace(" ", "_").lower()

            if not slug:
                continue

            slug = slug.lower()

            raw_values = item.get(field.get("name")) if isinstance(item, dict) else None
            values = []
            if isinstance(raw_values, (list, tuple)):
                values = list(raw_values)
            elif isinstance(raw_values, str):
                stripped = raw_values.strip()
                if stripped:
                    parsed = None
                    if stripped.startswith(("[", "{", '"')):
                        try:
                            parsed = json.loads(stripped)
                        except Exception:
                            try:
                                parsed = ast.literal_eval(stripped)
                            except Exception:
                                parsed = None
                    if isinstance(parsed, (list, tuple)):
                        values = list(parsed)
                    elif isinstance(parsed, dict):
                        values = [parsed]
                    elif isinstance(parsed, str):
                        values = [parsed]
                    elif parsed is not None:
                        values = [parsed]
                    if not values:
                        parts = [p.strip() for p in re.split(r"[\n;,]+", stripped) if p.strip()]
                        values = parts
            elif raw_values is not None:
                values = [raw_values]

            if not values:
                continue

            was_existing = slug in result
            collected = result.setdefault(slug, [])
            initial_len = len(collected)
            seen = {str(existing).casefold() for existing in collected if isinstance(existing, str)}
            for entry in values:
                name = None
                if isinstance(entry, dict):
                    for key in ("Name", "name", "Title", "title", "Target", "target", "Text", "text", "value", "Value"):
                        value = entry.get(key)
                        if value:
                            name = value
                            break
                    if name is None and len(entry) == 1:
                        try:
                            name = next(iter(entry.values()))
                        except StopIteration:
                            name = None
                else:
                    name = entry

                name = self.clean_value(name)
                if not name:
                    continue
                key = name.casefold()
                if key in seen:
                    continue
                seen.add(key)
                collected.append(name)

            if not was_existing and len(collected) == initial_len:
                result.pop(slug, None)

        return result

    def _display_label_for_slug(self, slug):
        if not slug:
            return ""
        if slug in ENTITY_DISPLAY_LABELS:
            return ENTITY_DISPLAY_LABELS[slug]
        slug_lower = str(slug).lower()
        for key, label in ENTITY_DISPLAY_LABELS.items():
            if key.lower() == slug_lower or label.lower() == slug_lower:
                return label
        return str(slug).replace("_", " ").title()

    def _blank_row_values(self):
        values = tuple("" for _ in self.columns)
        if self._link_column:
            return ("",) + values
        return values

    def _toggle_linked_rows(self, parent_iid):
        groups = self._linked_rows.get(parent_iid)
        if not groups:
            return
        if parent_iid in self._link_children:
            self._collapse_linked_rows(parent_iid)
        else:
            self._expand_linked_rows(parent_iid, groups)

    def _expand_linked_rows(self, parent_iid, groups, *, auto=False):
        headers = []
        name_nodes = []
        self.tree.item(parent_iid, open=True)
        for slug, names in groups.items():
            if not names:
                continue
            header_base = sanitize_id(f"{parent_iid}_{slug}_group") or f"{parent_iid}_{slug}_group"
            header_iid = unique_iid(self.tree, header_base)
            header_label = self._display_label_for_slug(slug)
            self.tree.insert(parent_iid, "end", iid=header_iid, text=header_label, values=self._blank_row_values())
            self.tree.item(header_iid, open=True)
            headers.append(header_iid)
            for name in names:
                name_base = sanitize_id(f"{parent_iid}_{slug}_{name}") or f"{parent_iid}_{slug}_{int(time.time()*1000)}"
                name_iid = unique_iid(self.tree, name_base)
                self.tree.insert(header_iid, "end", iid=name_iid, text=name, values=self._blank_row_values())
                self._link_targets[name_iid] = (slug, name)
                name_nodes.append(name_iid)
        if headers:
            self._link_children[parent_iid] = {"headers": headers, "names": name_nodes}
            if self._link_column:
                self.tree.set(parent_iid, self._link_column, "–")
            if auto:
                self._auto_expanded_rows.add(parent_iid)
                self._pinned_linked_rows.discard(parent_iid)
            else:
                self._pinned_linked_rows.add(parent_iid)
                self._auto_expanded_rows.discard(parent_iid)

    def _collapse_linked_rows(self, parent_iid):
        info = self._link_children.pop(parent_iid, None)
        if not info:
            return
        for name_iid in info.get("names", []):
            self._link_targets.pop(name_iid, None)
        for header_iid in info.get("headers", []):
            if self.tree.exists(header_iid):
                self.tree.delete(header_iid)
        if self._link_column:
            self.tree.set(parent_iid, self._link_column, "+")
        self._auto_expanded_rows.discard(parent_iid)
        self._pinned_linked_rows.discard(parent_iid)

    def _open_link_target(self, iid):
        target = self._link_targets.get(iid)
        if not target:
            return
        slug, name = target
        try:
            wrapper = GenericModelWrapper(slug)
        except Exception as exc:
            messagebox.showerror("Open Linked Entity", f"Unable to prepare editor for '{slug}': {exc}")
            return
        try:
            template = load_template(slug)
        except Exception as exc:
            messagebox.showerror("Open Linked Entity", f"Unable to load template for '{slug}': {exc}")
            return
        try:
            items = wrapper.load_items()
        except Exception as exc:
            messagebox.showerror("Open Linked Entity", f"Unable to load '{slug}' entries: {exc}")
            return

        key_field = "Title" if slug in {"scenarios", "books"} else "Name"
        target_item = None
        lookup_key = name.casefold()
        for record in items:
            raw_value = record.get(key_field, "")
            candidates = []
            if isinstance(raw_value, dict):
                for key in (
                    "Name",
                    "name",
                    "Title",
                    "title",
                    "Target",
                    "target",
                    "Text",
                    "text",
                    "label",
                    "Label",
                    "value",
                    "Value",
                ):
                    candidates.append(str(raw_value.get(key, "")))
            else:
                candidates.append(str(raw_value))

            cleaned_candidate = self.clean_value(raw_value)
            if cleaned_candidate:
                candidates.append(str(cleaned_candidate))

            for candidate in candidates:
                if candidate and candidate.casefold() == lookup_key:
                    target_item = record
                    break
            if target_item:
                break

        if not target_item:
            display_label = self._display_label_for_slug(slug) or slug
            messagebox.showerror(
                "Open Linked Entity",
                f"Could not find '{name}' in {display_label}.",
            )
            return

        editor = GenericEditorWindow(
            self.master,
            target_item,
            template,
            wrapper,
            creation_mode=False,
        )
        self.master.wait_window(editor)

        if getattr(editor, "saved", False):
            try:
                wrapper.save_items(items)
            except Exception as exc:
                messagebox.showerror("Open Linked Entity", f"Failed to save changes: {exc}")
                return
            if slug == self.model_wrapper.entity_type:
                self.items = self.model_wrapper.load_items()
                current_query = self.search_var.get() if hasattr(self, "search_var") else ""
                if current_query:
                    self.filter_items(current_query)
                else:
                    self.filtered_items = list(self.items)
                    self.refresh_list()

    def clean_value(self, val):
        if val is None:
            return ""
        if isinstance(val, dict):
            if "text" in val:
                return self.clean_value(val.get("text", ""))
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
            return ", ".join(self.clean_value(v) for v in val.values())
        if isinstance(val, list):
            return ", ".join(self.clean_value(v) for v in val if v is not None)
        return str(val).replace("{", "").replace("}", "").strip()

    def _get_display_value(self, item, column):
        if self.model_wrapper.entity_type == "books":
            if column == "Excerpts":
                return self._summarize_book_excerpts(item)
            if column in {"ExtractedText", "ExtractedPages"}:
                # Heavy fields are omitted from the list view; avoid pulling large payloads.
                return ""
        return item.get(column, "")

    def _summarize_book_excerpts(self, item):
        excerpts = list(self._iter_book_excerpts(item))
        labels = []
        for excerpt in excerpts:
            label = excerpt.get("Label")
            if not label:
                start = excerpt.get("StartPage")
                end = excerpt.get("EndPage")
                if start and end and start != end:
                    label = f"pp. {start}-{end}"
                elif start:
                    label = f"p. {start}"
                else:
                    label = os.path.basename(str(excerpt.get("Path", "")))
            if label:
                labels.append(str(label))
        return ", ".join(labels)

    def _iter_book_excerpts(self, item):
        pages = item.get("ExtractedPages") if isinstance(item, dict) else None
        if not isinstance(pages, list):
            return
        for entry in pages:
            if not isinstance(entry, dict):
                continue
            path = entry.get("Path") or entry.get("path")
            if not path:
                continue
            start = entry.get("StartPage") or entry.get("start_page")
            end = entry.get("EndPage") or entry.get("end_page")
            if isinstance(entry.get("page_range"), (list, tuple)) and len(entry["page_range"]) >= 2:
                start = start or entry["page_range"][0]
                end = end or entry["page_range"][1]
            label = entry.get("Label") or entry.get("label")
            yield {
                "StartPage": start,
                "EndPage": end,
                "Path": path,
                "Label": label,
                "Filename": entry.get("Filename") or entry.get("filename"),
            }

    def _build_excerpt_entry(self, metadata):
        page_range = metadata.get("page_range") if isinstance(metadata, dict) else None
        start = end = None
        if isinstance(page_range, (list, tuple)) and len(page_range) >= 2:
            start, end = int(page_range[0]), int(page_range[1])
        else:
            start = metadata.get("StartPage") or metadata.get("start_page")
            end = metadata.get("EndPage") or metadata.get("end_page")
        path = metadata.get("path") or metadata.get("Path")
        filename = metadata.get("filename") or metadata.get("Filename")
        label = metadata.get("label") or metadata.get("Label")
        if not label:
            if start and end and start != end:
                label = f"pp. {start}-{end}"
            elif start:
                label = f"p. {start}"
            elif filename:
                label = filename
            else:
                label = os.path.basename(str(path or "Excerpt"))
        return {
            "Type": "excerpt",
            "StartPage": start,
            "EndPage": end,
            "Path": path,
            "Label": label,
            "Filename": filename,
            "page_range": page_range,
        }

    def _parse_page_range_input(self, text, total_pages):
        cleaned = text.strip()
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", cleaned)
        if not match:
            raise ValueError("Enter a page number or range such as '5-8'.")
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        if start < 1 or end < 1:
            raise ValueError("Page numbers must be positive.")
        if end < start:
            raise ValueError("End page must be greater than or equal to start page.")
        if total_pages and (start > total_pages or end > total_pages):
            raise ValueError(f"Pages must be within 1-{total_pages}.")
        return start, end

    def _resolve_book_path(self, relative_path):
        if not relative_path:
            return ""
        if os.path.isabs(relative_path):
            return relative_path
        return os.path.join(ConfigHelper.get_campaign_dir(), relative_path)

    def _open_book_excerpt(self, excerpt):
        path = excerpt.get("Path") if isinstance(excerpt, dict) else None
        if not path:
            messagebox.showwarning("Open Excerpt", "This excerpt does not have an associated file.")
            return
        resolved = self._resolve_book_path(path)
        if not os.path.exists(resolved):
            messagebox.showwarning(
                "Open Excerpt",
                f"The excerpt file could not be found:\n{resolved}",
            )
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(resolved)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", resolved])
            else:
                subprocess.Popen(["xdg-open", resolved])
            log_info(
                f"Opened book excerpt '{resolved}'.",
                func_name="GenericListView._open_book_excerpt",
            )
        except Exception as exc:
            log_warning(
                f"Failed to open excerpt '{resolved}': {exc}",
                func_name="GenericListView._open_book_excerpt",
            )
            messagebox.showerror("Open Excerpt", f"Failed to open the file:\n{exc}")

    def _show_book_excerpts_menu(self, item, widget=None):
        excerpts = list(self._iter_book_excerpts(item))
        if not excerpts:
            messagebox.showinfo("Book Excerpts", "No excerpts available for this book.")
            return
        menu = tk.Menu(self, tearoff=0)
        for index, excerpt in enumerate(excerpts, start=1):
            label = excerpt.get("Label") or f"Excerpt {index}"
            menu.add_command(label=label, command=lambda e=excerpt: self._open_book_excerpt(e))
        x = y = 0
        if widget is not None:
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height()
        else:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def open_book(self, item):
        if not item:
            return
        top = self.winfo_toplevel() if hasattr(self, "winfo_toplevel") else self.master
        open_book_viewer(top, item)

    def extract_book_pages(self, item):
        if not item:
            return
        attachment = item.get("Attachment", "")
        if not attachment:
            messagebox.showwarning("Extract Pages", "This book has no attachment to extract from.")
            return
        campaign_dir = ConfigHelper.get_campaign_dir()
        try:
            total_pages = get_pdf_page_count(attachment, campaign_dir=campaign_dir)
        except Exception as exc:
            log_warning(
                f"Failed to determine page count for '{attachment}': {exc}",
                func_name="GenericListView.extract_book_pages",
            )
            messagebox.showerror("Extract Pages", f"Unable to load the PDF:\n{exc}")
            return

        prompt = simpledialog.askstring(
            "Extract Pages",
            f"Enter the page range to extract (1-{total_pages}):",
            parent=self,
        )
        if not prompt:
            return
        try:
            start_page, end_page = self._parse_page_range_input(prompt, total_pages)
        except ValueError as exc:
            messagebox.showerror("Extract Pages", str(exc))
            return

        try:
            metadata = export_pdf_page_range(
                attachment,
                start_page,
                end_page,
                campaign_dir=campaign_dir,
            )
        except Exception as exc:
            log_warning(
                f"Failed to export pages {start_page}-{end_page} for '{attachment}': {exc}",
                func_name="GenericListView.extract_book_pages",
            )
            messagebox.showerror("Extract Pages", f"Failed to export pages:\n{exc}")
            return

        excerpt_entry = self._build_excerpt_entry(metadata)
        extracted = item.get("ExtractedPages")
        if isinstance(extracted, list):
            extracted = list(extracted)
        else:
            extracted = []
        extracted.append(excerpt_entry)
        item["ExtractedPages"] = extracted
        log_info(
            f"Added excerpt {excerpt_entry.get('Label')} to book '{item.get(self.unique_field, 'Unknown')}'.",
            func_name="GenericListView.extract_book_pages",
        )
        try:
            self.model_wrapper.save_items(self.items)
        except Exception as exc:
            log_warning(
                f"Failed to save book excerpts: {exc}",
                func_name="GenericListView.extract_book_pages",
            )
            messagebox.showerror("Extract Pages", f"Unable to save the updated book:\n{exc}")
            return
        self.filter_items(self.search_var.get())
        label = excerpt_entry.get("Label") or f"Pages {start_page}-{end_page}"
        messagebox.showinfo("Extract Pages", f"Created excerpt {label}.")


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
        if iid is not None and column_id != "#0" and column_id != self._link_column:
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

        max_width = available - ellipsis_width
        if max_width <= 0:
            return self._ellipsis

        # Binary search the longest prefix that fits the available width.
        low, high = 0, len(text)
        best_prefix = ""
        while low <= high:
            mid = (low + high) // 2
            candidate = text[:mid]
            candidate_width = self._tree_font.measure(candidate)
            if candidate_width <= max_width:
                best_prefix = candidate
                low = mid + 1
            else:
                high = mid - 1

        return best_prefix + self._ellipsis

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
        if iid in self._link_targets:
            self._open_link_target(iid)
            return
        item, _ = self._find_item_by_iid(iid)
        if item:
            modifiers = getattr(event, "state", 0)
            if (
                self.model_wrapper.entity_type == "books"
                and not (modifiers & 0x0004 or modifiers & 0x0001)
            ):
                self.open_book(item)
            else:
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
        if self.model_wrapper.entity_type == "books" and item:
            menu.add_command(
                label="Open Book",
                command=lambda it=item: self.open_book(it),
            )
            menu.add_command(
                label="Extract Pages…",
                command=lambda it=item: self.extract_book_pages(it),
            )
            excerpts = list(self._iter_book_excerpts(item))
            if excerpts:
                excerpt_menu = tk.Menu(menu, tearoff=0)
                for index, excerpt in enumerate(excerpts, start=1):
                    label = excerpt.get("Label") or f"Excerpt {index}"
                    excerpt_menu.add_command(
                        label=label,
                        command=lambda e=excerpt: self._open_book_excerpt(e),
                    )
                menu.add_cascade(label="Open Excerpt", menu=excerpt_menu)
            menu.add_command(
                label="Edit Details…",
                command=lambda it=item: self._edit_item(it),
            )
            menu.add_separator()
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
        layout_manager = GMScreenLayoutManager()
        view = GMScreenView(
            window,
            scenario_item=item,
            initial_layout=None,
            layout_manager=layout_manager,
        )
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
            def iter_search_values(item):
                if self.model_wrapper.entity_type == "books":
                    for col in self.columns:
                        yield self._get_display_value(item, col)
                else:
                    yield from item.values()

            self.filtered_items = [
                it for it in self.items
                if any(q in self.clean_value(v).lower() for v in iter_search_values(it))
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

    def import_books_from_files_dialog(self):
        if self.model_wrapper.entity_type != "books":
            return
        log_info("Importing books from file selection", func_name="GenericListView.import_books_from_files_dialog")
        file_paths = filedialog.askopenfilenames(
            title="Select PDF Files",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if not file_paths:
            return
        try:
            records = prepare_books_from_files(file_paths, campaign_dir=ConfigHelper.get_campaign_dir())
        except Exception as exc:
            messagebox.showerror("Import PDFs", f"Failed to prepare books:\n{exc}")
            return
        self._persist_imported_books(records)

    def import_books_from_directory_dialog(self):
        if self.model_wrapper.entity_type != "books":
            return
        log_info("Importing books from directory", func_name="GenericListView.import_books_from_directory_dialog")
        dir_path = filedialog.askdirectory(title="Select Folder Containing PDFs")
        if not dir_path:
            return
        try:
            records = prepare_books_from_directory(dir_path, campaign_dir=ConfigHelper.get_campaign_dir())
        except Exception as exc:
            messagebox.showerror("Import Folder", f"Failed to prepare books:\n{exc}")
            return
        self._persist_imported_books(records)

    def _persist_imported_books(self, records):
        records = [rec for rec in records if isinstance(rec, dict)]
        if not records:
            messagebox.showinfo("Import Books", "No new PDF files were found to import.")
            return

        try:
            existing_items = self.model_wrapper.load_items()
        except Exception as exc:
            messagebox.showerror("Import Books", f"Failed to load existing books:\n{exc}")
            return

        existing_by_title = {}
        for item in existing_items:
            title = item.get("Title")
            if isinstance(title, str):
                existing_by_title[title.casefold()] = item

        to_save = []
        titles_for_indexing = []
        for record in records:
            title = record.get("Title", "")
            if not isinstance(title, str) or not title.strip():
                continue
            key = title.casefold()
            titles_for_indexing.append(title)
            if key in existing_by_title:
                merged = dict(existing_by_title[key])
                merged.update(record)
                to_save.append(merged)
            else:
                to_save.append(record)

        if not to_save:
            messagebox.showinfo("Import Books", "All selected books are already in the library.")
            return

        try:
            self.model_wrapper.save_items(to_save, replace=False)
        except Exception as exc:
            messagebox.showerror("Import Books", f"Failed to save imported books:\n{exc}")
            return

        self.items = self.model_wrapper.load_items()
        self.filter_items(self.search_var.get())
        messagebox.showinfo(
            "Import Books",
            f"Imported {len(to_save)} book(s). Indexing will continue in the background.",
        )
        self._queue_book_indexing(titles_for_indexing)

    def _queue_book_indexing(self, titles):
        filtered_titles = [t.strip() for t in titles if isinstance(t, str) and t.strip()]
        if not filtered_titles:
            return

        title_lookup = {t.casefold(): t for t in filtered_titles}

        def worker():
            try:
                items = self.model_wrapper.load_items()
            except Exception as exc:
                log_warning(
                    f"Failed to load books for indexing: {exc}",
                    func_name="GenericListView._queue_book_indexing",
                )
                return

            campaign_dir = ConfigHelper.get_campaign_dir()
            target_records = []
            for item in items:
                title = item.get("Title")
                if not isinstance(title, str):
                    continue
                if title.casefold() not in title_lookup:
                    continue
                target_records.append(dict(item))

            if not target_records:
                return

            prepping = []
            for record in target_records:
                update = dict(record)
                update["IndexStatus"] = "indexing"
                prepping.append(update)

            if prepping:
                try:
                    self.model_wrapper.save_items(prepping, replace=False)
                except Exception as exc:
                    log_warning(
                        f"Failed to mark books as indexing: {exc}",
                        func_name="GenericListView._queue_book_indexing",
                    )
                    return

            final_updates = []
            success = 0
            failures = []
            for record in target_records:
                attachment = record.get("Attachment", "")
                try:
                    page_count, extracted_text, extracted_pages = extract_text_from_book(
                        attachment, campaign_dir=campaign_dir
                    )
                    update = dict(record)
                    update["PageCount"] = page_count
                    update["ExtractedText"] = extracted_text
                    update["ExtractedPages"] = extracted_pages
                    update["IndexStatus"] = "indexed"
                    final_updates.append(update)
                    success += 1
                except Exception as exc:
                    log_warning(
                        f"Failed to index book '{record.get('Title', 'Unknown')}': {exc}",
                        func_name="GenericListView._queue_book_indexing",
                    )
                    update = dict(record)
                    update.setdefault("ExtractedText", "")
                    update.setdefault("ExtractedPages", [])
                    update["IndexStatus"] = f"error: {exc}"
                    final_updates.append(update)
                    failures.append((record.get("Title"), str(exc)))

            if final_updates:
                try:
                    self.model_wrapper.save_items(final_updates, replace=False)
                except Exception as exc:
                    log_warning(
                        f"Failed to persist indexed books: {exc}",
                        func_name="GenericListView._queue_book_indexing",
                    )
                    return

            self.after(0, lambda: self._on_book_indexing_complete(success, failures))

        threading.Thread(target=worker, daemon=True).start()

    def _on_book_indexing_complete(self, success_count, failures):
        try:
            self.items = self.model_wrapper.load_items()
        except Exception as exc:
            messagebox.showerror("Book Indexing", f"Failed to refresh books after indexing:\n{exc}")
            return
        self.filter_items(self.search_var.get())

        if failures:
            failed_titles = ", ".join(title or "(Unknown)" for title, _ in failures[:5])
            if len(failures) > 5:
                failed_titles += ", …"
            message = [f"Indexed {success_count} book(s).", f"Failed to index {len(failures)} book(s): {failed_titles}."]
            messagebox.showwarning("Book Indexing", "\n".join(message))
        else:
            messagebox.showinfo("Book Indexing", f"Indexed {success_count} book(s).")

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
        previous_selection = set(self._last_tree_selection)
        current_selection = self.tree.selection()
        selection_set = {iid for iid in current_selection}
        newly_selected = selection_set - previous_selection
        deselected = previous_selection - selection_set
        selected = set()
        for iid in current_selection:
            _, base_id = self._find_item_by_iid(iid)
            if base_id:
                selected.add(base_id)
        self.selected_iids = selected
        if current_selection:
            focus_iid = self.tree.focus()
            if focus_iid not in current_selection:
                self.tree.focus(current_selection[0])
        multi_select = len(current_selection) > 1
        if multi_select and current_selection:
            first_iid = current_selection[0]
            if (
                first_iid in self._auto_expanded_rows
                and first_iid not in self._pinned_linked_rows
            ):
                self._collapse_linked_rows(first_iid)
        if not self._link_toggle_in_progress and not multi_select:
            for iid in newly_selected:
                if iid in self._link_children:
                    continue
                groups = self._linked_rows.get(iid)
                if groups:
                    self._expand_linked_rows(iid, groups, auto=True)
        for iid in deselected:
            if iid in self._auto_expanded_rows and iid not in self._pinned_linked_rows:
                self._collapse_linked_rows(iid)
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
        if self._link_column:
            if self._link_column not in display:
                display = display + [self._link_column]
            display = [self._link_column] + [c for c in display if c != self._link_column]
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
        
