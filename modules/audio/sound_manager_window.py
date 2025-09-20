import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk
from typing import Any

from modules.audio.audio_library import AudioLibrary, AUDIO_EXTENSIONS
from modules.audio.audio_player import AudioPlayer
from modules.helpers.window_helper import position_window_at_top
from modules.helpers.logging_helper import log_exception, log_module_import

log_module_import(__name__)

AUDIO_FILE_TYPES = [
    ("Audio Files", " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS))),
    ("All Files", "*.*"),
]

SECTION_TITLES = {
    "music": "Music",
    "effects": "Sound Effects",
}


class SoundManagerWindow(ctk.CTkToplevel):
    """Utility window for organizing and playing music and sound effects."""

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.title("Sound & Music Manager")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.resizable(True, True)

        self.library = AudioLibrary()
        self.players = {
            "music": AudioPlayer(),
            "effects": AudioPlayer(),
        }
        self.sections: dict[str, dict[str, Any]] = {}

        self._build_ui()
        self._register_player_callbacks()
        position_window_at_top(self, width=1100, height=720)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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
        for idx in range(4):
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
            text="Remove",
            fg_color="#8b1d1d",
            hover_color="#6f1414",
            command=lambda s=section: self._remove_tracks(s),
        ).grid(row=0, column=3, sticky="ew", padx=(6, 0))
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

        shuffle_var = tk.BooleanVar(value=bool(self.library.get_setting(section, "shuffle", False)))
        shuffle_cb = ctk.CTkCheckBox(
            playback_frame,
            text="Shuffle",
            variable=shuffle_var,
            command=lambda s=section: self._toggle_shuffle(s),
        )
        shuffle_cb.grid(row=0, column=4, padx=6, pady=(6, 6))

        loop_var = tk.BooleanVar(value=bool(self.library.get_setting(section, "loop", False)))
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

        volume_value_var = tk.StringVar(value="100%")
        volume_value = ctk.CTkLabel(volume_frame, textvariable=volume_value_var, width=60)
        volume_value.grid(row=0, column=2, sticky="e", padx=(0, 8), pady=(8, 6))

        status_var = tk.StringVar(value="")
        status_label = ctk.CTkLabel(tracks_frame, textvariable=status_var, anchor="w")
        status_label.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 4))

        now_playing_var = tk.StringVar(value="")
        now_playing_label = ctk.CTkLabel(
            tracks_frame,
            textvariable=now_playing_var,
            anchor="w",
            font=("Segoe UI", 12, "italic"),
        )
        now_playing_label.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 12))
        category_list.bind("<<ListboxSelect>>", lambda _evt, s=section: self._on_category_selected(s))
        track_list.bind("<Double-Button-1>", lambda _evt, s=section: self._play_selected(s))

        initial_volume = float(self.library.get_setting(section, "volume", 0.8))
        volume_slider.set(initial_volume * 100)
        volume_value_var.set(f"{int(initial_volume * 100)}%")
        self.players[section].set_volume(initial_volume)
        self.players[section].set_shuffle(shuffle_var.get())
        self.players[section].set_loop(loop_var.get())

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
    def _register_player_callbacks(self) -> None:
        for section, player in self.players.items():
            player.add_listener(lambda event, payload, s=section: self._dispatch_player_event(s, event, payload))

    def show(self) -> None:
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(400, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def _dispatch_player_event(self, section: str, event: str, payload: dict[str, Any]) -> None:
        try:
            self.after(0, self._handle_player_event, section, event, payload)
        except Exception as exc:  # pragma: no cover - defensive
            log_exception(
                f"SoundManagerWindow._dispatch_player_event - failed to schedule event: {exc}",
                func_name="SoundManagerWindow._dispatch_player_event",
            )

    def _handle_player_event(self, section: str, event: str, payload: dict[str, Any]) -> None:
        state = self.sections.get(section)
        if not state:
            return
        if event == "track_started":
            track = payload.get("track") or {}
            name = track.get("name") or os.path.basename(track.get("path", ""))
            state["now_playing_var"].set(f"Now playing: {name}")
            self._highlight_track(section, track.get("id"))
        elif event == "error":
            message = payload.get("message") or "Playback failed."
            state["status_var"].set(f"Error: {message}")
        elif event == "stopped":
            state["now_playing_var"].set("")
        elif event == "playlist_ended":
            state["now_playing_var"].set("Playlist finished")
        elif event == "volume_changed":
            value = payload.get("value", 0.0)
            state["volume_slider"].set(float(value) * 100)
            state["volume_value_var"].set(f"{int(float(value) * 100)}%")

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
        player = self.players[section]
        player.set_playlist(list(tracks))
        if player.play(start_index=index):
            track = tracks[index]
            name = track.get("name") or os.path.basename(track.get("path", ""))
            self._set_status(section, f"Playing '{name}'.")
        else:
            details = player.last_error or "Failed to start playback."
            state["status_var"].set(f"Error: {details}")
            messagebox.showerror("Playback", f"Failed to start playback:\n{details}", parent=self)

    def _next_track(self, section: str) -> None:
        if self.players[section].next():
            self._set_status(section, "Skipped to next track.")
        else:
            self._set_status(section, "No next track available.")

    def _previous_track(self, section: str) -> None:
        if self.players[section].previous():
            self._set_status(section, "Returned to previous track.")
        else:
            self._set_status(section, "No previous track available.")

    def _stop_player(self, section: str) -> None:
        self.players[section].stop()
        self._set_status(section, "Playback stopped.")

    def _toggle_shuffle(self, section: str) -> None:
        state = self._get_state(section)
        value = bool(state["shuffle_var"].get())
        self.players[section].set_shuffle(value)
        self.library.set_setting(section, "shuffle", value)
        self._set_status(section, f"Shuffle {'enabled' if value else 'disabled'}.")

    def _toggle_loop(self, section: str) -> None:
        state = self._get_state(section)
        value = bool(state["loop_var"].get())
        self.players[section].set_loop(value)
        self.library.set_setting(section, "loop", value)
        self._set_status(section, f"Loop {'enabled' if value else 'disabled'}.")

    def _on_volume_change(self, section: str, value: float) -> None:
        state = self._get_state(section)
        normalized = max(0.0, min(float(value) / 100.0, 1.0))
        state["volume_value_var"].set(f"{int(normalized * 100)}%")
        self.players[section].set_volume(normalized)
        self.library.set_setting(section, "volume", normalized)

    def _on_close(self) -> None:
        for player in self.players.values():
            try:
                player.stop()
            except Exception:
                pass
        self.destroy()








