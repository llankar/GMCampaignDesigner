import os
import re
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.template_loader import (
    create_custom_entity,
    delete_custom_entity,
    load_entity_definitions,
    update_custom_entity,
)
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_methods,
    log_module_import,
)

log_module_import(__name__)

ICON_FILE_TYPES = [
    ("Image Files", "*.png;*.jpg;*.jpeg;*.gif"),
    ("All Files", "*.*"),
]


@log_function
def _slugify(value: str) -> str:
    """Return a lowercase slug safe for template/table names."""
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", value).strip("_")
    return slug.lower()


@log_methods
class NewEntityTypeDialog(ctk.CTkToplevel):
    """Dialog that seeds a new entity template and registers metadata."""

    def __init__(self, master, on_created=None):
        super().__init__(master)
        self.title("New Entity Type")
        self.geometry("760x420")
        self.resizable(False, False)
        self.lift(); self.focus_force(); self.grab_set()

        self._on_created = on_created
        self._icon_path = None
        self._icon_mode = "none"
        self._slug_dirty = False
        self._mode = "create"
        self._current_slug = None
        self._current_icon_path = None
        self._list_order = []

        current_defs = load_entity_definitions()
        self._existing_slugs = set(current_defs.keys())
        self._custom_entities = {
            slug: meta for slug, meta in current_defs.items() if meta.get("is_custom")
        }

        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=16, pady=16)
        main.grid_columnconfigure(0, weight=1, minsize=220)
        main.grid_columnconfigure(1, weight=1)

        list_frame = ctk.CTkFrame(main)
        list_frame.grid(row=0, column=0, rowspan=6, sticky="nsew", padx=(0, 12))
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(list_frame, text="Custom Entity Types:").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        self.entity_listbox = tk.Listbox(
            list_frame, height=12, exportselection=False, activestyle="none"
        )
        self.entity_listbox.grid(row=1, column=0, sticky="nsew")
        self.entity_listbox.bind("<<ListboxSelect>>", self._on_entity_select)
        list_scroll = ctk.CTkScrollbar(list_frame, command=self.entity_listbox.yview)
        list_scroll.grid(row=1, column=1, sticky="ns")
        self.entity_listbox.configure(yscrollcommand=list_scroll.set)

        list_btn_row = ctk.CTkFrame(list_frame)
        list_btn_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        list_btn_row.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            list_btn_row, text="New", command=self._enter_create_mode
        ).pack(side="left")
        self.remove_btn = ctk.CTkButton(
            list_btn_row, text="Remove", command=self._delete_selected
        )
        self.remove_btn.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(main, text="Display Name:").grid(row=0, column=1, sticky="w", pady=(0, 8))
        self.display_name_var = ctk.StringVar()
        self.display_entry = ctk.CTkEntry(main, textvariable=self.display_name_var)
        self.display_entry.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        self.display_name_var.trace_add("write", self._on_display_name_change)

        ctk.CTkLabel(main, text="Identifier (slug):").grid(row=1, column=1, sticky="w", pady=(0, 8))
        self.slug_var = ctk.StringVar()
        self.slug_entry = ctk.CTkEntry(main, textvariable=self.slug_var)
        self.slug_entry.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        self.slug_entry.bind("<KeyRelease>", lambda _e: self._mark_slug_dirty())

        icon_row = ctk.CTkFrame(main)
        icon_row.grid(row=2, column=1, sticky="ew", pady=(0, 12))
        icon_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(icon_row, text="Icon:").grid(row=0, column=0, sticky="w")
        self.icon_label_var = ctk.StringVar(value="(optional)")
        ctk.CTkLabel(icon_row, textvariable=self.icon_label_var, anchor="w").grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ctk.CTkButton(icon_row, text="Choose…", command=self._choose_icon).grid(row=0, column=2, padx=(8, 0))
        ctk.CTkButton(icon_row, text="Clear", command=self._clear_icon).grid(row=0, column=3, padx=(8, 0))

        info = ctk.CTkLabel(
            main,
            text="Creates a template seeded with Name/Description fields.\n"
                 "The identifier becomes the database table name.",
            justify="left",
        )
        info.grid(row=3, column=1, sticky="w", pady=(0, 12))

        btn_row = ctk.CTkFrame(main)
        btn_row.grid(row=4, column=1, sticky="e")
        ctk.CTkButton(btn_row, text="Cancel", command=self._close).pack(side="right", padx=(8, 0))
        self.action_button = ctk.CTkButton(btn_row, text="Create", command=self._perform_action)
        self.action_button.pack(side="right")

        self._refresh_custom_entities()
        self._enter_create_mode()

    def _mark_slug_dirty(self):
        self._slug_dirty = True

    def _on_display_name_change(self, *_):
        if self._slug_dirty:
            return
        suggestion = _slugify(self.display_name_var.get())
        self.slug_var.set(suggestion)

    def _choose_icon(self):
        start_dir = ConfigHelper.get_campaign_dir()
        path = filedialog.askopenfilename(
            title="Select Icon",
            filetypes=ICON_FILE_TYPES,
            initialdir=start_dir if os.path.isdir(start_dir) else os.getcwd(),
        )
        if not path:
            return
        self._icon_path = path
        self._icon_mode = "new"
        self.icon_label_var.set(os.path.basename(path))

    def _clear_icon(self):
        if self._mode == "edit" and self._current_icon_path:
            self._icon_mode = "clear"
        else:
            self._icon_mode = "none"
        self._icon_path = None
        self.icon_label_var.set("(optional)")

    def _validate(self, label: str, slug: str, *, allow_existing: bool = False) -> bool:
        if not label.strip():
            messagebox.showwarning("Missing Name", "Please provide a display name for the entity type.")
            return False
        if not slug:
            messagebox.showwarning("Missing Identifier", "Please provide an identifier for the entity type.")
            return False
        if not re.fullmatch(r"[a-z0-9_]+", slug):
            messagebox.showwarning("Invalid Identifier", "Use only lowercase letters, numbers, and underscores for the identifier.")
            return False
        if not allow_existing and slug in self._existing_slugs:
            messagebox.showwarning("Already Exists", f"An entity type named '{slug}' already exists.")
            return False
        return True

    def _perform_action(self):
        if self._mode == "edit":
            self._update_entity()
        else:
            self._create_entity()

    def _create_entity(self):
        label = self.display_name_var.get().strip()
        slug = self.slug_var.get().strip().lower()
        if not self._validate(label, slug):
            return
        try:
            meta = create_custom_entity(slug, label, self._icon_path)
            log_info(
                f"Created custom entity '{slug}'", func_name="NewEntityTypeDialog._create_entity"
            )
        except Exception as exc:
            messagebox.showerror("Failed", f"Unable to create entity type:\n{exc}")
            return
        messagebox.showinfo("Entity Created", f"Entity type '{label}' is ready to use.")
        if callable(self._on_created):
            try:
                self._on_created(meta)
            except Exception:
                pass
        self._refresh_custom_entities()
        self._enter_edit_mode(slug)

    def _update_entity(self):
        if not self._current_slug:
            return
        label = self.display_name_var.get().strip()
        if not self._validate(label, self._current_slug, allow_existing=True):
            return

        kwargs = {}
        if self._icon_mode == "new" and self._icon_path:
            kwargs["icon_source"] = self._icon_path
        elif self._icon_mode == "clear":
            kwargs["clear_icon"] = True

        try:
            meta = update_custom_entity(self._current_slug, label, **kwargs)
        except Exception as exc:
            messagebox.showerror("Failed", f"Unable to update entity type:\n{exc}")
            return

        self._current_icon_path = meta.get("icon")
        if self._current_icon_path:
            self.icon_label_var.set(os.path.basename(self._current_icon_path))
        else:
            self.icon_label_var.set("(optional)")
        self._icon_mode = "unchanged"
        self._icon_path = None

        messagebox.showinfo("Entity Updated", f"Entity type '{label}' has been updated.")
        self._refresh_custom_entities(preserve_selection=self._current_slug)
        if callable(self._on_created):
            try:
                self._on_created(meta)
            except Exception:
                pass

    def _refresh_custom_entities(self, preserve_selection: str | None = None):
        defs = load_entity_definitions()
        self._existing_slugs = set(defs.keys())
        self._custom_entities = {
            slug: meta for slug, meta in defs.items() if meta.get("is_custom")
        }
        items = sorted(
            ((slug, meta.get("label") or slug) for slug, meta in self._custom_entities.items()),
            key=lambda x: x[1].lower(),
        )
        self.entity_listbox.delete(0, tk.END)
        self._list_order = []
        for slug, label in items:
            self.entity_listbox.insert(tk.END, f"{label} ({slug})")
            self._list_order.append(slug)

        self.entity_listbox.selection_clear(0, tk.END)

        self.remove_btn.configure(
            state="normal" if self._custom_entities else "disabled"
        )

        if preserve_selection and preserve_selection in self._custom_entities:
            try:
                index = self._list_order.index(preserve_selection)
            except ValueError:
                index = None
            if index is not None:
                self.entity_listbox.selection_clear(0, tk.END)
                self.entity_listbox.selection_set(index)
                self.entity_listbox.see(index)
                self._enter_edit_mode(preserve_selection)
                return

    def _enter_create_mode(self):
        self._mode = "create"
        self._current_slug = None
        self._current_icon_path = None
        self._icon_mode = "none"
        self._icon_path = None
        self.display_name_var.set("")
        self.slug_var.set("")
        self.slug_entry.configure(state="normal")
        self.icon_label_var.set("(optional)")
        self.entity_listbox.selection_clear(0, tk.END)
        self.remove_btn.configure(
            state="normal" if self._custom_entities else "disabled"
        )
        self.action_button.configure(text="Create")
        self.display_entry.focus_set()
        self._slug_dirty = False

    def _enter_edit_mode(self, slug: str):
        meta = self._custom_entities.get(slug)
        if not meta:
            self._enter_create_mode()
            return

        self._mode = "edit"
        self._current_slug = slug
        self._current_icon_path = meta.get("icon")
        self._icon_mode = "unchanged"
        self._icon_path = None
        self._slug_dirty = True

        self.display_name_var.set(meta.get("label") or slug)
        self.slug_var.set(slug)
        self.slug_entry.configure(state="disabled")
        if self._current_icon_path:
            self.icon_label_var.set(os.path.basename(self._current_icon_path))
        else:
            self.icon_label_var.set("(optional)")
        self.remove_btn.configure(state="normal")
        self.action_button.configure(text="Save Changes")

    def _on_entity_select(self, _event=None):
        if not getattr(self, "_list_order", None):
            self._enter_create_mode()
            return
        selection = self.entity_listbox.curselection()
        if not selection:
            self._enter_create_mode()
            return
        index = selection[0]
        if index >= len(self._list_order):
            self._enter_create_mode()
            return
        slug = self._list_order[index]
        self._enter_edit_mode(slug)

    def _delete_selected(self):
        selection = self.entity_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(getattr(self, "_list_order", [])):
            return
        slug = self._list_order[index]
        meta = self._custom_entities.get(slug, {})
        label = meta.get("label") or slug
        if not messagebox.askyesno(
            "Remove Entity Type",
            f"Remove custom entity type '{label}'? This will delete its data table.",
        ):
            return
        try:
            delete_custom_entity(slug)
        except Exception as exc:
            messagebox.showerror("Failed", f"Unable to remove entity type:\n{exc}")
            return
        messagebox.showinfo("Entity Removed", f"Entity type '{label}' has been removed.")
        self._refresh_custom_entities()
        self._enter_create_mode()

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
