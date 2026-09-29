# Stratégie de rollback

Tant que le résultat n’est pas validé, seule la copie temporaire change. Un échec ferme les handles, conserve un rapport expurgé et retire les artefacts partiels. Après publication atomique, revenir signifie restaurer la sauvegarde vers un nouvel emplacement puis revalider; l’original historique reste intact.

## Relations

Voir [migration strategy](migration-strategy.md) et [backup format](../data-format/backup-format.md).
