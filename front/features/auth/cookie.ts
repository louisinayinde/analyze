// Fichier serveur uniquement, mêmes raisons que `shared/api/internal-url.ts`
// : jamais réexporté par `index.ts`, importé uniquement par les Route
// Handlers sous `app/api/auth/`.

export const REFRESH_COOKIE_NAME = "refresh_token";

// Un cookie est identifié par nom + path (+ domaine) : `path: "/"` par
// défaut de `.cookies.delete(nom)` ne correspond pas à `refreshCookieOptions()`
// ci-dessous, donc n'efface rien du navigateur — juste un cookie sans
// rapport à path "/". Toujours effacer via
// `.cookies.delete({ name: REFRESH_COOKIE_NAME, path: REFRESH_COOKIE_PATH })`.
export const REFRESH_COOKIE_PATH = "/api/auth";

// Aligné sur le défaut backend `jwt_refresh_token_expire_days = 30`
// (back/src/shared/config.py) : housekeeping côté navigateur seulement — la
// seule autorité réelle sur la validité d'un refresh token reste le back
// (C6, agents.md §7), qui rejette de toute façon un jeton expiré ou révoqué
// même si ce cookie traînait plus longtemps que prévu.
const REFRESH_COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60;

// httpOnly : inaccessible en JS, seule vraie protection contre le vol par
// XSS (projets.md, C6). secure : jamais transmis en clair (désactivé en dev
// local pour fonctionner sur http://localhost). sameSite=strict : jamais
// envoyé sur une requête cross-site (projets.md). path restreint aux routes
// d'auth : ce cookie n'a rien à faire sur une requête vers une page ou un
// asset, moindre privilège (agents.md §7).
export function refreshCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV !== "development",
    sameSite: "strict" as const,
    path: REFRESH_COOKIE_PATH,
    maxAge: REFRESH_COOKIE_MAX_AGE_SECONDS,
  };
}
