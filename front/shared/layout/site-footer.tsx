export function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto max-w-3xl px-4 py-6 text-sm text-muted-foreground">
        <p>© {new Date().getFullYear()} Analyse-moi ça</p>
      </div>
    </footer>
  );
}
