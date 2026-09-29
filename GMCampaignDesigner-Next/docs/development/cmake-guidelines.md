# Règles CMake

Employer des cibles modernes, propriétés `PRIVATE/PUBLIC/INTERFACE`, alias namespacés et sous-répertoires par module. Ne pas utiliser de flags globaux ni de glob pour les sources; pinner les dépendances et exporter les commandes de compilation. Les presets Debug et Release sont l’interface commune CI/développeur.

## Relations

Voir [getting started](getting-started.md) et [tests](testing-strategy.md).
