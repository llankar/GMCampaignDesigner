# GM Screen 2 Architecture

This document describes the **new isolated architecture** under `modules/scenarios/gm_screen2/`.

## Module boundaries

- `app/`
  - `gm_screen2_controller.py` orchestrates lifecycle: `initialize`, `load_scenario`, `update_state`, `teardown`.
- `domain/`
  - `models.py` defines immutable entities (`ScenarioSummary`, `PanelPayload`, `ScenarioFilter`, `LayoutPreset`, `ScenarioPanelBundle`).
- `services/`
  - `interfaces.py` defines repository/provider protocols.
  - `adapters.py` contains GM Screen 2 adapters over existing scenario data wrappers.
  - `mappers/` contains GM Screen 2-specific mapping logic.
- `state/`
  - `screen_state.py` stores mutable view state.
  - `layout_state.py` stores panel arrangement state.
- `events/`
  - `contracts.py` contains a local event bus contract implementation.
- `ui/`
  - `gm_screen2_root_view.py` is the passive root view.
  - `panels/` includes one file per panel type.
  - `layout/desktop_layout_engine.py` computes responsive panel geometry.

## Dependency direction rules

Allowed direction (outer to inner):

1. `ui -> app/state/domain`
2. `app -> services/state/events/domain`
3. `services -> domain`
4. `state -> domain`

Disallowed:

- `domain` importing from other layers.
- `ui` importing persistence/db code.
- Any import from `modules/scenarios/gm_screen/*` within `modules/scenarios/gm_screen2/*`.

## Migration guardrail

`MainWindow.open_gm_screen2(...)` keeps its public signature unchanged while routing to:

- `GMScreen2Controller`
- `GMScreen2RootView`
- GM Screen 2 service adapters and mappers.

The compatibility class `GMScreen2View` remains as a wrapper around the new controller/root view stack.
