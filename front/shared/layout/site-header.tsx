"use client";

import Link from "next/link";
import { useAuth } from "@/features/auth";

// Même anneau de focus que `shared/ui/button.tsx` : le focus clavier doit
// rester visuellement cohérent entre composants et layout (agents.md §5).
const focusRing =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

const navLinkClassName = `rounded-md text-muted-foreground transition-colors hover:text-foreground ${focusRing}`;

export function SiteHeader() {
  // `"use client"` (J5) : le seul lien qui dépend de l'auth est "Mon
  // compte"/"Se connecter" — `status` vit en mémoire JS (auth-provider.tsx),
  // pas question de pré-rendre ça côté serveur. Pendant "loading" (J3), on
  // n'affiche ni l'un ni l'autre plutôt que de deviner : un flash "Se
  // connecter" → "Mon compte" au chargement serait plus perturbant qu'un
  // slot vide le temps du rafraîchissement silencieux initial.
  const { status } = useAuth();

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
        <Link
          href="/"
          className={`rounded-md text-base font-semibold text-foreground ${focusRing}`}
        >
          Analyse-moi ça
        </Link>
        <nav aria-label="Navigation principale">
          <ul className="flex items-center gap-4 text-sm">
            <li>
              <Link href="/" className={navLinkClassName}>
                Accueil
              </Link>
            </li>
            {status === "authenticated" && (
              <>
                <li>
                  <Link href="/historique" className={navLinkClassName}>
                    Historique
                  </Link>
                </li>
                <li>
                  <Link href="/compte" className={navLinkClassName}>
                    Mon compte
                  </Link>
                </li>
              </>
            )}
            {status === "anonymous" && (
              <li>
                <Link href="/connexion" className={navLinkClassName}>
                  Se connecter
                </Link>
              </li>
            )}
          </ul>
        </nav>
      </div>
    </header>
  );
}
