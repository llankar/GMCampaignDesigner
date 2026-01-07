"""Dialog for managing campaign system definitions."""

from __future__ import annotations

import json
import tkinter as tk
from contextlib import closing
from tkinter import messagebox

import customtkinter as ctk

from db.db import get_connection, get_selected_system_slug, set_selected_system_slug
from modules.dice import dice_preferences
from modules.helpers import system_config
from modules.helpers.logging_helper import log_exception, log_module_import
from modules.helpers.selection_dialog import SelectionDialog

log_module_import(__name__)


class SystemManagerDialog(ctk.CTkToplevel):
    """Allow editing the list of campaign systems stored in the database."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.title("Manage Campaign Systems")
        self.geometry("1040x640")
        self.minsize(980, 600)

        self._systems: dict[str, dict[str, str | None]] = {}
        self._list_order: list[str] = []
        self._current_slug: str | None = None
        self._mode: str = "edit"
        self._active_slug: str | None = None

        self.slug_var = tk.StringVar()
        self.label_var = tk.StringVar()
        self.default_formula_var = tk.StringVar()
        self.status_var = tk.StringVar(value="")
        self.active_var = tk.StringVar(value="")

        self.system_listbox: tk.Listbox | None = None
        self.supported_faces_text: ctk.CTkTextbox | None = None
        self.analyzer_config_text: ctk.CTkTextbox | None = None

        self._build_ui()
        self._load_systems()
        self._refresh_active_label()
        self._select_initial_system()

        self.transient(master)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self) -> None:
        root = ctk.CTkFrame(self)
        root.pack(fill="both", expand=True, padx=18, pady=18)
        root.grid_columnconfigure(0, weight=1, minsize=240)
        root.grid_columnconfigure(1, weight=3)
        root.grid_rowconfigure(0, weight=1)

        list_frame = ctk.CTkFrame(root)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(list_frame, text="Campaign Systems:").grid(row=0, column=0, sticky="w", pady=(0, 8))

        listbox = tk.Listbox(list_frame, exportselection=False, activestyle="none")
        listbox.grid(row=1, column=0, sticky="nsew")
        listbox.bind("<<ListboxSelect>>", self._on_select)
        self.system_listbox = listbox

        list_scroll = ctk.CTkScrollbar(list_frame, command=listbox.yview)
        list_scroll.grid(row=1, column=1, sticky="ns")
        listbox.configure(yscrollcommand=list_scroll.set)

        list_buttons = ctk.CTkFrame(list_frame, fg_color="transparent")
        list_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        list_buttons.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(list_buttons, text="Create", command=self._enter_create_mode).pack(side="left")
        ctk.CTkButton(list_buttons, text="Duplicate", command=self._duplicate_selected).pack(side="left", padx=(8, 0))
        ctk.CTkButton(list_buttons, text="Delete", command=self._delete_selected).pack(side="left", padx=(8, 0))

        form_frame = ctk.CTkFrame(root)
        form_frame.grid(row=0, column=1, sticky="nsew")
        form_frame.grid_columnconfigure(0, weight=1)

        active_label = ctk.CTkLabel(form_frame, textvariable=self.active_var, justify="left")
        active_label.grid(row=0, column=0, sticky="w", pady=(0, 8))

        ctk.CTkLabel(form_frame, text="Slug:").grid(row=1, column=0, sticky="w")
        ctk.CTkEntry(form_frame, textvariable=self.slug_var).grid(row=2, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(form_frame, text="Label:").grid(row=3, column=0, sticky="w")
        ctk.CTkEntry(form_frame, textvariable=self.label_var).grid(row=4, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(form_frame, text="Default formula:").grid(row=5, column=0, sticky="w")
        ctk.CTkEntry(form_frame, textvariable=self.default_formula_var).grid(row=6, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(form_frame, text="Supported faces JSON:").grid(row=7, column=0, sticky="w")
        supported_text = ctk.CTkTextbox(form_frame, height=120)
        supported_text.grid(row=8, column=0, sticky="nsew", pady=(0, 12))
        form_frame.grid_rowconfigure(8, weight=1)
        self.supported_faces_text = supported_text

        ctk.CTkLabel(form_frame, text="Analyzer config JSON:").grid(row=9, column=0, sticky="w")
        analyzer_text = ctk.CTkTextbox(form_frame, height=160)
        analyzer_text.grid(row=10, column=0, sticky="nsew", pady=(0, 12))
        form_frame.grid_rowconfigure(10, weight=1)
        self.analyzer_config_text = analyzer_text

        status_label = ctk.CTkLabel(form_frame, textvariable=self.status_var, text_color="#ff6666", justify="left")
        status_label.grid(row=11, column=0, sticky="w")

        button_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        button_row.grid(row=12, column=0, sticky="e", pady=(16, 0))
        ctk.CTkButton(button_row, text="Save", command=self._save_current).pack(side="right")

    def _load_systems(self) -> None:
        self._systems.clear()
        self._list_order.clear()
        query = (
            "SELECT slug, label, default_formula, supported_faces_json, analyzer_config_json "
            "FROM campaign_systems ORDER BY label, slug"
        )
        with closing(get_connection()) as conn:
            cursor = conn.execute(query)
            for row in cursor.fetchall():
                slug, label, default_formula, supported_faces_json, analyzer_config_json = row
                data = {
                    "slug": str(slug),
                    "label": str(label),
                    "default_formula": default_formula,
                    "supported_faces_json": supported_faces_json,
                    "analyzer_config_json": analyzer_config_json,
                }
                self._systems[str(slug)] = data
                self._list_order.append(str(slug))
        self._render_list()

    def _render_list(self) -> None:
        listbox = self.system_listbox
        if listbox is None:
            return
        listbox.delete(0, "end")
        for slug in self._list_order:
            data = self._systems.get(slug, {})
            label = data.get("label") or slug
            listbox.insert("end", f"{label} ({slug})")

    def _refresh_active_label(self) -> None:
        self._active_slug = get_selected_system_slug()
        if self._active_slug:
            active_label = self._systems.get(self._active_slug, {}).get("label") or self._active_slug
            self.active_var.set(f"Active system: {active_label} ({self._active_slug})")
        else:
            self.active_var.set("Active system: (not set)")

    def _select_initial_system(self) -> None:
        if not self._list_order:
            self._enter_create_mode()
            return
        target = self._active_slug or self._list_order[0]
        try:
            index = self._list_order.index(target)
        except ValueError:
            index = 0
        self._select_list_index(index)

    def _select_list_index(self, index: int) -> None:
        listbox = self.system_listbox
        if listbox is None:
            return
        listbox.selection_clear(0, "end")
        listbox.selection_set(index)
        listbox.activate(index)
        listbox.see(index)
        slug = self._list_order[index]
        self._load_into_form(slug)

    def _load_into_form(self, slug: str) -> None:
        data = self._systems.get(slug)
        if not data:
            return
        self._current_slug = slug
        self._mode = "edit"
        self.slug_var.set(data.get("slug") or "")
        self.label_var.set(data.get("label") or "")
        self.default_formula_var.set(data.get("default_formula") or "")
        self._set_text(self.supported_faces_text, self._format_json(data.get("supported_faces_json")))
        self._set_text(self.analyzer_config_text, self._format_json(data.get("analyzer_config_json")))
        self.status_var.set("")

    def _enter_create_mode(self) -> None:
        self._mode = "create"
        self._current_slug = None
        self.slug_var.set("")
        self.label_var.set("")
        self.default_formula_var.set("")
        self._set_text(self.supported_faces_text, "")
        self._set_text(self.analyzer_config_text, "")
        self.status_var.set("")
        listbox = self.system_listbox
        if listbox is not None:
            listbox.selection_clear(0, "end")

    def _on_select(self, _event=None) -> None:
        listbox = self.system_listbox
        if listbox is None:
            return
        selection = listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if 0 <= index < len(self._list_order):
            slug = self._list_order[index]
            self._load_into_form(slug)

    def _duplicate_selected(self) -> None:
        if not self._current_slug or self._current_slug not in self._systems:
            messagebox.showwarning("No Selection", "Select a system to duplicate first.")
            return
        original = self._systems[self._current_slug]
        suggested_slug = self._suggest_duplicate_slug(original["slug"] or "system")
        self._mode = "create"
        self._current_slug = None
        self.slug_var.set(suggested_slug)
        self.label_var.set(f"{original.get('label') or suggested_slug} Copy")
        self.default_formula_var.set(original.get("default_formula") or "")
        self._set_text(self.supported_faces_text, self._format_json(original.get("supported_faces_json")))
        self._set_text(self.analyzer_config_text, self._format_json(original.get("analyzer_config_json")))
        self.status_var.set("")

    def _suggest_duplicate_slug(self, base: str) -> str:
        candidate = f"{base}_copy"
        if candidate not in self._systems:
            return candidate
        index = 2
        while True:
            candidate = f"{base}_copy_{index}"
            if candidate not in self._systems:
                return candidate
            index += 1

    def _save_current(self) -> None:
        values = self._validate_form()
        if values is None:
            return
        slug, label, formula, faces_json, analyzer_json = values
        try:
            with closing(get_connection()) as conn:
                if self._mode == "create" or self._current_slug is None:
                    conn.execute(
                        """
                        INSERT INTO campaign_systems (
                            slug, label, default_formula, supported_faces_json, analyzer_config_json
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (slug, label, formula, faces_json, analyzer_json),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE campaign_systems
                        SET slug = ?, label = ?, default_formula = ?, supported_faces_json = ?, analyzer_config_json = ?
                        WHERE slug = ?
                        """,
                        (slug, label, formula, faces_json, analyzer_json, self._current_slug),
                    )
                conn.commit()
        except Exception as exc:
            log_exception(
                f"Failed to save campaign system: {exc}",
                func_name="SystemManagerDialog._save_current",
            )
            messagebox.showerror("Save Failed", f"Unable to save the campaign system:\n{exc}")
            return

        if self._current_slug and self._current_slug != slug and self._current_slug == self._active_slug:
            try:
                set_selected_system_slug(slug)
            except Exception as exc:
                log_exception(
                    f"Failed to update active system slug: {exc}",
                    func_name="SystemManagerDialog._save_current",
                )

        self._load_systems()
        self._refresh_active_label()
        self._select_slug(slug)
        system_config.refresh_current_system()
        self.status_var.set("Saved.")

    def _delete_selected(self) -> None:
        if not self._current_slug:
            messagebox.showwarning("No Selection", "Select a system to delete first.")
            return
        if self._current_slug == self._active_slug:
            if len(self._systems) <= 1:
                messagebox.showwarning(
                    "Cannot Delete",
                    "The active system is the only configured system. Create another system before deleting this one.",
                )
                return
            replacement = self._prompt_replacement_system()
            if not replacement:
                return
            try:
                set_selected_system_slug(replacement)
                self._active_slug = replacement
            except Exception as exc:
                log_exception(
                    f"Failed to update active system slug: {exc}",
                    func_name="SystemManagerDialog._delete_selected",
                )
                messagebox.showerror("Update Failed", f"Unable to update the active system:\n{exc}")
                return
        if not messagebox.askyesno("Delete System", "Are you sure you want to delete this system?"):
            return

        try:
            with closing(get_connection()) as conn:
                conn.execute("DELETE FROM campaign_systems WHERE slug = ?", (self._current_slug,))
                conn.commit()
        except Exception as exc:
            log_exception(
                f"Failed to delete campaign system: {exc}",
                func_name="SystemManagerDialog._delete_selected",
            )
            messagebox.showerror("Delete Failed", f"Unable to delete the campaign system:\n{exc}")
            return

        self._load_systems()
        self._refresh_active_label()
        self._select_initial_system()
        system_config.refresh_current_system()

    def _prompt_replacement_system(self) -> str | None:
        options = []
        lookup: dict[str, str] = {}
        for slug in self._list_order:
            if slug == self._current_slug:
                continue
            label = self._systems.get(slug, {}).get("label") or slug
            display = f"{label} ({slug})"
            options.append(display)
            lookup[display] = slug
        if not options:
            return None
        dialog = SelectionDialog(self, "Select Replacement", "Select a replacement system:", options)
        dialog.wait_window()
        selection = dialog.result
        return lookup.get(selection)

    def _select_slug(self, slug: str) -> None:
        if slug not in self._list_order:
            return
        self._select_list_index(self._list_order.index(slug))

    def _validate_form(self) -> tuple[str, str, str | None, str | None, str | None] | None:
        slug = self.slug_var.get().strip().lower()
        label = self.label_var.get().strip()
        default_formula = self.default_formula_var.get().strip()
        faces_raw = self._get_text(self.supported_faces_text)
        analyzer_raw = self._get_text(self.analyzer_config_text)

        if not slug:
            self.status_var.set("Slug is required.")
            return None
        if self._mode == "create" or (self._current_slug and slug != self._current_slug):
            if slug in self._systems:
                self.status_var.set("Slug must be unique.")
                return None
        if not label:
            self.status_var.set("Label is required.")
            return None

        if default_formula:
            canonical = dice_preferences.canonicalize_formula(default_formula)
            if canonical is None:
                self.status_var.set("Default formula is invalid.")
                return None
            default_formula = canonical
        else:
            default_formula = None

        faces_json = self._validate_json_field(faces_raw, "Supported faces JSON")
        if faces_json is None and faces_raw.strip():
            return None

        analyzer_json = self._validate_json_field(analyzer_raw, "Analyzer config JSON")
        if analyzer_json is None and analyzer_raw.strip():
            return None

        return slug, label, default_formula, faces_json, analyzer_json

    def _validate_json_field(self, value: str, label: str) -> str | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            self.status_var.set(f"{label} must be valid JSON.")
            return None
        return json.dumps(parsed, ensure_ascii=False)

    @staticmethod
    def _format_json(raw: str | None) -> str:
        if not raw:
            return ""
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        return json.dumps(parsed, ensure_ascii=False, indent=2)

    @staticmethod
    def _set_text(widget: ctk.CTkTextbox | None, value: str) -> None:
        if widget is None:
            return
        widget.delete("1.0", "end")
        widget.insert("1.0", value)

    @staticmethod
    def _get_text(widget: ctk.CTkTextbox | None) -> str:
        if widget is None:
            return ""
        return widget.get("1.0", "end").strip()
