"""UI window that manages cross-campaign asset exports and imports."""

from __future__ import annotations

import copy
import re
import shutil
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, List, Optional

import customtkinter as ctk
from PIL import Image
from tkinter import END, filedialog, messagebox, simpledialog, ttk

from modules.generic.cross_campaign_asset_service import (
    CampaignDatabase,
    analyze_bundle,
    apply_direct_copy,
    apply_import,
    cleanup_analysis,
    detect_duplicates,
    discover_databases_in_directory,
    export_bundle,
    install_full_campaign_bundle,
    get_active_campaign,
    list_sibling_campaigns,
    load_entities,
)
from modules.generic.github_gallery_client import GalleryBundleSummary, GithubGalleryClient
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_exception, log_info, log_warning
from modules.helpers.portrait_helper import primary_portrait
from modules.helpers.secret_helper import decrypt_secret, encrypt_secret
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

        self.gallery_client = GithubGalleryClient()
        self._online_dialog: Optional["OnlineGalleryDialog"] = None
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
        for column_index in range(7):
            button_row.grid_columnconfigure(column_index, weight=1)

        self.export_btn = ctk.CTkButton(button_row, text="Export Selected…", command=self.export_selected)
        self.export_btn.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        self.copy_btn = ctk.CTkButton(
            button_row,
            text="Copy to Current Campaign",
            command=self.copy_selected_to_current_campaign,
        )
        self.copy_btn.grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        self.import_btn = ctk.CTkButton(button_row, text="Import Bundle…", command=self.import_bundle)
        self.import_btn.grid(row=0, column=2, padx=6, pady=6, sticky="ew")
        self.reload_btn = ctk.CTkButton(button_row, text="Refresh Source", command=self.reload_source)
        self.reload_btn.grid(row=0, column=3, padx=6, pady=6, sticky="ew")
        self.publish_btn = ctk.CTkButton(
            button_row,
            text="Publish to GitHub…",
            command=self.publish_selected_to_github,
        )
        self.publish_btn.grid(row=0, column=4, padx=6, pady=6, sticky="ew")
        self.gallery_btn = ctk.CTkButton(
            button_row,
            text="Browse Online Gallery…",
            command=self.open_online_gallery,
        )
        self.gallery_btn.grid(row=0, column=5, padx=6, pady=6, sticky="ew")

        self.github_token_btn = ctk.CTkButton(
            button_row,
            text=self._github_token_button_label(),
            command=self.configure_github_token,
        )
        self.github_token_btn.grid(row=0, column=6, padx=6, pady=6, sticky="ew")

        self._update_publish_button_state()

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
            image_path = primary_portrait(record.get("Portrait"))
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

        selections = self._gather_selected_records()

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
            return export_bundle(
                Path(destination),
                self.selected_campaign,
                selections,
                include_database=False,
                progress_callback=callback,
            )

        def detail(manifest: dict) -> str:
            lines = [f"Saved to: {manifest.get('archive_path')}"]
            for entity_type, meta in manifest.get("entities", {}).items():
                lines.append(f"{entity_type.title()}: {meta.get('count', 0)}")
            return "\n".join(lines)

        self._run_progress_task("Exporting Assets", worker, "Asset bundle created successfully.", detail)

    def publish_selected_to_github(self):
        if not self.selected_campaign:
            messagebox.showwarning("No Source", "Select a source campaign first.")
            return
        if not self.gallery_client.can_publish:
            messagebox.showerror(
                "GitHub Token Required",
                "Configure a GitHub personal access token with repo scope before publishing.",
            )
            return

        selections = self._gather_selected_records()
        publishing_full_campaign = False
        if not selections:
            if not messagebox.askyesno(
                "Publish Entire Campaign",
                "No assets are selected.\n\nDo you want to publish the entire campaign database, including all attachments?",
            ):
                return
            selections = self._gather_all_records()
            if not selections:
                messagebox.showinfo(
                    "Nothing to Publish",
                    "The selected campaign does not contain any exportable assets.",
                )
                return
            publishing_full_campaign = True

        default_title = self.selected_campaign.name or "Campaign Bundle"
        title = simpledialog.askstring(
            "Bundle Title",
            "Enter a title for the GitHub release:",
            initialvalue=default_title,
            parent=self,
        )
        if title is None:
            return
        title = title.strip()
        if not title:
            messagebox.showwarning("Invalid Title", "Enter a non-empty title for the bundle.")
            return

        description = simpledialog.askstring(
            "Bundle Description",
            "Optional description for the bundle:",
            parent=self,
        )
        if description is None:
            return
        description = description.strip()

        temp_dir = Path(tempfile.mkdtemp(prefix="gallery_publish_"))
        slug = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_") or "bundle"
        if len(slug) > 48:
            slug = slug[:48]
        archive_path = temp_dir / f"{slug}.zip"

        def worker(callback):
            try:
                manifest = export_bundle(
                    archive_path,
                    self.selected_campaign,
                    selections,
                    include_database=publishing_full_campaign,
                    progress_callback=callback,
                )
                return self.gallery_client.publish_bundle(
                    archive_path,
                    manifest,
                    title=title,
                    description=description,
                    progress_callback=callback,
                )
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        def on_success(summary: GalleryBundleSummary):
            lines = [
                f"Release: {summary.display_title}",
                f"Tag: {summary.tag or '—'}",
                f"Download URL: {summary.download_url}",
            ]
            if summary.entity_counts:
                lines.append("")
                lines.append("Entities:")
                for entity_type, count in sorted(summary.entity_counts.items()):
                    lines.append(f"  {entity_type}: {count}")
            message = "Bundle published to GitHub releases."
            detail_text = "\n".join(lines)
            if detail_text:
                message = f"{message}\n\n{detail_text}"
            messagebox.showinfo("Bundle Published", message)
            self._refresh_online_dialog()

        self._run_progress_task("Publishing Bundle", worker, None, None, on_success=on_success)

    def copy_selected_to_current_campaign(self):
        if not self.selected_campaign:
            messagebox.showwarning("No Source", "Select a source campaign first.")
            return

        selections = self._gather_selected_records()
        if not selections:
            messagebox.showinfo("No Selection", "Select at least one asset to copy.")
            return

        duplicates = detect_duplicates(selections, self.active_campaign)
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
                return
            overwrite = bool(response)
        else:
            overwrite = True

        def worker(callback):
            return apply_direct_copy(
                selections,
                source_campaign=self.selected_campaign,
                target_campaign=self.active_campaign,
                overwrite=overwrite,
                progress_callback=callback,
            )

        def detail(summary: dict) -> str:
            return (
                f"Imported: {summary.get('imported', 0)}\n"
                f"Updated: {summary.get('updated', 0)}\n"
                f"Skipped: {summary.get('skipped', 0)}"
            )

        self._run_progress_task(
            "Copying Assets",
            worker,
            "Assets copied into the active campaign.",
            detail,
            on_success=self._post_copy,
        )

    # ------------------------------------------------------------- Importing
    def import_bundle(self):
        bundle_path = filedialog.askopenfilename(
            title="Import Asset Bundle",
            filetypes=[("Zip Files", "*.zip"), ("All Files", "*.*")],
        )
        if not bundle_path:
            return
        self._start_import_from_bundle(Path(bundle_path))

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

    def _start_import_from_bundle(self, bundle_path: Path, *, cleanup: Optional[Callable[[], None]] = None):
        target_campaign = self.active_campaign

        def analyze_worker(_callback):
            try:
                return analyze_bundle(bundle_path, target_campaign.db_path)
            except Exception:
                if cleanup:
                    cleanup()
                raise

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
                    if cleanup:
                        cleanup()
                    return
                overwrite = bool(response)
            else:
                overwrite = True

            def import_worker(callback):
                try:
                    return apply_import(analysis, target_campaign, overwrite=overwrite, progress_callback=callback)
                except Exception:
                    cleanup_analysis(analysis)
                    if cleanup:
                        cleanup()
                    raise

            def detail(summary: dict) -> str:
                return (
                    f"Imported: {summary.get('imported', 0)}\n"
                    f"Updated: {summary.get('updated', 0)}\n"
                    f"Skipped: {summary.get('skipped', 0)}"
                )

            def finalize(result):
                try:
                    self._post_import(result, overwrite)
                finally:
                    cleanup_analysis(analysis)
                    if cleanup:
                        cleanup()

            self._run_progress_task(
                "Importing Assets",
                import_worker,
                "Bundle imported into the active campaign.",
                detail,
                on_success=finalize,
            )

        self._run_progress_task("Analyzing Bundle", analyze_worker, None, None, on_success=after_analysis)

    def open_online_gallery(self):
        if self._online_dialog and self._online_dialog.winfo_exists():
            try:
                self._online_dialog.lift()
                self._online_dialog.focus_force()
            except Exception:
                pass
            return
        self._online_dialog = OnlineGalleryDialog(self, self.gallery_client, self)
        self._online_dialog.update_permissions(self.gallery_client.can_publish)

    def _refresh_online_dialog(self):
        dialog = self._online_dialog
        if dialog and dialog.winfo_exists():
            dialog.refresh()

    def configure_github_token(self):
        raw_value = (ConfigHelper.get("Gallery", "github_token", fallback="") or "").strip()
        existing_token = decrypt_secret(raw_value)

        prompt_lines = [
            "Enter a GitHub personal access token with the repo scope.",
        ]
        if existing_token:
            prompt_lines.append("Leave the field blank to remove the stored token.")

        token = simpledialog.askstring(
            "GitHub Token",
            "\n".join(prompt_lines),
            parent=self,
            show="*",
        )
        if token is None:
            return

        token = token.strip()
        if not token:
            ConfigHelper.set("Gallery", "github_token", "")
            self.gallery_client.set_token(None)
            messagebox.showinfo("GitHub Token", "The stored GitHub token has been cleared.")
            self._update_publish_button_state()
            return

        try:
            encrypted_value = encrypt_secret(token)
        except Exception as exc:
            messagebox.showerror(
                "Encryption Error",
                f"Unable to store the GitHub token securely.\n{exc}",
            )
            return

        ConfigHelper.set("Gallery", "github_token", encrypted_value)
        self.gallery_client.set_token(token)
        messagebox.showinfo("GitHub Token", "Your GitHub token has been saved securely.")
        self._update_publish_button_state()

    def _github_token_button_label(self) -> str:
        return "Set GitHub Token…" if not self.gallery_client.can_publish else "Update GitHub Token…"

    def _update_publish_button_state(self):
        state = "normal" if self.gallery_client.can_publish else "disabled"
        try:
            self.publish_btn.configure(state=state)
        except Exception:
            pass
        try:
            self.github_token_btn.configure(text=self._github_token_button_label())
        except Exception:
            pass
        self._update_online_dialog_permissions()

    def _update_online_dialog_permissions(self):
        dialog = self._online_dialog
        if dialog and dialog.winfo_exists():
            try:
                dialog.update_permissions(self.gallery_client.can_publish)
            except Exception:
                pass

    def _download_gallery_bundle(self, bundle: GalleryBundleSummary, *, install_full_campaign: bool = False):
        temp_dir = Path(tempfile.mkdtemp(prefix="gallery_download_"))
        asset_name = bundle.asset_name or (bundle.tag or "bundle")
        asset_name = Path(asset_name).name
        if not asset_name.lower().endswith(".zip"):
            asset_name = f"{asset_name}.zip"
        archive_path = temp_dir / asset_name

        def worker(callback):
            try:
                return self.gallery_client.download_bundle(bundle, archive_path, progress_callback=callback)
            except Exception:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise

        def handle_success(path: Path):
            cleanup = lambda: shutil.rmtree(temp_dir, ignore_errors=True)
            if install_full_campaign:
                self._install_full_campaign_from_archive(bundle, path, cleanup=cleanup)
                return
            self._start_import_from_bundle(path, cleanup=cleanup)

        self._run_progress_task("Downloading Bundle", worker, None, None, on_success=handle_success)

    def _install_full_campaign_from_archive(
        self,
        bundle: Optional[GalleryBundleSummary],
        archive_path: Path,
        *,
        cleanup: Optional[Callable[[], None]] = None,
    ) -> None:
        default_name = bundle.source_campaign or bundle.display_title or Path(archive_path).stem
        folder_name = simpledialog.askstring(
            "Install Campaign",
            "Enter a folder name for the downloaded campaign:",
            parent=self,
            initialvalue=default_name,
        )
        if folder_name is None:
            if cleanup:
                cleanup()
            return

        folder_name = folder_name.strip()
        if not folder_name:
            messagebox.showwarning("Invalid Name", "Enter a non-empty folder name for the campaign.")
            if cleanup:
                cleanup()
            return

        parent_dir = (
            self.active_campaign.root.parent
            if self.active_campaign
            else Path(ConfigHelper.get_campaign_dir()).resolve()
        )
        if not parent_dir.exists():
            parent_dir = (
                self.active_campaign.root
                if self.active_campaign
                else Path(ConfigHelper.get_campaign_dir()).resolve()
            )
        target_dir = (parent_dir / folder_name).resolve()

        if target_dir.exists():
            if not messagebox.askyesno(
                "Replace Campaign",
                "A campaign with that name already exists.\n\nDo you want to replace it?",
            ):
                if cleanup:
                    cleanup()
                return
            try:
                shutil.rmtree(target_dir)
            except Exception as exc:
                messagebox.showerror(
                    "Unable to Replace Campaign",
                    f"Failed to remove the existing campaign directory.\n\n{exc}",
                )
                if cleanup:
                    cleanup()
                return

        def worker(callback):
            try:
                return install_full_campaign_bundle(archive_path, target_dir, progress_callback=callback)
            finally:
                if cleanup:
                    cleanup()

        def on_success(campaign: CampaignDatabase):
            messagebox.showinfo(
                "Campaign Installed",
                (
                    f"Campaign '{campaign.name}' has been installed.\n"
                    f"Location: {campaign.root}\n"
                    f"Database: {campaign.db_path.name}"
                ),
            )
            try:
                self.refresh_campaign_list()
            except Exception:
                pass

        self._run_progress_task(
            "Installing Campaign",
            worker,
            None,
            None,
            on_success=on_success,
        )

    def _delete_gallery_bundle(self, bundle: GalleryBundleSummary):
        def worker(callback):
            return self.gallery_client.delete_bundle(bundle, progress_callback=callback)

        def handle_success(_result):
            messagebox.showinfo(
                "Bundle Deleted",
                f"Bundle '{bundle.display_title}' has been removed from GitHub releases.",
            )
            self._refresh_online_dialog()

        self._run_progress_task("Deleting Bundle", worker, None, None, on_success=handle_success)

    def _post_copy(self, summary: dict):
        if hasattr(self.master, "refresh_entities"):
            try:
                self.master.refresh_entities()
            except Exception:
                pass
        messagebox.showinfo(
            "Copy Complete",
            (
                f"Assets imported: {summary.get('imported', 0)}\n"
                f"Assets updated: {summary.get('updated', 0)}\n"
                f"Assets skipped: {summary.get('skipped', 0)}"
            ),
        )

    def _gather_selected_records(self) -> Dict[str, List[dict]]:
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
        return selections

    def _gather_all_records(self) -> Dict[str, List[dict]]:
        return {
            entity_type: [copy.deepcopy(record) for record in records]
            for entity_type, records in self.entity_records.items()
            if records
        }

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
            details = str(exc).strip()
            if details:
                message = f"{exc.__class__.__name__}: {details}"
            else:
                message = repr(exc)
            messagebox.showerror("Operation Failed", message)

        def run():
            try:
                result = worker(update)
            except Exception as exc:
                log_exception(
                    f"Cross-campaign asset task failed: {exc}",
                    func_name="modules.generic.cross_campaign_asset_library._run_progress_task",
                )
                self.after(0, lambda exc=exc: handle_error(exc))
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


class OnlineGalleryDialog(ctk.CTkToplevel):
    def __init__(self, master, client: GithubGalleryClient, parent_window: CrossCampaignAssetLibraryWindow):
        super().__init__(master)
        self.client = client
        self.parent_window = parent_window
        self.title("Online Campaign Gallery")
        self.geometry("960x600")
        self.minsize(720, 480)
        self.transient(master)
        self.lift()
        self.focus_force()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(2, weight=2)

        self.tree = ttk.Treeview(
            self,
            columns=("title", "size", "published", "author"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("title", text="Bundle")
        self.tree.heading("size", text="Size")
        self.tree.heading("published", text="Published")
        self.tree.heading("author", text="Author")
        self.tree.column("title", width=380, anchor="w")
        self.tree.column("size", width=90, anchor="e")
        self.tree.column("published", width=160, anchor="w")
        self.tree.column("author", width=140, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))

        yscroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns", pady=(10, 0))

        detail_frame = ctk.CTkFrame(self)
        detail_frame.grid(row=0, column=2, sticky="nsew", padx=(10, 10), pady=(10, 0))
        detail_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(detail_frame, text="Details", font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, sticky="w", pady=(6, 4)
        )
        self.detail_text = ctk.CTkTextbox(detail_frame, wrap="word")
        self.detail_text.grid(row=1, column=0, sticky="nsew")
        self.detail_text.configure(state="disabled")

        button_bar = ctk.CTkFrame(self)
        button_bar.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(10, 10))
        button_bar.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.refresh_btn = ctk.CTkButton(button_bar, text="Refresh", command=self.refresh)
        self.refresh_btn.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        self.download_btn = ctk.CTkButton(button_bar, text="Download & Import…", command=self._download_selected)
        self.download_btn.grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        self.install_btn = ctk.CTkButton(button_bar, text="Download & Install Campaign…", command=self._install_selected)
        self.install_btn.grid(row=0, column=2, padx=6, pady=6, sticky="ew")
        self.delete_btn = ctk.CTkButton(button_bar, text="Delete from GitHub…", command=self._delete_selected)
        self.delete_btn.grid(row=0, column=3, padx=6, pady=6, sticky="ew")
        if not self.client.can_publish:
            self.delete_btn.configure(state="disabled")

        self.status_label = ctk.CTkLabel(self, text="", anchor="w")
        self.status_label.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._bundle_map: Dict[str, GalleryBundleSummary] = {}
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.after(150, self.refresh)

    # ----------------------------------------------------------------- Helpers
    def refresh(self):
        self.status_label.configure(text="Loading bundles…")
        self.tree.delete(*self.tree.get_children())
        self._bundle_map.clear()
        self._show_detail(None)

        def worker():
            try:
                bundles = self.client.list_bundles()
            except Exception as exc:
                self.after(0, lambda exc=exc: self._handle_error(exc))
                return
            self.after(0, lambda: self._populate(bundles))

        threading.Thread(target=worker, daemon=True).start()

    def _populate(self, bundles: List[GalleryBundleSummary]):
        if bundles:
            self.status_label.configure(text=f"Found {len(bundles)} bundle(s).")
        else:
            self.status_label.configure(text="No bundles available.")
        for bundle in bundles:
            iid = str(bundle.asset_id)
            self._bundle_map[iid] = bundle
            size_text = self._format_size(bundle.size)
            if bundle.published_at:
                published = bundle.published_at
                if published.tzinfo:
                    published = published.astimezone()
                date_text = published.strftime("%Y-%m-%d %H:%M:%S")
            else:
                date_text = "—"
            author_text = bundle.author or "—"
            self.tree.insert("", END, iid=iid, values=(bundle.display_title, size_text, date_text, author_text))

    def _handle_error(self, exc: Exception):
        self.status_label.configure(text=f"Failed to load bundles: {exc}")
        messagebox.showerror("Gallery Error", f"Unable to fetch GitHub releases.\n{exc}")

    def _on_select(self, _event):
        selection = self.tree.selection()
        if not selection:
            self._show_detail(None)
            return
        bundle = self._bundle_map.get(selection[0])
        self._show_detail(bundle)

    def _show_detail(self, bundle: Optional[GalleryBundleSummary]):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", END)
        if not bundle:
            self.detail_text.configure(state="disabled")
            return
        lines = [
            f"Release: {bundle.display_title}",
            f"Tag: {bundle.tag or '—'}",
            f"Author: {bundle.author or '—'}",
            f"Size: {self._format_size(bundle.size)}",
        ]
        if bundle.published_at:
            published = bundle.published_at
            if published.tzinfo:
                published = published.astimezone()
            lines.append(f"Published: {published.strftime('%Y-%m-%d %H:%M:%S %Z').strip()}")
        if bundle.asset_download_count:
            lines.append(f"Downloads: {bundle.asset_download_count}")
        if bundle.source_campaign:
            lines.append(f"Source campaign: {bundle.source_campaign}")
        if bundle.entity_counts:
            lines.append("")
            lines.append("Entities:")
            for entity_type, count in sorted(bundle.entity_counts.items()):
                lines.append(f"  {entity_type}: {count}")
        if bundle.description:
            lines.append("")
            lines.append(bundle.description)
        lines.append("")
        lines.append(f"Download URL: {bundle.download_url}")
        self.detail_text.insert("1.0", "\n".join(lines))
        self.detail_text.configure(state="disabled")

    def _download_selected(self):
        bundle = self._current_selection()
        if not bundle:
            messagebox.showinfo("No Selection", "Select a bundle to download.")
            return
        self.parent_window._download_gallery_bundle(bundle)

    def _install_selected(self):
        bundle = self._current_selection()
        if not bundle:
            messagebox.showinfo("No Selection", "Select a bundle to install.")
            return
        self.parent_window._download_gallery_bundle(bundle, install_full_campaign=True)

    def _delete_selected(self):
        if not self.client.can_publish:
            messagebox.showerror("Unavailable", "Configure a GitHub token to delete bundles.")
            return
        bundle = self._current_selection()
        if not bundle:
            messagebox.showinfo("No Selection", "Select a bundle to delete.")
            return
        confirm = messagebox.askyesno(
            "Delete Bundle",
            f"Remove '{bundle.display_title}' from GitHub releases?",
            parent=self,
        )
        if not confirm:
            return
        self.parent_window._delete_gallery_bundle(bundle)

    def _current_selection(self) -> Optional[GalleryBundleSummary]:
        selection = self.tree.selection()
        if not selection:
            return None
        return self._bundle_map.get(selection[0])

    def _on_close(self):
        try:
            self.parent_window._online_dialog = None
        except Exception:
            pass
        self.destroy()

    @staticmethod
    def _format_size(size: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
            value /= 1024

    def update_permissions(self, can_publish: bool) -> None:
        state = "normal" if can_publish else "disabled"
        try:
            self.delete_btn.configure(state=state)
        except Exception:
            pass
