import customtkinter as ctk

from modules.scenarios.wizard_steps.scenes.scene_mode_adapters import GUIDED_FLOW


class GuidedScenePlanner(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self._cards = []

        info = ctk.CTkLabel(
            self,
            text="Guided mode follows a linear arc: Hook → Rising action → Climax → Fallout.",
            text_color="#9db4d1",
            justify="left",
            anchor="w",
        )
        info.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 6))

        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        container.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        for idx, (label, _default_type) in enumerate(GUIDED_FLOW):
            card = ctk.CTkFrame(container, fg_color="#0f172a", corner_radius=12)
            card.grid(row=idx, column=0, sticky="ew", pady=(0, 10))
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                card,
                text=f"{idx + 1}. {label}",
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

            title_var = ctk.StringVar(value=label)
            title = ctk.CTkEntry(card, textvariable=title_var)
            title.grid(row=1, column=0, sticky="ew", padx=12)

            summary = ctk.CTkTextbox(card, height=96, wrap="word")
            summary.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 12))

            self._cards.append({
                "stage": label,
                "title_var": title_var,
                "summary": summary,
                "scene_type": _default_type,
                "_canvas": {},
                "_extra_fields": {},
            })

    def load_cards(self, cards):
        cards = cards or []
        for idx, card_ui in enumerate(self._cards):
            payload = cards[idx] if idx < len(cards) and isinstance(cards[idx], dict) else {}
            card_ui["title_var"].set(payload.get("Title") or card_ui["stage"])
            card_ui["summary"].delete("1.0", "end")
            card_ui["summary"].insert("1.0", payload.get("Summary") or "")
            card_ui["scene_type"] = payload.get("SceneType") or card_ui["scene_type"]
            card_ui["_canvas"] = dict(payload.get("_canvas") or {})
            card_ui["_extra_fields"] = dict(payload.get("_extra_fields") or {})

    def export_cards(self):
        data = []
        for card_ui in self._cards:
            data.append(
                {
                    "stage": card_ui["stage"],
                    "Title": card_ui["title_var"].get().strip() or card_ui["stage"],
                    "Summary": card_ui["summary"].get("1.0", "end").strip(),
                    "SceneType": card_ui["scene_type"],
                    "_canvas": dict(card_ui.get("_canvas") or {}),
                    "_extra_fields": dict(card_ui.get("_extra_fields") or {}),
                }
            )
        return data
