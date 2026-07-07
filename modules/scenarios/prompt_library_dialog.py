"""CustomTkinter dialog for managing scenario AI prompts."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from modules.helpers.logging_helper import log_exception
from modules.scenarios.ai_prompt_library import (
    PromptLibrary,
    PromptLibraryError,
    PromptQuestion,
    ScenarioPrompt,
    _utc_now,
    validate_prompt,
)


class PromptLibraryDialog(ctk.CTkToplevel):
    """Prompt library CRUD/import/export dialog."""

    def __init__(self, parent, library: PromptLibrary, on_change=None):
        super().__init__(parent)
        self.title("Manage Scenario Prompts")
        self.geometry("1100x720")
        self.library = library
        self.on_change = on_change
        self.prompts = self.library.load()
        self.selected_id: str | None = None
        self.name_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.description_var = tk.StringVar()
        self._build_widgets()
        self._refresh_list()
        if self.prompts:
            self._select_prompt(self.prompts[0].id)
        self.grab_set()

    def _build_widgets(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left.grid_rowconfigure(0, weight=1)
        self.listbox = tk.Listbox(left, width=30, exportselection=False)
        self.listbox.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        buttons = [
            ("New", self._new_prompt), ("Duplicate", self._duplicate_prompt),
            ("Delete", self._delete_prompt), ("Import", self._import_prompts),
            ("Export", self._export_prompts), ("Restore Defaults", self._restore_defaults),
        ]
        for idx, (label, command) in enumerate(buttons, start=1):
            ctk.CTkButton(left, text=label, command=command).grid(row=idx, column=0, columnspan=2, sticky="ew", padx=6, pady=3)

        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        right.grid_columnconfigure(1, weight=1)
        right.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(right, text="Name").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ctk.CTkEntry(right, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(right, text="Category / Genre").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ctk.CTkEntry(right, textvariable=self.category_var).grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(right, text="Description").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ctk.CTkEntry(right, textvariable=self.description_var).grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(right, text="Questions (one per line: key|Label|required|default)").grid(row=3, column=0, columnspan=2, sticky="w", padx=8)
        self.prompt_text = ctk.CTkTextbox(right, wrap="word")
        self.prompt_text.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=8, pady=4)
        self.questions_text = ctk.CTkTextbox(right, height=120, wrap="word")
        self.questions_text.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        footer = ctk.CTkFrame(right)
        footer.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        ctk.CTkButton(footer, text="Save Prompt", command=self._save_current).pack(side="right", padx=5)
        ctk.CTkButton(footer, text="Close", command=self.destroy).pack(side="right", padx=5)

    def _refresh_list(self) -> None:
        self.listbox.delete(0, tk.END)
        for prompt in self.prompts:
            self.listbox.insert(tk.END, prompt.name)

    def _on_select(self, _event=None) -> None:
        selection = self.listbox.curselection()
        if selection:
            self._select_prompt(self.prompts[selection[0]].id)

    def _select_prompt(self, prompt_id: str) -> None:
        prompt = next((p for p in self.prompts if p.id == prompt_id), None)
        if not prompt:
            return
        self.selected_id = prompt.id
        self.name_var.set(prompt.name)
        self.category_var.set(prompt.category)
        self.description_var.set(prompt.description)
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", prompt.prompt_text)
        self.questions_text.delete("1.0", "end")
        lines = [f"{q.key}|{q.label}|{str(q.required).lower()}|{q.default}" for q in prompt.questions]
        self.questions_text.insert("1.0", "\n".join(lines))

    def _parse_questions(self) -> list[PromptQuestion]:
        questions: list[PromptQuestion] = []
        for line in self.questions_text.get("1.0", "end").splitlines():
            if not line.strip():
                continue
            parts = [part.strip() for part in line.split("|", 3)]
            while len(parts) < 4:
                parts.append("")
            questions.append(PromptQuestion(parts[0], parts[1] or parts[0], parts[2].lower() not in {"false", "0", "no", "optional"}, parts[3]))
        return questions

    def _save_current(self) -> None:
        if not self.selected_id:
            self._new_prompt()
        prompt = next((p for p in self.prompts if p.id == self.selected_id), None)
        if not prompt:
            return
        prompt.name = self.name_var.get().strip()
        prompt.category = self.category_var.get().strip()
        prompt.description = self.description_var.get().strip()
        prompt.prompt_text = self.prompt_text.get("1.0", "end").strip()
        prompt.questions = self._parse_questions()
        prompt.updated_at = _utc_now()
        errors = validate_prompt(prompt, self.prompts)
        if errors:
            messagebox.showerror("Invalid Prompt", "\n".join(errors), parent=self)
            return
        try:
            self.library.save(self.prompts)
        except PromptLibraryError as exc:
            messagebox.showerror("Prompt Library", str(exc), parent=self)
            return
        self._refresh_list()
        if self.on_change:
            self.on_change()

    def _new_prompt(self) -> None:
        prompt = ScenarioPrompt.new("New Prompt", "", "", "Write a scenario about {theme}.", [PromptQuestion("theme", "Theme", True)])
        self.prompts.append(prompt)
        self.selected_id = prompt.id
        self._refresh_list()
        self._select_prompt(prompt.id)

    def _duplicate_prompt(self) -> None:
        prompt = next((p for p in self.prompts if p.id == self.selected_id), None)
        if not prompt:
            return
        copy = ScenarioPrompt.new(f"{prompt.name} Copy", prompt.description, prompt.category, prompt.prompt_text, list(prompt.questions))
        self.prompts.append(copy)
        self._refresh_list()
        self._select_prompt(copy.id)

    def _delete_prompt(self) -> None:
        prompt = next((p for p in self.prompts if p.id == self.selected_id), None)
        if not prompt or not messagebox.askyesno("Delete Prompt", f"Delete '{prompt.name}'?", parent=self):
            return
        self.prompts = [p for p in self.prompts if p.id != prompt.id]
        self.library.save(self.prompts)
        self._refresh_list()
        self.selected_id = None
        if self.prompts:
            self._select_prompt(self.prompts[0].id)
        if self.on_change:
            self.on_change()

    def _import_prompts(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], parent=self)
        if not filename:
            return
        try:
            self.prompts = self.library.import_from_file(filename, merge=True)
        except Exception as exc:
            log_exception("Prompt import failed")
            messagebox.showerror("Import failed", str(exc), parent=self)
            return
        self._refresh_list()
        if self.on_change:
            self.on_change()

    def _export_prompts(self) -> None:
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], parent=self)
        if filename:
            self.library.export_to_file(self.prompts, filename)

    def _restore_defaults(self) -> None:
        keep = messagebox.askyesno("Restore Defaults", "Keep existing custom prompts and add missing defaults?", parent=self)
        self.prompts = self.library.restore_defaults(keep_existing=keep)
        self._refresh_list()
        if self.prompts:
            self._select_prompt(self.prompts[0].id)
        if self.on_change:
            self.on_change()
