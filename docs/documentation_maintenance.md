# Documentation Maintenance

Use `scripts/generate_docs.py` to refresh the committed application documentation.

## What the script updates

- `docs/index.html`: generated reference page with screenshots, context menus, and module API output
- `docs/user-manual.html`: generated user manual
- `docs/images/*.png`: screenshots captured from the running desktop app

## When to run it

Run the generator after changes that affect any of the following:

- main application layout or window flow
- screenshots shown in the docs
- right-click menus
- module/class/function signatures or docstrings that should appear in the generated API reference
- user-manual copy embedded in `scripts/generate_docs.py`

## How to run it

From the repository root:

```powershell
python scripts/generate_docs.py
```

## Requirements

- Use the same Python environment that can already launch `main_window.py`.
- Run from an interactive desktop session. The script opens Tk/customtkinter windows and uses Pillow's `ImageGrab` to capture screenshots.
- Leave the desktop available while it runs. Moving or covering the windows can affect captured images.

## Recommended workflow

1. Make the UI or documentation-source changes.
2. Run `python scripts/generate_docs.py`.
3. Review `docs/index.html`, `docs/user-manual.html`, and any updated files in `docs/images/`.
4. Check that screenshots are complete, readable, and free of accidental personal campaign data.
5. Commit the source changes and the regenerated documentation together.

## Troubleshooting

- If screenshot capture fails, confirm that the script is running on a machine with an active desktop session.
- If imports fail, install the normal application dependencies first, then rerun the script.
- If generated screenshots contain the wrong campaign content, switch to the intended campaign data before running the generator.

## Notes

- `docs/index.html` and `docs/user-manual.html` are generated outputs. Long-term changes should be made in `scripts/generate_docs.py`, then reflected in the committed HTML files.
- The script sets `DOCS_MODE=1` while it runs so the application can adapt to documentation capture mode if needed.
