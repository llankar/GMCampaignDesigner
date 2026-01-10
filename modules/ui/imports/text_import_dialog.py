from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from modules.generic.generic_editor_window import GenericEditorWindow
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import (
    log_exception,
    log_function,
    log_methods,
    log_module_import,
)
from modules.helpers.template_loader import load_template
from modules.ui.imports.text_import_mappings import (
    build_source_metadata,
    extract_default_name,
    list_target_labels,
    target_for_label,
    target_for_slug,
)

log_module_import(__name__)


@log_methods
class TextImportDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        *,
        source_text: str,
        source_url: str | None = None,
        default_target_slug: str | None = None,
        on_complete=None,
    ):
        super().__init__(master)
        self.source_text = source_text or ""
        self.source_url = source_url or ""
        self.default_target_slug = default_target_slug
        self.on_complete = on_complete
        self._init_state()
        self._build_ui()

    def _init_state(self):
        default_label = None
        if self.default_target_slug:
            default_label = target_for_slug(self.default_target_slug).label
        self.target_var = ctk.StringVar(value=default_label or list_target_labels()[0])
        self.name_var = ctk.StringVar(
            value=extract_default_name(self.source_text, self.source_url)
        )

    def _build_ui(self):
        self.title("Import de texte")
        self.geometry("920x820")
        self.minsize(900, 780)
        self.transient(self.master)
        self.lift()
        self.grab_set()
        self.focus_force()
        self.bind("<Escape>", lambda e: self.destroy())

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        header = ctk.CTkLabel(
            container,
            text="Importer un texte dans une fiche",
            font=("TkDefaultFont", 16, "bold"),
        )
        header.pack(anchor="w", pady=(0, 6))

        source_frame = ctk.CTkFrame(container)
        source_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(source_frame, text="URL source").pack(anchor="w")
        self.url_entry = ctk.CTkEntry(source_frame)
        self.url_entry.insert(0, self.source_url)
        self.url_entry.pack(fill="x", pady=(2, 4))

        target_row = ctk.CTkFrame(container)
        target_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(target_row, text="Type cible").pack(side="left")
        self.target_menu = ctk.CTkOptionMenu(
            target_row,
            values=list_target_labels(),
            variable=self.target_var,
            command=lambda _: self._refresh_mapping_labels(),
        )
        self.target_menu.pack(side="left", padx=10)

        mapping_frame = ctk.CTkFrame(container)
        mapping_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            mapping_frame,
            text="Mapping minimal",
            font=("TkDefaultFont", 13, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        self.mapping_label = ctk.CTkLabel(mapping_frame, text="")
        self.mapping_label.pack(anchor="w")

        fields_frame = ctk.CTkFrame(container)
        fields_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(fields_frame, text="Nom").pack(anchor="w")
        self.name_entry = ctk.CTkEntry(fields_frame, textvariable=self.name_var)
        self.name_entry.pack(fill="x", pady=(2, 6))

        ctk.CTkLabel(fields_frame, text="Description").pack(anchor="w")
        self.description_text = ctk.CTkTextbox(fields_frame, height=140, wrap="word")
        self.description_text.insert("1.0", self.source_text)
        self.description_text.pack(fill="x", pady=(2, 6))

        ctk.CTkLabel(fields_frame, text="Notes").pack(anchor="w")
        self.notes_text = ctk.CTkTextbox(fields_frame, height=110, wrap="word")
        self.notes_text.pack(fill="x", pady=(2, 6))

        preview_frame = ctk.CTkFrame(container)
        preview_frame.pack(fill="both", expand=True, pady=(0, 8))
        ctk.CTkLabel(preview_frame, text="Aperçu (lecture seule)").pack(anchor="w")
        preview_box = ctk.CTkTextbox(preview_frame, wrap="word")
        preview_box.insert("1.0", self.source_text)
        preview_box.configure(state="disabled")
        preview_box.pack(fill="both", expand=True, pady=(2, 0))

        action_row = ctk.CTkFrame(container)
        action_row.pack(fill="x", pady=(6, 0))
        ctk.CTkButton(action_row, text="Annuler", command=self.destroy).pack(
            side="right", padx=6
        )
        ctk.CTkButton(
            action_row,
            text="Créer la fiche",
            command=self._create_record,
        ).pack(side="right")

        self._refresh_mapping_labels()

    def _refresh_mapping_labels(self):
        target = target_for_label(self.target_var.get())
        self.mapping_label.configure(
            text=(
                f"Nom → {target.name_field}   "
                f"Description → {target.description_field}   "
                f"Notes → {target.notes_field}"
            )
        )

    def _extract_field_text(self, widget: ctk.CTkTextbox) -> str:
        return widget.get("1.0", "end-1c").strip()

    @log_function
    def _create_record(self):
        target = target_for_label(self.target_var.get())
        name_value = self.name_var.get().strip()
        if not name_value:
            messagebox.showwarning("Nom manquant", "Veuillez saisir un nom.")
            return
        description = self._extract_field_text(self.description_text)
        notes = self._extract_field_text(self.notes_text)
        source_url = self.url_entry.get().strip()

        item = {
            target.name_field: name_value,
            "Source": build_source_metadata(self.source_text, source_url),
        }
        if description:
            item[target.description_field] = description
        if notes:
            item[target.notes_field] = notes

        try:
            template = load_template(target.slug)
            wrapper = GenericModelWrapper(target.slug)
        except Exception as exc:
            log_exception(
                f"Unable to load template for {target.slug}: {exc}",
                func_name="TextImportDialog._create_record",
            )
            messagebox.showerror("Erreur", "Impossible de charger le modèle cible.")
            return

        editor = GenericEditorWindow(
            self,
            item,
            template,
            wrapper,
            creation_mode=True,
        )
        self.wait_window(editor)
        if not getattr(editor, "saved", False):
            return
        try:
            wrapper.save_item(editor.item)
        except Exception as exc:
            log_exception(
                f"Unable to save imported record: {exc}",
                func_name="TextImportDialog._create_record",
            )
            messagebox.showerror("Erreur", "Impossible d'enregistrer la fiche.")
            return

        if callable(self.on_complete):
            self.on_complete(editor.item)
        self.destroy()
