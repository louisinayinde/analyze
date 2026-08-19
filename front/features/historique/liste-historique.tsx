"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/features/auth";
import { apiClient, useApiRequest } from "@/shared/api";
import type { components } from "@/shared/api";
import { Button, Card, CardContent, Skeleton } from "@/shared/ui";
import { EntreeHistoriqueCard } from "./entree-historique";

type HistoriquePage = components["schemas"]["HistoriquePageReponse"];

const SQUELETTES_AFFICHES = 5;

export function ListeHistorique() {
  // Monté uniquement une fois `RouteProtegee` (J4) satisfaite, donc
  // `accessToken` est déjà posé — même garantie que `app/compte/page.tsx`,
  // pas de course avec le rafraîchissement silencieux initial (J3).
  const { accessToken } = useAuth();
  const request = useApiRequest();

  const [page, setPage] = useState(1);
  const [donnees, setDonnees] = useState<HistoriquePage>();
  const [chargementEnCours, setChargementEnCours] = useState(true);

  useEffect(() => {
    let annule = false;

    async function charger() {
      setChargementEnCours(true);
      try {
        const resultat = await request(
          apiClient.GET("/historique", {
            params: { query: { page } },
            headers: { Authorization: `Bearer ${accessToken}` },
          }),
        );
        if (!annule) setDonnees(resultat);
      } finally {
        if (!annule) setChargementEnCours(false);
      }
    }

    charger();
    return () => {
      annule = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  if (chargementEnCours || !donnees) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: SQUELETTES_AFFICHES }).map((_, index) => (
          <Skeleton key={index} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (donnees.items.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
          <p className="text-sm text-muted-foreground">Aucune analyse pour l&apos;instant.</p>
        </CardContent>
      </Card>
    );
  }

  const dernierePage = Math.max(1, Math.ceil(donnees.total / donnees.page_size));

  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-col gap-3">
        {donnees.items.map((entree) => (
          <li key={entree.id}>
            <EntreeHistoriqueCard entree={entree} />
          </li>
        ))}
      </ul>

      {dernierePage > 1 && (
        <nav
          aria-label="Pagination de l'historique"
          className="flex items-center justify-between gap-4"
        >
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Précédent
          </Button>
          <p aria-live="polite" className="text-sm text-muted-foreground">
            Page {donnees.page} / {dernierePage}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page >= dernierePage}
            onClick={() => setPage((p) => p + 1)}
          >
            Suivant
          </Button>
        </nav>
      )}
    </div>
  );
}
