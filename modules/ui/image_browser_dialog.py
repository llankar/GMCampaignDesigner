"""Dialog window that launches a webview for browsing free image libraries."""

from __future__ import annotations

import tkinter as tk
from urllib.parse import quote_plus

import customtkinter as ctk

from modules.helpers.logging_helper import log_exception, log_module_import
from modules.helpers.window_helper import position_window_at_top
from modules.ui.webview.pywebview_client import PyWebviewClient

log_module_import(__name__)


class ImageBrowserDialog(ctk.CTkToplevel):
    """Display an optional dialog that launches a webview for free image search."""

    _PROVIDER_URLS: dict[str, str] = {
        "unsplash": "https://www.google.com/search?tbm=isch&q={query}&tbs=isz:l",
        "pexels": "https://www.pexels.com/search/{query}/",
        "pixabay": "https://pixabay.com/images/search/{query}/",
        "wikimedia": "https://commons.wikimedia.org/w/index.php?search={query}",
    }

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        search_query: str = "fantasy portrait",
        provider: str = "unsplash",
    ) -> None:
        super().__init__(master)
        self.title("Image Browser")
        self.geometry("1100x760")
        self.minsize(900, 620)
        position_window_at_top(self)

        self._search_query = search_query
        self._provider = provider.lower().strip()
        self._browser_client = PyWebviewClient(title="Image Browser")

        self._build_ui()
        self._load_initial_page()

        self.bind("<Escape>", lambda _event: self.destroy())
        self.transient(master)
        self.lift()
        self.focus_force()

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=14, pady=14)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(3, weight=1)

        title = ctk.CTkLabel(
            container,
            text="Browse free image libraries",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        helper = ctk.CTkLabel(
            container,
            text="Copiez l’image puis utilisez ‘Paste Portrait’.",
            font=ctk.CTkFont(size=12, slant="italic"),
            anchor="w",
        )
        helper.grid(row=1, column=0, sticky="w", pady=(6, 4))

        info = ctk.CTkLabel(
            container,
            text="Le navigateur d’images s’ouvre dans une fenêtre séparée.",
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        info.grid(row=2, column=0, sticky="w", pady=(0, 12))

        open_button = ctk.CTkButton(
            container,
            text="Ouvrir le navigateur",
            command=self._load_initial_page,
        )
        open_button.grid(row=3, column=0, sticky="w")

    @staticmethod
    def build_search_url(query: str, provider: str = "unsplash") -> str:
        provider_key = (provider or "").lower().strip()
        template = ImageBrowserDialog._PROVIDER_URLS.get(provider_key)
        if not template:
            template = ImageBrowserDialog._PROVIDER_URLS["unsplash"]
        encoded_query = quote_plus((query or "").strip() or "portrait")
        return template.format(query=encoded_query)

    def _resolve_search_url(self) -> str:
        return self.build_search_url(self._search_query, self._provider)

    def _load_initial_page(self) -> None:
        url = self._resolve_search_url()
        try:
            self._browser_client.open(url)
        except Exception as exc:  # pragma: no cover - UI fallback
            log_exception(
                f"Unable to load webview for {url}: {exc}",
                func_name="ImageBrowserDialog._load_initial_page",
            )
            error_label = ctk.CTkLabel(
                self,
                text=(
                    "Impossible d’ouvrir la page d’images. "
                    "Vérifiez la connexion puis réessayez."
                ),
                text_color="#ffb4b4",
            )
            error_label.pack(pady=12)
