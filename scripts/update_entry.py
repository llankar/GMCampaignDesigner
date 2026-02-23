"""Entry point for the frozen update helper executable."""

from updater_ui.controller import run_updater_app


def main() -> int:
    """Invoke the updater UI controller."""
    return run_updater_app()


if __name__ == "__main__":
    raise SystemExit(main())
