# Image editor architecture (image library)

The `modules/ui/image_library/editor/` package follows a layered split to keep files short and responsibilities explicit.

## Module boundaries

- `image_editor_dialog.py`
  - Thin orchestration/controller for UI events.
  - Wires widgets, state, commands, tools, and save services together.

- `core/`
  - Domain state and rendering primitives.
  - `document.py`, `layer.py`, and compositing/render support.

- `tools/`
  - User-facing editing tools (paint, eraser) that mutate the active layer.

- `widgets/`
  - Reusable UI components:
    - `toolbar.py`
    - `tool_options.py`
    - `layers_panel.py`
    - `status_bar.py`

- `io/`
  - Persistence and export concerns:
    - `save_service.py`
    - `formats.py` for output format handling.

- `history/`
  - Command stack and undo/redo command objects.

## Dependency direction

- `image_editor_dialog.py` may import from all subpackages.
- `widgets/`, `tools/`, `io/`, and `history/` should not import the dialog.
- `tools/` depend on `core/` abstractions only.
- `io/` stays unaware of UI and command history.
