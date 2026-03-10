"""Composable equipment editor for character creation."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

OBJECT_TITLES = {"weapon": "Objet 1", "armor": "Objet 2", "utility": "Objet 3"}
OBJECT_ORDER = ("weapon", "armor", "utility")
MAX_OBJECTS_PER_ROW = 3
FIELD_LABELS = {
    "damage": "Dommages",
    "pierce_armor": "Perce-armure",
    "armor": "Armure",
    "special_effect": "Effet spécial",
    "skill_bonus": "Bonus compétence",
}
ALLOWED_FIELDS = {
    "weapon": ("damage", "pierce_armor", "special_effect", "skill_bonus"),
    "armor": ("armor", "special_effect", "skill_bonus"),
    "utility": ("special_effect", "skill_bonus"),
}
GENERIC_ALLOWED_FIELDS = ("damage", "pierce_armor", "armor", "special_effect", "skill_bonus")


class _FallbackWidget:
    def __init__(self, master=None, *args, **kwargs):
        self.master = master
        self._grid_visible = True
        self._grid_kwargs = {}

    def grid(self, *args, **kwargs):
        self._grid_visible = True
        self._grid_kwargs = dict(kwargs)
        return None

    def grid_remove(self):
        self._grid_visible = False
        return None

    def grid_configure(self, *args, **kwargs):
        self._grid_kwargs.update(kwargs)
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def destroy(self):
        return None


class _FallbackComboBox(_FallbackWidget):
    def __init__(self, master=None, *args, values=None, command=None, **kwargs):
        super().__init__(master, *args, **kwargs)
        self._values = list(values or [])
        self._value = ""
        self._command = command

    def set(self, value):
        self._value = value

    def get(self):
        return self._value

    def configure(self, **kwargs):
        if "values" in kwargs:
            self._values = list(kwargs["values"])
        if "command" in kwargs:
            self._command = kwargs["command"]

    def cget(self, key):
        if key == "values":
            return self._values
        raise KeyError(key)


class _FallbackButton(_FallbackWidget):
    def __init__(self, master=None, *args, command=None, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.command = command


class EquipmentEditor:
    def __init__(self, parent, on_change, max_level_provider, grid_row: int = 11):
        self._on_change = on_change
        self._max_level_provider = max_level_provider
        self._columns: dict[str, dict] = {}
        self._active_object_keys: list[str] = [OBJECT_ORDER[0]]
        self._next_object_number = len(OBJECT_ORDER) + 1
        self._headless = not hasattr(parent, "tk")

        self.frame = self._make_frame(parent)
        self.frame.grid(row=grid_row, column=0, columnspan=2, sticky="ew", padx=6, pady=(4, 4))
        self.frame.grid_columnconfigure((0, 1, 2), weight=1)

        controls = self._make_frame(self.frame)
        controls.grid(row=0, column=0, columnspan=3, sticky="ew", padx=4, pady=(4, 0))
        controls.grid_columnconfigure(0, weight=1)

        self._make_label(controls, text="Gestion des objets", font=("Arial", 12, "bold")).grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self._make_button(controls, text="+ Ajouter un objet", width=140, command=self.add_object_slot).grid(
            row=0, column=1, sticky="e", padx=6, pady=4
        )

        for object_key in OBJECT_ORDER:
            self._columns[object_key] = self._build_column(object_key)
            self.add_effect_row(object_key)

        self._render_object_grid()

    def _build_column(self, object_key: str) -> dict:
        box = self._make_frame(self.frame)
        box.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        box.grid_columnconfigure(0, weight=1)

        header = self._make_frame(box)
        header.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
        header.grid_columnconfigure(0, weight=1)
        self._make_label(header, text=OBJECT_TITLES[object_key], font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w")
        self._make_button(
            header,
            text="Retirer",
            width=90,
            command=lambda key=object_key: self.remove_object_slot(key),
        ).grid(row=0, column=1, sticky="e")

        name_var = tk.StringVar(value="")
        self._make_label(box, text="Nom").grid(row=1, column=0, sticky="w", padx=6)
        self._make_entry(box, textvariable=name_var).grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 4))

        rows_frame = self._make_frame(box)
        rows_frame.grid(row=3, column=0, sticky="ew", padx=6, pady=(2, 4))
        rows_frame.grid_columnconfigure(0, weight=1)

        self._make_button(
            box,
            text="+ Ajouter un effet",
            width=130,
            command=lambda key=object_key: self.add_effect_row(key),
        ).grid(row=4, column=0, sticky="w", padx=6, pady=(2, 6))

        summary_var = tk.StringVar(value="Résumé : aucun effet")
        self._make_label(box, textvariable=summary_var, justify="left", wraplength=280).grid(row=5, column=0, sticky="w", padx=6, pady=(0, 6))

        name_var.trace_add("write", self._on_internal_change)
        return {
            "box": box,
            "name_var": name_var,
            "rows_frame": rows_frame,
            "rows": [],
            "summary_var": summary_var,
        }

    def add_object_slot(self) -> None:
        hidden = [key for key in self._columns if key not in self._active_object_keys]
        if hidden:
            next_key = hidden[0]
        else:
            next_key = self._create_object_slot()
        self._active_object_keys.append(next_key)
        self._columns[next_key]["box"].grid()
        if not self._columns[next_key]["rows"]:
            self.add_effect_row(next_key)
        self._render_object_grid()
        self._on_internal_change()

    def remove_object_slot(self, object_key: str) -> None:
        if object_key not in self._active_object_keys:
            return
        if len(self._active_object_keys) <= 1:
            return

        column = self._columns[object_key]
        column["name_var"].set("")
        for row in list(column["rows"]):
            row["frame"].destroy()
        column["rows"] = []
        self._active_object_keys = [key for key in self._active_object_keys if key != object_key]
        self._render_object_grid()
        self._on_internal_change()

    def _render_object_grid(self) -> None:
        for index, object_key in enumerate(self._active_object_keys):
            row = 1 + (index // MAX_OBJECTS_PER_ROW)
            col = index % MAX_OBJECTS_PER_ROW
            self._columns[object_key]["box"].grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

        for object_key, column in self._columns.items():
            if object_key not in self._active_object_keys:
                column["box"].grid_remove()

    def add_effect_row(self, object_key: str) -> None:
        column = self._columns[object_key]
        row_index = len(column["rows"])
        row_box = self._make_frame(column["rows_frame"])
        row_box.grid(row=row_index, column=0, sticky="ew", pady=3)
        row_box.grid_columnconfigure(0, weight=1)

        field_choices = list(self._allowed_fields_for(object_key))
        effect_var = tk.StringVar(value=field_choices[0])
        level_var = tk.StringVar(value="0")

        effect_combo = self._make_combobox(
            row_box,
            values=[FIELD_LABELS[field] for field in field_choices],
            state="readonly",
            command=lambda label, key=object_key, var=effect_var: self._set_field_from_label(key, var, label),
        )
        effect_combo.set(FIELD_LABELS[field_choices[0]])
        effect_combo.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))

        self._make_label(row_box, text="Niveau").grid(row=1, column=0, sticky="w", padx=4)
        level_combo = self._make_combobox(row_box, values=self._level_values_for(effect_var.get()), state="readonly")
        level_combo.set("0")
        level_combo.configure(command=lambda value, var=level_var: var.set(value))
        level_combo.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))

        self._make_button(
            row_box,
            text="Retirer cet effet",
            width=120,
            command=lambda key=object_key, target=row_box: self.remove_effect_row(key, target),
        ).grid(row=3, column=0, sticky="w", padx=4, pady=(0, 4))

        effect_var.trace_add("write", self._on_internal_change)
        level_var.trace_add("write", self._on_internal_change)

        column["rows"].append(
            {
                "frame": row_box,
                "effect_var": effect_var,
                "level_var": level_var,
                "effect_combo": effect_combo,
                "level_combo": level_combo,
            }
        )
        self._on_internal_change()

    def _make_frame(self, master):
        if self._headless:
            return _FallbackWidget(master)
        return ctk.CTkFrame(master)

    def _make_label(self, master, **kwargs):
        if self._headless:
            return _FallbackWidget(master, **kwargs)
        return ctk.CTkLabel(master, **kwargs)

    def _make_entry(self, master, **kwargs):
        if self._headless:
            return _FallbackWidget(master, **kwargs)
        return ctk.CTkEntry(master, **kwargs)

    def _make_button(self, master, **kwargs):
        if self._headless:
            return _FallbackButton(master, **kwargs)
        return ctk.CTkButton(master, **kwargs)

    def _make_combobox(self, master, **kwargs):
        if self._headless:
            return _FallbackComboBox(master, **kwargs)
        return ctk.CTkComboBox(master, **kwargs)

    def remove_effect_row(self, object_key: str, row_frame) -> None:
        column = self._columns[object_key]
        updated_rows = []
        for row in column["rows"]:
            if row["frame"] is row_frame:
                row["frame"].destroy()
                continue
            updated_rows.append(row)
        column["rows"] = updated_rows

        for idx, row in enumerate(column["rows"]):
            row["frame"].grid_configure(row=idx)

        self._on_internal_change()

    def _set_field_from_label(self, object_key: str, var: tk.StringVar, label: str) -> None:
        allowed_fields = self._allowed_fields_for(object_key)
        mapping = {FIELD_LABELS[field]: field for field in allowed_fields}
        var.set(mapping.get(label, allowed_fields[0]))

    def _allowed_fields_for(self, object_key: str) -> tuple[str, ...]:
        return ALLOWED_FIELDS.get(object_key, GENERIC_ALLOWED_FIELDS)

    def _object_title_for(self, object_key: str) -> str:
        return OBJECT_TITLES.get(object_key, f"Objet {self._next_object_number - 1}")

    def _create_object_slot(self) -> str:
        object_key = f"object_{self._next_object_number}"
        OBJECT_TITLES[object_key] = f"Objet {self._next_object_number}"
        self._next_object_number += 1
        self._columns[object_key] = self._build_column(object_key)
        self.add_effect_row(object_key)
        return object_key

    def _ensure_object_slot_exists(self, object_key: str) -> None:
        if object_key in self._columns:
            return

        if object_key.startswith("object_"):
            _, _, suffix = object_key.partition("_")
            try:
                target_number = int(suffix)
            except ValueError:
                target_number = self._next_object_number

            while self._next_object_number <= target_number:
                self._create_object_slot()
            return

        OBJECT_TITLES[object_key] = f"Objet {self._next_object_number}"
        self._next_object_number += 1
        self._columns[object_key] = self._build_column(object_key)
        self.add_effect_row(object_key)

    def _level_values_for(self, field: str) -> list[str]:
        max_level = max(self._max_level_provider(), 0)
        if field == "skill_bonus":
            values = [str(v) for v in range(0, max_level + 1, 2)]
            return values or ["0"]
        return [str(v) for v in range(0, max_level + 1)]

    def _on_internal_change(self, *_args) -> None:
        for object_key, column in self._columns.items():
            for row in column["rows"]:
                allowed = self._level_values_for(row["effect_var"].get())
                row["level_combo"].configure(values=allowed)
                if row["level_var"].get() not in allowed:
                    row["level_var"].set("0")
                    row["level_combo"].set("0")
            self._update_summary(object_key)
        self._on_change()

    def _update_summary(self, object_key: str) -> None:
        payload = self.get_purchase_payload()[object_key]
        name = self._columns[object_key]["name_var"].get().strip() or self._object_title_for(object_key)
        effects = []
        for field in self._allowed_fields_for(object_key):
            value = int(payload.get(field, 0) or 0)
            if value > 0:
                effects.append(f"{FIELD_LABELS[field]} {value}")
        self._columns[object_key]["summary_var"].set(
            f"Résumé : {name} | Bonus: {payload.get('skill_bonus', 0)} | Effets: {', '.join(effects) if effects else 'aucun'}"
        )

    def get_equipment_names(self) -> dict[str, str]:
        return {key: col["name_var"].get().strip() for key, col in self._columns.items()}

    def get_purchase_payload(self) -> dict[str, dict[str, int | str]]:
        payload: dict[str, dict[str, int | str]] = {}
        for object_key, column in self._columns.items():
            if object_key not in self._active_object_keys:
                payload[object_key] = {field: 0 for field in self._allowed_fields_for(object_key)}
                payload[object_key]["special_effect_details"] = ""
                payload[object_key]["skill_bonus_skill"] = ""
                continue
            values: dict[str, int | str] = {field: 0 for field in self._allowed_fields_for(object_key)}
            for row in column["rows"]:
                field = row["effect_var"].get()
                if field not in values:
                    continue
                try:
                    values[field] += int((row["level_var"].get() or "0").strip())
                except ValueError:
                    continue
            values["special_effect_details"] = ""
            values["skill_bonus_skill"] = ""
            payload[object_key] = values
        return payload

    def get_allocated_pe(self) -> dict[str, int]:
        payload = self.get_purchase_payload()
        return {
            key: sum(int(payload[key].get(field, 0) or 0) for field in self._allowed_fields_for(key))
            for key in payload
        }

    def apply_payload(self, equipment: dict, purchases: dict) -> None:
        for object_key in set(equipment.keys()) | set(purchases.keys()):
            self._ensure_object_slot_exists(object_key)

        active_keys = []
        for object_key, column in self._columns.items():
            column["name_var"].set((equipment.get(object_key) or "").strip())
            for row in list(column["rows"]):
                row["frame"].destroy()
            column["rows"] = []

            object_payload = purchases.get(object_key) or {}
            fields = [field for field in self._allowed_fields_for(object_key) if int(object_payload.get(field, 0) or 0) > 0]
            object_name = (equipment.get(object_key) or "").strip()
            if object_name or fields:
                active_keys.append(object_key)

            if not fields:
                fields = [self._allowed_fields_for(object_key)[0]]

            for field in fields:
                self.add_effect_row(object_key)
                row = column["rows"][-1]
                row["effect_var"].set(field)
                row["effect_combo"].set(FIELD_LABELS[field])
                value = str(object_payload.get(field, 0) or 0)
                if value not in row["level_combo"].cget("values"):
                    value = "0"
                row["level_var"].set(value)
                row["level_combo"].set(value)

        if not active_keys:
            active_keys = [OBJECT_ORDER[0]]
        self._active_object_keys = active_keys
        for object_key, column in self._columns.items():
            if object_key not in self._active_object_keys:
                column["name_var"].set("")
                for row in list(column["rows"]):
                    row["frame"].destroy()
                column["rows"] = []

        self._render_object_grid()

        self._on_internal_change()
