# Gestion des erreurs

Le domaine retourne des erreurs typées; les adaptateurs ajoutent contexte sans exposer secrets ni détails SQL. L’application traduit en actions récupérables, tandis que QML affiche un message localisé et conserve les détails corrélés pour le diagnostic. Annulation n’est pas un échec.

## Relations

La journalisation suit [logging](logging.md) et les transactions la [stratégie de rollback](../migration/rollback-strategy.md).
