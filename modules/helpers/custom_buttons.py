import customtkinter as ctk
import tkinter.font as tkFont

class MinimalCTkButton(ctk.CTkButton):
    def __init__(self, master, text="", **kwargs):
        # Retirer la largeur si elle est fournie
        kwargs.pop("width", None)
        # Récupérer la police si spécifiée, sinon utiliser une valeur par défaut
        self._button_font = kwargs.pop("text_font", ("TkDefaultFont", 10))
        super().__init__(master, text=text, **kwargs)
        # Ajuster la largeur après initialisation
        self.after(0, self._adjust_width, text)

    def _adjust_width(self, text):
        # Mesurer la largeur du texte avec la police stockée
        font = tkFont.Font(font=self._button_font)
        text_width = font.measure(text)
        marge = 10  # marge supplémentaire (à ajuster selon vos besoins)
        self.configure(width=text_width + marge)
