"""Panel for audio track."""

from __future__ import annotations

import os
import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk


def build_track_panel(parent: Any, *, section: str, controller_state: dict[str, Any] | None, get_setting: Callable[[str, str, Any], Any], on_play: Callable[[str], None], on_stop: Callable[[str], None], on_next: Callable[[str], None], on_previous: Callable[[str], None], on_toggle_shuffle: Callable[[str], None], on_toggle_loop: Callable[[str], None], on_toggle_continue: Callable[[str], None], on_volume_change: Callable[[str, float], None], on_add_files: Callable[[str], None], on_add_folder: Callable[[str], None], on_rescan: Callable[[str], None], on_ai_sort: Callable[[str], None], on_remove_tracks: Callable[[str], None], on_classify_moods: Callable[[str], None]) -> dict[str, Any]:
    """Build track panel."""
    frame = ctk.CTkFrame(parent)
    frame.grid(row=0, column=2, sticky="nsew")
    frame.grid_rowconfigure(1, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(frame, text="Tracks", font=("Segoe UI", 16, "bold")).grid(
        row=0, column=0, sticky="w", padx=8, pady=(8, 4)
    )

    track_list = tk.Listbox(frame, exportselection=False, activestyle="none", height=18)
    track_list.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
    track_list.bind("<Double-Button-1>", lambda _evt, s=section: on_play(s))

    track_scroll = tk.Scrollbar(frame, orient="vertical", command=track_list.yview)
    track_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 8))
    track_list.configure(yscrollcommand=track_scroll.set)

    track_buttons = ctk.CTkFrame(frame)
    track_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
    for idx in range(6):
        track_buttons.grid_columnconfigure(idx, weight=1)

    ctk.CTkButton(track_buttons, text="Add Files", command=lambda s=section: on_add_files(s)).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(track_buttons, text="Add Folder", command=lambda s=section: on_add_folder(s)).grid(row=0, column=1, sticky="ew", padx=3)
    ctk.CTkButton(track_buttons, text="Rescan", command=lambda s=section: on_rescan(s)).grid(row=0, column=2, sticky="ew", padx=3)
    ctk.CTkButton(track_buttons, text="AI Sorting", command=lambda s=section: on_ai_sort(s)).grid(row=0, column=3, sticky="ew", padx=3)
    ctk.CTkButton(track_buttons, text="Remove", fg_color="#8b1d1d", hover_color="#6f1414", command=lambda s=section: on_remove_tracks(s)).grid(row=0, column=4, sticky="ew", padx=3)
    ctk.CTkButton(track_buttons, text="Classify Moods", command=lambda s=section: on_classify_moods(s)).grid(row=0, column=5, sticky="ew", padx=(3, 0))

    playback_frame = ctk.CTkFrame(frame)
    playback_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
    for idx in range(7):
        playback_frame.grid_columnconfigure(idx, weight=0)
    playback_frame.grid_columnconfigure(7, weight=1)

    ctk.CTkButton(playback_frame, text="Prev", width=70, command=lambda s=section: on_previous(s)).grid(row=0, column=0, padx=(0, 6), pady=(6, 6))
    ctk.CTkButton(playback_frame, text="Play", width=70, command=lambda s=section: on_play(s)).grid(row=0, column=1, padx=6, pady=(6, 6))
    ctk.CTkButton(playback_frame, text="Stop", width=70, command=lambda s=section: on_stop(s)).grid(row=0, column=2, padx=6, pady=(6, 6))
    ctk.CTkButton(playback_frame, text="Next", width=70, command=lambda s=section: on_next(s)).grid(row=0, column=3, padx=6, pady=(6, 6))

    shuffle_initial = bool(controller_state.get("shuffle") if controller_state else get_setting(section, "shuffle", False))
    shuffle_var = tk.BooleanVar(value=shuffle_initial)
    ctk.CTkCheckBox(playback_frame, text="Shuffle", variable=shuffle_var, command=lambda s=section: on_toggle_shuffle(s)).grid(row=0, column=4, padx=6, pady=(6, 6))

    loop_initial = bool(controller_state.get("loop") if controller_state else get_setting(section, "loop", False))
    loop_var = tk.BooleanVar(value=loop_initial)
    ctk.CTkCheckBox(playback_frame, text="Loop", variable=loop_var, command=lambda s=section: on_toggle_loop(s)).grid(row=0, column=5, padx=6, pady=(6, 6))

    continue_initial = bool(controller_state.get("continue") if controller_state else get_setting(section, "continue", True))
    continue_var = tk.BooleanVar(value=continue_initial)
    ctk.CTkCheckBox(playback_frame, text="Continue", variable=continue_var, command=lambda s=section: on_toggle_continue(s)).grid(row=0, column=6, padx=6, pady=(6, 6))

    volume_frame = ctk.CTkFrame(frame)
    volume_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
    volume_frame.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(volume_frame, text="Volume").grid(row=0, column=0, sticky="w", padx=(8, 8), pady=(8, 6))
    volume_slider = ctk.CTkSlider(volume_frame, from_=0, to=100, command=lambda value, s=section: on_volume_change(s, value))
    volume_slider.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 6))

    volume_initial = float(controller_state.get("volume") if controller_state else get_setting(section, "volume", 0.8))
    volume_slider.set(volume_initial * 100)
    volume_value_var = tk.StringVar(value=f"{int(volume_initial * 100)}%")
    ctk.CTkLabel(volume_frame, textvariable=volume_value_var, width=60).grid(row=0, column=2, sticky="e", padx=(0, 8), pady=(8, 6))

    status_text = ""
    if controller_state:
        # Continue with this path when controller state is set.
        track_for_status = controller_state.get("current_track") or {}
        if controller_state.get("last_error"):
            status_text = f"Error: {controller_state.get('last_error')}"
        elif controller_state.get("is_playing") and track_for_status:
            # Continue with this path when controller_state.get('is_playing') and track for status is set.
            name = track_for_status.get("name") or os.path.basename(track_for_status.get("path", ""))
            status_text = f"Playing '{name}'."
        elif track_for_status:
            status_text = "Playback paused."

    status_var = tk.StringVar(value=status_text)
    ctk.CTkLabel(frame, textvariable=status_var, anchor="w").grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 4))

    now_playing_text = ""
    if controller_state:
        # Continue with this path when controller state is set.
        track = controller_state.get("current_track") or {}
        if controller_state.get("is_playing") and track:
            # Continue with this path when controller_state.get('is_playing') and track is set.
            name = track.get("name") or os.path.basename(track.get("path", ""))
            now_playing_text = f"Now playing: {name}"
        elif track:
            name = track.get("name") or os.path.basename(track.get("path", ""))
            now_playing_text = f"Last track: {name}"
    now_playing_var = tk.StringVar(value=now_playing_text)
    ctk.CTkLabel(frame, textvariable=now_playing_var, anchor="w", font=("Segoe UI", 12, "italic")).grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 12))

    return {
        "frame": frame,
        "track_list": track_list,
        "status_var": status_var,
        "now_playing_var": now_playing_var,
        "shuffle_var": shuffle_var,
        "loop_var": loop_var,
        "continue_var": continue_var,
        "volume_slider": volume_slider,
        "volume_value_var": volume_value_var,
    }
