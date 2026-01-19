import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from modules.exports.campaign_dossier.exporter import DossierExportOptions, export_campaign_dossier
from modules.exports.campaign_dossier.layouts import DEFAULT_LAYOUT_KEY, get_layout_presets
from modules.helpers.theme_manager import get_theme


class CampaignDossierExportDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Export Campaign Dossier")
        self.geometry("460x460")
        self.resizable(False, False)

        self.layout_var = tk.StringVar(value=DEFAULT_LAYOUT_KEY)
        self.pagination_var = tk.StringVar(value="section")
        self.output_mode_var = tk.StringVar(value="single")
        self.format_var = tk.StringVar(value="docx")
        self.include_toc_var = tk.BooleanVar(value=True)
        self.include_branding_var = tk.BooleanVar(value=False)

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=16, pady=16)

        header = ctk.CTkLabel(container, text="Export Entire Campaign (Dossier Binder)", font=("Arial", 16, "bold"))
        header.pack(anchor="w", pady=(0, 12))

        theme_row = ctk.CTkLabel(container, text=f"Current theme: {get_theme()}")
        theme_row.pack(anchor="w", pady=(0, 12))

        layout_frame = ctk.CTkFrame(container, fg_color="transparent")
        layout_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(layout_frame, text="Layout preset:").pack(side="left")
        presets = get_layout_presets()
        preset_labels = {preset.label: preset.key for preset in presets.values()}
        preset_label_list = list(preset_labels.keys())
        default_label = next(
            (label for label, key in preset_labels.items() if key == DEFAULT_LAYOUT_KEY),
            preset_label_list[0],
        )
        self.layout_menu = ctk.CTkOptionMenu(
            layout_frame,
            values=preset_label_list,
            command=lambda label: self.layout_var.set(preset_labels[label]),
        )
        self.layout_menu.set(default_label)
        self.layout_menu.pack(side="right", fill="x", expand=True, padx=(8, 0))

        pagination_frame = ctk.CTkFrame(container, fg_color="transparent")
        pagination_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(pagination_frame, text="Pagination:").pack(anchor="w")
        ctk.CTkRadioButton(
            pagination_frame,
            text="One entity per page",
            variable=self.pagination_var,
            value="entity",
        ).pack(anchor="w")
        ctk.CTkRadioButton(
            pagination_frame,
            text="Section per page (multiple entities)",
            variable=self.pagination_var,
            value="section",
        ).pack(anchor="w")
        ctk.CTkRadioButton(
            pagination_frame,
            text="Continuous (no forced breaks)",
            variable=self.pagination_var,
            value="continuous",
        ).pack(anchor="w")

        output_mode_frame = ctk.CTkFrame(container, fg_color="transparent")
        output_mode_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(output_mode_frame, text="Output mode:").pack(anchor="w")
        ctk.CTkRadioButton(
            output_mode_frame,
            text="Single dossier",
            variable=self.output_mode_var,
            value="single",
        ).pack(anchor="w")
        ctk.CTkRadioButton(
            output_mode_frame,
            text="Per-entity folder",
            variable=self.output_mode_var,
            value="folder",
        ).pack(anchor="w")

        format_frame = ctk.CTkFrame(container, fg_color="transparent")
        format_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(format_frame, text="Output format:").pack(side="left")
        self.format_menu = ctk.CTkOptionMenu(format_frame, values=["docx", "pdf"], variable=self.format_var)
        self.format_menu.pack(side="right", fill="x", expand=True, padx=(8, 0))

        toc_frame = ctk.CTkFrame(container, fg_color="transparent")
        toc_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkCheckBox(
            toc_frame,
            text="Include table of contents",
            variable=self.include_toc_var,
        ).pack(anchor="w")
        ctk.CTkCheckBox(
            toc_frame,
            text="Include binder branding (header/footer)",
            variable=self.include_branding_var,
        ).pack(anchor="w", pady=(4, 0))

        button_row = ctk.CTkFrame(container, fg_color="transparent")
        button_row.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(button_row, text="Cancel", command=self.destroy).pack(side="right")
        ctk.CTkButton(button_row, text="Export", command=self._export).pack(side="right", padx=(0, 8))

        self.transient(master)
        self.grab_set()

    def _export(self):
        output_mode = self.output_mode_var.get()
        output_format = self.format_var.get()

        if output_mode == "folder":
            target = filedialog.askdirectory(title="Choose export folder")
            if not target:
                return
        else:
            ext = ".pdf" if output_format == "pdf" else ".docx"
            target = filedialog.asksaveasfilename(
                title="Save campaign dossier",
                defaultextension=ext,
                filetypes=[("Document", f"*{ext}"), ("All Files", "*.*")],
            )
            if not target:
                return

        options = DossierExportOptions(
            layout_key=self.layout_var.get(),
            pagination_mode=self.pagination_var.get(),
            include_toc=self.include_toc_var.get(),
            include_branding=self.include_branding_var.get(),
            output_mode=output_mode,
            output_format=output_format,
            output_target=target,
        )

        output_paths = export_campaign_dossier(options)
        if not output_paths:
            messagebox.showwarning("No Data", "No entity data found to export.")
            return

        if output_mode == "folder":
            messagebox.showinfo(
                "Export Complete",
                f"Exported {len(output_paths)} files to:\n{target}",
            )
        else:
            messagebox.showinfo(
                "Export Complete",
                f"Campaign dossier exported to:\n{output_paths[0]}",
            )
        self.destroy()


def open_campaign_dossier_exporter(master):
    CampaignDossierExportDialog(master)
