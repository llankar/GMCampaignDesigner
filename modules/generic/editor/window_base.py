from modules.generic.editor.window_context import *
from modules.generic.editor.styles import EDITOR_PALETTE


@log_methods
class GenericEditorWindowBase(ctk.CTkToplevel):
    def __init__(self, master, item, template, model_wrapper, creation_mode=False):
        super().__init__(master)
        self.item = item
        # ``FogMaskPath`` and the token metadata are intentionally hidden from the
        # editor UI, but they must be preserved when the record is written back
        # to the database.  If we omit them from the INSERT/REPLACE statement the
        # corresponding columns are reset to NULL, which destroys the saved fog
        # state in Map Tool.  Capture the current values so ``save()`` can
        # restore them even though there is no visible widget for those fields.
        hidden_fields = {"FogMaskPath", "Tokens", "token_size"}
        self._preserved_hidden_fields = {}
        if isinstance(item, dict):
            for field_name in hidden_fields:
                if field_name in item:
                    self._preserved_hidden_fields[field_name] = item[field_name]
        self.template = template
        self.saved = False
        self.model_wrapper = model_wrapper
        self.creation_mode = creation_mode
        self.field_widgets = {}
        self._file_field_info = {}
        self._field_sections = {}
        self._field_section_order = []
        self._hidden_field_sections = set()
        self._dirty = False
        
        self.transient(master)
        self.lift()
        self.grab_set()
        self.focus_force()
        self.bind("<Escape>", lambda e: self.destroy())
        item_type = self.model_wrapper.entity_type.capitalize()[:-1]  # "npcs" → "Npc"
        self.title(
            f"Create {item_type}"
            if creation_mode
            else self._build_edit_title(item_type)
        )

        self.configure(fg_color=EDITOR_PALETTE["surface"])

        self.main_frame = ctk.CTkFrame(self, fg_color=EDITOR_PALETTE["surface"])
        self.main_frame.pack(fill="both", expand=True)

        self.toolbar = SmartEditorToolbar(
            self.main_frame,
            on_filter_change=self._filter_visible_fields,
            on_jump_to_field=self._jump_to_field,
        )
        self.toolbar.pack(fill="x", padx=5, pady=(5, 0))

        self.scroll_frame = ctk.CTkScrollableFrame(
            self.main_frame,
            fg_color=EDITOR_PALETTE["surface"],
            scrollbar_button_color=EDITOR_PALETTE["surface_soft"],
            scrollbar_button_hover_color=EDITOR_PALETTE["accent"],
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.scroll_frame.grid_columnconfigure(0, weight=1, uniform="editor_fields")
        self.scroll_frame.grid_columnconfigure(1, weight=1, uniform="editor_fields")

        self._left_column = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._right_column = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._left_column.grid(row=0, column=0, sticky="new")
        self._right_column.grid(row=0, column=1, sticky="new")

        fields = prioritize_fields(self.template["fields"])
        for field in fields:
            self._render_standard_field(field)

        self.toolbar.set_fields(self._field_section_order)
                

        self.create_action_bar()

        # Instead of a fixed geometry, update layout and compute the required size.
        self.update_idletasks()
        req_width = self.winfo_reqwidth()
        req_height = self.winfo_reqheight()
        # Responsive width on smaller screens while preserving comfortable defaults.
        screen_w = max(self.winfo_screenwidth(), 1200)
        screen_h = self.winfo_screenheight()
        min_width = min(1000, int(screen_w * 0.92))
        min_height = min(900, int(screen_h * 0.88))
        req_width = max(min_width, min(req_width, int(screen_w * 0.94)))
        # Force the generic editor to open at 1080px tall (capped by screen size
        # on smaller displays) so the window consistently fills a 1080p screen.
        req_height = min(1080, screen_h)
        self.geometry(f"{req_width}x{req_height}")
        self.minsize(min_width, min_height)

        # Optionally, adjust window position.
        position_window_at_top(self)
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<KeyRelease>", self._mark_dirty, add="+")
        # Lazy AI client init
        self._ai_client = None

    def _build_edit_title(self, item_type: str) -> str:
        """Display the entity name in the title bar to save vertical UI space."""
        if not isinstance(self.item, dict):
            return f"Edit {item_type}"

        candidate_keys = ("Name", "Title", "Label")
        for key in candidate_keys:
            value = str(self.item.get(key, "")).strip()
            if value:
                return f"Edit {value}"
        return f"Edit {item_type}"
