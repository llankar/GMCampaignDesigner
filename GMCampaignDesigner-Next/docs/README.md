# Documentation de GMCampaignDesigner Next

Cet index est la porte d’entrée normative. Les décisions détaillées dans les ADR complètent l’[architecture générale](architecture/overview.md).

## Produit
- [Vision](vision/product-vision.md), [périmètre](vision/scope.md), [personas](vision/personas.md), [critères de succès](vision/success-criteria.md)

## Architecture
- [Vue d’ensemble](architecture/overview.md), [frontières](architecture/module-boundaries.md), [threads](architecture/threading-model.md), [budget de performance](architecture/performance-budget.md)
- [Gestion d’erreurs](architecture/error-handling.md), [journalisation](architecture/logging.md)
- Décisions : [C++23, Qt 6 et QML](architecture/adr/0001-cpp23-qt6-qml.md), [architecture en couches](architecture/adr/0002-layered-architecture.md), [persistance SQLite](architecture/adr/0003-sqlite-persistence.md), [tâches en arrière-plan](architecture/adr/0004-background-tasks.md), [processus secondaire Python pour l’IA](architecture/adr/0005-python-ai-sidecar.md)

## Expérience, données et migration
- [Design system](ui/design-system.md), [espace de travail](ui/workspace-layout.md), [navigation](ui/navigation.md), [accessibilité](ui/accessibility.md), [règles QML](ui/qml-guidelines.md)
- [Format de campagne](data-format/campaign-format.md), [schéma SQLite](data-format/sqlite-schema.md), [médias](data-format/media-layout.md), [versions](data-format/schema-versioning.md), [sauvegardes](data-format/backup-format.md)
- [Stratégie de migration](migration/migration-strategy.md), [compatibilité](migration/legacy-compatibility.md), [validation](migration/validation-rules.md), [rollback](migration/rollback-strategy.md)

## Ingénierie, sécurité et livraison
- [Démarrage](development/getting-started.md), [structure](development/repository-structure.md), [standards](development/coding-standards.md), [CMake](development/cmake-guidelines.md), [tests](development/testing-strategy.md), [benchmarks](development/benchmarking.md), [contribution](development/contribution-workflow.md)
- [Menaces](security/threat-model.md), [secrets](security/secrets-management.md), [services réseau](security/network-services.md), [mises à jour](security/update-security.md)
- [Versionnage](releases/versioning.md), [packaging Windows](releases/packaging-windows.md), [publication](releases/release-process.md), [retour arrière](releases/rollback.md)
- [Licence Qt](legal/qt-licensing.md), [dépendances](legal/third-party-dependencies.md), [assets](legal/asset-licensing.md)
