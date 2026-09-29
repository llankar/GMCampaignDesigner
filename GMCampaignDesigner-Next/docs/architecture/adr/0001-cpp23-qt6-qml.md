# ADR : C++23, Qt 6 et QML

- Statut : Accepté
- Date : 2026-09-29

## Contexte

La réécriture doit être performante, testable et découplée de l’application Python historique, tout en gardant une présentation moderne.

## Décision

Utiliser C++23 pour le cœur et Qt 6/Qt Quick/QML/Controls 2 pour la présentation.

## Conséquences

Séparation forte, outillage natif et UI déclarative; Qt reste hors domaine et ses obligations de licence sont suivies.

Cette décision s’applique avec la [vue d’ensemble](../overview.md), les [frontières](../module-boundaries.md) et les [tests](../../development/testing-strategy.md).
