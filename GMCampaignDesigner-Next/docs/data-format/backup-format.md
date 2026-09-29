# Format de sauvegarde

Une sauvegarde est une archive immuable avec manifeste versionné, empreintes, base cohérente et médias référencés. La création utilise snapshot/transaction puis publication atomique. La restauration s’effectue vers un nouvel emplacement après validation et ne remplace jamais silencieusement une campagne.

## Relations

Voir [campaign format](campaign-format.md) et [rollback](../migration/rollback-strategy.md).
