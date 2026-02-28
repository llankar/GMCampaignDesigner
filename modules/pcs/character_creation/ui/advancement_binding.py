"""Bindings between advancement combo labels and internal option values."""

from __future__ import annotations

import tkinter as tk


def bind_advancement_type_and_label_vars(
    type_var: tk.StringVar,
    label_var: tk.StringVar,
    label_to_value: dict[str, str],
    value_to_label: dict[str, str],
    on_type_updated,
) -> None:
    """Keep `type_var` and displayed `label_var` synchronized both ways."""

    guard = {"active": False}

    def _update_type_from_label(*_args):
        if guard["active"]:
            return
        selected_label = (label_var.get() or "").strip()
        selected_value = label_to_value.get(selected_label, "")
        guard["active"] = True
        try:
            type_var.set(selected_value)
        finally:
            guard["active"] = False

    def _update_label_from_type(*_args):
        if guard["active"]:
            return
        selected_type = (type_var.get() or "").strip()
        selected_label = value_to_label.get(selected_type, "")
        guard["active"] = True
        try:
            label_var.set(selected_label)
        finally:
            guard["active"] = False

    label_var.trace_add("write", _update_type_from_label)
    type_var.trace_add("write", _update_label_from_type)
    type_var.trace_add("write", on_type_updated)

    _update_label_from_type()
