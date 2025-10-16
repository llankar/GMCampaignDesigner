import random
from typing import Dict, List, Optional

import customtkinter as ctk
from tkinter import messagebox

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.objects.object_constants import OBJECT_CATEGORY_ALLOWED
from modules.helpers.template_loader import load_template
from modules.helpers.text_helpers import format_multiline_text
from modules.helpers.logging_helper import (
    log_info,
    log_exception,
    log_methods,
)


@log_methods
class LootGeneratorPanel(ctk.CTkFrame):
    """Embedded loot generator panel for the GM screen."""

    def __init__(
        self,
        master,
        object_wrapper: Optional[GenericModelWrapper] = None,
        template: Optional[dict] = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.wrapper = object_wrapper or GenericModelWrapper("Objects")
        self.template = template or load_template("objects")
        self.template_fields = (self.template or {}).get("fields", [])
        self.objects = self._load_objects()

        self.category_vars: Dict[str, ctk.BooleanVar] = {}
        self.numeric_fields: Dict[str, Dict[str, ctk.StringVar]] = {}
        self.generated_results: List[dict] = []

        self._build_ui()

    # ------------------------------------------------------------------
    def _load_objects(self) -> List[dict]:
        try:
            items = self.wrapper.load_items()
            log_info(
                f"Loaded {len(items)} objects for loot generation",
                func_name="LootGeneratorPanel._load_objects",
            )
            return items
        except Exception as exc:
            log_exception(
                "Unable to load objects for loot generation",
                exc,
                func_name="LootGeneratorPanel._load_objects",
            )
            messagebox.showerror(
                "Loot Generator",
                "Unable to read the objects database. Please try again.",
            )
            return []

    # ------------------------------------------------------------------
    def _build_ui(self):
        config_frame = ctk.CTkFrame(self)
        config_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        config_frame.columnconfigure(0, weight=1)

        count_row = ctk.CTkFrame(config_frame)
        count_row.grid(row=0, column=0, sticky="ew", pady=6)
        count_row.columnconfigure(1, weight=1)
        ctk.CTkLabel(count_row, text="Number of items:").grid(row=0, column=0, sticky="w")
        self.count_var = ctk.StringVar(value="3")
        ctk.CTkEntry(count_row, textvariable=self.count_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        keyword_row = ctk.CTkFrame(config_frame)
        keyword_row.grid(row=1, column=0, sticky="ew", pady=6)
        keyword_row.columnconfigure(1, weight=1)
        ctk.CTkLabel(keyword_row, text="Include keywords (comma separated):").grid(
            row=0, column=0, sticky="w"
        )
        self.include_var = ctk.StringVar()
        ctk.CTkEntry(keyword_row, textvariable=self.include_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        exclude_row = ctk.CTkFrame(config_frame)
        exclude_row.grid(row=2, column=0, sticky="ew", pady=6)
        exclude_row.columnconfigure(1, weight=1)
        ctk.CTkLabel(exclude_row, text="Exclude keywords (comma separated):").grid(
            row=0, column=0, sticky="w"
        )
        self.exclude_var = ctk.StringVar()
        ctk.CTkEntry(exclude_row, textvariable=self.exclude_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        categories_frame = ctk.CTkFrame(config_frame)
        categories_frame.grid(row=3, column=0, sticky="nsew", pady=(6, 0))
        categories_frame.columnconfigure(0, weight=1)
        ctk.CTkLabel(categories_frame, text="Categories").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )

        cat_scroll = ctk.CTkScrollableFrame(categories_frame, height=150)
        cat_scroll.grid(row=1, column=0, sticky="nsew")

        categories = self._collect_categories()
        for idx, category in enumerate(categories):
            var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(cat_scroll, text=category or "(Uncategorized)", variable=var)
            chk.grid(row=idx // 2, column=idx % 2, sticky="w", padx=4, pady=2)
            self.category_vars[category] = var

        button_row = ctk.CTkFrame(config_frame)
        button_row.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ctk.CTkButton(button_row, text="Select All", command=self._select_all_categories).pack(
            side="left"
        )
        ctk.CTkButton(button_row, text="Clear", command=self._clear_categories).pack(
            side="left", padx=(6, 0)
        )

        numeric_container = ctk.CTkFrame(config_frame)
        numeric_container.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        numeric_container.columnconfigure(0, weight=1)
        numeric_fields = self._discover_numeric_fields()
        if numeric_fields:
            ctk.CTkLabel(numeric_container, text="Numeric field filters").grid(
                row=0, column=0, sticky="w", pady=(0, 6)
            )
            for idx, field_name in enumerate(numeric_fields, start=1):
                row = ctk.CTkFrame(numeric_container)
                row.grid(row=idx, column=0, sticky="ew", pady=4)
                row.columnconfigure(1, weight=1)
                row.columnconfigure(3, weight=1)
                ctk.CTkLabel(row, text=field_name).grid(row=0, column=0, sticky="w")
                min_var = ctk.StringVar()
                max_var = ctk.StringVar()
                ctk.CTkEntry(row, textvariable=min_var, placeholder_text="Min").grid(
                    row=0, column=1, sticky="ew", padx=(6, 3)
                )
                ctk.CTkLabel(row, text="to").grid(row=0, column=2, padx=3)
                ctk.CTkEntry(row, textvariable=max_var, placeholder_text="Max").grid(
                    row=0, column=3, sticky="ew", padx=(3, 0)
                )
                self.numeric_fields[field_name] = {"min": min_var, "max": max_var}
        else:
            ctk.CTkLabel(
                numeric_container,
                text="No numeric custom fields detected. Add them via custom fields to unlock extra filters.",
                wraplength=760,
                justify="left",
            ).grid(row=0, column=0, sticky="w")

        action_row = ctk.CTkFrame(config_frame)
        action_row.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        ctk.CTkButton(action_row, text="Generate", command=self._generate_loot).pack(
            side="left"
        )
        ctk.CTkButton(action_row, text="Copy to Clipboard", command=self._copy_to_clipboard).pack(
            side="left", padx=(8, 0)
        )

        self.status_var = ctk.StringVar()
        ctk.CTkLabel(config_frame, textvariable=self.status_var).grid(
            row=7, column=0, sticky="w", pady=(8, 0)
        )

        self.results_frame = ctk.CTkScrollableFrame(self)
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.results_frame.columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    def _collect_categories(self) -> List[str]:
        discovered = {cat for cat in OBJECT_CATEGORY_ALLOWED}
        for obj in self.objects:
            cat = (obj.get("Category") or "").strip()
            if cat:
                discovered.add(cat)
        return sorted(discovered, key=lambda c: (c == "", c.lower()))

    # ------------------------------------------------------------------
    def _discover_numeric_fields(self) -> List[str]:
        numeric_types = {"int", "float", "number"}
        fields = []
        for field in self.template_fields:
            try:
                name = str(field.get("name"))
            except Exception:
                continue
            if not name:
                continue
            ftype = str(field.get("type", "")).lower()
            if ftype in numeric_types:
                fields.append(name)
        return fields

    # ------------------------------------------------------------------
    def _select_all_categories(self):
        for var in self.category_vars.values():
            var.set(True)

    # ------------------------------------------------------------------
    def _clear_categories(self):
        for var in self.category_vars.values():
            var.set(False)

    # ------------------------------------------------------------------
    def _parse_count(self) -> int:
        raw = (self.count_var.get() or "").strip()
        try:
            value = int(raw)
            return max(1, value)
        except ValueError:
            messagebox.showwarning(
                "Loot Generator",
                "Invalid count. Using 1 item.",
            )
            return 1

    # ------------------------------------------------------------------
    def _keyword_list(self, var: ctk.StringVar) -> List[str]:
        raw = (var.get() or "").strip()
        if not raw:
            return []
        return [segment.strip().lower() for segment in raw.split(",") if segment.strip()]

    # ------------------------------------------------------------------
    def _numeric_filter_values(self) -> Dict[str, Dict[str, float]]:
        filters: Dict[str, Dict[str, float]] = {}
        for field_name, pair in self.numeric_fields.items():
            min_raw = (pair["min"].get() or "").strip()
            max_raw = (pair["max"].get() or "").strip()
            min_val = self._parse_float(min_raw) if min_raw else None
            max_val = self._parse_float(max_raw) if max_raw else None
            if min_val is None and min_raw:
                messagebox.showwarning(
                    "Loot Generator",
                    f"Ignoring invalid minimum value for {field_name}.",
                )
            if max_val is None and max_raw:
                messagebox.showwarning(
                    "Loot Generator",
                    f"Ignoring invalid maximum value for {field_name}.",
                )
            if min_val is not None or max_val is not None:
                filters[field_name] = {"min": min_val, "max": max_val}
        return filters

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_float(raw: str) -> Optional[float]:
        try:
            return float(raw)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_numeric(value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                return float(raw)
            except ValueError:
                return None
        return None

    # ------------------------------------------------------------------
    @staticmethod
    def _text_from_rtf(value) -> str:
        """Extract plain text from a rich text field."""
        if isinstance(value, dict):
            return value.get("text", "")
        if value is None:
            return ""
        return str(value)

    # ------------------------------------------------------------------
    def _filter_objects(self) -> List[dict]:
        selected_categories = [cat for cat, var in self.category_vars.items() if var.get()]
        include_keywords = self._keyword_list(self.include_var)
        exclude_keywords = self._keyword_list(self.exclude_var)
        numeric_filters = self._numeric_filter_values()

        filtered = []
        for obj in self.objects:
            category = (obj.get("Category") or "").strip()
            if selected_categories and category not in selected_categories:
                continue

            blob = " ".join(
                str(obj.get(field, ""))
                for field in [
                    "Name",
                    "Description",
                    "Stats",
                    "Secrets",
                ]
            ).lower()
            if include_keywords and not all(keyword in blob for keyword in include_keywords):
                continue
            if exclude_keywords and any(keyword in blob for keyword in exclude_keywords):
                continue

            numeric_ok = True
            for field_name, bounds in numeric_filters.items():
                value = self._coerce_numeric(obj.get(field_name))
                if value is None:
                    numeric_ok = False
                    break
                if bounds["min"] is not None and value < bounds["min"]:
                    numeric_ok = False
                    break
                if bounds["max"] is not None and value > bounds["max"]:
                    numeric_ok = False
                    break
            if not numeric_ok:
                continue

            filtered.append(obj)

        return filtered

    # ------------------------------------------------------------------
    def _generate_loot(self):
        if not self.objects:
            self.status_var.set("No objects available to generate loot.")
            return

        filtered = self._filter_objects()
        if not filtered:
            self.generated_results = []
            self._render_results()
            self.status_var.set("No items matched your filters.")
            return

        count = self._parse_count()
        if count <= len(filtered):
            results = random.sample(filtered, count)
        else:
            results = []
            while len(results) < count:
                results.append(random.choice(filtered))
        self.generated_results = results
        self._render_results()
        self.status_var.set(f"Generated {len(results)} item(s) from {len(filtered)} matches.")

    # ------------------------------------------------------------------
    def _render_results(self):
        for child in self.results_frame.winfo_children():
            child.destroy()

        if not self.generated_results:
            ctk.CTkLabel(
                self.results_frame,
                text="Adjust filters and click Generate to build a loot list.",
            ).grid(row=0, column=0, sticky="w", padx=6, pady=6)
            return

        for idx, item in enumerate(self.generated_results):
            card = ctk.CTkFrame(self.results_frame)
            card.grid(row=idx, column=0, sticky="ew", padx=6, pady=6)
            card.columnconfigure(0, weight=1)
            name = item.get("Name") or item.get("Title") or "Unnamed Object"
            category = item.get("Category") or ""
            header = name if not category else f"{name} ({category})"
            ctk.CTkLabel(
                card,
                text=header,
                font=("TkDefaultFont", 14, "bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
            description = format_multiline_text(self._text_from_rtf(item.get("Description"))).strip()
            stats = format_multiline_text(self._text_from_rtf(item.get("Stats"))).strip()
            if description:
                ctk.CTkLabel(
                    card,
                    text=description,
                    wraplength=720,
                    justify="left",
                    anchor="w",
                ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 4))
            if stats:
                ctk.CTkLabel(
                    card,
                    text=stats,
                    wraplength=720,
                    justify="left",
                    anchor="w",
                    text_color="#AAAAAA",
                ).grid(row=2, column=0, sticky="w", padx=8, pady=(0, 8))

    # ------------------------------------------------------------------
    def _copy_to_clipboard(self):
        if not self.generated_results:
            messagebox.showinfo(
                "Loot Generator",
                "Generate loot before copying to the clipboard.",
            )
            return
        lines = []
        for item in self.generated_results:
            name = item.get("Name") or item.get("Title") or "Unnamed Object"
            category = item.get("Category")
            header = name if not category else f"{name} ({category})"
            lines.append(header)
            description = self._text_from_rtf(item.get("Description")).strip()
            stats = self._text_from_rtf(item.get("Stats")).strip()
            if description:
                lines.append(description)
            if stats:
                lines.append(stats)
            lines.append("")
        text = "\n".join(lines).strip()
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_var.set("Copied loot summary to clipboard.")
        except Exception as exc:
            log_exception(
                "Failed to copy loot to clipboard",
                exc,
                func_name="LootGeneratorPanel._copy_to_clipboard",
            )
            messagebox.showwarning(
                "Loot Generator",
                "Unable to copy loot to the clipboard on this platform.",
            )
