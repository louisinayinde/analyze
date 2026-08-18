"use client";

import { useCallback } from "react";
import { useToast } from "@/shared/ui";
import { ApiError, ApiNetworkError, ApiTimeoutError } from "./errors";
import { unwrap } from "./client";

// Convertit une erreur normalisée (client.ts) en toast : un seul endroit
// décide du titre/variant affiché pour chaque famille d'erreur, pour que
// deux écrans qui appellent l'API n'inventent pas chacun leur propre
// libellé (agents.md §1, DRY — même connaissance, un seul endroit).
function afficherErreur(toast: ReturnType<typeof useToast>["toast"], error: unknown): void {
  if (error instanceof ApiTimeoutError) {
    toast({ title: "Délai dépassé", description: error.message, variant: "warning" });
    return;
  }
  if (error instanceof ApiNetworkError) {
    toast({ title: "Connexion impossible", description: error.message, variant: "destructive" });
    return;
  }
  if (error instanceof ApiError) {
    toast({ title: "Erreur", description: error.message, variant: "destructive" });
    return;
  }
  toast({
    title: "Erreur inattendue",
    description: "Réessaie dans quelques instants.",
    variant: "destructive",
  });
}

// Point d'entrée recommandé pour appeler l'API depuis un composant (I5,
// backlog.md) : combine `unwrap` (client.ts) et l'affichage du toast, pour
// qu'un écran n'ait jamais à réécrire son propre traitement d'erreur
// réseau/timeout. L'erreur est aussi re-levée après le toast, pour que
// l'appelant puisse encore réagir localement (ex. sortir d'un état de
// chargement) sans dupliquer l'affichage.
export function useApiRequest() {
  const { toast } = useToast();

  return useCallback(
    async <T>(call: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> => {
      try {
        return await unwrap(call);
      } catch (error) {
        afficherErreur(toast, error);
        throw error;
      }
    },
    [toast],
  );
}
