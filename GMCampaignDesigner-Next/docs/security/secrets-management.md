# Gestion des secrets

Les jetons résident dans le coffre du système ou le gestionnaire de secrets CI, jamais dans Git, logs, campagnes ou presets. Les droits sont minimaux, les environnements séparés et la rotation documentée. Une détection automatisée bloque les commits; une fuite déclenche révocation avant nettoyage.

## Relations

Voir [threat model](threat-model.md) et [logging](../architecture/logging.md).
