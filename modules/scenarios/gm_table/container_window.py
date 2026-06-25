"""Nested container workspace for the GM Table."""

from __future__ import annotations

from uuid import uuid4

import customtkinter as ctk

from modules.scenarios.gm_table.workspace import (
    PanelDefinition,
    TABLE_PALETTE,
    GMTableWorkspace,
)
from modules.scenarios.gm_table.pages import GMTableNotePage

CONTAINER_LAYOUT_STATE_KEY = "container_layout"


class GMTableContainerPage(ctk.CTkFrame):
    """A mini virtual table hosted inside a GM Table floating panel.

    The container gives the GM a second, smaller workspace for grouping related
    cards/windows before arranging the outer GM Table. It intentionally uses the
    same floating-window primitives as the main table so dragging, resizing,
    minimizing, tiling, cascading, and layout persistence behave consistently.
    """

    def __init__(
        self,
        master,
        *,
        initial_state: dict | None = None,
        on_layout_changed=None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._initial_state = initial_state or {}
        self._on_layout_changed = on_layout_changed
        self._build_toolbar()
        self.workspace = GMTableWorkspace(
            self,
            on_panel_build=self._mount_container_panel,
            on_layout_changed=self._handle_workspace_changed,
        )
        self.workspace.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.after_idle(self._restore_or_seed_layout)

    def _build_toolbar(self) -> None:
        """Build controls for the nested workspace."""
        toolbar = ctk.CTkFrame(
            self,
            fg_color=TABLE_PALETTE["table_alt"],
            corner_radius=18,
            border_width=1,
            border_color=TABLE_PALETTE["table_line"],
        )
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            toolbar,
            text="Container Window",
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=8)

        actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=8, pady=6)

        self._add_button(actions, "New Window", self.add_window).pack(
            side="left", padx=(0, 6)
        )
        self._add_button(actions, "Note", self.add_note).pack(side="left", padx=(0, 6))
        self._add_button(actions, "Tile", self.tile_windows).pack(
            side="left", padx=(0, 6)
        )
        self._add_button(actions, "Cascade", self.cascade_windows).pack(
            side="left", padx=(0, 6)
        )
        self._add_button(actions, "Restore", self.restore_windows).pack(side="left")

    @staticmethod
    def _add_button(master, text: str, command):
        """Create a compact toolbar button."""
        return ctk.CTkButton(
            master,
            text=text,
            width=92,
            height=28,
            fg_color=TABLE_PALETTE["table_chip"],
            hover_color="#283146",
            text_color=TABLE_PALETTE["text"],
            corner_radius=14,
            command=command,
        )

    def _restore_or_seed_layout(self) -> None:
        """Restore saved internal windows or add starter cards."""
        layout = self._initial_state.get(CONTAINER_LAYOUT_STATE_KEY)
        if isinstance(layout, dict) and isinstance(layout.get("panels"), list):
            self.workspace.restore(layout)
            return
        self.add_window(
            title="Prep Area",
            body="Drop related maps, notes, clues, and reminders here.",
        )
        self.add_note(title="Container Notes")

    def _handle_workspace_changed(self) -> None:
        """Bubble nested layout changes up to the outer GM Table."""
        if callable(self._on_layout_changed):
            self._on_layout_changed()

    def _create_internal_panel(
        self,
        kind: str,
        title: str,
        state: dict,
        *,
        geometry: dict | None = None,
    ) -> str:
        """Create a floating panel inside the container."""
        definition = PanelDefinition(
            panel_id=uuid4().hex,
            kind=kind,
            title=title,
            state=dict(state or {}),
        )
        self.workspace.add_panel(definition, geometry=geometry)
        return definition.panel_id

    def add_window(self, *, title: str | None = None, body: str | None = None) -> None:
        """Open a simple organizer card inside the container."""
        card_count = len(self.workspace.list_panels(kinds={"container_card"}))
        card_title = title or f"Window {card_count + 1}"
        self._create_internal_panel(
            "container_card",
            card_title,
            {"body": body or "Use this card to group related GM table material."},
            geometry={"width": 360, "height": 260},
        )

    def add_note(self, *, title: str | None = None) -> None:
        """Open a scratch note inside the container."""
        note_count = len(self.workspace.list_panels(kinds={"container_note"}))
        note_title = title or f"Note {note_count + 1}"
        self._create_internal_panel(
            "container_note",
            note_title,
            {"text": ""},
            geometry={"width": 420, "height": 300},
        )

    def tile_windows(self) -> None:
        """Tile internal windows."""
        self.workspace.auto_arrange()

    def cascade_windows(self) -> None:
        """Cascade internal windows."""
        self.workspace.cascade_panels()

    def restore_windows(self) -> None:
        """Restore minimized internal windows."""
        self.workspace.restore_all_panels()

    def _mount_container_panel(self, parent: ctk.CTkFrame, definition: PanelDefinition):
        """Build content for an internal container panel."""
        if definition.kind == "container_note":
            return GMTableNotePage(
                parent,
                initial_text=str(definition.state.get("text") or ""),
                session_controls_enabled=False,
                scenario_actions_enabled=False,
            )
        return GMTableContainerCard(
            parent,
            title=definition.title,
            body=str(definition.state.get("body") or ""),
        )

    def get_state(self) -> dict:
        """Return serializable container state for the outer table layout."""
        return {CONTAINER_LAYOUT_STATE_KEY: self.workspace.serialize()}

    def close(self) -> None:
        """Dispose nested workspace payloads."""
        self.workspace.dispose()


class GMTableContainerCard(ctk.CTkFrame):
    """Simple editable card for a container workspace."""

    def __init__(self, master, *, title: str, body: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._title = title
        ctk.CTkLabel(
            self,
            text=title,
            text_color=TABLE_PALETTE["text"],
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.textbox = ctk.CTkTextbox(self, wrap="word")
        self.textbox.grid(row=1, column=0, sticky="nsew")
        if body:
            self.textbox.insert("1.0", body)

    def get_state(self) -> dict:
        """Return editable card text."""
        return {"body": self.textbox.get("1.0", "end-1c")}
