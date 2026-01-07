"""Reusable checkbox modal dialog."""

from __future__ import annotations

import customtkinter as ctk


class CheckboxDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        title: str,
        message: str,
        checkbox_label: str,
        *,
        default: bool = True,
        confirm_label: str = "OK",
        cancel_label: str = "Cancel",
    ):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.result = None

        self._value = ctk.BooleanVar(value=default)

        container = ctk.CTkFrame(self)
        container.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)

        message_label = ctk.CTkLabel(container, text=message, justify="left", anchor="w")
        message_label.grid(row=0, column=0, sticky="w", pady=(0, 10))

        checkbox = ctk.CTkCheckBox(container, text=checkbox_label, variable=self._value)
        checkbox.grid(row=1, column=0, sticky="w", pady=(0, 10))

        button_row = ctk.CTkFrame(container, fg_color="transparent")
        button_row.grid(row=2, column=0, sticky="e")

        ok_button = ctk.CTkButton(button_row, text=confirm_label, command=self._confirm)
        ok_button.grid(row=0, column=0, padx=(0, 6))
        cancel_button = ctk.CTkButton(button_row, text=cancel_label, command=self._cancel)
        cancel_button.grid(row=0, column=1)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _confirm(self):
        self.result = bool(self._value.get())
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
