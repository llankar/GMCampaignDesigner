from __future__ import annotations

import copy
from typing import Dict, Optional


class FlowCanvasModel:
    """Pure data operations for the visual flow canvas."""

    def __init__(self, payload=None):
        self._payload = copy.deepcopy(payload or {"version": 1, "nodes": [], "links": []})

    @property
    def payload(self):
        return self._payload

    def set_payload(self, payload):
        self._payload = copy.deepcopy(payload or {"version": 1, "nodes": [], "links": []})

    def get_node(self, node_id: str) -> Optional[Dict]:
        node_key = str(node_id or "")
        return next((node for node in self._payload.get("nodes", []) if str(node.get("id") or "") == node_key), None)

    def get_link(self, link_id: str) -> Optional[Dict]:
        link_key = str(link_id or "")
        return next((link for link in self._payload.get("links", []) if str(link.get("id") or "") == link_key), None)

    def move_node(self, node_id: str, x: int, y: int) -> bool:
        node = self.get_node(node_id)
        if node is None:
            return False
        node["x"] = int(x)
        node["y"] = int(y)
        return True

    def remove_node(self, node_id: str) -> bool:
        before = len(self._payload.get("nodes", []))
        self._payload["nodes"] = [n for n in self._payload.get("nodes", []) if str(n.get("id") or "") != str(node_id or "")]
        self._payload["links"] = [
            l for l in self._payload.get("links", [])
            if str(l.get("source") or "") != str(node_id or "") and str(l.get("target") or "") != str(node_id or "")
        ]
        return len(self._payload["nodes"]) != before

    def remove_link(self, link_id: str) -> bool:
        before = len(self._payload.get("links", []))
        self._payload["links"] = [l for l in self._payload.get("links", []) if str(l.get("id") or "") != str(link_id or "")]
        return len(self._payload["links"]) != before
