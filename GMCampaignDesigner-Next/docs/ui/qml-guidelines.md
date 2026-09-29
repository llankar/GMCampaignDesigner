# Règles QML

QML reste déclaratif : composition, liaisons et états visuels. Il ne fait ni SQL, ni accès fichier, ni logique métier. Les modèles C++ exposent rôles stables, propriétés notifiables, signaux et commandes; les delegates restent légers et les listes virtualisées.

## Relations

Les calculs cartographiques lourds utilisent `QQuickItem` selon l’[architecture](../architecture/overview.md).
