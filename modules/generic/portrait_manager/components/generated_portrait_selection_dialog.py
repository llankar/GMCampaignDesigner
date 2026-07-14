"""Dialog-owned candidate selection UI for generated scenario portraits."""
from __future__ import annotations

import customtkinter as ctk

from modules.generic.portrait_manager.swarmui_portrait_generator import GeneratedPortraitCandidate


class GeneratedPortraitSelectionDialog(ctk.CTkToplevel):
    """Modal picker that lets the user choose one generated portrait candidate."""

    def __init__(self, master, *, entity_name: str, candidates: list[GeneratedPortraitCandidate]):
        super().__init__(master)
        self.result: GeneratedPortraitCandidate | None = None
        self._candidates = candidates
        self._images: list[ctk.CTkImage] = []

        self.title(f"Choose Portrait - {entity_name}")
        self.transient(master)
        self.grab_set()
        self._build_ui(entity_name)
        self._fit_to_candidates()

    def _build_ui(self, entity_name: str) -> None:
        shell = ctk.CTkFrame(self, corner_radius=16)
        shell.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(
            shell,
            text=f"Select a portrait for {entity_name}",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            shell,
            text="Click a generated candidate to attach it to the current scenario entity.",
            justify="left",
            text_color=("#5f6368", "#b8beca"),
        ).pack(anchor="w", padx=12, pady=(0, 12))

        grid = ctk.CTkFrame(shell, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=6, pady=6)
        cols = min(5, max(1, len(self._candidates)))
        for column in range(cols):
            grid.grid_columnconfigure(column, weight=1)
        for index, candidate in enumerate(self._candidates):
            image = ctk.CTkImage(light_image=candidate.thumbnail, size=(180, 180))
            self._images.append(image)
            ctk.CTkButton(
                grid,
                image=image,
                text=f"Use candidate #{index + 1}",
                compound="top",
                width=190,
                height=220,
                command=lambda selected=index: self._choose(selected),
            ).grid(row=index // cols, column=index % cols, padx=6, pady=6, sticky="nsew")

        actions = ctk.CTkFrame(shell, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkButton(actions, text="Cancel", fg_color="transparent", border_width=1, command=self._cancel).pack(side="right")

    def _fit_to_candidates(self) -> None:
        self.update_idletasks()
        cols = min(5, max(1, len(self._candidates)))
        rows = (len(self._candidates) + cols - 1) // cols
        width = min(1120, max(420, cols * 210 + 60))
        height = min(820, max(360, rows * 240 + 150))
        self.geometry(f"{width}x{height}")

    def _choose(self, index: int) -> None:
        self.result = self._candidates[index]
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
