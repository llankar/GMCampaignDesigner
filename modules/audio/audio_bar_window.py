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

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        controller: Optional[AudioController] = None,
    ) -> None:
        super().__init__(master)
        self.controller = controller or get_audio_controller()
        self._listener: Optional[Any] = None
        self._active_section: str = (
            DEFAULT_SECTION if DEFAULT_SECTION in SECTION_TITLES else next(iter(SECTION_TITLES))
        )
        self._section_cycle: tuple[str, ...] = tuple(SECTION_TITLES.keys())
        self._playlist_lookup: Dict[str, Dict[str, Any]] = {}
        self._selected_track_key: Optional[str] = None

        self.overrideredirect(True)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda _event: self._on_close())

        self.section_toggle_var = tk.StringVar(value=self._section_button_label(self._active_section))
        self.now_playing_var = tk.StringVar(value="No tracks available")
        self.status_var = tk.StringVar(value="Status: Idle")
        self.shuffle_var = tk.BooleanVar(value=False)
        self.loop_var = tk.BooleanVar(value=False)
        self.volume_value_var = tk.StringVar(value="0%")

        self._bar_frame: Optional[ctk.CTkFrame] = None
        self._content_frame: Optional[ctk.CTkFrame] = None
        self._content_grid_options: Optional[Dict[str, Any]] = None
        self._collapse_button: Optional[ctk.CTkButton] = None
        self._is_collapsed = False
        self._remembered_track_label: Optional[str] = None
        self._building_ui = False
        self._build_ui()
        self._register_controller_listener()
        self._refresh_from_state()
        self.after(0, self._apply_geometry)

        self.bind("<Destroy>", self._on_destroy_event)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._building_ui = True
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(self, corner_radius=0)
        bar.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        bar.grid_columnconfigure(0, weight=0)
        bar.grid_columnconfigure(1, weight=1)
        self._bar_frame = bar

        self._collapse_button = ctk.CTkButton(
            bar,
            text="◀",
            width=32,
            command=self._toggle_collapsed,
        )
        self._collapse_button.grid(row=0, column=0, padx=(4, 6), pady=4, sticky="nsw")

        content = ctk.CTkFrame(bar, corner_radius=0)
        self._content_grid_options = {"row": 0, "column": 1, "padx": 0, "pady": 0, "sticky": "nsew"}
        content.grid(**self._content_grid_options)
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=2)
        content.grid_columnconfigure(10, weight=3)
        content.grid_columnconfigure(12, weight=2)
        self._content_frame = content

        self.section_toggle_button = ctk.CTkButton(
            content,
            textvariable=self.section_toggle_var,
            command=self._toggle_section,
            width=110,
        )
        self.section_toggle_button.grid(row=0, column=0, padx=(4, 8), pady=4, sticky="ew")

        self.now_playing_menu = ctk.CTkOptionMenu(
            content,
            variable=self.now_playing_var,
            values=["No tracks available"],
            command=self._on_track_selected,
            width=320,
        )
        self.now_playing_menu.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        self.now_playing_menu.configure(state="disabled")

        self.prev_button = ctk.CTkButton(content, text="Prev", command=self._on_prev_clicked, width=70)
        self.prev_button.grid(row=0, column=2, padx=4, pady=4, sticky="ew")

        self.play_button = ctk.CTkButton(content, text="Play", command=self._on_play_clicked, width=70)
        self.play_button.grid(row=0, column=3, padx=4, pady=4, sticky="ew")

        self.pause_button = ctk.CTkButton(content, text="Pause", command=self._on_pause_clicked, width=70)
        self.pause_button.grid(row=0, column=4, padx=4, pady=4, sticky="ew")

        self.stop_button = ctk.CTkButton(content, text="Stop", command=self._on_stop_clicked, width=70)
        self.stop_button.grid(row=0, column=5, padx=4, pady=4, sticky="ew")

        self.next_button = ctk.CTkButton(content, text="Next", command=self._on_next_clicked, width=70)
        self.next_button.grid(row=0, column=6, padx=4, pady=4, sticky="ew")

        self.shuffle_checkbox = ctk.CTkCheckBox(
            content,
            text="Shuffle",
            variable=self.shuffle_var,
            command=self._on_shuffle_toggle,
        )
        self.shuffle_checkbox.grid(row=0, column=7, padx=6, pady=4, sticky="w")

        self.loop_checkbox = ctk.CTkCheckBox(
            content,
            text="Loop",
            variable=self.loop_var,
            command=self._on_loop_toggle,
        )
        self.loop_checkbox.grid(row=0, column=8, padx=6, pady=4, sticky="w")

        volume_label = ctk.CTkLabel(content, text="Volume")
        volume_label.grid(row=0, column=9, padx=(12, 4), pady=4, sticky="e")

        self.volume_slider = ctk.CTkSlider(
            content,
            from_=0,
            to=100,
            command=self._on_volume_changed,
        )
        self.volume_slider.grid(row=0, column=10, padx=4, pady=4, sticky="ew")

        self.volume_value_label = ctk.CTkLabel(content, textvariable=self.volume_value_var, width=60)
        self.volume_value_label.grid(row=0, column=11, padx=(4, 12), pady=4, sticky="e")

        self.status_label = ctk.CTkLabel(content, textvariable=self.status_var, anchor="w")
        self.status_label.grid(row=0, column=12, padx=(8, 4), pady=4, sticky="ew")

        self._building_ui = False
        self._update_collapse_button()

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

        if event in {"track_started", "state_changed", "playlist_set"}:
            self._refresh_from_state(section)
            self._update_status_from_state(section)
        elif event == "stopped":
            self._refresh_from_state(section)
            self.status_var.set("Status: Stopped")
        elif event == "playlist_ended":
            self._refresh_from_state(section)
            self.status_var.set("Status: Playlist finished")
        elif event == "volume_changed":
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
                self.status_var.set(f"Error: {message}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _toggle_section(self) -> None:
        if not self._section_cycle:
            return
        try:
            current_index = self._section_cycle.index(self._active_section)
        except ValueError:
            current_index = 0
        next_index = (current_index + 1) % len(self._section_cycle)
        self._active_section = self._section_cycle[next_index]
        self.section_toggle_var.set(self._section_button_label(self._active_section))
        self._refresh_from_state(self._active_section)

    def _on_track_selected(self, choice: str) -> None:
        if choice not in self._playlist_lookup:
            return
        self._selected_track_key = choice

    def _on_play_clicked(self) -> None:
        info = self._get_selected_track_info()
        if info:
            identifier = info.get("identifier")
            if identifier:
                success = self.controller.play(self._active_section, track_id=identifier)
            else:
                success = self.controller.play(self._active_section, start_index=info.get("index"))
        else:
            success = self.controller.play(self._active_section)
        if not success:
            self._update_status_from_state(self._active_section)

    def _on_pause_clicked(self) -> None:
        self.controller.pause(self._active_section)
        self.status_var.set("Status: Paused")

    def _on_stop_clicked(self) -> None:
        self.controller.stop(self._active_section)
        self.status_var.set("Status: Stopped")

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
        playlist = (state or {}).get("playlist") or []
        self._update_playlist_menu(playlist)

        track = None
        if state:
            track = state.get("current_track") or state.get("last_track")

        if track:
            self._remembered_track_label = self._format_track_label(track) or None
            label = self._find_label_for_track(track)
            if label:
                self._set_selected_track_by_label(label)
            else:
                display = self._remembered_track_label or ""
                if display:
                    self.now_playing_menu.configure(values=[display], state="disabled")
                    self.now_playing_var.set(display)
                else:
                    self.now_playing_var.set("No tracks available")
                self._selected_track_key = None
        elif self._playlist_lookup:
            if self._selected_track_key not in self._playlist_lookup:
                first_label = next(iter(self._playlist_lookup))
                self._set_selected_track_by_label(first_label)
        else:
            if self._remembered_track_label:
                self.now_playing_menu.configure(values=[self._remembered_track_label], state="disabled")
                self.now_playing_var.set(self._remembered_track_label)
            else:
                self.now_playing_var.set("No tracks available")
            self._selected_track_key = None

        self.shuffle_var.set(bool((state or {}).get("shuffle", False)))
        self.loop_var.set(bool((state or {}).get("loop", False)))
        self._apply_volume((state or {}).get("volume", 0.0))
        self._update_status_from_state(section)
        self._update_button_states(state or {})

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
            self.status_var.set("Status: Idle")
            return
        if state.get("last_error"):
            self.status_var.set(f"Error: {state['last_error']}")
            return
        if state.get("is_playing"):
            self.status_var.set("Status: Playing")
        elif state.get("current_track") or state.get("last_track"):
            self.status_var.set("Status: Paused")
        else:
            self.status_var.set("Status: Idle")

    def _update_button_states(self, state: Dict[str, Any]) -> None:
        playing = bool(state.get("is_playing"))
        playlist = state.get("playlist") or []
        has_tracks = bool(playlist)
        multi_track = len(playlist) > 1
        has_remembered = bool(self._remembered_track_label)

        self.play_button.configure(state=tk.NORMAL if has_tracks or has_remembered else tk.DISABLED)
        self.pause_button.configure(state=tk.NORMAL if playing else tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL if has_tracks else tk.DISABLED)
        self.next_button.configure(state=tk.NORMAL if multi_track else tk.DISABLED)
        self.prev_button.configure(state=tk.NORMAL if multi_track else tk.DISABLED)

        if has_tracks:
            self.now_playing_menu.configure(state="normal")
        else:
            self.now_playing_menu.configure(state="disabled")

    def _update_playlist_menu(self, playlist: list[Dict[str, Any]]) -> None:
        self._playlist_lookup = {}
        values: list[str] = []
        for index, track in enumerate(playlist):
            identifier = self._track_identifier(track)
            base_label = self._format_track_label(track) or f"Track {index + 1}"
            label = base_label
            suffix = 2
            while label in self._playlist_lookup:
                label = f"{base_label} ({suffix})"
                suffix += 1
            self._playlist_lookup[label] = {
                "identifier": identifier,
                "index": index,
                "track": track,
            }
            values.append(label)

        if values:
            self.now_playing_menu.configure(values=values)
            if self._selected_track_key in self._playlist_lookup:
                self.now_playing_var.set(self._selected_track_key)
            else:
                self._selected_track_key = values[0]
                self.now_playing_var.set(values[0])
            self.now_playing_menu.configure(state="normal")
        else:
            if self._remembered_track_label:
                self.now_playing_menu.configure(values=[self._remembered_track_label], state="disabled")
                self.now_playing_var.set(self._remembered_track_label)
            else:
                self.now_playing_menu.configure(values=["No tracks available"], state="disabled")
                self.now_playing_var.set("No tracks available")
            self._selected_track_key = None

    def _find_label_for_track(self, track: Dict[str, Any]) -> Optional[str]:
        identifier = self._track_identifier(track)
        for label, info in self._playlist_lookup.items():
            if info.get("identifier") == identifier:
                return label
        return None

    def _set_selected_track_by_label(self, label: str) -> None:
        if label not in self._playlist_lookup:
            return
        self._selected_track_key = label
        self.now_playing_var.set(label)
        self.now_playing_menu.configure(state="normal")

    def _get_selected_track_info(self) -> Optional[Dict[str, Any]]:
        if self._selected_track_key is None:
            return None
        return self._playlist_lookup.get(self._selected_track_key)

    @staticmethod
    def _track_identifier(track: Dict[str, Any]) -> str:
        identifier = track.get("id")
        if identifier:
            return str(identifier)
        path = track.get("path")
        if isinstance(path, str) and path:
            return path
        return ""

    @staticmethod
    def _format_track_label(track: Dict[str, Any]) -> str:
        name = track.get("name")
        if isinstance(name, str) and name:
            return name
        path = track.get("path")
        if isinstance(path, str) and path:
            return os.path.basename(path)
        return ""

    def _section_button_label(self, section: str) -> str:
        if section == "effects":
            return "Sound"
        return SECTION_TITLES.get(section, section.title())

    def _apply_geometry(self) -> None:
        try:
            self.update_idletasks()
            if self._is_collapsed:
                target = self._collapse_button or self
                width = max(80, int(target.winfo_reqwidth() + 16))
                height_source = target
            else:
                width = self.winfo_screenwidth()
                height_source = self._bar_frame or self
            height = max(36, int((height_source.winfo_reqheight() if height_source else 36) + 16))
            y = self.winfo_screenheight() - height
            self.geometry(f"{width}x{height}+0+{max(0, y)}")
        except Exception:
            pass

    def _toggle_collapsed(self) -> None:
        self._set_collapsed(not self._is_collapsed)

    def _set_collapsed(self, collapsed: bool) -> None:
        if collapsed == self._is_collapsed:
            return
        self._is_collapsed = collapsed
        if self._content_frame is not None:
            if collapsed:
                self._content_frame.grid_remove()
            else:
                if self._content_grid_options is not None:
                    self._content_frame.grid(**self._content_grid_options)
                else:
                    self._content_frame.grid(row=0, column=1, padx=0, pady=0, sticky="nsew")
        self._update_collapse_button()
        self._apply_geometry()

    def _update_collapse_button(self) -> None:
        if not self._collapse_button:
            return
        if self._is_collapsed:
            self._collapse_button.configure(text="▶")
        else:
            self._collapse_button.configure(text="◀")

    # ------------------------------------------------------------------
    # Window helpers
    # ------------------------------------------------------------------
    def show(self) -> None:
        try:
            self.deiconify()
            self._apply_geometry()
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

