"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { cn } from "./cn";

export type ToastVariant = "default" | "success" | "destructive" | "warning";

export type ToastOptions = {
  title: string;
  description?: string;
  variant?: ToastVariant;
  /** Durée d'affichage en ms avant disparition automatique. 0 = pas d'auto-dismiss. */
  duration?: number;
};

type ToastItem = ToastOptions & { id: string };

type ToastContextValue = {
  toast: (options: ToastOptions) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const DEFAULT_DURATION = 5000;

const variantClasses: Record<ToastVariant, string> = {
  default: "border-border bg-surface text-surface-foreground",
  success: "border-success bg-success text-success-foreground",
  destructive: "border-destructive bg-destructive text-destructive-foreground",
  warning: "border-warning bg-warning text-warning-foreground",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback(
    (options: ToastOptions) => {
      const id = crypto.randomUUID();
      const duration = options.duration ?? DEFAULT_DURATION;
      setToasts((current) => [...current, { ...options, id }]);
      if (duration > 0) {
        window.setTimeout(() => dismiss(id), duration);
      }
    },
    [dismiss],
  );

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        role="region"
        aria-label="Notifications"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col gap-2 p-4 sm:inset-x-auto sm:right-0 sm:w-full sm:max-w-sm"
      >
        {toasts.map((item) => {
          const variant = item.variant ?? "default";
          return (
            <div
              key={item.id}
              role={variant === "destructive" ? "alert" : "status"}
              aria-live={variant === "destructive" ? "assertive" : "polite"}
              className={cn(
                "pointer-events-auto flex items-start gap-3 rounded-md border p-4 shadow-lg",
                variantClasses[variant],
              )}
            >
              <div className="flex-1">
                <p className="text-sm font-medium">{item.title}</p>
                {item.description && <p className="mt-1 text-sm opacity-90">{item.description}</p>}
              </div>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                aria-label="Fermer la notification"
                className="rounded-md p-1 opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
