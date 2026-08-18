import { setAccessToken } from "./token-store";

// Appelle nos propres Route Handlers (app/api/auth/*), jamais le backend
// FastAPI directement (J3, backlog.md) — c'est ce Route Handler qui détient
// le refresh token via son cookie httpOnly, le navigateur ne le voit jamais.
//
// Forme de retour volontairement identique à celle attendue par `unwrap`
// (shared/api/client.ts) : `data`/`error`/`response`. Ça permet à un écran
// (ex. app/connexion/page.tsx) de réutiliser tel quel `useApiRequest()` —
// même gestion d'erreur/toast que pour tout appel API générique (I5), sans
// dupliquer cette logique ici (agents.md §1, DRY).

type JetonReponse = { expiresIn: number };
type ResultatAppel<T> = { data?: T; error?: unknown; response: Response };

async function appeler<T extends { expiresIn: number } | undefined>(
  chemin: string,
  corps?: unknown,
): Promise<ResultatAppel<T>> {
  const reponse = await fetch(chemin, {
    method: "POST",
    headers: corps !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: corps !== undefined ? JSON.stringify(corps) : undefined,
  });

  if (reponse.status === 204) {
    setAccessToken(null);
    return { data: undefined as T, response: reponse };
  }

  const donnees = await reponse.json().catch(() => undefined);

  if (!reponse.ok) {
    setAccessToken(null);
    return { error: donnees, response: reponse };
  }

  setAccessToken(donnees.access_token);
  return { data: { expiresIn: donnees.expires_in } as T, response: reponse };
}

export function connecter(email: string, motDePasse: string): Promise<ResultatAppel<JetonReponse>> {
  return appeler<JetonReponse>("/api/auth/connexion", { email, mot_de_passe: motDePasse });
}

export function rafraichir(): Promise<ResultatAppel<JetonReponse>> {
  return appeler<JetonReponse>("/api/auth/refresh");
}

export function deconnecter(): Promise<ResultatAppel<undefined>> {
  return appeler<undefined>("/api/auth/deconnexion");
}

export type { JetonReponse, ResultatAppel };
