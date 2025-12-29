from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import Any, Dict

from modules.handouts.newsletter_rtf import (
    build_newsletter_rtf_from_ai_text,
    build_newsletter_rtf_from_payload,
    build_newsletter_rtf_json_from_ai_text,
    build_newsletter_rtf_json_from_payload,
)
from modules.helpers.logging_helper import log_exception, log_module_import
from modules.helpers.rtf_rendering import render_rtf_to_text_widget
from modules.helpers.window_helper import position_window_at_top

log_module_import(__name__)


class NewsletterWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent: tk.Misc | None = None,
        payload: Any | None = None,
        ai_text: Any | None = None,
        language: str | None = None,
        style: str | None = None,
        title: str = "Newsletter",
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.geometry("900x650")
        self.minsize(900, 500)
        position_window_at_top(self)

        self._payload = payload
        self._ai_text = ai_text
        self._language = language
        self._style = style

        self._rtf_json: Dict[str, Any] = {}
        self._rtf_string = ""

        self._build_ui()
        self._render_content()

    def _build_ui(self) -> None:
        header = ctk.CTkLabel(self, text="Newsletter (RTF)", font=("Arial", 18, "bold"))
        header.pack(fill="x", padx=15, pady=(15, 5))

        self.status_var = tk.StringVar(value="")
        status = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", padx=15, pady=(0, 5))

        self.textbox = ctk.CTkTextbox(self, wrap="word")
        self.textbox.pack(fill="both", expand=True, padx=15, pady=10)

        button_row = ctk.CTkFrame(self)
        button_row.pack(fill="x", padx=15, pady=(0, 15))
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=1)

        copy_plain = ctk.CTkButton(
            button_row,
            text="Copier dans le presse-papiers",
            command=self._copy_plain_text,
        )
        copy_plain.grid(row=0, column=0, padx=5, sticky="ew")

        copy_rtf = ctk.CTkButton(
            button_row,
            text="Copier en RTF",
            command=self._copy_rtf,
        )
        copy_rtf.grid(row=0, column=1, padx=5, sticky="ew")

    def _render_content(self) -> None:
        if self._ai_text:
            self._rtf_json = build_newsletter_rtf_json_from_ai_text(self._ai_text)
            self._rtf_string = build_newsletter_rtf_from_ai_text(self._ai_text)
        else:
            self._rtf_json = build_newsletter_rtf_json_from_payload(
                self._payload,
                self._language,
                self._style,
            )
            self._rtf_string = build_newsletter_rtf_from_payload(
                self._payload,
                self._language,
                self._style,
            )

        try:
            render_rtf_to_text_widget(self.textbox, self._rtf_json)
            self.status_var.set("RTF chargé.")
        except Exception as exc:
            log_exception(
                f"RTF rendering failed: {exc}",
                func_name="NewsletterWindow._render_content",
            )
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", tk.END)
            self.textbox.insert("1.0", str(self._rtf_json.get("text", "")))
            self.textbox.configure(state="disabled")
            self.status_var.set("Affichage en texte brut (RTF non compatible).")

    def _copy_plain_text(self) -> None:
        text = str(self._rtf_json.get("text", ""))
        if not text.strip():
            messagebox.showinfo("Newsletter", "Aucun texte à copier.")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_var.set("Texte copié dans le presse-papiers.")
        except Exception as exc:
            log_exception(
                f"Clipboard copy failed: {exc}",
                func_name="NewsletterWindow._copy_plain_text",
            )
            messagebox.showwarning("Newsletter", "Impossible de copier le texte.")

    def _copy_rtf(self) -> None:
        if not self._rtf_string.strip():
            messagebox.showinfo("Newsletter", "Aucun RTF à copier.")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(self._rtf_string)
            self.status_var.set("RTF copié dans le presse-papiers.")
        except Exception as exc:
            log_exception(
                f"RTF clipboard copy failed: {exc}",
                func_name="NewsletterWindow._copy_rtf",
            )
            messagebox.showwarning("Newsletter", "Impossible de copier le RTF.")
