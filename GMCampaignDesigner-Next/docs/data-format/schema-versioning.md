# Versionnement du schéma

Chaque changement persistant incrémente une version entière, fournit migration montante, validation, test depuis toutes versions supportées et stratégie de rollback. Une version inconnue ou future est refusée en lecture-écriture et peut être inspectée sans mutation.

## Relations

La procédure complète est dans [migration](../migration/migration-strategy.md).
