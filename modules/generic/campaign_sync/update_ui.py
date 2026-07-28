"""Small Tk views for campaign update preferences and available updates."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from typing import Callable, Optional

import customtkinter as ctk

from .settings import CampaignUpdatePreferences
from .update_checker import CampaignUpdateResult
from .change_detector import CampaignChangeState


class CampaignUpdatePrompt(ctk.CTkToplevel):
    """Non-modal prompt: the rest of the application remains usable."""

    def __init__(self, master, result: CampaignUpdateResult, *, on_update: Callable[[], None],
                 on_later: Callable[[], None], on_ignore: Callable[[], None],
                 on_backup_replace: Optional[Callable[[], None]] = None,
                 on_publish_local: Optional[Callable[[], None]] = None,
                 on_save_remote: Optional[Callable[[], None]] = None) -> None:
        super().__init__(master)
        self.title("Campaign update available")
        self.geometry("680x500")
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
        if result.conflict:
            details.extend((
                "", "Conflict: local and remote changes derive from the same parent revision.",
                "Nothing will be merged or overwritten automatically.",
            ))
        elif result.local_change_state is CampaignChangeState.LOCALLY_MODIFIED:
            details.extend(("", "Local content has changed since the installed revision."))
        elif result.local_change_state is CampaignChangeState.UNKNOWN:
            details.extend(("", "Local change state is unknown; a safe one-click replacement is disabled."))
        ctk.CTkLabel(self, text="\n".join(details), justify="left", anchor="nw",
                     wraplength=500).pack(fill="both", expand=True, padx=28, pady=12)
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(8, 20))
        if result.local_change_state is CampaignChangeState.CLEAN:
            ctk.CTkButton(buttons, text="Replace with update", command=lambda: self._choose(on_update)).pack(side="left")
        else:
            ctk.CTkButton(
                buttons, text="Back up local and replace",
                command=lambda: self._choose(on_backup_replace),
                state="normal" if on_backup_replace else "disabled",
            ).pack(side="left")
            ctk.CTkButton(
                buttons, text="Publish local as new revision",
                command=lambda: self._choose(on_publish_local),
                state="normal" if on_publish_local and not result.conflict else "disabled",
            ).pack(side="left", padx=8)
            ctk.CTkButton(
                buttons, text="Save remote separately",
                command=lambda: self._choose(on_save_remote),
                state="normal" if on_save_remote else "disabled",
            ).pack(side="left")
        ctk.CTkButton(buttons, text="Cancel", command=self._later).pack(side="right", padx=8)
        ctk.CTkButton(buttons, text="Ignore", command=lambda: self._choose(on_ignore)).pack(side="right")
        self.lift()

    def _choose(self, callback: Optional[Callable[[], None]]) -> None:
        if callback is None:
            return
        self.destroy()
        callback()

    def _later(self) -> None:
        self.destroy()
        self._on_later()


class CampaignUpdateSettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, *, on_saved: Optional[Callable[[CampaignUpdatePreferences], None]] = None) -> None:
        super().__init__(master)
        self._on_saved = on_saved
        self.title("Campaign Update Settings")
        self.geometry("560x470")
        self.resizable(False, False)
        preferences = CampaignUpdatePreferences.load()
        self.checks = tk.BooleanVar(value=preferences.automatic_checks)
        self.download = tk.BooleanVar(value=preferences.automatic_download)
        self.offline = tk.BooleanVar(value=preferences.offline)
        self.frequency = tk.StringVar(value=str(preferences.frequency_hours))
        self.auto_publish = tk.BooleanVar(value=preferences.automatic_publication)
        self.publish_idle = tk.StringVar(value=str(preferences.publication_idle_seconds))
        self.publish_maximum = tk.StringVar(value=str(preferences.publication_maximum_seconds))
        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkCheckBox(frame, text="Automatically check linked campaigns", variable=self.checks).pack(anchor="w", pady=8)
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", pady=8)
        ctk.CTkLabel(row, text="Check frequency (hours):").pack(side="left")
        ctk.CTkEntry(row, textvariable=self.frequency, width=90).pack(side="left", padx=12)
        ctk.CTkCheckBox(frame, text="Download updates automatically (confirmation is still required to apply)",
                        variable=self.download).pack(anchor="w", pady=8)
        ctk.CTkCheckBox(frame, text="Automatically publish saved campaign changes",
                        variable=self.auto_publish).pack(anchor="w", pady=8)
        publish_row = ctk.CTkFrame(frame, fg_color="transparent")
        publish_row.pack(fill="x", pady=8)
        ctk.CTkLabel(publish_row, text="Idle delay (seconds):").pack(side="left")
        ctk.CTkEntry(publish_row, textvariable=self.publish_idle, width=75).pack(side="left", padx=8)
        ctk.CTkLabel(publish_row, text="Maximum interval:").pack(side="left", padx=(12, 0))
        ctk.CTkEntry(publish_row, textvariable=self.publish_maximum, width=75).pack(side="left", padx=8)
        ctk.CTkCheckBox(frame, text="Offline / disable network checks", variable=self.offline).pack(anchor="w", pady=8)
        self.error = ctk.CTkLabel(frame, text="", text_color="#ff7777")
        self.error.pack(anchor="w", pady=4)
        ctk.CTkButton(frame, text="Save", command=self._save).pack(side="right", pady=12)
        self.transient(master)
        self.lift()

    def _save(self) -> None:
        try:
            hours = int(self.frequency.get())
            idle = int(self.publish_idle.get())
            maximum = int(self.publish_maximum.get())
            if hours < 1 or idle < 1 or maximum < idle:
                raise ValueError
        except ValueError:
            self.error.configure(text="Use positive whole numbers; maximum must be at least the idle delay.")
            return
        preferences = CampaignUpdatePreferences(
            self.checks.get(), hours, self.download.get(), self.offline.get(),
            self.auto_publish.get(), idle, maximum,
        )
        preferences.save()
        if self._on_saved is not None:
            self._on_saved(preferences)
        self.destroy()
