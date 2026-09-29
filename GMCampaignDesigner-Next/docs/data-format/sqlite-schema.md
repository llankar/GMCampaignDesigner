# Schéma SQLite

Les tables utilisent clés stables, contraintes de référence explicites et index justifiés par requêtes mesurées. Les écritures applicatives sont transactionnelles; les migrations modifient `user_version` uniquement après validation. Les blobs volumineux restent dans le stockage média.

## Relations

Évolution dans [schema versioning](schema-versioning.md); accès limité à [infrastructure](../architecture/overview.md).
