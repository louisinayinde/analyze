import type { Metadata } from "next";
import { headers } from "next/headers";
import { cache } from "react";
import { ResultatAnalyse, statutVersSuivi } from "@/features/analyse";
import type { SuiviAnalyse } from "@/features/analyse";
import type { components } from "@/shared/api";
import { requireInternalApiUrl } from "@/shared/api/internal-url";

type AnalyseTerminee = components["schemas"]["AnalyseTermineeReponse"];

// Page publique — pas de `RouteProtegee` (K4, backlog.md) : le résultat est
// justement fait pour être ouvert par n'importe qui via un lien partagé,
// authentifié ou non. Cohérent avec `GET /analyses/{id}/statut`, qui n'a
// aucune dépendance d'auth côté back (agents.md §7 : rien de sensible n'est
// exposé par ce endpoint).
//
// Server Component (K5, backlog.md) : résout le statut *avant* le premier
// rendu, plutôt que de systématiquement afficher un spinner client le temps
// d'un aller-retour réseau après hydratation. Dans le parcours normal
// (K2/K3), `/` ne redirige ici qu'une fois l'analyse `done` — donc la
// quasi-totalité des visites (lien partagé, retour arrière, actualisation)
// tombent sur une analyse déjà résolue, et peuvent recevoir le résultat
// complet (texte + image) dans le HTML initial. C'est le principal levier
// LCP disponible sur cette page, qui est souvent le point d'entrée d'un
// visiteur externe.
//
// 3 s de timeout, volontairement plus court que le timeout client
// (`DEFAULT_TIMEOUT_MS`, shared/api/client.ts) : un dépassement ici ne doit
// pas retarder l'affichage de la page, seulement lui faire manquer
// l'occasion d'un premier rendu déjà résolu. Toute issue autre que `200`/
// `404` retombe donc sur `en_cours`, jamais sur une erreur affichée
// directement — `ResultatAnalyse` reprend le suivi côté client (poll, avec
// ses propres retries) exactement comme si la page avait démarré sans
// donnée serveur.
// `cache()` (React) plutôt que de compter sur la mémoïsation automatique de
// `fetch` par Next : `generateMetadata` et le composant de page ci-dessous
// appellent tous les deux cette fonction pour le même `id` — sans ça, ce
// serait un appel réseau en double vers le backend à chaque visite.
const resoudreSuiviInitial = cache(async (id: string): Promise<SuiviAnalyse> => {
  try {
    const reponse = await fetch(`${requireInternalApiUrl()}/analyses/${id}/statut`, {
      signal: AbortSignal.timeout(3000),
    });

    if (reponse.status === 404) return { statut: "introuvable" };
    if (!reponse.ok) return { statut: "en_cours" };

    const resultat = (await reponse.json()) as AnalyseTerminee;
    return statutVersSuivi(resultat);
  } catch {
    return { statut: "en_cours" };
  }
});

async function resoudreUrlPartage(id: string): Promise<string> {
  const entetes = await headers();
  const hote = entetes.get("host");
  if (!hote) return "";
  const protocole = entetes.get("x-forwarded-proto") ?? "http";
  return `${protocole}://${hote}/analyse/${id}`;
}

export async function generateMetadata({ params }: PageProps<"/analyse/[id]">): Promise<Metadata> {
  const { id } = await params;
  const suivi = await resoudreSuiviInitial(id);

  const titre =
    suivi.statut === "introuvable"
      ? "Analyse introuvable"
      : suivi.statut === "echec"
        ? "Échec de l'analyse"
        : "Résultat de l'analyse";

  return { title: titre };
}

export default async function AnalysePage({ params }: PageProps<"/analyse/[id]">) {
  const { id } = await params;
  const [suiviInitial, urlPartage] = await Promise.all([
    resoudreSuiviInitial(id),
    resoudreUrlPartage(id),
  ]);

  return <ResultatAnalyse analyseId={id} suiviInitial={suiviInitial} urlPartage={urlPartage} />;
}
