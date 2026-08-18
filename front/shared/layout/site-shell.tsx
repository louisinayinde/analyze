import type { ReactNode } from "react";
import { SiteFooter } from "./site-footer";
import { SiteHeader } from "./site-header";
import { SkipLink } from "./skip-link";

// Structure de page partagée : lien d'évitement, header/nav, `<main>`
// repérable, footer. Tout ce que rend `app/*/page.tsx` devient l'enfant de
// `<main>` (agents.md §5 — un seul landmark `main` par page).
export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <>
      <SkipLink />
      <SiteHeader />
      <main id="main-content" className="flex flex-1 flex-col">
        {children}
      </main>
      <SiteFooter />
    </>
  );
}
