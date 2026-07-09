"""Dialog for managing portraits of entities linked to a scenario."""
from __future__ import annotations
from pathlib import Path
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageGrab
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.portrait_helper import parse_portrait_value, primary_portrait, resolve_portrait_path
from modules.helpers.template_loader import load_template
from modules.ui.image_browser_dialog import ImageBrowserDialog
from modules.ui.webview.pywebview_client import PyWebviewClient
from modules.generic.portrait_manager.entity_portrait_actions import ScenarioPortraitEntity, campaign_relative_path, copy_portrait_to_campaign, missing_portrait_indices, portrait_status, set_entity_portraits

class ScenarioPortraitManagerDialog(ctk.CTkToplevel):
    """Manage portraits for all entities referenced by one scenario."""
    def __init__(self, master, *, scenario: dict, entities: list[ScenarioPortraitEntity], on_change=None):
        super().__init__(master)
        self.scenario = scenario
        self.entities = entities
        self.on_change = on_change
        self.current_index = 0 if entities else -1
        self._preview_image = None
        self._row_ids: dict[int, str] = {}
        self.title(f"Scenario Portraits - {scenario.get('Title', 'Scenario')}")
        self.geometry("980x640")
        self.transient(master)
        self._build_ui()
        self._refresh_all()
        if self.entities:
            self._select_index(0)

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(header, text="Generate and manage portraits for linked scenario entities", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=12, pady=6)
        ctk.CTkButton(nav, text="Previous missing", command=self.previous_missing).pack(side="left", padx=4)
        ctk.CTkButton(nav, text="Next missing", command=self.next_missing).pack(side="left", padx=4)
        ctk.CTkButton(nav, text="Skip", command=self.next_missing).pack(side="left", padx=4)
        self.missing_label = ctk.CTkLabel(nav, text="")
        self.missing_label.pack(side="left", padx=12)
        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=12, pady=6)
        self.tree = ttk.Treeview(body, columns=("type", "name", "status", "preview"), show="headings", height=14)
        for column, label, width in (("type", "Entity Type", 120), ("name", "Entity Name", 240), ("status", "Portrait Status", 130), ("preview", "Current Portrait", 300)):
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        right = ctk.CTkFrame(body)
        right.pack(side="right", fill="y", padx=(8, 0), pady=8)
        self.preview_label = ctk.CTkLabel(right, text="[No Portrait]", width=256, height=256)
        self.preview_label.pack(padx=8, pady=8)
        self.detail_label = ctk.CTkLabel(right, text="", justify="left")
        self.detail_label.pack(fill="x", padx=8, pady=(0, 8))
        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=4)
        for label, command in (("Add", self.add_portrait), ("Search", self.search_portrait), ("Image Library", self.open_image_library), ("Paste", self.paste_portrait), ("Create Portrait", self.create_portrait), ("Primary", self.make_primary), ("Remove", self.remove_portrait)):
            ctk.CTkButton(actions, text=label, command=command, width=118).pack(fill="x", pady=3)

    def _entity(self):
        if 0 <= self.current_index < len(self.entities):
            return self.entities[self.current_index]
        return None

    def _refresh_all(self):
        self.tree.delete(*self.tree.get_children())
        self._row_ids.clear()
        for index, entity in enumerate(self.entities):
            paths = parse_portrait_value(entity.record.get("Portrait", ""))
            primary = primary_portrait(paths)
            row_id = self.tree.insert("", "end", values=(entity.entity_type, entity.name, portrait_status(entity.record), primary or "[No Portrait]"))
            self._row_ids[index] = row_id
        self._refresh_missing_label()

    def _refresh_current(self):
        entity = self._entity()
        if not entity:
            return
        row_id = self._row_ids.get(self.current_index)
        paths = parse_portrait_value(entity.record.get("Portrait", ""))
        primary = primary_portrait(paths)
        if row_id:
            self.tree.item(row_id, values=(entity.entity_type, entity.name, portrait_status(entity.record), primary or "[No Portrait]"))
        self._refresh_preview()
        self._refresh_missing_label()
        if callable(self.on_change):
            self.on_change(entity)

    def _refresh_missing_label(self):
        missing = missing_portrait_indices(self.entities)
        self.missing_label.configure(text=f"Missing portraits: {len(missing)} / {len(self.entities)}")

    def _select_index(self, index: int):
        if not self.entities:
            return
        self.current_index = max(0, min(index, len(self.entities) - 1))
        row_id = self._row_ids.get(self.current_index)
        if row_id:
            self.tree.selection_set(row_id)
            self.tree.see(row_id)
        self._refresh_preview()

    def _on_tree_select(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        for index, row_id in self._row_ids.items():
            if row_id == selected[0]:
                self.current_index = index
                break
        self._refresh_preview()

    def _refresh_preview(self):
        entity = self._entity()
        if not entity:
            self.preview_label.configure(image=None, text="[No Portrait]")
            return
        self.detail_label.configure(text=f"{entity.entity_type}: {entity.name}\nSource: {entity.source_field}")
        primary = primary_portrait(parse_portrait_value(entity.record.get("Portrait", "")))
        resolved = resolve_portrait_path(primary, ConfigHelper.get_campaign_dir()) if primary else None
        try:
            if resolved and Path(resolved).exists():
                image = Image.open(resolved).resize((256, 256))
                self._preview_image = ctk.CTkImage(light_image=image, size=(256, 256))
                self.preview_label.configure(image=self._preview_image, text="")
                return
        except Exception:
            pass
        self._preview_image = None
        self.preview_label.configure(image=None, text="[No Portrait]")

    def _paths(self) -> list[str]:
        entity = self._entity()
        return list(parse_portrait_value(entity.record.get("Portrait", ""))) if entity else []

    def _save_paths(self, paths: list[str]):
        entity = self._entity()
        if not entity:
            return
        set_entity_portraits(entity, paths)
        self._refresh_current()

    def previous_missing(self):
        self._move_missing(-1)

    def next_missing(self):
        self._move_missing(1)

    def _move_missing(self, direction: int):
        missing = missing_portrait_indices(self.entities)
        if not missing:
            return
        if self.current_index not in missing:
            target = missing[0] if direction >= 0 else missing[-1]
        else:
            pos = missing.index(self.current_index)
            target = missing[(pos + direction) % len(missing)]
        self._select_index(target)

    def add_portrait(self):
        entity = self._entity()
        if not entity:
            return
        paths = filedialog.askopenfilenames(title="Select Portrait Image(s)", filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp"), ("All Files", "*.*")])
        current = self._paths()
        for path in paths:
            if Path(path).is_file():
                current.append(copy_portrait_to_campaign(path, entity.name))
        self._save_paths(current)

    def search_portrait(self):
        entity = self._entity()
        if entity:
            PyWebviewClient(title="Image Browser").open(ImageBrowserDialog.build_search_url(entity.name))

    def open_image_library(self):
        opener = self._resolve_image_library_opener()
        entity = self._entity()
        if not callable(opener) or not entity:
            messagebox.showerror("Image Library", "Image library is unavailable from this window.")
            return
        opener(search_query=entity.name, on_attach_to_entity=self._attach_from_library)

    def _resolve_image_library_opener(self):
        widget = self.master
        while widget is not None:
            opener = getattr(widget, "open_image_library_browser", None)
            if callable(opener):
                return opener
            widget = getattr(widget, "master", None) or getattr(widget, "parent", None)
        return None

    def _attach_from_library(self, image_result):
        entity = self._entity()
        source = str(getattr(image_result, "path", image_result))
        if entity and Path(source).is_file():
            self._save_paths(self._paths() + [copy_portrait_to_campaign(source, entity.name)])

    def paste_portrait(self):
        entity = self._entity()
        if not entity:
            return
        data = ImageGrab.grabclipboard()
        if isinstance(data, list):
            for path in data:
                if Path(path).is_file():
                    self._save_paths(self._paths() + [copy_portrait_to_campaign(path, entity.name)])
                    return
        if isinstance(data, Image.Image):
            folder = Path(ConfigHelper.get_campaign_dir()) / "assets" / "portraits"
            folder.mkdir(parents=True, exist_ok=True)
            dest = folder / f"{entity.name.replace(' ', '_')}_{id(self)}.png"
            data.save(dest, format="PNG")
            self._save_paths(self._paths() + [campaign_relative_path(str(dest))])
            return
        messagebox.showinfo("Paste Portrait", "No image found in clipboard.")

    def create_portrait(self):
        entity = self._entity()
        if not entity:
            return
        from modules.generic.generic_editor_window import GenericEditorWindow

        try:
            template = load_template(entity.entity_type)
        except Exception as exc:
            messagebox.showerror(
                "Create Portrait",
                f"Unable to load editor template for '{entity.entity_type}': {exc}",
            )
            return

        editor = GenericEditorWindow(self, entity.record, template, entity.wrapper)
        editor.create_portrait_with_swarmui()
        self.wait_window(editor)
        if getattr(editor, "saved", False):
            entity.wrapper.save_item(entity.record)
        self._refresh_current()

    def make_primary(self):
        paths = self._paths()
        if len(paths) > 1:
            self._save_paths([paths[-1], *paths[:-1]])

    def remove_portrait(self):
        paths = self._paths()
        if paths:
            self._save_paths(paths[1:])
