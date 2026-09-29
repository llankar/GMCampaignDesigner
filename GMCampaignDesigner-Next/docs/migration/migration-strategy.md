# Stratégie de migration

## Invariants de sécurité

L’ancienne base est toujours ouverte **en lecture seule**. Toute migration travaille exclusivement sur **une copie** créée dans une zone temporaire contrôlée; ni l’original ni sa sauvegarde ne sont modifiés. L’espace disponible et les permissions sont vérifiés avant la copie.

## Pipeline

1. Identifier le format et la version de schéma source; refuser une version inconnue sans modifier de fichier.
2. Créer une sauvegarde vérifiable de l’original, puis copier la base et les médias avec chemins normalisés.
3. Exécuter un contrôle d’intégrité avant migration sur la copie; arrêter et produire un diagnostic en cas d’échec.
4. Appliquer des étapes transactionnelles, ordonnées et idempotentes, en enregistrant la version de schéma cible.
5. Valider comptes, références, médias et contraintes, puis exécuter un contrôle d’intégrité après migration.
6. Produire un rapport de migration sans secret : versions, étapes, avertissements, rejets, durées et empreintes utiles.
7. Publier atomiquement le résultat seulement après validation; conserver sauvegarde et rapport selon la politique de rétention.

En cas d’échec ou d’annulation, supprimer la copie partielle de la zone de travail et suivre la [procédure de rollback](rollback-strategy.md); l’utilisateur peut toujours rouvrir l’original inchangé. Voir aussi la [compatibilité historique](legacy-compatibility.md), les [règles de validation](validation-rules.md), le [versionnage du schéma](../data-format/schema-versioning.md) et les [tests de migration](../development/testing-strategy.md).
