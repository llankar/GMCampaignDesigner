"""Compact always-on-top audio controller widget."""

from __future__ import annotations

import os
import tkinter as tk
from typing import Any, Dict, Optional

import customtkinter as ctk

from modules.audio.audio_constants import DEFAULT_SECTION, SECTION_TITLES
from modules.audio.audio_controller import AudioController, get_audio_controller
from modules.helpers.logging_helper import log_exception, log_module_import

log_module_import(__name__)


class AudioBarWindow(ctk.CTkToplevel):
    """Light-weight controller that mirrors the shared audio state."""

    _NO_TRACKS_TEXT = "No tracks available"

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        controller: Optional[AudioController] = None,
    ) -> None:
        super().__init__(master)
        self.controller = controller or get_audio_controller()
        self._listener: Optional[Any] = None

        self._section_order = list(SECTION_TITLES.keys()) or [DEFAULT_SECTION]
        default_section = (
            DEFAULT_SECTION
            if DEFAULT_SECTION in SECTION_TITLES
            else self._section_order[0]
        )
        self._active_section: str = default_section
        self._section_key_to_display = {k: v for k, v in SECTION_TITLES.items()}
        self._bar_height = 80
        self._updating_selector = False

        self._playlist_cache: Dict[str, list[Dict[str, Any]]] = {
            section: [] for section in self._section_order
        }
        self._track_lookup_by_section: Dict[str, Dict[str, Dict[str, Any]]] = {
            section: {} for section in self._section_order
        }
        self._selected_track_display_by_section: Dict[str, str] = {
            section: self._NO_TRACKS_TEXT for section in self._section_order
        }
        self._selected_track_info_by_section: Dict[str, Optional[Dict[str, Any]]] = {
            section: None for section in self._section_order
        }

        self.track_selector_var = tk.StringVar(value=self._NO_TRACKS_TEXT)
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
        self._apply_window_style()
        self._register_controller_listener()
        self._refresh_from_state()

        self.bind("<Destroy>", self._on_destroy_event)
        self.bind("<Escape>", lambda _event: self._on_close())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._building_ui = True
        self.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(self, corner_radius=0)
        bar.grid(row=0, column=0, sticky="nsew", padx=10, pady=6)
        bar.grid_columnconfigure(1, weight=3)
        bar.grid_columnconfigure(10, weight=2)
        bar.grid_columnconfigure(12, weight=2)

        self.section_button = ctk.CTkButton(
            bar,
            text=self._section_key_to_display.get(self._active_section, self._active_section.title()),
            command=self._on_section_button_clicked,
            width=110,
        )
        self.section_button.grid(row=0, column=0, padx=(4, 8), pady=4, sticky="w")

        self.track_selector = ctk.CTkOptionMenu(
            bar,
            values=[self._NO_TRACKS_TEXT],
            variable=self.track_selector_var,
            command=self._on_track_selected,
            width=360,
        )
        self.track_selector.grid(row=0, column=1, padx=(0, 8), pady=4, sticky="ew")

        button_kwargs = {"width": 68, "height": 32}
        self.prev_button = ctk.CTkButton(
            bar, text="Prev", command=self._on_prev_clicked, **button_kwargs
        )
        self.prev_button.grid(row=0, column=2, padx=4, pady=4)

        self.play_button = ctk.CTkButton(
            bar, text="Play", command=self._on_play_clicked, **button_kwargs
        )
        self.play_button.grid(row=0, column=3, padx=4, pady=4)

        self.pause_button = ctk.CTkButton(
            bar, text="Pause", command=self._on_pause_clicked, **button_kwargs
        )
        self.pause_button.grid(row=0, column=4, padx=4, pady=4)

        self.stop_button = ctk.CTkButton(
            bar, text="Stop", command=self._on_stop_clicked, **button_kwargs
        )
        self.stop_button.grid(row=0, column=5, padx=4, pady=4)

        self.next_button = ctk.CTkButton(
            bar, text="Next", command=self._on_next_clicked, **button_kwargs
        )
        self.next_button.grid(row=0, column=6, padx=4, pady=4)

        self.shuffle_checkbox = ctk.CTkCheckBox(
            bar,
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
        self.shuffle_checkbox.grid(row=0, column=7, padx=6, pady=4, sticky="w")

        self.loop_checkbox = ctk.CTkCheckBox(
            bar,
        self.shuffle_checkbox.grid(row=0, column=0, padx=4, pady=4, sticky="w")

        self.loop_checkbox = ctk.CTkCheckBox(
            toggles,
            text="Loop",
            variable=self.loop_var,
            command=self._on_loop_toggle,
        )
        self.loop_checkbox.grid(row=0, column=8, padx=(6, 4), pady=4, sticky="w")

        ctk.CTkLabel(bar, text="Vol").grid(row=0, column=9, padx=(8, 2), pady=4, sticky="w")
        self.volume_slider = ctk.CTkSlider(
            bar,
            from_=0,
            to=100,
            command=self._on_volume_changed,
            width=220,
        )
        self.volume_slider.grid(row=0, column=10, padx=4, pady=4, sticky="ew")

        self.volume_value_label = ctk.CTkLabel(
            bar, textvariable=self.volume_value_var, width=60, anchor="e"
        )
        self.volume_value_label.grid(row=0, column=11, padx=(4, 8), pady=4, sticky="e")

        self.status_label = ctk.CTkLabel(
            bar, textvariable=self.status_var, anchor="w"
        )
        self.status_label.grid(row=0, column=12, padx=(4, 8), pady=4, sticky="ew")

        self._building_ui = False

    def _apply_window_style(self) -> None:
        self.overrideredirect(True)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(0, self._position_window)

    def _position_window(self) -> None:
        try:
            self.update_idletasks()
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            height = self._bar_height
            width = max(320, screen_width)
            x = 0
            y = max(0, screen_height - height)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

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
        self._listener = (
            lambda section, event, payload: self._dispatch_controller_event(
                section, event, payload
            )
        )
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
        if event in {"track_started", "state_changed", "stopped", "playlist_ended", "playlist_set"}:
            self._refresh_from_state(section)
            if section == self._active_section and event == "playlist_ended":
                self.status_var.set("Playlist finished")
            return

        if section != self._active_section:
            return

        if event == "volume_changed":
            self._apply_volume(payload.get("value"))
        elif event == "shuffle_changed":
            self.shuffle_var.set(bool(payload.get("value")))
        elif event == "loop_changed":
            self.loop_var.set(bool(payload.get("value")))
        elif event == "error":
            message = payload.get("message") or "Playback failed."
            self.status_var.set(f"Error: {message}")
        elif event in {"play_failed", "navigation_failed"}:
            message = payload.get("message") or self.controller.get_last_error(section)
            if message:
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
    def _on_section_button_clicked(self) -> None:
        if not self._section_order:
            return
        try:
            current_index = self._section_order.index(self._active_section)
        except ValueError:
            current_index = 0
        next_index = (current_index + 1) % len(self._section_order)
        next_section = self._section_order[next_index]
        self._active_section = next_section
        self.section_button.configure(
            text=self._section_key_to_display.get(next_section, next_section.title())
        )
        self._refresh_from_state(next_section)

    def _on_track_selected(self, display_value: str) -> None:
        if self._updating_selector:
            return
        lookup = self._track_lookup_by_section.get(self._active_section, {})
        info = lookup.get(display_value)
        self._selected_track_display_by_section[self._active_section] = display_value
        self._selected_track_info_by_section[self._active_section] = info

    def _on_play_clicked(self) -> None:
        info = self._selected_track_info_by_section.get(self._active_section)
        track_id = info.get("id") if info else None
        index = info.get("index") if info else None
        if track_id:
            success = self.controller.play(self._active_section, track_id=track_id)
        elif index is not None:
            success = self.controller.play(self._active_section, start_index=index)
        else:
            success = self.controller.play(self._active_section)
        if not success:
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
    def _refresh_from_state(
        self,
        section: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
    ) -> None:
        section = section or self._active_section
        if state is None:
            state = self.controller.get_state(section)
        state = state or {}
        playlist = list(state.get("playlist") or [])
        self._playlist_cache[section] = playlist

        lookup: Dict[str, Dict[str, Any]] = {}
        values: list[str] = []
        for index, track in enumerate(playlist):
            display = self._format_track_display(track, index)
            lookup[display] = {"track": track, "id": track.get("id"), "index": index}
            values.append(display)
        if not values:
            values = [self._NO_TRACKS_TEXT]

        self._track_lookup_by_section[section] = lookup

        selection = self._determine_selected_display(section, state, lookup, values)
        self._selected_track_display_by_section[section] = selection
        self._selected_track_info_by_section[section] = lookup.get(selection)

        if section == self._active_section:
            self._updating_selector = True
            self.track_selector.configure(values=values)
            self.track_selector.set(selection)
            self.track_selector_var.set(selection)
            self._updating_selector = False

            self.shuffle_var.set(bool(state.get("shuffle", False)))
            self.loop_var.set(bool(state.get("loop", False)))
            self._apply_volume(state.get("volume", 0.0))
            self._update_status_from_state(section, state)
            self._update_button_states(state)
        else:
            # Ensure placeholders are kept consistent for inactive sections.
            if selection not in values:
                self._selected_track_display_by_section[section] = values[0]
                self._selected_track_info_by_section[section] = lookup.get(values[0])
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

    def _update_status_from_state(
        self, section: str, state: Optional[Dict[str, Any]] = None
    ) -> None:
        state = state or self.controller.get_state(section) or {}
        if state.get("last_error"):
            self.status_var.set(f"Error: {state['last_error']}")
            return
        if state.get("is_playing"):
            self.status_var.set("Playing")
            return
        if state.get("current_track"):
            self.status_var.set("Paused")
            return
        if state.get("last_track"):
            self.status_var.set("Ready")
            return
        self.status_var.set("Idle")

    def _update_button_states(self, state: Dict[str, Any]) -> None:
        playlist = state.get("playlist") or self._playlist_cache.get(self._active_section, [])
        playing = bool(state.get("is_playing"))
        has_playlist = bool(playlist)
        state_normal = tk.NORMAL if has_playlist else tk.DISABLED

        self.play_button.configure(state=tk.NORMAL if has_playlist else tk.DISABLED)
        self.pause_button.configure(state=tk.NORMAL if playing else tk.DISABLED)
        self.stop_button.configure(state=state_normal)
        self.next_button.configure(state=state_normal)
        self.prev_button.configure(state=state_normal)

    def _determine_selected_display(
        self,
        section: str,
        state: Dict[str, Any],
        lookup: Dict[str, Dict[str, Any]],
        values: list[str],
    ) -> str:
        if not lookup:
            return self._NO_TRACKS_TEXT

        display = self._match_track_display(lookup, state.get("current_track"))
        if display:
            return display

        display = self._match_track_display(lookup, state.get("last_track"))
        if display:
            return display

        stored = self._selected_track_display_by_section.get(section)
        if stored and stored in lookup:
            return stored

        return values[0]

    @staticmethod
    def _match_track_display(
        lookup: Dict[str, Dict[str, Any]], track: Optional[Dict[str, Any]]
    ) -> str:
        if not track:
            return ""
        track_id = track.get("id")
        path = track.get("path")
        name = track.get("name")
        for display, info in lookup.items():
            candidate = info.get("track", {})
            if track_id and candidate.get("id") == track_id:
                return display
            if path and candidate.get("path") == path:
                return display
            if name and candidate.get("name") == name:
                return display
        return ""

    @staticmethod
    def _format_track_display(track: Dict[str, Any], index: int) -> str:
        name = track.get("name")
        if not name:
            path = track.get("path", "")
            name = os.path.basename(path) if path else f"Track {index + 1}"
        return f"{index + 1}. {name}"

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
            self._position_window()
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
