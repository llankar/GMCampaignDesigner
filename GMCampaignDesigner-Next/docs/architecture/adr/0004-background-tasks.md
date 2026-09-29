# ADR : Tâches en arrière-plan

- Statut : Accepté
- Date : 2026-09-29

## Contexte

La réécriture doit être performante, testable et découplée de l’application Python historique, tout en gardant une présentation moderne.

## Décision

Exécuter I/O et calculs longs dans des workers annulables, avec progression et résultats renvoyés au thread UI.

## Conséquences

Interface réactive; il faut gérer durée de vie, annulation, erreurs et affinité explicitement.

Cette décision s’applique avec la [vue d’ensemble](../overview.md), les [frontières](../module-boundaries.md) et les [tests](../../development/testing-strategy.md).
