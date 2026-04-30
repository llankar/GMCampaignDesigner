from __future__ import annotations

import copy
import re
import tkinter as tk
from tkinter import simpledialog

import customtkinter as ctk

from modules.scenarios.wizard_steps.scenes.component_library.definitions import COMPONENT_GROUPS
from modules.scenarios.scene_flow_rendering import apply_scene_flow_canvas_styling
from modules.scenarios.wizard_steps.scenes.component_library.node_factory import build_default_node
from modules.scenarios.wizard_steps.scenes.flow_canvas.minimap import minimap_to_world, world_to_minimap
from modules.scenarios.wizard_steps.scenes.flow_canvas.model import FlowCanvasModel
from modules.scenarios.wizard_steps.scenes.flow_canvas.node_rendering import NODE_STYLES as _NODE_STYLES, resolve_node_visual
from modules.scenarios.wizard_steps.scenes.flow_canvas.viewport import (
    ZOOM_MAX,
    ZOOM_MIN,
    clamp_zoom,
    compute_fit_viewport,
)
from modules.scenarios.wizard_steps.scenes.visual_flow.commands import (
    make_create_link_command,
    make_delete_node_command,
    make_update_link_command,
)
from modules.scenarios.wizard_steps.scenes.visual_flow.interactions import (
    normalise_link_selection,
    normalise_single_selection,
    now,
    resolve_link_target,
    should_open_context_menu,
)
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

_CONDITION_LABELS = {"yes": "Yes", "no": "No", "success": "Success", "failure": "Failure"}


def _menu_node_entries():
    by_kind = {}
    for group in COMPONENT_GROUPS:
        for item in group.get("items") or []:
            kind = str(item.get("kind") or "").strip()
            label = str(item.get("label") or "").strip()
            icon = str(item.get("icon") or "").strip()
            if kind and label:
                by_kind[kind] = {"kind": kind, "label": label, "icon": icon}
    ordered_kinds = ["scene", "objective", "side_objective", "interaction", "condition", "action", "note"]
    return [by_kind[kind] for kind in ordered_kinds if kind in by_kind]


_CANVAS_MENU_NODE_ENTRIES = _menu_node_entries()


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
        self._toolbar = ctk.CTkFrame(self, fg_color="#111827")
        self._toolbar.place(relx=1.0, x=-12, y=12, anchor="ne")
        ctk.CTkButton(self._toolbar, text="−", width=28, command=self.zoom_out).pack(side="left", padx=(6, 4), pady=6)
        ctk.CTkButton(self._toolbar, text="+", width=28, command=self.zoom_in).pack(side="left", padx=4, pady=6)
        ctk.CTkButton(self._toolbar, text="Fit", width=42, command=self.fit_view).pack(side="left", padx=(4, 6), pady=6)
        self._node_items = {}
        self._link_items = {}
        self._selected_node_id = None
        self._selected_link_id = None
        self._drag_state = None
        self._pan_state = None
        self._space_held = False
        self._drag_link_source = None
        self._drag_link_preview_item = None
        self._context_press_ts = 0.0
        self._zoom = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._minimap_drag_active = False
        self._minimap_projection = None
        self._bind_events()

    def _bind_events(self):
        self.canvas.bind("<MouseWheel>", self._zoom_view)
        self.canvas.bind("<Button-4>", self._zoom_view)
        self.canvas.bind("<Button-5>", self._zoom_view)
        self.canvas.bind("<Button-2>", self._start_pan)
        self.canvas.bind("<B2-Motion>", self._pan)
        self.canvas.bind("<ButtonRelease-2>", self._end_pan)
        self.canvas.bind("<Button-3>", self._on_context_press)
        self.canvas.bind("<ButtonRelease-3>", self._canvas_menu)
        self.canvas.bind("<ButtonRelease-1>", self._complete_link_drag, add="+")
        self.canvas.bind("<B1-Motion>", self._drag_link_motion, add="+")
        self.canvas.bind("<Double-1>", self._double_click)
        self.canvas.bind_all("<Escape>", self._cancel_link_drag)
        self.canvas.bind("<Control-0>", lambda _e: self.reset_zoom())
        self.canvas.bind("<Control-plus>", lambda _e: self.zoom_in())
        self.canvas.bind("<Control-equal>", lambda _e: self.zoom_in())
        self.canvas.bind("<Control-minus>", lambda _e: self.zoom_out())
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

    def get_viewport_state(self):
        return {"x": self._offset_x, "y": self._offset_y, "zoom": self._zoom}

    def set_viewport_state(self, viewport_dict):
        if not isinstance(viewport_dict, dict):
            return
        x = viewport_dict.get("x", self._offset_x)
        y = viewport_dict.get("y", self._offset_y)
        zoom = viewport_dict.get("zoom", self._zoom)
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return
        if not isinstance(zoom, (int, float)) or zoom <= 0:
            return
        self._offset_x = int(x)
        self._offset_y = int(y)
        self._zoom = float(zoom)
        self.render()

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
            style = resolve_node_visual(kind, selected=nid == self._selected_node_id)
            x, y = self._world_to_screen(int(node.get("x", 0)), int(node.get("y", 0)))
            w, h = 190 * self._zoom, 88 * self._zoom
            if style["shape"] == "diamond":
                body = self.canvas.create_polygon(
                    x + w / 2, y, x + w, y + h / 2, x + w / 2, y + h, x, y + h / 2,
                    fill=style["body_fill"], outline=style["body_outline"], width=style["body_width"], tags=("node", nid)
                )
            elif style["shape"] == "note":
                body = self.canvas.create_rectangle(x, y, x + w, y + h, fill=style["body_fill"], outline=style["body_outline"], width=style["body_width"], tags=("node", nid))
                self.canvas.create_polygon(x + w - 26, y, x + w, y, x + w, y + 26, fill="#525252", outline=style["body_outline"], width=1, tags=("node", nid))
            else:
                body = self.canvas.create_rectangle(x, y, x + w, y + h, fill=style["body_fill"], outline=style["body_outline"], width=style["body_width"], tags=("node", nid))

            self.canvas.create_text(x + 10, y + 10, text=f"{style['symbol']} {node.get('title') or 'Untitled'}", anchor="nw", fill=style["title_color"], tags=("node", nid))
            handle = self.canvas.create_oval(x + w - 14, y + h / 2 - 6, x + w - 2, y + h / 2 + 6, fill=style["handle_fill"], outline=style["handle_outline"], tags=("handle", nid))
            self._node_items[nid] = {"body": body, "handle": handle}
            self.canvas.tag_bind(body, "<Button-1>", lambda e, node_id=nid: self._start_node_drag(e, node_id))
            self.canvas.tag_bind(body, "<B1-Motion>", self._drag_node)
            self.canvas.tag_bind(body, "<ButtonRelease-1>", self._end_node_drag)
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


    def _zoom_view(self, event):
        direction = self._event_zoom_direction(event)
        if direction == 0:
            return
        self._zoom_around_screen_point(event.x, event.y, factor=1.1 if direction > 0 else (1.0 / 1.1))

    @staticmethod
    def _event_zoom_direction(event):
        delta = getattr(event, "delta", 0)
        if delta > 0:
            return 1
        if delta < 0:
            return -1
        num = getattr(event, "num", None)
        if num == 4:
            return 1
        if num == 5:
            return -1
        return 0

    def _zoom_around_screen_point(self, sx, sy, *, factor):
        prev_zoom = self._zoom
        next_zoom = clamp_zoom(prev_zoom * float(factor), minimum=ZOOM_MIN, maximum=ZOOM_MAX)
        if abs(next_zoom - prev_zoom) < 1e-9:
            return
        wx, wy = self._screen_to_world(sx, sy)
        self._zoom = next_zoom
        self._offset_x = int(round(sx - wx * self._zoom))
        self._offset_y = int(round(sy - wy * self._zoom))
        self.render()

    def zoom_in(self):
        self._zoom_around_screen_point(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2, factor=1.1)

    def zoom_out(self):
        self._zoom_around_screen_point(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2, factor=1.0 / 1.1)

    def _compute_world_bounds(self):
        nodes = self.model.payload.get("nodes") or []
        if not nodes:
            return (0.0, 0.0, 1000.0, 700.0)
        left = min(float(n.get("x", 0)) for n in nodes)
        top = min(float(n.get("y", 0)) for n in nodes)
        right = max(float(n.get("x", 0)) + 190.0 for n in nodes)
        bottom = max(float(n.get("y", 0)) + 88.0 for n in nodes)
        return (left - 80.0, top - 80.0, right + 80.0, bottom + 80.0)

    def _apply_minimap_recenter(self, sx, sy):
        projection = self._minimap_projection
        if not projection:
            return
        world_x, world_y = minimap_to_world(
            sx,
            sy,
            world_bounds=projection["world_bounds"],
            minimap_bounds=projection["minimap_bounds"],
        )
        self._offset_x = int(self.canvas.winfo_width() / 2 - world_x * self._zoom)
        self._offset_y = int(self.canvas.winfo_height() / 2 - world_y * self._zoom)
        self.render()

    def _start_minimap_drag(self, event):
        self._minimap_drag_active = True
        self._apply_minimap_recenter(event.x, event.y)

    def _drag_minimap(self, event):
        if self._minimap_drag_active:
            self._apply_minimap_recenter(event.x, event.y)

    def _end_minimap_drag(self, _event):
        self._minimap_drag_active = False

    def _draw_minimap(self):
        mini_left, mini_top = 16, self.canvas.winfo_height() - 126
        mini_right, mini_bottom = 176, self.canvas.winfo_height() - 16
        minimap_bounds = (mini_left + 8, mini_top + 8, mini_right - 8, mini_bottom - 8)
        world_bounds = self._compute_world_bounds()
        self._minimap_projection = {"world_bounds": world_bounds, "minimap_bounds": minimap_bounds}

        shell = self.canvas.create_rectangle(mini_left, mini_top, mini_right, mini_bottom, fill="#111827", outline="#4b5563", tags=("minimap",))
        self.canvas.tag_bind(shell, "<Button-1>", self._start_minimap_drag)
        self.canvas.tag_bind(shell, "<B1-Motion>", self._drag_minimap)
        self.canvas.tag_bind(shell, "<ButtonRelease-1>", self._end_minimap_drag)

        for node in self.model.payload.get("nodes") or []:
            wx = float(node.get("x", 0)) + 95.0
            wy = float(node.get("y", 0)) + 44.0
            mx, my = world_to_minimap(wx, wy, world_bounds=world_bounds, minimap_bounds=minimap_bounds)
            dot = self.canvas.create_oval(mx - 2, my - 2, mx + 2, my + 2, fill="#93c5fd", outline="", tags=("minimap",))
            self.canvas.tag_bind(dot, "<Button-1>", self._start_minimap_drag)
            self.canvas.tag_bind(dot, "<B1-Motion>", self._drag_minimap)
            self.canvas.tag_bind(dot, "<ButtonRelease-1>", self._end_minimap_drag)

        vw, vh = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        top_left_world = self._screen_to_world(0, 0)
        bottom_right_world = self._screen_to_world(vw, vh)
        vx1, vy1 = world_to_minimap(top_left_world[0], top_left_world[1], world_bounds=world_bounds, minimap_bounds=minimap_bounds)
        vx2, vy2 = world_to_minimap(bottom_right_world[0], bottom_right_world[1], world_bounds=world_bounds, minimap_bounds=minimap_bounds)
        self.canvas.create_rectangle(vx1, vy1, vx2, vy2, outline="#fbbf24", width=1, tags=("minimap",))

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

    def _on_context_press(self, _event):
        self._context_press_ts = now()

    def _canvas_menu(self, event):
        if not should_open_context_menu(3, self._context_press_ts, now()):
            return
        menu = tk.Menu(self, tearoff=False)
        for entry in _CANVAS_MENU_NODE_ENTRIES:
            menu.add_command(
                label=f"Add {entry['icon']} {entry['label']}",
                command=lambda node_kind=entry["kind"]: self._add_node_at(event.x, event.y, node_kind),
            )
        menu.add_command(label="Reset Zoom", command=self.reset_zoom)
        menu.add_command(label="Fit", command=self.fit_view)
        menu.tk_popup(event.x_root, event.y_root)

    def _link_menu(self, event, link_id):
        if not should_open_context_menu(3, self._context_press_ts, now()):
            return
        self.select_link(link_id)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Edit link", command=lambda: self._edit_link(link_id))
        menu.add_command(label="Delete link", command=lambda: (self.model.remove_link(link_id), self._emit_change(), self.render()))
        menu.tk_popup(event.x_root, event.y_root)

    def _add_node_at(self, sx, sy, kind):
        wx, wy = self._screen_to_world(sx, sy)
        self._create_node(kind=kind, x=int(wx), y=int(wy))
        self._emit_change(); self.render()

    def _create_node(self, kind, x, y):
        existing_nodes = self.model.payload.get("nodes") or []
        node = build_default_node(kind=kind, x=int(x), y=int(y), existing_ids=[n.get("id") for n in existing_nodes], scene_index=len(existing_nodes))
        self.model.payload.setdefault("nodes", []).append(node)
        return node

    def create_node_at_viewport_center(self, kind):
        cx = self.canvas.winfo_width() / 2
        cy = self.canvas.winfo_height() / 2
        wx, wy = self._screen_to_world(cx, cy)
        node = self._create_node(kind=kind, x=int(wx), y=int(wy))
        self._emit_change()
        self.render()
        return node

    def _start_link_drag(self, event, node_id):
        self._drag_link_source = str(node_id or "").strip() or None
        self._update_link_preview(event.x, event.y)

    def _drag_link_motion(self, event):
        if not self._drag_link_source:
            return
        self._update_link_preview(event.x, event.y)

    def _update_link_preview(self, sx, sy):
        if not self._drag_link_source:
            self._clear_link_preview()
            return
        source_node = self.model.get_node(self._drag_link_source)
        if not source_node:
            self._clear_link_preview()
            return
        from_x, from_y = self._world_to_screen(int(source_node.get("x", 0)) + 190, int(source_node.get("y", 0)) + 44)
        if self._drag_link_preview_item:
            self.canvas.coords(self._drag_link_preview_item, from_x, from_y, sx, sy)
        else:
            self._drag_link_preview_item = self.canvas.create_line(
                from_x, from_y, sx, sy, fill="#7dd3fc", width=2, dash=(6, 4), tags=("link_preview",)
            )

    def _clear_link_preview(self):
        if self._drag_link_preview_item:
            self.canvas.delete(self._drag_link_preview_item)
            self._drag_link_preview_item = None

    def _cancel_link_drag(self, _event=None):
        self._drag_link_source = None
        self._clear_link_preview()

    def _resolve_link_target_from_geometry(self, source_id, sx, sy):
        wx, wy = self._screen_to_world(sx, sy)
        best_target = None
        best_distance = None
        for node in self.model.payload.get("nodes") or []:
            node_id = str(node.get("id") or "")
            if not node_id or node_id == source_id:
                continue
            nx, ny = int(node.get("x", 0)), int(node.get("y", 0))
            left, top, right, bottom = nx, ny, nx + 190, ny + 88
            if left <= wx <= right and top <= wy <= bottom:
                return node_id
            cx, cy = nx + 95, ny + 44
            dist = ((wx - cx) ** 2 + (wy - cy) ** 2) ** 0.5
            if best_distance is None or dist < best_distance:
                best_target = node_id
                best_distance = dist
        if best_distance is not None and best_distance <= 120:
            return best_target
        return None

    def _complete_link_drag(self, event):
        if not self._drag_link_source:
            return
        source_id = self._drag_link_source
        self._drag_link_source = None
        self._clear_link_preview()
        item = self.canvas.find_withtag("current")
        target_id = None
        if item:
            tags = self.canvas.gettags(item[0])
            if "node" in tags and len(tags) > 1:
                target_id = tags[-1]
        if not target_id:
            target_id = self._resolve_link_target_from_geometry(source_id, event.x, event.y)
        target_id = resolve_link_target(source_id, [target_id])
        if not target_id:
            return
        existing = self.model.payload.setdefault("links", [])
        link = {"id": normalise_flow_node_id(f"{source_id}-{target_id}", [l.get("id") for l in existing]), "source": source_id, "target": target_id, "label": "", "kind": "scene_link"}
        existing.append(link)
        cmd = make_create_link_command(source_id=source_id, target_id=target_id, link_payload=link)
        if cmd.changed:
            self.select_link(link["id"])
            self._emit_change()
            self.render()
            self._edit_link(link["id"])

    def _emit_change(self):
        if self.on_change:
            self.on_change()

    def select_node(self, node_id, emit=False):
        self._selected_node_id, self._selected_link_id = normalise_single_selection(node_id)
        self._selected_node_id = self._selected_node_id or ""
        if emit and self.on_select:
            self.on_select(self._selected_node_id, source="canvas")

    def select_link(self, link_id):
        self._selected_node_id, self._selected_link_id = normalise_link_selection(link_id)
        self._selected_link_id = self._selected_link_id or ""

    def delete_selected(self):
        changed = False
        if self._selected_node_id:
            node = self.model.get_node(self._selected_node_id)
            links = [l for l in (self.model.payload.get("links") or []) if l.get("source") == self._selected_node_id or l.get("target") == self._selected_node_id]
            cmd = make_delete_node_command(node_id=self._selected_node_id, removed_node=node, removed_links=links)
            changed = self.model.remove_node(self._selected_node_id) and cmd.changed
        elif self._selected_link_id:
            link = self.model.get_link(self._selected_link_id)
            changed = self.model.remove_link(self._selected_link_id)
            _ = make_update_link_command(link_id=self._selected_link_id, before=link or {}, after={})
        if changed:
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
        viewport = compute_fit_viewport(
            self.model.payload.get("nodes") or [],
            canvas_width=self.canvas.winfo_width(),
            canvas_height=self.canvas.winfo_height(),
        )
        self._zoom = viewport["zoom"]
        self._offset_x = int(round(viewport["offset_x"]))
        self._offset_y = int(round(viewport["offset_y"]))
        self.render()
