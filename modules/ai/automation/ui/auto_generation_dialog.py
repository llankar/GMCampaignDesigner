import threading
import customtkinter as ctk
from tkinter import messagebox

from modules.ai.automation import AutoGenerationService
from modules.helpers.template_loader import load_entity_definitions
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


class AutoGenerationDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, default_entity: str | None = None, on_complete=None):
        super().__init__(parent)
        self.title("Auto Generation")
        self.geometry("700x500")
        self.transient(parent)
        self.grab_set()
        self._on_complete = on_complete

        self._service = AutoGenerationService()
        self._running = False

        entity_defs = load_entity_definitions()
        self._entity_labels = {slug: meta["label"] for slug, meta in entity_defs.items()}
        self._entity_slugs = sorted(self._entity_labels.keys())

        default_slug = default_entity if default_entity in self._entity_slugs else (self._entity_slugs[0] if self._entity_slugs else "")
        self.entity_var = ctk.StringVar(value=default_slug)
        self.count_var = ctk.IntVar(value=1)
        self.include_linked_var = ctk.BooleanVar(value=True)

        self._build_layout()

    def _build_layout(self):
        header = ctk.CTkLabel(self, text="Auto-génération IA", font=("Arial", 18, "bold"))
        header.pack(pady=(12, 8))

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=16, pady=8)

        row = ctk.CTkFrame(form)
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="Type d'entité", width=140, anchor="w").pack(side="left")
        options = [self._entity_labels[slug] for slug in self._entity_slugs]
        self._label_to_slug = {self._entity_labels[slug]: slug for slug in self._entity_slugs}
        self.entity_menu = ctk.CTkOptionMenu(
            row,
            values=options,
            command=self._on_entity_label_selected,
        )
        if self.entity_var.get() in self._entity_labels:
            self.entity_menu.set(self._entity_labels[self.entity_var.get()])
        self.entity_menu.pack(side="left", fill="x", expand=True, padx=8)

        row = ctk.CTkFrame(form)
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="Nombre", width=140, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=self.count_var).pack(side="left", fill="x", expand=True, padx=8)

        row = ctk.CTkFrame(form)
        row.pack(fill="x", pady=4)
        ctk.CTkCheckBox(
            row,
            text="Créer automatiquement les entités liées",
            variable=self.include_linked_var,
        ).pack(side="left", padx=8)

        ctk.CTkLabel(self, text="Brief / contraintes", anchor="w").pack(anchor="w", padx=20)
        self.prompt_box = ctk.CTkTextbox(self, height=160, wrap="word")
        self.prompt_box.pack(fill="both", expand=True, padx=16, pady=(4, 8))

        self.status_var = ctk.StringVar(value="Prêt.")
        status = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", padx=16, pady=(0, 8))

        btn_row = ctk.CTkFrame(self)
        btn_row.pack(fill="x", padx=16, pady=(0, 12))
        self.run_button = ctk.CTkButton(btn_row, text="Lancer", command=self._start_generation)
        self.run_button.pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Fermer", command=self.destroy).pack(side="right", padx=4)

    def _on_entity_label_selected(self, label: str):
        slug = self._label_to_slug.get(label)
        if slug:
            self.entity_var.set(slug)

    def _start_generation(self):
        if self._running:
            return
        entity_slug = self.entity_var.get().strip()
        if not entity_slug:
            messagebox.showerror("Erreur", "Sélectionnez un type d'entité.")
            return
        try:
            count = int(self.count_var.get())
        except Exception:
            messagebox.showerror("Erreur", "Nombre invalide.")
            return
        if count <= 0:
            messagebox.showerror("Erreur", "Le nombre doit être supérieur à 0.")
            return

        prompt = self.prompt_box.get("1.0", "end").strip()
        include_linked = bool(self.include_linked_var.get())

        self._running = True
        self.run_button.configure(state="disabled")
        self.status_var.set("Génération en cours...")

        thread = threading.Thread(
            target=self._run_generation,
            args=(entity_slug, count, prompt, include_linked),
            daemon=True,
        )
        thread.start()

    def _run_generation(self, entity_slug: str, count: int, prompt: str, include_linked: bool):
        try:
            self._service.generate_and_save(
                entity_slug,
                count,
                prompt,
                include_linked=include_linked,
            )
        except Exception as exc:
            self.after(0, lambda: self._on_error(exc))
            return
        self.after(0, self._on_success)

    def _on_success(self):
        self.status_var.set("Terminé. Les entités ont été créées.")
        self.run_button.configure(state="normal")
        self._running = False
        if self._on_complete:
            try:
                self._on_complete()
            except Exception:
                pass

    def _on_error(self, exc: Exception):
        self.status_var.set("Erreur pendant la génération.")
        self.run_button.configure(state="normal")
        self._running = False
        messagebox.showerror("Erreur", str(exc))
