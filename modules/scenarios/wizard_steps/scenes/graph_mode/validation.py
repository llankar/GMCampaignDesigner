"""Validation helpers for graph mode scenes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Severity = Literal["error", "warning"]
IssueCode = Literal[
    "invalid_title",
    "start_count",
    "missing_reachable_end",
    "orphan_node",
    "choice_outgoing",
    "condition_exits",
]


@dataclass(slots=True, frozen=True)
class ValidationIssue:
    code: IssueCode
    severity: Severity
    message: str
    node_id: str | None = None
    edge_id: str | None = None

    @property
    def blocking(self) -> bool:
        return self.severity == "error"


def validate_scenes(scenes: list[dict], edges: list[dict] | None = None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    edge_rows = list(edges or [])
    node_ids = {str(scene.get("id")) for scene in scenes if scene.get("id")}

    for index, scene in enumerate(scenes, start=1):
        if not str(scene.get("title") or "").strip():
            issues.append(
                ValidationIssue(
                    code="invalid_title",
                    severity="warning",
                    message=f"Scene {index} has an empty title",
                    node_id=str(scene.get("id") or "") or None,
                )
            )

    start_nodes = [scene for scene in scenes if str(scene.get("type") or "").upper() == "START"]
    if len(start_nodes) != 1:
        issues.append(
            ValidationIssue(
                code="start_count",
                severity="error",
                message=f"Graph must contain exactly one START node (found {len(start_nodes)})",
                node_id=str(start_nodes[0].get("id")) if start_nodes else None,
            )
        )

    adjacency: dict[str, list[dict]] = {node_id: [] for node_id in node_ids}
    incoming_count: dict[str, int] = {node_id: 0 for node_id in node_ids}
    for edge in edge_rows:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in adjacency:
            adjacency[source].append(edge)
        if target in incoming_count:
            incoming_count[target] += 1

    reachable: set[str] = set()
    if len(start_nodes) == 1:
        stack = [str(start_nodes[0].get("id") or "")]
        while stack:
            node_id = stack.pop()
            if not node_id or node_id in reachable:
                continue
            reachable.add(node_id)
            for edge in adjacency.get(node_id, []):
                nxt = str(edge.get("target") or "")
                if nxt and nxt not in reachable:
                    stack.append(nxt)

    has_reachable_end = any(
        str(scene.get("type") or "").upper() in {"END_SUCCESS", "END_FAIL"}
        and str(scene.get("id") or "") in reachable
        for scene in scenes
    )
    if not has_reachable_end:
        issues.append(
            ValidationIssue(
                code="missing_reachable_end",
                severity="error",
                message="Graph must have at least one reachable END_SUCCESS or END_FAIL node",
            )
        )

    for scene in scenes:
        node_id = str(scene.get("id") or "")
        if not node_id:
            continue
        if incoming_count.get(node_id, 0) == 0 and node_id not in {str(n.get("id") or "") for n in start_nodes}:
            issues.append(
                ValidationIssue(
                    code="orphan_node",
                    severity="error",
                    message="Node is orphaned (no incoming edges)",
                    node_id=node_id,
                )
            )

    for scene in scenes:
        node_id = str(scene.get("id") or "")
        node_type = str(scene.get("type") or "").upper()
        outgoing = adjacency.get(node_id, [])

        if node_type == "CHOICE" and len(outgoing) < 2:
            issues.append(
                ValidationIssue(
                    code="choice_outgoing",
                    severity="error",
                    message="CHOICE node must have at least 2 outgoing edges",
                    node_id=node_id,
                )
            )

        if node_type == "CONDITION":
            exits = {
                str(edge.get("condition_value") or edge.get("label") or edge.get("condition_type") or "").strip().lower()
                for edge in outgoing
                if str(edge.get("condition_value") or edge.get("label") or edge.get("condition_type") or "").strip()
            }
            if len(exits) < 2:
                issues.append(
                    ValidationIssue(
                        code="condition_exits",
                        severity="error",
                        message="CONDITION node must expose at least 2 logical exits",
                        node_id=node_id,
                    )
                )

    return issues
