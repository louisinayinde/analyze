"use client";

import { useState } from "react";
import { Button, buttonVariants, useToast } from "@/shared/ui";

// Partage du résultat (K4, backlog.md). Liens `http` bruts vers chaque
// réseau plutôt qu'un SDK de partage : trois URL d'intent ne justifient pas
// une dépendance (agents.md §2 — une dépendance = une dette).
const MESSAGE_PARTAGE = "Regarde ce que l'IA a dit de moi sur Analyse-moi ça";

function construireLiensPartage(url: string, texte: string) {
  const urlEncodee = encodeURIComponent(url);
  const texteEncode = encodeURIComponent(texte);
  return {
    x: `https://twitter.com/intent/tweet?url=${urlEncodee}&text=${texteEncode}`,
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${urlEncodee}`,
    whatsapp: `https://wa.me/?text=${texteEncode}%20${urlEncodee}`,
  };
}

export function PartageResultat({ url }: { url: string }) {
  const { toast } = useToast();
  const [copieEnCours, setCopieEnCours] = useState(false);
  const liens = construireLiensPartage(url, MESSAGE_PARTAGE);

  async function copierLeLien() {
    setCopieEnCours(true);
    try {
      await navigator.clipboard.writeText(url);
      toast({ title: "Lien copié", variant: "success" });
    } catch {
      // Presse-papiers refusé par le navigateur (permission, contexte non
      // sécurisé) — cas rare en HTTPS moderne, on informe plutôt que de
      // silencieusement échouer.
      toast({
        title: "Impossible de copier le lien",
        description: "Sélectionne-le manuellement dans la barre d'adresse.",
        variant: "destructive",
      });
    } finally {
      setCopieEnCours(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium text-foreground">Partager ce résultat</p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          loading={copieEnCours}
          onClick={copierLeLien}
        >
          Copier le lien
        </Button>
        <a
          href={liens.x}
          target="_blank"
          rel="noopener noreferrer"
          className={buttonVariants("outline", "sm")}
        >
          Partager sur X
        </a>
        <a
          href={liens.linkedin}
          target="_blank"
          rel="noopener noreferrer"
          className={buttonVariants("outline", "sm")}
        >
          Partager sur LinkedIn
        </a>
        <a
          href={liens.whatsapp}
          target="_blank"
          rel="noopener noreferrer"
          className={buttonVariants("outline", "sm")}
        >
          Partager sur WhatsApp
        </a>
      </div>
    </div>
  );
}
