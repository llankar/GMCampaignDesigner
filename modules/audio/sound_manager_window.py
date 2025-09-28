import json
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk
from typing import Any

from modules.ai.local_ai_client import LocalAIClient
from modules.audio.audio_library import AUDIO_EXTENSIONS
from modules.audio.audio_controller import AudioController, get_audio_controller
from modules.audio.audio_constants import SECTION_TITLES
from modules.helpers.window_helper import position_window_at_top
from modules.helpers.logging_helper import log_exception, log_module_import

log_module_import(__name__)

AUDIO_FILE_TYPES = [
    ("Audio Files", " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS))),
    ("All Files", "*.*"),
]

class SoundManagerWindow(ctk.CTkToplevel):
    """Utility window for organizing and playing music and sound effects."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        controller: AudioController | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Sound & Music Manager")
        self.geometry("1200x900")
        self.minsize(1200, 900)
        self.resizable(True, True)

        self.controller = controller or get_audio_controller()
        self.library = self.controller.library
        self.sections: dict[str, dict[str, Any]] = {}
        self._controller_listener: Any | None = None

        self._build_ui()
        self._register_controller_callbacks()
        position_window_at_top(self, width=1100, height=720)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Destroy>", self._on_destroy_event)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)

        for section, title in SECTION_TITLES.items():
            tab = self.tab_view.add(title)
            tab.grid_columnconfigure(1, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            self.sections[section] = self._build_section(tab, section)

        for key in SECTION_TITLES:
            self._refresh_categories(key)

        self.tab_view.set(SECTION_TITLES["music"])

    def _build_section(self, parent: Any, section: str) -> dict[str, Any]:
        container = ctk.CTkFrame(parent)
        container.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        container.grid_columnconfigure(0, weight=0)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(0, weight=1)

        category_frame = ctk.CTkFrame(container)
        category_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        category_frame.grid_rowconfigure(1, weight=1)
        category_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(category_frame, text="Types", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )

        category_list = tk.Listbox(
            category_frame,
            exportselection=False,
            activestyle="none",
            height=14,
        )
        category_list.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))

        cat_scroll = tk.Scrollbar(category_frame, orient="vertical", command=category_list.yview)
        cat_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 8))
        category_list.configure(yscrollcommand=cat_scroll.set)

        directories_var = tk.StringVar(value="")
        directories_label = ctk.CTkLabel(
            category_frame,
            textvariable=directories_var,
            justify="left",
            wraplength=220,
            anchor="w",
        )
        directories_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))

        cat_buttons = ctk.CTkFrame(category_frame)
        cat_buttons.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        cat_buttons.grid_columnconfigure((0, 1), weight=1)

        add_cat_btn = ctk.CTkButton(
            cat_buttons,
            text="Add Type",
            command=lambda s=section: self._add_category(s),
        )
        add_cat_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        rename_cat_btn = ctk.CTkButton(
            cat_buttons,
            text="Rename",
            command=lambda s=section: self._rename_category(s),
        )
        rename_cat_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        remove_cat_btn = ctk.CTkButton(
            cat_buttons,
            text="Remove",
            fg_color="#8b1d1d",
            hover_color="#6f1414",
            command=lambda s=section: self._remove_category(s),
        )
        remove_cat_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        tracks_frame = ctk.CTkFrame(container)
        tracks_frame.grid(row=0, column=1, sticky="nsew")
        tracks_frame.grid_rowconfigure(1, weight=1)
        tracks_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tracks_frame, text="Tracks", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )

        track_list = tk.Listbox(
            tracks_frame,
            exportselection=False,
            activestyle="none",
            height=18,
        )
        track_list.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))

        track_scroll = tk.Scrollbar(tracks_frame, orient="vertical", command=track_list.yview)
        track_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 8))
        track_list.configure(yscrollcommand=track_scroll.set)
        track_buttons = ctk.CTkFrame(tracks_frame)
        track_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        for idx in range(5):
            track_buttons.grid_columnconfigure(idx, weight=1)

        ctk.CTkButton(
            track_buttons,
            text="Add Files",
            command=lambda s=section: self._add_tracks_via_files(s),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            track_buttons,
            text="Add Folder",
            command=lambda s=section: self._add_tracks_via_folder(s),
        ).grid(row=0, column=1, sticky="ew", padx=3)

        ctk.CTkButton(
            track_buttons,
            text="Rescan",
            command=lambda s=section: self._rescan_category(s),
        ).grid(row=0, column=2, sticky="ew", padx=3)

        ctk.CTkButton(
            track_buttons,
            text="AI Sorting",
            command=lambda s=section: self._ai_sort_directory(s),
        ).grid(row=0, column=3, sticky="ew", padx=3)

        ctk.CTkButton(
            track_buttons,
            text="Remove",
            fg_color="#8b1d1d",
            hover_color="#6f1414",
            command=lambda s=section: self._remove_tracks(s),
        ).grid(row=0, column=4, sticky="ew", padx=(6, 0))
        playback_frame = ctk.CTkFrame(tracks_frame)
        playback_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        for idx in range(6):
            playback_frame.grid_columnconfigure(idx, weight=0)
        playback_frame.grid_columnconfigure(6, weight=1)

        prev_btn = ctk.CTkButton(
            playback_frame,
            text="Prev",
            width=70,
            command=lambda s=section: self._previous_track(s),
        )
        prev_btn.grid(row=0, column=0, padx=(0, 6), pady=(6, 6))

        play_btn = ctk.CTkButton(
            playback_frame,
            text="Play",
            width=70,
            command=lambda s=section: self._play_selected(s),
        )
        play_btn.grid(row=0, column=1, padx=6, pady=(6, 6))

        stop_btn = ctk.CTkButton(
            playback_frame,
            text="Stop",
            width=70,
            command=lambda s=section: self._stop_player(s),
        )
        stop_btn.grid(row=0, column=2, padx=6, pady=(6, 6))

        next_btn = ctk.CTkButton(
            playback_frame,
            text="Next",
            width=70,
            command=lambda s=section: self._next_track(s),
        )
        next_btn.grid(row=0, column=3, padx=6, pady=(6, 6))

        controller_state = self.controller.get_state(section)
        shuffle_initial = bool(
            controller_state.get("shuffle") if controller_state else self.library.get_setting(section, "shuffle", False)
        )
        shuffle_var = tk.BooleanVar(value=shuffle_initial)
        shuffle_cb = ctk.CTkCheckBox(
            playback_frame,
            text="Shuffle",
            variable=shuffle_var,
            command=lambda s=section: self._toggle_shuffle(s),
        )
        shuffle_cb.grid(row=0, column=4, padx=6, pady=(6, 6))

        loop_initial = bool(
            controller_state.get("loop") if controller_state else self.library.get_setting(section, "loop", False)
        )
        loop_var = tk.BooleanVar(value=loop_initial)
        loop_cb = ctk.CTkCheckBox(
            playback_frame,
            text="Loop",
            variable=loop_var,
            command=lambda s=section: self._toggle_loop(s),
        )
        loop_cb.grid(row=0, column=5, padx=6, pady=(6, 6))

        volume_frame = ctk.CTkFrame(tracks_frame)
        volume_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        volume_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(volume_frame, text="Volume").grid(row=0, column=0, sticky="w", padx=(8, 8), pady=(8, 6))

        volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0,
            to=100,
            command=lambda value, s=section: self._on_volume_change(s, value),
        )
        volume_slider.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(8, 6))

        volume_initial = float(
            controller_state.get("volume") if controller_state else self.library.get_setting(section, "volume", 0.8)
        )
        volume_slider.set(volume_initial * 100)
        volume_value_var = tk.StringVar(value=f"{int(volume_initial * 100)}%")
        volume_value = ctk.CTkLabel(volume_frame, textvariable=volume_value_var, width=60)
        volume_value.grid(row=0, column=2, sticky="e", padx=(0, 8), pady=(8, 6))

        status_text = ""
        if controller_state:
            track_for_status = controller_state.get("current_track") or {}
            if controller_state.get("last_error"):
                status_text = f"Error: {controller_state.get('last_error')}"
            elif controller_state.get("is_playing") and track_for_status:
                name = track_for_status.get("name") or os.path.basename(track_for_status.get("path", ""))
                status_text = f"Playing '{name}'."
            elif track_for_status:
                status_text = "Playback paused."
        status_var = tk.StringVar(value=status_text)
        status_label = ctk.CTkLabel(tracks_frame, textvariable=status_var, anchor="w")
        status_label.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 4))

        now_playing_text = ""
        if controller_state:
            track = controller_state.get("current_track") or {}
            if controller_state.get("is_playing") and track:
                name = track.get("name") or os.path.basename(track.get("path", ""))
                now_playing_text = f"Now playing: {name}"
            elif track:
                name = track.get("name") or os.path.basename(track.get("path", ""))
                now_playing_text = f"Last track: {name}"
        now_playing_var = tk.StringVar(value=now_playing_text)
        now_playing_label = ctk.CTkLabel(
            tracks_frame,
            textvariable=now_playing_var,
            anchor="w",
            font=("Segoe UI", 12, "italic"),
        )
        now_playing_label.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 12))
        category_list.bind("<<ListboxSelect>>", lambda _evt, s=section: self._on_category_selected(s))
        track_list.bind("<Double-Button-1>", lambda _evt, s=section: self._play_selected(s))

        state: dict[str, Any] = {
            "container": container,
            "category_list": category_list,
            "track_list": track_list,
            "directories_var": directories_var,
            "status_var": status_var,
            "now_playing_var": now_playing_var,
            "shuffle_var": shuffle_var,
            "loop_var": loop_var,
            "volume_slider": volume_slider,
            "volume_value_var": volume_value_var,
            "track_items": [],
            "current_category": None,
        }
        return state
    def _register_controller_callbacks(self) -> None:
        if self._controller_listener is not None:
            return
        self._controller_listener = (
            lambda section, event, payload: self._dispatch_controller_event(section, event, payload)
        )
        self.controller.add_listener(self._controller_listener)

    def _detach_controller_listener(self) -> None:
        if self._controller_listener is None:
            return
        self.controller.remove_listener(self._controller_listener)
        self._controller_listener = None

    def _on_destroy_event(self, event: tk.Event) -> None:  # pragma: no cover - UI callback
        if event.widget is self:
            self._detach_controller_listener()

    def show(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(400, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def _dispatch_controller_event(self, section: str, event: str, payload: dict[str, Any]) -> None:
        try:
            self.after(0, self._handle_controller_event, section, event, payload)
        except Exception as exc:  # pragma: no cover - defensive
            log_exception(
                f"SoundManagerWindow._dispatch_controller_event - failed to schedule event: {exc}",
                func_name="SoundManagerWindow._dispatch_controller_event",
            )

    def _handle_controller_event(self, section: str, event: str, payload: dict[str, Any]) -> None:
        state = self.sections.get(section)
        if not state:
            return
        if event == "track_started":
            track = payload.get("track") or {}
            name = track.get("name") or os.path.basename(track.get("path", ""))
            state["now_playing_var"].set(f"Now playing: {name}")
            self._highlight_track(section, track.get("id"))
            state["status_var"].set(f"Playing '{name}'.")
        elif event == "error":
            message = payload.get("message") or "Playback failed."
            state["status_var"].set(f"Error: {message}")
        elif event == "stopped":
            state["now_playing_var"].set("")
            state["status_var"].set("Playback stopped.")
        elif event == "playlist_ended":
            state["now_playing_var"].set("Playlist finished")
            state["status_var"].set("Playlist finished.")
        elif event == "volume_changed":
            value = payload.get("value", 0.0)
            state["volume_slider"].set(float(value) * 100)
            state["volume_value_var"].set(f"{int(float(value) * 100)}%")
        elif event == "shuffle_changed":
            state["shuffle_var"].set(bool(payload.get("value")))
        elif event == "loop_changed":
            state["loop_var"].set(bool(payload.get("value")))
        elif event == "state_changed":
            data = payload.get("state")
            if isinstance(data, dict):
                self._apply_controller_state(section, data)
        elif event in {"play_failed", "navigation_failed"}:
            message = payload.get("message") or self.controller.get_last_error(section)
            if message:
                state["status_var"].set(f"Error: {message}")

    def _apply_controller_state(self, section: str, data: dict[str, Any]) -> None:
        state = self.sections.get(section)
        if not state:
            return

        if "volume" in data:
            try:
                value = float(data.get("volume", 0.0))
            except (TypeError, ValueError):
                value = 0.0
            state["volume_slider"].set(value * 100)
            state["volume_value_var"].set(f"{int(value * 100)}%")

        if "shuffle" in data:
            state["shuffle_var"].set(bool(data.get("shuffle")))
        if "loop" in data:
            state["loop_var"].set(bool(data.get("loop")))

        category = data.get("category")
        if isinstance(category, str) and category:
            current = state.get("current_category")
            if current != category:
                categories = self.library.get_categories(section)
                if category in categories:
                    index = categories.index(category)
                    listbox = state["category_list"]
                    listbox.select_clear(0, "end")
                    listbox.select_set(index)
                    listbox.see(index)
                    state["current_category"] = category
                    self._refresh_tracks(section)

        track = data.get("current_track") or {}
        last_error = data.get("last_error", "")
        name = track.get("name") or os.path.basename(track.get("path", ""))
        if track:
            if data.get("is_playing"):
                state["now_playing_var"].set(f"Now playing: {name}")
                state["status_var"].set(f"Playing '{name}'.")
            elif not state["now_playing_var"].get():
                state["now_playing_var"].set(f"Last track: {name}")
            self._highlight_track(section, track.get("id"))
        elif not data.get("is_playing"):
            state["now_playing_var"].set("")

        if last_error:
            state["status_var"].set(f"Error: {last_error}")

    def _highlight_track(self, section: str, track_id: str | None) -> None:
        if not track_id:
            return
        state = self.sections.get(section)
        if not state:
            return
        items = state.get("track_items", [])
        try:
            listbox = state["track_list"]
        except KeyError:
            return
        for idx, track in enumerate(items):
            if track.get("id") == track_id:
                listbox.select_clear(0, "end")
                listbox.select_set(idx)
                listbox.see(idx)
                break
    def _get_state(self, section: str) -> dict[str, Any]:
        state = self.sections.get(section)
        if state is None:
            raise KeyError(f"Unknown section '{section}'.")
        return state
    def _refresh_categories(self, section: str) -> None:
        state = self._get_state(section)
        categories = self.library.get_categories(section)
        listbox = state["category_list"]
        listbox.delete(0, "end")
        for name in categories:
            listbox.insert("end", name)

        if not categories:
            state["current_category"] = None
            state["track_items"] = []
            state["track_list"].delete(0, "end")
            state["directories_var"].set("Folders: none")
            state["status_var"].set("No types configured yet.")
            return

        current = state.get("current_category")
        if current in categories:
            index = categories.index(current)
        else:
            index = 0
            current = categories[0]
        listbox.select_set(index)
        listbox.see(index)
        state["current_category"] = current
        self._refresh_tracks(section)

    def _select_category(self, section: str, category: str) -> None:
        state = self._get_state(section)
        categories = self.library.get_categories(section)
        if category not in categories:
            return
        index = categories.index(category)
        listbox = state["category_list"]
        listbox.select_clear(0, "end")
        listbox.select_set(index)
        listbox.see(index)
        state["current_category"] = category
        self._refresh_tracks(section)

    def _refresh_tracks(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        listbox = state["track_list"]
        listbox.delete(0, "end")
        if not category:
            state["track_items"] = []
            state["status_var"].set("Select a type to see tracks.")
            state["directories_var"].set("Folders: none")
            return

        tracks = self.library.list_tracks(section, category)
        state["track_items"] = tracks
        for track in tracks:
            name = track.get("name") or os.path.basename(track.get("path", ""))
            listbox.insert("end", name)

        state["status_var"].set(f"{len(tracks)} track(s) in {category}.")
        directories = self.library.get_directories(section, category)
        self._update_directories_label(state, directories)

    def _update_directories_label(self, state: dict[str, Any], directories: list[str]) -> None:
        if directories:
            formatted = "Folders:\\n" + "\\n".join(f"- {directory}" for directory in directories)
        else:
            formatted = "Folders: none"
        state["directories_var"].set(formatted)

    def _set_status(self, section: str, message: str) -> None:
        state = self._get_state(section)
        state["status_var"].set(message)

    def _get_selected_category(self, section: str) -> str | None:
        state = self._get_state(section)
        selection = state["category_list"].curselection()
        if not selection:
            return None
        return state["category_list"].get(selection[0])

    def _add_category(self, section: str) -> None:
        name = simpledialog.askstring("Add Type", "Enter a name for the new type:", parent=self)
        if not name:
            return
        try:
            self.library.add_category(section, name)
            self._set_status(section, f"Added type '{name}'.")
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
        self._refresh_categories(section)

    def _rename_category(self, section: str) -> None:
        current = self._get_selected_category(section)
        if not current:
            messagebox.showinfo("Rename Type", "Select a type to rename.", parent=self)
            return
        new_name = simpledialog.askstring("Rename Type", "Enter the new name:", initialvalue=current, parent=self)
        if not new_name or new_name == current:
            return
        try:
            self.library.rename_category(section, current, new_name)
            self._set_status(section, f"Renamed '{current}' to '{new_name}'.")
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Error", str(exc), parent=self)
        self._refresh_categories(section)

    def _remove_category(self, section: str) -> None:
        current = self._get_selected_category(section)
        if not current:
            messagebox.showinfo("Remove Type", "Select a type to remove.", parent=self)
            return
        if not messagebox.askyesno("Remove Type", f"Remove '{current}'?", parent=self):
            return
        try:
            self.library.remove_category(section, current)
            self._set_status(section, f"Removed '{current}'.")
        except KeyError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
        self._refresh_categories(section)

    def _on_category_selected(self, section: str) -> None:
        selected = self._get_selected_category(section)
        if not selected:
            return
        state = self._get_state(section)
        state["current_category"] = selected
        self._refresh_tracks(section)

    def _get_initial_dir(self, section: str, category: str | None) -> str:
        last = self.library.get_setting(section, "last_directory", "")
        if isinstance(last, str) and last and os.path.isdir(last):
            return last
        if category:
            directories = self.library.get_directories(section, category)
            if directories:
                return directories[0]
        return os.getcwd()

    def _add_tracks_via_files(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        if not category:
            messagebox.showinfo("Add Files", "Create or select a type first.", parent=self)
            return
        initialdir = self._get_initial_dir(section, category)
        paths = filedialog.askopenfilenames(
            title="Select audio files",
            initialdir=initialdir,
            filetypes=AUDIO_FILE_TYPES,
            parent=self,
        )
        if not paths:
            return
        added = self.library.add_tracks(section, category, paths)
        if added:
            directory = os.path.dirname(added[0]["path"])
            self.library.set_setting(section, "last_directory", directory)
            self._set_status(section, f"Added {len(added)} track(s) to {category}.")
        else:
            self._set_status(section, "No new audio files were added.")
        self._refresh_tracks(section)

    def _add_tracks_via_folder(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        if not category:
            messagebox.showinfo("Add Folder", "Create or select a type first.", parent=self)
            return
        initialdir = self._get_initial_dir(section, category)
        directory = filedialog.askdirectory(
            title="Select folder with audio",
            initialdir=initialdir,
            parent=self,
        )
        if not directory:
            return
        try:
            added = self.library.add_directory(section, category, directory, recursive=True)
            self.library.set_setting(section, "last_directory", directory)
            if added:
                self._set_status(section, f"Added {len(added)} track(s) from folder.")
            else:
                self._set_status(section, "Folder contains no new audio files.")
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
        self._refresh_tracks(section)

    def _remove_tracks(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        if not category:
            messagebox.showinfo("Remove Tracks", "Select a type first.", parent=self)
            return
        selection = state["track_list"].curselection()
        if not selection:
            messagebox.showinfo("Remove Tracks", "Select track(s) to remove.", parent=self)
            return
        if not messagebox.askyesno("Remove Tracks", "Remove selected track(s)?", parent=self):
            return
        removed = 0
        for idx in reversed(selection):
            try:
                track = state["track_items"][idx]
            except IndexError:
                continue
            if self.library.remove_track(section, category, track.get("id", "")):
                removed += 1
        if removed:
            self._set_status(section, f"Removed {removed} track(s) from {category}.")
        else:
            self._set_status(section, "No tracks were removed.")
        self._refresh_tracks(section)

    def _rescan_category(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        if not category:
            messagebox.showinfo("Rescan", "Select a type first.", parent=self)
            return
        try:
            result = self.library.rescan_category(section, category)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        added = len(result.get("added", []))
        removed = len(result.get("removed", []))
        self._set_status(section, f"Rescan complete. Added {added}, removed {removed}.")
        self._refresh_tracks(section)

    def _ai_sort_directory(self, section: str) -> None:
        directory = filedialog.askdirectory(parent=self, title="Select Folder for AI Sorting")
        if not directory:
            return
        audio_files = self._gather_audio_files(directory)
        if not audio_files:
            messagebox.showinfo("AI Sorting", "No audio files found in the selected folder.", parent=self)
            return
        self._set_status(section, "Preparing AI sorting request...")

        thread = threading.Thread(
            target=self._ai_sort_directory_worker,
            args=(section, directory, audio_files),
            daemon=True,
        )
        thread.start()

    def _ai_sort_directory_worker(
        self, section: str, directory: str, audio_files: list[dict[str, str]]
    ) -> None:
        self.after(0, lambda: self._set_status(section, "Contacting local AI for sorting..."))
        try:
            assignments = self._invoke_ai_sort(audio_files)
        except Exception as exc:
            log_exception(
                f"SoundManagerWindow._ai_sort_directory_worker - AI sorting failed: {exc}",
                func_name="SoundManagerWindow._ai_sort_directory_worker",
            )
            self.after(
                0,
                lambda: (
                    messagebox.showerror("AI Sorting Failed", str(exc), parent=self),
                    self._set_status(section, "AI sorting failed."),
                ),
            )
            return

        self.after(
            0,
            lambda: self._apply_ai_sort_results(section, directory, audio_files, assignments),
        )

    def _invoke_ai_sort(self, audio_files: list[dict[str, str]]) -> dict[str, list[str]]:
        client = LocalAIClient()
        payload = [
            {
                "relative_path": entry["relative"],
                "file_name": entry["filename"],
            }
            for entry in audio_files
        ]
        prompt = (
            "You organize tabletop audio assets by analyzing their file names only.\n"
            "Group the provided files into categories that describe their purpose, mood, or use at the table.\n"
            "Return STRICT JSON matching this schema exactly:\n"
            "{\n  \"categories\": [\n    {\n      \"name\": \"Category Name\",\n      \"files\": [\"relative/path.ext\"]\n    }\n  ]\n}\n"
            "Rules:\n"
            "- Every file must appear in exactly one category.\n"
            "- Use the provided relative_path strings verbatim in your output.\n"
            "- If uncertain, create a category named \"Unsorted\".\n"
            "- Do not invent files or extra fields.\n\n"
            f"Files (JSON):\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

        response = client.chat(
            [
                {
                    "role": "system",
                    "content": "Classify audio file names into useful tabletop categories. Respond with strict JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )

        data = LocalAIClient._parse_json_safe(response)
        if not isinstance(data, dict):
            raise RuntimeError("AI response was not a JSON object.")
        categories = data.get("categories")
        if not isinstance(categories, list):
            raise RuntimeError("AI response missing 'categories' list.")

        assignments: dict[str, list[str]] = {}
        for entry in categories:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            files = entry.get("files")
            if not isinstance(name, str):
                continue
            clean_name = name.strip()
            if not clean_name:
                continue
            if not isinstance(files, list):
                continue
            for file_ref in files:
                if not isinstance(file_ref, str):
                    continue
                clean_ref = file_ref.strip()
                if not clean_ref:
                    continue
                assignments.setdefault(clean_name, []).append(clean_ref)

        if not assignments:
            raise RuntimeError("AI response did not provide any file assignments.")
        return assignments

    def _apply_ai_sort_results(
        self,
        section: str,
        directory: str,
        audio_files: list[dict[str, str]],
        assignments: dict[str, list[str]],
    ) -> None:
        path_lookup: dict[str, str] = {}
        all_paths: set[str] = set()
        for entry in audio_files:
            absolute = entry["path"]
            relative = entry["relative"]
            filename = entry["filename"]
            all_paths.add(absolute)
            for key in {
                relative,
                relative.replace("\\", "/"),
                os.path.normpath(relative),
                filename,
            }:
                path_lookup[key.casefold()] = absolute

        category_paths: dict[str, list[str]] = {}
        assigned_paths: set[str] = set()
        for category, files in assignments.items():
            clean_category = category.strip()
            if not clean_category:
                continue
            for reference in files:
                normalized = reference.strip().replace("\\", "/")
                if not normalized:
                    continue
                path = path_lookup.get(normalized.casefold())
                if not path:
                    alt_key = os.path.normpath(reference).casefold()
                    path = path_lookup.get(alt_key)
                if not path:
                    continue
                if path in assigned_paths:
                    continue
                bucket = category_paths.setdefault(clean_category, [])
                if path not in bucket:
                    bucket.append(path)
                    assigned_paths.add(path)

        unassigned = sorted(all_paths - assigned_paths)
        if unassigned:
            unsorted_bucket = category_paths.setdefault("Unsorted", [])
            for path in unassigned:
                if path not in unsorted_bucket:
                    unsorted_bucket.append(path)

        existing_categories = set(self.library.get_categories(section))
        created_categories: list[str] = []
        for category in category_paths:
            if category not in existing_categories:
                try:
                    self.library.add_category(section, category)
                    created_categories.append(category)
                    existing_categories.add(category)
                except ValueError:
                    continue

        added_counts: dict[str, int] = {}
        focus_category: str | None = None
        for category, paths in category_paths.items():
            unique_paths: list[str] = []
            seen: set[str] = set()
            for path in paths:
                normalized = os.path.normpath(path)
                if normalized in seen:
                    continue
                seen.add(normalized)
                unique_paths.append(path)
            if not unique_paths:
                added_counts[category] = 0
                continue
            try:
                added = self.library.add_tracks(section, category, unique_paths)
            except KeyError:
                added_counts[category] = 0
                continue
            added_counts[category] = len(added)
            if added and focus_category is None:
                focus_category = category

        total_added = sum(added_counts.values())
        self.library.set_setting(section, "last_directory", directory)
        self._refresh_categories(section)
        if focus_category:
            self._select_category(section, focus_category)

        details = []
        for category, count in sorted(added_counts.items()):
            details.append(f"{category}: {count} new track(s)")
        if created_categories:
            details.append(f"Created categories: {', '.join(sorted(created_categories))}")
        summary = "\n".join(details) if details else "No assignments were applied."

        if total_added:
            status = f"AI sorting complete. Added {total_added} track(s)."
        else:
            status = "AI sorting complete. No new tracks were added."
        self._set_status(section, status)

        messagebox.showinfo("AI Sorting Complete", summary, parent=self)

    def _gather_audio_files(self, directory: str) -> list[dict[str, str]]:
        collected: list[dict[str, str]] = []
        if not os.path.isdir(directory):
            return collected

        for root, _dirs, files in os.walk(directory):
            for filename in files:
                extension = os.path.splitext(filename)[1].lower()
                if extension not in AUDIO_EXTENSIONS:
                    continue
                absolute = os.path.join(root, filename)
                relative = os.path.relpath(absolute, directory).replace(os.sep, "/")
                collected.append(
                    {
                        "path": absolute,
                        "relative": relative,
                        "filename": filename,
                    }
                )
        collected.sort(key=lambda item: item["relative"].lower())
        return collected

    def _play_selected(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        if not category:
            messagebox.showinfo("Play", "Select a type first.", parent=self)
            return
        tracks = state.get("track_items", [])
        if not tracks:
            messagebox.showinfo("Play", "No tracks available in this type.", parent=self)
            return
        selection = state["track_list"].curselection()
        index = selection[0] if selection else 0
        self.controller.set_playlist(section, list(tracks), category=category)
        if self.controller.play(section, start_index=index):
            track = tracks[index]
            name = track.get("name") or os.path.basename(track.get("path", ""))
            self._set_status(section, f"Playing '{name}'.")
        else:
            details = self.controller.get_last_error(section) or "Failed to start playback."
            state["status_var"].set(f"Error: {details}")
            messagebox.showerror("Playback", f"Failed to start playback:\n{details}", parent=self)

    def _next_track(self, section: str) -> None:
        if self.controller.next(section):
            self._set_status(section, "Skipped to next track.")
        else:
            self._set_status(section, "No next track available.")

    def _previous_track(self, section: str) -> None:
        if self.controller.previous(section):
            self._set_status(section, "Returned to previous track.")
        else:
            self._set_status(section, "No previous track available.")

    def _stop_player(self, section: str) -> None:
        self.controller.stop(section)
        self._set_status(section, "Playback stopped.")

    def _toggle_shuffle(self, section: str) -> None:
        state = self._get_state(section)
        value = bool(state["shuffle_var"].get())
        self.controller.set_shuffle(section, value)
        self._set_status(section, f"Shuffle {'enabled' if value else 'disabled'}.")

    def _toggle_loop(self, section: str) -> None:
        state = self._get_state(section)
        value = bool(state["loop_var"].get())
        self.controller.set_loop(section, value)
        self._set_status(section, f"Loop {'enabled' if value else 'disabled'}.")

    def _on_volume_change(self, section: str, value: float) -> None:
        state = self._get_state(section)
        normalized = max(0.0, min(float(value) / 100.0, 1.0))
        state["volume_value_var"].set(f"{int(normalized * 100)}%")
        self.controller.set_volume(section, normalized)

    def _on_close(self) -> None:
        self._detach_controller_listener()
        self.destroy()








