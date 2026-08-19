"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { RouteProtegee, useAuth } from "@/features/auth";
import { apiClient, ApiError, useApiRequest } from "@/shared/api";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Skeleton,
  useToast,
} from "@/shared/ui";

// `Intl.DateTimeFormat`, pas de formatage manuel (agents.md §10) : instancié
// une seule fois au niveau du module, pas à chaque rendu.
const FORMATTEUR_DATE = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long" });

type InfosCompte = { email: string; createdAt: string };

function ComptePageContenu({ onSuppressionReussie }: { onSuppressionReussie: () => void }) {
  const router = useRouter();
  const request = useApiRequest();
  const { toast } = useToast();
  const { accessToken, logout } = useAuth();

  const [compte, setCompte] = useState<InfosCompte | null>(null);
  const [chargementEnCours, setChargementEnCours] = useState(true);

  const [suppressionOuverte, setSuppressionOuverte] = useState(false);
  const [motDePasse, setMotDePasse] = useState("");
  const [erreurMotDePasse, setErreurMotDePasse] = useState<string>();
  const [suppressionEnCours, setSuppressionEnCours] = useState(false);

  // Monté uniquement une fois `RouteProtegee` (J4) satisfaite, donc
  // `accessToken` est déjà posé — pas de course avec le rafraîchissement
  // silencieux initial (J3, auth-provider.tsx).
  useEffect(() => {
    let annule = false;

    async function charger() {
      try {
        const donnees = await request(
          apiClient.GET("/compte", {
            headers: { Authorization: `Bearer ${accessToken}` },
          }),
        );
        if (!annule) {
          setCompte({ email: donnees.email, createdAt: donnees.created_at });
        }
      } finally {
        if (!annule) setChargementEnCours(false);
      }
    }

    charger();
    return () => {
      annule = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleConfirmerSuppression(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!motDePasse) {
      setErreurMotDePasse("Le mot de passe est obligatoire.");
      return;
    }

    setSuppressionEnCours(true);
    try {
      // 204 en cas de succès : compte, refresh tokens et historique
      // supprimés en cascade côté back (H3).
      await request(
        apiClient.DELETE("/compte", {
          body: { mot_de_passe: motDePasse },
          headers: { Authorization: `Bearer ${accessToken}` },
        }),
      );
      // Avant `logout()`, pas après : signale à `RouteProtegee` de ne pas
      // rediriger vers /connexion quand `status` va passer à "anonymous"
      // (voir le commentaire sur `suspendreRedirection`, route-protegee.tsx)
      // — on veut atterrir sur "/", pas /connexion.
      onSuppressionReussie();
      // `logout()` (J3) efface le cookie httpOnly et l'état local — appel
      // idempotent même si les refresh tokens sont déjà révoqués côté back
      // par la suppression (DeconnecterUtilisateur.executer, back).
      await logout();
      toast({
        title: "Compte supprimé",
        description: "Ton compte et ton historique ont été définitivement supprimés.",
        variant: "success",
      });
      router.push("/");
    } catch (error) {
      // 401 générique du contrat (schema.gen.ts) : mot de passe incorrect,
      // même posture anti-énumération que /auth/connexion (agents.md §7).
      if (error instanceof ApiError && error.code === "non_authentifie") {
        setErreurMotDePasse(error.message);
      }
    } finally {
      setSuppressionEnCours(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 px-4 py-12">
      <Card>
        <CardHeader>
          <CardTitle>Mon compte</CardTitle>
          <CardDescription>Les informations liées à ton compte.</CardDescription>
        </CardHeader>
        <CardContent>
          {chargementEnCours || !compte ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ) : (
            <dl className="flex flex-col gap-3 text-sm">
              <div className="flex flex-col gap-0.5">
                <dt className="text-muted-foreground">Email</dt>
                <dd className="text-foreground">{compte.email}</dd>
              </div>
              <div className="flex flex-col gap-0.5">
                <dt className="text-muted-foreground">Membre depuis</dt>
                <dd className="text-foreground">
                  {FORMATTEUR_DATE.format(new Date(compte.createdAt))}
                </dd>
              </div>
            </dl>
          )}
        </CardContent>
      </Card>

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Supprimer mon compte</CardTitle>
          <CardDescription>
            Action irréversible : ton compte et ton historique d&apos;analyses seront définitivement
            supprimés.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!suppressionOuverte ? (
            <Button variant="destructive" onClick={() => setSuppressionOuverte(true)}>
              Supprimer mon compte
            </Button>
          ) : (
            // La re-saisie du mot de passe sert de confirmation explicite
            // (exigée par ce ticket) ET de vérification renforcée côté back
            // (step-up, H3, agents.md §7) — pas de logique dupliquée pour
            // ces deux besoins.
            <form noValidate onSubmit={handleConfirmerSuppression} className="flex flex-col gap-4">
              <p role="alert" className="text-sm text-destructive">
                Cette action est définitive. Confirme ton mot de passe pour supprimer ton compte.
              </p>

              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="mot-de-passe-suppression"
                  className="text-sm font-medium text-foreground"
                >
                  Mot de passe
                </label>
                <Input
                  id="mot-de-passe-suppression"
                  name="mot-de-passe"
                  type="password"
                  autoComplete="current-password"
                  value={motDePasse}
                  onChange={(event) => {
                    setMotDePasse(event.target.value);
                    if (erreurMotDePasse) setErreurMotDePasse(undefined);
                  }}
                  invalid={Boolean(erreurMotDePasse)}
                  aria-describedby={
                    erreurMotDePasse ? "mot-de-passe-suppression-erreur" : undefined
                  }
                  disabled={suppressionEnCours}
                  autoFocus
                />
                {erreurMotDePasse && (
                  <p
                    id="mot-de-passe-suppression-erreur"
                    role="alert"
                    className="text-sm text-destructive"
                  >
                    {erreurMotDePasse}
                  </p>
                )}
              </div>

              <div className="flex gap-2">
                <Button type="submit" variant="destructive" loading={suppressionEnCours}>
                  Confirmer la suppression définitive
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={suppressionEnCours}
                  onClick={() => {
                    setSuppressionOuverte(false);
                    setMotDePasse("");
                    setErreurMotDePasse(undefined);
                  }}
                >
                  Annuler
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function ComptePage() {
  const [suppressionReussie, setSuppressionReussie] = useState(false);

  return (
    <RouteProtegee suspendreRedirection={suppressionReussie}>
      <ComptePageContenu onSuppressionReussie={() => setSuppressionReussie(true)} />
    </RouteProtegee>
  );
}
