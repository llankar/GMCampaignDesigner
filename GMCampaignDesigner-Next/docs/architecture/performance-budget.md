# Budget de performance

## Objectifs mesurables

- Maintenir **60 FPS** pendant les interactions graphiques, soit un budget maximal de **16,7 ms par image** pour mise à jour, synchronisation et rendu.
- N’exécuter **aucune opération bloquante sur le thread UI**.
- Fournir un retour visuel en moins de **100 ms** pour une action courante; l’achèvement peut être asynchrone et afficher sa progression.
- Ouvrir progressivement les campagnes volumineuses : métadonnées et vue active d’abord, contenu secondaire ensuite.
- Charger portraits et miniatures de manière asynchrone avec cache borné et annulation lorsque l’élément quitte la vue.

## Mesure

Chaque métrique de latence publie les **50e, 95e et 99e percentiles** ainsi que taille d’échantillon, matériel, OS, version et configuration Release. Les régressions sont comparées à une base versionnée; moyenne seule et mesure Debug ne permettent pas une décision.

Les benchmarks couvrent des campagnes anonymisées **petites**, **moyennes** et **grandes**, avec volumes documentés d’entités, relations, cartes et médias. Ils mesurent démarrage, ouverture progressive, recherche, défilement, rendu cartographique, sauvegarde et migration. Voir [benchmarking](../development/benchmarking.md), [threading](threading-model.md) et [tests](../development/testing-strategy.md).
