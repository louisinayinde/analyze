import { THEME_STORAGE_KEY } from "./constants";

// Doit rester en phase avec la logique de résolution de `theme-provider.tsx`
// (même définition de "dark") pour éviter tout flash entre le rendu initial
// et l'hydratation React.
const script = `(function(){try{var s=localStorage.getItem("${THEME_STORAGE_KEY}");var m=window.matchMedia("(prefers-color-scheme: dark)").matches;var dark=s==="dark"||(s!=="light"&&m);var root=document.documentElement;root.classList.toggle("dark",dark);root.style.colorScheme=dark?"dark":"light";}catch(e){}})();`;

// Script bloquant exécuté avant tout paint : lit la préférence stockée (ou le
// thème système) et applique la classe `dark` avant que la page ne soit
// visible, pour éviter le flash clair/sombre au chargement.
export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
