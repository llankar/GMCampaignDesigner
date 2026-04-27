"""Ambiance page embedded in GM Table / GM Screen."""

from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from modules.scenarios.gm_table.ambiance.repository import (
    AmbianceMediaRecord,
    AmbianceMediaRepository,
)
from modules.scenarios.gm_table.ambiance.thumbnail_cache import ThumbnailCache
from modules.ui.ambiance.models import AmbianceItem, AmbiancePlaylist
from modules.ui.ambiance.settings import (
    AmbianceSettings,
    load_ambiance_settings,
    update_ambiance_settings,
)


class GMTableAmbiancePage(ctk.CTkFrame):
    """Manage ambiance playlists and control second-screen playback."""

    def __init__(self, master, *, initial_state: dict | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        state = dict(initial_state or {})
        self._repository = AmbianceMediaRepository()
        self._thumbnail_cache = ThumbnailCache()
        self._records: list[AmbianceMediaRecord] = []
        self._restoring_ui_state = True

        settings = load_ambiance_settings()
        preloaded_folder, preloaded_playlist = self._resolve_source_paths(state=state, settings=settings)

        self._folder_var = tk.StringVar(value=preloaded_folder)
        self._playlist_var = tk.StringVar(value=preloaded_playlist)
        self._status_var = tk.StringVar(value="")
        duration_value = state.get("image_duration", settings.default_duration_sec)
        self._duration_var = tk.StringVar(value=str(duration_value if duration_value not in (None, "") else "8"))
        self._loop_var = tk.BooleanVar(value=bool(state.get("loop", settings.loop)))
        self._shuffle_var = tk.BooleanVar(value=bool(state.get("shuffle", settings.shuffle)))
        self._enabled_var = tk.BooleanVar(value=bool(settings.enabled))
        self._transition_var = tk.StringVar(value=settings.transition if settings.transition in {"fade", "cut"} else "fade")
        self._monitor_var = tk.StringVar(value=str(max(0, settings.target_monitor_index)))

        ctk.CTkLabel(
            self,
            text="Ambiance Screen",
            anchor="w",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 6))

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        controls.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(controls, text="Folder", width=78, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(controls, textvariable=self._folder_var, height=30).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ctk.CTkButton(controls, text="Browse", width=86, command=self._pick_folder).grid(row=0, column=2, padx=(0, 4))
        ctk.CTkButton(controls, text="Scan", width=70, command=self._scan_folder).grid(row=0, column=3)

        ctk.CTkLabel(controls, text="Playlist", width=78, anchor="w").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ctk.CTkEntry(controls, textvariable=self._playlist_var, height=30).grid(
            row=1, column=1, sticky="ew", padx=6, pady=(6, 0)
        )
        ctk.CTkButton(controls, text="Load", width=86, command=self._pick_playlist).grid(row=1, column=2, padx=(0, 4), pady=(6, 0))
        ctk.CTkButton(controls, text="Refresh", width=70, command=self._refresh_sources).grid(row=1, column=3, pady=(6, 0))

        options = ctk.CTkFrame(self, fg_color="transparent")
        options.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        options.grid_columnconfigure(8, weight=1)

        ctk.CTkLabel(options, text="Image duration (s)").grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(options, textvariable=self._duration_var, width=88, height=30).grid(row=0, column=1, padx=(6, 16), sticky="w")
        ctk.CTkCheckBox(options, text="Loop", variable=self._loop_var).grid(row=0, column=2, padx=(0, 10))
        ctk.CTkCheckBox(options, text="Shuffle", variable=self._shuffle_var).grid(row=0, column=3, padx=(0, 10))
        ctk.CTkLabel(options, text="Transition").grid(row=0, column=4, padx=(0, 6))
        ctk.CTkOptionMenu(
            options,
            variable=self._transition_var,
            values=["fade", "cut"],
            width=96,
            height=30,
        ).grid(row=0, column=5, padx=(0, 12))
        ctk.CTkLabel(options, text="Monitor").grid(row=0, column=6, padx=(0, 6))
        ctk.CTkEntry(options, textvariable=self._monitor_var, width=52, height=30).grid(row=0, column=7, padx=(0, 12), sticky="w")
        ctk.CTkCheckBox(options, text="Auto resume", variable=self._enabled_var).grid(row=0, column=8, padx=(0, 10))

        ctk.CTkButton(options, text="Start", width=72, command=self._start).grid(row=0, column=9, padx=(0, 6), sticky="e")
        ctk.CTkButton(options, text="Pause", width=72, command=self._pause_or_resume).grid(row=0, column=10, padx=(0, 6), sticky="e")
        ctk.CTkButton(options, text="Stop", width=72, command=self._stop).grid(row=0, column=11, padx=(0, 6), sticky="e")
        ctk.CTkButton(options, text="Next", width=72, command=self._next).grid(row=0, column=12, sticky="e")

        self._list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._list.grid(row=3, column=0, sticky="nsew")

        ctk.CTkLabel(
            self,
            textvariable=self._status_var,
            anchor="w",
            justify="left",
            text_color="#F59E0B",
        ).grid(row=4, column=0, sticky="ew", pady=(6, 0))

        self._bind_persistence_traces()
        self._refresh_sources()
        self._restoring_ui_state = False
        if self._enabled_var.get() and self._records:
            self.after(120, self._start)

    def _resolve_source_paths(self, *, state: dict, settings: AmbianceSettings) -> tuple[str, str]:
        folder_value = str(state.get("folder") or "")
        playlist_value = str(state.get("playlist") or "")
        if folder_value or playlist_value:
            return folder_value, playlist_value

        folder = ""
        playlist = ""
        for raw_path in settings.playlist_paths:
            path = Path(str(raw_path)).expanduser()
            if not playlist and path.is_file():
                playlist = str(path)
            elif not folder and path.is_dir():
                folder = str(path)
        return folder, playlist

    def _bind_persistence_traces(self) -> None:
        for variable in (
            self._folder_var,
            self._playlist_var,
            self._duration_var,
            self._loop_var,
            self._shuffle_var,
            self._enabled_var,
            self._transition_var,
            self._monitor_var,
        ):
            variable.trace_add("write", self._on_setting_changed)

    def _on_setting_changed(self, *_args) -> None:
        if self._restoring_ui_state:
            return
        self._persist_settings()

    def _persist_settings(self) -> None:
        sources = [self._playlist_var.get().strip(), self._folder_var.get().strip()]
        valid_sources = tuple(path for path in sources if path)
        update_ambiance_settings(
            enabled=bool(self._enabled_var.get()),
            playlist_paths=valid_sources,
            default_duration_sec=self._safe_duration_value(),
            transition=(self._transition_var.get().strip().lower() or "fade"),
            shuffle=bool(self._shuffle_var.get()),
            loop=bool(self._loop_var.get()),
            target_monitor_index=self._safe_monitor_index(),
        )

    def _safe_duration_value(self) -> float:
        try:
            return max(0.5, float(self._duration_var.get().strip()))
        except Exception:
            return 8.0

    def _safe_monitor_index(self) -> int:
        try:
            return max(0, int(self._monitor_var.get().strip()))
        except Exception:
            return 1

    def _pick_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select ambiance folder")
        if selected:
            self._folder_var.set(selected)
            self._scan_folder()

    def _pick_playlist(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select ambiance playlist",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected:
            self._playlist_var.set(selected)
            self._load_playlist_file(selected)

    def _refresh_sources(self) -> None:
        playlist_path = self._playlist_var.get().strip()
        folder = self._folder_var.get().strip()
        if playlist_path:
            self._load_playlist_file(playlist_path)
            self._persist_settings()
            return
        if folder:
            self._scan_folder()
            self._persist_settings()
            return
        self._records = []
        self._render_records()
        self._persist_settings()

    def _scan_folder(self) -> None:
        folder = self._folder_var.get().strip()
        if not folder:
            self._status_var.set("Select a folder before scanning.")
            return
        self._records = self._repository.scan_folder(folder)
        self._status_var.set(f"{len(self._records)} media indexed from folder.")
        self._render_records()
        self._persist_settings()

    def _load_playlist_file(self, playlist_path: str) -> None:
        path = Path(playlist_path).expanduser()
        if not path.is_file():
            self._status_var.set("Playlist file not found.")
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._status_var.set(f"Unable to read playlist: {exc}")
            return

        media_items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(media_items, list):
            media_items = []
        media_paths = [str((item or {}).get("path") or "") for item in media_items if isinstance(item, dict)]
        self._records = self._repository.build_index(media_paths)

        if isinstance(payload, dict):
            self._loop_var.set(bool(payload.get("loop", self._loop_var.get())))
            self._shuffle_var.set(bool(payload.get("shuffle", self._shuffle_var.get())))
            duration = payload.get("default_duration")
            if duration not in (None, ""):
                self._duration_var.set(str(duration))
        self._status_var.set(f"{len(self._records)} media loaded from playlist.")
        self._render_records()
        self._persist_settings()

    def _render_records(self) -> None:
        for child in self._list.winfo_children():
            child.destroy()

        if not self._records:
            ctk.CTkLabel(self._list, text="No media detected.", anchor="w").grid(row=0, column=0, sticky="ew", padx=4, pady=4)
            return

        self._list.grid_columnconfigure(1, weight=1)
        for idx, record in enumerate(self._records):
            row = ctk.CTkFrame(self._list)
            row.grid(row=idx, column=0, sticky="ew", padx=2, pady=2)
            row.grid_columnconfigure(1, weight=1)

            thumb = self._thumbnail_cache.get(record)
            ctk.CTkLabel(row, text="", image=thumb, width=116).grid(row=0, column=0, padx=(6, 8), pady=6)

            details = record.name
            if record.width and record.height:
                details = f"{details} · {record.width}x{record.height}"
            ctk.CTkLabel(row, text=details, anchor="w").grid(row=0, column=1, sticky="ew", padx=(0, 8))
            ctk.CTkLabel(row, text=record.media_type.title(), text_color="#9CA3AF", width=72).grid(row=0, column=2, padx=(0, 8))

    def _build_playlist(self) -> AmbiancePlaylist | None:
        if not self._records:
            self._status_var.set("No media available. Scan folder or load playlist first.")
            return None

        try:
            default_duration = max(0.5, float(self._duration_var.get().strip()))
        except Exception:
            self._status_var.set("Image duration must be a number.")
            return None

        items = [
            AmbianceItem(path=record.path, media_type=record.media_type, duration=default_duration)
            for record in self._records
        ]
        return AmbiancePlaylist(
            items=items,
            loop=bool(self._loop_var.get()),
            shuffle=bool(self._shuffle_var.get()),
            default_duration=default_duration,
            transition_ms=0 if self._transition_var.get().strip().lower() == "cut" else 380,
        )

    def _resolve_player(self):
        host = self.winfo_toplevel()
        getter = getattr(host, "get_ambiance_player", None)
        if callable(getter):
            return getter()
        self._status_var.set("Ambiance player unavailable from this window.")
        return None

    def _start(self) -> None:
        player = self._resolve_player()
        playlist = self._build_playlist()
        if player is None or playlist is None:
            return
        try:
            setter = getattr(player, "set_target_monitor_index", None)
            if callable(setter):
                setter(self._safe_monitor_index())
            player.start(playlist)
            self._status_var.set(f"Playback started ({len(playlist.items)} media).")
            self._persist_settings()
        except Exception as exc:
            self._status_var.set(f"Start failed: {exc}")

    def _pause_or_resume(self) -> None:
        player = self._resolve_player()
        if player is None:
            return
        try:
            state = getattr(player, "_state", None)
            if state is not None and getattr(state, "is_paused", False):
                player.resume()
                self._status_var.set("Playback resumed.")
            else:
                player.pause()
                self._status_var.set("Playback paused.")
        except Exception as exc:
            self._status_var.set(f"Pause failed: {exc}")

    def _stop(self) -> None:
        player = self._resolve_player()
        if player is None:
            return
        try:
            player.stop()
            self._status_var.set("Playback stopped.")
        except Exception as exc:
            self._status_var.set(f"Stop failed: {exc}")

    def _next(self) -> None:
        player = self._resolve_player()
        if player is None:
            return
        try:
            player.next()
            self._status_var.set("Skipped to next media.")
        except Exception as exc:
            self._status_var.set(f"Next failed: {exc}")
