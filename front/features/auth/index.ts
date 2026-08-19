// Surface publique de la feature `auth`.
// Tout ce qui doit être visible depuis `app/` ou une autre feature passe par
// ce fichier — jamais d'import direct dans un sous-dossier interne.
//
// `cookie.ts` en est volontairement absent : fichier serveur uniquement
// (`next/headers`), consommé seulement par les Route Handlers sous
// `app/api/auth/` — le réexporter ici risquerait de faire entrer du code
// serveur dans le bundle client via ce même barrel (agents.md §4 : la
// frontière suit la contrainte réelle, pas la commodité). Même raisonnement
// pour `requireInternalApiUrl` (`shared/api/internal-url.ts`, K5).
export { AuthProvider, useAuth } from "./auth-provider";
export { RouteProtegee } from "./route-protegee";
