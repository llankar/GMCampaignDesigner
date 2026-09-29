# Instructions aux agents

Ces règles s’appliquent à tout ce dépôt.

- Le dépôt C++ **GMCampaignDesigner Next est le seul dépôt modifiable**. Le dépôt Python historique est une référence en lecture seule : ne jamais y écrire, reformater, migrer en place ni y committer.
- Tout nouveau module utilise des sous-répertoires et des fichiers séparés, avec une responsabilité identifiable par fichier.
- Aucun fichier monolithique ne doit regrouper interface utilisateur, SQL et logique métier.
- Aucun secret, jeton, chemin local propre à une machine ou donnée de campagne réelle ne doit être versionné.
- Toute modification doit comporter les tests correspondants au niveau approprié de la [stratégie de test](docs/development/testing-strategy.md).
- Les chemins critiques en performances doivent être mesurés en configuration **Release**, selon le [budget de performance](docs/architecture/performance-budget.md).
- Les dépendances respectent les frontières décrites dans l’[architecture](docs/architecture/overview.md); le domaine reste indépendant de Qt, SQLite et QML.
- Les changements de format persistant nécessitent une version de schéma, un test de migration et une procédure de retour arrière.
