// Fichier serveur uniquement (Route Handlers sous `app/api/auth/`, J3, et
// Server Components qui font un appel API avant le premier rendu, K5 —
// jamais un composant client) : volontairement pas réexporté par
// `index.ts`, dont la surface publique reste client-safe (agents.md §4).
//
// URL depuis laquelle le serveur Next.js atteint l'API — distincte de
// `NEXT_PUBLIC_API_URL` (client.ts), qui est l'URL depuis laquelle le
// *navigateur* atteint l'API. En docker-compose, le nom de service `api`
// n'est résolvable qu'entre containers (.env.example). Vivait à l'origine
// dans `features/auth/` (premier appelant, J3) ; déplacé ici car ce n'est
// pas une connaissance propre à l'auth — n'importe quel appel serveur au
// backend en a besoin (agents.md §1 DRY : une seule source de vérité).
export function requireInternalApiUrl(): string {
  const url = process.env.API_INTERNAL_URL;
  if (!url) {
    throw new Error(
      "API_INTERNAL_URL est manquant : impossible de contacter l'API backend depuis le serveur.",
    );
  }
  return url;
}
