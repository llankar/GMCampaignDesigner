import customtkinter as ctk


class GuidedScenePlanner(ctk.CTkFrame):
    def __init__(self, master, *, entity_fields=None, on_add_entity=None):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._cards = []
        self._entity_fields = entity_fields or []
        self._on_add_entity = on_add_entity

        info = ctk.CTkLabel(
            self,
            text=(
                "Guided mode starts with an opening and ending scene. "
                "Add intermediary scenes to shape your own pacing."
            ),
            text_color="#9db4d1",
            justify="left",
            anchor="w",
        )
        info.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 6))

        add_row = ctk.CTkFrame(self, fg_color="transparent")
        add_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        ctk.CTkButton(add_row, text="Add middle scene", command=self._insert_middle_scene).pack(side="left")

        self._container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._container.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._container.grid_columnconfigure(0, weight=1)

    def _default_scene_payload(self, index):
        if index == 0:
            return {"Title": "Opening Scene", "SceneType": "Setup", "Summary": ""}
        return {"Title": f"Scene {index + 1}", "SceneType": "Choice", "Summary": ""}

    def _insert_middle_scene(self):
        insert_at = max(1, len(self._cards) - 1)
        self._cards.insert(insert_at, self._default_scene_payload(insert_at))
        self._refresh_cards()

    def _remove_scene(self, index):
        if index <= 0 or index >= len(self._cards) - 1:
            return
        self._cards.pop(index)
        self._refresh_cards()

    def _add_entity_to_card(self, index, field):
        if not callable(self._on_add_entity):
            return
        selected = self._on_add_entity(index, field)
        if not selected:
            return
        card = self._cards[index]
        values = list(card.get(field) or [])
        if selected not in values:
            values.append(selected)
            card[field] = sorted(values, key=lambda value: value.casefold())
            self._refresh_cards()

    def _refresh_cards(self):
        for widget in self._container.winfo_children():
            widget.destroy()

        for idx, card in enumerate(self._cards):
            panel = ctk.CTkFrame(self._container, fg_color="#0f172a", corner_radius=12)
            panel.grid(row=idx, column=0, sticky="ew", pady=(0, 10))
            panel.grid_columnconfigure(0, weight=1)

            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=f"Scene {idx + 1}", font=ctk.CTkFont(size=14, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
            if 0 < idx < len(self._cards) - 1:
                ctk.CTkButton(row, text="Remove", width=90, command=lambda i=idx: self._remove_scene(i)).grid(row=0, column=1, sticky="e")

            title_var = ctk.StringVar(value=card.get("Title") or f"Scene {idx + 1}")
            title_var.trace_add("write", lambda *_args, i=idx, var=title_var: self._cards[i].__setitem__("Title", var.get()))
            ctk.CTkEntry(panel, textvariable=title_var).grid(row=1, column=0, sticky="ew", padx=12)
            card["_title_var"] = title_var

            summary = ctk.CTkTextbox(panel, height=92, wrap="word")
            summary.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 10))
            summary.insert("1.0", card.get("Summary") or "")
            card["_summary_widget"] = summary

            card["SceneType"] = card.get("SceneType") or ("Setup" if idx == 0 else ("Outcome" if idx == len(self._cards) - 1 else "Choice"))

            if self._entity_fields:
                entities_frame = ctk.CTkFrame(panel, fg_color="transparent")
                entities_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
                entities_frame.grid_columnconfigure(0, weight=1)
                for row_idx, (field, label) in enumerate(self._entity_fields):
                    values = list(card.get(field) or [])
                    pill_text = ", ".join(values) if values else "None"
                    ctk.CTkLabel(entities_frame, text=f"{label}s: {pill_text}", anchor="w", wraplength=660).grid(
                        row=row_idx, column=0, sticky="w", pady=2
                    )
                    ctk.CTkButton(
                        entities_frame,
                        text=f"+ {label}",
                        width=90,
                        command=lambda i=idx, f=field: self._add_entity_to_card(i, f),
                    ).grid(row=row_idx, column=1, sticky="e", padx=(8, 0), pady=2)

    def load_cards(self, cards):
        self._cards = []
        for card in cards or []:
            payload = dict(card)
            for field, _label in self._entity_fields:
                payload[field] = list(payload.get(field) or [])
            self._cards.append(payload)
        if len(self._cards) < 2:
            self._cards = [self._default_scene_payload(0), {"Title": "Final Scene", "SceneType": "Outcome", "Summary": ""}]
        self._refresh_cards()

    def export_cards(self):
        result = []
        for idx, card in enumerate(self._cards):
            if card.get("_summary_widget") is not None:
                card["Summary"] = card["_summary_widget"].get("1.0", "end").strip()
            exported = {
                "stage": card.get("stage") or f"Scene {idx + 1}",
                "Title": str(card.get("Title") or f"Scene {idx + 1}").strip(),
                "Summary": str(card.get("Summary") or "").strip(),
                "SceneType": card.get("SceneType") or ("Setup" if idx == 0 else ("Outcome" if idx == len(self._cards) - 1 else "Choice")),
                "_canvas": dict(card.get("_canvas") or {}),
                "_extra_fields": dict(card.get("_extra_fields") or {}),
            }
            for field, _label in self._entity_fields:
                exported[field] = list(card.get(field) or [])
            result.append(exported)
        return result
