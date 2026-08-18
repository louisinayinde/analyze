// Surface publique du module `theme` — aucun autre module ne doit importer
// un fichier interne (`theme-provider.tsx`, `theme-script.tsx`, `constants.ts`)
// directement (agents.md §4).
export { ThemeProvider, useTheme } from "./theme-provider";
export { ThemeScript } from "./theme-script";
export type { ResolvedTheme, Theme } from "./constants";
