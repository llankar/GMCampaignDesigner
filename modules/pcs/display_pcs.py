import customtkinter as ctk
from modules.helpers import theme_manager
from modules.helpers.text_helpers import format_multiline_text
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


def display_pcs_in_banner(banner_frame, pcs_items):
    banner_frame._pcs_items_cache = pcs_items
    if not getattr(banner_frame, "_pcs_theme_listener", None):
        def _refresh(_theme):
            if not banner_frame.winfo_exists():
                return
            cached = getattr(banner_frame, "_pcs_items_cache", None)
            if cached is None:
                return
            banner_frame.after(0, lambda: display_pcs_in_banner(banner_frame, cached))

        banner_frame._pcs_theme_listener = _refresh
        banner_frame._pcs_theme_unsub = theme_manager.register_theme_change_listener(_refresh)

        def _cleanup(_event):
            unsub = getattr(banner_frame, "_pcs_theme_unsub", None)
            if unsub:
                unsub()
            banner_frame._pcs_theme_unsub = None
            banner_frame._pcs_theme_listener = None

        banner_frame.bind("<Destroy>", _cleanup, add="+")

    for widget in banner_frame.winfo_children():
        widget.destroy()

    if not pcs_items:
        empty = ctk.CTkLabel(
            banner_frame,
            text="No PCs to display.",
            text_color="#9aa3b2",
            font=("Segoe UI", 13),
        )
        empty.pack(padx=16, pady=16)
        return

    banner_frame.update_idletasks()
    available_width = banner_frame.winfo_width() or banner_frame.winfo_reqwidth()
    if available_width <= 1:
        available_width = 1200

    card_width = 280
    banner_visible_height = 230

    tokens = theme_manager.get_tokens()
    banner_bg = "#2B2B2B"

    colors = {
        "canvas": banner_bg,
        "card_bg": tokens.get("panel_alt_bg", "#252a36"),
        "card_border": tokens.get("button_border", "#323a49"),
        "header_bg": tokens.get("accent_button_fg", "#2b3140"),
        "text": "#f5f6fa",
        "muted": "#9aa3b2",
    }

    fonts = {
        "title": ("Segoe UI", 14, "bold"),
        "label": ("Segoe UI", 11, "bold"),
        "body": ("Segoe UI", 12),
    }

    canvas = ctk.CTkCanvas(
        banner_frame,
        bg=colors["canvas"],
        highlightthickness=0,
        width=available_width,
        height=banner_visible_height,
    )

    h_scrollbar = ctk.CTkScrollbar(banner_frame, orientation="horizontal", command=canvas.xview)
    v_scrollbar = ctk.CTkScrollbar(banner_frame, orientation="vertical", command=canvas.yview)

    scrollable_frame = ctk.CTkFrame(canvas, fg_color="transparent")
    scrollable_frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

    canvas.grid(row=0, column=0, sticky="nsew")
    v_scrollbar.grid(row=0, column=1, sticky="ns")
    h_scrollbar.grid(row=1, column=0, sticky="ew")

    banner_frame.grid_rowconfigure(0, weight=1)
    banner_frame.grid_columnconfigure(0, weight=1)

    def _on_mousewheel(event):
        delta = event.delta if hasattr(event, "delta") else (120 if event.num == 4 else -120)
        if getattr(event, "state", 0) & 0x0001:
            canvas.xview_scroll(int(-1 * (delta / 120)), "units")
        else:
            canvas.yview_scroll(int(-1 * (delta / 120)), "units")
        return "break"

    def _bind_banner_scroll(_event):
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

    def _unbind_banner_scroll(_event):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", _bind_banner_scroll)
    canvas.bind("<Leave>", _unbind_banner_scroll)

    col_idx = 0

    def add_header(parent, name):
        header = ctk.CTkFrame(
            parent,
            fg_color=colors["header_bg"],
            corner_radius=8,
        )
        header.pack(fill="x", padx=10, pady=(10, 6))
        label = ctk.CTkLabel(
            header,
            text=name,
            font=fonts["title"],
            text_color=colors["text"],
            anchor="w",
        )
        label.pack(fill="x", padx=10, pady=6)

    def add_section(parent, title, content):
        if not content:
            return
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=(0, 8))
        label_title = ctk.CTkLabel(
            frame,
            text=title.upper(),
            font=fonts["label"],
            text_color=colors["muted"],
            anchor="w",
        )
        label_title.pack(fill="x")
        label_content = ctk.CTkLabel(
            frame,
            text=content,
            font=fonts["body"],
            text_color=colors["text"],
            anchor="w",
            justify="left",
            wraplength=card_width - 24,
        )
        label_content.pack(fill="x", pady=(2, 0))

    for pc_name, pc_data in pcs_items.items():
        pc_frame = ctk.CTkFrame(
            scrollable_frame,
            fg_color=colors["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=colors["card_border"],
        )
        pc_frame.grid(row=0, column=col_idx, sticky="nsew", padx=10, pady=10)

        display_name = pc_data.get("Name") or pc_name
        add_header(pc_frame, display_name)

        add_section(pc_frame, "Traits", format_multiline_text(pc_data.get("Traits", "")))
        add_section(pc_frame, "Background", format_multiline_text(pc_data.get("Background", "")))
        add_section(pc_frame, "Secret", format_multiline_text(pc_data.get("Secret", "")))

        col_idx += 1

    def _fix_scroll():
        banner_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    banner_frame.after(100, _fix_scroll)
