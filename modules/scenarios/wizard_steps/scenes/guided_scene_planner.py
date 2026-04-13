"""Utilities for scenes guided scene planner."""

import customtkinter as ctk

from modules.scenarios.wizard_steps.scenes.scene_mode_adapters import GUIDED_BOUNDARY_FLOW
from modules.scenarios.wizard_steps.scenes.scene_entity_fields import (
    SCENE_ENTITY_FIELDS,
    normalise_entity_list,
)
from modules.scenarios.wizard_steps.scenes.scene_mode_adapters import SCENE_STRUCTURED_FIELDS
from modules.scenarios.wizard_steps.scenes.scene_structured_editor_fields import (
    SCENE_STRUCTURED_FIELD_LABELS,
    convert_structured_fields_from_text,
    parse_multiline_items,
)


class GuidedScenePlanner(ctk.CTkFrame):
    def __init__(self, master, *, entity_selector_callbacks=None):
        """Initialize the GuidedScenePlanner instance."""
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._cards = []
        self._entity_selector_callbacks = dict(entity_selector_callbacks or {})

        info = ctk.CTkLabel(
            self,
            text="Guided mode follows a linear arc with fixed first/last scenes and flexible middle scenes.",
            text_color="#9db4d1",
            justify="left",
            anchor="w",
        )
        info.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 6))

        self._container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._container.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._container.grid_columnconfigure(0, weight=1)

    def _new_card_data(
        self,
        *,
        title="",
        summary="",
        scene_type="Choice",
        stage="",
        canvas=None,
        extra_fields=None,
        entities=None,
        structured=None,
        structured_prefilled=False,
    ):
        """Internal helper for new card data."""
        card = {
            "stage": stage or "Scene",
            "Title": title,
            "Summary": summary,
            "SceneType": scene_type,
            "_canvas": dict(canvas or {}),
            "_extra_fields": dict(extra_fields or {}),
        }
        incoming_entities = entities or {}
        for field_name in SCENE_ENTITY_FIELDS:
            card[field_name] = normalise_entity_list(
                incoming_entities.get(field_name) if isinstance(incoming_entities, dict) else None
            )
        incoming_structured = structured or {}
        for field_name in SCENE_STRUCTURED_FIELDS:
            card[field_name] = parse_multiline_items(
                incoming_structured.get(field_name) if isinstance(incoming_structured, dict) else None
            )
        card["_structured_prefilled"] = bool(structured_prefilled)
        return card

    def _card_heading(self, index):
        """Internal helper for card heading."""
        total = len(self._cards)
        if index == 0:
            return f"1. {GUIDED_BOUNDARY_FLOW[0][0]} (required)"
        if index == total - 1:
            return f"{index + 1}. {GUIDED_BOUNDARY_FLOW[-1][0]} (required)"
        return f"{index + 1}. Middle scene"

    def _normalise_card_data(self, card, index, total):
        """Internal helper for normalise card data."""
        payload = card if isinstance(card, dict) else {}
        if index == 0:
            stage, scene_type = GUIDED_BOUNDARY_FLOW[0]
        elif index == total - 1:
            stage, scene_type = GUIDED_BOUNDARY_FLOW[-1]
        else:
            stage = str(payload.get("stage") or f"Scene {index + 1}").strip() or f"Scene {index + 1}"
            scene_type = str(payload.get("SceneType") or "Choice").strip() or "Choice"
        return self._new_card_data(
            title=str(payload.get("Title") or stage).strip() or stage,
            summary=str(payload.get("Summary") or ""),
            scene_type=scene_type,
            stage=stage,
            canvas=payload.get("_canvas"),
            extra_fields=payload.get("_extra_fields"),
            entities={field_name: payload.get(field_name) for field_name in SCENE_ENTITY_FIELDS},
            structured={field_name: payload.get(field_name) for field_name in SCENE_STRUCTURED_FIELDS},
            structured_prefilled=payload.get("_structured_prefilled"),
        )

    def _render_cards(self):
        """Render cards."""
        for child in self._container.winfo_children():
            child.destroy()

        total = len(self._cards)
        for idx, payload in enumerate(self._cards):
            # Process each (idx, payload) from enumerate(_cards).
            payload = self._normalise_card_data(payload, idx, total)
            self._cards[idx] = payload

            is_middle = 0 < idx < total - 1
            card = ctk.CTkFrame(self._container, fg_color="#0f172a", corner_radius=12)
            card.grid(row=idx, column=0, sticky="ew", pady=(0, 10))
            card.grid_columnconfigure(0, weight=1)

            header = ctk.CTkFrame(card, fg_color="transparent")
            header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
            header.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                header,
                text=self._card_heading(idx),
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            controls = ctk.CTkFrame(header, fg_color="transparent")
            controls.grid(row=0, column=1, sticky="e")
            ctk.CTkButton(
                controls,
                text="+ Add scene after",
                width=124,
                command=lambda insert_after=idx: self._insert_scene_after(insert_after),
            ).pack(side="left")

            if is_middle:
                ctk.CTkButton(controls, text="↑", width=34, command=lambda i=idx: self._move_scene(i, -1)).pack(side="left", padx=(6, 0))
                ctk.CTkButton(controls, text="↓", width=34, command=lambda i=idx: self._move_scene(i, 1)).pack(side="left", padx=(6, 0))
                ctk.CTkButton(controls, text="Remove", width=88, fg_color="#991b1b", hover_color="#7f1d1d", command=lambda i=idx: self._remove_scene(i)).pack(side="left", padx=(6, 0))

            title_var = ctk.StringVar(value=payload["Title"])
            title = ctk.CTkEntry(card, textvariable=title_var)
            title.grid(row=1, column=0, sticky="ew", padx=12)

            summary = ctk.CTkTextbox(card, height=96, wrap="word")
            summary.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 12))
            summary.insert("1.0", payload["Summary"])

            structured_section = ctk.CTkFrame(card, fg_color="#111827", corner_radius=10)
            structured_section.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
            structured_section.grid_columnconfigure((0, 1), weight=1)
            ctk.CTkLabel(
                structured_section,
                text="Scene Structure",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#b8c7e2",
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
            convert_state = "disabled" if payload.get("_structured_prefilled") else "normal"
            ctk.CTkButton(
                structured_section,
                text="Convert from existing text",
                width=180,
                state=convert_state,
                command=lambda i=idx: self._prefill_structured_fields(i),
            ).grid(row=0, column=1, sticky="e", padx=10, pady=(8, 4))

            structured_widgets = {}
            for section_idx, field_name in enumerate(SCENE_STRUCTURED_FIELDS):
                row = 1 + (section_idx // 2)
                col = section_idx % 2
                field_frame = ctk.CTkFrame(structured_section, fg_color="transparent")
                field_frame.grid(row=row, column=col, sticky="nsew", padx=10, pady=(0, 8))
                field_frame.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(
                    field_frame,
                    text=SCENE_STRUCTURED_FIELD_LABELS.get(field_name, field_name),
                    anchor="w",
                    text_color="#8fa6cc",
                ).grid(row=0, column=0, sticky="w", pady=(0, 4))
                widget = ctk.CTkTextbox(field_frame, height=74, wrap="word")
                widget.grid(row=1, column=0, sticky="ew")
                widget.insert("1.0", "\n".join(payload.get(field_name) or []))
                structured_widgets[field_name] = widget

            entities_section = ctk.CTkFrame(card, fg_color="#111827", corner_radius=10)
            entities_section.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))
            entities_section.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                entities_section,
                text="Scene Entities",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#b8c7e2",
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

            entity_vars = {}
            for row_offset, field_name in enumerate(SCENE_ENTITY_FIELDS, start=1):
                # Process each (row_offset, field_name) from enumerate(SCENE_ENTITY_FIELDS, start=1).
                row = ctk.CTkFrame(entities_section, fg_color="transparent")
                row.grid(row=row_offset, column=0, sticky="ew", padx=10, pady=(0, 6))
                row.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(row, text=f"{field_name}", width=82, anchor="w", text_color="#8fa6cc").grid(row=0, column=0, sticky="w")
                entity_var = ctk.StringVar(value=", ".join(normalise_entity_list(payload.get(field_name))))
                ctk.CTkEntry(row, textvariable=entity_var).grid(row=0, column=1, sticky="ew", padx=(8, 6))
                selector = self._entity_selector_callbacks.get(field_name)
                select_btn_state = "normal" if callable(selector) else "disabled"
                ctk.CTkButton(
                    row,
                    text="Select",
                    width=72,
                    state=select_btn_state,
                    command=lambda f=field_name, v=entity_var: self._open_entity_selector(f, v),
                ).grid(row=0, column=2, sticky="e")
                entity_vars[field_name] = entity_var

            payload["title_var"] = title_var
            payload["summary_widget"] = summary
            payload["structured_widgets"] = structured_widgets
            payload["entity_vars"] = entity_vars

    def _prefill_structured_fields(self, index):
        """Run legacy parser once to prefill structured scene fields."""
        if index < 0 or index >= len(self._cards):
            return
        payload = self._cards[index]
        if payload.get("_structured_prefilled"):
            return
        summary_widget = payload.get("summary_widget")
        summary = summary_widget.get("1.0", "end").strip() if summary_widget is not None else str(payload.get("Summary") or "")
        converted = convert_structured_fields_from_text(payload, summary)
        for field_name, values in converted.items():
            payload[field_name] = values
            widget = (payload.get("structured_widgets") or {}).get(field_name)
            if widget is not None:
                widget.delete("1.0", "end")
                widget.insert("1.0", "\n".join(values))
        payload["_structured_prefilled"] = True
        self._render_cards()

    def _open_entity_selector(self, field_name, entity_var):
        """Open entity selector."""
        selector = self._entity_selector_callbacks.get(field_name)
        if not callable(selector):
            return
        current = normalise_entity_list(entity_var.get())
        selected = selector(current)
        if selected is None:
            return
        entity_var.set(", ".join(normalise_entity_list(selected)))

    def _snapshot_ui(self):
        """Internal helper for snapshot UI."""
        snapshot = []
        total = len(self._cards)
        for idx, payload in enumerate(self._cards):
            # Process each (idx, payload) from enumerate(_cards).
            title_var = payload.get("title_var")
            summary_widget = payload.get("summary_widget")
            title = title_var.get().strip() if title_var is not None else str(payload.get("Title") or "").strip()
            summary = summary_widget.get("1.0", "end").strip() if summary_widget is not None else str(payload.get("Summary") or "")
            base = self._normalise_card_data(payload, idx, total)
            base["Title"] = title or base["stage"]
            base["Summary"] = summary
            structured_widgets = payload.get("structured_widgets") or {}
            for field_name in SCENE_STRUCTURED_FIELDS:
                field_widget = structured_widgets.get(field_name)
                if field_widget is not None:
                    base[field_name] = parse_multiline_items(field_widget.get("1.0", "end"))
            entity_vars = payload.get("entity_vars") or {}
            for field_name in SCENE_ENTITY_FIELDS:
                # Process each field_name from SCENE_ENTITY_FIELDS.
                field_var = entity_vars.get(field_name)
                if field_var is not None:
                    base[field_name] = normalise_entity_list(field_var.get())
            base["_structured_prefilled"] = bool(payload.get("_structured_prefilled"))
            snapshot.append(base)
        self._cards = snapshot

    def _insert_scene_after(self, index):
        """Internal helper for insert scene after."""
        self._snapshot_ui()
        insert_at = max(1, min(index + 1, len(self._cards) - 1))
        self._cards.insert(insert_at, self._new_card_data(title=f"Scene {insert_at + 1}", scene_type="Choice", stage=f"Scene {insert_at + 1}"))
        self._render_cards()

    def _move_scene(self, index, delta):
        """Move scene."""
        self._snapshot_ui()
        target = index + delta
        if not (0 < index < len(self._cards) - 1):
            return
        if not (0 < target < len(self._cards) - 1):
            return
        self._cards[index], self._cards[target] = self._cards[target], self._cards[index]
        self._render_cards()

    def _remove_scene(self, index):
        """Remove scene."""
        self._snapshot_ui()
        if not (0 < index < len(self._cards) - 1):
            return
        del self._cards[index]
        self._render_cards()

    def load_cards(self, cards):
        """Load cards."""
        payload = [card for card in (cards or []) if isinstance(card, dict)]
        if not payload:
            payload = [{}, {}]
        elif len(payload) == 1:
            payload = [payload[0], {}]
        total = len(payload)
        self._cards = [self._normalise_card_data(card, idx, total) for idx, card in enumerate(payload)]
        self._render_cards()

    def export_cards(self):
        """Export cards."""
        self._snapshot_ui()
        return [self._normalise_card_data(card, idx, len(self._cards)) for idx, card in enumerate(self._cards)]
