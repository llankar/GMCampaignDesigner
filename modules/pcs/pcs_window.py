import customtkinter as ctk

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_function, log_module_import
from modules.pcs.display_pcs import display_pcs_in_banner

log_module_import(__name__)


class PCSWindow(ctk.CTkToplevel):
    def __init__(self, parent, pc_wrapper=None, on_close=None):
        super().__init__(parent)
        self.pc_wrapper = pc_wrapper or GenericModelWrapper("pcs")
        self._on_close = on_close
        self._is_docked = False
        self._restore_geometry = None

        self.title("PCs")
        self.geometry("1200x300")

        self._build_layout()
        self.refresh_banner()

        self.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _build_layout(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        self.dock_button = ctk.CTkButton(
            header,
            text="Dock Top",
            width=120,
            command=self._toggle_dock,
        )
        self.dock_button.pack(side="left")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.banner_frame = ctk.CTkFrame(content, fg_color="#444")
        self.banner_frame.pack(fill="both", expand=True)

    def refresh_banner(self):
        pcs_items = self.pc_wrapper.load_items()
        pcs_map = {}
        for idx, pc in enumerate(pcs_items or []):
            pc_name = pc.get("Name") or f"PC {idx + 1}"
            pcs_map[pc_name] = pc
        display_pcs_in_banner(self.banner_frame, pcs_map)

    def _toggle_dock(self):
        if not self._is_docked:
            self._restore_geometry = self.geometry()
            self.update_idletasks()
            height = max(self.winfo_height(), self.winfo_reqheight())
            screen_width = self.winfo_screenwidth()
            self.geometry(f"{screen_width}x{height}+0+0")
            self._is_docked = True
            self.dock_button.configure(text="Undock")
        else:
            if self._restore_geometry:
                self.geometry(self._restore_geometry)
            self._is_docked = False
            self.dock_button.configure(text="Dock Top")

    def _handle_close(self):
        if callable(self._on_close):
            self._on_close()
        self.destroy()


@log_function
def open_pcs_window(parent, pc_wrapper=None, on_close=None):
    window = PCSWindow(parent, pc_wrapper=pc_wrapper, on_close=on_close)
    window.lift()
    window.focus_force()
    return window
