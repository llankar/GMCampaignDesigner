from modules.helpers.logging_helper import log_debug, log_function
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

@log_function
def position_window_at_top(window, width=None, height=None):
    """ Positionne une fenêtre au sommet de l'écran, centrée horizontalement.

    Args:
        window: la fenêtre CustomTkinter ou Tkinter à positionner.
        width: largeur fixe (facultatif). Si None, utilise la taille actuelle.
        height: hauteur fixe (facultatif). Si None, utilise la taille actuelle.
    """
    window.update_idletasks()

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    # Prefer the current geometry if already set (e.g., after window.geometry("900x650"))
    try:
        geo = window.geometry().split("+", 1)[0]
        parsed_w, parsed_h = map(int, geo.split("x"))
        g_width = parsed_w if parsed_w > 10 else None
        g_height = parsed_h if parsed_h > 10 else None
    except Exception:
        g_width = g_height = None

    if width is None:
        width_candidates = [g_width, window.winfo_width(), window.winfo_reqwidth()]
        width = next((w for w in width_candidates if w and w > 1), 1)
    if height is None:
        height_candidates = [g_height, window.winfo_height(), window.winfo_reqheight()]
        height = next((h for h in height_candidates if h and h > 1), 1)

    x = (screen_width - width) // 2
    y = 0  # Collé en haut de l'écran

    geometry = f"{width}x{height}+{x}+{y}"
    log_debug(f"Applying geometry {geometry} on screen {screen_width}x{screen_height}",
              func_name="modules.helpers.window_helper.position_window_at_top")
    window.geometry(geometry)
