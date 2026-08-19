// Surface publique de la feature `analyse`.
// Tout ce qui doit être visible depuis `app/` ou une autre feature passe par
// ce fichier — jamais d'import direct dans un sous-dossier interne.

export { useSuiviAnalyse } from "./use-suivi-analyse";
export type { SuiviAnalyse } from "./use-suivi-analyse";
