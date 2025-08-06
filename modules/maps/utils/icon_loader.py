from modules.helpers.template_loader import load_template
from PIL import Image
import customtkinter as ctk


def load_icon(self, path, size=(32,32)):
    #Load & resize with PIL
    pil_img = Image.open(path).resize(size, resample=Image.LANCZOS)
    # Wrap in a CTkImage so CustomTkinter buttons get the right type
    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)

