"""Modal dialog for switching the active campaign system."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from modules.helpers import system_config
from modules.helpers import theme_manager
from modules.helpers.logging_helper import (
    log_exception,
    log_info,
    log_module_import,
    log_warning,
)

log_module_import(__name__)


SystemSelectedCallback = Callable[[system_config.SystemConfig], None]


class CampaignSystemSelectorDialog(ctk.CTkToplevel):
    """Displays available campaign systems and updates the active selection."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        on_selected: SystemSelectedCallback | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Select Campaign System")
        self.geometry("440x420")
        self.resizable(False, False)

        self._on_selected = on_selected
        self._system_var = tk.StringVar()
        self._system_var.trace_add("write", lambda *_args: self._update_confirm_state())
        self._theme_var = tk.StringVar(value=theme_manager.get_theme())

        self._radio_container: ctk.CTkScrollableFrame | None = None
        self._confirm_button: ctk.CTkButton | None = None

        self._build_ui()
        self._load_systems()

        self.transient(master)
        self.grab_set()
        self.lift()
        self.focus_force()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=18, pady=18)
        container.grid_columnconfigure(0, weight=1)

        header = ctk.CTkLabel(
            container,
            text="Choose which rules system this campaign should use.",
            wraplength=360,
            justify="left",
        )
        header.grid(row=0, column=0, sticky="w")

        radio_container = ctk.CTkScrollableFrame(container, height=260)
        radio_container.grid(row=1, column=0, sticky="nsew", pady=12)
        radio_container.grid_columnconfigure(0, weight=1)
        self._radio_container = radio_container

        button_row = ctk.CTkFrame(container, fg_color="transparent")
        button_row.grid(row=2, column=0, sticky="e")

        cancel = ctk.CTkButton(
            button_row,
            text="Cancel",
            command=self._cancel,
            width=100,
        )
        cancel.pack(side="right", padx=(6, 0))

        confirm = ctk.CTkButton(
            button_row,
            text="Use Selected System",
            command=self._confirm_selection,
            width=180,
        )
        confirm.pack(side="right")
        self._confirm_button = confirm

        # Theme selection row below the list
        theme_row = ctk.CTkFrame(container, fg_color="transparent")
        theme_row.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ctk.CTkLabel(theme_row, text="Visual Theme:").pack(side="left", padx=(0, 8))
        themes = [
            ("Default", theme_manager.THEME_DEFAULT),
            ("Medieval", theme_manager.THEME_MEDIEVAL),
            ("Sci‑Fi", theme_manager.THEME_SF),
        ]
        for label, key in themes:
            rb = ctk.CTkRadioButton(theme_row, text=label, value=key, variable=self._theme_var)
            rb.pack(side="left", padx=6)

    def _load_systems(self) -> None:
        container = self._radio_container
        if container is None:
            return

        for child in list(container.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        try:
            systems = system_config.list_available_systems()
        except Exception as exc:
            log_exception(
                f"Failed to list campaign systems: {exc}",
                func_name="CampaignSystemSelectorDialog._load_systems",
            )
            self._display_empty_state(
                "Unable to load the list of systems. Please try again later."
            )
            return

        if not systems:
            self._display_empty_state(
                "No campaign systems are configured. Add entries to the database first."
            )
            return

        current = system_config.get_current_system_config()
        current_slug = getattr(current, "slug", "")
        self._system_var.set(current_slug)

        for index, entry in enumerate(systems):
            row = ctk.CTkFrame(container, fg_color="transparent")
            row.grid(row=index, column=0, sticky="ew", pady=4)
            row.grid_columnconfigure(0, weight=1)

            radio = ctk.CTkRadioButton(
                row,
                text=f"{entry.label} ({entry.slug})",
                value=entry.slug,
                variable=self._system_var,
            )
            radio.grid(row=0, column=0, sticky="w")

            if entry.default_formula:
                formula_label = ctk.CTkLabel(
                    row,
                    text=f"Default formula: {entry.default_formula}",
                    font=ctk.CTkFont(size=12, slant="italic"),
                )
                formula_label.grid(row=1, column=0, sticky="w", padx=(24, 0))

        self._update_confirm_state()

    def _display_empty_state(self, message: str) -> None:
        container = self._radio_container
        if container is None:
            return
        label = ctk.CTkLabel(container, text=message, wraplength=360, justify="left")
        label.grid(row=0, column=0, sticky="w")
        if self._confirm_button:
            self._confirm_button.configure(state="disabled")

    def _update_confirm_state(self) -> None:
        if self._confirm_button is None:
            return
        state = "normal" if self._system_var.get().strip() else "disabled"
        self._confirm_button.configure(state=state)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _cancel(self) -> None:
        self.destroy()

    def _confirm_selection(self) -> None:
        # Always persist/apply theme selection, even if system doesn't change
        try:
            sel_theme = self._theme_var.get().strip()
            if sel_theme:
                theme_manager.set_theme(sel_theme)
        except Exception:
            pass

        slug = self._system_var.get().strip()
        if not slug:
            self._update_confirm_state()
            self.destroy()
            return

        current = system_config.get_current_system_config()
        current_slug = getattr(current, "slug", None)
        if slug == current_slug:
            # Theme already applied; no system change needed
            self.destroy()
            return

        try:
            new_config = system_config.set_current_system(slug)
        except ValueError as exc:
            log_warning(
                f"Rejected invalid system selection '{slug}': {exc}",
                func_name="CampaignSystemSelectorDialog._confirm_selection",
            )
            messagebox.showwarning("Invalid Selection", str(exc))
            return
        except Exception as exc:
            log_exception(
                f"Failed to update campaign system: {exc}",
                func_name="CampaignSystemSelectorDialog._confirm_selection",
            )
            messagebox.showerror(
                "Error",
                "An unexpected error occurred while updating the campaign system.",
            )
            return

        if isinstance(new_config, system_config.SystemConfig):
            log_info(
                f"Campaign system updated to '{new_config.slug}'",
                func_name="CampaignSystemSelectorDialog._confirm_selection",
            )
        else:
            log_info(
                f"Campaign system updated to '{slug}'",
                func_name="CampaignSystemSelectorDialog._confirm_selection",
            )

        if callable(self._on_selected) and isinstance(new_config, system_config.SystemConfig):
            try:
                self._on_selected(new_config)
            except Exception as exc:
                log_warning(
                    f"System selection callback failed: {exc}",
                    func_name="CampaignSystemSelectorDialog._confirm_selection",
                )

        self.destroy()

    def destroy(self) -> None:  # type: ignore[override]
        try:
            self.grab_release()
        except Exception:
            pass
        super().destroy()

