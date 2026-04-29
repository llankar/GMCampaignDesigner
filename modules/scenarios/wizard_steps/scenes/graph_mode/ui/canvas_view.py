from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from .edge_renderer import EdgeDrawSpec, EdgeRenderer


class GraphCanvasView(ctk.CTkFrame):
    """Interactive graph canvas with incremental updates."""

    NODE_W = 220
    NODE_H = 100

    def __init__(self, master):
        super().__init__(master, corner_radius=12, fg_color="#0b1220")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, bg="#0b1220", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.grid_snap = True
        self.grid_size = 24

        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str, str]] = []
        self.selected_nodes: set[str] = set()
        self.selected_edge_id: str | None = None
        self._drag_node: str | None = None
        self._drag_offset = (0, 0)
        self._space_pan = False
        self._connecting_from: str | None = None
        self._preview_edge_id: int | None = None
        self.edge_renderer = EdgeRenderer()
        self.on_selection_change = None

        self.canvas.bind("<Button-1>", self._on_left_down)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_up)
        self.canvas.bind("<Button-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_drag)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<KeyPress-space>", lambda _e: self._set_space_pan(True))
        self.canvas.bind_all("<KeyRelease-space>", lambda _e: self._set_space_pan(False))

    def load_scenes(self, scenes: list[dict]) -> None:
        self.nodes.clear()
        self.edges.clear()
        self.selected_nodes.clear()
        self.selected_edge_id = None
        for idx, scene in enumerate(scenes, start=1):
            node_id = scene.get("id") or f"scene_{idx}"
            self.nodes[node_id] = {
                "title": scene.get("title") or f"Scène {idx}",
                "x": scene.get("x", (idx - 1) * 280),
                "y": scene.get("y", 0),
                "items": {},
            }
            if idx > 1:
                prev = scenes[idx - 2].get("id") or f"scene_{idx-1}"
                self.edges.append((f"edge_{idx-1}_{idx}", prev, node_id))
        self.redraw_full()

    def redraw_full(self) -> None:
        self.canvas.delete("all")
        self.edge_renderer.clear(self.canvas)
        self._draw_grid()
        for node_id in self.nodes:
            self._draw_node(node_id)
        self._redraw_edges()

    def fit_to_view(self) -> None:
        if not self.nodes:
            return
        xs = [n["x"] for n in self.nodes.values()]
        ys = [n["y"] for n in self.nodes.values()]
        self.pan_x = -min(xs) + 40
        self.pan_y = -min(ys) + 40
        self.redraw_full()

    def _draw_grid(self) -> None:
        step = int(self.grid_size * self.zoom)
        if step < 8:
            return
        w = self.canvas.winfo_width() or 900
        h = self.canvas.winfo_height() or 600
        for x in range(int(self.pan_x) % step, w, step):
            self.canvas.create_line(x, 0, x, h, fill="#111a2d", tags=("grid",))
        for y in range(int(self.pan_y) % step, h, step):
            self.canvas.create_line(0, y, w, y, fill="#111a2d", tags=("grid",))

    def _draw_node(self, node_id: str) -> None:
        n = self.nodes[node_id]
        x, y = self._world_to_screen(n["x"], n["y"])
        w, h = self.NODE_W * self.zoom, self.NODE_H * self.zoom
        selected = node_id in self.selected_nodes
        outline = "#facc15" if selected else "#334155"
        fill = "#172033"
        items = n["items"]
        if not items:
            items["rect"] = self.canvas.create_rectangle(x, y, x + w, y + h, fill=fill, outline=outline, width=2, tags=("node", node_id))
            items["title"] = self.canvas.create_text(x + 12, y + 18, anchor="w", text=n["title"], fill="#e2e8f0", font=("Arial", max(10, int(12 * self.zoom))), tags=("node", node_id))
            items["out"] = self.canvas.create_oval(x + w - 12, y + h / 2 - 6, x + w, y + h / 2 + 6, fill="#22d3ee", outline="", tags=("connector", f"out::{node_id}"))
            items["in"] = self.canvas.create_oval(x, y + h / 2 - 6, x + 12, y + h / 2 + 6, fill="#94a3b8", outline="", tags=("connector", f"in::{node_id}"))
        else:
            self.canvas.coords(items["rect"], x, y, x + w, y + h)
            self.canvas.coords(items["title"], x + 12, y + 18)
            self.canvas.itemconfig(items["title"], text=n["title"], font=("Arial", max(10, int(12 * self.zoom))))
            self.canvas.coords(items["out"], x + w - 12, y + h / 2 - 6, x + w, y + h / 2 + 6)
            self.canvas.coords(items["in"], x, y + h / 2 - 6, x + 12, y + h / 2 + 6)
            self.canvas.itemconfig(items["rect"], outline=outline)

    def _redraw_edges(self) -> None:
        for edge_id, src, dst in self.edges:
            if src not in self.nodes or dst not in self.nodes:
                continue
            sx, sy = self._connector_world(src, True)
            tx, ty = self._connector_world(dst, False)
            ss = self._world_to_screen(sx, sy)
            ts = self._world_to_screen(tx, ty)
            self.edge_renderer.draw_or_update(self.canvas, EdgeDrawSpec(edge_id=edge_id, source_center=ss, target_center=ts, selected=edge_id == self.selected_edge_id))

    def _connector_world(self, node_id: str, out: bool) -> tuple[float, float]:
        n = self.nodes[node_id]
        return (n["x"] + (self.NODE_W if out else 0), n["y"] + self.NODE_H / 2)


    def focus_on_node(self, node_id: str) -> None:
        if node_id not in self.nodes:
            return
        self.selected_nodes = {node_id}
        self.selected_edge_id = None
        node = self.nodes[node_id]
        self.pan_x = (self.canvas.winfo_width() or 900) / 2 - (node["x"] + self.NODE_W / 2) * self.zoom
        self.pan_y = (self.canvas.winfo_height() or 600) / 2 - (node["y"] + self.NODE_H / 2) * self.zoom
        self.redraw_full()
        self._notify_selection()

    def focus_on_edge(self, edge_id: str) -> None:
        if not any(existing_edge_id == edge_id for existing_edge_id, _src, _dst in self.edges):
            return
        self.selected_edge_id = edge_id
        self.selected_nodes.clear()
        self._redraw_edges()
        self._notify_selection()

    def _on_left_down(self, event):
        if self._space_pan:
            self._on_pan_start(event)
            return
        tags = self.canvas.gettags("current")
        shift = bool(event.state & 0x1)
        connector_tag = next((t for t in tags if t.startswith("out::")), None)
        if connector_tag:
            self._connecting_from = connector_tag.split("::", 1)[1]
            return
        node_tag = next((t for t in tags if t in self.nodes), None)
        if node_tag:
            if shift:
                if node_tag in self.selected_nodes:
                    self.selected_nodes.remove(node_tag)
                else:
                    self.selected_nodes.add(node_tag)
            else:
                self.selected_nodes = {node_tag}
                self.selected_edge_id = None
            self._drag_node = node_tag
            wx, wy = self._screen_to_world(event.x, event.y)
            self._drag_offset = (wx - self.nodes[node_tag]["x"], wy - self.nodes[node_tag]["y"])
            self._update_selection_visuals()
            self._notify_selection()
            return
        edge = self.edge_renderer.hit_test(event.x, event.y)
        if edge:
            self.selected_edge_id = edge
            self.selected_nodes.clear()
            self._redraw_edges()
            self._notify_selection()
            return
        self.selected_nodes.clear()
        self.selected_edge_id = None
        self._update_selection_visuals()
        self._notify_selection()

    def _on_left_drag(self, event):
        if self._space_pan:
            self._on_pan_drag(event)
            return
        if self._drag_node:
            wx, wy = self._screen_to_world(event.x, event.y)
            nx = wx - self._drag_offset[0]
            ny = wy - self._drag_offset[1]
            if self.grid_snap:
                nx = round(nx / self.grid_size) * self.grid_size
                ny = round(ny / self.grid_size) * self.grid_size
            self.nodes[self._drag_node]["x"] = nx
            self.nodes[self._drag_node]["y"] = ny
            self._draw_node(self._drag_node)
            self._redraw_edges()
        elif self._connecting_from:
            sx, sy = self._connector_world(self._connecting_from, True)
            sx, sy = self._world_to_screen(sx, sy)
            if self._preview_edge_id is None:
                self._preview_edge_id = self.canvas.create_line(sx, sy, event.x, event.y, fill="#38bdf8", dash=(4, 4), width=2)
            else:
                self.canvas.coords(self._preview_edge_id, sx, sy, event.x, event.y)

    def _on_left_up(self, event):
        tags = self.canvas.gettags("current")
        in_tag = next((t for t in tags if t.startswith("in::")), None)
        if self._connecting_from and in_tag:
            dst = in_tag.split("::", 1)[1]
            if dst != self._connecting_from:
                edge_id = f"edge_{self._connecting_from}_{dst}_{len(self.edges)+1}"
                self.edges.append((edge_id, self._connecting_from, dst))
                self._redraw_edges()
        self._drag_node = None
        self._connecting_from = None
        if self._preview_edge_id:
            self.canvas.delete(self._preview_edge_id)
            self._preview_edge_id = None

    def _on_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _on_pan_drag(self, event):
        dx = event.x - self.canvas.canvasx(0)
        dy = event.y - self.canvas.canvasy(0)
        self.pan_x += dx * 0.02
        self.pan_y += dy * 0.02
        self.redraw_full()

    def _on_wheel(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom = min(2.5, max(0.4, self.zoom * factor))
        self.redraw_full()

    def _set_space_pan(self, active: bool):
        self._space_pan = active

    def _world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        return x * self.zoom + self.pan_x, y * self.zoom + self.pan_y

    def _screen_to_world(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.pan_x) / self.zoom, (y - self.pan_y) / self.zoom

    def _update_selection_visuals(self) -> None:
        for node_id in self.nodes:
            self._draw_node(node_id)
        self._redraw_edges()

    def _notify_selection(self) -> None:
        if self.on_selection_change is None:
            return
        node_id = next(iter(self.selected_nodes), None) if self.selected_nodes else None
        self.on_selection_change(node_id, self.selected_edge_id)
