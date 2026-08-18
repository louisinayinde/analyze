"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/features/auth";
import { ApiError, useApiRequest } from "@/shared/api";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
} from "@/shared/ui";

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
  return undefined;
}

export default function ConnexionPage() {
  const router = useRouter();
  const request = useApiRequest();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreurs, setErreurs] = useState<ChampErreurs>({});
  const [erreurFormulaire, setErreurFormulaire] = useState<string>();
  const [envoiEnCours, setEnvoiEnCours] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const erreursValidation: ChampErreurs = {
      email: validerEmail(email),
      motDePasse: validerMotDePasse(motDePasse),
    };
    setErreurs(erreursValidation);
    setErreurFormulaire(undefined);
    if (erreursValidation.email || erreursValidation.motDePasse) {
      return;
    }

    setEnvoiEnCours(true);
    try {
      // `login` (features/auth, J3) passe par le Route Handler
      // `app/api/auth/connexion` : c'est lui qui pose le refresh token en
      // cookie httpOnly, jamais visible ici. L'access token part en mémoire
      // (token-store.ts) et un rafraîchissement silencieux est planifié
      // avant son expiration.
      await request(login(email, motDePasse));
      router.push("/");
    } catch (error) {
      // 401 générique du contrat (`schema.gen.ts`) : le backend ne dit
      // jamais si c'est l'email ou le mot de passe qui est faux (agents.md
      // §7, anti-énumération). On affiche donc l'erreur au niveau du
      // formulaire, jamais rattachée à un champ précis — sinon on
      // réintroduirait côté front la fuite d'info que le back évite.
      if (error instanceof ApiError && error.code === "non_authentifie") {
        setErreurFormulaire(error.message);
      }
    } finally {
      setEnvoiEnCours(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-4 py-12">
      <Card>
        <CardHeader>
          <CardTitle>Se connecter</CardTitle>
          <CardDescription>Retrouve ton historique d&apos;analyses.</CardDescription>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-4">
            {erreurFormulaire && (
              <p role="alert" className="text-sm text-destructive">
                {erreurFormulaire}
              </p>
            )}

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
                  if (erreurFormulaire) setErreurFormulaire(undefined);
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
                autoComplete="current-password"
                value={motDePasse}
                onChange={(event) => {
                  setMotDePasse(event.target.value);
                  if (erreurs.motDePasse) {
                    setErreurs((current) => ({ ...current, motDePasse: undefined }));
                  }
                  if (erreurFormulaire) setErreurFormulaire(undefined);
                }}
                invalid={Boolean(erreurs.motDePasse)}
                aria-describedby={erreurs.motDePasse ? "mot-de-passe-erreur" : undefined}
                disabled={envoiEnCours}
              />
              {erreurs.motDePasse && (
                <p id="mot-de-passe-erreur" role="alert" className="text-sm text-destructive">
                  {erreurs.motDePasse}
                </p>
              )}
            </div>

            <Button type="submit" loading={envoiEnCours} className="mt-2">
              Se connecter
            </Button>
          </form>
        </CardContent>
      </Card>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Pas encore de compte ?{" "}
        <Link
          href="/inscription"
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          Créer un compte
        </Link>
      </p>
    </div>
  );
}
