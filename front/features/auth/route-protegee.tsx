"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Spinner } from "@/shared/ui";
import { useAuth } from "./auth-provider";

// Garde de route côté client (J4, backlog.md). Volontairement PAS un
// `proxy.ts` (ex-`middleware.ts`, renommé en Next 16) : ce fichier tournerait
// côté edge, sur la requête HTTP brute — or le seul cookie de session
// (`refresh_token`, cookie.ts) est httpOnly ET scopé à `path: "/api/auth"`
// (J3). Le navigateur n'envoie donc CE cookie que sur une requête vers
// `/api/auth/*` ; sur une requête vers `/compte` ou `/historique`, il est
// absent, et un proxy ne pourrait rien y lire — élargir son path casserait
// le moindre privilège déjà décidé en J3 pour un gain cosmétique. La seule
// source de vérité disponible ici est `status` d'`AuthProvider`, qui vit en
// mémoire JS.
//
// Ceci reste un contrôle UX, pas une frontière de sécurité (agents.md §7 :
// « le client n'est jamais l'autorité »). La vraie protection est déjà en
// place côté back (`get_current_user`, C7) sur chaque endpoint concerné
// (H3, `/historique` et `/compte`) : même si ce composant était contourné
// ou son JS désactivé, aucune donnée ne fuiterait.
export function RouteProtegee({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // `replace`, pas `push` : une page protégée ne doit pas rester dans
    // l'historique de navigation après une redirection vers /connexion —
    // sinon le bouton "précédent" ramène sur un écran qui se re-redirige
    // aussitôt.
    if (status === "anonymous") {
      router.replace("/connexion");
    }
  }, [status, router]);

  // "loading" : le rafraîchissement silencieux initial (J3) n'a pas encore
  // tranché. "anonymous" : la redirection ci-dessus vient d'être déclenchée
  // mais la navigation n'a pas encore eu lieu. Dans les deux cas, on
  // n'affiche jamais le contenu protégé — jamais sur la seule absence
  // d'`accessToken`, qui vaut aussi `null` pendant "loading" (auth-provider.tsx).
  if (status !== "authenticated") {
    return (
      <div className="flex flex-1 items-center justify-center py-24">
        <Spinner size="lg" label="Vérification de la session…" />
      </div>
    );
  }

  return <>{children}</>;
}
