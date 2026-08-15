import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from modules.auth.domaine.jeton import DonneesAcces, DonneesRefresh, Jetons
from modules.auth.ports.emetteur_jeton import EmetteurJetonPort
from shared.errors import NonAuthentifie

# Algorithme unique, choisi ici et nulle part ailleurs. Le pinner en dur (au
# lieu de le lire depuis un header ou une config) élimine par construction
# la classe de vulnérabilité "alg confusion" (dont `alg: none`) : un jeton
# entrant ne peut être vérifié qu'avec cet algorithme précis, jamais celui
# qu'il prétend utiliser (agents.md §7 — allowlist, pas de confiance dans
# l'entrée). `ALGORITHMES_AUTORISES` est l'allowlist explicite réutilisée
# telle quelle par `_decoder_claims`, commun à `decoder_refresh` (C6) et
# `decoder_acces` (C7) : `jwt.decode(..., algorithms=ALGORITHMES_AUTORISES)`,
# jamais `jwt.get_unverified_header(...)["alg"]`.
ALGORITHME = "HS256"
ALGORITHMES_AUTORISES = (ALGORITHME,)

_TYPE_ACCES = "access"
_TYPE_REFRESH = "refresh"

# Message unique, quelle que soit la cause réelle (signature invalide,
# expiré, mauvais `type`, `jti` malformé) : même principe qu'à la connexion
# (C4) — un seul chemin d'échec, pas d'oracle distinguant la raison exacte
# (agents.md §7).
_MESSAGE_REFRESH_INVALIDE = "Refresh token invalide ou expiré."
# Même principe pour l'access token (C7), message distinct pour ne pas
# faire croire à un problème de refresh sur une route protégée.
_MESSAGE_ACCES_INVALIDE = "Jeton d'accès invalide ou expiré."


class EmetteurJWT(EmetteurJetonPort):
    """Adaptateur JWT du port `EmetteurJetonPort` (C4, C6, agents.md §7).

    Via PyJWT (bindings vers une implémentation JWT éprouvée) — pas de
    format de jeton maison. Claims minimaux et sans PII : `sub` (id
    utilisateur), `type` (distingue access/refresh — un refresh ne doit pas
    pouvoir être accepté comme un access token par une route protégée),
    `iat`/`exp`, `jti` (identifiant unique du jeton, réutilisé tel quel par
    C6 pour la persistance de rotation — voir `EnregistrementRefresh` —
    sans qu'aucun claim supplémentaire n'ait dû être ajouté au jeton
    lui-même).
    """

    def __init__(
        self, cle_signature: str, duree_access: timedelta, duree_refresh: timedelta
    ) -> None:
        self._cle_signature = cle_signature
        self._duree_access = duree_access
        self._duree_refresh = duree_refresh

    def emettre_jetons(self, id_utilisateur: uuid.UUID) -> Jetons:
        maintenant = datetime.now(UTC)
        refresh_jti = uuid.uuid4()
        refresh_expires_at = maintenant + self._duree_refresh
        return Jetons(
            access_token=self._encoder(
                id_utilisateur, maintenant, self._duree_access, _TYPE_ACCES, uuid.uuid4()
            ),
            refresh_token=self._encoder(
                id_utilisateur, maintenant, self._duree_refresh, _TYPE_REFRESH, refresh_jti
            ),
            expires_in=int(self._duree_access.total_seconds()),
            refresh_jti=refresh_jti,
            refresh_expires_at=refresh_expires_at,
        )

    def decoder_refresh(self, refresh_token: str) -> DonneesRefresh:
        claims = self._decoder_claims(refresh_token, _TYPE_REFRESH, _MESSAGE_REFRESH_INVALIDE)
        try:
            return DonneesRefresh(user_id=uuid.UUID(claims["sub"]), jti=uuid.UUID(claims["jti"]))
        except (KeyError, ValueError) as exc:
            # `sub`/`jti` absents ou mal formés : ne peut arriver qu'avec un
            # jeton correctement signé par notre propre clé mais aux claims
            # incohérents (bug interne) ou falsifié après coup sans succès —
            # dans tous les cas, même chemin d'échec générique.
            raise NonAuthentifie(_MESSAGE_REFRESH_INVALIDE) from exc

    def decoder_acces(self, access_token: str) -> DonneesAcces:
        claims = self._decoder_claims(access_token, _TYPE_ACCES, _MESSAGE_ACCES_INVALIDE)
        try:
            return DonneesAcces(user_id=uuid.UUID(claims["sub"]))
        except (KeyError, ValueError) as exc:
            raise NonAuthentifie(_MESSAGE_ACCES_INVALIDE) from exc

    def _decoder_claims(self, token: str, type_attendu: str, message_erreur: str) -> dict[str, Any]:
        """Décodage + vérification communs à `decoder_refresh` et `decoder_acces` (C6, C7).

        Factorisé ici plutôt que dupliqué : même connaissance (vérifier
        signature/alg/exp puis le claim `type`) utilisée par les deux
        méthodes publiques (agents.md §1, DRY).
        """
        try:
            # `algorithms=ALGORITHMES_AUTORISES` (allowlist épinglée en dur,
            # jamais l'`alg` que prétend le jeton) : rejette par construction
            # `alg: none` et toute confusion d'algorithme (agents.md §7).
            # PyJWT vérifie aussi `exp` ici — un jeton expiré échoue avant
            # tout traitement ultérieur par l'appelant.
            claims = jwt.decode(token, self._cle_signature, algorithms=ALGORITHMES_AUTORISES)
        except jwt.InvalidTokenError as exc:
            raise NonAuthentifie(message_erreur) from exc

        if claims.get("type") != type_attendu:
            raise NonAuthentifie(message_erreur)

        return claims

    def _encoder(
        self,
        id_utilisateur: uuid.UUID,
        maintenant: datetime,
        duree: timedelta,
        type_jeton: str,
        jti: uuid.UUID,
    ) -> str:
        claims = {
            "sub": str(id_utilisateur),
            "type": type_jeton,
            "iat": maintenant,
            "exp": maintenant + duree,
            "jti": str(jti),
        }
        return jwt.encode(claims, self._cle_signature, algorithm=ALGORITHME)
