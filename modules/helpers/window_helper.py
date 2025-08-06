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

    if width is None:
        width = window.winfo_reqwidth()
    if height is None:
        height = window.winfo_reqheight()

    x = (screen_width - width) // 2
    y = 0  # Collé en haut de l'écran

    window.geometry(f"{width}x{height}+{x}+{y}")
