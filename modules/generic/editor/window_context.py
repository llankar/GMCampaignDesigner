import customtkinter as ctk
import os
import requests
import subprocess
import time
import shutil
from urllib.parse import quote_plus
from modules.helpers import text_helpers
from modules.helpers.rich_text_editor import RichTextEditor
from modules.helpers.window_helper import position_window_at_top
from PIL import Image, ImageTk
from PIL import ImageGrab
from tkinter import filedialog,  messagebox
from modules.helpers.swarmui_helper import get_available_models
from modules.helpers.config_helper import ConfigHelper
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.helpers.template_loader import load_template
import tkinter as tk
import random
from modules.helpers.text_helpers import format_longtext
from modules.helpers.text_helpers import ai_text_to_rtf_json
from modules.helpers.dice_markup import parse_inline_actions
from modules.ai.local_ai_client import LocalAIClient
from modules.events.ui.shared.schedule_widgets import EventDatePickerField, EventTimePickerField
import json
import ast
from io import BytesIO
from pathlib import Path
from modules.audio.entity_audio import play_entity_audio, resolve_audio_path, stop_entity_audio
from modules.helpers.portrait_helper import (
    parse_portrait_value,
    primary_portrait,
    serialize_portrait_value,
)
from modules.helpers.logging_helper import (
    log_exception,
    log_function,
    log_info,
    log_methods,
    log_warning,
    log_module_import,
)
from modules.ui.image_browser_dialog import ImageBrowserDialog
from modules.ui.webview.pywebview_client import PyWebviewClient
from modules.generic.editor import SmartEditorToolbar, prioritize_fields

log_module_import(__name__)

SWARMUI_PROCESS = None


class ReadOnlyLongTextPreview(ctk.CTkFrame):
    """Lightweight preview widget for very large longtext fields.

    The Books entity uses a massive OCR transcript (``ExtractedText``) that can
    contain hundreds of thousands of characters.  Rendering that content inside
    ``RichTextEditor`` freezes Tk for several seconds because the widget
    re-computes the layout for every line.  This helper keeps the editor fast by
    showing only a short, read-only preview and deferring the full transcript to
    a separate window when requested.
    """

    PREVIEW_CHAR_LIMIT = 2000

    def __init__(self, parent, field_label: str, raw_value):
        super().__init__(parent)
        self.field_label = field_label
        # Preserve the original payload so ``save()`` can write it back without
        # forcing the UI to materialise the whole transcript.
        self._raw_value = raw_value if raw_value is not None else ""
        self._full_text = self._coerce_to_text(self._raw_value)

        info = ctk.CTkLabel(
            self,
            text=(
                f"{field_label} preview (read-only). "
                "Open the full transcript to view everything."
            ),
            anchor="w",
        )
        info.pack(fill="x", padx=5, pady=(5, 0))

        preview_text = self._full_text
        trimmed = False
        if len(preview_text) > self.PREVIEW_CHAR_LIMIT:
            preview_text = preview_text[: self.PREVIEW_CHAR_LIMIT].rstrip()
            trimmed = True

        self.textbox = ctk.CTkTextbox(self, height=180, wrap="word")
        self.textbox.insert("1.0", preview_text or "(No text extracted yet)")
        if trimmed:
            self.textbox.insert(
                "end",
                "\n\n… (truncated for speed – open the full transcript to read everything)",
            )
        self.textbox.configure(state="disabled")
        self.textbox.pack(fill="x", expand=False, padx=5, pady=5)

        btn_row = ctk.CTkFrame(self)
        btn_row.pack(fill="x", padx=5, pady=(0, 5))

        open_btn = ctk.CTkButton(
            btn_row,
            text="Open Full Transcript",
            command=self._open_full_transcript,
        )
        open_btn.pack(side="right")

    @staticmethod
    def _coerce_to_text(value) -> str:
        if isinstance(value, dict):
            text_val = value.get("text")
            if isinstance(text_val, str):
                return text_val
            return json.dumps(value)
        if isinstance(value, list):
            try:
                return "\n".join(str(v) for v in value)
            except Exception:
                return str(value)
        return str(value or "")

    def _open_full_transcript(self):
        top = ctk.CTkToplevel(self)
        top.title(f"{self.field_label} – Full Transcript")
        top.geometry("900x600")
        position_window_at_top(top)

        textbox = ctk.CTkTextbox(top, wrap="word")
        textbox.pack(fill="both", expand=True, padx=10, pady=10)
        textbox.insert("1.0", self._full_text or "(No text extracted yet)")
        textbox.configure(state="disabled")

    def get_text_data(self):
        """Return the original longtext payload for persistence."""

        return self._raw_value

@log_methods
class CustomDropdown(ctk.CTkToplevel):
    def __init__(self, master, options, command, width=None, max_height=300, **kwargs):
        """
        master      – parent widget (usually the root or your main window)
        options     – list of strings
        command     – callback(value) when the user selects
        width       – desired pixel width (defaults to master widget’s width)
        max_height  – maximum pixel height
        """
        super().__init__(master, **kwargs)
        self.command         = command
        self.all_options     = list(options)
        self.filtered_options= list(options)
        self.max_height      = max_height
        self.overrideredirect(True)

        # ─── Search Entry ─────────────────────────────────────────────────────
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.entry = ctk.CTkEntry(self, textvariable=self.search_var,
                                placeholder_text="Search…")
        self.entry.pack(fill="x", padx=5, pady=(5, 0))
        self.entry.bind("<Return>", lambda e: self._on_activate(e))
        self.entry.focus_set()
       
        # ─── Listbox + Scrollbar ─────────────────────────────────────────────
        container = tk.Frame(self)
        container.pack(fill="both", expand=True, padx=5, pady=5)
        self.listbox = tk.Listbox(container, exportselection=False)
        self.scroll  = tk.Scrollbar(container, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=self.scroll.set)

        # let python size the listbox for us, then enforce max_height below
        self.listbox.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")

        # ─── Now populate & size ────────────────────────────────────────────
        self._populate_options()
        self.update_idletasks()  # make sure all req sizes are calculated

        # determine final geometry
        final_w = width or master.winfo_width()
        total_req_h = self.winfo_reqheight()
        final_h = min(total_req_h, self.max_height)

        # master = the widget you clicked on (you should pass its .winfo_toplevel())
        # you still need to set x,y yourself in open_dropdown:
        self.geometry(f"{final_w}x{final_h}")

        # ensure clicks in entry/listbox don't close us
        self.grab_set()

        # ─── Event Bindings ────────────────────────────────────────────────
        self.listbox.bind("<Double-Button-1>", self._on_activate)
        self.listbox.bind("<Return>",         self._on_activate)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.listbox.bind(seq, self._on_mousewheel)

        for widget in (self, self.entry, self.listbox):
            widget.bind("<Escape>", lambda e: self.destroy())
        self.after_idle(lambda: self.entry.focus_set())

        self.after_idle(lambda: self.bind("<FocusOut>", self._on_focus_out))
        self.listbox.bind("<Return>", self._on_activate)
        self.entry.bind("<Down>", lambda e: self.listbox.focus_set())
                        
    def _populate_options(self):
        self.listbox.delete(0, tk.END)
        for opt in self.filtered_options:
            self.listbox.insert(tk.END, opt)
        if self.filtered_options:
            self.listbox.selection_set(0)

    def _on_search_change(self, *args):
        q = self.search_var.get().lower()
        if q:
            self.filtered_options = [o for o in self.all_options if q in o.lower()]
        else:
            self.filtered_options = list(self.all_options)
        self._populate_options()
        # after filter, we could also dynamically resize height if you like

    def _on_activate(self, event):
        sel = self.listbox.curselection()
        if not sel: return
        value = self.filtered_options[sel[0]]
        self.command(value)
        self.destroy()

    def _on_mousewheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.listbox.yview_scroll(-1, "units")
        else:
            self.listbox.yview_scroll(1,  "units")

    def _on_focus_out(self, event):
        # if the new focus is still inside our Toplevel, do nothing
        new = self.focus_get()
        if new and str(new).startswith(str(self)):
            return
        self.destroy()

@log_function
def load_entities_list(entity_type):
    """
    Creates a model wrapper for the given entity type, fetches all
    database records, and returns a list of names.

    Args:
        entity_type (str): The type of entity to load (e.g., "npcs", "factions").

    Returns:
        list: A list of names for the given entity, or an empty list on error.
    """
    try:
        wrapper = GenericModelWrapper(entity_type)
        entities = wrapper.load_items() # Assumes get_all() returns a list of dictionaries.

        key_field = "Title" if str(entity_type).lower() in {"scenarios", "books"} else "Name"
        options = []
        for entity in entities:
            value = entity.get(key_field)
            if value is None and key_field != "Name":
                value = entity.get("Name")
            if value is None and key_field != "Title":
                value = entity.get("Title")
            label = str(value).strip() if value is not None else ""
            if label:
                options.append(label)

        return options
    except Exception as e:
        # Log error if needed:
        print(f"Error loading {entity_type}: {e}")
        return []

@log_function
def load_factions_list():
    return load_entities_list("factions")

@log_function
def load_npcs_list():
    return load_entities_list("npcs")
@log_function
def load_villains_list():
    return load_entities_list("villains")
@log_function
def load_pcs_list():
    return load_entities_list("pcs")
@log_function
def load_places_list():
    return load_entities_list("places")

@log_function
def load_objects_list():
    return load_entities_list("objects")

@log_function
def load_creatures_list():
    return load_entities_list("creatures")

@log_function
def load_books_list():
    return load_entities_list("books")
