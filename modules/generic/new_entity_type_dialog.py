import os
import re
import customtkinter as ctk
from tkinter import filedialog, messagebox

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.template_loader import (
    create_custom_entity,
    load_entity_definitions,
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
        self.geometry("560x360")
        self.resizable(False, False)
        self.lift(); self.focus_force(); self.grab_set()

        self._on_created = on_created
        self._icon_path = None
        self._slug_dirty = False

        current_defs = load_entity_definitions()
        self._existing_slugs = set(current_defs.keys())

        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=16, pady=16)
        main.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(main, text="Display Name:").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.display_name_var = ctk.StringVar()
        self.display_entry = ctk.CTkEntry(main, textvariable=self.display_name_var)
        self.display_entry.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        self.display_name_var.trace_add("write", self._on_display_name_change)

        ctk.CTkLabel(main, text="Identifier (slug):").grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.slug_var = ctk.StringVar()
        slug_entry = ctk.CTkEntry(main, textvariable=self.slug_var)
        slug_entry.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        slug_entry.bind("<KeyRelease>", lambda _e: self._mark_slug_dirty())

        icon_row = ctk.CTkFrame(main)
        icon_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        icon_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(icon_row, text="Icon:").grid(row=0, column=0, sticky="w")
        self.icon_label_var = ctk.StringVar(value="(optional)")
        ctk.CTkLabel(icon_row, textvariable=self.icon_label_var, anchor="w").grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ctk.CTkButton(icon_row, text="Choose…", command=self._choose_icon).grid(row=0, column=2, padx=(8, 0))

        info = ctk.CTkLabel(
            main,
            text="Creates a template seeded with Name/Description fields.\n"
                 "The identifier becomes the database table name.",
            justify="left",
        )
        info.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 12))

        btn_row = ctk.CTkFrame(main)
        btn_row.grid(row=4, column=0, columnspan=2, sticky="e")
        ctk.CTkButton(btn_row, text="Cancel", command=self._close).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_row, text="Create", command=self._create_entity).pack(side="right")

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
        self.icon_label_var.set(os.path.basename(path))

    def _validate(self, label: str, slug: str) -> bool:
        if not label.strip():
            messagebox.showwarning("Missing Name", "Please provide a display name for the entity type.")
            return False
        if not slug:
            messagebox.showwarning("Missing Identifier", "Please provide an identifier for the entity type.")
            return False
        if not re.fullmatch(r"[a-z0-9_]+", slug):
            messagebox.showwarning("Invalid Identifier", "Use only lowercase letters, numbers, and underscores for the identifier.")
            return False
        if slug in self._existing_slugs:
            messagebox.showwarning("Already Exists", f"An entity type named '{slug}' already exists.")
            return False
        return True

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
        self._close()

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
