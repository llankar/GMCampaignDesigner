"""Campaign selector dialog used before global validation runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class CampaignSelectorOption:
    """One campaign candidate available for validation."""

    campaign_id: str
    label: str
    item: dict[str, Any]

    @property
    def display_text(self) -> str:
        """Return a stable user-facing label for dropdowns and lists."""

        if self.label == self.campaign_id:
            return self.label
        return f"{self.label} ({self.campaign_id})"


class CampaignSelectorDialog:
    """Blocking CustomTkinter dialog that requires a campaign before Run."""

    def __init__(self, master: Any, campaigns: Sequence[CampaignSelectorOption]) -> None:
        self.master = master
        self.campaigns = tuple(campaigns)
        self.selected_campaign: CampaignSelectorOption | None = None
        self.window: Any | None = None
        self._selected_text: Any | None = None
        self._run_button: Any | None = None
        self._display_to_option = {campaign.display_text: campaign for campaign in self.campaigns}

    def show(self) -> CampaignSelectorOption | None:
        """Open the modal selector and return the chosen campaign, or ``None``."""

        import customtkinter as ctk

        window = ctk.CTkToplevel(self.master)
        self.window = window
        window.title("Choisir une campagne")
        window.transient(self.master)
        window.grab_set()
        window.geometry("480x260")
        window.grid_columnconfigure(0, weight=1)
        window.protocol("WM_DELETE_WINDOW", self.cancel)

        ctk.CTkLabel(
            window,
            text="Choisir une campagne",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        if self.campaigns:
            ctk.CTkLabel(
                window,
                text=(
                    "Sélectionnez la campagne à vérifier. La validation ne "
                    "démarrera qu’après ce choix."
                ),
                wraplength=420,
                justify="left",
            ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 14))
            self._selected_text = ctk.StringVar(value="")
            dropdown = ctk.CTkOptionMenu(
                window,
                values=[campaign.display_text for campaign in self.campaigns],
                variable=self._selected_text,
                command=self._on_selection_changed,
            )
            dropdown.grid(row=2, column=0, sticky="ew", padx=20, pady=4)
        else:
            ctk.CTkLabel(
                window,
                text=(
                    "Aucune campagne n’existe encore. Créez ou importez une campagne "
                    "avant de lancer la validation."
                ),
                wraplength=420,
                justify="left",
            ).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 14))

        actions = ctk.CTkFrame(window)
        actions.grid(row=3, column=0, sticky="e", padx=20, pady=(22, 20))
        self._run_button = ctk.CTkButton(actions, text="Run", command=self.run, state="disabled")
        self._run_button.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(actions, text="Annuler", command=self.cancel).grid(row=0, column=1)

        window.wait_window()
        return self.selected_campaign

    def _on_selection_changed(self, selected_text: str) -> None:
        if self._run_button is not None:
            state = "normal" if selected_text in self._display_to_option else "disabled"
            self._run_button.configure(state=state)

    def run(self) -> None:
        """Accept the current selection and close the dialog."""

        selected_text = self._selected_text.get() if self._selected_text is not None else ""
        selected_campaign = self._display_to_option.get(selected_text)
        if selected_campaign is None:
            return
        self.selected_campaign = selected_campaign
        self._close()

    def cancel(self) -> None:
        """Abort validation cleanly without a selected campaign."""

        self.selected_campaign = None
        self._close()

    def _close(self) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None


def open_campaign_selector_dialog(
    master: Any,
    campaigns: Sequence[CampaignSelectorOption],
) -> CampaignSelectorOption | None:
    """Open the dedicated campaign selector dialog."""

    return CampaignSelectorDialog(master, campaigns).show()
