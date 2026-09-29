# ADR : Processus secondaire Python pour l’IA

- Statut : Accepté
- Date : 2026-09-29

## Contexte

La réécriture doit être performante, testable et découplée de l’application Python historique, tout en gardant une présentation moderne.

## Décision

Conserver Python uniquement comme sidecar isolé pour les traitements IA qui le nécessitent.

## Conséquences

Le cœur reste C++ déployable; protocole versionné, délais, annulation et validation limitent la confiance accordée au processus.

Cette décision s’applique avec la [vue d’ensemble](../overview.md), les [frontières](../module-boundaries.md) et les [tests](../../development/testing-strategy.md).
