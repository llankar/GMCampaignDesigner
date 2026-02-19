from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

import customtkinter as ctk


@dataclass
class HistoryEntry:
    timestamp: str
    label: str
    value: str


class HistoryPanel(ctk.CTkFrame):
    def __init__(self, parent, max_entries: int = 200):
        super().__init__(parent)
        self._entries: List[HistoryEntry] = []
        self._max_entries = max(20, int(max_entries))

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(header, text="History", font=("Segoe UI", 15, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Clear", width=80, command=self.clear).pack(side="right")

        self._box = ctk.CTkTextbox(self, height=180)
        self._box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._box.configure(state="disabled")

    def add_lap(self, timer_name: str, lap_seconds: float) -> None:
        self._append("Lap", f"{timer_name}: {self._format_seconds(lap_seconds)}")

    def add_finished(self, timer_name: str) -> None:
        self._append("Finished", timer_name)

    def clear(self) -> None:
        self._entries.clear()
        self._render()

    def _append(self, label: str, value: str) -> None:
        self._entries.append(
            HistoryEntry(timestamp=datetime.now().strftime("%H:%M:%S"), label=label, value=value)
        )
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]
        self._render()

    def _render(self) -> None:
        self._box.configure(state="normal")
        self._box.delete("1.0", "end")
        for entry in self._entries:
            self._box.insert("end", f"[{entry.timestamp}] {entry.label} - {entry.value}\n")
        self._box.see("end")
        self._box.configure(state="disabled")

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes, sec = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
