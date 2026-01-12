from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

import customtkinter as ctk
from tkinter import messagebox

from modules.helpers.logging_helper import (
    log_exception,
    log_function,
    log_methods,
    log_module_import,
)
from modules.helpers.window_helper import position_window_at_top
from modules.ui.imports.text_import_dialog import TextImportDialog
from modules.ui.webview.pywebview_client import PyWebviewClient

log_module_import(__name__)


@log_methods
class WebTextImportDialog(ctk.CTkToplevel):
    _SEARCH_URL = "https://www.google.com/search?q={query}"
    _DEFAULT_QUERY = "fantasy lore"

    def __init__(
        self,
        master,
        *,
        default_target_slug: str | None = None,
        on_complete=None,
    ) -> None:
        super().__init__(master)
        self.default_target_slug = default_target_slug
        self.on_complete = on_complete
        self._selection_path = self._build_selection_path()
        self._browser_client = PyWebviewClient(title="Web Text Import")
        self._polling_job = None
        self._subject_var = ctk.StringVar()
        self._status_var = ctk.StringVar()
        self._build_ui()

        self.bind("<Escape>", lambda _event: self._on_close())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.transient(master)
        self.lift()
        self.focus_force()

    def _build_ui(self) -> None:
        self.title("Import de texte (Web)")
        self.geometry("880x320")
        self.minsize(820, 280)
        position_window_at_top(self)

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)
        container.grid_columnconfigure(1, weight=1)

        header = ctk.CTkLabel(
            container,
            text="Importer un texte depuis le web",
            font=("TkDefaultFont", 16, "bold"),
            anchor="w",
        )
        header.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        helper = ctk.CTkLabel(
            container,
            text="Sélectionnez du texte dans la page puis cliquez « Importer ».",
            font=("TkDefaultFont", 12, "italic"),
            anchor="w",
        )
        helper.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ctk.CTkLabel(container, text="Sujet", anchor="w").grid(
            row=2, column=0, sticky="w"
        )
        subject_entry = ctk.CTkEntry(container, textvariable=self._subject_var)
        subject_entry.grid(row=2, column=1, sticky="ew", padx=(8, 0))

        search_button = ctk.CTkButton(
            container,
            text="Rechercher",
            command=self._open_search,
        )
        search_button.grid(row=3, column=1, sticky="e", pady=(8, 0))

        info = ctk.CTkLabel(
            container,
            text="Le navigateur s’ouvre dans une fenêtre séparée.",
            font=("TkDefaultFont", 12),
            anchor="w",
        )
        info.grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

        status = ctk.CTkLabel(
            container,
            textvariable=self._status_var,
            text_color="#9fa6b2",
            anchor="w",
        )
        status.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

    @staticmethod
    def _build_selection_path() -> Path:
        filename = f"web_selection_{uuid4().hex}.json"
        return Path(tempfile.gettempdir()) / filename

    def _resolve_search_url(self) -> str:
        subject = (self._subject_var.get() or "").strip() or self._DEFAULT_QUERY
        encoded = quote_plus(subject)
        return self._SEARCH_URL.format(query=encoded)

    @log_function
    def _open_search(self) -> None:
        url = self._resolve_search_url()
        self._status_var.set("Recherche ouverte dans le navigateur.")
        try:
            if self._selection_path.exists():
                self._selection_path.unlink()
            self._browser_client.open(
                url,
                use_shell=True,
                selection_output=str(self._selection_path),
            )
        except Exception as exc:  # pragma: no cover - UI fallback
            log_exception(
                f"Unable to open webview for {url}: {exc}",
                func_name="WebTextImportDialog._open_search",
            )
            messagebox.showerror(
                "Import Web",
                "Impossible d’ouvrir le navigateur web.",
            )
            return
        if not self._polling_job:
            self._poll_selection()

    def _poll_selection(self) -> None:
        self._polling_job = self.after(800, self._poll_selection)
        if not self._selection_path.exists():
            return
        try:
            payload_text = self._selection_path.read_text(encoding="utf-8").strip()
        except Exception as exc:
            log_exception(
                f"Unable to read selection payload: {exc}",
                func_name="WebTextImportDialog._poll_selection",
            )
            return
        if not payload_text:
            return
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            log_exception(
                "Invalid selection payload received.",
                func_name="WebTextImportDialog._poll_selection",
            )
            try:
                self._selection_path.unlink()
            except Exception:
                pass
            return
        selection = (payload.get("selection") or "").strip()
        url = (payload.get("url") or "").strip()
        if selection:
            self._open_text_import_dialog(selection, url)
            self._status_var.set("Sélection récupérée.")
        try:
            self._selection_path.unlink()
        except Exception:
            pass

    def _open_text_import_dialog(self, selection: str, url: str) -> None:
        dialog = TextImportDialog(
            self,
            source_text=selection,
            source_url=url or None,
            default_target_slug=self.default_target_slug,
            on_complete=self.on_complete,
        )
        dialog.focus_force()

    def _on_close(self) -> None:
        if self._polling_job:
            self.after_cancel(self._polling_job)
            self._polling_job = None
        try:
            if self._selection_path.exists():
                self._selection_path.unlink()
        except Exception:
            pass
        self.destroy()
