"""UI window that manages cross-campaign asset exports and imports."""

from __future__ import annotations

import copy
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List

import customtkinter as ctk
from PIL import Image
from tkinter import filedialog, messagebox, ttk, END

from modules.generic.cross_campaign_asset_service import (
    CampaignDatabase,
    analyze_bundle,
    apply_import,
    cleanup_analysis,
    discover_databases_in_directory,
    export_bundle,
    get_active_campaign,
    list_sibling_campaigns,
    load_entities,
)
from modules.helpers.logging_helper import log_exception, log_info, log_warning
from modules.helpers.selection_dialog import SelectionDialog
from modules.helpers.template_loader import load_entity_definitions, list_known_entities


class CrossCampaignAssetLibraryWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Cross-campaign Asset Library")
        self.geometry("1200x720")
        self.minsize(1000, 620)
        self.transient(master)
        self.lift()
        self.focus_force()

        self.entity_definitions = load_entity_definitions()
        self.entity_types = tuple(list_known_entities()) or tuple(sorted(self.entity_definitions.keys()))
        if not self.entity_types:
            self.entity_types = ("npcs", "objects", "maps")
        for slug in self.entity_types:
            self.entity_definitions.setdefault(slug, {"label": slug.replace("_", " ").title()})
        self.entity_records: Dict[str, List[dict]] = {key: [] for key in self.entity_types}

        self.active_campaign = get_active_campaign()
        self.source_campaigns: List[CampaignDatabase] = []
        self.selected_campaign: CampaignDatabase | None = None
        self._preview_image = None

        self._build_ui()
        self.refresh_campaign_list()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, sticky="nsw", padx=10, pady=10)
        self.left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.left_frame, text="Available Campaigns", font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )

        self.campaign_list = ctk.CTkScrollableFrame(self.left_frame, width=260)
        self.campaign_list.grid(row=1, column=0, columnspan=2, sticky="nsew")

        self.campaign_buttons: List[ctk.CTkButton] = []

        browse_btn = ctk.CTkButton(self.left_frame, text="Browse…", command=self.browse_for_campaign)
        browse_btn.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        refresh_btn = ctk.CTkButton(self.left_frame, text="Refresh", command=self.refresh_campaign_list)
        refresh_btn.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(10, 0))

        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=3)
        self.right_frame.grid_columnconfigure(1, weight=2)

        self.tabview = ctk.CTkTabview(self.right_frame)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.treeviews: Dict[str, ttk.Treeview] = {}
        if not self.entity_types:
            return

        for entity_type in self.entity_types:
            label = self.entity_definitions.get(entity_type, {}).get("label") or entity_type.replace("_", " ").title()
            tab = self.tabview.add(label)
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(0, weight=1)
            columns = ("name", "summary")
            tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="extended", height=14)
            tree.heading("name", text="Name")
            tree.heading("summary", text="Summary")
            tree.column("name", width=220, anchor="w")
            tree.column("summary", width=360, anchor="w")
            tree.grid(row=0, column=0, sticky="nsew")
            tree.bind("<<TreeviewSelect>>", lambda _evt, et=entity_type: self.update_preview_from_tree(et))
            yscroll = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=yscroll.set)
            yscroll.grid(row=0, column=1, sticky="ns")
            self.treeviews[entity_type] = tree

        self.preview_frame = ctk.CTkFrame(self.right_frame)
        self.preview_frame.grid(row=0, column=1, sticky="nsew")
        self.preview_frame.grid_rowconfigure(2, weight=1)
        self.preview_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.preview_frame, text="Preview", font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, sticky="nw"
        )
        self.preview_name = ctk.CTkLabel(self.preview_frame, text="", font=("Segoe UI", 14, "bold"))
        self.preview_name.grid(row=1, column=0, sticky="nw", pady=(4, 4))

        self.preview_image_label = ctk.CTkLabel(self.preview_frame, text="", image=None)
        self.preview_image_label.grid(row=2, column=0, sticky="nwe", pady=6)

        self.preview_text = ctk.CTkTextbox(self.preview_frame, wrap="word")
        self.preview_text.grid(row=3, column=0, sticky="nsew")
        self.preview_text.configure(state="disabled")

        button_row = ctk.CTkFrame(self)
        button_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        button_row.grid_columnconfigure((0, 1, 2), weight=1)

        self.export_btn = ctk.CTkButton(button_row, text="Export Selected…", command=self.export_selected)
        self.export_btn.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        self.import_btn = ctk.CTkButton(button_row, text="Import Bundle…", command=self.import_bundle)
        self.import_btn.grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        self.reload_btn = ctk.CTkButton(button_row, text="Refresh Source", command=self.reload_source)
        self.reload_btn.grid(row=0, column=2, padx=6, pady=6, sticky="ew")

    # --------------------------------------------------------- Campaign list
    def refresh_campaign_list(self):
        for btn in self.campaign_buttons:
            btn.destroy()
        self.campaign_buttons.clear()

        self.source_campaigns = list_sibling_campaigns(include_current=False)
        for index, campaign in enumerate(self.source_campaigns):
            btn = ctk.CTkButton(
                self.campaign_list,
                text=campaign.name,
                command=lambda c=campaign: self.select_campaign(c),
                anchor="w",
            )
            btn.grid(row=index, column=0, sticky="ew", pady=2, padx=2)
            self.campaign_buttons.append(btn)

        if self.source_campaigns:
            self.select_campaign(self.source_campaigns[0])
        else:
            self.selected_campaign = None
            self.clear_entities()

    def browse_for_campaign(self):
        directory = filedialog.askdirectory(title="Select Campaign Directory")
        if not directory:
            return
        candidates = discover_databases_in_directory(Path(directory))
        if not candidates:
            messagebox.showwarning(
                "No Campaign Database",
                "The selected directory does not contain any .db files.",
            )
            return
        if len(candidates) == 1:
            self.select_campaign(candidates[0])
            return

        dialog = SelectionDialog(self, "Select Database", "Choose a campaign database:", [c.name for c in candidates])
        self.wait_window(dialog)
        if dialog.result is None:
            return
        for candidate in candidates:
            if candidate.name == dialog.result:
                self.select_campaign(candidate)
                break

    def select_campaign(self, campaign: CampaignDatabase):
        self.selected_campaign = campaign
        log_info(
            f"Selected campaign for asset browsing: {campaign.db_path}",
            func_name="modules.generic.cross_campaign_asset_library.select_campaign",
        )
        self.reload_source()

    # -------------------------------------------------------------- Loading
    def reload_source(self):
        if not self.selected_campaign:
            return
        with self._busy_cursor():
            try:
                for entity_type in self.entity_types:
                    self.entity_records[entity_type] = load_entities(entity_type, self.selected_campaign.db_path)
            except Exception as exc:
                log_exception(
                    f"Failed to load entities from {self.selected_campaign.db_path}: {exc}",
                    func_name="modules.generic.cross_campaign_asset_library.reload_source",
                )
                messagebox.showerror(
                    "Load Error",
                    f"Unable to read from the selected campaign database.\n{exc}",
                )
                self.clear_entities()
                return
        self.populate_lists()

    def clear_entities(self):
        for entity_type in self.entity_types:
            self.entity_records[entity_type] = []
            tree = self.treeviews.get(entity_type)
            if tree:
                tree.delete(*tree.get_children())
        self._set_preview(None, None)

    def populate_lists(self):
        for entity_type, tree in self.treeviews.items():
            tree.delete(*tree.get_children())
            records = self.entity_records.get(entity_type, [])
            for idx, record in enumerate(records):
                name = record.get("Name") or record.get("Title") or "<Unnamed>"
                summary = None
                for field in ("Description", "Summary", "Information", "Notes", "Background", "Secret"):
                    value = record.get(field)
                    if value:
                        summary = value
                        break
                if summary is None:
                    summary = ""
                summary_text = " ".join(str(summary).split())[:140]
                tree.insert("", END, iid=f"{entity_type}:{idx}", values=(name, summary_text))
        self._set_preview(None, None)

    # ------------------------------------------------------------- Preview
    def update_preview_from_tree(self, entity_type: str):
        tree = self.treeviews.get(entity_type)
        if not tree:
            return
        selection = tree.selection()
        if not selection:
            self._set_preview(None, None)
            return
        item_id = selection[0]
        try:
            _, index_str = item_id.split(":", 1)
            index = int(index_str)
        except ValueError:
            self._set_preview(None, None)
            return
        record = self.entity_records.get(entity_type, [])
        if index >= len(record):
            self._set_preview(None, None)
            return
        self._set_preview(entity_type, record[index])

    def _set_preview(self, entity_type: str | None, record: dict | None):
        if not record or not entity_type:
            self.preview_name.configure(text="")
            self.preview_text.configure(state="normal")
            self.preview_text.delete("1.0", END)
            self.preview_text.configure(state="disabled")
            self.preview_image_label.configure(image=None, text="")
            self._preview_image = None
            return

        name = record.get("Name") or record.get("Title") or "<Unnamed>"
        self.preview_name.configure(text=name)

        description = ""
        for field in ("Description", "Summary", "Information", "Notes", "Background", "Secret"):
            value = record.get(field)
            if value:
                description = value
                break
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", END)
        self.preview_text.insert("1.0", description)
        extra_lines: List[str] = []
        audio_value = record.get("Audio")
        if audio_value:
            extra_lines.append(f"Audio: {audio_value}")
        attachment_value = record.get("Attachment")
        if attachment_value:
            extra_lines.append(f"Attachment: {attachment_value}")
        if extra_lines:
            self.preview_text.insert("end", "\n\n" + "\n".join(extra_lines))
        self.preview_text.configure(state="disabled")

        image_path = None
        if entity_type in {"npcs", "objects", "pcs", "creatures", "places", "clues"}:
            image_path = record.get("Portrait")
        elif entity_type == "maps":
            image_path = record.get("Image")

        if image_path:
            resolved = self._resolve_asset_path(image_path)
            if resolved and resolved.exists():
                try:
                    pil_image = Image.open(resolved)
                    pil_image.thumbnail((360, 360))
                    self._preview_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=pil_image.size)
                    self.preview_image_label.configure(image=self._preview_image, text="")
                    return
                except Exception as exc:
                    log_warning(
                        f"Failed to load preview image {resolved}: {exc}",
                        func_name="modules.generic.cross_campaign_asset_library._set_preview",
                    )

        self.preview_image_label.configure(image=None, text="No preview available")
        self._preview_image = None

    def _resolve_asset_path(self, value: str) -> Path | None:
        if not value or not self.selected_campaign:
            return None
        normalized = str(value).strip()
        path = Path(normalized)
        if path.is_absolute():
            return path
        return (self.selected_campaign.root / normalized).resolve()

    # ----------------------------------------------------------- Exporting
    def export_selected(self):
        if not self.selected_campaign:
            messagebox.showwarning("No Source", "Select a source campaign first.")
            return

        selections: Dict[str, List[dict]] = {}
        for entity_type, tree in self.treeviews.items():
            records = self.entity_records.get(entity_type, [])
            items: List[dict] = []
            for item_id in tree.selection():
                try:
                    _, index_str = item_id.split(":", 1)
                    index = int(index_str)
                except ValueError:
                    continue
                if 0 <= index < len(records):
                    items.append(copy.deepcopy(records[index]))
            if items:
                selections[entity_type] = items

        if not selections:
            messagebox.showinfo("No Selection", "Select at least one asset to export.")
            return

        default_name = f"asset_bundle_{self.selected_campaign.name.replace(' ', '_')}.zip"
        destination = filedialog.asksaveasfilename(
            title="Export Asset Bundle",
            defaultextension=".zip",
            initialfile=default_name,
            filetypes=[("Zip Files", "*.zip")],
        )
        if not destination:
            return

        def worker(callback):
            return export_bundle(Path(destination), self.selected_campaign, selections, progress_callback=callback)

        def detail(manifest: dict) -> str:
            lines = [f"Saved to: {manifest.get('archive_path')}"]
            for entity_type, meta in manifest.get("entities", {}).items():
                lines.append(f"{entity_type.title()}: {meta.get('count', 0)}")
            return "\n".join(lines)

        self._run_progress_task("Exporting Assets", worker, "Asset bundle created successfully.", detail)

    # ------------------------------------------------------------- Importing
    def import_bundle(self):
        bundle_path = filedialog.askopenfilename(
            title="Import Asset Bundle",
            filetypes=[("Zip Files", "*.zip"), ("All Files", "*.*")],
        )
        if not bundle_path:
            return

        target_campaign = self.active_campaign

        def analyze_worker(_callback):
            return analyze_bundle(Path(bundle_path), target_campaign.db_path)

        def after_analysis(analysis):
            duplicates = analysis.duplicates
            if duplicates:
                details = []
                for entity_type, names in duplicates.items():
                    details.append(f"{entity_type.title()}: {len(names)}")
                detail_text = "\n".join(details)
                response = messagebox.askyesnocancel(
                    "Overwrite Existing Entries?",
                    "Some assets already exist in the active campaign:\n"
                    f"{detail_text}\n\nSelect Yes to overwrite them, No to skip duplicates, or Cancel to abort.",
                )
                if response is None:
                    cleanup_analysis(analysis)
                    return
                overwrite = bool(response)
            else:
                overwrite = True

            def import_worker(callback):
                try:
                    return apply_import(analysis, target_campaign, overwrite=overwrite, progress_callback=callback)
                except Exception:
                    cleanup_analysis(analysis)
                    raise

            def detail(summary: dict) -> str:
                return (
                    f"Imported: {summary.get('imported', 0)}\n"
                    f"Updated: {summary.get('updated', 0)}\n"
                    f"Skipped: {summary.get('skipped', 0)}"
                )

            def finalize(result):
                cleanup_analysis(analysis)
                self._post_import(result, overwrite)

            self._run_progress_task(
                "Importing Assets",
                import_worker,
                "Bundle imported into the active campaign.",
                detail,
                on_success=finalize,
            )

        self._run_progress_task("Analyzing Bundle", analyze_worker, None, None, on_success=after_analysis)

    def _post_import(self, summary: dict, overwrite: bool):
        if hasattr(self.master, "refresh_entities"):
            try:
                self.master.refresh_entities()
            except Exception:
                pass
        messagebox.showinfo(
            "Import Complete",
            (
                f"Assets imported: {summary.get('imported', 0)}\n"
                f"Assets updated: {summary.get('updated', 0)}\n"
                f"Assets skipped: {summary.get('skipped', 0)}"
            ),
        )

    # ------------------------------------------------------- Busy handling
    def _run_progress_task(self, title, worker, success_message, detail_builder, on_success=None):
        progress_win = ctk.CTkToplevel(self)
        progress_win.title(title)
        progress_win.geometry("420x160")
        progress_win.resizable(False, False)
        progress_win.transient(self)
        progress_win.grab_set()
        progress_win.lift()

        label = ctk.CTkLabel(progress_win, text="Starting...", wraplength=360, justify="center")
        label.pack(fill="x", padx=20, pady=(20, 10))
        bar = ctk.CTkProgressBar(progress_win, mode="determinate")
        bar.pack(fill="x", padx=20, pady=(0, 20))
        bar.set(0.0)

        def update(message: str, fraction: float):
            def apply():
                label.configure(text=message)
                try:
                    bar.set(max(0.0, min(1.0, float(fraction))))
                except Exception:
                    bar.set(0.0)

            self.after(0, apply)

        def close():
            if progress_win.winfo_exists():
                try:
                    progress_win.grab_release()
                except Exception:
                    pass
                progress_win.destroy()

        def handle_success(result):
            close()
            if on_success:
                on_success(result)
                return
            if success_message:
                detail = detail_builder(result) if detail_builder else None
                message = success_message if not detail else f"{success_message}\n\n{detail}"
                messagebox.showinfo("Success", message)

        def handle_error(exc: Exception):
            close()
            messagebox.showerror("Operation Failed", str(exc))

        def run():
            try:
                result = worker(update)
            except Exception as exc:
                log_exception(
                    f"Cross-campaign asset task failed: {exc}",
                    func_name="modules.generic.cross_campaign_asset_library._run_progress_task",
                )
                self.after(0, lambda: handle_error(exc))
                return
            self.after(0, lambda: handle_success(result))

        threading.Thread(target=run, daemon=True).start()

    @contextmanager
    def _busy_cursor(self):
        try:
            self.configure(cursor="watch")
        except Exception:
            pass
        try:
            yield
        finally:
            try:
                self.configure(cursor="")
            except Exception:
                pass
