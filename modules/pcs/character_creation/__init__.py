__all__ = ["CharacterCreationView"]


def __getattr__(name):
    if name == "CharacterCreationView":
        from .view import CharacterCreationView

        return CharacterCreationView
    raise AttributeError(name)
