"""Character Creation package."""

__all__ = ["CharacterCreationView"]


def __getattr__(name):
    """Handle getattr."""
    if name == "CharacterCreationView":
        from .view import CharacterCreationView

        return CharacterCreationView
    raise AttributeError(name)
