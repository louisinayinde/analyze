# Modules

Un module ne s'importe que via son `index.py` — jamais en important un fichier
interne (`domaine/`, `application/`, `ports/`, `adaptateurs/`). Contourner
l'index d'un module est un smell (voir agents.md §4).
