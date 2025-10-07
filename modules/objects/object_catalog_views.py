import os
from typing import Callable, Iterable, Optional

import customtkinter as ctk
from PIL import Image

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import


MERCHANT_HEADER_COLOR = "#3C2F2F"
MERCHANT_HEADER_BORDER = "#9C6B3D"
MERCHANT_BODY_COLOR = "#241B14"
MERCHANT_TEXT_COLOR = "#F5E6C8"
MERCHANT_SUBTEXT_COLOR = "#C9AA7D"
MERCHANT_SECTION_GAP = 8

OBJECT_VIEW_SECTION = "ObjectCatalogView"
OBJECT_VIEW_KEY = "mode"
OBJECT_VIEW_CLASSIC = "classic"
OBJECT_VIEW_ACCORDION = "accordion"


def load_object_catalog_mode() -> str:
    """Return the persisted object catalog display mode."""

    cfg = ConfigHelper.load_campaign_config()
    if cfg.has_section(OBJECT_VIEW_SECTION):
        raw = cfg.get(OBJECT_VIEW_SECTION, OBJECT_VIEW_KEY, fallback="")
        normalized = raw.strip().lower()
        if normalized in {OBJECT_VIEW_CLASSIC, OBJECT_VIEW_ACCORDION}:
            return normalized
    return OBJECT_VIEW_CLASSIC


def save_object_catalog_mode(mode: str) -> None:
    """Persist the object catalog display mode to the campaign settings."""

    mode = (mode or "").strip().lower()
    if mode not in {OBJECT_VIEW_CLASSIC, OBJECT_VIEW_ACCORDION}:
        mode = OBJECT_VIEW_CLASSIC
    cfg = ConfigHelper.load_campaign_config()
    if not cfg.has_section(OBJECT_VIEW_SECTION):
        cfg.add_section(OBJECT_VIEW_SECTION)
    cfg.set(OBJECT_VIEW_SECTION, OBJECT_VIEW_KEY, mode)
    settings_path = ConfigHelper.get_campaign_settings_path()
    with open(settings_path, "w", encoding="utf-8") as f:
        cfg.write(f)
    try:
        ConfigHelper._campaign_mtime = os.path.getmtime(settings_path)
    except OSError:
        pass


class _CollapsibleSection(ctk.CTkFrame):
    """Fallback collapsible section for environments lacking CTkCollapsibleFrame."""

    def __init__(
        self,
        master,
        *,
        title: str,
        subtitle: str = "",
        category: str = "",
        on_open: Optional[Callable[[], None]] = None,
        merchant_palette: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._body_visible = False
        self._on_open = on_open
        self._body_frame: Optional[ctk.CTkFrame] = None
        self._indicator_label: Optional[ctk.CTkLabel] = None
        self._merchant_palette = merchant_palette

        self.container = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color=MERCHANT_HEADER_COLOR if merchant_palette else "#2B2B2B",
            border_width=1,
            border_color=MERCHANT_HEADER_BORDER if merchant_palette else "#444444",
        )
        self.container.pack(fill="x", padx=4, pady=(MERCHANT_SECTION_GAP, 0))
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_columnconfigure(1, weight=0)

        title_font = ("Segoe UI", 15, "bold")
        subtitle_font = ("Segoe UI", 12)
        category_font = ("Segoe UI", 11, "bold")

        text_color = MERCHANT_TEXT_COLOR if merchant_palette else "white"
        subtext_color = MERCHANT_SUBTEXT_COLOR if merchant_palette else "#CCCCCC"

        self._title_label = ctk.CTkLabel(
            self.container,
            text=title,
            font=title_font,
            anchor="w",
            text_color=text_color,
        )
        self._title_label.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 0))

        if category:
            self._category_label = ctk.CTkLabel(
                self.container,
                text=category,
                font=category_font,
                anchor="e",
                text_color=subtext_color,
            )
            self._category_label.grid(row=0, column=1, sticky="e", padx=(0, 16), pady=(12, 0))
        else:
            self._category_label = None

        self._subtitle_label = ctk.CTkLabel(
            self.container,
            text=subtitle,
            font=subtitle_font,
            anchor="w",
            text_color=subtext_color,
            wraplength=520,
        )
        self._subtitle_label.grid(row=1, column=0, columnspan=2, sticky="we", padx=16, pady=(4, 12))

        self._indicator_label = ctk.CTkLabel(
            self.container,
            text="▼",
            font=("Segoe UI", 18),
            text_color=subtext_color,
        )
        self._indicator_label.place(relx=0.98, rely=0.5, anchor="e")

        for widget in (self.container, self._title_label, self._subtitle_label, self._indicator_label):
            widget.bind("<Button-1>", self._toggle)

    def _toggle(self, _event=None):
        if self._body_visible:
            self.hide()
        else:
            self.show()
        if self._body_visible and callable(self._on_open):
            try:
                self._on_open()
            except Exception:
                pass

    def show(self):
        if self._body_frame is None:
            return
        if not self._body_visible:
            self._body_frame.pack(fill="x", padx=4, pady=(0, MERCHANT_SECTION_GAP))
            if self._indicator_label:
                self._indicator_label.configure(text="▲")
            self._body_visible = True

    def hide(self):
        if self._body_frame and self._body_visible:
            self._body_frame.pack_forget()
            if self._indicator_label:
                self._indicator_label.configure(text="▼")
            self._body_visible = False

    def assign_body(self, frame: ctk.CTkFrame):
        self._body_frame = frame
        frame.configure(corner_radius=0)


class MerchantCatalogEntry(_CollapsibleSection):
    """Visual representation of a single object in the merchant-style catalog."""

    def __init__(
        self,
        master,
        *,
        name: str,
        stats_preview: str,
        category: str,
        description: str,
        stats_full: str,
        secrets: str,
        portrait_path: Optional[str],
        resolve_media_path: Optional[Callable[[str], Optional[str]]],
        on_edit: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(
            master,
            title=name or "Unnamed Object",
            subtitle=stats_preview,
            category=category,
            on_open=None,
        )
        self._resolve_media_path = resolve_media_path
        self._portrait_path = portrait_path
        self._portrait_image: Optional[ctk.CTkImage] = None
        self._on_edit = on_edit
        self._description = description
        self._stats_full = stats_full
        self._secrets = secrets

        body = ctk.CTkFrame(
            self,
            fg_color=MERCHANT_BODY_COLOR,
            border_width=1,
            border_color=MERCHANT_HEADER_BORDER,
        )
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)

        text_color = MERCHANT_TEXT_COLOR
        header_font = ("Segoe UI", 12, "bold")
        body_font = ("Segoe UI", 12)

        row = 0
        if self._stats_full:
            stats_section = ctk.CTkFrame(body, fg_color="transparent")
            stats_section.grid(row=row, column=0, sticky="we", padx=18, pady=(16, 8))
            ctk.CTkLabel(
                stats_section,
                text="Stats",
                font=header_font,
                text_color=text_color,
                anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                stats_section,
                text=self._stats_full,
                font=body_font,
                text_color=text_color,
                wraplength=620,
                justify="left",
                anchor="w",
            ).pack(anchor="w", pady=(4, 0))
            row += 1

        if self._description:
            desc_section = ctk.CTkFrame(body, fg_color="transparent")
            desc_section.grid(row=row, column=0, sticky="we", padx=18, pady=(8, 8))
            ctk.CTkLabel(
                desc_section,
                text="Description",
                font=header_font,
                text_color=text_color,
                anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                desc_section,
                text=self._description,
                font=body_font,
                text_color=text_color,
                wraplength=620,
                justify="left",
                anchor="w",
            ).pack(anchor="w", pady=(4, 0))
            row += 1

        if self._secrets:
            secret_section = ctk.CTkFrame(body, fg_color="transparent")
            secret_section.grid(row=row, column=0, sticky="we", padx=18, pady=(8, 12))
            ctk.CTkLabel(
                secret_section,
                text="Secrets",
                font=header_font,
                text_color=text_color,
                anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                secret_section,
                text=self._secrets,
                font=body_font,
                text_color=text_color,
                wraplength=620,
                justify="left",
                anchor="w",
            ).pack(anchor="w", pady=(4, 0))
            row += 1

        edit_container = ctk.CTkFrame(body, fg_color="transparent")
        edit_container.grid(row=row, column=0, sticky="we", padx=18, pady=(4, 16))
        edit_container.grid_columnconfigure(0, weight=1)
        if callable(self._on_edit):
            edit_button = ctk.CTkButton(
                edit_container,
                text="Open in Editor",
                command=self._on_edit,
                fg_color="#A47148",
                hover_color="#C18E5A",
            )
            edit_button.grid(row=0, column=0, sticky="e")
        row += 1

        if portrait_path:
            image_label = ctk.CTkLabel(body, text="", anchor="center")
            image_label.grid(row=0, column=1, rowspan=row, sticky="ne", padx=(0, 18), pady=18)
            self._assign_portrait(image_label)

        self.assign_body(body)

    def _assign_portrait(self, label: ctk.CTkLabel) -> None:
        if not self._resolve_media_path:
            return
        resolved = self._resolve_media_path(self._portrait_path)
        if not resolved:
            return
        try:
            with Image.open(resolved) as img:
                preview = img.copy()
        except Exception:
            return
        if hasattr(Image, "Resampling"):
            preview.thumbnail((180, 180), Image.Resampling.LANCZOS)
        else:
            preview.thumbnail((180, 180), Image.LANCZOS)
        self._portrait_image = ctk.CTkImage(light_image=preview, dark_image=preview, size=preview.size)
        label.configure(image=self._portrait_image)


class ObjectAccordionCatalog(ctk.CTkFrame):
    """Scrollable merchant-style accordion catalog for objects."""

    def __init__(
        self,
        master,
        *,
        resolve_media_path: Optional[Callable[[str], Optional[str]]] = None,
        on_edit_item: Optional[Callable[[dict], None]] = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._resolve_media_path = resolve_media_path
        self._on_edit_item = on_edit_item
        self._items: Iterable[dict] = []
        self._sections: list[MerchantCatalogEntry] = []

        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self._scroll.pack(fill="both", expand=True)

        self._empty_label = ctk.CTkLabel(
            self._scroll,
            text="No objects to display",
            font=("Segoe UI", 14, "italic"),
            text_color=MERCHANT_SUBTEXT_COLOR,
        )
        self._empty_label.pack_forget()

    @staticmethod
    def _clean_text(value: Optional[str]) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _stats_preview(stats: str, limit: int = 160) -> str:
        if not stats:
            return "No stats available"
        text = " ".join(stats.split())
        if len(text) > limit:
            return text[:limit].rstrip() + "..."
        return text

    def populate(
        self,
        items: Iterable[dict],
        *,
        unique_field: str = "Name",
        stats_field: str = "Stats",
        description_field: str = "Description",
        secrets_field: str = "Secrets",
        category_field: str = "Category",
        portrait_field: Optional[str] = None,
    ) -> None:
        """Populate the accordion with the provided object entries."""

        for widget in self._scroll.winfo_children():
            widget.destroy()
        self._sections.clear()

        item_list = list(items)
        if not item_list:
            empty = ctk.CTkLabel(
                self._scroll,
                text="No objects to display",
                font=("Segoe UI", 14, "italic"),
                text_color=MERCHANT_SUBTEXT_COLOR,
            )
            empty.pack(padx=24, pady=24)
            self._empty_label = empty
            return

        self._empty_label = None

        for item in item_list:
            name = self._clean_text(item.get(unique_field) or item.get("Name") or "") or "Unnamed Object"
            stats_full = self._clean_text(item.get(stats_field))
            description = self._clean_text(item.get(description_field))
            secrets = self._clean_text(item.get(secrets_field))
            category = self._clean_text(item.get(category_field))
            portrait_path = item.get(portrait_field) if portrait_field else None

            preview = self._stats_preview(stats_full)

            def _make_edit_callback(entry=item):
                if not callable(self._on_edit_item):
                    return None

                def _callback():
                    try:
                        self._on_edit_item(entry)
                    except Exception:
                        pass

                return _callback

            section = MerchantCatalogEntry(
                self._scroll,
                name=name,
                stats_preview=preview,
                category=category,
                description=description,
                stats_full=stats_full,
                secrets=secrets,
                portrait_path=portrait_path,
                resolve_media_path=self._resolve_media_path,
                on_edit=_make_edit_callback(),
            )
            section.pack(fill="x", padx=4, pady=0)
            self._sections.append(section)


log_module_import(__name__)

