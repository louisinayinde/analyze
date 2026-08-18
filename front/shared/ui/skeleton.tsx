import type { HTMLAttributes } from "react";
import { cn } from "./cn";

// Purement visuel : masqué des lecteurs d'écran, le vrai contenu en cours de
// chargement n'existe pas encore dans le DOM.
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}
