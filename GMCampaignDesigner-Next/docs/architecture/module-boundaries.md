# Frontières des modules

Le domaine ne dépend de rien d’externe. Application dépend du domaine; infrastructure implémente ses ports; présentation dépend de contrats applicatifs; app assemble. Les échanges sont des types métier ou DTO explicites, jamais des handles SQLite ou objets QML traversant les couches.

## Relations

Les exceptions exigent un ADR; voir la [vue d’ensemble](overview.md) et l’[ADR des couches](adr/0002-layered-architecture.md).
