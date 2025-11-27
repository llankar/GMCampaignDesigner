import json
import os
import re
from typing import List, Optional

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.random_table_loader import RandomTableLoader
from modules.helpers.logging_helper import log_exception, log_module_import
from modules.scenarios.dialogs.random_table_import_dialog import RandomTableImportDialog
from modules.scenarios.random_tables_panel import RandomTablesPanel

log_module_import(__name__)


class RandomTableEditorDialog(ctk.CTkToplevel):
    """Dialog to create or edit a structured random table."""

    def __init__(self, master=None, table: Optional[dict] = None):
        super().__init__(master)
        self.title("Random Table Editor")
        self.geometry("760x600")
        self.table = table or {}
        self.table_source = self.table.get("source")
        self.loader = RandomTableLoader(RandomTableLoader.default_data_path())
        self.categories = self.loader.load().get("categories") or []

        self.title_var = tk.StringVar(value=self.table.get("title", ""))
        self.dice_var = tk.StringVar(value=self.table.get("dice", "1d20"))
        self.category_var = tk.StringVar(value=self._resolve_category_name(self.table.get("category")))
        self.tags_var = tk.StringVar(value=", ".join(self.table.get("tags", [])))
        self.system_var = tk.StringVar(value=self.table.get("system", ""))
        self.biome_var = tk.StringVar(value=self.table.get("biome", ""))
        self.theme_var = tk.StringVar(value=self.table.get("theme", ""))
        self.table_id = self.table.get("id")

        self.entry_rows: List[dict] = []

        self._build_ui()
        self._populate_entries(self.table.get("entries") or [])
        self.description_box.insert("1.0", self.table.get("description", ""))

        self.grab_set()
        self.focus_force()

    # ------------------------------------------------------------------
    def _build_ui(self):
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        meta_frame = ctk.CTkFrame(container)
        meta_frame.pack(fill="x", pady=(0, 10))
        meta_frame.columnconfigure(1, weight=1)
        meta_frame.columnconfigure(3, weight=1)
        meta_frame.columnconfigure(5, weight=1)

        ctk.CTkLabel(meta_frame, text="Title:").grid(row=0, column=0, sticky="w", padx=(4, 6), pady=4)
        ctk.CTkEntry(meta_frame, textvariable=self.title_var).grid(row=0, column=1, sticky="ew", pady=4)

        ctk.CTkLabel(meta_frame, text="Dice:").grid(row=0, column=2, sticky="w", padx=(8, 6))
        ctk.CTkEntry(meta_frame, textvariable=self.dice_var, width=140).grid(row=0, column=3, sticky="w", pady=4)

        ctk.CTkLabel(meta_frame, text="Category:").grid(row=1, column=0, sticky="w", padx=(4, 6), pady=4)
        category_values = [cat.get("name") for cat in self.categories if cat.get("name")]
        category_entry = ctk.CTkComboBox(meta_frame, variable=self.category_var, values=category_values)
        category_entry.grid(row=1, column=1, sticky="ew", pady=4)

        ctk.CTkLabel(meta_frame, text="System:").grid(row=1, column=2, sticky="w", padx=(8, 6))
        ctk.CTkEntry(meta_frame, textvariable=self.system_var).grid(row=1, column=3, sticky="ew", pady=4)

        ctk.CTkLabel(meta_frame, text="Theme:").grid(row=1, column=4, sticky="w", padx=(8, 6))
        ctk.CTkEntry(meta_frame, textvariable=self.theme_var).grid(row=1, column=5, sticky="ew", pady=4)

        ctk.CTkLabel(meta_frame, text="Biome:").grid(row=2, column=0, sticky="w", padx=(4, 6), pady=4)
        ctk.CTkEntry(meta_frame, textvariable=self.biome_var).grid(row=2, column=1, sticky="ew", pady=4)

        ctk.CTkLabel(meta_frame, text="Tags (comma separated):").grid(row=2, column=2, sticky="w", padx=(8, 6))
        ctk.CTkEntry(meta_frame, textvariable=self.tags_var).grid(row=2, column=3, sticky="ew", pady=4)

        desc_label = ctk.CTkLabel(container, text="Description:")
        desc_label.pack(anchor="w")
        self.description_box = ctk.CTkTextbox(container, height=60, wrap="word")
        self.description_box.pack(fill="x", pady=(2, 8))

        entries_header = ctk.CTkFrame(container)
        entries_header.pack(fill="x")
        ctk.CTkLabel(entries_header, text="Entries").pack(side="left")
        ctk.CTkButton(entries_header, text="Add Entry", command=self._add_entry_row).pack(side="right")
        ctk.CTkButton(entries_header, text="Import Text", command=self._open_import_dialog).pack(side="right", padx=(0, 6))

        self.entries_frame = ctk.CTkScrollableFrame(container, height=320)
        self.entries_frame.pack(fill="both", expand=True, pady=(4, 8))
        for col, weight in enumerate((1, 1, 4, 2, 0)):
            self.entries_frame.grid_columnconfigure(col, weight=weight)

        actions = ctk.CTkFrame(container)
        actions.pack(fill="x", pady=(6, 0))
        ctk.CTkButton(actions, text="Save", command=self._save).pack(side="right", padx=(6, 0))
        ctk.CTkButton(actions, text="Cancel", command=self.destroy).pack(side="right")

    def _populate_entries(self, entries: List[dict]):
        self._clear_entry_rows()
        if not entries:
            self._add_entry_row()
            return
        for entry in entries:
            self._add_entry_row(entry)

    def _clear_entry_rows(self):
        for row in self.entry_rows:
            row["frame"].destroy()
        self.entry_rows.clear()

    def _add_entry_row(self, data: Optional[dict] = None):
        row = len(self.entry_rows)
        frame = ctk.CTkFrame(self.entries_frame)
        frame.grid(row=row, column=0, columnspan=5, sticky="ew", pady=4)
        frame.grid_columnconfigure(2, weight=1)

        min_var = tk.StringVar(value=str(data.get("min", "")) if data else "")
        max_var = tk.StringVar(value=str(data.get("max", "")) if data else "")
        result_var = tk.StringVar(value=data.get("result", "") if data else "")
        tags_var = tk.StringVar(value=", ".join(data.get("tags", [])) if data else "")

        ctk.CTkEntry(frame, textvariable=min_var, width=60, placeholder_text="Min").grid(row=0, column=0, padx=(4, 4))
        ctk.CTkEntry(frame, textvariable=max_var, width=60, placeholder_text="Max").grid(row=0, column=1, padx=(0, 4))
        ctk.CTkEntry(frame, textvariable=result_var, placeholder_text="Result text").grid(row=0, column=2, sticky="ew")
        ctk.CTkEntry(frame, textvariable=tags_var, width=160, placeholder_text="Entry tags").grid(row=0, column=3, padx=4)
        ctk.CTkButton(frame, text="Remove", command=lambda f=frame: self._remove_entry_row(f)).grid(row=0, column=4, padx=(4, 6))

        self.entry_rows.append({"frame": frame, "min": min_var, "max": max_var, "result": result_var, "tags": tags_var})

    def _remove_entry_row(self, frame: ctk.CTkFrame):
        for idx, row in enumerate(self.entry_rows):
            if row["frame"] is frame:
                frame.destroy()
                del self.entry_rows[idx]
                break

    def _open_import_dialog(self):
        dialog = RandomTableImportDialog(self)
        self.wait_window(dialog)
        imported_entries = getattr(dialog, "result_entries", None)
        if not imported_entries:
            return
        self._populate_entries(imported_entries)

    # ------------------------------------------------------------------
    def _resolve_category_name(self, cat_id: Optional[str]) -> str:
        if not cat_id:
            return ""
        for cat in self.categories:
            if cat.get("id") == cat_id:
                return cat.get("name") or cat_id
        return cat_id

    def _slugify(self, value: str) -> str:
        text = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())
        return text.strip("_") or "table"

    def _parse_tags(self, value: str) -> List[str]:
        return [tag.strip() for tag in (value or "").split(",") if tag.strip()]

    # ------------------------------------------------------------------
    def _collect_entries(self) -> Optional[List[dict]]:
        entries: List[dict] = []
        for row in self.entry_rows:
            try:
                min_val = int(row["min"].get())
                max_val = int(row["max"].get())
            except ValueError:
                messagebox.showwarning("Random Table", "Each entry requires numeric min and max values.")
                return None
            if min_val > max_val:
                messagebox.showwarning("Random Table", "Entry min value cannot be greater than max value.")
                return None
            result = row["result"].get().strip()
            if not result:
                messagebox.showwarning("Random Table", "Each entry needs result text.")
                return None
            entries.append(
                {
                    "min": min_val,
                    "max": max_val,
                    "result": result,
                    "tags": self._parse_tags(row["tags"].get()),
                }
            )
        if not entries:
            messagebox.showwarning("Random Table", "Add at least one entry before saving.")
            return None
        return entries

    def _validate_metadata(self) -> Optional[dict]:
        title = self.title_var.get().strip()
        dice = self.dice_var.get().strip()
        category = self.category_var.get().strip()
        if not title or not dice or not category:
            messagebox.showwarning("Random Table", "Title, dice, and category are required.")
            return None
        return {
            "title": title,
            "dice": dice,
            "category": category,
            "tags": self._parse_tags(self.tags_var.get()),
            "system": self.system_var.get().strip(),
            "biome": self.biome_var.get().strip(),
            "theme": self.theme_var.get().strip(),
            "description": self.description_box.get("1.0", "end").strip(),
        }

    def _save(self):
        metadata = self._validate_metadata()
        if metadata is None:
            return
        entries = self._collect_entries()
        if entries is None:
            return

        table_id = self.table_id or self._slugify(metadata["title"])
        theme_value = metadata.get("theme") or None
        table_data = {
            "id": table_id,
            "title": metadata["title"],
            "dice": metadata["dice"],
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags") or [],
            "entries": entries,
            "system": metadata.get("system"),
            "biome": metadata.get("biome"),
            "category": self._slugify(metadata["category"]),
        }
        if theme_value is not None:
            table_data["theme"] = theme_value

        try:
            target_path = self._persist_table(
                table_data,
                metadata["category"],
                metadata.get("system"),
                metadata.get("biome"),
                source_path=self.table_source,
                theme=theme_value,
            )
            messagebox.showinfo("Random Table", f"Table saved to {target_path}")
            RandomTablesPanel.refresh_all()
            self.destroy()
        except Exception as exc:
            log_exception(exc, func_name="RandomTableEditorDialog._save")
            messagebox.showerror("Random Table", f"Unable to save table: {exc}")

    # ------------------------------------------------------------------
    def _persist_table(
        self,
        table_data: dict,
        category_name: str,
        system: Optional[str],
        biome: Optional[str],
        *,
        source_path: Optional[str] = None,
        theme: Optional[str] = None,
    ) -> str:
        base_path = self._resolve_base_path()
        target_file = self._resolve_target_file(base_path, source_path)
        data = self._load_existing_tables(target_file)

        cat_id = self._slugify(category_name)
        category = next((c for c in data["categories"] if c.get("id") == cat_id), None)
        if category is None:
            category = {"id": cat_id, "name": category_name, "tables": []}
            data["categories"].append(category)
        category["name"] = category_name
        category.setdefault("tables", [])

        replaced = False
        for idx, existing in enumerate(category["tables"]):
            if existing.get("id") == table_data.get("id"):
                category["tables"][idx] = table_data
                replaced = True
                break
        if not replaced:
            category["tables"].append(table_data)

        if system:
            data["system"] = system
        if biome:
            data["biome"] = biome
        if theme:
            data["theme"] = theme
        elif "theme" in data:
            data.pop("theme")

        with open(target_file, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

        return target_file

    def _resolve_base_path(self) -> str:
        base_path = RandomTableLoader.default_data_path()
        campaign_dir = os.path.join(ConfigHelper.get_campaign_dir(), "static", "data", "random_tables")
        campaign_file = os.path.join(ConfigHelper.get_campaign_dir(), "static", "data", "random_tables.json")

        if os.path.isdir(campaign_dir):
            base_path = campaign_dir
        elif os.path.exists(campaign_file):
            base_path = campaign_file

        return base_path

    def _resolve_target_file(self, base_path: str, source_path: Optional[str]) -> str:
        if source_path and os.path.exists(source_path):
            os.makedirs(os.path.dirname(source_path) or ".", exist_ok=True)
            return source_path
        if os.path.isdir(base_path):
            os.makedirs(base_path, exist_ok=True)
            return os.path.join(base_path, "campaign_custom_tables.json")
        os.makedirs(os.path.dirname(base_path) or ".", exist_ok=True)
        return base_path

    def _load_existing_tables(self, target_file: str) -> dict:
        data = {"categories": []}
        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                log_exception("Failed to read existing random tables file", func_name="RandomTableEditorDialog._persist_table")

        data.setdefault("categories", [])
        return data


__all__ = ["RandomTableEditorDialog"]
