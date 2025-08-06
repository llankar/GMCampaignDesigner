# Plan for Implementing Shapes in Display Map Controller

This document outlines the plan to add functionality for creating, editing, and managing shapes (rectangles and ovals) within the display map controller, basing the implementation on the existing token management system.

**User Requirements:**

- Shapes: Rectangle and Oval.
- Modes: Full fill or border only.
- Editable: Color, size.
- Movable.
- Copyable: Ctrl+C, Ctrl+V.

**Clarifications Received:**

1.  **Storage**: Integrate shape data into the existing `current_map["Tokens"]` list by adding a 'type' field (e.g., 'token', 'rectangle', 'oval').
2.  **Toolbar**: Use a dropdown menu for shape tools.
3.  **Creation UX**: Users click to place a default-sized shape, then edit.
4.  **Editing UX for Size**: Resize shapes via a dialog box.
5.  **Layering**: Layering order can be managed by the user.

---

## I. Data Model Enhancements

- **Location:** Primarily [`modules/maps/services/token_manager.py`](modules/maps/services/token_manager.py) and impacting how data is handled in [`modules/maps/controllers/display_map_controller.py`](modules/maps/controllers/display_map_controller.py).
- **Changes:**
  1.  **Modify Token Structure:**
      - In `DisplayMapController` (where `self.tokens` is managed) and in `_persist_tokens` in `token_manager.py`, the dictionary for each item in `self.tokens` will be augmented.
      - Add a `type` field: This will be a string, e.g., `"token"`, `"rectangle"`, or `"oval"`.
      - For items with `type` as `"rectangle"` or `"oval"`, add the following fields:
        - `shape_type`: String, either `"rectangle"` or `"oval"`.
        - `fill_color`: String, hex color code (e.g., `"#FF0000"`).
        - `border_color`: String, hex color code (already present for tokens, will be reused).
        - `is_filled`: Boolean, `True` if the shape is filled, `False` if only border.
        - `width`: Integer, width of the shape in pixels.
        - `height`: Integer, height of the shape in pixels.
        - `position`: Tuple `(x, y)` representing the top-left corner.
  2.  **Persistence (`_persist_tokens`):**
      - Modify `_persist_tokens` in `token_manager.py` to serialize these new fields (`type`, `shape_type`, `fill_color`, `is_filled`, `width`, `height`) when an item is a shape.
  3.  **Loading Logic:**
      - When loading map data (likely in `_on_display_map` in `DisplayMapController`), ensure it correctly deserializes these new fields and populates the `self.tokens` list with both tokens and shapes.

---

## II. Toolbar Integration

- **Location:** `modules/maps/views/toolbar_view.py` (function `_build_toolbar`) and `DisplayMapController` for state management.
- **Changes:**
  1.  **Drawing Mode Selection:**
      - Add a new state variable in `DisplayMapController`, e.g., `self.drawing_mode` (values: `"token"`, `"rectangle"`, `"oval"`). Default to `"token"`.
      - In `_build_toolbar`, add a dropdown menu (e.g., `ctk.CTkOptionMenu`) to allow the user to select the `drawing_mode`. The callback for this menu will update `self.drawing_mode`.
  2.  **Shape Fill/Border Mode:**
      - Add a state variable in `DisplayMapController`, e.g., `self.shape_is_filled` (boolean).
      - In `_build_toolbar`, add a button or a small dropdown to toggle `self.shape_is_filled`. This control should perhaps only be active/visible when `self.drawing_mode` is `"rectangle"` or `"oval"`.
  3.  **Color Pickers:**
      - Add state variables in `DisplayMapController` for `self.current_shape_fill_color` and `self.current_shape_border_color`.
      - In `_build_toolbar`, add two buttons that, when clicked, open a color chooser dialog. One for fill color, one for border color. These update the respective state variables. These might also only be active/visible when a shape drawing mode is selected.

---

## III. Shape Creation

- **Location:** `DisplayMapController` (mouse event handlers like `_on_mouse_down`) and `modules/maps/views/canvas_view.py` for drawing.
- **Changes:**
  1.  **Creation Trigger:**
      - Modify `_on_mouse_down` (or a similar canvas click handler) in `DisplayMapController`.
      - If `self.drawing_mode` is `"rectangle"` or `"oval"`:
        - Create a new shape dictionary with default dimensions (e.g., 50x50 pixels), the current `self.shape_is_filled`, `self.current_shape_fill_color`, `self.current_shape_border_color`, and the click position.
        - Set its `type` to `self.drawing_mode`.
        - Add this new shape dictionary to `self.tokens`.
        - Call `self._update_canvas_images()` to draw it.
        - Call `self._persist_tokens()` to save it.
  2.  **Drawing Shapes (`_update_canvas_images`):**
      - In `_update_canvas_images` in `DisplayMapController`:
        - When iterating through `self.tokens`, check the `item['type']`.
        - If it's `"rectangle"`: Use `self.canvas.create_rectangle()` with `item['position']`, `item['width']`, `item['height']`, `item['fill_color']` (if `item['is_filled']`), and `item['border_color']`.
        - If it's `"oval"`: Use `self.canvas.create_oval()` similarly.
        - Store the canvas ID(s) in the item dictionary (e.g., `item['canvas_ids'] = (shape_id,)`) for later manipulation.

---

## IV. Shape Editing

- **Location:** `modules/maps/services/token_manager.py` and `DisplayMapController`.
- **Changes:**
  1.  **Selection (`_on_token_press`):**
      - The existing `_on_token_press` in `token_manager.py` should work for shapes if they have `canvas_ids` and are tagged appropriately. `self.selected_token` in `DisplayMapController` will now point to the selected shape or token.
  2.  **Context Menu (`_show_token_menu`):**
      - Modify `_show_token_menu` in `token_manager.py`.
      - If `self.selected_token['type']` is `"rectangle"` or `"oval"`:
        - Show a different context menu:
          - "Edit Shape Color": Calls a new function `_edit_shape_color_dialog(self, shape)`.
          - "Edit Shape Size": Calls a new function `_resize_shape_dialog(self, shape)`.
          - "Toggle Fill/Border": Calls a function `_toggle_shape_fill(self, shape)`.
          - "Delete Shape": Can adapt/reuse `_delete_token`.
          - "Copy Shape": Can adapt/reuse `_copy_token`.
          - "Bring to Front" / "Send to Back": Calls new layering functions.
  3.  **Color Editing (`_edit_shape_color_dialog`):**
      - Create this new function.
      - It opens two color choosers: one for fill, one for border.
      - Updates the shape's `fill_color` and `border_color` properties.
      - Calls `self._update_canvas_images()` and `self._persist_tokens()`.
  4.  **Size Editing (`_resize_shape_dialog`):**
      - Create this new function.
      - Similar to `_resize_token_dialog`, but prompts for `width` and `height` via a dialog.
      - Updates the shape's `width` and `height`.
      - Calls `self._update_canvas_images()` and `self._persist_tokens()`.
  5.  **Fill/Border Toggle (`_toggle_shape_fill`):**
      - Create this new function. It flips the `is_filled` boolean for the selected shape.
      - Calls `self._update_canvas_images()` and `self._persist_tokens()`.

---

## V. Movement

- **Location:** `modules/maps/services/token_manager.py`.
- **Changes:**
  - The existing `_on_token_move` should largely work for shapes if their `canvas_ids` are correctly managed and they have a `position` attribute that's updated. Ensure the `position` reflects the top-left corner after a move.

---

## VI. Copy/Paste

- **Location:** `modules/maps/services/token_manager.py`.
- **Changes:**
  1.  **`_copy_token`:**
      - Modify `_copy_token`. If `self.selected_token['type']` is a shape, copy its shape-specific properties (`type`, `shape_type`, `fill_color`, `border_color`, `is_filled`, `width`, `height`) into `self.clipboard_token`.
  2.  **`_paste_token`:**
      - Modify `_paste_token`. If `self.clipboard_token['type']` is a shape, create a new shape dictionary with these properties, place it at the current mouse position or canvas center, add it to `self.tokens`, and redraw/persist.

---

## VII. Layering

- **Location:** `DisplayMapController`.
- **Changes:**
  1.  The drawing order is determined by the order of items in `self.tokens`.
  2.  **`_bring_to_front(self, item)`:**
      - Removes `item` from `self.tokens` and appends it.
      - Calls `self._update_canvas_images()` and `self._persist_tokens()`.
  3.  **`_send_to_back(self, item)`:**
      - Removes `item` from `self.tokens` and inserts it at the beginning (index 0).
      - Calls `self._update_canvas_images()` and `self._persist_tokens()`.
  4.  Shapes and tokens will be drawn on top of fog of war layers as per their order in `self.tokens`.

---

## VIII. Keyboard Shortcuts

- **Location:** `DisplayMapController` (where canvas bindings are set up).
- **Changes:**
  - The existing bindings for Ctrl+C (`_copy_token`) and Ctrl+V (`_paste_token`) should work for shapes once those functions are adapted.

---

## Mermaid Diagram (Illustrative Flow)

```mermaid
graph TD
    subgraph Toolbar
        direction LR
        TB1[Dropdown: Select Tool (Token/Rect/Oval)] -->|Updates self.drawing_mode| DMC
        TB2[Button: Fill/Border] -->|Updates self.shape_is_filled| DMC
        TB3[Button: Pick Fill Color] -->|Updates self.current_shape_fill_color| DMC
        TB4[Button: Pick Border Color] -->|Updates self.current_shape_border_color| DMC
    end

    subgraph Canvas Interaction
        direction TB
        CI1[User Click on Canvas] -->|If shape tool active| DMC_CreateShape["DisplayMapController: Create Shape"]
        CI2[User Right-Click Shape] --> DMC_ContextMenu["DisplayMapController: Show Shape Context Menu"]
        CI3[User Drags Shape] --> TM_Move["TokenManager: _on_token_move (adapted)"]
        CI4[User Presses Ctrl+C/V] --> DMC_CopyPaste["DisplayMapController: Calls _copy_token/_paste_token"]
    end

    subgraph DisplayMapController as DMC
        direction TB
        DMC_CreateShape --> AddToTokens["Add shape to self.tokens"]
        AddToTokens --> UpdateCanvas["_update_canvas_images (draws shapes)"]
        AddToTokens --> Persist["_persist_tokens (saves shapes)"]
        DMC_ContextMenu --> TM_Edit["TokenManager: Shape Edit Functions (Size, Color, Fill)"]
        TM_Edit --> UpdateCanvas
        TM_Edit --> Persist
        DMC_CopyPaste --> TM_CopyPaste["TokenManager: _copy_token/_paste_token (adapted)"]
        TM_CopyPaste --> AddToTokens
    end

    subgraph TokenManager as TM
        direction TB
        TM_Move --> UpdateCanvas
        TM_Move --> Persist
    end

    DMC --> TM
```
