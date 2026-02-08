import os
import re
import sqlite3
from difflib import SequenceMatcher
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_exception, log_info, log_module_import
from modules.helpers.window_helper import position_window_at_top

log_module_import(__name__)


class PortraitPreview(ctk.CTkFrame):
    """Display helper that keeps portrait previews crisp and centered."""

    def __init__(self, parent, placeholder: str = "Portrait preview"):
        super().__init__(parent)
        self.configure(fg_color=("#1e1e1e", "#1e1e1e"))
        self._label = ctk.CTkLabel(
            self,
            text=placeholder,
            justify="center",
            anchor="center",
            wraplength=320,
        )
        self._label.pack(fill="both", expand=True, padx=10, pady=10)
        self._placeholder = placeholder
        self._original_image: Image.Image | None = None
        self._photo_image: ImageTk.PhotoImage | None = None
        self._original_size: tuple[int, int] | None = None
        self.bind("<Configure>", self._on_resize)

    def clear(self):
        self._original_image = None
        self._photo_image = None
        self._original_size = None
        self._label.configure(text=self._placeholder, image="")
        self._label.image = None

    def show_error(self, message: str):
        self._original_image = None
        self._photo_image = None
        self._original_size = None
        self._label.configure(text=message, image="")
        self._label.image = None

    def display_image(self, path: str) -> tuple[int, int] | None:
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA")
                self._original_image = img.copy()
                self._original_size = img.size
        except Exception as exc:  # pragma: no cover - best effort UI feedback
            self.show_error(f"Unable to load preview:\n{exc}")
            return None

        self._update_display()
        return self._original_size

    def _on_resize(self, _event=None):
        if self._original_image is not None:
            self._update_display()

    def _update_display(self):
        if self._original_image is None:
            return

        width = max(self.winfo_width() - 20, 50)
        height = max(self.winfo_height() - 20, 50)
        target_size = (width, height)
        rendered = ImageOps.contain(
            self._original_image,
            target_size,
            Image.Resampling.LANCZOS,
        )
        self._photo_image = ImageTk.PhotoImage(rendered)
        self._label.configure(image=self._photo_image, text="")
        self._label.image = self._photo_image


class PortraitImportReviewWindow:
    """Interactive window that lets users review and assign portrait matches."""

    def __init__(
        self,
        parent,
        entity_review_data: list[dict],
        replace_existing: bool,
        copy_and_resize_callback,
    ) -> None:
        self.parent = parent
        self.entity_review_data = entity_review_data
        self.replace_existing = replace_existing
        self.copy_and_resize_portrait = copy_and_resize_callback

        self.window = ctk.CTkToplevel(parent)
        self.window.title("Portrait Import Review")
        self.window.geometry("1020x620")
        self.window.minsize(900, 520)
        position_window_at_top(self.window)

        self.tree_records: dict[str, dict] = {}
        self.match_index_map: list[dict] = []
        self.current_entity: dict | None = None

        self._build_ui()
        self._populate_entities()
        self.window.bind("<Escape>", lambda _event: self.window.destroy())

        # Preselect the first entity that has matches to streamline the workflow.
        for record in self.entity_review_data:
            if record.get("matches"):
                self._show_entity_details(record)
                if record.get("tree_id"):
                    self.tree.selection_set(record["tree_id"])
                    self.tree.focus(record["tree_id"])
                break

    def _build_ui(self):
        container = ctk.CTkFrame(self.window)
        container.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(2, weight=1)

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        title_font = ctk.CTkFont(size=18, weight="bold")
        subtitle_font = ctk.CTkFont(size=13)

        header = ctk.CTkLabel(
            container,
            text="Review portrait matches",
            font=title_font,
            anchor="w",
        )
        header.grid(row=0, column=0, columnspan=2, sticky="w")

        subheader = ctk.CTkLabel(
            container,
            text=(
                "Double-click an entity to inspect potential portraits. Use the similarity slider to widen or "
                "narrow the suggestions and double-click a portrait to assign it."
            ),
            font=subtitle_font,
            justify="left",
            wraplength=880,
            anchor="w",
        )
        subheader.grid(row=1, column=0, columnspan=2, sticky="we", pady=(4, 12))

        self._build_entity_panel(container)
        self._build_detail_panel(container)

    def _build_entity_panel(self, container):
        left_frame = ctk.CTkFrame(container)
        left_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        left_label = ctk.CTkLabel(left_frame, text="Entities", anchor="w")
        left_label.grid(row=0, column=0, sticky="we")

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover - depends on environment
            pass
        style.configure(
            "PortraitReview.Treeview",
            background="#1e1e1e",
            fieldbackground="#1e1e1e",
            foreground="#f2f2f2",
            bordercolor="#2a2a2a",
            rowheight=26,
        )
        style.configure(
            "PortraitReview.Treeview.Heading",
            background="#2a2a2a",
            foreground="#f2f2f2",
            relief="flat",
        )
        style.map(
            "PortraitReview.Treeview",
            background=[("selected", "#3a7ebf")],
            foreground=[("selected", "#ffffff")],
        )

        columns = ("type", "name", "score", "status")
        self.tree = ttk.Treeview(
            left_frame,
            columns=columns,
            show="headings",
            style="PortraitReview.Treeview",
            selectmode="browse",
        )
        self.tree.heading("type", text="Type")
        self.tree.heading("name", text="Name")
        self.tree.heading("score", text="Best match")
        self.tree.heading("status", text="Status")
        self.tree.column("type", width=120, anchor="w")
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("score", width=110, anchor="center")
        self.tree.column("status", width=240, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew")

        tree_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)

        left_hint = ctk.CTkLabel(
            left_frame,
            text="Tip: double-click an entity to load suggested portraits.",
            anchor="w",
            wraplength=360,
            justify="left",
        )
        left_hint.grid(row=2, column=0, columnspan=2, sticky="we", pady=(6, 0))

        self.tree.tag_configure("auto", foreground="#7bcf8d")
        self.tree.tag_configure("manual", foreground="#80caff")
        self.tree.tag_configure("skipped", foreground="#f4c77f")
        self.tree.tag_configure("error", foreground="#f28b82")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

    def _build_detail_panel(self, container):
        detail_frame = ctk.CTkFrame(container)
        detail_frame.grid(row=2, column=1, sticky="nsew")
        detail_frame.grid_columnconfigure(0, weight=1)
        detail_frame.grid_rowconfigure(4, weight=0)
        detail_frame.grid_rowconfigure(6, weight=1)

        self.entity_title_label = ctk.CTkLabel(
            detail_frame,
            text="Select an entity to review matches.",
            font=ctk.CTkFont(size=16, weight="bold"),
            justify="left",
            wraplength=360,
            anchor="w",
        )
        self.entity_title_label.grid(row=0, column=0, sticky="we")

        self.detail_status_label = ctk.CTkLabel(
            detail_frame,
            text="",
            justify="left",
            wraplength=360,
            anchor="w",
        )
        self.detail_status_label.grid(row=1, column=0, sticky="we", pady=(4, 6))

        similarity_frame = ctk.CTkFrame(detail_frame)
        similarity_frame.grid(row=2, column=0, sticky="we")
        similarity_frame.grid_columnconfigure(1, weight=1)

        similarity_label = ctk.CTkLabel(similarity_frame, text="Similarity threshold:")
        similarity_label.grid(row=0, column=0, padx=(0, 6), sticky="w")

        self.threshold_var = tk.DoubleVar(value=85.0)
        self.threshold_display = ctk.CTkLabel(similarity_frame, text="85%")
        self.threshold_display.grid(row=0, column=3, sticky="e")

        self.slider = ttk.Scale(
            similarity_frame,
            from_=50,
            to=100,
            orient="horizontal",
            command=self._on_slider_change,
        )
        self.slider.grid(row=0, column=1, sticky="we")

        self.threshold_spin = tk.Spinbox(
            similarity_frame,
            from_=50,
            to=100,
            textvariable=self.threshold_var,
            width=5,
            command=self._on_spin_change,
        )
        self.threshold_spin.grid(row=0, column=2, padx=(8, 6))
        self.threshold_spin.bind("<Return>", lambda _event: self._on_spin_change())
        self.threshold_spin.bind("<FocusOut>", lambda _event: self._on_spin_change())

        self.matches_label = ctk.CTkLabel(detail_frame, text="Suggested portraits", anchor="w")
        self.matches_label.grid(row=3, column=0, sticky="we", pady=(10, 4))

        matches_frame = tk.Frame(
            detail_frame,
            bg="#1e1e1e",
            highlightthickness=1,
            highlightbackground="#2a2a2a",
        )
        matches_frame.grid(row=4, column=0, sticky="nsew")
        matches_frame.grid_columnconfigure(0, weight=1)
        matches_frame.grid_rowconfigure(0, weight=1)

        self.match_listbox = tk.Listbox(
            matches_frame,
            activestyle="none",
            selectmode="browse",
            exportselection=False,
            bg="#1e1e1e",
            fg="#f2f2f2",
            highlightthickness=0,
            selectbackground="#3a7ebf",
            selectforeground="#ffffff",
            height=6,
        )
        self.match_listbox.grid(row=0, column=0, sticky="nsew")

        match_scroll = tk.Scrollbar(matches_frame, orient="vertical", command=self.match_listbox.yview)
        match_scroll.grid(row=0, column=1, sticky="ns")
        self.match_listbox.configure(yscrollcommand=match_scroll.set)

        self.match_info_label = ctk.CTkLabel(
            detail_frame,
            text="Select a portrait to preview.",
            justify="left",
            wraplength=360,
            anchor="w",
        )
        self.match_info_label.grid(row=5, column=0, sticky="we", pady=(8, 6))

        self.preview = PortraitPreview(detail_frame)
        self.preview.grid(row=6, column=0, sticky="nsew")

        self.assign_button = ctk.CTkButton(
            detail_frame,
            text="Assign Selected Portrait",
            command=self._assign_selected_portrait,
            state="disabled",
        )
        self.assign_button.grid(row=7, column=0, sticky="we", pady=(12, 6))

        detail_hint_label = ctk.CTkLabel(
            detail_frame,
            text="Tip: double-click a portrait in the list to assign it instantly.",
            wraplength=360,
            justify="left",
            anchor="w",
        )
        detail_hint_label.grid(row=8, column=0, sticky="we")

        self.match_listbox.bind("<<ListboxSelect>>", self._on_match_select)
        self.match_listbox.bind("<Double-Button-1>", self._assign_selected_portrait)

        # Ensure the slider reflects the default threshold once dependent widgets exist.
        self.slider.set(self.threshold_var.get())

    def _populate_entities(self):
        for record in self.entity_review_data:
            score_text = (
                f"{record.get('best_score', 0) * 100:.1f}%" if record.get("best_score") else "—"
            )
            status_text = record.get("status") or "Ready to review"
            lowered = status_text.lower()
            tags = []
            if "error" in lowered:
                tags.append("error")
            elif "assigned manually" in lowered:
                tags.append("manual")
            elif "imported automatically" in lowered:
                tags.append("auto")
            elif "skipped" in lowered or "no match" in lowered:
                tags.append("skipped")

            tree_id = self.tree.insert(
                "",
                "end",
                values=(record.get("display_table"), record.get("name"), score_text, status_text),
                tags=tags if tags else ("default",),
            )
            record["tree_id"] = tree_id
            self.tree_records[tree_id] = record

    def _on_slider_change(self, value):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return
        self.threshold_var.set(numeric)
        self._update_threshold_label(numeric)
        self._populate_match_list()

    def _on_spin_change(self):
        try:
            numeric = float(self.threshold_var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        numeric = min(max(numeric, 50.0), 100.0)
        self.threshold_var.set(numeric)
        self.slider.set(numeric)
        self._update_threshold_label(numeric)
        self._populate_match_list()

    def _update_threshold_label(self, value):
        self.threshold_display.configure(text=f"{float(value):.0f}%")

    def _populate_match_list(self):
        self.match_listbox.delete(0, "end")
        self.match_index_map = []
        self.assign_button.configure(state="disabled")
        self.preview.clear()

        if self.current_entity is None:
            self.match_info_label.configure(text="Select an entity to see suggested portraits.")
            return

        matches = self.current_entity.get("matches") or []
        if not matches:
            self.match_info_label.configure(text="No portrait suggestions are available for this entity.")
            return

        try:
            threshold = float(self.threshold_var.get()) / 100.0
        except (TypeError, ValueError, tk.TclError):
            threshold = 0.85

        filtered = [m for m in matches if m.get("score", 0) >= threshold]
        if not filtered:
            filtered = matches[:5]
            if filtered:
                self.match_info_label.configure(
                    text="No portraits meet the chosen threshold. Showing the closest matches instead."
                )
            else:
                self.match_info_label.configure(
                    text="No portrait suggestions are available for this entity."
                )
        else:
            self.match_info_label.configure(
                text=f"Showing {len(filtered)} portrait(s) with ≥{self.threshold_var.get():.0f}% similarity."
            )

        for match in filtered:
            entry_text = f"{match.get('score', 0) * 100:.1f}% · {match.get('display')}"
            self.match_listbox.insert("end", entry_text)
            self.match_index_map.append(match)

        if self.match_index_map:
            self.match_listbox.selection_set(0)
            self._on_match_select()

    def _on_match_select(self, _event=None):
        selection = self.match_listbox.curselection()
        if not selection:
            self.assign_button.configure(state="disabled")
            self.match_info_label.configure(text="Select a portrait to preview.")
            self.preview.clear()
            return

        match = self.match_index_map[selection[0]]
        self.assign_button.configure(state="normal")
        rel_path = match.get("relative") or os.path.basename(match.get("path", ""))
        size = self.preview.display_image(match.get("path", ""))
        if size:
            size_text = f"{size[0]}×{size[1]} px"
        else:
            size_text = "Unable to display preview"
        self.match_info_label.configure(
            text=f"{match.get('score', 0) * 100:.1f}% similarity\n{rel_path}\n{size_text}"
        )

    def _show_entity_details(self, record: dict | None):
        self.current_entity = record
        if not record:
            self.entity_title_label.configure(text="Select an entity to review matches.")
            self.detail_status_label.configure(text="")
            self.match_info_label.configure(text="Select a portrait to preview.")
            self.match_listbox.delete(0, "end")
            self.assign_button.configure(state="disabled")
            self.preview.clear()
            return

        self.entity_title_label.configure(
            text=f"{record.get('display_table')}: {record.get('name')}"
        )
        self.detail_status_label.configure(text=record.get("status") or "Ready to review")

        default_threshold = 85.0
        if record.get("best_score"):
            default_threshold = min(100.0, max(50.0, round(record["best_score"] * 100)))

        self.threshold_var.set(default_threshold)
        self.slider.set(default_threshold)
        self._update_threshold_label(default_threshold)
        self._populate_match_list()

    def _on_tree_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        record = self.tree_records.get(selection[0])
        self._show_entity_details(record)

    def _on_tree_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self._show_entity_details(self.tree_records.get(item_id))

    def _assign_selected_portrait(self, _event=None):
        if self.current_entity is None:
            return

        selection = self.match_listbox.curselection()
        if not selection:
            return

        match = self.match_index_map[selection[0]]
        target_path = match.get("path")
        if not target_path:
            return

        if (
            self.current_entity.get("existing_portrait")
            and not self.replace_existing
            and not self.current_entity.get("applied_path")
        ):
            confirm = messagebox.askyesno(
                "Replace Portrait?",
                (
                    f"{self.current_entity.get('display_table')} '{self.current_entity.get('name')}' already has a portrait.\n"
                    "Do you want to replace it with the selected one?"
                ),
            )
            if not confirm:
                return

        try:
            new_path = self.copy_and_resize_portrait(
                {"Name": self.current_entity.get("name", "Unnamed")},
                target_path,
            )
        except Exception as exc:  # pragma: no cover - user feedback path
            messagebox.showerror(
                "Import Portraits",
                f"Failed to copy portrait:\n{exc}",
            )
            return

        try:
            db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db")
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    f"UPDATE {self.current_entity['table']} SET Portrait = ? WHERE {self.current_entity['key_field']} = ?",
                    (new_path, self.current_entity.get("name")),
                )
                conn.commit()
        except Exception as exc:  # pragma: no cover - user feedback path
            messagebox.showerror(
                "Import Portraits",
                f"Failed to save portrait to the database:\n{exc}",
            )
            return

        self.current_entity["status"] = f"Assigned manually ({match.get('score', 0) * 100:.1f}%)"
        self.current_entity["applied_path"] = new_path
        self.current_entity["applied_source"] = target_path
        self.current_entity["applied_score"] = match.get("score", 0)
        self.current_entity["existing_portrait"] = new_path

        self.detail_status_label.configure(text=self.current_entity["status"])
        rel_path = match.get("relative") or os.path.basename(target_path)
        self.match_info_label.configure(
            text=f"Assigned portrait ({match.get('score', 0) * 100:.1f}% match)\n{rel_path}"
        )

        self.tree.set(self.current_entity["tree_id"], "status", self.current_entity["status"])
        self.tree.set(
            self.current_entity["tree_id"],
            "score",
            f"{match.get('score', 0) * 100:.1f}%",
        )
        self.tree.item(self.current_entity["tree_id"], tags=("manual",))
        self.assign_button.configure(state="disabled")


class PortraitImporter:
    """High level workflow for importing portraits from a directory."""

    def __init__(self, main_window) -> None:
        self.main_window = main_window

    def import_portraits_from_directory(self):
        """Match and import portraits from a directory for all portrait-capable entities."""

        directory = filedialog.askdirectory(title="Select Portrait Directory")
        if not directory:
            log_info(
                "Portrait import cancelled: no directory selected",
                func_name="portrait_importer.PortraitImporter.import_portraits_from_directory",
            )
            return

        supported_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
        image_candidates: list[dict] = []

        for root, _dirs, files in os.walk(directory):
            for file_name in files:
                ext = os.path.splitext(file_name)[1].lower()
                if ext not in supported_exts:
                    continue
                base_name = os.path.splitext(file_name)[0]
                normalized = self.main_window.normalize_name(base_name)
                cleaned = re.sub(
                    r"\b(portrait|token|image|img|picture|photo|pic)\b",
                    " ",
                    normalized,
                )
                cleaned = " ".join(cleaned.split())
                candidate = cleaned or normalized
                if not candidate:
                    continue

                path = os.path.join(root, file_name)
                image_candidates.append(
                    {
                        "normalized": candidate,
                        "compact": candidate.replace(" ", ""),
                        "path": path,
                        "display": file_name,
                        "relative": os.path.relpath(path, directory),
                    }
                )

        if not image_candidates:
            log_info(
                "Portrait import aborted: no compatible images discovered",
                func_name="portrait_importer.PortraitImporter.import_portraits_from_directory",
            )
            messagebox.showinfo(
                "Import Portraits",
                "No image files were found in the selected directory.",
            )
            return

        replace_existing = messagebox.askyesno(
            "Import Portraits",
            "Replace existing portraits when a match is found?\n\n"
            "Choose 'Yes' to overwrite existing portraits, or 'No' to update only missing ones.",
            icon="question",
            default="no",
        )

        entity_configs = [
            ("npcs", "Name"),
            ("pcs", "Name"),
            ("creatures", "Name"),
            ("places", "Name"),
            ("objects", "Name"),
            ("clues", "Name"),
            ("factions", "Name"),
        ]
        display_names = {
            "npcs": "NPCs",
            "pcs": "PCs",
            "creatures": "Creatures",
            "places": "Places",
            "objects": "Objects",
            "clues": "Clues",
            "factions": "Factions",
        }

        def compute_matches(normalized_name: str) -> list[dict]:
            matches: list[dict] = []
            if not normalized_name:
                return matches

            compact_name = normalized_name.replace(" ", "")
            for candidate in image_candidates:
                score_full = SequenceMatcher(
                    None,
                    normalized_name,
                    candidate["normalized"],
                ).ratio()
                if compact_name:
                    score_compact = SequenceMatcher(
                        None,
                        compact_name,
                        candidate["compact"],
                    ).ratio()
                else:
                    score_compact = score_full
                score = max(score_full, score_compact)
                matches.append(
                    {
                        "score": score,
                        "path": candidate["path"],
                        "display": candidate["display"],
                        "relative": candidate["relative"],
                        "normalized": candidate["normalized"],
                    }
                )

            matches.sort(key=lambda item: item["score"], reverse=True)
            return matches[:20]

        entity_review_data: list[dict] = []

        db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        total_updates = 0
        skipped_existing = 0
        skipped_low_score = 0
        per_entity_updates: list[str] = []

        try:
            cursor = conn.cursor()
            for table, key_field in entity_configs:
                cursor.execute(f"SELECT {key_field}, Portrait FROM {table}")
                rows = cursor.fetchall()
                updated_here = 0
                for row in rows:
                    raw_name = row[key_field]
                    if raw_name is None:
                        continue
                    name = str(raw_name).strip()
                    if not name:
                        continue
                    existing_portrait = str(row["Portrait"] or "").strip()
                    normalized_name = self.main_window.normalize_name(name)
                    matches = compute_matches(normalized_name)
                    best_match = matches[0] if matches else None
                    best_score = best_match["score"] if best_match else 0.0

                    entity_record = {
                        "table": table,
                        "key_field": key_field,
                        "display_table": display_names.get(table, table.title()),
                        "name": name,
                        "existing_portrait": existing_portrait,
                        "matches": matches,
                        "best_score": best_score,
                        "best_source": best_match["path"] if best_match else "",
                        "status": "Ready to review" if matches else "No portrait suggestions",
                    }
                    entity_review_data.append(entity_record)

                    if existing_portrait and not replace_existing:
                        skipped_existing += 1
                        entity_record["status"] = "Skipped (existing portrait)"
                        continue

                    if not best_match or best_score < 0.85:
                        skipped_low_score += 1
                        if not matches:
                            entity_record["status"] = "No portrait suggestions"
                        else:
                            entity_record["status"] = "No match ≥85%"
                        continue

                    try:
                        new_path = self.main_window.copy_and_resize_portrait({"Name": name}, best_match["path"])
                    except Exception as exc:
                        log_exception(
                            f"Failed to copy portrait for {name}: {exc}",
                            func_name="portrait_importer.PortraitImporter.import_portraits_from_directory",
                        )
                        entity_record["status"] = f"Error importing ({exc})"
                        continue

                    cursor.execute(
                        f"UPDATE {table} SET Portrait = ? WHERE {key_field} = ?",
                        (new_path, name),
                    )
                    updated_here += 1
                    total_updates += 1
                    entity_record["status"] = f"Imported automatically ({best_score * 100:.1f}%)"
                    entity_record["applied_path"] = new_path
                    entity_record["applied_source"] = best_match["path"]
                    entity_record["applied_score"] = best_score
                    log_info(
                        f"Imported portrait for {display_names.get(table, table.title())} '{name}' (score {best_score * 100:.1f}%)",
                        func_name="portrait_importer.PortraitImporter.import_portraits_from_directory",
                    )

                if updated_here:
                    per_entity_updates.append(
                        f"{display_names.get(table, table.title())}: {updated_here}"
                    )

            if total_updates:
                conn.commit()
            else:
                conn.rollback()

        except Exception as exc:
            conn.rollback()
            log_exception(
                f"Portrait import failed: {exc}",
                func_name="portrait_importer.PortraitImporter.import_portraits_from_directory",
            )
            messagebox.showerror(
                "Import Portraits",
                f"Portrait import failed:\n{exc}",
            )
            return
        finally:
            conn.close()

        if total_updates:
            log_info(
                f"Imported {total_updates} portraits from directory {directory}",
                func_name="portrait_importer.PortraitImporter.import_portraits_from_directory",
            )
            summary_lines = [
                "Imported portraits for the following entities:",
                *per_entity_updates,
            ]
            if not per_entity_updates:
                summary_lines.append("(No entities were updated despite successful matches.)")
            if skipped_existing and not replace_existing:
                summary_lines.append(
                    f"Skipped {skipped_existing} entries that already had portraits."
                )
            if skipped_low_score:
                summary_lines.append(
                    f"Skipped {skipped_low_score} entries without a ≥85% name match."
                )
            if image_candidates:
                summary_lines.append(
                    "Review and fine-tune matches in the portrait matcher window that opens next."
                )
            messagebox.showinfo("Import Portraits", "\n".join(summary_lines))
        else:
            log_info(
                "No portraits met the similarity threshold during import",
                func_name="portrait_importer.PortraitImporter.import_portraits_from_directory",
            )
            details: list[str] = []
            if skipped_existing and not replace_existing:
                details.append(
                    f"{skipped_existing} entities already had portraits (not replaced)."
                )
            if skipped_low_score:
                details.append(
                    f"{skipped_low_score} entities had no image above the 85% similarity threshold."
                )
            if not details:
                details.append(
                    "Ensure image file names closely match entity names (≥85% similarity)."
                )
            elif image_candidates:
                details.append(
                    "Adjust matches manually in the review window that opens next."
                )
            messagebox.showinfo("Import Portraits", "\n".join(details))

        if image_candidates and entity_review_data:
            PortraitImportReviewWindow(
                self.main_window,
                entity_review_data,
                replace_existing,
                self.main_window.copy_and_resize_portrait,
            )
