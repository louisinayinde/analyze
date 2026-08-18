import type { SVGAttributes } from "react";
import { cn } from "./cn";

export type SpinnerSize = "sm" | "md" | "lg";

export type SpinnerProps = SVGAttributes<SVGSVGElement> & {
  size?: SpinnerSize;
  label?: string;
};

const sizeClasses: Record<SpinnerSize, string> = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-8 w-8",
};

// Indicateur fonctionnel (pas décoratif) : reste animé même en mouvement
// réduit, c'est le seul moyen de savoir qu'un traitement est en cours.
export function Spinner({ className, size = "md", label = "Chargement…", ...props }: SpinnerProps) {
  return (
    <svg
      role="status"
      aria-label={label}
      viewBox="0 0 24 24"
      fill="none"
      className={cn("animate-spin text-current", sizeClasses[size], className)}
      {...props}
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
      <path
        d="M22 12a10 10 0 0 0-10-10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        className="opacity-90"
      />
    </svg>
  );
}
