from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from modules.auto_improve.orchestrator import AutoImproveOrchestrator
from modules.auto_improve.models import ImprovementProposal


class AutoImprovePanel(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Auto-improvement")
        self.geometry("900x640")
        self.transient(master)

        self.orchestrator = AutoImproveOrchestrator()
        self.proposals: list[ImprovementProposal] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkLabel(
            self,
            text="Run automatically generated product improvements with Codex CLI",
            font=("Helvetica", 16, "bold"),
        )
        self.header.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, padx=16, pady=8, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        body.grid_rowconfigure(3, weight=2)

        self.listbox = tk.Listbox(body, exportselection=False, height=7)
        self.listbox.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        controls = ctk.CTkFrame(body, fg_color="transparent")
        controls.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="ew")

        self.refresh_button = ctk.CTkButton(controls, text="Refresh ideas", command=self.load_proposals)
        self.refresh_button.pack(side="left", padx=(0, 8))

        self.run_button = ctk.CTkButton(controls, text="Run proposal", command=self.run_selected)
        self.run_button.pack(side="left")

        self.summary_label = ctk.CTkLabel(body, text="Select a proposal to view details.", justify="left")
        self.summary_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        self.output = ctk.CTkTextbox(body, wrap="word")
        self.output.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.load_proposals()

    def load_proposals(self):
        try:
            self.proposals = self.orchestrator.list_proposals(limit=5)
        except Exception as exc:
            self.proposals = []
            self.listbox.delete(0, tk.END)
            self.summary_label.configure(text="Unable to generate ideas right now.")
            messagebox.showerror("Auto-improvement", f"Failed to generate ideas:\\n{exc}")
            return

        self.listbox.delete(0, tk.END)
        for proposal in self.proposals:
            self.listbox.insert(tk.END, proposal.title)
        if self.proposals:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
            self._on_select(None)

    def _on_select(self, _event):
        index = self._selected_index()
        if index is None:
            return
        proposal = self.proposals[index]
        self.summary_label.configure(text=f"{proposal.summary}\nScope: {proposal.scope}")

    def _selected_index(self) -> int | None:
        selected = self.listbox.curselection()
        if not selected:
            return None
        return int(selected[0])

    def run_selected(self):
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Auto-improvement", "Please choose a proposal first.")
            return

        proposal = self.proposals[index]
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, f"Running: {proposal.title}\n")
        self.run_button.configure(state="disabled")

        def worker():
            report = self.orchestrator.execute(proposal)
            self.after(0, lambda: self._render_report(report))

        threading.Thread(target=worker, daemon=True).start()

    def _render_report(self, report):
        self.run_button.configure(state="normal")
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, f"Proposal: {report.proposal.title}\n")
        self.output.insert(tk.END, f"Success: {'yes' if report.success else 'no'}\n")
        self.output.insert(tk.END, f"Started: {report.started_at.isoformat()}\n")
        if report.completed_at:
            self.output.insert(tk.END, f"Completed: {report.completed_at.isoformat()}\n\n")
        for step in report.steps:
            self.output.insert(tk.END, f"- {step}\n")
