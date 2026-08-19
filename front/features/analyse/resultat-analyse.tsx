"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { PartageResultat } from "./partage-resultat";
import { useSuiviAnalyse } from "./use-suivi-analyse";
import type { SuiviAnalyse } from "./use-suivi-analyse";
import {
  buttonVariants,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Spinner,
} from "@/shared/ui";

// Dimensions fixes du template de rendu backend (E2, backlog.md — voir
// back/src/modules/ia/adaptateurs/rendu_image_template.py, LARGEUR/HAUTEUR) :
// toute image générée fait exactement 1200x630. Les déclarer ici réserve
// l'espace avant même que l'image ait chargé, ce qui élimine le saut de
// mise en page correspondant (CLS, K5, backlog.md).
const IMAGE_LARGEUR = 1200;
const IMAGE_HAUTEUR = 630;

function PageCentree({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-4 py-12">
      {children}
    </div>
  );
}

// Rendu interactif de `/analyse/[id]` (K4/K5, backlog.md). Séparé de
// `app/analyse/[id]/page.tsx`, qui reste un Server Component : c'est lui qui
// résout le statut initial côté serveur (K5 — évite le spinner systématique
// le temps d'un aller-retour réseau client, cas quasi toujours inutile
// puisque K2/K3 ne redirigent ici qu'une fois l'analyse `done`). Ce
// composant ne fait que continuer le suivi (poll) si ce statut initial est
// encore `en_cours` — voir `useSuiviAnalyse`.
export function ResultatAnalyse({
  analyseId,
  suiviInitial,
  urlPartage,
}: {
  analyseId: string;
  suiviInitial: SuiviAnalyse;
  urlPartage: string;
}) {
  const suivi = useSuiviAnalyse(analyseId, suiviInitial);

  // Déplace le focus clavier/lecteur d'écran sur le titre dès que le statut
  // change *après* le premier rendu — jamais au premier rendu lui-même (cas
  // courant : la page arrive déjà résolue depuis le serveur, l'utilisateur
  // n'attendait rien, lui voler le focus serait perturbant). C'est
  // l'équivalent d'une annonce de statut (WCAG 4.1.3) pour un remplacement
  // de contenu que `aria-live` gère mal à cette échelle (tout un bloc, pas
  // un simple message) — le focus lu par le lecteur d'écran sur le nouveau
  // titre fait l'annonce.
  const titreRef = useRef<HTMLHeadingElement>(null);
  const statutPrecedentRef = useRef(suivi.statut);
  useEffect(() => {
    if (statutPrecedentRef.current === "en_cours" && suivi.statut !== "en_cours") {
      titreRef.current?.focus();
    }
    statutPrecedentRef.current = suivi.statut;
  }, [suivi.statut]);

  if (suivi.statut === "introuvable") {
    return (
      <PageCentree>
        <Card>
          <CardHeader>
            <CardTitle as="h1" ref={titreRef} tabIndex={-1}>
              Analyse introuvable
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4 text-center">
            <p role="alert" className="text-sm text-destructive">
              Aucune analyse ne correspond à ce lien. Il a peut-être expiré ou été mal copié.
            </p>
            <Link href="/" className={buttonVariants("primary", "md")}>
              Faire une nouvelle analyse
            </Link>
          </CardContent>
        </Card>
      </PageCentree>
    );
  }

  if (suivi.statut === "echec") {
    return (
      <PageCentree>
        <Card>
          <CardHeader>
            <CardTitle as="h1" ref={titreRef} tabIndex={-1}>
              Échec de l&apos;analyse
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4 text-center">
            <p role="alert" className="text-sm text-destructive">
              La génération de cette analyse a échoué. Elle n&apos;est plus disponible.
            </p>
            <Link href="/" className={buttonVariants("primary", "md")}>
              Faire une nouvelle analyse
            </Link>
          </CardContent>
        </Card>
      </PageCentree>
    );
  }

  if (suivi.statut === "erreur") {
    return (
      <PageCentree>
        <Card>
          <CardHeader>
            <CardTitle as="h1" ref={titreRef} tabIndex={-1}>
              Erreur de chargement
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4 text-center">
            <p role="alert" className="text-sm text-destructive">
              Impossible de charger cette analyse. Vérifie ta connexion et réessaie.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className={buttonVariants("primary", "md")}
            >
              Réessayer
            </button>
          </CardContent>
        </Card>
      </PageCentree>
    );
  }

  if (suivi.statut === "en_cours") {
    return (
      <PageCentree>
        <Card>
          <CardHeader>
            <CardTitle as="h1" ref={titreRef} tabIndex={-1}>
              Analyse en cours
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4 text-center">
            <Spinner size="lg" />
            <p aria-live="polite" className="text-sm text-muted-foreground">
              L&apos;analyse est en cours de génération...
            </p>
          </CardContent>
        </Card>
      </PageCentree>
    );
  }

  const { analyse } = suivi;

  return (
    <PageCentree>
      <Card>
        <CardHeader>
          <CardTitle as="h1" ref={titreRef} tabIndex={-1}>
            Résultat de l&apos;analyse
          </CardTitle>
          <CardDescription>Voici ce que l&apos;IA a pensé de ce texte.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {analyse.resultat_image_url && (
            // `<img>` plutôt que `next/image` : `resultat_image_url` est une
            // URL absolue vers un bucket dont l'hôte varie par environnement
            // (GCS en prod, filesystem local en dev) — l'optimiseur d'image
            // exigerait une allowlist de domaines à maintenir en double avec
            // la config d'infra (agents.md §8 : pas d'optimisation sans
            // donnée montrant le problème). `width`/`height` restent
            // déclarés explicitement (dimensions fixes du template, voir
            // plus haut) pour réserver l'espace et éviter un CLS ; c'est
            // aussi très probablement l'élément LCP de cette page publique
            // (K5, backlog.md), d'où `fetchPriority="high"` pour la faire
            // charger sans attendre la découverte tardive par le navigateur.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={analyse.resultat_image_url}
              alt="Illustration générée pour cette analyse"
              width={IMAGE_LARGEUR}
              height={IMAGE_HAUTEUR}
              fetchPriority="high"
              className="w-full rounded-md border border-border"
            />
          )}

          {analyse.resultat_texte && (
            <p className="whitespace-pre-wrap text-sm text-foreground">{analyse.resultat_texte}</p>
          )}

          {urlPartage && <PartageResultat url={urlPartage} />}
        </CardContent>
      </Card>
    </PageCentree>
  );
}
