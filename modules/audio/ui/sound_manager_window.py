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
from modules.audio.services.music_mood_classifier import NO_MOOD
from modules.audio.ui.category_panel import build_category_panel
from modules.audio.ui.mood_panel import build_mood_panel
from modules.audio.ui.track_panel import build_track_panel
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
        container.grid_columnconfigure(1, weight=0)
        container.grid_columnconfigure(2, weight=1)
        container.grid_rowconfigure(0, weight=1)

        category_panel = build_category_panel(
            container,
            section=section,
            on_select=self._on_category_selected,
            on_add=self._add_category,
            on_rename=self._rename_category,
            on_remove=self._remove_category,
        )
        mood_panel = build_mood_panel(
            container,
            section=section,
            on_select=self._on_mood_selected,
            on_add=self._add_mood,
            on_rename=self._rename_mood,
            on_remove=self._remove_mood,
        )
        track_panel = build_track_panel(
            container,
            section=section,
            controller_state=self.controller.get_state(section),
            get_setting=self.library.get_setting,
            on_play=self._play_selected,
            on_stop=self._stop_player,
            on_next=self._next_track,
            on_previous=self._previous_track,
            on_toggle_shuffle=self._toggle_shuffle,
            on_toggle_loop=self._toggle_loop,
            on_toggle_continue=self._toggle_continue,
            on_volume_change=self._on_volume_change,
            on_add_files=self._add_tracks_via_files,
            on_add_folder=self._add_tracks_via_folder,
            on_rescan=self._rescan_category,
            on_ai_sort=self._ai_sort_directory,
            on_remove_tracks=self._remove_tracks,
            on_classify_moods=self._classify_moods,
        )

        state: dict[str, Any] = {
            "container": container,
            "category_list": category_panel["category_list"],
            "mood_list": mood_panel["mood_list"],
            "track_list": track_panel["track_list"],
            "directories_var": category_panel["directories_var"],
            "status_var": track_panel["status_var"],
            "now_playing_var": track_panel["now_playing_var"],
            "shuffle_var": track_panel["shuffle_var"],
            "loop_var": track_panel["loop_var"],
            "continue_var": track_panel["continue_var"],
            "volume_slider": track_panel["volume_slider"],
            "volume_value_var": track_panel["volume_value_var"],
            "track_items": [],
            "current_category": None,
            "current_mood": None,
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
        elif event == "continue_changed":
            state["continue_var"].set(bool(payload.get("value")))
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
        if "continue" in data:
            state["continue_var"].set(bool(data.get("continue")))

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
                    state["current_mood"] = None
                    self._refresh_moods(section)

        track = data.get("current_track") or {}
        last_error = data.get("last_error", "")
        if track:
            track_mood = str(track.get("mood", "")).strip()
            if track_mood and track_mood != state.get("current_mood"):
                state["current_mood"] = track_mood
                self._refresh_moods(section)
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
            state["current_mood"] = None
            state["mood_list"].delete(0, "end")
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
        self._refresh_moods(section)

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
        self._refresh_moods(section)

    def _refresh_moods(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        mood_list = state["mood_list"]
        mood_list.delete(0, "end")
        if not category:
            state["current_mood"] = None
            state["track_items"] = []
            state["track_list"].delete(0, "end")
            state["status_var"].set("Sélectionne une catégorie puis un mood.")
            return

        moods = self.library.get_moods(section, category)
        for mood in moods:
            mood_list.insert("end", mood)

        if not moods:
            state["current_mood"] = None
            state["track_items"] = []
            state["track_list"].delete(0, "end")
            state["status_var"].set("Aucun mood disponible. Ajoute un mood pour cette catégorie.")
            self._update_directories_label(state, self.library.get_directories(section, category))
            return

        current_mood = state.get("current_mood")
        if current_mood in moods:
            index = moods.index(current_mood)
        else:
            index = 0
            current_mood = moods[0]
        mood_list.select_set(index)
        mood_list.see(index)
        state["current_mood"] = current_mood
        self._refresh_tracks(section)

    def _refresh_tracks(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        mood = state.get("current_mood")
        listbox = state["track_list"]
        listbox.delete(0, "end")
        if not category:
            state["track_items"] = []
            state["status_var"].set("Sélectionne une catégorie puis un mood.")
            state["directories_var"].set("Folders: none")
            return
        if not mood:
            state["track_items"] = []
            state["status_var"].set("Sélectionne une catégorie puis un mood.")
            self._update_directories_label(state, self.library.get_directories(section, category))
            return

        tracks = self.library.list_tracks(section, category, mood=mood)
        state["track_items"] = tracks
        for track in tracks:
            name = track.get("name") or os.path.basename(track.get("path", ""))
            track_mood = str(track.get("mood", NO_MOOD) or NO_MOOD)
            listbox.insert("end", f"{name} [{track_mood}]")

        state["status_var"].set(f"{len(tracks)} track(s) in {category} / {mood}.")
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

    def _get_selected_mood(self, section: str) -> str | None:
        state = self._get_state(section)
        selection = state["mood_list"].curselection()
        if not selection:
            return None
        return state["mood_list"].get(selection[0])

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
        state["current_mood"] = None
        self._refresh_moods(section)

    def _on_mood_selected(self, section: str) -> None:
        selected = self._get_selected_mood(section)
        if not selected:
            return
        state = self._get_state(section)
        state["current_mood"] = selected
        self._refresh_tracks(section)

    def _add_mood(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        if not category:
            messagebox.showinfo("Add Mood", "Sélectionne une catégorie puis un mood.", parent=self)
            return
        name = simpledialog.askstring("Add Mood", "Enter a name for the new mood:", parent=self)
        if not name:
            return
        self.library.add_mood(section, category, name)
        state["current_mood"] = name.strip()
        self._refresh_moods(section)
        self._set_status(section, f"Added mood '{name.strip()}' in {category}.")

    def _rename_mood(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        if not category:
            messagebox.showinfo("Rename Mood", "Sélectionne une catégorie puis un mood.", parent=self)
            return
        current = self._get_selected_mood(section)
        if not current:
            messagebox.showinfo("Rename Mood", "Sélectionne une catégorie puis un mood.", parent=self)
            return
        new_name = simpledialog.askstring("Rename Mood", "Enter the new mood name:", initialvalue=current, parent=self)
        if not new_name or new_name == current:
            return
        try:
            self.library.rename_mood(section, category, current, new_name)
            state["current_mood"] = new_name.strip()
            self._set_status(section, f"Renamed mood '{current}' to '{new_name.strip()}'.")
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Error", str(exc), parent=self)
        self._refresh_moods(section)

    def _remove_mood(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        if not category:
            messagebox.showinfo("Remove Mood", "Sélectionne une catégorie puis un mood.", parent=self)
            return
        current = self._get_selected_mood(section)
        if not current:
            messagebox.showinfo("Remove Mood", "Sélectionne une catégorie puis un mood.", parent=self)
            return
        if not messagebox.askyesno("Remove Mood", f"Remove mood '{current}' from '{category}'?", parent=self):
            return
        try:
            self.library.remove_mood(section, category, current)
            state["current_mood"] = None
            self._set_status(section, f"Removed mood '{current}' from {category}.")
        except KeyError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
        self._refresh_moods(section)

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
            messagebox.showinfo("Add Files", "Sélectionne une catégorie puis un mood.", parent=self)
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
        self._refresh_moods(section)

    def _add_tracks_via_folder(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        if not category:
            messagebox.showinfo("Add Folder", "Sélectionne une catégorie puis un mood.", parent=self)
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
        self._refresh_moods(section)

    def _remove_tracks(self, section: str) -> None:
        state = self._get_state(section)
        category = state.get("current_category")
        mood = state.get("current_mood")
        if not category or not mood:
            messagebox.showinfo("Remove Tracks", "Sélectionne une catégorie puis un mood.", parent=self)
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
            messagebox.showinfo("Rescan", "Sélectionne une catégorie puis un mood.", parent=self)
            return
        try:
            result = self.library.rescan_category(section, category)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        added = len(result.get("added", []))
        removed = len(result.get("removed", []))
        self._set_status(section, f"Rescan complete. Added {added}, removed {removed}.")
        self._refresh_moods(section)

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
        mood = state.get("current_mood")
        if not category or not mood:
            messagebox.showinfo("Play", "Sélectionne une catégorie puis un mood.", parent=self)
            return
        tracks = state.get("track_items", [])
        if not tracks:
            messagebox.showinfo("Play", "Aucune track disponible pour cette catégorie et ce mood.", parent=self)
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

    def _classify_moods(self, section: str) -> None:
        if section != "music":
            messagebox.showinfo("Classify Moods", "Mood classification is available for music only.", parent=self)
            return
        result = self.library.classify_section_moods(section)
        updated = int(result.get("updated", 0))
        self._refresh_categories(section)
        if updated:
            self._set_status(section, f"Mood classification complete ({updated} track(s) updated).")
        else:
            self._set_status(section, "Mood classification complete (no changes).")

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

    def _toggle_continue(self, section: str) -> None:
        state = self._get_state(section)
        value = bool(state["continue_var"].get())
        self.controller.set_continue(section, value)
        self._set_status(section, f"Continue {'enabled' if value else 'disabled'}.")

    def _on_volume_change(self, section: str, value: float) -> None:
        state = self._get_state(section)
        normalized = max(0.0, min(float(value) / 100.0, 1.0))
        state["volume_value_var"].set(f"{int(normalized * 100)}%")
        self.controller.set_volume(section, normalized)

    def _on_close(self) -> None:
        self._detach_controller_listener()
        self.destroy()
