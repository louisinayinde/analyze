# Shared

Ce qui est réellement transverse aux features (`analyse/`, `auth/`,
`historique/`) : design system, helpers génériques, types partagés, client
API généré.

Ce dossier ne contient **aucune règle métier** (agents.md §4). Dès qu'un
utilitaire « partagé » porte de la logique propre à un domaine, il migre
dans la feature correspondante plutôt que de rester ici.
