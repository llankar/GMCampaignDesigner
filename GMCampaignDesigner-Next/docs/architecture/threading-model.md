# Modèle de threading

Le thread UI traite entrée, propriétés et rendu seulement. Un ordonnanceur applicatif lance les travaux longs sur workers annulables avec état de progression. Les résultats immuables reviennent par connexions queued; les objets ne changent pas d’affinité implicitement et SQLite utilise des connexions propres au worker.

## Relations

Les budgets et erreurs suivent [performance](performance-budget.md) et [error handling](error-handling.md).
