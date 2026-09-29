# Sécurité des mises à jour

Le client vérifie manifeste et artefact signés avec clé embarquée et rotation contrôlée, impose TLS, refuse versions rétrogrades non autorisées et vérifie plateforme/canal. Installation et remplacement sont atomiques avec récupération de la version précédente; aucune réponse réseau non signée ne commande l’exécution.

## Relations

Le packaging suit [release process](../releases/release-process.md).
