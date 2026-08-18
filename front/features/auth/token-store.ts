// Le seul endroit où l'access token vit côté client (J3, backlog.md) : une
// variable de module, jamais `localStorage`/`sessionStorage` (projets.md —
// surface XSS explicitement écartée). Perdue à chaque rechargement de page
// par construction ; `AuthProvider` la reconstitue au montage via un
// rafraîchissement silencieux contre le cookie httpOnly (app/api/auth/refresh).
//
// Store externe minimal (pas de contexte React ici) pour que n'importe quel
// code non-React puisse lire le jeton courant sans dépendre du montage d'un
// provider ; `AuthProvider` s'y abonne via `useSyncExternalStore`.

type Ecouteur = () => void;

let jetonAcces: string | null = null;
const ecouteurs = new Set<Ecouteur>();

export function getAccessToken(): string | null {
  return jetonAcces;
}

export function setAccessToken(jeton: string | null): void {
  jetonAcces = jeton;
  ecouteurs.forEach((ecouteur) => ecouteur());
}

export function subscribe(ecouteur: Ecouteur): () => void {
  ecouteurs.add(ecouteur);
  return () => ecouteurs.delete(ecouteur);
}
