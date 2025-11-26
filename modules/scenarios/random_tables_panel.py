import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from modules.dice import dice_engine
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import (
    log_exception,
    log_info,
    log_methods,
    log_module_import,
)

log_module_import(__name__)


@log_methods
class RandomTablesPanel(ctk.CTkFrame):
    """Panel to browse and roll structured random tables."""

    def __init__(self, master=None, data_path: Optional[str] = None, initial_state: Optional[Dict] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=3)
        self.rowconfigure(3, weight=2)

        self.data_path = data_path or self._default_data_path()
        self.tables: Dict[str, dict] = {}
        self.categories: List[dict] = []
        self._table_index: List[str] = []
        self.selected_table_id: Optional[str] = None
        self.history: List[str] = []

        self._load_tables()
        self._build_ui()
        self.apply_state(initial_state or {})

    # ------------------------------------------------------------------
    def _default_data_path(self) -> str:
        local_path = os.path.join(os.path.dirname(__file__), "..", "..", "static", "data", "random_tables.json")
        campaign_path = os.path.join(ConfigHelper.get_campaign_dir(), "static", "data", "random_tables.json")
        return local_path if os.path.exists(local_path) else campaign_path

    def _load_tables(self) -> None:
        if not os.path.exists(self.data_path):
            log_info(
                f"Random tables file missing at {self.data_path}",
                func_name="RandomTablesPanel._load_tables",
            )
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as handle:
                data = json.load(handle) or {}
        except Exception as exc:  # pragma: no cover - file errors shown to GM
            log_exception(exc, func_name="RandomTablesPanel._load_tables")
            messagebox.showerror("Random Tables", "Unable to read random_tables.json.")
            return

        categories = data.get("categories") or []
        self.categories = []
        self.tables = {}
        for category in categories:
            cat_id = str(category.get("id") or "").strip() or category.get("name") or "category"
            entry = {
                "id": cat_id,
                "name": category.get("name") or cat_id.title(),
                "tables": [],
            }
            for table in category.get("tables") or []:
                t_id = str(table.get("id") or table.get("title") or f"table_{len(self.tables)+1}").strip()
                normalized = {
                    "id": t_id,
                    "title": table.get("title") or t_id.title(),
                    "dice": table.get("dice") or "1d20",
                    "entries": self._normalize_entries(table.get("entries") or []),
                    "description": table.get("description", ""),
                    "tags": [str(tag) for tag in (table.get("tags") or [])],
                    "category": entry["id"],
                }
                self.tables[t_id] = normalized
                entry["tables"].append(normalized)
            self.categories.append(entry)
        self._table_index = list(self.tables.keys())

    def _normalize_entries(self, entries: List[dict]) -> List[dict]:
        normalized: List[dict] = []
        for idx, raw in enumerate(entries, start=1):
            result = str(raw.get("result") or raw.get("text") or f"Entry {idx}")
            rng = raw.get("range")
            if rng is None and "min" in raw and "max" in raw:
                rng = f"{raw.get('min')}-{raw.get('max')}"
            min_val, max_val = self._parse_range(str(rng) if rng is not None else str(idx))
            normalized.append(
                {
                    "min": min_val,
                    "max": max_val,
                    "result": result,
                    "tags": [str(tag) for tag in (raw.get("tags") or [])],
                }
            )
        return normalized

    def _parse_range(self, range_text: str) -> tuple[int, int]:
        text = (range_text or "").strip()
        if "-" in text:
            start, end = text.split("-", 1)
            try:
                return int(start), int(end)
            except ValueError:
                return 1, 1
        try:
            value = int(text)
            return value, value
        except ValueError:
            return 1, 1

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        filter_bar = ctk.CTkFrame(self)
        filter_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        filter_bar.columnconfigure(2, weight=1)

        ctk.CTkLabel(filter_bar, text="Category:").grid(row=0, column=0, padx=(4, 6), sticky="w")
        categories = ["All"] + [cat.get("name") for cat in self.categories]
        self.category_var = ctk.StringVar(value=categories[0] if categories else "All")
        ctk.CTkOptionMenu(filter_bar, variable=self.category_var, values=categories, command=self._on_category_change).grid(
            row=0, column=1, sticky="w", padx=(0, 10)
        )

        ctk.CTkLabel(filter_bar, text="Tag filter:").grid(row=0, column=2, sticky="w")
        self.tag_var = ctk.StringVar()
        tag_entry = ctk.CTkEntry(filter_bar, textvariable=self.tag_var, placeholder_text="optional tag")
        tag_entry.grid(row=0, column=3, sticky="ew", padx=(6, 4))
        tag_entry.bind("<KeyRelease>", lambda _e: self._refresh_table_list())

        list_container = ctk.CTkFrame(self)
        list_container.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 6))
        list_container.columnconfigure(0, weight=1)
        list_container.columnconfigure(1, weight=2)
        list_container.rowconfigure(1, weight=1)

        self.table_list = tk.Listbox(list_container, activestyle="none", exportselection=False, height=10)
        self.table_list.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8), pady=4)
        self.table_list.bind("<<ListboxSelect>>", lambda _e: self._on_table_select())

        meta_frame = ctk.CTkFrame(list_container)
        meta_frame.grid(row=0, column=1, sticky="ew", pady=(4, 2))
        meta_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(meta_frame, text="Dice:").grid(row=0, column=0, sticky="w")
        self.dice_var = ctk.StringVar(value="-")
        ctk.CTkLabel(meta_frame, textvariable=self.dice_var).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(meta_frame, text="Tags:").grid(row=1, column=0, sticky="w")
        self.tags_var = ctk.StringVar(value="-")
        ctk.CTkLabel(meta_frame, textvariable=self.tags_var, wraplength=400, justify="left").grid(row=1, column=1, sticky="w")

        ctk.CTkLabel(meta_frame, text="Description:").grid(row=2, column=0, sticky="nw")
        self.description_box = ctk.CTkTextbox(meta_frame, height=60, wrap="word")
        self.description_box.grid(row=2, column=1, sticky="ew", pady=(4, 0))
        self.description_box.configure(state="disabled")

        entries_frame = ctk.CTkFrame(list_container)
        entries_frame.grid(row=1, column=1, sticky="nsew")
        entries_frame.rowconfigure(0, weight=1)
        entries_frame.columnconfigure(0, weight=1)
        ctk.CTkLabel(entries_frame, text="Entries").grid(row=0, column=0, sticky="w", padx=2)
        self.entries_box = ctk.CTkTextbox(entries_frame, wrap="word")
        self.entries_box.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.entries_box.configure(state="disabled")

        actions = ctk.CTkFrame(self)
        actions.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 6))
        actions.columnconfigure(3, weight=1)

        ctk.CTkButton(actions, text="Roll", command=self.roll_once).grid(row=0, column=0, padx=(0, 6), pady=4)
        ctk.CTkLabel(actions, text="Times:").grid(row=0, column=1, sticky="w")
        self.count_var = ctk.StringVar(value="3")
        ctk.CTkEntry(actions, textvariable=self.count_var, width=60).grid(row=0, column=2, padx=(4, 8))
        ctk.CTkButton(actions, text="Roll Multiple", command=self.roll_multiple).grid(row=0, column=3, sticky="w")

        history_frame = ctk.CTkFrame(self)
        history_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))
        history_frame.rowconfigure(1, weight=1)
        history_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(history_frame, text="History").grid(row=0, column=0, sticky="w")
        self.history_box = ctk.CTkTextbox(history_frame, wrap="word", height=140)
        self.history_box.grid(row=1, column=0, sticky="nsew")
        self.history_box.configure(state="disabled")

        self._refresh_table_list()

    # ------------------------------------------------------------------
    def _filter_tables(self) -> List[dict]:
        tag_filter = (self.tag_var.get() or "").strip().lower()
        category_label = (self.category_var.get() or "All").strip()
        selected_category = None
        for cat in self.categories:
            if cat.get("name") == category_label:
                selected_category = cat["id"]
                break

        matched: List[dict] = []
        for table in self.tables.values():
            if selected_category and table.get("category") != selected_category:
                continue
            if tag_filter:
                tags = [t.lower() for t in table.get("tags") or []]
                if tag_filter not in tags:
                    continue
            matched.append(table)
        return sorted(matched, key=lambda t: t.get("title", ""))

    def _refresh_table_list(self) -> None:
        tables = self._filter_tables()
        self.table_list.delete(0, "end")
        self._table_index = []
        for table in tables:
            self.table_list.insert("end", table.get("title") or table.get("id"))
            self._table_index.append(table["id"])
        if self._table_index:
            target = self.selected_table_id if self.selected_table_id in self._table_index else self._table_index[0]
            idx = self._table_index.index(target)
            self.table_list.selection_clear(0, "end")
            self.table_list.selection_set(idx)
            self.table_list.see(idx)
            self._on_table_select()
        else:
            self.selected_table_id = None
            self._update_metadata(None)

    def _on_category_change(self, *_args):
        self._refresh_table_list()

    def _on_table_select(self):
        selection = self.table_list.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx >= len(self._table_index):
            return
        table_id = self._table_index[idx]
        self.selected_table_id = table_id
        table = self.tables.get(table_id)
        self._update_metadata(table)

    def _update_metadata(self, table: Optional[dict]) -> None:
        if not table:
            self.dice_var.set("-")
            self.tags_var.set("-")
            self.description_box.configure(state="normal")
            self.description_box.delete("1.0", "end")
            self.description_box.configure(state="disabled")
            self.entries_box.configure(state="normal")
            self.entries_box.delete("1.0", "end")
            self.entries_box.configure(state="disabled")
            return

        self.dice_var.set(table.get("dice", "-"))
        tags = table.get("tags") or []
        self.tags_var.set(", ".join(tags) if tags else "-")

        self.description_box.configure(state="normal")
        self.description_box.delete("1.0", "end")
        desc = table.get("description") or ""
        if desc:
            self.description_box.insert("end", desc)
        self.description_box.configure(state="disabled")

        self.entries_box.configure(state="normal")
        self.entries_box.delete("1.0", "end")
        for entry in table.get("entries", []):
            rng = entry.get("min")
            max_val = entry.get("max")
            label = f"{rng}-{max_val}" if rng != max_val else str(rng)
            tags_text = f" (tags: {', '.join(entry.get('tags', []))})" if entry.get("tags") else ""
            self.entries_box.insert("end", f"{label}: {entry.get('result')}{tags_text}\n")
        self.entries_box.configure(state="disabled")

    # ------------------------------------------------------------------
    def roll_once(self):
        self._roll_table(times=1)

    def roll_multiple(self):
        try:
            count = int(self.count_var.get())
        except ValueError:
            messagebox.showwarning("Random Tables", "Please provide a valid number of rolls.")
            return
        self._roll_table(times=max(1, count))

    def _roll_table(self, *, times: int):
        table = self.tables.get(self.selected_table_id or "") if self.selected_table_id else None
        if not table:
            messagebox.showinfo("Random Tables", "Select a table to roll first.")
            return

        try:
            parsed_results = [dice_engine.roll_formula(table.get("dice", "1d20")) for _ in range(times)]
        except Exception as exc:
            log_exception(exc, func_name="RandomTablesPanel._roll_table")
            messagebox.showerror("Random Tables", f"Unable to roll dice: {exc}")
            return

        for roll in parsed_results:
            entry = self._match_entry(table, roll.total)
            timestamp = datetime.now().strftime("%H:%M:%S")
            text = f"[{timestamp}] {table.get('title')}: {roll.total} -> {entry.get('result')}"
            self.history.append(text)
            self._append_history(text)

    def _match_entry(self, table: dict, value: int) -> dict:
        for entry in table.get("entries", []):
            if entry.get("min", 0) <= value <= entry.get("max", 0):
                return entry
        return table.get("entries", [{}])[0] if table.get("entries") else {"result": "(no entries)"}

    def _append_history(self, line: str) -> None:
        self.history_box.configure(state="normal")
        self.history_box.insert("end", line + "\n")
        self.history_box.see("end")
        self.history_box.configure(state="disabled")

    # ------------------------------------------------------------------
    def get_state(self) -> Dict:
        return {
            "selected_table": self.selected_table_id,
            "category": self.category_var.get() if hasattr(self, "category_var") else None,
            "tag": self.tag_var.get() if hasattr(self, "tag_var") else None,
            "history": list(self.history),
        }

    def apply_state(self, state: Dict) -> None:
        if not state:
            self._refresh_table_list()
            return
        category = state.get("category")
        if category and hasattr(self, "category_var"):
            self.category_var.set(category)
        tag = state.get("tag")
        if tag and hasattr(self, "tag_var"):
            self.tag_var.set(tag)
        self.selected_table_id = state.get("selected_table")
        self._refresh_table_list()
        for line in state.get("history") or []:
            self._append_history(line)

    def roll_random_table(self) -> Optional[dict]:
        if not self.tables:
            return None
        table = self.tables.get(self.selected_table_id) if self.selected_table_id else None
        if table is None:
            table = next(iter(self.tables.values()))
            self.selected_table_id = table.get("id")
            self._refresh_table_list()
        try:
            roll = dice_engine.roll_formula(table.get("dice", "1d20"))
        except Exception:
            return None
        entry = self._match_entry(table, roll.total)
        result = {
            "table": table.get("title"),
            "roll": roll.total,
            "result": entry.get("result"),
        }
        self._append_history(f"(Quick Roll) {result['table']}: {result['roll']} -> {result['result']}")
        return result
