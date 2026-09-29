# ADR : Persistance SQLite

- Statut : Accepté
- Date : 2026-09-29

## Contexte

La réécriture doit être performante, testable et découplée de l’application Python historique, tout en gardant une présentation moderne.

## Décision

Implémenter SQLite uniquement sous infrastructure/sqlite derrière les ports applicatifs.

## Conséquences

Transactions locales robustes; connexions par worker, migrations versionnées et tests d’intégration obligatoires.

Cette décision s’applique avec la [vue d’ensemble](../overview.md), les [frontières](../module-boundaries.md) et les [tests](../../development/testing-strategy.md).
