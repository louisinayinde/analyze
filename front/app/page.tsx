"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError, useApiRequest } from "@/shared/api";
import type { components } from "@/shared/api";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Spinner,
  TextArea,
} from "@/shared/ui";

type SourceAnalyse = components["schemas"]["SourceAnalyse"];
type AnalyseReponse =
  | components["schemas"]["AnalyseTermineeReponse"]
  | components["schemas"]["AnalyseEnAttenteReponse"];

// Même borne que `back/src/modules/analyse/domaine/texte_analyse.py`
// (`TEXTE_LONGUEUR_MAX`, D7) : validation front pour un retour immédiat,
// mais le back reste la seule autorité — s'il change cette borne, le pire
// cas ici est un aller-retour réseau évitable, jamais une faille (agents.md
// §7).
const TEXTE_LONGUEUR_MAX = 5000;

const SOURCES: { value: SourceAnalyse; label: string }[] = [
  { value: "github", label: "Profil GitHub" },
  { value: "spotify", label: "Historique d'écoute" },
  { value: "bio", label: "Bio" },
  { value: "autre", label: "Autre texte" },
];

function validerTexte(texte: string): string | undefined {
  if (!texte.trim()) return "Colle un texte à analyser avant de continuer.";
  if (texte.length > TEXTE_LONGUEUR_MAX) {
    return `Le texte dépasse la limite de ${texte.length - TEXTE_LONGUEUR_MAX} caractère(s) (max ${TEXTE_LONGUEUR_MAX}).`;
  }
  return undefined;
}

function estAnalyseEnAttente(
  resultat: AnalyseReponse,
): resultat is components["schemas"]["AnalyseEnAttenteReponse"] {
  return "job_id" in resultat;
}

export default function Home() {
  const router = useRouter();
  const request = useApiRequest();

  const [texte, setTexte] = useState("");
  const [sourceType, setSourceType] = useState<SourceAnalyse>("autre");
  const [erreurTexte, setErreurTexte] = useState<string>();
  const [envoiEnCours, setEnvoiEnCours] = useState(false);
  // Cache-miss (202) : on garde le `job_id` pour K3, qui branchera le
  // polling `GET /analyses/{id}/statut` dessus. Tant que cet état est posé,
  // on affiche le chargement à la place du formulaire (K2) — cache-hit
  // (200) ne passe jamais par cet état, il redirige tout de suite.
  const [jobIdEnAttente, setJobIdEnAttente] = useState<string>();

  const texteEstValide = texte.trim().length > 0 && texte.length <= TEXTE_LONGUEUR_MAX;
  const texteDepasseLaLimite = texte.length > TEXTE_LONGUEUR_MAX;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const erreurValidation = validerTexte(texte);
    setErreurTexte(erreurValidation);
    if (erreurValidation) return;

    setEnvoiEnCours(true);
    try {
      const resultat = await request(
        apiClient.POST("/analyses", {
          body: { texte: texte.trim(), source_type: sourceType },
        }),
      );

      // Branchement cache-hit / cache-miss (K2) :
      // - cache-miss (202) : rien à montrer tout de suite, on bascule dans
      //   l'état de chargement (`jobIdEnAttente`) — K3 y branchera le
      //   polling `GET /analyses/{id}/statut` avec ce `job_id`.
      // - cache-hit (200) : le résultat existe déjà, on redirige tout de
      //   suite plutôt que de faire attendre l'utilisateur pour rien.
      if (estAnalyseEnAttente(resultat)) {
        setJobIdEnAttente(resultat.job_id);
      } else {
        router.push(`/analyse/${resultat.id}`);
      }
      setTexte("");
    } catch (error) {
      // `useApiRequest` a déjà affiché un toast (I5). On ajoute ici un
      // message explicite à côté du champ concerné pour l'erreur métier
      // connue du contrat (`shared/api/schema.gen.ts`), pour qu'elle reste
      // visible après la disparition du toast — même pattern que J1.
      if (error instanceof ApiError && error.code === "entree_invalide") {
        setErreurTexte(error.message);
      }
    } finally {
      setEnvoiEnCours(false);
    }
  }

  // Cache-miss : le formulaire cède la place à l'attente — K3 remplacera ce
  // bloc par le vrai polling (message engageant, arrêt sur done/failed) sans
  // toucher au branchement ci-dessus.
  if (jobIdEnAttente) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-4 py-12">
        <Card>
          <CardContent className="flex flex-col items-center gap-4 pt-6 text-center">
            <Spinner size="lg" />
            <p aria-live="polite" className="text-sm text-muted-foreground">
              On génère ton analyse, ça prend quelques secondes...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-4 py-12">
      <Card>
        <CardHeader>
          <CardTitle>Analyse-moi ça</CardTitle>
          <CardDescription>
            Colle ton profil GitHub, ton historique d&apos;écoute ou ta bio. On te renvoie une
            analyse (et une image) prête à partager.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="source" className="text-sm font-medium text-foreground">
                Type de contenu
              </label>
              <select
                id="source"
                name="source"
                value={sourceType}
                onChange={(event) => setSourceType(event.target.value as SourceAnalyse)}
                disabled={envoiEnCours}
                className="flex h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
              >
                {SOURCES.map((source) => (
                  <option key={source.value} value={source.value}>
                    {source.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="texte" className="text-sm font-medium text-foreground">
                Texte à analyser
              </label>
              <TextArea
                id="texte"
                name="texte"
                rows={10}
                placeholder="Colle ton texte ici..."
                value={texte}
                onChange={(event) => {
                  setTexte(event.target.value);
                  if (erreurTexte) setErreurTexte(undefined);
                }}
                invalid={Boolean(erreurTexte)}
                aria-describedby={
                  erreurTexte ? "texte-erreur texte-compteur" : "texte-compteur"
                }
                disabled={envoiEnCours}
              />
              <div className="flex items-center justify-between gap-4">
                {erreurTexte ? (
                  <p id="texte-erreur" role="alert" className="text-sm text-destructive">
                    {erreurTexte}
                  </p>
                ) : (
                  <span />
                )}
                <p
                  id="texte-compteur"
                  className={`shrink-0 text-sm ${texteDepasseLaLimite ? "text-destructive" : "text-muted-foreground"}`}
                >
                  {texte.length} / {TEXTE_LONGUEUR_MAX}
                </p>
              </div>
            </div>

            <Button
              type="submit"
              loading={envoiEnCours}
              disabled={!texteEstValide}
              size="lg"
              className="mt-2"
            >
              Analyser mon texte
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
