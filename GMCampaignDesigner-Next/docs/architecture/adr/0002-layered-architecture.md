# ADR : Architecture en couches

- Statut : Accepté
- Date : 2026-09-29

## Contexte

La réécriture doit être performante, testable et découplée de l’application Python historique, tout en gardant une présentation moderne.

## Décision

Adopter domain, application, infrastructure, map_engine, presentation et app avec dépendances vers l’intérieur.

## Conséquences

Testabilité accrue; adaptateurs et composition explicites ajoutent du code mais empêchent le couplage UI/SQL.

Cette décision s’applique avec la [vue d’ensemble](../overview.md), les [frontières](../module-boundaries.md) et les [tests](../../development/testing-strategy.md).
