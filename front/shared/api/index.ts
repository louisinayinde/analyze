// Surface publique du module `api` — aucun autre module ne doit importer
// `schema.gen.ts`, `client.ts` ou `use-api-request.ts` directement
// (agents.md §4). `schema.gen.ts` est régénéré depuis le contrat OpenAPI du
// backend (H2, backlog.md ; voir scripts/generate-api-client.sh) et écrasé
// à chaque régénération.

export type { components, operations, paths } from "./schema.gen";

// I5 (backlog.md) : wrapper autour du client généré — gestion uniforme des
// erreurs réseau/timeouts et affichage via Toast.
export { apiClient, unwrap } from "./client";
export { ApiError, ApiNetworkError, ApiTimeoutError } from "./errors";
export type { ApiRequestError } from "./errors";
export { useApiRequest } from "./use-api-request";
