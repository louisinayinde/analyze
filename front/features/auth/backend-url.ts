// Fichier serveur uniquement (utilisé par les Route Handlers sous
// `app/api/auth/`, jamais par un composant client) : n'est volontairement
// pas réexporté par `index.ts` (agents.md §4 — la surface publique de la
// feature reste client-safe, voir `auth-provider.tsx`).
//
// URL depuis laquelle le serveur Next.js atteint l'API — distincte de
// `NEXT_PUBLIC_API_URL` (shared/api/client.ts), qui est l'URL depuis
// laquelle le *navigateur* atteint l'API. En docker-compose, le nom de
// service `api` n'est résolvable qu'entre containers (.env.example).
export function requireInternalApiUrl(): string {
  const url = process.env.API_INTERNAL_URL;
  if (!url) {
    throw new Error(
      "API_INTERNAL_URL est manquant : impossible de contacter l'API backend depuis le serveur.",
    );
  }
  return url;
}
