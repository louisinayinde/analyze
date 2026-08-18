// Surface publique du module `ui` — aucun autre module ne doit importer un
// fichier interne (`button.tsx`, `cn.ts`, ...) directement (agents.md §4).

export { Button } from "./button";
export type { ButtonProps, ButtonSize, ButtonVariant } from "./button";

export { Input } from "./input";
export type { InputProps } from "./input";

export { TextArea } from "./textarea";
export type { TextAreaProps } from "./textarea";

export { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "./card";

export { Spinner } from "./spinner";
export type { SpinnerProps, SpinnerSize } from "./spinner";

export { Skeleton } from "./skeleton";

export { ToastProvider, useToast } from "./toast-provider";
export type { ToastOptions, ToastVariant } from "./toast-provider";
