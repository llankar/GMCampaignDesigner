# UI concepts for database-backed whiteboards

This note outlines multiple UI approaches for saving and loading whiteboards that are stored in a database and linked to scenarios.

## 1. Scenario-sidecar controls
- **What it looks like:** Add "Whiteboard" controls to each scenario view pane (e.g., a toolbar with **Save**, **Load**, and **History** buttons). Saving writes the in-memory state into the DB row keyed by the scenario; loading pulls the latest saved state.
- **Pros:**
  - Keeps the controls where scenario authors already work, reducing navigation.
  - Clear ownership: the scenario context guarantees the correct board is targeted.
  - Minimal new navigation surfaces; can reuse existing scenario detail layout.
- **Cons:**
  - Toolbar clutter if the scenario view is already dense.
  - Discoverability depends on users visiting the scenario page; no global view of boards.
  - History browsing may be constrained by the scenario layout.

## 2. Dedicated whiteboard manager panel
- **What it looks like:** A new side panel or page listing scenarios with their latest whiteboard status, with actions for **Open**, **Save**, **Restore previous**, and **Duplicate**. Selecting a scenario loads its board into the canvas.
- **Pros:**
  - Central place to manage all boards, with filters for scenarios that have unsaved changes or stale boards.
  - Easier to introduce multi-board-per-scenario in the future because the manager can show multiple rows per scenario.
  - Supports batch actions (e.g., save all dirty boards) and at-a-glance health checks.
- **Cons:**
  - Adds navigation overhead compared to in-scenario controls.
  - Requires UI real estate for the manager; context switching away from the scenario view.
  - More work to keep the manager in sync with scenario edits.

## 3. Modal save/load workflow
- **What it looks like:** From the whiteboard canvas, a **Save/Load** button opens a modal tied to the current scenario. The modal shows the current board metadata, allows naming snapshots, and lists previous saves for restore.
- **Pros:**
  - Keeps focus on the canvas while exposing per-scenario persistence.
  - Modals are quick to implement and avoid permanent UI clutter.
  - Snapshot naming/notes can live in the modal without crowding the main view.
- **Cons:**
  - Modal-heavy UX can feel interruptive.
  - Limited room for rich history browsing or diffing.
  - If multiple boards per scenario arrive later, the modal may become crowded.

## 4. Timeline/history drawer
- **What it looks like:** A collapsible drawer on the whiteboard screen showing a chronological list of saves for the current scenario, with **Revert**, **Pin**, and **Label** actions. Saves are triggered by an explicit **Save** button or auto-save interval.
- **Pros:**
  - Immediate visibility of save state and the ability to jump to older versions.
  - Encourages frequent saves because the history is one click away.
  - Drawer can show sync status/errors from the DB backend.
- **Cons:**
  - Consumes space on the whiteboard screen, potentially reducing canvas area.
  - Heavier to implement (UI state + pagination) than a basic toolbar.
  - Without good pruning rules, history can become noisy.

## 5. Autosave with status indicator
- **What it looks like:** The canvas auto-saves to the scenario-linked DB record on interval or blur, with a small status chip (e.g., "Saved", "Syncing…", "Offline"). Manual **Save now**/**Restore last** remain available via a menu.
- **Pros:**
  - Reduces risk of data loss and lowers cognitive load on users.
  - Status chip clarifies when the DB write succeeds or fails.
  - Manual override paths remain for power users.
- **Cons:**
  - Needs careful conflict handling if multiple clients edit the same scenario.
  - Auto-saving may briefly interrupt performance on large boards if not batched.
  - Users may prefer explicit control for major milestones despite autosave.
