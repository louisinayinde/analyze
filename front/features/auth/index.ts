// Surface publique de la feature `auth`.
// Tout ce qui doit être visible depuis `app/` ou une autre feature passe par
// ce fichier — jamais d'import direct dans un sous-dossier interne.
//
// `cookie.ts` et `backend-url.ts` en sont volontairement absents : fichiers
// serveur uniquement (`next/headers`), consommés seulement par les Route
// Handlers sous `app/api/auth/` — les réexporter ici risquerait de faire
// entrer du code serveur dans le bundle client via ce même barrel (agents.md
// §4 : la frontière suit la contrainte réelle, pas la commodité).
export { AuthProvider, useAuth } from "./auth-provider";
export { RouteProtegee } from "./route-protegee";
