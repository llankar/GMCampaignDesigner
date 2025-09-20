"""Compact always-on-top audio controller widget."""

from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, Optional

import customtkinter as ctk

from modules.audio.audio_constants import DEFAULT_SECTION, SECTION_TITLES
from modules.audio.audio_controller import AudioController, get_audio_controller
from modules.helpers.logging_helper import log_exception, log_module_import

log_module_import(__name__)


class AudioBarWindow(ctk.CTkToplevel):
    """Light-weight controller that mirrors the shared audio state."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        controller: Optional[AudioController] = None,
    ) -> None:
        super().__init__(master)
        self.controller = controller or get_audio_controller()
        self._listener: Optional[Any] = None
        self._active_section: str = DEFAULT_SECTION if DEFAULT_SECTION in SECTION_TITLES else next(iter(SECTION_TITLES))

        self.title("Audio Controls")
        self.geometry("520x220")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._section_display_to_key = {v: k for k, v in SECTION_TITLES.items()}
        self._section_key_to_display = {k: v for k, v in SECTION_TITLES.items()}
        default_display = self._section_key_to_display.get(self._active_section, "")

        self.section_display_var = tk.StringVar(value=default_display)
        self.now_playing_var = tk.StringVar(value="No track playing")
        self.category_var = tk.StringVar(value="Category: none")
        self.status_var = tk.StringVar(value="Idle")
        self.shuffle_var = tk.BooleanVar(value=False)
        self.loop_var = tk.BooleanVar(value=False)
        self.volume_value_var = tk.StringVar(value="0%")

        self._building_ui = False
        self._build_ui()
        self._register_controller_listener()
        self._refresh_from_state()

        self.bind("<Destroy>", self._on_destroy_event)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._building_ui = True
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="Section:").grid(row=0, column=0, padx=(4, 8), pady=4, sticky="w")
        self.section_selector = ctk.CTkOptionMenu(
            header,
            values=list(self._section_display_to_key.keys()),
            variable=self.section_display_var,
            command=self._on_section_selected,
            width=220,
        )
        self.section_selector.grid(row=0, column=1, padx=(0, 4), pady=4, sticky="ew")

        controls = ctk.CTkFrame(self)
        controls.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))
        for column in range(5):
            controls.grid_columnconfigure(column, weight=1)

        self.prev_button = ctk.CTkButton(controls, text="Prev", command=self._on_prev_clicked)
        self.prev_button.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        self.play_button = ctk.CTkButton(controls, text="Play", command=self._on_play_clicked)
        self.play_button.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.pause_button = ctk.CTkButton(controls, text="Pause", command=self._on_pause_clicked)
        self.pause_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        self.stop_button = ctk.CTkButton(controls, text="Stop", command=self._on_stop_clicked)
        self.stop_button.grid(row=0, column=3, padx=4, pady=4, sticky="ew")

        self.next_button = ctk.CTkButton(controls, text="Next", command=self._on_next_clicked)
        self.next_button.grid(row=0, column=4, padx=4, pady=4, sticky="ew")

        toggles = ctk.CTkFrame(self)
        toggles.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 4))
        toggles.grid_columnconfigure(0, weight=1)
        toggles.grid_columnconfigure(1, weight=1)

        self.shuffle_checkbox = ctk.CTkCheckBox(
            toggles,
            text="Shuffle",
            variable=self.shuffle_var,
            command=self._on_shuffle_toggle,
        )
        self.shuffle_checkbox.grid(row=0, column=0, padx=4, pady=4, sticky="w")

        self.loop_checkbox = ctk.CTkCheckBox(
            toggles,
            text="Loop",
            variable=self.loop_var,
            command=self._on_loop_toggle,
        )
        self.loop_checkbox.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        volume_frame = ctk.CTkFrame(self)
        volume_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 4))
        volume_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(volume_frame, text="Volume").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0,
            to=100,
            command=self._on_volume_changed,
        )
        self.volume_slider.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        self.volume_value_label = ctk.CTkLabel(volume_frame, textvariable=self.volume_value_var, width=60)
        self.volume_value_label.grid(row=0, column=2, padx=4, pady=4, sticky="e")

        info = ctk.CTkFrame(self)
        info.grid(row=4, column=0, sticky="ew", padx=12, pady=(4, 12))
        info.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(info, textvariable=self.now_playing_var, anchor="w", justify="left").grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 2),
        )
        ctk.CTkLabel(info, textvariable=self.category_var, anchor="w").grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(0, 2),
        )
        ctk.CTkLabel(info, textvariable=self.status_var, anchor="w").grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(0, 2),
        )

        self._building_ui = False

    # ------------------------------------------------------------------
    # Controller listener handling
    # ------------------------------------------------------------------
    def _register_controller_listener(self) -> None:
        if self._listener is not None:
            return
        self._listener = lambda section, event, payload: self._dispatch_controller_event(section, event, payload)
        self.controller.add_listener(self._listener)

    def _detach_controller_listener(self) -> None:
        if self._listener is None:
            return
        self.controller.remove_listener(self._listener)
        self._listener = None

    def _dispatch_controller_event(self, section: str, event: str, payload: Dict[str, Any]) -> None:
        try:
            self.after(0, self._handle_controller_event, section, event, payload)
        except Exception as exc:  # pragma: no cover - defensive
            log_exception(
                f"AudioBarWindow._dispatch_controller_event - failed to schedule event: {exc}",
                func_name="AudioBarWindow._dispatch_controller_event",
            )

    def _handle_controller_event(self, section: str, event: str, payload: Dict[str, Any]) -> None:
        if section != self._active_section:
            return

        if event in {"track_started", "state_changed"}:
            self._refresh_from_state(section)
            self._update_status_from_state(section)
        elif event == "stopped":
            self._refresh_from_state(section)
            self.status_var.set("Stopped")
        elif event == "playlist_ended":
            self._refresh_from_state(section)
            self.status_var.set("Playlist finished")
        elif event == "volume_changed":
            if section == self._active_section:
                self._apply_volume(payload.get("value"))
        elif event == "shuffle_changed":
            if section == self._active_section:
                self.shuffle_var.set(bool(payload.get("value")))
        elif event == "loop_changed":
            if section == self._active_section:
                self.loop_var.set(bool(payload.get("value")))
        elif event == "error":
            message = payload.get("message") or "Playback failed."
            if section == self._active_section:
                self.status_var.set(f"Error: {message}")
        elif event in {"play_failed", "navigation_failed"}:
            message = payload.get("message") or self.controller.get_last_error(section)
            if section == self._active_section and message:
                self.status_var.set(f"Error: {message}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_section_selected(self, display_value: str) -> None:
        section = self._section_display_to_key.get(display_value, self._active_section)
        self._active_section = section
        self.section_display_var.set(self._section_key_to_display.get(section, display_value))
        self._refresh_from_state(section)

    def _on_play_clicked(self) -> None:
        if not self.controller.play(self._active_section):
            self._update_status_from_state(self._active_section)

    def _on_pause_clicked(self) -> None:
        self.controller.pause(self._active_section)
        self.status_var.set("Paused")

    def _on_stop_clicked(self) -> None:
        self.controller.stop(self._active_section)
        self.status_var.set("Stopped")

    def _on_next_clicked(self) -> None:
        if not self.controller.next(self._active_section):
            self._update_status_from_state(self._active_section)

    def _on_prev_clicked(self) -> None:
        if not self.controller.previous(self._active_section):
            self._update_status_from_state(self._active_section)

    def _on_shuffle_toggle(self) -> None:
        value = bool(self.shuffle_var.get())
        self.controller.set_shuffle(self._active_section, value)

    def _on_loop_toggle(self) -> None:
        value = bool(self.loop_var.get())
        self.controller.set_loop(self._active_section, value)

    def _on_volume_changed(self, value: float) -> None:
        normalized = max(0.0, min(float(value) / 100.0, 1.0))
        self.volume_value_var.set(f"{int(normalized * 100)}%")
        self.controller.set_volume(self._active_section, normalized)

    # ------------------------------------------------------------------
    # State synchronisation helpers
    # ------------------------------------------------------------------
    def _refresh_from_state(self, section: Optional[str] = None) -> None:
        section = section or self._active_section
        state = self.controller.get_state(section)
        if not state:
            self.now_playing_var.set("No track playing")
            self.category_var.set("Category: none")
            self.status_var.set("Idle")
            self.shuffle_var.set(False)
            self.loop_var.set(False)
            self._apply_volume(0.0)
            return

        track = state.get("current_track") or {}
        name = track.get("name") or track.get("path") or "No track playing"
        if state.get("is_playing"):
            self.now_playing_var.set(f"Now playing: {name}")
        elif track:
            self.now_playing_var.set(f"Last track: {name}")
        else:
            self.now_playing_var.set("No track playing")

        category = state.get("category") or "none"
        self.category_var.set(f"Category: {category}")
        self.shuffle_var.set(bool(state.get("shuffle", False)))
        self.loop_var.set(bool(state.get("loop", False)))
        self._apply_volume(state.get("volume", 0.0))
        self._update_status_from_state(section)
        self._update_button_states(state)

    def _apply_volume(self, value: Any) -> None:
        try:
            normalized = max(0.0, min(float(value), 1.0))
        except (TypeError, ValueError):
            normalized = 0.0
        if not self._building_ui:
            self.volume_slider.set(normalized * 100)
        self.volume_value_var.set(f"{int(normalized * 100)}%")

    def _update_status_from_state(self, section: str) -> None:
        state = self.controller.get_state(section)
        if not state:
            self.status_var.set("Idle")
            return
        if state.get("last_error"):
            self.status_var.set(f"Error: {state['last_error']}")
            return
        if state.get("is_playing"):
            self.status_var.set("Playing")
        elif state.get("current_track"):
            self.status_var.set("Paused")
        else:
            self.status_var.set("Idle")

    def _update_button_states(self, state: Dict[str, Any]) -> None:
        playing = bool(state.get("is_playing"))
        playlist = state.get("playlist") or []
        state_normal = tk.NORMAL if playlist else tk.DISABLED

        self.play_button.configure(state=tk.NORMAL if playlist else tk.DISABLED)
        self.pause_button.configure(state=tk.NORMAL if playing else tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL if playlist else tk.DISABLED)
        self.next_button.configure(state=state_normal)
        self.prev_button.configure(state=state_normal)

    # ------------------------------------------------------------------
    # Window helpers
    # ------------------------------------------------------------------
    def show(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
        except Exception:
            pass

    def _on_destroy_event(self, event: tk.Event) -> None:  # pragma: no cover - UI callback
        if event.widget is self:
            self._detach_controller_listener()

    def _on_close(self) -> None:
        self._detach_controller_listener()
        self.destroy()

