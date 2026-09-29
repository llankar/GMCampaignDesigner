# Règles de validation

Avant et après migration sont vérifiés intégrité SQLite, clés étrangères, identifiants, cardinalités, encodage, chemins confinés, présence et empreinte des médias. Les écarts sont classés bloquants, récupérables ou informatifs et consignés sans contenu sensible.

## Relations

Les échecs suivent [rollback](rollback-strategy.md).
