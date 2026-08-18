// Premier élément focusable de la page (agents.md §5 — WCAG 2.1 AA, critère
// 2.4.1) : permet d'atteindre `#main-content` sans traverser le header à
// chaque page. Invisible tant qu'il n'a pas le focus clavier.
export function SkipLink() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      Aller au contenu principal
    </a>
  );
}
