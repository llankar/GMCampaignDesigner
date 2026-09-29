# Stratégie de test

La pyramide et les portes de livraison comprennent obligatoirement :

1. **Tests unitaires du domaine**, rapides, déterministes et sans Qt/SQLite.
2. **Tests des services applicatifs** avec ports simulés, annulation et erreurs.
3. **Tests d’intégration SQLite** sur bases temporaires, contraintes et transactions.
4. **Tests des migrations** depuis chaque version prise en charge, y compris échec et rollback.
5. **Tests des modèles exposés à QML**, rôles, signaux et mises à jour incrémentales.
6. **Tests QML** des composants, navigation clavier, états vide/chargement/erreur.
7. **Tests de lancement** et de composition sur chaque plateforme cible.
8. **Tests de performance** en Release selon les percentiles et jeux de tailles définis.
9. **Tests de packaging** : installation propre, dépendances, désinstallation, signature et mise à niveau.
10. **Tests sur campagnes anonymisées**, synthétiques ou assainies, sans donnée réelle identifiable.

Les tests écrivent uniquement dans des répertoires temporaires isolés et sont reproductibles en CI. Une correction de bug commence par un test qui reproduit le défaut. Les résultats Release suivent le [budget de performance](../architecture/performance-budget.md); migrations et sécurité suivent la [stratégie de migration](../migration/migration-strategy.md) et le [modèle de menace](../security/threat-model.md).
