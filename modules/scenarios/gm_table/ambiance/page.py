"""Ambiance page driven by campaign-local wallpaper library."""

from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from modules.ui.ambiance.importer.service import WallpaperImportService
from modules.ui.ambiance.importer.thumbnailer import WallpaperThumbnailer
from modules.ui.ambiance.library.models import WallpaperLibraryItem, WallpaperQuery
from modules.ui.ambiance.library.repository import CampaignWallpaperRepository
from modules.ui.ambiance.models import AmbianceItem, AmbiancePlaylist
from modules.ui.ambiance.settings import AmbianceSettings, load_ambiance_settings, update_ambiance_settings


class GMTableAmbiancePage(ctk.CTkFrame):
    """Manage ambiance library selection and playback playlist."""

    def __init__(self, master, *, initial_state: dict | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._repository = CampaignWallpaperRepository()
        self._import_service = WallpaperImportService(self._repository.store)
        self._thumbnailer = WallpaperThumbnailer(size=(136, 82))
        self._selected_ids: set[str] = set()
        self._playlist: list[dict] = []
        self._drag_index: int | None = None
        self._restoring_ui_state = True

        state = dict(initial_state or {})
        settings = load_ambiance_settings()
        self._migrate_legacy_sources_if_needed(settings)
        settings = load_ambiance_settings()

        self._query_var = tk.StringVar(value="")
        self._media_var = tk.StringVar(value="all")
        self._orientation_var = tk.StringVar(value="all")
        self._sort_var = tk.StringVar(value="name")
        self._status_var = tk.StringVar(value="")

        self._duration_var = tk.StringVar(value=str(state.get("image_duration", settings.default_duration_sec or 8)))
        self._loop_var = tk.BooleanVar(value=bool(state.get("loop", settings.loop)))
        self._shuffle_var = tk.BooleanVar(value=bool(state.get("shuffle", settings.shuffle)))
        self._enabled_var = tk.BooleanVar(value=bool(settings.enabled))
        self._transition_var = tk.StringVar(value=settings.transition if settings.transition in {"fade", "cut"} else "fade")
        self._monitor_var = tk.StringVar(value=str(max(0, settings.target_monitor_index)))

        persisted_entries = list(settings.playlist_entries)
        state_playlist = state.get("playlist_entries")
        if isinstance(state_playlist, list):
            persisted_entries = state_playlist
        self._playlist = _normalize_playlist_entries(persisted_entries, default_duration=self._safe_duration_value())

        self._build_header()
        self._build_filters()
        self._build_body()
        self._build_player_controls()

        self._query_var.trace_add("write", lambda *_args: self._render_library())
        self._media_var.trace_add("write", lambda *_args: self._render_library())
        self._orientation_var.trace_add("write", lambda *_args: self._render_library())
        self._sort_var.trace_add("write", lambda *_args: self._render_library())

        self._bind_persistence_traces()
        self._render_library()
        self._render_playlist()
        self._restoring_ui_state = False

    def _build_header(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text="Ambiance Screen", anchor="w", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ctk.CTkButton(top, text="Open Importer", width=130, command=self._open_importer).grid(row=0, column=1, padx=(10, 0))

    def _build_filters(self) -> None:
        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        filters.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(filters, text="Search").grid(row=0, column=0, padx=(0, 6), sticky="w")
        ctk.CTkEntry(filters, textvariable=self._query_var, height=30, placeholder_text="Filename or tag").grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(0, 8),
        )
        ctk.CTkOptionMenu(filters, variable=self._media_var, values=["all", "image", "video"], width=110).grid(row=0, column=2, padx=(0, 8))
        ctk.CTkOptionMenu(filters, variable=self._orientation_var, values=["all", "landscape", "portrait", "square"], width=126).grid(row=0, column=3, padx=(0, 8))
        ctk.CTkOptionMenu(filters, variable=self._sort_var, values=["name", "created_desc", "size_desc"], width=120).grid(row=0, column=4, padx=(0, 8))
        ctk.CTkButton(filters, text="Add to playlist", width=130, command=self._add_selected_to_playlist).grid(row=0, column=5)

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=1)

        self._library_frame = ctk.CTkScrollableFrame(body, fg_color="transparent")
        self._library_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._library_frame.grid_columnconfigure(0, weight=1)

        playlist_panel = ctk.CTkFrame(body)
        playlist_panel.grid(row=0, column=1, sticky="nsew")
        playlist_panel.grid_rowconfigure(1, weight=1)
        playlist_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(playlist_panel, text="Session Playlist", anchor="w", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=8,
            pady=(8, 6),
        )
        self._playlist_frame = ctk.CTkScrollableFrame(playlist_panel, fg_color="transparent")
        self._playlist_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

    def _build_player_controls(self) -> None:
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        controls.grid_columnconfigure(8, weight=1)

        ctk.CTkLabel(controls, text="Image duration (s)").grid(row=0, column=0, sticky="w")
        ctk.CTkEntry(controls, textvariable=self._duration_var, width=76, height=30).grid(row=0, column=1, padx=(6, 14), sticky="w")
        ctk.CTkCheckBox(controls, text="Loop", variable=self._loop_var).grid(row=0, column=2, padx=(0, 8))
        ctk.CTkCheckBox(controls, text="Shuffle", variable=self._shuffle_var).grid(row=0, column=3, padx=(0, 8))
        ctk.CTkLabel(controls, text="Transition").grid(row=0, column=4, padx=(0, 6))
        ctk.CTkOptionMenu(controls, variable=self._transition_var, values=["fade", "cut"], width=86).grid(row=0, column=5, padx=(0, 10))
        ctk.CTkLabel(controls, text="Monitor").grid(row=0, column=6, padx=(0, 6))
        ctk.CTkEntry(controls, textvariable=self._monitor_var, width=50, height=30).grid(row=0, column=7, padx=(0, 10), sticky="w")
        ctk.CTkCheckBox(controls, text="Auto resume", variable=self._enabled_var).grid(row=0, column=8, padx=(0, 10), sticky="w")

        ctk.CTkButton(controls, text="Start", width=72, command=self._start).grid(row=0, column=9, padx=(0, 6), sticky="e")
        ctk.CTkButton(controls, text="Pause", width=72, command=self._pause_or_resume).grid(row=0, column=10, padx=(0, 6), sticky="e")
        ctk.CTkButton(controls, text="Stop", width=72, command=self._stop).grid(row=0, column=11, padx=(0, 6), sticky="e")
        ctk.CTkButton(controls, text="Next", width=72, command=self._next).grid(row=0, column=12, sticky="e")

        ctk.CTkLabel(self, textvariable=self._status_var, anchor="w", text_color="#F59E0B").grid(row=4, column=0, sticky="ew", pady=(6, 0))

    def _library_items(self) -> list[WallpaperLibraryItem]:
        return self._repository.list_items(
            WallpaperQuery(
                search=self._query_var.get(),
                media_type=self._media_var.get(),
                orientation=self._orientation_var.get(),
                sort_key=self._sort_var.get(),
            )
        )

    def _render_library(self) -> None:
        for child in self._library_frame.winfo_children():
            child.destroy()
        items = self._library_items()
        if not items:
            card = ctk.CTkFrame(self._library_frame)
            card.grid(row=0, column=0, sticky="ew", padx=4, pady=6)
            ctk.CTkLabel(card, text="No wallpapers imported yet", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=(10, 2))
            ctk.CTkLabel(card, text="Import wallpapers into this campaign to build your playlist.", text_color="#9CA3AF").pack(anchor="w", padx=10, pady=(0, 10))
            ctk.CTkButton(card, text="Open Importer", command=self._open_importer).pack(anchor="w", padx=10, pady=(0, 10))
            return

        for idx, item in enumerate(items):
            self._render_library_card(item=item, row_idx=idx)

    def _render_library_card(self, *, item: WallpaperLibraryItem, row_idx: int) -> None:
        card = ctk.CTkFrame(self._library_frame, border_width=1, border_color="#334155")
        card.grid(row=row_idx, column=0, sticky="ew", padx=4, pady=4)
        card.grid_columnconfigure(1, weight=1)

        abs_path = self._repository.store.absolute_path(item)
        thumb = self._thumbnailer.get(abs_path, media_type=item.media_type)
        ctk.CTkLabel(card, text="", image=thumb, width=144).grid(row=0, column=0, rowspan=2, padx=(8, 8), pady=8)

        selected = item.id in self._selected_ids
        select_button = ctk.CTkCheckBox(
            card,
            text=item.filename,
            onvalue=True,
            offvalue=False,
            command=lambda item_id=item.id: self._toggle_select(item_id),
        )
        if selected:
            select_button.select()
        else:
            select_button.deselect()
        select_button.grid(row=0, column=1, sticky="w", pady=(8, 2))

        details = f"{item.media_type.title()} · {item.width or '—'}x{item.height or '—'} · {_format_size(item.filesize)}"
        ctk.CTkLabel(card, text=details, text_color="#9CA3AF", anchor="w").grid(row=1, column=1, sticky="w", pady=(0, 8))

        quick_actions = ctk.CTkFrame(card, fg_color="transparent")
        quick_actions.grid(row=0, column=2, rowspan=2, padx=(0, 8))
        preview_btn = ctk.CTkButton(quick_actions, text="Preview", width=74, command=lambda i=item: self._preview_item(i))
        add_btn = ctk.CTkButton(quick_actions, text="+ Playlist", width=86, command=lambda i=item: self._add_single_to_playlist(i))
        tag_btn = ctk.CTkButton(quick_actions, text="Tag", width=54, command=lambda i=item: self._tag_item(i))

        def _show(_event=None):
            preview_btn.grid(row=0, column=0, padx=(0, 4), pady=(0, 4))
            add_btn.grid(row=0, column=1, padx=(0, 4), pady=(0, 4))
            tag_btn.grid(row=0, column=2, pady=(0, 4))

        def _hide(_event=None):
            for widget in (preview_btn, add_btn, tag_btn):
                widget.grid_forget()

        card.bind("<Enter>", _show)
        card.bind("<Leave>", _hide)

    def _render_playlist(self) -> None:
        for child in self._playlist_frame.winfo_children():
            child.destroy()

        items = self._repository.find_by_ids([entry["id"] for entry in self._playlist])
        by_id = {item.id: item for item in items}
        if not self._playlist:
            ctk.CTkLabel(self._playlist_frame, text="Playlist is empty.", text_color="#9CA3AF").grid(row=0, column=0, sticky="w", padx=4, pady=6)
            self._persist_settings()
            return

        for idx, entry in enumerate(self._playlist):
            item = by_id.get(entry["id"])
            if item is None:
                continue
            row = ctk.CTkFrame(self._playlist_frame)
            row.grid(row=idx, column=0, sticky="ew", padx=2, pady=2)
            row.grid_columnconfigure(1, weight=1)
            row.bind("<ButtonPress-1>", lambda _event, i=idx: self._begin_drag(i))
            row.bind("<ButtonRelease-1>", lambda _event, i=idx: self._drop_drag(i))

            ctk.CTkLabel(row, text="☰", width=22, text_color="#94A3B8").grid(row=0, column=0, padx=(6, 6), pady=6)
            ctk.CTkLabel(row, text=item.filename, anchor="w").grid(row=0, column=1, sticky="ew")
            chip = ctk.CTkLabel(row, text=f"{float(entry.get('duration', self._safe_duration_value())):.0f}s", width=44, fg_color="#1F2937", corner_radius=10)
            chip.grid(row=0, column=2, padx=(6, 4), pady=6)
            ctk.CTkButton(row, text="+", width=26, command=lambda i=idx: self._adjust_duration(i, +1)).grid(row=0, column=3, padx=(0, 4))
            ctk.CTkButton(row, text="-", width=26, command=lambda i=idx: self._adjust_duration(i, -1)).grid(row=0, column=4, padx=(0, 4))
            ctk.CTkButton(row, text="×", width=26, fg_color="#B91C1C", hover_color="#991B1B", command=lambda i=idx: self._remove_playlist_index(i)).grid(row=0, column=5, padx=(0, 6))

        self._persist_settings()

    def _begin_drag(self, index: int) -> None:
        self._drag_index = index

    def _drop_drag(self, target_index: int) -> None:
        source = self._drag_index
        self._drag_index = None
        if source is None or source == target_index:
            return
        if source < 0 or source >= len(self._playlist) or target_index < 0 or target_index >= len(self._playlist):
            return
        entry = self._playlist.pop(source)
        self._playlist.insert(target_index, entry)
        self._render_playlist()

    def _toggle_select(self, item_id: str) -> None:
        if item_id in self._selected_ids:
            self._selected_ids.remove(item_id)
        else:
            self._selected_ids.add(item_id)

    def _add_selected_to_playlist(self) -> None:
        selected_items = self._repository.find_by_ids(list(self._selected_ids))
        if not selected_items:
            self._toast("No wallpaper selected.")
            return
        for item in selected_items:
            self._playlist.append({"id": item.id, "duration": self._safe_duration_value()})
        self._render_playlist()
        self._toast(f"Added {len(selected_items)} item(s) to playlist.")

    def _add_single_to_playlist(self, item: WallpaperLibraryItem) -> None:
        self._playlist.append({"id": item.id, "duration": self._safe_duration_value()})
        self._render_playlist()
        self._toast(f"Added '{item.filename}' to playlist.")

    def _remove_playlist_index(self, index: int) -> None:
        if 0 <= index < len(self._playlist):
            self._playlist.pop(index)
            self._render_playlist()

    def _adjust_duration(self, index: int, delta: int) -> None:
        if not (0 <= index < len(self._playlist)):
            return
        current = float(self._playlist[index].get("duration", self._safe_duration_value()))
        self._playlist[index]["duration"] = max(1.0, current + float(delta))
        self._render_playlist()

    def _preview_item(self, item: WallpaperLibraryItem) -> None:
        messagebox.showinfo("Wallpaper", f"{item.filename}\n{item.width or '—'}x{item.height or '—'}\nTags: {', '.join(item.tags) or 'none'}", parent=self)

    def _tag_item(self, item: WallpaperLibraryItem) -> None:
        current = ", ".join(item.tags)
        answer = simpledialog.askstring("Tags", "Comma-separated tags", initialvalue=current, parent=self)
        if answer is None:
            return
        tags = tuple(tag.strip() for tag in answer.split(",") if tag.strip())
        updated = WallpaperLibraryItem(
            id=item.id,
            relative_path=item.relative_path,
            filename=item.filename,
            media_type=item.media_type,
            width=item.width,
            height=item.height,
            filesize=item.filesize,
            created_at=item.created_at,
            tags=tags,
        )
        self._repository.store.upsert(updated)
        self._render_library()

    def _build_playlist(self) -> AmbiancePlaylist | None:
        if not self._playlist:
            self._status_var.set("No media in playlist. Add imported wallpapers first.")
            return None

        lookup = {item.id: item for item in self._repository.find_by_ids([entry["id"] for entry in self._playlist])}
        if not lookup:
            self._status_var.set("Playlist references missing library items.")
            return None

        try:
            default_duration = max(0.5, float(self._duration_var.get().strip()))
        except Exception:
            self._status_var.set("Image duration must be a number.")
            return None

        items: list[AmbianceItem] = []
        for entry in self._playlist:
            source = lookup.get(entry["id"])
            if source is None:
                continue
            absolute = self._repository.store.absolute_path(source)
            duration = float(entry.get("duration") or default_duration)
            items.append(AmbianceItem(path=absolute, media_type=source.media_type, duration=max(0.5, duration), tags=source.tags))

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

    def _open_importer(self) -> None:
        host = self.winfo_toplevel()
        opener = getattr(host, "open_wallpaper_importer", None)
        if callable(opener):
            opener(on_complete=lambda _result: self._on_import_completed())
            return
        self._status_var.set("Importer unavailable from this window.")

    def _on_import_completed(self) -> None:
        self._repository.rebuild()
        self._render_library()
        self._toast("Wallpaper library updated.")

    def _bind_persistence_traces(self) -> None:
        for variable in (
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
        update_ambiance_settings(
            enabled=bool(self._enabled_var.get()),
            playlist_paths=(),
            playlist_item_ids=tuple(entry["id"] for entry in self._playlist),
            playlist_entries=tuple({"id": entry["id"], "duration": float(entry.get("duration", self._safe_duration_value()))} for entry in self._playlist),
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

    def _toast(self, text: str) -> None:
        self._status_var.set(text)
        self.after(3500, lambda: self._status_var.set(""))

    def _migrate_legacy_sources_if_needed(self, settings: AmbianceSettings) -> None:
        if settings.playlist_entries:
            return
        if not settings.playlist_paths:
            return

        gathered: list[str] = []
        for raw in settings.playlist_paths:
            path = Path(str(raw or "")).expanduser()
            if path.is_dir():
                gathered.extend(str(candidate) for candidate in sorted(path.rglob("*")) if candidate.is_file())
                continue
            if path.is_file() and path.suffix.lower() == ".json":
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                items = payload.get("items") if isinstance(payload, dict) else []
                if isinstance(items, list):
                    for item in items:
                        media_path = str((item or {}).get("path") or "") if isinstance(item, dict) else ""
                        if media_path:
                            gathered.append(media_path)
                continue
            if path.is_file():
                gathered.append(str(path))

        if not gathered:
            update_ambiance_settings(playlist_paths=(), playlist_item_ids=(), playlist_entries=())
            return

        result = self._import_service.import_files(gathered, strategy="skip")
        if result.imported_items:
            migrated_entries = tuple({"id": item.id, "duration": settings.default_duration_sec or 8.0} for item in result.imported_items)
            update_ambiance_settings(
                playlist_paths=(),
                playlist_item_ids=tuple(item.id for item in result.imported_items),
                playlist_entries=migrated_entries,
            )
        else:
            update_ambiance_settings(playlist_paths=(), playlist_item_ids=(), playlist_entries=())


def _normalize_playlist_entries(raw_entries: list | tuple, *, default_duration: float) -> list[dict]:
    normalized: list[dict] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        item_id = str(raw.get("id") or "").strip()
        if not item_id:
            continue
        try:
            duration = max(0.5, float(raw.get("duration") or default_duration))
        except Exception:
            duration = default_duration
        normalized.append({"id": item_id, "duration": duration})
    return normalized


def _format_size(size: int) -> str:
    value = float(max(0, int(size)))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
