"""Reusable session-control widgets for scenario note surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import customtkinter as ctk

Callback = Callable[[], None]
PersistCallback = Callable[[object | None], None]


@dataclass(frozen=True)
class SessionControlsCallbacks:
    """Callbacks triggered by the session-control buttons."""

    on_start: Callback
    on_end: Callback
    on_capture: Callback
    on_debrief: Callback
    on_settings: Callback
    on_hours_changed: PersistCallback | None = None


@dataclass(frozen=True)
class SessionControlsWidgets:
    """References to the controls that callers may need to update later."""

    mid_entry: ctk.CTkEntry
    end_entry: ctk.CTkEntry
    start_button: ctk.CTkButton
    end_button: ctk.CTkButton
    capture_button: ctk.CTkButton
    debrief_button: ctk.CTkButton
    settings_button: ctk.CTkButton


class SessionControls(ctk.CTkFrame):
    """Shared Start/End/Capture/Debrief/Settings control strip."""

    def __init__(
        self,
        master,
        *,
        mid_variable,
        end_variable,
        callbacks: SessionControlsCallbacks,
        enabled: bool = True,
        scenario_actions_enabled: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="Session:").pack(side="left", padx=(6, 4))
        ctk.CTkLabel(self, text="Mid (hrs)").pack(side="left", padx=(0, 4))
        mid_entry = ctk.CTkEntry(self, width=60, textvariable=mid_variable)
        mid_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(self, text="End (hrs)").pack(side="left", padx=(0, 4))
        end_entry = ctk.CTkEntry(self, width=60, textvariable=end_variable)
        end_entry.pack(side="left", padx=(0, 8))
        start_btn = ctk.CTkButton(
            self, text="Start", width=70, command=callbacks.on_start
        )
        start_btn.pack(side="left", padx=(0, 4))
        end_btn = ctk.CTkButton(self, text="End", width=70, command=callbacks.on_end)
        end_btn.pack(side="left", padx=(0, 4))
        capture_btn = ctk.CTkButton(
            self, text="Capture", width=84, command=callbacks.on_capture
        )
        capture_btn.pack(side="left", padx=(0, 4))
        debrief_btn = ctk.CTkButton(
            self, text="Debrief", width=84, command=callbacks.on_debrief
        )
        debrief_btn.pack(side="left")
        settings_btn = ctk.CTkButton(
            self, text="Settings", width=84, command=callbacks.on_settings
        )
        settings_btn.pack(side="left", padx=(4, 0))

        if callbacks.on_hours_changed is not None:
            mid_entry.bind("<FocusOut>", callbacks.on_hours_changed, add="+")
            end_entry.bind("<FocusOut>", callbacks.on_hours_changed, add="+")
            mid_entry.bind("<Return>", callbacks.on_hours_changed, add="+")
            end_entry.bind("<Return>", callbacks.on_hours_changed, add="+")

        self.widgets = SessionControlsWidgets(
            mid_entry=mid_entry,
            end_entry=end_entry,
            start_button=start_btn,
            end_button=end_btn,
            capture_button=capture_btn,
            debrief_button=debrief_btn,
            settings_button=settings_btn,
        )
        self.set_enabled(
            enabled=enabled, scenario_actions_enabled=scenario_actions_enabled
        )

    def set_enabled(
        self, *, enabled: bool = True, scenario_actions_enabled: bool = True
    ) -> None:
        """Enable or disable the whole strip and scenario-specific actions."""
        base_state = "normal" if enabled else "disabled"
        scenario_state = (
            "normal" if enabled and scenario_actions_enabled else "disabled"
        )
        for widget in (
            self.widgets.mid_entry,
            self.widgets.end_entry,
            self.widgets.start_button,
        ):
            widget.configure(state=base_state)
        self.widgets.end_button.configure(state=scenario_state)
        self.widgets.capture_button.configure(state=scenario_state)
        self.widgets.debrief_button.configure(state=scenario_state)
        self.widgets.settings_button.configure(state=base_state)
