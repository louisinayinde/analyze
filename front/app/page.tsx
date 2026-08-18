"use client";

import { useEffect, useState } from "react";
import { apiClient, useApiRequest } from "@/shared/api";

type HealthStatus = "loading" | "ok" | "error";

export default function Home() {
  const [status, setStatus] = useState<HealthStatus>("loading");
  const request = useApiRequest();

  useEffect(() => {
    request(apiClient.GET("/health"))
      .then(() => setStatus("ok"))
      .catch(() => setStatus("error"));
  }, [request]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-semibold text-foreground">Analyse-moi ça</h1>
      <p className="text-lg text-muted-foreground">
        Statut backend :{" "}
        <span
          className={
            status === "ok"
              ? "text-success"
              : status === "error"
                ? "text-destructive"
                : "text-muted-foreground"
          }
        >
          {status === "loading" ? "vérification..." : status === "ok" ? "OK" : "indisponible"}
        </span>
      </p>
    </div>
  );
}
