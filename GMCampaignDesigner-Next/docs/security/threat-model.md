# Modèle de menace

## Actifs et frontières

Les campagnes, médias, secrets d’API, identité des joueurs, paquets de mise à jour et processus locaux sont sensibles. Toute entrée issue d’une archive, d’un média, du réseau, d’un plugin ou du sidecar IA est non fiable.

## Menaces et mesures

- **Bases et archives malveillantes** : limites de taille, validation de schéma, décompression bornée et traitement dans une zone temporaire.
- **Traversées de chemins** : canonicalisation, rejet des chemins absolus et de `..`, extraction confinée sous une racine dédiée.
- **Mises à jour compromises** : manifeste signé, vérification cryptographique, canal TLS, anti-downgrade et rollback sûr.
- **Serveurs locaux exposés** : écoute sur loopback par défaut, ports explicites, CORS restrictif, arrêt avec l’application et aucune découverte publique implicite.
- **Authentification des vues joueur** : jetons courts, révocables et à portée limitée; séparation stricte des informations maître/joueur.
- **Secrets GitHub/API** : coffre du système ou CI, privilège minimal, rotation et rédaction des journaux.
- **Plugins ou processus IA** : protocole borné, permissions minimales, délais, annulation, validation de sortie; Python reste un processus secondaire isolé.
- **Médias non fiables** : type détecté par contenu, limites de dimensions/durée, décodeurs à jour et miniatures isolées.
- **Migrations de campagnes** : source en lecture seule, copie de travail, intégrité avant/après et publication atomique.

Les abus sont testés avec corpus synthétiques non sensibles. Consulter [services réseau](network-services.md), [secrets](secrets-management.md), [mises à jour](update-security.md) et [migration](../migration/migration-strategy.md).
