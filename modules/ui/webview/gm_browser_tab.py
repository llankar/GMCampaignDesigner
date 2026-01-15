"""Embedded browser tab for the GM screen."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk
from tkinterweb import HtmlFrame

DEFAULT_HOME_URL = "https://example.com"


def _normalize_url(raw_url: str | None) -> str:
    if not raw_url:
        return DEFAULT_HOME_URL
    url = raw_url.strip()
    if not url:
        return DEFAULT_HOME_URL
    if "://" not in url:
        return f"https://{url}"
    return url


def create_gm_browser_frame(master: ctk.CTkBaseClass, *, initial_url: str | None = None) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(master)
    toolbar = ctk.CTkFrame(frame)
    toolbar.pack(fill="x", padx=8, pady=(8, 4))

    url_var = tk.StringVar(value=_normalize_url(initial_url))
    address_entry = ctk.CTkEntry(toolbar, textvariable=url_var)
    address_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    button_bar = ctk.CTkFrame(toolbar, fg_color="transparent")
    button_bar.pack(side="left")

    browser = HtmlFrame(frame)
    browser.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    frame.browser = browser
    frame.current_url = ""

    def _load(url: str | None) -> None:
        target = _normalize_url(url)
        url_var.set(target)
        frame.current_url = target
        if hasattr(browser, "load_website"):
            browser.load_website(target)
        elif hasattr(browser, "load_url"):
            browser.load_url(target)

    def _sync_url(_event=None) -> None:
        new_url = getattr(browser, "url", "") or getattr(browser, "current_url", "")
        if new_url:
            frame.current_url = new_url
            url_var.set(new_url)

    def _go_back() -> None:
        if hasattr(browser, "go_back"):
            browser.go_back()

    def _go_forward() -> None:
        if hasattr(browser, "go_forward"):
            browser.go_forward()

    def _reload() -> None:
        if hasattr(browser, "reload"):
            browser.reload()
        elif hasattr(browser, "load_website"):
            browser.load_website(_normalize_url(url_var.get()))

    back_button = ctk.CTkButton(button_bar, text="◀", width=36, command=_go_back)
    back_button.pack(side="left", padx=(0, 6))
    forward_button = ctk.CTkButton(button_bar, text="▶", width=36, command=_go_forward)
    forward_button.pack(side="left", padx=(0, 6))
    reload_button = ctk.CTkButton(button_bar, text="⟳", width=36, command=_reload)
    reload_button.pack(side="left")
    go_button = ctk.CTkButton(button_bar, text="Go", width=60, command=lambda: _load(url_var.get()))
    go_button.pack(side="left", padx=(6, 0))

    address_entry.bind("<Return>", lambda _event=None: _load(url_var.get()))
    browser.bind("<<URLChanged>>", _sync_url)

    _load(url_var.get())

    return frame
