"use client";

import { RouteProtegee } from "@/features/auth";
import { ListeHistorique } from "@/features/historique";

// Page protégée (K6, backlog.md — dépend de J4) : contrairement à
// `/analyse/[id]` (K4, publique par nature), l'historique est propre à
// l'utilisateur connecté. `RouteProtegee` gère l'UX de redirection ; la
// vraie frontière de sécurité est déjà côté back sur `GET /historique`
// (`get_current_user`, H3, agents.md §7).
export default function HistoriquePage() {
  return (
    <RouteProtegee>
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-12">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-foreground">Mon historique</h1>
          <p className="text-sm text-muted-foreground">
            Retrouve toutes tes analyses précédentes.
          </p>
        </div>
        <ListeHistorique />
      </div>
    </RouteProtegee>
  );
}
