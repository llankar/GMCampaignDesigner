from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, List

from modules.helpers.logging_helper import log_module_import
from modules.helpers.window_helper import position_window_at_top

log_module_import(__name__)

SECTION_OPTIONS = [
    ("Summary", "Résumé"),
    ("Scenes", "Scènes"),
    ("Places", "Lieux"),
    ("NPCs", "PNJ"),
    ("Creatures", "Créatures"),
    ("Factions", "Factions"),
    ("Objects", "Objets"),
    ("Books", "Livres"),
]


class NewsletterConfigDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent: tk.Misc | None,
        scenario_title: str,
        on_generate: Callable[[Dict[str, object]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("Newsletter - Configuration")
        self.geometry("520x680")
        self.minsize(520, 680)

        self._scenario_title = scenario_title
        self._on_generate = on_generate

        self._section_vars: Dict[str, tk.BooleanVar] = {}
        self._language_var = tk.StringVar(value="français")
        self._style_var = tk.StringVar(value="neutre")
        self._use_ai_var = tk.BooleanVar(value=False)
        self._base_textbox: ctk.CTkTextbox | None = None
        self._destroy_scheduled = False

        self._build_ui()
        position_window_at_top(self)

    def _build_ui(self) -> None:
        header = ctk.CTkLabel(
            self,
            text=f"Newsletter : {self._scenario_title}",
            font=("Arial", 18, "bold"),
        )
        header.pack(fill="x", padx=20, pady=(20, 10))

        recap_frame = ctk.CTkFrame(self)
        recap_frame.pack(fill="both", expand=False, padx=20, pady=(0, 10))
        recap_label = ctk.CTkLabel(
            recap_frame,
            text="Résumé de la partie (base principale du texte)",
            font=("Arial", 14, "bold"),
        )
        recap_label.pack(anchor="w", padx=10, pady=(10, 4))
        self._base_textbox = ctk.CTkTextbox(recap_frame, height=120, wrap="word")
        self._base_textbox.pack(fill="x", padx=10, pady=(0, 10))

        section_frame = ctk.CTkFrame(self)
        section_frame.pack(fill="both", expand=False, padx=20, pady=10)

        section_label = ctk.CTkLabel(
            section_frame,
            text="Sections à inclure",
            font=("Arial", 14, "bold"),
        )
        section_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(10, 5))

        for index, (key, label) in enumerate(SECTION_OPTIONS, start=1):
            var = tk.BooleanVar(value=True)
            self._section_vars[key] = var
            checkbox = ctk.CTkCheckBox(
                section_frame,
                text=label,
                variable=var,
            )
            row = (index - 1) // 2 + 1
            col = (index - 1) % 2
            checkbox.grid(row=row, column=col, sticky="w", padx=10, pady=4)

        language_frame = ctk.CTkFrame(self)
        language_frame.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(language_frame, text="Langue", width=90, anchor="w").grid(
            row=0,
            column=0,
            padx=10,
            pady=8,
            sticky="w",
        )
        language_entry = ctk.CTkEntry(language_frame, textvariable=self._language_var)
        language_entry.grid(row=0, column=1, padx=10, pady=8, sticky="ew")
        language_frame.columnconfigure(1, weight=1)

        style_frame = ctk.CTkFrame(self)
        style_frame.pack(fill="x", padx=20, pady=(5, 5))
        ctk.CTkLabel(style_frame, text="Ton / style", width=90, anchor="w").grid(
            row=0,
            column=0,
            padx=10,
            pady=8,
            sticky="w",
        )
        style_entry = ctk.CTkEntry(style_frame, textvariable=self._style_var)
        style_entry.grid(row=0, column=1, padx=10, pady=8, sticky="ew")
        style_frame.columnconfigure(1, weight=1)

        ai_frame = ctk.CTkFrame(self)
        ai_frame.pack(fill="x", padx=20, pady=(5, 15))
        ai_checkbox = ctk.CTkCheckBox(
            ai_frame,
            text="Utiliser l'IA locale",
            variable=self._use_ai_var,
        )
        ai_checkbox.pack(anchor="w", padx=10, pady=8)

        button_row = ctk.CTkFrame(self)
        button_row.pack(fill="x", padx=20, pady=(0, 20))
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=1)

        generate_button = ctk.CTkButton(
            button_row,
            text="Prévisualiser",
            command=self._handle_generate,
        )
        generate_button.grid(row=0, column=0, padx=8, sticky="ew")

        cancel_button = ctk.CTkButton(
            button_row,
            text="Annuler",
            command=self._handle_cancel,
        )
        cancel_button.grid(row=0, column=1, padx=8, sticky="ew")

    def _handle_generate(self) -> None:
        sections = [
            key for key, var in self._section_vars.items() if var.get()
        ]
        if not sections:
            messagebox.showwarning(
                "Newsletter",
                "Sélectionnez au moins une section.",
                parent=self,
            )
            return
        language = self._language_var.get().strip() or None
        style = self._style_var.get().strip() or None
        use_ai = bool(self._use_ai_var.get())
        base_text = ""
        if self._base_textbox is not None:
            base_text = self._base_textbox.get("1.0", "end").strip()

        payload: Dict[str, object] = {
            "sections": sections,
            "language": language,
            "style": style,
            "use_ai": use_ai,
            "base_text": base_text or None,
        }
        if self._on_generate:
            self._on_generate(payload)
        self.destroy()

    def _handle_cancel(self) -> None:
        self.destroy()

    def _schedule_safe_destroy(self) -> None:  # pragma: no cover - UI teardown
        if self._destroy_scheduled:
            return

        self._destroy_scheduled = True

        try:
            if self.winfo_exists():
                self.withdraw()
        except Exception:
            pass

        def _finalize() -> None:
            try:
                super(NewsletterConfigDialog, self).destroy()
            except Exception:
                pass

        try:
            self.after(150, _finalize)
        except Exception:
            _finalize()

    def destroy(self) -> None:  # pragma: no cover - UI teardown
        self._schedule_safe_destroy()

    def focus_set(self) -> None:  # pragma: no cover - UI focus handling
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            super().focus_set()
        except tk.TclError:
            pass

    def focus_force(self) -> None:  # pragma: no cover - UI focus handling
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            super().focus_force()
        except tk.TclError:
            pass
