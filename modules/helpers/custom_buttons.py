"""Utilities for custom buttons."""

import customtkinter as ctk
import tkinter.font as tkFont
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

class MinimalCTkButton(ctk.CTkButton):
    def __init__(self, master, text="", **kwargs):
        """Initialize the MinimalCTkButton instance."""
        # Retirer la largeur si elle est fournie
        kwargs.pop("width", None)
        # Retrieve the font if specified, otherwise use a default value
        self._button_font = kwargs.pop("text_font", ("TkDefaultFont", 10))
        super().__init__(master, text=text, **kwargs)
        # Adjust the width after initialization
        self.after(0, self._adjust_width, text)

    def _adjust_width(self, text):
        """Internal helper for adjust width."""
        # Measure text width with the stored font
        font = tkFont.Font(font=self._button_font)
        text_width = font.measure(text)
        margin = 10  # extra margin (adjust as needed)
        self.configure(width=text_width + margin)
