"""Entry point for the frozen update helper executable."""

from apply_update import main as _apply_update_main


def main() -> None:
    """Invoke the update application logic."""
    _apply_update_main()


if __name__ == "__main__":
    main()
