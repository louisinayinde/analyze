// Hiérarchie d'erreurs normalisée pour tout appel API (I5, backlog.md).
// `ApiError` porte le `code`/`message` déjà décidés par le backend
// (shared/errors.py côté back : `message` est déjà la version destinée à
// l'utilisateur, jamais reformulée ici — agents.md §1 DRY, une seule
// source de vérité pour le texte d'erreur). `ApiNetworkError` et
// `ApiTimeoutError` couvrent les deux cas où le backend n'a justement pas
// pu répondre, donc où aucun message serveur n'existe (agents.md §3 :
// timeouts explicites sur chaque appel externe).

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly correlationId: string;

  constructor(message: string, code: string, status: number, correlationId: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.correlationId = correlationId;
  }
}

export class ApiNetworkError extends Error {
  constructor(message = "Impossible de contacter le serveur. Vérifie ta connexion.") {
    super(message);
    this.name = "ApiNetworkError";
  }
}

export class ApiTimeoutError extends Error {
  constructor(message = "Le serveur met trop de temps à répondre.") {
    super(message);
    this.name = "ApiTimeoutError";
  }
}

export type ApiRequestError = ApiError | ApiNetworkError | ApiTimeoutError;
