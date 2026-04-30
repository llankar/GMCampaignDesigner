from __future__ import annotations

import copy
import re
import tkinter as tk
from tkinter import simpledialog

import customtkinter as ctk

from modules.scenarios.scene_flow_rendering import apply_scene_flow_canvas_styling
from modules.scenarios.wizard_steps.scenes.flow_canvas.model import FlowCanvasModel
def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "scene"


def normalise_flow_node_id(title, existing_ids):
    used = {str(value).strip() for value in (existing_ids or []) if str(value).strip()}
    base = _slugify(str(title or "Scene"))
    candidate = base
    idx = 2
    while candidate in used:
        candidate = f"{base}-{idx}"
        idx += 1
    return candidate

_NODE_STYLES = {
    "scene": {"fill": "#1f2937", "outline": "#60a5fa", "symbol": "●"},
    "objective": {"fill": "#1f3a2e", "outline": "#34d399", "symbol": "◆"},
    "condition": {"fill": "#3b2f1f", "outline": "#f59e0b", "symbol": "?"},
    "action": {"fill": "#2f1f3b", "outline": "#c084fc", "symbol": "▶"},
    "note": {"fill": "#3a3a3a", "outline": "#a3a3a3", "symbol": "■"},
}

_CONDITION_LABELS = {"yes": "Yes", "no": "No", "success": "Success", "failure": "Failure"}


class VisualFlowCanvas(ctk.CTkFrame):
    def __init__(self, master, on_select=None, on_change=None, on_save=None):
        super().__init__(master)
        self.on_select = on_select
        self.on_change = on_change
        self.on_save = on_save
        self.model = FlowCanvasModel()
        self._tile_cache = {}
        self.canvas = tk.Canvas(self, bg="#0f172a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self._node_items = {}
        self._link_items = {}
        self._selected_node_id = None
        self._selected_link_id = None
        self._drag_state = None
        self._pan_state = None
        self._space_held = False
        self._drag_link_source = None
        self._zoom = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._bind_events()

    def _bind_events(self):
        self.canvas.bind("<Button-2>", self._start_pan)
        self.canvas.bind("<B2-Motion>", self._pan)
        self.canvas.bind("<ButtonRelease-2>", self._end_pan)
        self.canvas.bind("<Button-3>", self._canvas_menu)
        self.canvas.bind("<Double-1>", self._double_click)
        self.canvas.bind("<Control-0>", lambda _e: self.reset_zoom())
        self.canvas.bind_all("<Delete>", lambda _e: self.delete_selected())
        self.canvas.bind_all("<Control-d>", lambda _e: self.duplicate_selected())
        self.canvas.bind_all("<Control-s>", lambda _e: self.save_state())
        self.canvas.bind_all("<space>", lambda _e: self._set_space(True))
        self.canvas.bind_all("<KeyRelease-space>", lambda _e: self._set_space(False))

    def _set_space(self, value):
        self._space_held = value

    def set_payload(self, payload):
        self.model.set_payload(payload)
        self.render()

    def export_payload(self):
        return copy.deepcopy(self.model.payload)

    def render(self):
        self.canvas.delete("all")
        self._node_items.clear()
        self._link_items.clear()
        apply_scene_flow_canvas_styling(self.canvas, tile_cache=self._tile_cache, extent_width=4000, extent_height=3000)
        self._draw_links()
        self._draw_nodes()
        self._draw_minimap()

    def _world_to_screen(self, x, y):
        return x * self._zoom + self._offset_x, y * self._zoom + self._offset_y

    def _screen_to_world(self, x, y):
        return (x - self._offset_x) / max(self._zoom, 0.001), (y - self._offset_y) / max(self._zoom, 0.001)

    def _draw_nodes(self):
        for node in self.model.payload.get("nodes") or []:
            nid = str(node.get("id") or "")
            kind = str(node.get("kind") or "scene")
            style = _NODE_STYLES.get(kind, _NODE_STYLES["scene"])
            x, y = self._world_to_screen(int(node.get("x", 0)), int(node.get("y", 0)))
            w, h = 190 * self._zoom, 88 * self._zoom
            rect = self.canvas.create_rectangle(x, y, x + w, y + h, fill=style["fill"], outline=style["outline"], width=2, tags=("node", nid))
            self.canvas.create_text(x + 10, y + 10, text=f"{style['symbol']} {node.get('title') or 'Untitled'}", anchor="nw", fill="#f8fafc", tags=("node", nid))
            handle = self.canvas.create_oval(x + w - 14, y + h / 2 - 6, x + w - 2, y + h / 2 + 6, fill="#38bdf8", outline="", tags=("handle", nid))
            self._node_items[nid] = {"rect": rect, "handle": handle}
            self.canvas.tag_bind(rect, "<Button-1>", lambda e, node_id=nid: self._start_node_drag(e, node_id))
            self.canvas.tag_bind(rect, "<B1-Motion>", self._drag_node)
            self.canvas.tag_bind(rect, "<ButtonRelease-1>", self._end_node_drag)
            self.canvas.tag_bind(handle, "<Button-1>", lambda e, node_id=nid: self._start_link_drag(e, node_id))

    def _draw_links(self):
        nodes = {str(n.get("id") or ""): n for n in self.model.payload.get("nodes") or []}
        for link in self.model.payload.get("links") or []:
            source = nodes.get(str(link.get("source") or ""))
            target = nodes.get(str(link.get("target") or ""))
            if not source or not target:
                continue
            sx, sy = self._world_to_screen(int(source.get("x", 0)) + 190, int(source.get("y", 0)) + 44)
            tx, ty = self._world_to_screen(int(target.get("x", 0)), int(target.get("y", 0)) + 44)
            line = self.canvas.create_line(sx, sy, tx, ty, fill="#93c5fd", width=2, arrow="last", tags=("link", str(link.get("id") or "")))
            label = str(link.get("label") or "").strip()
            if not label:
                kind_label = _CONDITION_LABELS.get(str(link.get("kind") or "").lower())
                label = kind_label or ""
            if label:
                lx, ly = (sx + tx) / 2, (sy + ty) / 2
                text = self.canvas.create_text(lx, ly - 8, text=label, fill="#e2e8f0", tags=("link_label", str(link.get("id") or "")))
            else:
                text = None
            lid = str(link.get("id") or "")
            self._link_items[lid] = {"line": line, "text": text}
            self.canvas.tag_bind(line, "<Button-1>", lambda _e, link_id=lid: self.select_link(link_id))
            self.canvas.tag_bind(line, "<Button-3>", lambda e, link_id=lid: self._link_menu(e, link_id))

    def _draw_minimap(self):
        self.canvas.create_rectangle(16, self.canvas.winfo_height() - 126, 176, self.canvas.winfo_height() - 16, fill="#111827", outline="#4b5563")

    def _start_node_drag(self, event, node_id):
        if self._space_held:
            self._start_pan(event)
            return
        self.select_node(node_id, emit=True)
        wx, wy = self._screen_to_world(event.x, event.y)
        self._drag_state = {"node_id": node_id, "x": wx, "y": wy}

    def _drag_node(self, event):
        if not self._drag_state:
            return
        wx, wy = self._screen_to_world(event.x, event.y)
        dx = wx - self._drag_state["x"]
        dy = wy - self._drag_state["y"]
        node = self.model.get_node(self._drag_state["node_id"])
        if node:
            self.model.move_node(node["id"], int(node.get("x", 0) + dx), int(node.get("y", 0) + dy))
            self._drag_state["x"], self._drag_state["y"] = wx, wy
            self.render()

    def _end_node_drag(self, _event):
        self._drag_state = None
        self._emit_change()

    def _start_pan(self, event):
        self._pan_state = {"x": event.x, "y": event.y}

    def _pan(self, event):
        if not self._pan_state:
            return
        self._offset_x += event.x - self._pan_state["x"]
        self._offset_y += event.y - self._pan_state["y"]
        self._pan_state = {"x": event.x, "y": event.y}
        self.render()

    def _end_pan(self, _event):
        self._pan_state = None

    def _double_click(self, event):
        item = self.canvas.find_withtag("current")
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        if "node" in tags:
            self._edit_node(tags[-1])
        if "link" in tags or "link_label" in tags:
            self._edit_link(tags[-1])

    def _edit_node(self, node_id):
        node = self.model.get_node(node_id)
        if not node:
            return
        title = simpledialog.askstring("Edit node", "Node title:", initialvalue=str(node.get("title") or ""))
        if title is not None:
            node["title"] = title
            self._emit_change(); self.render()

    def _edit_link(self, link_id):
        link = self.model.get_link(link_id)
        if not link:
            return
        text = simpledialog.askstring("Edit link", "Link label:", initialvalue=str(link.get("label") or ""))
        if text is not None:
            link["label"] = text
            self._emit_change(); self.render()

    def _canvas_menu(self, event):
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Add scene", command=lambda: self._add_node_at(event.x, event.y, "scene"))
        menu.add_command(label="Add condition", command=lambda: self._add_node_at(event.x, event.y, "condition"))
        menu.add_command(label="Reset Zoom", command=self.reset_zoom)
        menu.add_command(label="Fit", command=self.fit_view)
        menu.tk_popup(event.x_root, event.y_root)

    def _link_menu(self, event, link_id):
        self.select_link(link_id)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Edit link", command=lambda: self._edit_link(link_id))
        menu.add_command(label="Delete link", command=lambda: (self.model.remove_link(link_id), self._emit_change(), self.render()))
        menu.tk_popup(event.x_root, event.y_root)

    def _add_node_at(self, sx, sy, kind):
        wx, wy = self._screen_to_world(sx, sy)
        node_id = normalise_flow_node_id(kind, [n.get("id") for n in self.model.payload.get("nodes") or []])
        self.model.payload.setdefault("nodes", []).append({"id": node_id, "title": kind.title(), "scene_index": len(self.model.payload.get("nodes") or []), "x": int(wx), "y": int(wy), "kind": kind, "summary": ""})
        self._emit_change(); self.render()

    def _start_link_drag(self, event, node_id):
        self._drag_link_source = node_id

    def _emit_change(self):
        if self.on_change:
            self.on_change()

    def select_node(self, node_id, emit=False):
        self._selected_link_id = None
        self._selected_node_id = str(node_id or "")
        if emit and self.on_select:
            self.on_select(self._selected_node_id, source="canvas")

    def select_link(self, link_id):
        self._selected_node_id = None
        self._selected_link_id = str(link_id or "")

    def delete_selected(self):
        if self._selected_node_id:
            self.model.remove_node(self._selected_node_id)
        elif self._selected_link_id:
            self.model.remove_link(self._selected_link_id)
        self._emit_change(); self.render()

    def duplicate_selected(self):
        if not self._selected_node_id:
            return
        src = self.model.get_node(self._selected_node_id)
        if not src:
            return
        clone = copy.deepcopy(src)
        clone["id"] = normalise_flow_node_id(clone.get("title") or "scene", [n.get("id") for n in self.model.payload.get("nodes")])
        clone["x"] = int(clone.get("x", 0)) + 40
        clone["y"] = int(clone.get("y", 0)) + 40
        self.model.payload.setdefault("nodes", []).append(clone)
        self._emit_change(); self.render()

    def save_state(self):
        if callable(self.on_save):
            self.on_save()

    def reset_zoom(self):
        self._zoom = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self.render()

    def fit_view(self):
        self.reset_zoom()
