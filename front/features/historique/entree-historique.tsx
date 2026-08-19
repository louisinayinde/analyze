import Link from "next/link";
import type { components } from "@/shared/api";

const FORMATTEUR_DATE = new Intl.DateTimeFormat("fr-FR", {
  dateStyle: "long",
  timeStyle: "short",
});

// Longueur au-delà de laquelle l'extrait est tronqué, pour garder une liste
// lisible d'un coup d'œil — le texte complet reste consultable en suivant le
// lien vers `/analyse/[id]`.
const EXTRAIT_LONGUEUR_MAX = 140;

function tronquer(texte: string): string {
  if (texte.length <= EXTRAIT_LONGUEUR_MAX) return texte;
  return `${texte.slice(0, EXTRAIT_LONGUEUR_MAX).trimEnd()}…`;
}

type EntreeHistorique = components["schemas"]["EntreeHistoriqueReponse"];

export function EntreeHistoriqueCard({ entree }: { entree: EntreeHistorique }) {
  return (
    // `resultat_id`, pas `entree.id` : ce dernier identifie la ligne
    // d'historique elle-même, `resultat_id` l'analyse à afficher (K4) —
    // même distinction que côté back (api_historique.py).
    <Link
      href={`/analyse/${entree.resultat_id}`}
      className="flex flex-col gap-1.5 rounded-md border border-border p-4 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <p className="text-sm text-foreground">{tronquer(entree.input_text)}</p>
      <p className="text-xs text-muted-foreground">
        {FORMATTEUR_DATE.format(new Date(entree.created_at))}
      </p>
    </Link>
  );
}
