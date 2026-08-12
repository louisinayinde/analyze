"use client";

import { useEffect, useState } from "react";

type HealthStatus = "loading" | "ok" | "error";

export default function Home() {
  const [status, setStatus] = useState<HealthStatus>("loading");

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;

    fetch(`${apiUrl}/health`)
      .then((res) => setStatus(res.ok ? "ok" : "error"))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 bg-zinc-50 font-sans dark:bg-black">
      <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">
        Analyse-moi ça
      </h1>
      <p className="text-lg text-zinc-600 dark:text-zinc-400">
        Statut backend :{" "}
        <span
          className={
            status === "ok"
              ? "text-green-600 dark:text-green-400"
              : status === "error"
                ? "text-red-600 dark:text-red-400"
                : "text-zinc-500"
          }
        >
          {status === "loading" ? "vérification..." : status === "ok" ? "OK" : "indisponible"}
        </span>
      </p>
    </div>
  );
}
