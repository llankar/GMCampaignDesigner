"""Scenario-wizard styled character graph embedded in the GM scenario board."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import customtkinter as ctk

from modules.scenarios.scenario_character_graph import ScenarioCharacterGraphEditor


LINK_LABEL_TAG = "link_label"
LINK_LABEL_BG_TAG = "link_text_bg"
LINK_LABEL_PADDING = (5, 3)
BOARD_LABEL_MAX_CHARS = 44
BOARD_LABEL_MAX_PARTS = 3
BOARD_LINK_COLORS = (
    "#FFB86C",
    "#8BE9FD",
    "#50FA7B",
    "#FF79C6",
    "#F1FA8C",
    "#BD93F9",
    "#66D9EF",
    "#A6E22E",
    "#FD971F",
    "#E6DB74",
    "#AE81FF",
    "#F92672",
)


def renderable_character_graph_links(
    graph_data: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """Return links whose endpoints exist and can be drawn on the board."""
    if not isinstance(graph_data, Mapping):
        return []
    raw_nodes = graph_data.get("nodes")
    if not isinstance(raw_nodes, (list, tuple)):
        return []
    node_tags = {
        node.get("tag")
        for node in raw_nodes
        if isinstance(node, Mapping) and node.get("tag")
    }
    if not node_tags:
        return []
    raw_links = graph_data.get("links")
    if not isinstance(raw_links, (list, tuple)):
        return []
    links: list[Mapping[str, Any]] = []
    for link in raw_links:
        if not isinstance(link, Mapping):
            continue
        tag1 = link.get("node1_tag")
        tag2 = link.get("node2_tag")
        if tag1 and tag2 and tag1 != tag2 and tag1 in node_tags and tag2 in node_tags:
            links.append(link)
    return links


def has_renderable_character_graph_links(graph_data: Mapping[str, Any]) -> bool:
    """Return whether the board graph has at least one drawable relationship."""
    return bool(renderable_character_graph_links(graph_data))


def padded_text_bbox(bbox, pad_x=LINK_LABEL_PADDING[0], pad_y=LINK_LABEL_PADDING[1]):
    """Return rectangle coords padded around a canvas text bbox."""
    return (
        bbox[0] - pad_x,
        bbox[1] - pad_y,
        bbox[2] + pad_x,
        bbox[3] + pad_y,
    )


class ScenarioBoardCharacterGraph(ScenarioCharacterGraphEditor):
    """A presentation-focused variant of the wizard's character graph."""

    def load_graph_data(self, graph_data):
        """Load board graph data and apply a presentation layout during first draw."""
        self._board_layout_applied = False
        super().load_graph_data(graph_data)

    def init_toolbar(self) -> None:
        """Replace editing actions with a compact viewing hint."""
        toolbar = ctk.CTkFrame(self, fg_color="#172536", corner_radius=0)
        toolbar.pack(fill="x")
        ctk.CTkLabel(
            toolbar,
            text="NPC RELATIONSHIPS",
            text_color="#f3f7fb",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=12, pady=8)
        ctk.CTkLabel(
            toolbar,
            text="Drag to inspect · Ctrl + wheel to zoom",
            text_color="#9db4d1",
            font=ctk.CTkFont(size=10),
        ).pack(side="right", padx=12, pady=8)

    def on_right_click(self, _event):
        """Keep the board representation free of destructive context actions."""
        return "break"

    def open_character_editor(self, _event):
        """Prevent the presentation-only board from opening an editable record."""
        return "break"

    def _stable_link_signature(self, link):
        """Return data-derived fields used to order board links for colouring."""
        if not isinstance(link, dict):
            return ("", "", "", "")
        return (
            str(link.get("node1_tag") or ""),
            str(link.get("node2_tag") or ""),
            str(link.get("text") or ""),
            str(link.get("arrow_mode") or "both"),
        )

    def _fallback_link_color_index(self, link):
        """Return a deterministic palette index for links outside the current graph."""
        seed = "|".join(self._stable_link_signature(link))
        return sum((index + 1) * ord(char) for index, char in enumerate(seed)) % len(
            BOARD_LINK_COLORS
        )

    def _ordered_board_links_for_colors(self):
        """Return renderable links in a stable order for deterministic palette use."""
        graph = getattr(self, "graph", {}) or {}
        raw_links = [
            link for link in graph.get("links", []) if isinstance(link, dict)
        ]
        if not raw_links:
            return []

        node_positions = getattr(self, "node_positions", {}) or {}
        if node_positions:
            links = [
                link
                for link in raw_links
                if link.get("node1_tag") in node_positions
                and link.get("node2_tag") in node_positions
                and link.get("node1_tag") != link.get("node2_tag")
            ]
        else:
            links = raw_links

        indexed_links = [
            (self._stable_link_signature(link), index, link)
            for index, link in enumerate(links)
        ]
        return [
            link
            for _signature, _index, link in sorted(
                indexed_links,
                key=lambda item: (item[0], item[1]),
            )
        ]

    def _board_link_color(self, link):
        """Return this link's stable readable colour without mutating graph data."""
        for index, candidate in enumerate(self._ordered_board_links_for_colors()):
            if candidate is link:
                return BOARD_LINK_COLORS[index % len(BOARD_LINK_COLORS)]
        return BOARD_LINK_COLORS[self._fallback_link_color_index(link)]

    def _get_link_style(self, link):
        """Use a stable readable board link colour on the dark scenario surface."""
        is_selected = bool(
            self.selected_link and self._link_matches(link, self.selected_link)
        )
        return self._board_link_color(link), 3 if is_selected else 2

    def draw_arrowhead(self, node_tag, target_x, target_y, color, item_tag=None):
        """Draw board arrowheads with fill and outline matching the link colour."""
        arrow_id = super().draw_arrowhead(
            node_tag,
            target_x,
            target_y,
            color,
            item_tag=item_tag,
        )
        self.canvas.itemconfig(arrow_id, outline=color)
        return arrow_id

    def _valid_board_links(self):
        """Return drawable links whose endpoints exist in the current graph."""
        graph = getattr(self, "graph", {}) or {}
        return list(renderable_character_graph_links(graph))

    def _ordered_board_nodes(self, nodes, links):
        """Order linked nodes deterministically so related NPCs tend to sit nearby."""
        node_by_tag = {node.get("tag"): node for node in nodes if node.get("tag")}
        original_index = {node.get("tag"): index for index, node in enumerate(nodes)}
        adjacency = {tag: set() for tag in node_by_tag}
        for link in links:
            tag1 = link.get("node1_tag")
            tag2 = link.get("node2_tag")
            if tag1 in adjacency and tag2 in adjacency:
                adjacency[tag1].add(tag2)
                adjacency[tag2].add(tag1)

        def sort_key(tag):
            node = node_by_tag[tag]
            return (-len(adjacency[tag]), str(node.get("entity_name") or tag).casefold(), original_index[tag])

        remaining = set(node_by_tag)
        ordered_tags = []
        while remaining:
            if not ordered_tags:
                tag = min(remaining, key=sort_key)
            else:
                previous = ordered_tags[-1]
                tag = min(
                    remaining,
                    key=lambda candidate: (
                        candidate not in adjacency[previous],
                        -len(adjacency[candidate] & set(ordered_tags)),
                        *sort_key(candidate),
                    ),
                )
            ordered_tags.append(tag)
            remaining.remove(tag)
        return [node_by_tag[tag] for tag in ordered_tags]

    def _readable_board_node_positions(self, nodes, links):
        """Return spaced, stable board positions for NPC relationship nodes."""
        ordered_nodes = self._ordered_board_nodes(nodes, links)
        count = len(ordered_nodes)
        if not count:
            return {}

        scale = getattr(self, "canvas_scale", 1.0) or 1.0
        if count == 1:
            return {ordered_nodes[0]["tag"]: (320, 220)}
        if count == 2:
            spacing = max(320, int(340 * scale))
            return {
                ordered_nodes[0]["tag"]: (240, 230),
                ordered_nodes[1]["tag"]: (240 + spacing, 230),
            }

        radius_x = max(300, int((260 + count * 40) * scale))
        radius_y = max(190, int((180 + count * 34) * scale))
        center_x = radius_x + 260
        center_y = radius_y + 230

        positions = {}
        for index, node in enumerate(ordered_nodes):
            angle = -math.pi / 2 + (2 * math.pi * index / count)
            positions[node["tag"]] = (
                round(center_x + radius_x * math.cos(angle)),
                round(center_y + radius_y * math.sin(angle)),
            )
        return positions

    def _needs_readable_board_layout(self, nodes):
        """Return whether saved coordinates are too compact for board display."""
        positions = []
        for node in nodes:
            try:
                positions.append((float(node.get("x")), float(node.get("y"))))
            except (TypeError, ValueError):
                return True

        count = len(positions)
        if count <= 1:
            return False

        min_distance = min(
            math.hypot(left[0] - right[0], left[1] - right[1])
            for left_index, left in enumerate(positions)
            for right in positions[left_index + 1 :]
        )
        if min_distance < 210:
            return True

        if count == 2:
            return min_distance < 300

        width = max(x for x, _y in positions) - min(x for x, _y in positions)
        height = max(y for _x, y in positions) - min(y for _x, y in positions)
        return width < 360 or height < 180

    def _apply_readable_board_layout(self):
        """Replace compact persisted coordinates with a wider presentation layout."""
        nodes = [
            node
            for node in self.graph.get("nodes", [])
            if isinstance(node, dict) and node.get("tag")
        ]
        if not self._needs_readable_board_layout(nodes):
            self.original_positions = dict(self.node_positions)
            return
        positions = self._readable_board_node_positions(nodes, self._valid_board_links())
        if not positions:
            return
        for node in nodes:
            tag = node.get("tag")
            if tag not in positions:
                continue
            x, y = positions[tag]
            self.node_positions[tag] = (x, y)
            node["x"], node["y"] = x, y
        self.original_positions = dict(self.node_positions)

    def draw_graph(self):
        """Apply the board layout once, then render through the shared editor."""
        if not getattr(self, "_board_layout_applied", False):
            self._apply_readable_board_layout()
            self._board_layout_applied = True
        super().draw_graph()

    def _display_link_label(self, text):
        """Return a compact label for dense board edges without mutating graph data."""
        raw = str(text or "").strip()
        if not raw:
            return ""
        parts = [part.strip() for part in raw.split(" / ") if part.strip()]
        if len(parts) > BOARD_LABEL_MAX_PARTS:
            raw = " / ".join(parts[: BOARD_LABEL_MAX_PARTS - 1])
            suffix = f" +{len(parts) - (BOARD_LABEL_MAX_PARTS - 1)}"
            if len(raw) + len(suffix) > BOARD_LABEL_MAX_CHARS:
                limit = BOARD_LABEL_MAX_CHARS - len(suffix) - 3
                raw = raw[:limit].rstrip() + "..."
            return raw + suffix
        if len(raw) > BOARD_LABEL_MAX_CHARS:
            return raw[: BOARD_LABEL_MAX_CHARS - 3].rstrip() + "..."
        return raw

    def _link_label_position(self, start_x, start_y, end_x, end_y, label_offset=0):
        """Place board labels away from the crowded midpoint band."""
        if not isinstance(label_offset, Mapping):
            return super()._link_label_position(
                start_x,
                start_y,
                end_x,
                end_y,
                label_offset,
            )

        dx = end_x - start_x
        dy = end_y - start_y
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return (start_x + end_x) / 2, (start_y + end_y) / 2

        along = max(-0.28, min(0.28, float(label_offset.get("along", 0))))
        perpendicular = float(label_offset.get("perpendicular", 0))
        base_x = start_x + dx * (0.5 + along)
        base_y = start_y + dy * (0.5 + along)
        return (
            base_x - (dy / length) * perpendicular,
            base_y + (dx / length) * perpendicular,
        )

    def _parallel_link_label_offsets(self, links):
        """Stagger every board label, including non-parallel links."""
        valid_links = [
            link
            for link in links
            if isinstance(link, dict)
            and link.get("node1_tag") in self.node_positions
            and link.get("node2_tag") in self.node_positions
            and link.get("node1_tag") != link.get("node2_tag")
        ]
        pair_groups = {}
        for link in valid_links:
            pair_groups.setdefault(self._link_pair_key(link), []).append(link)

        spacing = max(28, int(34 * self.canvas_scale))
        parallel_spacing = max(18, int(24 * self.canvas_scale))
        lanes = (-2, 2, -3, 3, -1, 1, -4, 4)
        along_lanes = (-0.16, 0.16, -0.08, 0.08, -0.22, 0.22)

        offsets = {}
        for pair_index, pair in enumerate(sorted(pair_groups, key=lambda key: tuple(str(part) for part in key))):
            group = pair_groups[pair]
            center_index = (len(group) - 1) / 2
            base_lane = lanes[pair_index % len(lanes)]
            lane_cycle = pair_index // len(lanes)
            if lane_cycle:
                base_lane += lane_cycle * (1 if base_lane > 0 else -1)
            for link_index, link in enumerate(group):
                parallel_delta = link_index - center_index
                offsets[self._link_canvas_key(link)] = {
                    "perpendicular": base_lane * spacing + parallel_delta * parallel_spacing,
                    "along": along_lanes[(pair_index + link_index) % len(along_lanes)],
                }
        return offsets

    def _link_label_item_tag(self, link, tag1, tag2):
        """Return a shared canvas tag for one link label's text and background."""
        return f"{LINK_LABEL_TAG}:{tag1}:{tag2}:{id(link)}"

    def _add_link_label_tags(self, link, text_id, tag1, tag2):
        """Tag the text so the label foreground/background can be treated as one unit."""
        item_tag = self._link_label_item_tag(link, tag1, tag2)
        self.canvas.addtag_withtag(LINK_LABEL_TAG, text_id)
        self.canvas.addtag_withtag(item_tag, text_id)
        return item_tag

    def _link_label_background_coords(self, text_id):
        """Read the real text bbox and convert it to background rectangle coords."""
        bbox = self.canvas.bbox(text_id)
        if not bbox:
            return None
        return padded_text_bbox(bbox)

    def _create_link_label_background(self, link, tag1, tag2, text_id):
        """Create and register a background rectangle directly from the text bbox."""
        item_tag = self._add_link_label_tags(link, text_id, tag1, tag2)
        coords = self._link_label_background_coords(text_id)
        if not coords:
            return None
        link_color, _line_width = self._get_link_style(link)
        background_id = self.canvas.create_rectangle(
            *coords,
            fill="#172536",
            outline=link_color,
            width=1,
            tags=("link", LINK_LABEL_BG_TAG, LINK_LABEL_TAG, item_tag),
        )
        key = self._link_canvas_key(link)
        self.link_canvas_ids.setdefault(key, {})["text_bg"] = background_id
        self._stack_link_label_background(link, tag1, tag2)
        return background_id

    def _stack_link_label_background(self, link, tag1, tag2):
        """Keep label backgrounds above edge graphics while staying behind text."""
        canvas_ids = self.link_canvas_ids.get(self._link_canvas_key(link), {})
        text_id = canvas_ids.get("text")
        background_id = canvas_ids.get("text_bg")
        if not text_id or not background_id:
            return
        for link_item_id in [canvas_ids.get("line"), *canvas_ids.get("arrows", [])]:
            if link_item_id:
                self.canvas.tag_lower(link_item_id, background_id)
        self.canvas.tag_lower(background_id, text_id)

    def _sync_link_label_background(self, link, tag1, tag2):
        """Keep an existing label background aligned to its text after movement."""
        canvas_ids = self.link_canvas_ids.get(self._link_canvas_key(link), {})
        text_id = canvas_ids.get("text")
        background_id = canvas_ids.get("text_bg")
        if not text_id or not background_id:
            return
        coords = self._link_label_background_coords(text_id)
        if not coords:
            return
        link_color, _line_width = self._get_link_style(link)
        self.canvas.coords(background_id, *coords)
        self.canvas.itemconfig(text_id, fill=link_color)
        self.canvas.itemconfig(background_id, outline=link_color)
        self._stack_link_label_background(link, tag1, tag2)

    def draw_one_link(self, link, label_offset=0):
        """Draw only links with two real endpoints and clarify their label."""
        tag1 = link.get("node1_tag")
        tag2 = link.get("node2_tag")
        if (
            not tag1
            or not tag2
            or tag1 == tag2
            or tag1 not in self.node_positions
            or tag2 not in self.node_positions
        ):
            return
        super().draw_one_link(link, label_offset=label_offset)
        text_id = self.link_canvas_ids.get(self._link_canvas_key(link), {}).get("text")
        if not text_id:
            return
        link_color, _line_width = self._get_link_style(link)
        self.canvas.itemconfig(
            text_id,
            text=self._display_link_label(link.get("text")),
            fill=link_color,
        )
        self._create_link_label_background(link, tag1, tag2, text_id)

    def update_links_positions_for_node(self, node_tag):
        """Move board link backgrounds along with their label text during drag."""
        super().update_links_positions_for_node(node_tag)
        for link in self.graph["links"]:
            tag1 = link.get("node1_tag")
            tag2 = link.get("node2_tag")
            if node_tag in (tag1, tag2):
                self._sync_link_label_background(link, tag1, tag2)


def create_scenario_character_graph(
    master,
    *,
    graph_data: Mapping[str, Any],
    wrappers: Mapping[str, object],
) -> ScenarioBoardCharacterGraph | None:
    """Create the graph when its data and required entity stores are available."""
    if not has_renderable_character_graph_links(graph_data):
        return None
    required = ("NPCs", "PCs", "Factions")
    if any(wrappers.get(key) is None for key in required):
        return None
    return ScenarioBoardCharacterGraph(
        master,
        npc_wrapper=wrappers["NPCs"],
        pc_wrapper=wrappers["PCs"],
        faction_wrapper=wrappers["Factions"],
        graph_data=dict(graph_data),
        background_style="scene_flow",
        node_style="modern",
    )
