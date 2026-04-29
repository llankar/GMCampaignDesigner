from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from ..validation import ValidationIssue


class ValidationPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._blocking_issues: list[ValidationIssue] = []
        self._warning_issues: list[ValidationIssue] = []
        self.on_issue_click: Callable[[ValidationIssue], None] | None = None

        self.grid_columnconfigure(0, weight=1)

        self._errors_label = ctk.CTkLabel(self, text="Blocking errors", anchor="w")
        self._errors_label.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 4))

        self._errors_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", height=120)
        self._errors_frame.grid(row=1, column=0, sticky="nsew", padx=4)

        self._warnings_label = ctk.CTkLabel(self, text="Warnings", anchor="w")
        self._warnings_label.grid(row=2, column=0, sticky="ew", padx=4, pady=(12, 4))

        self._warnings_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", height=100)
        self._warnings_frame.grid(row=3, column=0, sticky="nsew", padx=4)

    def update_issues(self, issues: list[ValidationIssue]) -> None:
        self._blocking_issues = [issue for issue in issues if issue.blocking]
        self._warning_issues = [issue for issue in issues if not issue.blocking]
        self._render_frame(self._errors_frame, self._blocking_issues)
        self._render_frame(self._warnings_frame, self._warning_issues)

    def has_blocking_errors(self) -> bool:
        return bool(self._blocking_issues)

    def _render_frame(self, frame: ctk.CTkScrollableFrame, issues: list[ValidationIssue]) -> None:
        for child in frame.winfo_children():
            child.destroy()
        if not issues:
            ctk.CTkLabel(frame, text="None", text_color="#94a3b8", anchor="w").pack(fill="x", padx=4, pady=2)
            return
        for issue in issues:
            button = ctk.CTkButton(
                frame,
                text=f"• {issue.message}",
                anchor="w",
                fg_color="transparent",
                hover_color="#1e293b",
                command=lambda current=issue: self._handle_issue_click(current),
            )
            button.pack(fill="x", padx=2, pady=1)

    def _handle_issue_click(self, issue: ValidationIssue) -> None:
        if self.on_issue_click is None:
            return
        self.on_issue_click(issue)
