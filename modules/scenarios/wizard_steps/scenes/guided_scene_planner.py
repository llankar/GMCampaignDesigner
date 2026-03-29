import customtkinter as ctk

from modules.scenarios.wizard_steps.scenes.scene_mode_adapters import GUIDED_BOUNDARY_FLOW


class GuidedScenePlanner(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._cards = []

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

    def _new_card_data(self, *, title="", summary="", scene_type="Choice", stage="", canvas=None, extra_fields=None):
        return {
            "stage": stage or "Scene",
            "Title": title,
            "Summary": summary,
            "SceneType": scene_type,
            "_canvas": dict(canvas or {}),
            "_extra_fields": dict(extra_fields or {}),
        }

    def _card_heading(self, index):
        total = len(self._cards)
        if index == 0:
            return f"1. {GUIDED_BOUNDARY_FLOW[0][0]} (required)"
        if index == total - 1:
            return f"{index + 1}. {GUIDED_BOUNDARY_FLOW[-1][0]} (required)"
        return f"{index + 1}. Middle scene"

    def _normalise_card_data(self, card, index, total):
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
        )

    def _render_cards(self):
        for child in self._container.winfo_children():
            child.destroy()

        total = len(self._cards)
        for idx, payload in enumerate(self._cards):
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

            payload["title_var"] = title_var
            payload["summary_widget"] = summary

    def _snapshot_ui(self):
        snapshot = []
        total = len(self._cards)
        for idx, payload in enumerate(self._cards):
            title_var = payload.get("title_var")
            summary_widget = payload.get("summary_widget")
            title = title_var.get().strip() if title_var is not None else str(payload.get("Title") or "").strip()
            summary = summary_widget.get("1.0", "end").strip() if summary_widget is not None else str(payload.get("Summary") or "")
            base = self._normalise_card_data(payload, idx, total)
            base["Title"] = title or base["stage"]
            base["Summary"] = summary
            snapshot.append(base)
        self._cards = snapshot

    def _insert_scene_after(self, index):
        self._snapshot_ui()
        insert_at = max(1, min(index + 1, len(self._cards) - 1))
        self._cards.insert(insert_at, self._new_card_data(title=f"Scene {insert_at + 1}", scene_type="Choice", stage=f"Scene {insert_at + 1}"))
        self._render_cards()

    def _move_scene(self, index, delta):
        self._snapshot_ui()
        target = index + delta
        if not (0 < index < len(self._cards) - 1):
            return
        if not (0 < target < len(self._cards) - 1):
            return
        self._cards[index], self._cards[target] = self._cards[target], self._cards[index]
        self._render_cards()

    def _remove_scene(self, index):
        self._snapshot_ui()
        if not (0 < index < len(self._cards) - 1):
            return
        del self._cards[index]
        self._render_cards()

    def load_cards(self, cards):
        payload = [card for card in (cards or []) if isinstance(card, dict)]
        if not payload:
            payload = [{}, {}]
        elif len(payload) == 1:
            payload = [payload[0], {}]
        total = len(payload)
        self._cards = [self._normalise_card_data(card, idx, total) for idx, card in enumerate(payload)]
        self._render_cards()

    def export_cards(self):
        self._snapshot_ui()
        return [self._normalise_card_data(card, idx, len(self._cards)) for idx, card in enumerate(self._cards)]
