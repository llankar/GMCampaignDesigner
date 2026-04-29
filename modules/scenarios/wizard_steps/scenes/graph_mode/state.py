"""Centralized state container for graph mode planner."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class GraphViewportState:
    """Viewport transform state."""

    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0


@dataclass(slots=True)
class GraphModeState:
    """Mutable planner state used by GraphModePlanner."""

    scenes: list[dict[str, Any]] = field(default_factory=list)
    selected_node_id: str | None = None
    selected_edge_id: str | None = None
    viewport: GraphViewportState = field(default_factory=GraphViewportState)
    edges: list[dict[str, Any]] = field(default_factory=list)
    dirty: bool = False
    _undo_stack: list[tuple[list[dict[str, Any]], list[dict[str, Any]], str | None, str | None, GraphViewportState, bool]] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    _redo_stack: list[tuple[list[dict[str, Any]], list[dict[str, Any]], str | None, str | None, GraphViewportState, bool]] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    def reset(self) -> None:
        self.scenes.clear()
        self.selected_node_id = None
        self.selected_edge_id = None
        self.viewport = GraphViewportState()
        self.edges.clear()
        self.dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()

    def set_selected_node(self, node_id: str | None) -> None:
        self.selected_node_id = node_id
        if node_id is not None:
            self.selected_edge_id = None

    def set_selected_edge(self, edge_id: str | None) -> None:
        self.selected_edge_id = edge_id
        if edge_id is not None:
            self.selected_node_id = None

    def set_viewport(self, *, zoom: float | None = None, pan_x: float | None = None, pan_y: float | None = None) -> None:
        self.viewport = GraphViewportState(
            zoom=self.viewport.zoom if zoom is None else float(zoom),
            pan_x=self.viewport.pan_x if pan_x is None else float(pan_x),
            pan_y=self.viewport.pan_y if pan_y is None else float(pan_y),
        )


    def selected_node(self) -> dict[str, Any] | None:
        if not self.selected_node_id:
            return None
        return next((scene for scene in self.scenes if str(scene.get("id")) == self.selected_node_id), None)

    def selected_edge(self) -> dict[str, Any] | None:
        edge_id = self.selected_edge_id
        if not edge_id:
            return None
        edges = self._edge_store()
        return next((edge for edge in edges if str(edge.get("id")) == edge_id), None)

    def update_selected_node_field(self, field: str, value: Any) -> None:
        node = self.selected_node()
        if node is None:
            return
        def op(state: "GraphModeState") -> None:
            target = state.selected_node()
            if target is not None:
                target[field] = value
        self.mutate(op)

    def update_selected_edge_field(self, field: str, value: Any) -> None:
        if self.selected_edge() is None:
            return
        def op(state: "GraphModeState") -> None:
            for edge in state._edge_store():
                if str(edge.get("id")) == state.selected_edge_id:
                    edge[field] = value
                    break
        self.mutate(op)

    def _edge_store(self) -> list[dict[str, Any]]:
        return self.edges
    def mark_clean(self) -> None:
        self.dirty = False

    def mutate(self, operation: Callable[["GraphModeState"], None]) -> None:
        """Undo/redo-ready centralized mutation entry point."""

        self._undo_stack.append(self._snapshot())
        self._redo_stack.clear()
        operation(self)
        self.dirty = True

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        self._restore(self._undo_stack.pop())
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        self._restore(self._redo_stack.pop())
        return True

    def _snapshot(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None, str | None, GraphViewportState, bool]:
        return (
            [dict(scene) for scene in self.scenes],
            [dict(edge) for edge in self.edges],
            self.selected_node_id,
            self.selected_edge_id,
            GraphViewportState(self.viewport.zoom, self.viewport.pan_x, self.viewport.pan_y),
            self.dirty,
        )

    def _restore(self, snapshot: tuple[list[dict[str, Any]], list[dict[str, Any]], str | None, str | None, GraphViewportState, bool]) -> None:
        scenes, edges, selected_node_id, selected_edge_id, viewport, dirty = snapshot
        self.scenes = [dict(scene) for scene in scenes]
        self.edges = [dict(edge) for edge in edges]
        self.selected_node_id = selected_node_id
        self.selected_edge_id = selected_edge_id
        self.viewport = GraphViewportState(viewport.zoom, viewport.pan_x, viewport.pan_y)
        self.dirty = dirty
