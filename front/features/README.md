# Features

Arborescence miroir de la logique métier, pas par type de fichier (agents.md
§4) : chaque dossier ici regroupe tout ce qui concerne **une** fonctionnalité
— composants, hooks, appels API — spécifique à ce domaine.

Un module ne s'importe que via son `index.ts` — jamais en important un
fichier interne. Contourner l'index d'une feature est un smell.

- `analyse/` — le parcours cœur du produit : soumission de texte, résultat
  partageable.
- `auth/` — inscription, connexion, gestion des tokens.
- `historique/` — historique personnel des analyses de l'utilisateur.

Le code réellement transverse, sans logique métier propre à l'une de ces
features, vit dans [`shared/`](../shared/README.md).
