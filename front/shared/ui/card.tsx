import type { ElementType, HTMLAttributes, Ref } from "react";
import { cn } from "./cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-surface text-surface-foreground shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1.5 p-6", className)} {...props} />;
}

export type CardTitleProps = HTMLAttributes<HTMLHeadingElement> & {
  // `h3` par défaut (une `Card` est le plus souvent une sous-section d'une
  // page qui a déjà son propre `<h1>` ailleurs). `as="h1"` reste
  // disponible pour la carte qui EST le contenu principal de sa page — cas
  // de `/analyse/[id]` (K5, backlog.md) : chaque page ne doit exposer
  // qu'un seul `<h1>` (WCAG 2.4.6/1.3.1, agents.md §5), donc ce choix est
  // au niveau de l'appelant, pas de `Card` elle-même.
  as?: ElementType;
  // Prop `ref` directement typée (React 19 : plus besoin de `forwardRef`
  // pour un composant fonction) — utilisé par K5/backlog.md pour déplacer
  // le focus sur le titre quand le résultat de l'analyse remplace l'état
  // de chargement.
  ref?: Ref<HTMLHeadingElement>;
};

export function CardTitle({ className, as: Comp = "h3", ref, ...props }: CardTitleProps) {
  return (
    <Comp ref={ref} className={cn("text-lg font-semibold leading-none", className)} {...props} />
  );
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-6 pb-6", className)} {...props} />;
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center gap-2 px-6 pb-6", className)} {...props} />;
}
