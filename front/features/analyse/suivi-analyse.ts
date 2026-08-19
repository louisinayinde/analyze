import type { components } from "@/shared/api";

type AnalyseTerminee = components["schemas"]["AnalyseTermineeReponse"];

export type SuiviAnalyse =
  | { statut: "en_cours" }
  | { statut: "terminee"; analyse: AnalyseTerminee }
  // `statut: "failed"` renvoyé par le back (job de génération en échec, E4).
  | { statut: "echec" }
  // Le poll lui-même n'a pas abouti après plusieurs tentatives (réseau,
  // timeout) — distinct de l'échec métier ci-dessus pour un message adapté.
  | { statut: "erreur" }
  // 404 : aucune analyse pour cet id (K4, lien partagé invalide/périmé).
  // Définitif — contrairement à `erreur`, retenter n'y changera rien, donc
  // pas de décompte de tentatives avant de s'arrêter.
  | { statut: "introuvable" };

// Traduit une réponse `GET /analyses/{id}/statut` en `SuiviAnalyse` — utilisé
// à la fois côté serveur (page.tsx, K5 : premier rendu déjà résolu, sans
// passer par le polling) et côté client (`use-suivi-analyse.ts`, à chaque
// poll). Une seule source de vérité pour ce mapping (agents.md §1 DRY) : le
// dupliquer aurait fait diverger silencieusement l'état initial
// server-rendered de l'état obtenu après un poll.
//
// Vit dans son propre fichier, séparé de `use-suivi-analyse.ts` : ce
// dernier est marqué `"use client"`, ce qui rendrait cette fonction pure
// inutilisable depuis un Server Component (Next.js interdit d'appeler
// directement une fonction exportée par un module client) alors qu'elle n'a
// elle-même aucune dépendance client.
export function statutVersSuivi(resultat: AnalyseTerminee): SuiviAnalyse {
  if (resultat.statut === "pending") return { statut: "en_cours" };
  if (resultat.statut === "failed") return { statut: "echec" };
  return { statut: "terminee", analyse: resultat };
}
