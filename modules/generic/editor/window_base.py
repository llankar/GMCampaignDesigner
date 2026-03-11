from modules.generic.editor.window_context import *


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
        self._dirty = False
        
        self.transient(master)
        self.lift()
        self.grab_set()
        self.focus_force()
        self.bind("<Escape>", lambda e: self.destroy())
        item_type = self.model_wrapper.entity_type.capitalize()[:-1]  # "npcs" → "Npc"
        self.title(f"Create {item_type}" if creation_mode else f"Edit {item_type}")

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True)

        self.toolbar = SmartEditorToolbar(
            self.main_frame,
            on_filter_change=self._filter_visible_fields,
            on_jump_to_field=self._jump_to_field,
        )
        self.toolbar.pack(fill="x", padx=5, pady=(5, 0))

        self.scroll_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

        fields = prioritize_fields(self.template["fields"])
        for field in fields:
            self._render_standard_field(field)

        self.toolbar.set_fields(self._field_section_order)
                

        self.create_action_bar()

        # Instead of a fixed geometry, update layout and compute the required size.
        self.update_idletasks()
        req_width = self.winfo_reqwidth()
        req_height = self.winfo_reqheight()
        # Responsive size on smaller screens while preserving comfortable defaults.
        screen_w = max(self.winfo_screenwidth(), 1200)
        screen_h = max(self.winfo_screenheight(), 900)
        min_width = min(1000, int(screen_w * 0.92))
        min_height = min(900, int(screen_h * 0.88))
        req_width = max(min_width, min(req_width, int(screen_w * 0.94)))
        req_height = max(min_height, min(req_height, int(screen_h * 0.92)))
        self.geometry(f"{req_width}x{req_height}")
        self.minsize(min_width, min_height)

        # Optionally, adjust window position.
        position_window_at_top(self)
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<KeyRelease>", self._mark_dirty, add="+")
        # Lazy AI client init
        self._ai_client = None
