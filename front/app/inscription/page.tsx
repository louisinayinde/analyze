"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient, ApiError, useApiRequest } from "@/shared/api";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
} from "@/shared/ui";

// Mêmes bornes que `back/src/modules/auth/domaine/mot_de_passe.py` (C3) :
// validation front pour un retour immédiat, mais le back reste la seule
// autorité — s'il change ses règles, le pire cas ici est un aller-retour
// réseau évitable, jamais une faille (agents.md §7).
const MOT_DE_PASSE_LONGUEUR_MIN = 10;
const MOT_DE_PASSE_LONGUEUR_MAX = 128;

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type ChampErreurs = {
  email?: string;
  motDePasse?: string;
};

function validerEmail(email: string): string | undefined {
  if (!email.trim()) return "L'adresse email est obligatoire.";
  if (!EMAIL_REGEX.test(email)) return "L'adresse email n'est pas valide.";
  return undefined;
}

function validerMotDePasse(motDePasse: string): string | undefined {
  if (!motDePasse) return "Le mot de passe est obligatoire.";
  if (
    motDePasse.length < MOT_DE_PASSE_LONGUEUR_MIN ||
    motDePasse.length > MOT_DE_PASSE_LONGUEUR_MAX
  ) {
    return `Le mot de passe doit contenir entre ${MOT_DE_PASSE_LONGUEUR_MIN} et ${MOT_DE_PASSE_LONGUEUR_MAX} caractères.`;
  }
  return undefined;
}

export default function InscriptionPage() {
  const router = useRouter();
  const request = useApiRequest();

  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreurs, setErreurs] = useState<ChampErreurs>({});
  const [envoiEnCours, setEnvoiEnCours] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const erreursValidation: ChampErreurs = {
      email: validerEmail(email),
      motDePasse: validerMotDePasse(motDePasse),
    };
    setErreurs(erreursValidation);
    if (erreursValidation.email || erreursValidation.motDePasse) {
      return;
    }

    setEnvoiEnCours(true);
    try {
      await request(
        apiClient.POST("/auth/inscription", {
          body: { email, mot_de_passe: motDePasse },
        }),
      );
      router.push("/connexion");
    } catch (error) {
      // `useApiRequest` a déjà affiché un toast (I5). On ajoute ici un
      // message explicite à côté du champ concerné pour les deux erreurs
      // métier connues du contrat (`shared/api/schema.gen.ts`), pour que
      // l'erreur reste visible même après la disparition du toast.
      if (error instanceof ApiError && error.code === "conflit_ressource") {
        setErreurs((current) => ({ ...current, email: error.message }));
      } else if (error instanceof ApiError && error.code === "entree_invalide") {
        setErreurs((current) => ({ ...current, motDePasse: error.message }));
      }
    } finally {
      setEnvoiEnCours(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-4 py-12">
      <Card>
        <CardHeader>
          <CardTitle>Créer un compte</CardTitle>
          <CardDescription>
            Pour retrouver ton historique d&apos;analyses et les partager plus tard.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="email" className="text-sm font-medium text-foreground">
                Email
              </label>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  if (erreurs.email) setErreurs((current) => ({ ...current, email: undefined }));
                }}
                invalid={Boolean(erreurs.email)}
                aria-describedby={erreurs.email ? "email-erreur" : undefined}
                disabled={envoiEnCours}
              />
              {erreurs.email && (
                <p id="email-erreur" role="alert" className="text-sm text-destructive">
                  {erreurs.email}
                </p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="mot-de-passe" className="text-sm font-medium text-foreground">
                Mot de passe
              </label>
              <Input
                id="mot-de-passe"
                name="mot-de-passe"
                type="password"
                autoComplete="new-password"
                value={motDePasse}
                onChange={(event) => {
                  setMotDePasse(event.target.value);
                  if (erreurs.motDePasse) {
                    setErreurs((current) => ({ ...current, motDePasse: undefined }));
                  }
                }}
                invalid={Boolean(erreurs.motDePasse)}
                aria-describedby={erreurs.motDePasse ? "mot-de-passe-erreur" : "mot-de-passe-aide"}
                disabled={envoiEnCours}
              />
              {erreurs.motDePasse ? (
                <p id="mot-de-passe-erreur" role="alert" className="text-sm text-destructive">
                  {erreurs.motDePasse}
                </p>
              ) : (
                <p id="mot-de-passe-aide" className="text-sm text-muted-foreground">
                  Entre {MOT_DE_PASSE_LONGUEUR_MIN} et {MOT_DE_PASSE_LONGUEUR_MAX} caractères.
                </p>
              )}
            </div>

            <Button type="submit" loading={envoiEnCours} className="mt-2">
              Créer mon compte
            </Button>
          </form>
        </CardContent>
      </Card>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Déjà un compte ?{" "}
        <Link
          href="/connexion"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Se connecter
        </Link>
      </p>
    </div>
  );
}
