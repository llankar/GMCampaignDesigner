import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from modules.helpers.template_loader import _load_base_template, save_custom_fields, list_known_entities
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_methods,
    log_module_import,
)

log_module_import(__name__)

FIELD_TYPES = [
    "text",
    "longtext",
    "boolean",
    "list",
    "list_longtext",
    "file",
    "audio",
]


@log_methods
class CustomFieldsEditor(ctk.CTkToplevel):
    """UI to manage user-defined custom fields per entity.

    - Shows base (built-in) fields as read-only for the selected entity
    - Lets users add/remove custom fields (name + type, optional linked_type)
    - Persists to config/custom_fields.json
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("Customize Fields")
        self.geometry("900x600")
        self.lift(); self.focus_force(); self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.entities = list_known_entities() or [
            # Fallback ordering if discovery fails
            "scenarios", "pcs", "npcs", "creatures", "factions", "places", "objects", "informations", "clues", "maps"
        ]
        self.entity_var = tk.StringVar(value=(self.entities[0] if self.entities else ""))

        # Top bar: entity selection + save
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(top, text="Entity:").pack(side="left", padx=(4, 6))
        self.entity_menu = ctk.CTkOptionMenu(top, values=self.entities, variable=self.entity_var, command=self._on_entity_change)
        self.entity_menu.pack(side="left")
        ctk.CTkButton(top, text="Save", command=self._save_current).pack(side="right", padx=(6, 4))

        # Main split: base fields (left) vs custom fields (right)
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Left: Base fields (read-only)
        ctk.CTkLabel(main, text="Base Fields (read-only)", anchor="w").grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        self.base_list = tk.Listbox(main, exportselection=False)
        self.base_list.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        # Right: Custom fields with controls
        ctk.CTkLabel(main, text="Custom Fields", anchor="w").grid(row=0, column=1, sticky="ew", padx=6, pady=(6, 2))
        right = ctk.CTkFrame(main)
        right.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(3, weight=1)

        form = ctk.CTkFrame(right)
        form.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        form.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(form, text="Name").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.name_var = tk.StringVar()
        ctk.CTkEntry(form, textvariable=self.name_var).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(form, text="Type").grid(row=1, column=0, padx=4, pady=4, sticky="w")
        self.type_var = tk.StringVar(value=FIELD_TYPES[0])
        self.type_menu = ctk.CTkOptionMenu(form, values=FIELD_TYPES, variable=self.type_var, command=self._on_type_change)
        self.type_menu.grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(form, text="Linked Type (for list)").grid(row=2, column=0, padx=4, pady=4, sticky="w")
        self.linked_var = tk.StringVar(value="")
        # known linked types match display names used elsewhere
        self.known_linked = ["NPCs", "PCs", "Creatures", "Factions", "Objects", "Places", "Scenarios", "Clues", "Informations", "Maps", "Books"]
        self.linked_menu = ctk.CTkOptionMenu(form, values=[""] + self.known_linked, variable=self.linked_var)
        self.linked_menu.grid(row=2, column=1, padx=4, pady=4, sticky="ew")

        btns = ctk.CTkFrame(right)
        btns.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkButton(btns, text="Add / Update Field", command=self._add_or_update).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Remove Selected", command=self._remove_selected).pack(side="left", padx=4)

        self.custom_list = tk.Listbox(right, exportselection=False)
        self.custom_list.grid(row=3, column=0, sticky="nsew")
        self.custom_list.bind("<<ListboxSelect>>", self._on_select_custom)

        # State
        self._custom_buffer = {}  # entity -> [fields]
        self._on_entity_change(self.entity_var.get())

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _on_entity_change(self, entity: str):
        log_info(f"Loading custom fields for {entity}", func_name="CustomFieldsEditor._on_entity_change")
        # Load base fields
        try:
            base = _load_base_template(entity)
            base_fields = base.get("fields", [])
        except Exception:
            base_fields = []
        self._base_names = [f"{f.get('name','')}  [{f.get('type','text')}]" for f in base_fields]
        self._base_name_set = {str(f.get("name", "")).strip() for f in base_fields}
        self.base_list.delete(0, tk.END)
        for s in self._base_names:
            self.base_list.insert(tk.END, s)

        # Load custom fields for this entity
        customs = list((base.get("custom_fields") or []))
        self._custom_current = customs
        self._refresh_custom_list()
        self.name_var.set("")
        self.type_var.set(FIELD_TYPES[0])
        self.linked_var.set("")

    def _refresh_custom_list(self):
        self.custom_list.delete(0, tk.END)
        for f in self._custom_current:
            label = f"{f.get('name','')}  [{f.get('type','text')}]"
            lt = f.get("linked_type")
            if lt:
                label += f" -> {lt}"
            self.custom_list.insert(tk.END, label)

    def _on_type_change(self, *_):
        t = self.type_var.get().strip().lower()
        # show linked type only for list types
        state = tk.NORMAL if t in ("list", "list_longtext") else tk.DISABLED
        try:
            self.linked_menu.configure(state=state)
        except Exception:
            pass

    def _add_or_update(self):
        log_info(f"Custom field add/update requested for {self.entity_var.get()}", func_name="CustomFieldsEditor._add_or_update")
        name = self.name_var.get().strip()
        ftype = self.type_var.get().strip() or "text"
        linked = self.linked_var.get().strip()
        entity = self.entity_var.get()
        if not name:
            messagebox.showwarning("Invalid Field", "Please provide a field name.")
            return
        if name in self._base_name_set:
            messagebox.showwarning("Locked Field", "This name matches an existing base field and cannot be modified.")
            return
        item = {"name": name, "type": ftype}
        if ftype in ("list", "list_longtext") and linked:
            item["linked_type"] = linked
        # update or append
        replaced = False
        for i, f in enumerate(self._custom_current):
            if str(f.get("name", "")).strip().lower() == name.lower():
                self._custom_current[i] = item
                replaced = True
                break
        if not replaced:
            self._custom_current.append(item)
        self._custom_buffer[entity] = list(self._custom_current)
        self._refresh_custom_list()
        self.name_var.set("")
        self.type_var.set(FIELD_TYPES[0])
        self.linked_var.set("")

    def _remove_selected(self):
        log_info(f"Removing selected custom field for {self.entity_var.get()}", func_name="CustomFieldsEditor._remove_selected")
        sel = self.custom_list.curselection()
        if not sel:
            return
        idx = sel[0]
        try:
            self._custom_current.pop(idx)
            self._custom_buffer[self.entity_var.get()] = list(self._custom_current)
            self._refresh_custom_list()
        except IndexError:
            pass

    def _on_select_custom(self, _evt=None):
        sel = self.custom_list.curselection()
        if not sel:
            return
        idx = sel[0]
        try:
            f = self._custom_current[idx]
        except IndexError:
            return
        self.name_var.set(str(f.get("name", "")))
        self.type_var.set(str(f.get("type", "text")))
        self.linked_var.set(str(f.get("linked_type", "")))
        self._on_type_change()

    def _save_current(self):
        log_info(f"Saving custom fields for {self.entity_var.get()}", func_name="CustomFieldsEditor._save_current")
        entity = self.entity_var.get()
        # Filter out any entries that accidentally collide with base names
        safe = [f for f in self._custom_current if str(f.get("name", "")) not in self._base_name_set]
        try:
            save_custom_fields(entity, safe)
            messagebox.showinfo("Saved", f"Custom fields saved for '{entity}'.\nReopen the entity to see changes.")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
