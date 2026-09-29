# Vue d’ensemble de l’architecture

## Couches imposées

```text
src/
├── domain/
├── application/
├── infrastructure/
│   ├── sqlite/
│   ├── media/
│   ├── networking/
│   └── ai/
├── map_engine/
├── presentation/
│   ├── qml/
│   ├── models/
│   └── components/
└── app/
```

Le **domaine** exprime les entités, règles et ports en C++23 sans dépendance vers Qt, SQLite ou QML. L’**application** orchestre les cas d’usage et dépend du domaine. L’**infrastructure** implémente persistance SQLite, fichiers/médias, réseau et adaptateur IA. `map_engine` porte le rendu cartographique intensif. `presentation` adapte les cas d’usage à Qt Quick; `app` compose les dépendances et le cycle de vie.

## Règles normatives

- C++23 est utilisé pour domaine, services, persistance et traitements; Qt 6, Qt Quick, QML et Qt Quick Controls 2 servent la présentation.
- QML ne contient aucune requête SQLite, opération fichier ou logique métier.
- Le thread principal est réservé aux interactions et au rendu; les tâches longues s’exécutent dans des workers annulables.
- La communication avec QML passe par propriétés, signaux, commandes et `QAbstractItemModel`.
- Les listes sont virtualisées et leurs modèles mis à jour de façon incrémentale.
- Les composants cartographiques intensifs sont implémentés en C++ avec `QQuickItem`.
- Python est conservé uniquement comme processus secondaire isolé pour les traitements IA qui l’exigent; il n’est ni runtime métier ni couche UI.

Les dépendances pointent vers l’intérieur et transitent par des interfaces. Voir les [frontières](module-boundaries.md), le [modèle de threading](threading-model.md), le [budget](performance-budget.md) et les ADR [technologie](adr/0001-cpp23-qt6-qml.md), [couches](adr/0002-layered-architecture.md), [SQLite](adr/0003-sqlite-persistence.md), [workers](adr/0004-background-tasks.md), [IA Python](adr/0005-python-ai-sidecar.md).
