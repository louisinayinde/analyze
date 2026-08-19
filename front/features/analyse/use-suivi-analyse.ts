"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError, unwrap } from "@/shared/api";
import type { components } from "@/shared/api";

type AnalyseTerminee = components["schemas"]["AnalyseTermineeReponse"];

// 1,5 s : au milieu de la fourchette « 1-2 s » du ticket (K3, backlog.md).
const INTERVALLE_POLLING_MS = 1500;
// Un poll qui échoue (blip réseau) ne doit pas arrêter le suivi tout de
// suite — seule une série d'échecs consécutifs signale un vrai problème
// (agents.md §3 : coder pour l'échec, mais sans abandonner au premier accroc).
const TENTATIVES_ERREUR_MAX = 3;

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

// Suivi léger du statut d'une analyse en cours (K3, backlog.md) : poll
// `GET /analyses/{id}/statut` à intervalle fixe tant que le statut reste
// `pending`, s'arrête proprement sur `done`/`failed`.
//
// `setTimeout` récursif plutôt que `setInterval` : un poll ne se replanifie
// qu'une fois le précédent terminé, donc jamais deux requêtes en vol en
// parallèle si le réseau ralentit — même motif que `planifierRafraichissement`
// (features/auth/auth-provider.tsx, J3).
export function useSuiviAnalyse(analyseId: string | undefined): SuiviAnalyse {
  const [suivi, setSuivi] = useState<SuiviAnalyse>({ statut: "en_cours" });
  const minuteurRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const monteRef = useRef(true);

  // Réinitialise le suivi quand `analyseId` change (nouvelle soumission
  // après un échec, cf. `reprendreLeFormulaire` côté `app/page.tsx`) —
  // ajustement d'état pendant le rendu plutôt que dans un effet
  // (react-hooks/set-state-in-effect), pour ne pas déclencher un rendu
  // intermédiaire avec l'ancien statut avant que le nouveau poll ne parte.
  const [analyseIdSuivi, setAnalyseIdSuivi] = useState(analyseId);
  if (analyseId !== analyseIdSuivi) {
    setAnalyseIdSuivi(analyseId);
    setSuivi({ statut: "en_cours" });
  }

  useEffect(() => {
    monteRef.current = true;
    return () => {
      monteRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!analyseId) return;

    let tentativesErreur = 0;

    async function pollerUneFois() {
      try {
        const resultat = await unwrap(
          apiClient.GET("/analyses/{analyse_id}/statut", {
            params: { path: { analyse_id: analyseId as string } },
          }),
        );
        tentativesErreur = 0;
        if (!monteRef.current) return;

        if (resultat.statut === "pending") {
          minuteurRef.current = setTimeout(pollerUneFois, INTERVALLE_POLLING_MS);
          return;
        }
        setSuivi(
          resultat.statut === "done"
            ? { statut: "terminee", analyse: resultat }
            : { statut: "echec" },
        );
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          if (!monteRef.current) return;
          setSuivi({ statut: "introuvable" });
          return;
        }
        tentativesErreur += 1;
        if (!monteRef.current) return;
        if (tentativesErreur >= TENTATIVES_ERREUR_MAX) {
          setSuivi({ statut: "erreur" });
          return;
        }
        minuteurRef.current = setTimeout(pollerUneFois, INTERVALLE_POLLING_MS);
      }
    }

    pollerUneFois();
    return () => {
      if (minuteurRef.current) clearTimeout(minuteurRef.current);
    };
  }, [analyseId]);

  return suivi;
}
