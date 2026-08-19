"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { PartageResultat, useSuiviAnalyse } from "@/features/analyse";
import {
  buttonVariants,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Spinner,
} from "@/shared/ui";

// Page publique — pas de `RouteProtegee` (K4, backlog.md) : le résultat est
// justement fait pour être ouvert par n'importe qui via un lien partagé,
// authentifié ou non. Cohérent avec `GET /analyses/{id}/statut`, qui n'a
// aucune dépendance d'auth côté back (agents.md §7 : rien de sensible n'est
// exposé par ce endpoint).
function PageCentree({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-4 py-12">
      {children}
    </div>
  );
}

export default function AnalysePage() {
  const { id } = useParams<{ id: string }>();
  const suivi = useSuiviAnalyse(id);

  // `window.location.origin` seul en état paresseux (même compromis que
  // `readStoredTheme`/`getSystemTheme`, shared/theme/theme-provider.tsx :
  // absent côté serveur, d'où la garde) — jamais `location.href` en entier,
  // qui reste sur l'URL précédente au moment du montage lors d'une
  // navigation côté client (`router.push` depuis "/", K3) : l'origine ne
  // change jamais pendant la session, alors que le chemin recalculé à partir
  // de `id` (réactif via `useParams`) reste toujours juste.
  const [origin] = useState(() => (typeof window === "undefined" ? "" : window.location.origin));
  const urlPartage = origin ? `${origin}/analyse/${id}` : "";

  if (suivi.statut === "introuvable") {
    return (
      <PageCentree>
        <Card>
          <CardContent className="flex flex-col items-center gap-4 pt-6 text-center">
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
          <CardContent className="flex flex-col items-center gap-4 pt-6 text-center">
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
          <CardContent className="flex flex-col items-center gap-4 pt-6 text-center">
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
          <CardContent className="flex flex-col items-center gap-4 pt-6 text-center">
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
          <CardTitle>Résultat de l&apos;analyse</CardTitle>
          <CardDescription>Voici ce que l&apos;IA a pensé de ce texte.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {analyse.resultat_image_url && (
            // `<img>` plutôt que `next/image` : `resultat_image_url` est une
            // URL absolue vers un bucket dont l'hôte varie par environnement
            // (GCS en prod, filesystem local en dev) — l'optimiseur d'image
            // exigerait une allowlist de domaines à maintenir en double avec
            // la config d'infra, pour un gain de perf non mesuré ici
            // (agents.md §8 : pas d'optimisation sans donnée montrant le
            // problème).
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={analyse.resultat_image_url}
              alt="Illustration générée pour cette analyse"
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
