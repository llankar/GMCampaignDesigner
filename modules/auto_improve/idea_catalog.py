from __future__ import annotations

from modules.auto_improve.models import ImprovementProposal


PROPOSALS: tuple[ImprovementProposal, ...] = (
    ImprovementProposal(
        slug="feature-flags",
        title="Feature Flags System",
        summary="Allow new features to be toggled on/off from config to reduce rollout risk.",
        scope="config, modules/system, main_window",
        prompt=(
            "Implement a feature-flag framework for this codebase. Use dedicated subdirectories and split files by"
            " responsibility. Add a config section, a loader service, and integration points in MainWindow."
            " Add focused tests and keep backward compatibility."
        ),
    ),
    ImprovementProposal(
        slug="data-migrations",
        title="Versioned Data Migrations",
        summary="Introduce startup migrations for settings/data schema changes.",
        scope="modules/system/migrations, startup",
        prompt=(
            "Create a versioned migration engine with registry + runner + one sample migration."
            " Ensure migration state is persisted and safe. Keep architecture readable with subfolders and separate files."
        ),
    ),
    ImprovementProposal(
        slug="health-dashboard",
        title="Application Health Dashboard",
        summary="Add a diagnostics panel for paths, DB connection, optional services and recent errors.",
        scope="modules/diagnostics, UI",
        prompt=(
            "Add a health dashboard window that runs non-destructive checks (db available, config readable,"
            " required directories present). Structure code in separate modules for checks, models, and ui."
        ),
    ),
    ImprovementProposal(
        slug="bulk-edit",
        title="Bulk Edit Assistant",
        summary="Enable bulk updates across selected entities with preview before apply.",
        scope="generic list/editing modules",
        prompt=(
            "Implement bulk edit support with preview and rollback-friendly operations."
            " Use separate files for models, service, and dialog. Add tests for transformation logic."
        ),
    ),
    ImprovementProposal(
        slug="performance-tracing",
        title="Performance Tracing",
        summary="Track slow actions and long-running UI operations to identify bottlenecks.",
        scope="helpers/logging, UI actions",
        prompt=(
            "Add lightweight performance tracing for key workflows (open views, exports, imports)."
            " Persist traces to logs and provide a small viewer panel. Keep module separation strict."
        ),
    ),
)


def get_proposals(limit: int = 5) -> list[ImprovementProposal]:
    return list(PROPOSALS[: max(1, limit)])
