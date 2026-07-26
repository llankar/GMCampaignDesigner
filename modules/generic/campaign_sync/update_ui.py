"""Small Tk views for campaign update preferences and available updates."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from typing import Callable

import customtkinter as ctk

from .settings import CampaignUpdatePreferences
from .update_checker import CampaignUpdateResult


class CampaignUpdatePrompt(ctk.CTkToplevel):
    """Non-modal prompt: the rest of the application remains usable."""

    def __init__(self, master, result: CampaignUpdateResult, *, on_update: Callable[[], None],
                 on_later: Callable[[], None], on_ignore: Callable[[], None]) -> None:
        super().__init__(master)
        self.title("Campaign update available")
        self.geometry("560x390")
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._later)
        self._on_later = on_later

        ctk.CTkLabel(self, text=f"Update available for {result.campaign_name}",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(padx=24, pady=(24, 12))
        published = (
            result.published_at.astimezone().strftime("%Y-%m-%d %H:%M %Z")
            if isinstance(result.published_at, datetime)
            else str(result.published_at or "Unknown")
        )
        details = [
            f"Installed revision: {result.installed_revision}",
            f"Available revision: {result.available_revision}",
            f"Published: {published}",
        ]
        if result.publisher:
            details.append(f"Publisher: {result.publisher}")
        if result.change_summary:
            details.extend(("", "Changes:", result.change_summary))
        ctk.CTkLabel(self, text="\n".join(details), justify="left", anchor="nw",
                     wraplength=500).pack(fill="both", expand=True, padx=28, pady=12)
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(8, 20))
        ctk.CTkButton(buttons, text="Update now", command=lambda: self._choose(on_update)).pack(side="left")
        ctk.CTkButton(buttons, text="Later", command=self._later).pack(side="left", padx=10)
        ctk.CTkButton(buttons, text="Ignore this revision", command=lambda: self._choose(on_ignore)).pack(side="right")
        self.lift()

    def _choose(self, callback: Callable[[], None]) -> None:
        self.destroy()
        callback()

    def _later(self) -> None:
        self.destroy()
        self._on_later()


class CampaignUpdateSettingsDialog(ctk.CTkToplevel):
    def __init__(self, master) -> None:
        super().__init__(master)
        self.title("Campaign Update Settings")
        self.geometry("520x330")
        self.resizable(False, False)
        preferences = CampaignUpdatePreferences.load()
        self.checks = tk.BooleanVar(value=preferences.automatic_checks)
        self.download = tk.BooleanVar(value=preferences.automatic_download)
        self.offline = tk.BooleanVar(value=preferences.offline)
        self.frequency = tk.StringVar(value=str(preferences.frequency_hours))
        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkCheckBox(frame, text="Automatically check linked campaigns", variable=self.checks).pack(anchor="w", pady=8)
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", pady=8)
        ctk.CTkLabel(row, text="Check frequency (hours):").pack(side="left")
        ctk.CTkEntry(row, textvariable=self.frequency, width=90).pack(side="left", padx=12)
        ctk.CTkCheckBox(frame, text="Download updates automatically (confirmation is still required to apply)",
                        variable=self.download).pack(anchor="w", pady=8)
        ctk.CTkCheckBox(frame, text="Offline / disable network checks", variable=self.offline).pack(anchor="w", pady=8)
        self.error = ctk.CTkLabel(frame, text="", text_color="#ff7777")
        self.error.pack(anchor="w", pady=4)
        ctk.CTkButton(frame, text="Save", command=self._save).pack(side="right", pady=12)
        self.transient(master)
        self.lift()

    def _save(self) -> None:
        try:
            hours = int(self.frequency.get())
            if hours < 1:
                raise ValueError
        except ValueError:
            self.error.configure(text="Frequency must be a positive whole number.")
            return
        CampaignUpdatePreferences(self.checks.get(), hours, self.download.get(), self.offline.get()).save()
        self.destroy()
