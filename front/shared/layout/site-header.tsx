import Link from "next/link";

// Même anneau de focus que `shared/ui/button.tsx` : le focus clavier doit
// rester visuellement cohérent entre composants et layout (agents.md §5).
const focusRing =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

export function SiteHeader() {
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
              <Link
                href="/"
                className={`rounded-md text-muted-foreground transition-colors hover:text-foreground ${focusRing}`}
              >
                Accueil
              </Link>
            </li>
          </ul>
        </nav>
      </div>
    </header>
  );
}
