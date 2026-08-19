import createClient from "openapi-fetch";
import type { paths } from "./schema.gen";
import { ApiError, ApiNetworkError, ApiTimeoutError } from "./errors";

// Pas de valeur par défaut : même posture que `Settings` côté back
// (shared/config.py) — si la variable manque, on échoue explicitement au
// démarrage plutôt que d'appeler une URL fantôme (agents.md §7).
function requireBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_API_URL est manquant : impossible d'appeler l'API backend.");
  }
  return url;
}

const DEFAULT_TIMEOUT_MS = 10_000;

// Timeout explicite sur l'appel réseau sous-jacent (agents.md §3 : un appel
// sans timeout est un blocage en attente). `AbortSignal.any` combine le
// signal propre à la requête (réservé à une future annulation côté
// appelant, non utilisée aujourd'hui) et notre propre horloge, pour ne
// jamais écraser silencieusement un abort déclenché ailleurs.
async function fetchWithTimeout(request: Request): Promise<Response> {
  const timeoutSignal = AbortSignal.timeout(DEFAULT_TIMEOUT_MS);
  const signal = AbortSignal.any([request.signal, timeoutSignal]);

  try {
    return await fetch(request, { signal });
  } catch (error) {
    if (timeoutSignal.aborted) {
      throw new ApiTimeoutError();
    }
    // `fetch` rejette avec un `TypeError` pour tout échec réseau (DNS,
    // connexion refusée, CORS) — jamais pour une réponse HTTP d'erreur,
    // qui arrive normalement jusqu'à `openapi-fetch` (spec fetch).
    if (error instanceof TypeError) {
      throw new ApiNetworkError();
    }
    throw error;
  }
}

// Client généré (H2, backlog.md) : `paths` vient de `schema.gen.ts`, donc
// toute route/paramètre/schéma appelé ici est vérifié à la compilation
// contre le contrat OpenAPI réel du backend.
export const apiClient = createClient<paths>({
  baseUrl: requireBaseUrl(),
  fetch: fetchWithTimeout,
});

type ErreurAPIBody = { code: string; message: string; correlation_id: string };

function estErreurAPI(value: unknown): value is ErreurAPIBody {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Record<string, unknown>).code === "string" &&
    typeof (value as Record<string, unknown>).message === "string" &&
    typeof (value as Record<string, unknown>).correlation_id === "string"
  );
}

// Normalise un appel `apiClient.GET/POST/...` : `data` en cas de succès,
// sinon une `ApiError` construite à partir du corps `ErreurAPI` renvoyé par
// le backend (shared/errors.py — même forme partout, agents.md §3). Les
// erreurs de validation FastAPI par défaut (422 `HTTPValidationError`, pas
// encore uniformisées côté back) retombent sur un message générique plutôt
// que de faire planter l'appelant sur une forme inattendue.
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;

  if (error !== undefined) {
    if (estErreurAPI(error)) {
      throw new ApiError(error.message, error.code, response.status, error.correlation_id);
    }
    throw new ApiError(
      "La requête n'a pas pu être traitée.",
      "entree_invalide",
      response.status,
      response.headers.get("x-correlation-id") ?? "",
    );
  }

  // `204 No Content` : `data` vaut légitimement `undefined` en cas de succès
  // (aucun corps à parser) — openapi-fetch ne le distingue pas autrement
  // d'un corps manquant à tort (voir `coreFetch`, openapi-fetch/src/index.js).
  // Même traitement que `appeler()` (features/auth/auth-client.ts) pour ce
  // même statut, côté Route Handler.
  if (response.status === 204) {
    return undefined as T;
  }

  if (data === undefined) {
    throw new ApiError(
      "Réponse vide inattendue du serveur.",
      "reponse_invalide",
      response.status,
      response.headers.get("x-correlation-id") ?? "",
    );
  }

  return data;
}
