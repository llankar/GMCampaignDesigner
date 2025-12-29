import ast
import copy
import functools
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
import tkinter as tk
import tkinter.font as tkfont
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox, simpledialog, ttk

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.generic.helpers.treeview_loader import TreeviewLoader
from modules.helpers import theme_manager
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.portrait_helper import (
    parse_portrait_value,
    primary_portrait,
    resolve_portrait_candidate,
    resolve_portrait_path,
)
from modules.helpers.logging_helper import (
    log_debug,
    log_function,
    log_info,
    log_methods,
    log_module_import,
    log_warning,
)
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
    "puzzles": "Puzzles",
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
    "puzzles": "Puzzles",
    "maps": "Maps",
    "books": "Books",
}

AI_CATEGORIZE_BATCH_SIZE = 20
PORTRAIT_MENU_THUMB_SIZE = (48, 48)


try:
    RESAMPLE_MODE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1 fallback
    RESAMPLE_MODE = Image.LANCZOS


def _lazy_editor_window():
    from modules.generic.generic_editor_window import GenericEditorWindow

    return GenericEditorWindow


def _lazy_selection_view():
    from modules.generic.generic_list_selection_view import GenericListSelectionView

    return GenericListSelectionView


def _lazy_portrait_viewer():
    from modules.ui.image_viewer import show_portrait

    return show_portrait


def _lazy_second_screen():
    from modules.ui.second_screen_display import show_entity_on_second_screen

    return show_entity_on_second_screen


def _lazy_audio():
    from modules.audio.entity_audio import (
        get_entity_audio_value,
        play_entity_audio,
        stop_entity_audio,
    )

    return get_entity_audio_value, play_entity_audio, stop_entity_audio


def _lazy_gm_screen():
    from modules.scenarios.gm_layout_manager import GMScreenLayoutManager
    from modules.scenarios.gm_screen_view import GMScreenView

    return GMScreenLayoutManager, GMScreenView


def _lazy_ai_components():
    from modules.ai.authoring_wizard import AuthoringWizardView
    from modules.ai.local_ai_client import LocalAIClient

    return AuthoringWizardView, LocalAIClient


def _lazy_template_loader():
    from modules.helpers.template_loader import load_template

    return load_template


def _lazy_book_importers():
    from modules.books.book_importer import (
        extract_text_from_book,
        prepare_books_from_directory,
        prepare_books_from_files,
    )

    return extract_text_from_book, prepare_books_from_directory, prepare_books_from_files


def _lazy_book_viewer():
    from modules.books.book_viewer import open_book_viewer

    return open_book_viewer


def _lazy_newsletter_components():
    from modules.handouts.newsletter_ai import generate_newsletter_ai
    from modules.handouts.newsletter_dialog import NewsletterConfigDialog
    from modules.handouts.newsletter_generator import build_newsletter_payload
    from modules.handouts.newsletter_window import NewsletterWindow

    return (
        NewsletterConfigDialog,
        NewsletterWindow,
        generate_newsletter_ai,
        build_newsletter_payload,
    )


def _lazy_pdf_processing():
    from modules.books.pdf_processing import export_pdf_page_range, get_pdf_page_count

    return export_pdf_page_range, get_pdf_page_count


def _lazy_object_shelf():
    from modules.objects.object_shelf_canvas_view import ObjectShelfView

    return ObjectShelfView


def _profile_call(name, fn):
    if getattr(fn, "_profile_wrapped", False):
        return fn

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    wrapper._profile_wrapped = True
    return wrapper


def _profile_module_functions(namespace, func_names, prefix):
    for name in func_names:
        fn = namespace.get(name)
        if not callable(fn):
            continue
        namespace[name] = _profile_call(f"{prefix}.{name}", fn)


def _profile_class_methods(cls, prefix):
    for attr_name, attr_value in list(vars(cls).items()):
        if attr_name.startswith("__"):
            continue
        wrapped = None
        if isinstance(attr_value, staticmethod):
            wrapped = staticmethod(_profile_call(f"{prefix}.{attr_name}", attr_value.__func__))
        elif isinstance(attr_value, classmethod):
            wrapped = classmethod(_profile_call(f"{prefix}.{attr_name}", attr_value.__func__))
        elif callable(attr_value):
            wrapped = _profile_call(f"{prefix}.{attr_name}", attr_value)
        if wrapped is not None:
            setattr(cls, attr_name, wrapped)


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

class GenericListView(ctk.CTkFrame):
    def __init__(self, master, model_wrapper, template, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.model_wrapper = model_wrapper
        self.template = template
        self.media_field = self._detect_media_field()
        os.makedirs(PORTRAIT_FOLDER, exist_ok=True)

        # Start with empty collections and stream data in asynchronously to avoid
        # blocking the UI on large tables.
        self.items = []
        self.filtered_items = []
        self._initial_dataset_ready = False
        self.selected_iids = set()
        self._base_to_iids = {}
        self._suppress_tree_select_event = False
        self.grid_cards = []
        self.copied_items = []
        self.ai_categorize_button = None
        self._ai_categorize_running = False
        self._display_queue = []
        self._next_page_start = 0
        self._display_window_start = 0
        self._max_display_rows = 1000000
        self._page_size = 40
        self._group_nodes = {}
        self._pending_scroll_load = False
        self._tree_loader = None
        self._freeze_selection_changes = False
        self._tree_loading = False
        self._payload_executor = ThreadPoolExecutor(max_workers=1)
        self._payload_batch_size = 500
        self._load_queue = None
        self._load_thread = None
        self._load_session_id = 0
        self._first_chunk_inserted = False
        self._seen_base_ids = set()
        self._iid_to_item = {}
        self._portrait_menu_images = []

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
        # Precompute which columns come from long-form fields so we can use
        # a faster, approximate truncation for them instead of expensive font
        # measurements on every cell.
        self._longtext_columns = set()
        for field in self.template.get("fields", []):
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            if not name:
                continue
            ftype = str(field.get("type", "")).strip().lower()
            if ftype in {"longtext", "list_longtext", "list"}:
                self._longtext_columns.add(name)

        # Add a dedicated link column when the template supports linked entities so users
        # can expand/collapse rows to view the linked records.
        self._link_column = "_linked"
        if not self._template_supports_linking():
            self._link_column = None

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

        self._tree_columns = (
            [self._link_column] + list(self.columns)
            if self._link_column
            else list(self.columns)
        )
        self._linked_rows = {}
        self._linked_row_sources = {}
        self._link_targets = {}
        self._link_children = {}
        self._auto_expanded_rows = set()
        self._pinned_linked_rows = set()
        # Remember last row under pointer to make double-click robust
        self._last_pointer_row = None
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
                text="Import PDFs...",
                command=self.import_books_from_files_dialog,
            ).pack(side="left", padx=5)
            ctk.CTkButton(
                self.search_frame,
                text="Import Folder...",
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
        self.grid_image_cache = {}
        self._grid_render_job = None
        self._grid_loading_frame = None
        self._grid_loading_bar = None
        self._grid_render_threshold = 150
        self._grid_batch_delay_ms = 40

        self.shelf_view = None
        if self.model_wrapper.entity_type == "objects":
            shelf_cls = _lazy_object_shelf()
            self.shelf_view = shelf_cls(self, OBJECT_CATEGORY_ALLOWED)

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
                width=0,
                minwidth=0,
                anchor="center",
                stretch=False,
            )

        self._apply_column_settings()

        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        self._vertical_scrollbar = vsb
        self.tree.configure(yscrollcommand=self._on_tree_yview, xscrollcommand=hsb.set)

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
        self._drag_start_row = None
        self._drag_start_xy = None
        self._drag_threshold = 6
        self._tree_loader = TreeviewLoader(self.tree)
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
        self.items = []
        self.filtered_items = []
        self._initial_dataset_ready = False
        self.selected_iids.clear()
        self.refresh_list()
        self._update_bulk_controls()

    def show_portrait_window(self, iid):
        log_info(f"Showing portrait for {self.model_wrapper.entity_type} item: {iid}", func_name="GenericListView.show_portrait_window")
        item, _ = self._find_item_by_iid(iid)
        if not item:
            messagebox.showerror("Error", "Item not found.")
            return
        path = primary_portrait(item.get("Portrait", ""))
        title = str(item.get(self.unique_field, ""))
        show_portrait = _lazy_portrait_viewer()
        show_portrait(path, title)

    def refresh_list(self, *, skip_background_fetch=False):
        log_info(f"Refreshing list for {self.model_wrapper.entity_type}", func_name="GenericListView.refresh_list")
        if not skip_background_fetch:
            self._initial_dataset_ready = False
        # Keep a tiny seed to show immediately
        initial_slice = self.filtered_items[: min(50, len(self.filtered_items))]
        if self._tree_loader:
            self._tree_loader.reset_tree()
        else:
            self.tree.delete(*self.tree.get_children())
        self._last_tree_selection = set()
        self._cell_texts.clear()
        self._linked_rows.clear()
        self._linked_row_sources.clear()
        self._link_targets.clear()
        self._link_children.clear()
        self._auto_expanded_rows.clear()
        self._pinned_linked_rows.clear()
        self._base_to_iids = {}
        self._group_nodes = {}
        self._seen_base_ids = set()
        self._iid_to_item = {}
        self.batch_index = 0
        total_items = len(self.filtered_items)
        # Configure batch sizing before streaming so TreeviewLoader has sane chunks.
        self._configure_batch_settings(total_items)
        # Keep UI insert bursts small so rows appear in ~20-item increments.
        self.batch_size = 10
        # Reset collections to avoid double-counting once background load begins.
        if not skip_background_fetch:
            self.items = []
            self.filtered_items = []
        self._display_queue = []
        self._next_page_start = 0
        self._pending_scroll_load = False
        self._page_size = self._calculate_page_size(total_items)
        # Use small delay to let the UI breathe while streaming in rows.
        self._batch_delay_ms = 5
        self._payload_batch_size = self._calculate_payload_batch_size(total_items)
        self._set_tree_loading(True)
        if self._tree_loader:
            self._tree_loader.reset_tree()
        else:
            self.tree.delete(*self.tree.get_children())
        # Seed the UI immediately with a small slice so something appears at once.
        if initial_slice:
            if not skip_background_fetch:
                self.items.extend(initial_slice)
                self.filtered_items.extend(initial_slice)
            self._display_queue.extend(initial_slice)
            initial_payloads = self._build_payloads(initial_slice)
            self._start_tree_insertion(initial_payloads, reset_tree=True)
            for it in initial_slice:
                base_id = self._get_base_id(it)
                if base_id:
                    self._seen_base_ids.add(base_id)
        if skip_background_fetch:
            self._load_session_id += 1
            self._load_queue = None
            remaining_items = self.filtered_items[len(initial_slice):]
            if remaining_items:
                self._display_queue.extend(remaining_items)
                self._submit_payload_job(remaining_items, reset_tree=False)
            elif not initial_slice:
                self._on_tree_load_complete()
        else:
            # Async background fetch: load DB rows in a worker thread, enqueue to UI.
            self._first_chunk_inserted = False
            self._load_session_id += 1
            session_id = self._load_session_id
            self._load_queue = queue.Queue()
            query = ""
            if hasattr(self, "search_var"):
                try:
                    query = self.search_var.get().strip().lower()
                except Exception:
                    query = ""
            self._load_thread = threading.Thread(
                target=self._background_fetch_items, args=(session_id,), daemon=True
            )
            self._load_thread.start()
            self.after(0, lambda: self._drain_load_queue(session_id, query))
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
        self._update_load_more_state()

    def _configure_batch_settings(self, total_items):
        if total_items > 2500:
            self.batch_size = 800
            self._batch_delay_ms = 10
        elif total_items > 1500:
            self.batch_size = 650
            self._batch_delay_ms = 15
        elif total_items > 800:
            self.batch_size = 500
            self._batch_delay_ms = 20
        else:
            self.batch_size = 300
            self._batch_delay_ms = 25
        # Allow large batches even when many rows are displayed to reduce UI churn
        self._payload_batch_size = self._calculate_payload_batch_size(total_items)

    def _reset_paging(self, total_items):
        self._display_queue = []
        self._display_window_start = 0
        self._next_page_start = self._display_window_start
        self._pending_scroll_load = False
        self._page_size = self._calculate_page_size(total_items)

    def _calculate_page_size(self, total_items):
        if total_items > 3000:
            return 800
        if total_items > 1500:
            return 600
        if total_items > 800:
            return 400
        return 250

    def _calculate_payload_batch_size(self, total_items):
        if total_items > 3000:
            return 1200
        if total_items > 1500:
            return 900
        if total_items > 800:
            return 700
        return 500

    def _reset_tree_for_window(self):
        self._base_to_iids = {}
        self._group_nodes = {}
        if self._tree_loader:
            self._tree_loader.reset_tree()
        else:
            self.tree.delete(*self.tree.get_children(""))
        self._display_queue = []

    def _background_fetch_items(self, session_id):
        """Load items from DB in chunks on a worker thread."""
        import sqlite3

        try:
            conn = self.model_wrapper._get_connection()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {self.model_wrapper.table}")
            batch = 40
            while True:
                rows = cur.fetchmany(batch)
                if not rows:
                    break
                items = [self.model_wrapper._deserialize_row(r) for r in rows]
                if self._load_queue:
                    self._load_queue.put((session_id, items))
            if self._load_queue:
                self._load_queue.put((session_id, None))
        except Exception as exc:
            if self._load_queue:
                self._load_queue.put((session_id, exc))
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _drain_load_queue(self, session_id, query):
        if session_id != self._load_session_id:
            return
        done = False
        try:
            sid, payload = self._load_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if sid == session_id:
                if isinstance(payload, Exception):
                    # Log and stop loading on error
                    log_warning(f"Background load failed: {payload}", func_name="GenericListView._drain_load_queue")
                    done = True
                elif payload is None:
                    done = True
                else:
                    self._handle_loaded_items(payload, query)
        if done:
            self._initial_dataset_ready = True
            self._on_tree_load_complete()
        else:
            self.after(15, lambda: self._drain_load_queue(session_id, query))

    def _handle_loaded_items(self, items, query):
        # Merge into master list
        self.items.extend(items)
        # Apply in-flight filter if any
        if query:
            def iter_search_values(item):
                if self.model_wrapper.entity_type == "books":
                    for col in self.columns:
                        yield self._get_display_value(item, col)
                else:
                    yield from item.values()
            filtered = [
                it for it in items
                if any(query in self.clean_value(v).lower() for v in iter_search_values(it))
            ]
        else:
            filtered = items

        if not filtered:
            self.update_entity_count()
            return

        deduped = []
        for it in filtered:
            base_id = self._get_base_id(it)
            if base_id and base_id in self._seen_base_ids:
                continue
            if base_id:
                self._seen_base_ids.add(base_id)
            deduped.append(it)

        if not deduped:
            self.update_entity_count()
            return

        # Only extend with deduped rows to avoid inflating counts
        self.filtered_items.extend(deduped)
        self._display_queue.extend(deduped)

        reset_tree = not self._first_chunk_inserted
        self._first_chunk_inserted = True
        # Build payloads off the UI thread to keep the interface responsive.
        self._submit_payload_job(deduped, reset_tree)
        self.update_entity_count()

    def _shift_window_forward(self):
        # Windowing is no longer used; keep method for compatibility
        return

    def _queue_next_page(self, *, reset_tree=False):
        if not self.filtered_items:
            self._set_tree_loading(False)
            return
        new_items = self._slice_next_items()
        if not new_items:
            self._set_tree_loading(False)
            return
        self._set_tree_loading(True)
        self._submit_payload_job(new_items, reset_tree)

    def _slice_next_items(self):
        if self._next_page_start >= len(self.filtered_items):
            return []
        end = min(
            self._next_page_start + self._page_size,
            len(self.filtered_items),
        )
        new_items = self.filtered_items[self._next_page_start:end]
        self._display_queue.extend(new_items)
        self._next_page_start = end
        return new_items

    def _submit_payload_job(self, items, reset_tree):
        def build_payload_batches():
            batches = []
            for start in range(0, len(items), self._payload_batch_size):
                subset = items[start : start + self._payload_batch_size]
                payloads = self._build_payloads(subset)
                if payloads:
                    batches.append(payloads)
            return batches

        def on_complete(future):
            try:
                batches = future.result()
            except Exception:
                batches = []
            self.after(0, lambda: self._enqueue_payload_batches(batches, reset_tree))

        future = self._payload_executor.submit(build_payload_batches)
        future.add_done_callback(on_complete)

    def _enqueue_payload_batches(self, batches, reset_tree):
        if not batches:
            self._on_tree_load_complete()
            return
        for index, batch in enumerate(batches):
            self._start_tree_insertion(batch, reset_tree if index == 0 else False)

    def _start_tree_insertion(self, payloads, reset_tree):
        if not payloads:
            self._on_tree_load_complete()
            return
        if not self._tree_loader:
            self._tree_loader = TreeviewLoader(self.tree)
        if reset_tree or not self._tree_loader.is_running():
            self._tree_loader.start(
                payloads,
                self._insert_tree_payload,
                chunk_size=self.batch_size,
                delay_ms=self._batch_delay_ms,
                on_complete=self._on_tree_load_complete,
                reset=reset_tree,
            )
        else:
            self._tree_loader.append(payloads)

    def _build_payloads(self, items):
        payloads = []
        if self.group_column:
            for item in items:
                group_val = self.clean_value(item.get(self.group_column, "")) or "Unknown"
                group_id = self._group_nodes.get(group_val)
                if not group_id:
                    base_group_id = sanitize_id(f"group_{group_val}")
                    group_id = unique_iid(self.tree, base_group_id)
                    self._group_nodes[group_val] = group_id
                    payloads.append({"type": "group", "iid": group_id, "label": group_val})
                payloads.append(self._build_row_payload(item, parent=group_id))
        else:
            payloads.extend(self._build_row_payload(item) for item in items)
        return payloads

    def _build_row_payload(self, item, parent=""):
        raw = item.get(self.unique_field, "")
        if isinstance(raw, dict):
            raw = raw.get("text", "")
        base_id = sanitize_id(raw or f"item_{int(time.time()*1000)}").lower()
        iid = unique_iid(self.tree, base_id)
        name_text = self._format_cell("#0", item.get(self.unique_field, ""), iid)
        values = []
        if self._link_column:
            values.append(self._register_link_source(iid, item))
        values.extend(
            self._format_cell(c, self._get_display_value(item, c), iid) for c in self.columns
        )
        color = self.row_colors.get(base_id)
        return {
            "type": "item",
            "parent": parent,
            "iid": iid,
            "text": name_text,
            "values": tuple(values),
            "base_id": base_id,
            "color": color,
            "item": item,
        }

    def _insert_tree_payload(self, payload):
        if payload.get("type") == "group":
            if self.tree.exists(payload["iid"]):
                return
            self.tree.insert("", "end", iid=payload["iid"], text=payload.get("label", ""), open=True)
            return
        iid = payload["iid"]
        parent = payload.get("parent", "")
        if parent and not self.tree.exists(parent):
            # Safeguard: create the missing group node to avoid Tk errors.
            label = payload.get("group_label") or parent.replace("group_", "").replace("_", " ").title()
            self.tree.insert("", "end", iid=parent, text=label, open=True)
        if self.tree.exists(iid):
            return
        self.tree.insert(
            parent,
            "end",
            iid=iid,
            text=payload.get("text", ""),
            values=payload.get("values", ()),
        )
        color = payload.get("color")
        if color:
            self.tree.item(iid, tags=(f"color_{color}",))
        base_id = payload.get("base_id", "")
        self._register_tree_iid(base_id, iid)
        if base_id:
            self._seen_base_ids.add(base_id)
        # Map iid to original item for reliable lookups when double-clicking.
        if "item" in payload:
            self._iid_to_item[iid] = payload["item"]
        if base_id in self.selected_iids:
            self.tree.selection_add(iid)

    def _on_tree_load_complete(self):
        self._tree_loading = False
        self._set_tree_loading(False)
        self._update_tree_selection_tags()
        self.update_entity_count()
        self._update_load_more_state()
        if self._pending_scroll_load:
            self._pending_scroll_load = False
            self._load_next_page(auto=True)

    def update_entity_count(self):
        total = len(self.filtered_items)
        overall = len(self.items)
        visible = min(len(self._display_queue), total)
        start_idx = 1 if total else 0
        end_idx = visible if total else 0
        text = (
            f"Displaying {start_idx}-{end_idx} of {total} filtered / {overall} total entities"
        )
        if getattr(self, "count_label", None) is None:
            return
        try:
            if self.count_label.winfo_exists():
                self.count_label.configure(text=text)
        except tk.TclError:
            # The label may have been destroyed while a deferred update was still queued.
            return
        if self.shelf_view:
            self.shelf_view.update_summary()

    def _set_tree_loading(self, loading):
        self._tree_loading = loading
        log_info(
            f"Tree loading set to {loading}",
            func_name="GenericListView._set_tree_loading",
        )
        # Keep the widget interactive during streaming updates while still
        # avoiding mid-load selection churn.
        self._freeze_selection_changes = bool(loading)
        if not loading:
            # Ensure any prior suppression is lifted even if exceptions occurred
            # during loading.
            self._suppress_tree_select_event = False

    def _can_load_more(self):
        return False

    def _update_load_more_state(self):
        state = tk.DISABLED
        if getattr(self, "load_more_button", None) and self.load_more_button.winfo_exists():
            self.load_more_button.configure(state=state)

    def _load_next_page(self, auto=False):
        self._pending_scroll_load = False

    def _on_tree_yview(self, first, last):
        if getattr(self, "_vertical_scrollbar", None):
            self._vertical_scrollbar.set(first, last)
        # No-op for infinite scrolling; everything is loaded eagerly.

    def _maybe_trigger_scroll_load(self, last):
        return

    def _trigger_scroll_load(self):
        return

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
        self._cancel_grid_render()
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
        self._cancel_grid_render()
        self.tree_frame.pack_forget()
        self.grid_frame.pack_forget()
        self.shelf_view.show(before_widget=self.footer_frame)
        self.shelf_view.populate()
        self.shelf_view.refresh_selection()
        self.shelf_view.start_visibility_monitor()
        self.update_entity_count()
        self._update_view_toggle_state()

    def _cancel_grid_render(self):
        if self._grid_render_job:
            try:
                self.after_cancel(self._grid_render_job)
            except Exception:
                pass
        self._grid_render_job = None

    def _show_grid_loading_indicator(self, row, columns):
        if self._grid_loading_frame is None or not self._grid_loading_frame.winfo_exists():
            self._grid_loading_frame = ctk.CTkFrame(self.grid_container, fg_color="#2B2B2B")
            self._grid_loading_bar = ctk.CTkProgressBar(
                self._grid_loading_frame, mode="indeterminate", width=200
            )
            self._grid_loading_bar.pack(fill="x", padx=10, pady=(5, 0))
            self._grid_loading_bar.start()
            ctk.CTkLabel(
                self._grid_loading_frame,
                text="Loading more...",
                font=("Segoe UI", 11, "bold"),
                justify="center",
            ).pack(fill="x", padx=10, pady=(0, 5))
        self._grid_loading_frame.grid(
            row=row,
            column=0,
            columnspan=columns,
            padx=10,
            pady=10,
            sticky="ew",
        )

    def _hide_grid_loading_indicator(self):
        if self._grid_loading_bar and self._grid_loading_bar.winfo_exists():
            try:
                self._grid_loading_bar.stop()
            except Exception:
                pass
        if self._grid_loading_frame and self._grid_loading_frame.winfo_exists():
            self._grid_loading_frame.destroy()
        self._grid_loading_frame = None
        self._grid_loading_bar = None

    def _calculate_grid_batch_size(self, total):
        if total > 800:
            return 90
        if total > 500:
            return 70
        if total > 300:
            return 60
        if total > 150:
            return 50
        return total or 1

    def _create_grid_card(self, item, row, col):
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
        name_label = ctk.CTkLabel(card, text=name, justify="center", wraplength=160)
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
        return card

    def _render_grid_batch(self):
        if not hasattr(self, "grid_container"):
            return
        total = len(self.filtered_items)
        if total == 0:
            self._hide_grid_loading_indicator()
            return
        start = getattr(self, "_grid_batch_index", 0)
        if start >= total:
            self._hide_grid_loading_indicator()
            return
        end = min(start + getattr(self, "_grid_batch_size", total), total)
        columns = getattr(self, "_grid_columns", 4)
        for idx in range(start, end):
            item = self.filtered_items[idx]
            row, col = divmod(idx, columns)
            self._create_grid_card(item, row, col)
        self._grid_batch_index = end
        self._refresh_grid_selection()
        if end < total and getattr(self, "_grid_use_batches", False):
            next_row = (end + columns - 1) // columns
            self._show_grid_loading_indicator(next_row, columns)
            self._grid_render_job = self.after(self._grid_batch_delay_ms, self._render_grid_batch)
        else:
            self._grid_render_job = None
            self._hide_grid_loading_indicator()

    def populate_grid(self):
        if not hasattr(self, "grid_container"):
            return
        self._cancel_grid_render()
        for child in self.grid_container.winfo_children():
            child.destroy()
        self.grid_images.clear()
        self.grid_cards = []
        self._grid_batch_index = 0
        self._grid_columns = 4
        for col in range(self._grid_columns):
            self.grid_container.grid_columnconfigure(col, weight=1)
        if not self.filtered_items:
            self._hide_grid_loading_indicator()
            ctk.CTkLabel(self.grid_container, text="No entities to display").grid(
                row=0, column=0, padx=10, pady=10, sticky="w"
            )
            return

        total = len(self.filtered_items)
        self._grid_batch_size = self._calculate_grid_batch_size(total)
        self._grid_use_batches = total > self._grid_render_threshold
        if not self._grid_use_batches:
            self._grid_batch_size = total
        self._hide_grid_loading_indicator()
        self._render_grid_batch()

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
        cache_key = resolved or "__placeholder__"
        cached = self.grid_image_cache.get(cache_key)
        if cached:
            self.grid_images.append(cached)
            return cached
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
        self.grid_image_cache[cache_key] = ctk_image
        self.grid_images.append(ctk_image)
        return ctk_image

    def _edit_item(self, item):
        editor_cls = _lazy_editor_window()
        editor = editor_cls(
            self.master,
            item,
            self.template,
            self.model_wrapper,
            creation_mode=False,
        )
        self.master.wait_window(editor)
        if getattr(editor, "saved", False):
            # Persist only the edited record so filtering does not risk
            # overwriting/deleting the rest of the table.
            try:
                key_field = self.unique_field or self.model_wrapper._infer_key_field()
                self.model_wrapper.save_item(editor.item, key_field=key_field)
            except Exception as exc:
                messagebox.showerror("Save Error", f"Failed to save changes: {exc}")
                return
            self.refresh_list()

    def _edit_selected_item(self):
        selection = self.tree.selection()
        iid = selection[0] if selection else self.tree.focus()
        if not iid:
            return
        item, _ = self._find_item_by_iid(iid)
        if item:
            self._edit_item(item)

    def on_button_press(self, event):
        region = self.tree.identify("region", event.x, event.y)
        log_info(
            f"ButtonPress region={region} row={self.tree.identify_row(event.y)} col={self.tree.identify_column(event.x)} loading={self._tree_loading}",
            func_name="GenericListView.on_button_press",
        )
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
        # Activate row drag only after cursor moved enough to count as a drag.
        if not self.dragging_iid and self._drag_start_row and self._drag_start_xy:
            dx = abs(event.x - self._drag_start_xy[0])
            dy = abs(event.y - self._drag_start_xy[1])
            if max(dx, dy) >= self._drag_threshold:
                self.dragging_iid = self._drag_start_row
                try:
                    self.start_index = self.tree.index(self.dragging_iid)
                except tk.TclError:
                    self.start_index = None
        if self.dragging_iid:
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
            if self.dragging_iid:
                self.on_tree_drop(event)
        self._reset_drag_state()
        self._save_column_settings()

    def on_tree_click(self, event):
        column = self._normalize_column_id(self.tree.identify_column(event.x))
        row = self.tree.identify_row(event.y)
        log_info(
            f"Tree click row={row} column={column} loading={self._tree_loading}",
            func_name="GenericListView.on_tree_click",
        )
        # Track pointer row for double-click targeting independent of selection
        self._last_pointer_row = row
        if self._link_column and column == self._link_column and row:
            self.tree.selection_set(row)
            self.tree.focus(row)
            self._link_toggle_in_progress = True
            try:
                self._toggle_linked_rows(row)
            finally:
                self._link_toggle_in_progress = False
            self.dragging_iid = None
            return
        # Prevent drag operations on non-root rows (e.g., linked headers/names)
        # so clicking a sub-entity does not move it to the top level.
        if row and self.tree.parent(row) != "":
            self._reset_drag_state()
            return
        if self.group_column or self.filtered_items != self.items:
            self._reset_drag_state()
            return
        # Defer starting drag until movement threshold is hit.
        self._drag_start_row = row
        self._drag_start_xy = (event.x, event.y)

    def on_tree_drag(self, event):
        pass

    def on_tree_drop(self, event):
        if not self.dragging_iid:
            return
        if self.group_column or self.filtered_items != self.items:
            self.dragging_iid = None
            return
        # Do not allow dragging of non-root rows (linked children/headers)
        if self.tree.parent(self.dragging_iid) != "":
            self.dragging_iid = None
            return
        if self.start_index is None:
            self.dragging_iid = None
            return
        target_iid = self.tree.identify_row(event.y)
        if not target_iid:
            target_index = len(self.tree.get_children()) - 1
        else:
            # Normalize target to its root ancestor to keep moves within top level
            parent = self.tree.parent(target_iid)
            while parent != "":
                target_iid = parent
                parent = self.tree.parent(target_iid)
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
        self._drag_start_row = None
        self._drag_start_xy = None
        self.start_index = None

    def _reset_drag_state(self):
        self.dragging_iid = None
        self._drag_start_row = None
        self._drag_start_xy = None
        self.start_index = None

    def _load_portrait_menu_image(self, path: str) -> ImageTk.PhotoImage | None:
        resolved = resolve_portrait_candidate(path, ConfigHelper.get_campaign_dir())
        if not resolved:
            return None
        try:
            img = Image.open(resolved)
            img.thumbnail(PORTRAIT_MENU_THUMB_SIZE, RESAMPLE_MODE)
            photo = ImageTk.PhotoImage(img)
            self._portrait_menu_images.append(photo)
            return photo
        except Exception as exc:
            log_warning(
                f"Failed to load portrait menu thumbnail for '{path}': {exc}",
                func_name="GenericListView._load_portrait_menu_image",
            )
            return None

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
        self._load_next_page(auto=True)

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
                vals = []
                if self._link_column:
                    vals.append(self._register_link_source(iid, item))
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
            seen = set()
            for existing in collected:
                if isinstance(existing, dict):
                    key_value = existing.get("display") or ""
                else:
                    key_value = existing
                if not isinstance(key_value, str):
                    key_value = str(key_value)
                if key_value:
                    seen.add(key_value.casefold())
            for entry in values:
                display_name = self.clean_value(entry)
                if not display_name:
                    continue
                display_key = display_name.casefold()
                if display_key in seen:
                    continue

                lookup_candidates = []
                if isinstance(entry, dict):
                    for key in (
                        "Name",
                        "name",
                        "Title",
                        "title",
                        "Target",
                        "target",
                        "Text",
                        "text",
                        "value",
                        "Value",
                    ):
                        value = entry.get(key)
                        if value:
                            lookup_candidates.append(value)
                    if not lookup_candidates and len(entry) == 1:
                        try:
                            lookup_candidates.append(next(iter(entry.values())))
                        except StopIteration:
                            pass
                else:
                    lookup_candidates.append(entry)

                lookup_candidates.append(display_name)
                lookup_values = []
                lookup_seen = set()
                for candidate in lookup_candidates:
                    cleaned = self.clean_value(candidate)
                    if not cleaned:
                        continue
                    normalized = cleaned.casefold()
                    if normalized in lookup_seen:
                        continue
                    lookup_seen.add(normalized)
                    lookup_values.append(cleaned)

                collected.append({"display": display_name, "lookups": lookup_values})
                seen.add(display_key)

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

    def _template_supports_linking(self):
        fields = self.template.get("fields", []) if isinstance(self.template, dict) else []
        if not isinstance(fields, list):
            return False
        for field in fields:
            if not isinstance(field, dict):
                continue
            field_type = str(field.get("type", "")).strip().lower()
            if field_type not in {"list", "list_longtext"}:
                continue
            if field_type == "list_longtext" and not field.get("linked_type"):
                continue
            return True
        return False

    def _has_linkable_content(self, item):
        if not isinstance(self.template, dict):
            return False
        fields = self.template.get("fields", [])
        if not isinstance(fields, list):
            return False
        for field in fields:
            if not isinstance(field, dict):
                continue
            field_type = str(field.get("type", "")).strip().lower()
            if field_type not in {"list", "list_longtext"}:
                continue
            if field_type == "list_longtext" and not field.get("linked_type"):
                continue
            name = field.get("name")
            if not name:
                continue
            raw_values = item.get(name) if isinstance(item, dict) else None
            if isinstance(raw_values, str):
                if raw_values.strip():
                    return True
            elif isinstance(raw_values, (list, tuple, dict)):
                if raw_values:
                    return True
            elif raw_values:
                return True
        return False

    def _register_link_source(self, iid, item):
        marker = ""
        if not self._link_column:
            return marker
        if self._has_linkable_content(item):
            marker = "+"
            self._linked_row_sources[iid] = item
        else:
            self._linked_row_sources.pop(iid, None)
        self._linked_rows.pop(iid, None)
        self._link_children.pop(iid, None)
        self._auto_expanded_rows.discard(iid)
        self._pinned_linked_rows.discard(iid)
        return marker

    def _ensure_linked_groups(self, parent_iid):
        if parent_iid in self._linked_rows:
            return self._linked_rows[parent_iid]
        item = self._linked_row_sources.get(parent_iid)
        if not item:
            return None
        groups = self._collect_linked_entities(item)
        if groups:
            self._linked_rows[parent_iid] = groups
            if self._link_column and self.tree.exists(parent_iid):
                self.tree.set(parent_iid, self._link_column, "-")
        else:
            self._linked_row_sources.pop(parent_iid, None)
            if self._link_column and self.tree.exists(parent_iid):
                self.tree.set(parent_iid, self._link_column, "")
        return groups

    def _toggle_linked_rows(self, parent_iid):
        groups = self._ensure_linked_groups(parent_iid)
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
            for entry in names:
                if isinstance(entry, dict):
                    display_name = (
                        entry.get("display")
                        or entry.get("name")
                        or entry.get("title")
                        or ""
                    )
                else:
                    display_name = entry

                if not isinstance(display_name, str):
                    display_name = str(display_name)
                display_name = display_name.strip()
                if not display_name:
                    display_name = "Unnamed"

                name_base = (
                    sanitize_id(f"{parent_iid}_{slug}_{display_name}")
                    or f"{parent_iid}_{slug}_{int(time.time()*1000)}"
                )
                name_iid = unique_iid(self.tree, name_base)
                self.tree.insert(
                    header_iid,
                    "end",
                    iid=name_iid,
                    text=display_name,
                    values=self._blank_row_values(),
                )
                if isinstance(entry, dict):
                    lookup_payload = dict(entry)
                    lookup_payload.setdefault("display", display_name)
                    if not lookup_payload.get("lookups"):
                        lookup_payload["lookups"] = [display_name]
                else:
                    lookup_payload = {"display": display_name, "lookups": [display_name]}
                self._link_targets[name_iid] = (slug, lookup_payload)
                name_nodes.append(name_iid)
        if headers:
            self._link_children[parent_iid] = {"headers": headers, "names": name_nodes}
        if self._link_column:
            self.tree.set(parent_iid, self._link_column, "-")
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
            marker = "+" if parent_iid in self._linked_row_sources else ""
            self.tree.set(parent_iid, self._link_column, marker)
        self._auto_expanded_rows.discard(parent_iid)
        self._pinned_linked_rows.discard(parent_iid)
        self._linked_rows.pop(parent_iid, None)

    def _open_link_target(self, iid):
        target = self._link_targets.get(iid)
        if not target:
            return
        slug, payload = target
        display_name = ""
        lookup_values = []
        if isinstance(payload, dict):
            display_name = (
                payload.get("display")
                or payload.get("name")
                or payload.get("title")
                or ""
            )
            raw_lookups = payload.get("lookups")
            if isinstance(raw_lookups, (list, tuple, set)):
                lookup_values.extend(raw_lookups)
            elif isinstance(raw_lookups, str):
                lookup_values.append(raw_lookups)
            elif raw_lookups is not None:
                lookup_values.append(raw_lookups)
            for key in (
                "Name",
                "name",
                "Title",
                "title",
                "Target",
                "target",
                "Text",
                "text",
                "value",
                "Value",
            ):
                if key in payload:
                    lookup_values.append(payload.get(key))
        else:
            display_name = str(payload)
            lookup_values.append(payload)

        if not display_name:
            for candidate in lookup_values:
                candidate_str = self.clean_value(candidate)
                if candidate_str:
                    display_name = candidate_str
                    break

        normalized_lookups = set()
        for candidate in lookup_values:
            candidate_str = self.clean_value(candidate)
            if not candidate_str:
                continue
            normalized = candidate_str.casefold()
            if normalized in normalized_lookups:
                continue
            normalized_lookups.add(normalized)

        if not normalized_lookups and display_name:
            display_candidate = self.clean_value(display_name)
            if display_candidate:
                normalized_lookups.add(display_candidate.casefold())

        if not normalized_lookups:
            return

        try:
            wrapper = GenericModelWrapper(slug)
        except Exception as exc:
            messagebox.showerror("Open Linked Entity", f"Unable to prepare editor for '{slug}': {exc}")
            return
        try:
            load_template = _lazy_template_loader()
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
                    candidates.append(raw_value.get(key, ""))
                if len(raw_value) == 1:
                    try:
                        candidates.append(next(iter(raw_value.values())))
                    except StopIteration:
                        pass
                candidates.append(raw_value)
            else:
                candidates.append(raw_value)

            cleaned_candidate = self.clean_value(raw_value)
            if cleaned_candidate:
                candidates.append(cleaned_candidate)

            for candidate in candidates:
                candidate_str = self.clean_value(candidate)
                if not candidate_str:
                    continue
                if candidate_str.casefold() in normalized_lookups:
                    target_item = record
                    break
            if target_item:
                break

        if not target_item:
            display_label = self._display_label_for_slug(slug) or slug
            messagebox.showerror(
                "Open Linked Entity",
                f"Could not find '{display_name}' in {display_label}.",
            )
            return

        editor_cls = _lazy_editor_window()
        editor = editor_cls(
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
                current_query = self.search_var.get() if hasattr(self, "search_var") else ""
                try:
                    self.search_var.set(current_query)
                except Exception:
                    pass
                self.reload_from_db()

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
        match = re.fullmatch(r"(\d+)(...:\s*-\s*(\d+))...", cleaned)
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
        open_book_viewer = _lazy_book_viewer()
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
        export_pdf_page_range, get_pdf_page_count = _lazy_pdf_processing()
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
        # Use a cheap, width-based estimate to avoid expensive tk font measurements per cell.
        try:
            width = self.tree.column(column_id, "width")
        except Exception:
            width = 0
        if width <= 0:
            return text
        # Rough chars per pixel; subtract padding to reflect tree padding.
        char_limit = max(8, int((width - 10) / 6))
        if len(text) <= char_limit:
            return text
        return text[: max(char_limit - len(self._ellipsis), 0)].rstrip() + self._ellipsis

    def _approximate_truncate(self, text, column_id):
        """Cheap truncation for longtext columns: trim by character count."""
        try:
            width = self.tree.column(column_id, "width")
        except Exception:
            width = 0
        char_limit = max(30, int(width / 6) if width else 120)
        if len(text) <= char_limit:
            return text
        return text[: max(char_limit - len(self._ellipsis), 0)].rstrip() + self._ellipsis

    def sort_column(self, column_name):
        if not hasattr(self, "sort_directions"):
            self.sort_directions = {}
        asc = self.sort_directions.get(column_name, True)
        self.sort_directions[column_name] = not asc
        self.filtered_items.sort(
            key=lambda x: str(x.get(column_name, "")),
            reverse=not asc
        )
        self.refresh_list(skip_background_fetch=True)

    def on_double_click(self, event):
        # Resolve target strictly from pointer position to avoid stale selection
        click_iid = self.tree.identify_row(event.y)
        iid = click_iid or self._last_pointer_row
        if not iid:
            # Fallback to selection/focus only as last resort
            selection = self.tree.selection()
            iid = selection[0] if selection else self.tree.focus()
        log_info(
            f"Double-click: click_iid={click_iid}, resolved_iid={iid}, tree_loading={self._tree_loading}",
            func_name="GenericListView.on_double_click",
        )
        if not iid:
            return
        # Do not force selection changes here; it can interfere with child targeting
        if iid in self._link_targets:
            self._open_link_target(iid)
            # Clear pointer snapshot after handling
            self._last_pointer_row = None
            return
        item, _ = self._find_item_by_iid(iid)
        if not item:
            # Fallback: resolve by the visible text in the unique column to handle
            # rare cases where the iid mapping was not populated yet.
            try:
                display_name = self.tree.item(iid, "text")
            except Exception:
                display_name = ""
            if display_name:
                normalized = self.clean_value(display_name)
                for candidate in self.filtered_items or self.items:
                    if self.clean_value(candidate.get(self.unique_field, "")) == normalized:
                        item = candidate
                        break
        if item:
            modifiers = getattr(event, "state", 0)
            if (
                self.model_wrapper.entity_type == "books"
                and not (modifiers & 0x0004 or modifiers & 0x0001)
            ):
                self.open_book(item)
            else:
                self._edit_item(item)
        else:
            log_info(
                f"Double-click could not resolve item: iid={iid}, "
                f"tree_loading={self._tree_loading}, "
                f"iid_cache={len(self._iid_to_item)}, base_map={len(self._base_to_iids)}, "
                f"display_rows={len(self._display_queue)}",
                func_name="GenericListView.on_double_click",
            )
        # Clear pointer snapshot after handling
        self._last_pointer_row = None

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
        portrait_paths = []
        if item:
            portrait_paths = [
                path
                for path in parse_portrait_value(item.get("Portrait", ""))
                if resolve_portrait_candidate(path, ConfigHelper.get_campaign_dir())
            ]
        has_portrait = bool(portrait_paths)
        self._portrait_menu_images = []

        menu = tk.Menu(self, tearoff=0)
        if self.model_wrapper.entity_type == "books" and item:
            menu.add_command(
                label="Open Book",
                command=lambda it=item: self.open_book(it),
            )
            menu.add_command(
                label="Extract Pages...",
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
                label="Edit Details...",
                command=lambda it=item: self._edit_item(it),
            )
            menu.add_separator()
        if item and self.model_wrapper.entity_type != "books":
            menu.add_command(
                label="Edit...",
                command=self._edit_selected_item,
            )
        if self.model_wrapper.entity_type == "scenarios":
            menu.add_command(
                label="Open in GM Screen",
                command=lambda: self.open_in_gm_screen(iid)
            )
            menu.add_command(
                label="Generate Newsletter...",
                command=lambda: self.open_newsletter_preview(iid),
            )
        if item:
            menu.add_command(
                label="Display on Second Screen",
                command=lambda: self.display_on_second_screen(iid)
            )
        if has_portrait:
            show_portrait = _lazy_portrait_viewer()
            title = str(item.get(self.unique_field, "")) if item else ""
            if len(portrait_paths) == 1:
                menu.add_command(
                    label="Show Portrait",
                    command=lambda p=portrait_paths[0]: show_portrait(p, title),
                )
            else:
                portrait_menu = tk.Menu(menu, tearoff=0)
                for index, path in enumerate(portrait_paths, start=1):
                    label = f"Portrait {index}"
                    portrait_image = self._load_portrait_menu_image(path)
                    if portrait_image:
                        portrait_menu.add_command(
                            label=label,
                            image=portrait_image,
                            compound="left",
                            command=lambda p=path: show_portrait(p, title),
                        )
                    else:
                        portrait_menu.add_command(
                            label=label,
                            command=lambda p=path: show_portrait(p, title),
                        )
                menu.add_cascade(label="Show Portraits", menu=portrait_menu)
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
                _, _, stop_audio = _lazy_audio()
                menu.add_command(label="Stop Audio", command=stop_audio)
        menu.post(event.x_root, event.y_root)

    def display_on_second_screen(self, iid):
        log_info(f"Displaying {self.model_wrapper.entity_type} on second screen: {iid}", func_name="GenericListView.display_on_second_screen")
        item, _ = self._find_item_by_iid(iid)
        if not item:
            return
        title = str(item.get(self.unique_field, ""))
        fields = list(self.display_fields) if getattr(self, 'display_fields', None) else list(self.columns[:3])
        show_on_second_screen = _lazy_second_screen()
        show_on_second_screen(item=item, title=title, fields=fields)

    def open_newsletter_preview(self, iid):
        item, _ = self._find_item_by_iid(iid)
        if not item:
            return
        scenario_title = str(item.get("Title") or item.get(self.unique_field, "")).strip()
        if not scenario_title:
            messagebox.showwarning(
                "Newsletter",
                "Impossible de déterminer le titre du scénario.",
            )
            return

        (
            NewsletterConfigDialog,
            NewsletterWindow,
            generate_newsletter_ai,
            build_newsletter_payload,
        ) = _lazy_newsletter_components()

        def _handle_generate(config):
            sections = config.get("sections") or []
            language = config.get("language")
            style = config.get("style")
            use_ai = bool(config.get("use_ai"))
            base_text = config.get("base_text")
            pcs = config.get("pcs") or []

            if use_ai:
                ai_text = generate_newsletter_ai(
                    {
                        "scenario_title": scenario_title,
                        "sections": sections,
                        "base_text": base_text,
                        "pcs": pcs,
                    },
                    language,
                    style,
                )
                NewsletterWindow(
                    self,
                    ai_text=ai_text,
                    language=language,
                    style=style,
                    title=f"Newsletter - {scenario_title}",
                )
            else:
                payload = build_newsletter_payload(
                    scenario_title,
                    sections,
                    language,
                    style,
                    base_text,
                    pcs,
                )
                NewsletterWindow(
                    self,
                    payload=payload,
                    language=language,
                    style=style,
                    title=f"Newsletter - {scenario_title}",
                )

        dialog = NewsletterConfigDialog(self, scenario_title, on_generate=_handle_generate)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.focus_force()
        dialog.wait_window(dialog)

    def _get_audio_value(self, item):
        if not item:
            return ""
        get_audio_value, _, _ = _lazy_audio()
        return get_audio_value(item)

    def play_item_audio(self, item):
        audio_value = self._get_audio_value(item)
        if not audio_value:
            messagebox.showinfo("Audio", "No audio file configured for this entry.")
            return
        name = str(item.get(self.unique_field, "Entity"))
        _, play_audio, _ = _lazy_audio()
        if not play_audio(audio_value, entity_label=name):
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
        layout_manager_cls, gm_view_cls = _lazy_gm_screen()
        layout_manager = layout_manager_cls()
        view = gm_view_cls(
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
        editor_cls = _lazy_editor_window()
        ed = editor_cls(
            self.master, item, self.template,
            self.model_wrapper, creation_mode
        )
        self.master.wait_window(ed)
        return getattr(ed, "saved", False)

    def filter_items(self, query):
        log_info(f"Filtering {self.model_wrapper.entity_type} with query: {query}", func_name="GenericListView.filter_items")
        trimmed = query.strip()
        # Keep the search box in sync when filtering is triggered programmatically.
        try:
            self.search_var.set(trimmed)
        except Exception:
            pass
        normalized = trimmed.lower()
        has_cache = bool(self.items)

        if normalized and has_cache:
            def iter_search_values(item):
                if self.model_wrapper.entity_type == "books":
                    for col in self.columns:
                        yield self._get_display_value(item, col)
                else:
                    yield from item.values()

            self.filtered_items = [
                it for it in self.items
                if any(normalized in self.clean_value(v).lower() for v in iter_search_values(it))
            ]
            self.refresh_list(skip_background_fetch=True)
            return

        if not normalized and has_cache:
            self.filtered_items = list(self.items)
            self.refresh_list(skip_background_fetch=True)
            return

        # Fall back to streaming from the database when no cached dataset exists yet.
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
            "Merge them into single entities...",
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
        _, _, prepare_books_from_files = _lazy_book_importers()
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
        _, prepare_books_from_directory, _ = _lazy_book_importers()
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

        current_query = self.search_var.get() if hasattr(self, "search_var") else ""
        try:
            self.search_var.set(current_query)
        except Exception:
            pass
        self.reload_from_db()
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
            extract_text_from_book, _, _ = _lazy_book_importers()
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
        current_query = self.search_var.get() if hasattr(self, "search_var") else ""
        try:
            self.search_var.set(current_query)
        except Exception:
            pass
        self.reload_from_db()

        if failures:
            failed_titles = ", ".join(title or "(Unknown)" for title, _ in failures[:5])
            if len(failures) > 5:
                failed_titles += ", ..."
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
        authoring_view, _ = _lazy_ai_components()
        frame = authoring_view(top)
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
        _, ai_client_cls = _lazy_ai_components()
        client = ai_client_cls()
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
        preview = raw.strip().replace("\r", " ").replace("\n", " ") if isinstance(raw, str) else str(raw)
        if len(preview) > 500:
            preview = preview[:497] + "..."
        log_info(
            f"AI categorization response preview: {preview}",
            func_name="GenericListView._request_ai_category_assignments",
        )
        try:
            data = ai_client_cls._parse_json_safe(raw)
        except Exception as exc:
            raise RuntimeError(f"AI returned invalid JSON: {exc}. Raw: {raw[:500]}")

        assignments_raw = None
        allowed_from_ai = None

        def _salvage_assignment_list_from_text(text):
            if not isinstance(text, str):
                return None
            pattern = re.compile(
                r"\"(...:Name|name|Item|item)\"\s*:\s*\"([^\"]+)\"[^{}]*...\"(...:Category|category|Type|type)\"\s*:\s*\"([^\"]+)\"",
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
                    parsed = ai_client_cls._parse_json_safe(value)
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
                        parsed = ai_client_cls._parse_json_safe(current)
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
                parsed = ai_client_cls._parse_json_safe(allowed_from_ai)
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
            "Contact the local AI to classify every object and update the Category field...",
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
        # Fast lookup for streamed rows
        if iid in self._iid_to_item:
            item = self._iid_to_item.get(iid)
            return item, self._get_base_id(item or {}, fallback_iid=iid)

        mapped_base = None
        for base, iids in self._base_to_iids.items():
            if iid == base or iid in iids:
                mapped_base = base
                break

        # Prefer exact match on sanitized ID or mapped base
        for it in self.filtered_items:
            base_id = self._get_base_id(it, fallback_iid=mapped_base or iid)
            if iid == base_id or (mapped_base and base_id == mapped_base):
                return it, base_id

        # If the iid has a duplicate suffix like "_2", strip it and try again
        m = re.match(r"^(.*)_\d+$", iid or "")
        if m:
            base = m.group(1)
            for it in self.filtered_items:
                base_id = self._get_base_id(it, fallback_iid=base)
                if base_id == base:
                    return it, base_id

        return None, None

    def _get_base_id(self, item, fallback_iid=None):
        raw = item.get(self.unique_field, "")
        if isinstance(raw, dict):
            raw = raw.get("text", "")
        sanitized = sanitize_id(raw).lower()
        if sanitized:
            return sanitized

        # Try to derive the base id from existing tree mappings
        if fallback_iid:
            for base, iids in self._base_to_iids.items():
                if fallback_iid == base or fallback_iid in iids:
                    return base
            if isinstance(fallback_iid, str) and fallback_iid.startswith("item_"):
                return fallback_iid

        return ""

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
        if self._suppress_tree_select_event or self._freeze_selection_changes:
            return
        start = time.perf_counter()
        previous_selection = set(self._last_tree_selection)
        current_selection = self.tree.selection()
        selection_set = {iid for iid in current_selection}
        newly_selected = selection_set - previous_selection
        deselected = previous_selection - selection_set
        # If a linked child/header is selected, avoid auto-collapsing its parent.
        parents_with_selected_children = set()
        if selection_set and self._link_children:
            for parent_iid, info in self._link_children.items():
                names = set(info.get("names", []))
                headers = set(info.get("headers", []))
                if names.intersection(selection_set) or headers.intersection(selection_set):
                    parents_with_selected_children.add(parent_iid)
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
                and first_iid not in parents_with_selected_children
            ):
                self._collapse_linked_rows(first_iid)
        if not self._link_toggle_in_progress and not multi_select:
            for iid in newly_selected:
                if iid in self._link_children:
                    continue
                groups = self._ensure_linked_groups(iid)
                if groups:
                    self._expand_linked_rows(iid, groups, auto=True)
        for iid in deselected:
            if (
                iid in self._auto_expanded_rows
                and iid not in self._pinned_linked_rows
                and iid not in parents_with_selected_children
            ):
                self._collapse_linked_rows(iid)
        self._update_tree_selection_tags(current_selection)
        self._update_bulk_controls()
        self._refresh_grid_selection()
        if self.shelf_view:
            self.shelf_view.refresh_selection()
        elapsed_ms = (time.perf_counter() - start) * 1000
        log_info(
            f"Selection change processed in {elapsed_ms:.2f} ms (selected={len(selection_set)}, newly_selected={len(newly_selected)}, deselected={len(deselected)})",
            func_name="GenericListView._on_tree_selection_changed",
        )

    def _update_tree_selection_tags(self, selection=None):
        if not hasattr(self, "tree"):
            return

        try:
            if not self.tree.winfo_exists():
                return
            if selection is None:
                selection = self.tree.selection()
        except tk.TclError:
            return

        try:
            selection_set = {iid for iid in selection if self.tree.exists(iid)}
        except tk.TclError:
            return
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
        load_template = _lazy_template_loader()
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

        selection_view = _lazy_selection_view()
        view = selection_view(
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
        load_template = _lazy_template_loader()
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

        selection_view = _lazy_selection_view()
        view = selection_view(
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
        layout_manager_cls, _ = _lazy_gm_screen()
        manager = layout_manager_cls()
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
        
