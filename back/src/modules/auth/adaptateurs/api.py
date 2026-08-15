import logging
import uuid
from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from modules.auth.application.connexion import ConnecterUtilisateur
from modules.auth.application.deconnexion import DeconnecterUtilisateur
from modules.auth.application.inscription import InscrireUtilisateur
from modules.auth.application.rafraichir_jetons import RafraichirJetons
from modules.auth.domaine.jeton import Jetons, RefreshTokenRejoue
from modules.auth.domaine.utilisateur import Utilisateur
from modules.auth.ports.depot_refresh_token import DépôtRefreshTokenPort
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from modules.auth.ports.emetteur_jeton import EmetteurJetonPort
from modules.auth.ports.hacheur_mot_de_passe import HacheurMotDePassePort
from shared.errors import ErreurDomaine, NonAuthentifie

# Adaptateur d'entrée (driving adapter, agents.md §4) : seul fichier du
# module Auth qui connaît FastAPI. Traduit HTTP <-> cas d'usage (C3, C4),
# eux-mêmes ignorants du framework. Câblé au point de composition via
# `index.py` (composition/app.py, C5).
router = APIRouter(prefix="/auth", tags=["auth"])

# `auto_error=False` : sans jeton présenté, on lève nous-mêmes
# `NonAuthentifie` (voir `get_current_user`) pour rester dans l'enveloppe
# d'erreur unique du module (`ErreurAPI`, C7) plutôt que de laisser
# FastAPI renvoyer son propre 403 générique, incohérent avec le reste de
# l'API (agents.md §7 — un seul format d'erreur d'auth).
_bearer_scheme = HTTPBearer(auto_error=False)

# Un seul logger dédié aux événements métier d'auth, distinct du logger
# "http" de CorrelationIdMiddleware (shared/correlation.py) qui journalise
# déjà chaque requête : ici, ce sont des événements d'audit métier
# (connexion, échec...), pas la mécanique HTTP (agents.md §7, §9).
_logger = logging.getLogger("auth")


class InscriptionRequete(BaseModel):
    email: str
    mot_de_passe: str


class ConnexionRequete(BaseModel):
    # Type `str` volontairement, pas `EmailStr` : un format malformé doit
    # suivre exactement le même chemin d'échec générique qu'un mot de passe
    # incorrect (voir le commentaire dans `ConnecterUtilisateur.executer`) —
    # une validation de format ici court-circuiterait ce choix (agents.md
    # §7, pas d'oracle de format distinct du chemin d'échec générique).
    email: str
    mot_de_passe: str


class RafraichissementRequete(BaseModel):
    refresh_token: str


class DeconnexionRequete(BaseModel):
    refresh_token: str


class UtilisateurReponse(BaseModel):
    """Ne reprend jamais `password_hash` : un hash n'a rien à faire dans une réponse API."""

    id: uuid.UUID
    email: str
    created_at: datetime

    @classmethod
    def depuis_domaine(cls, utilisateur: Utilisateur) -> "UtilisateurReponse":
        return cls(id=utilisateur.id, email=utilisateur.email, created_at=utilisateur.created_at)


class JetonsReponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str

    @classmethod
    def depuis_domaine(cls, jetons: Jetons) -> "JetonsReponse":
        return cls(
            access_token=jetons.access_token,
            refresh_token=jetons.refresh_token,
            expires_in=jetons.expires_in,
            token_type=jetons.token_type,
        )


def _inscrire_utilisateur(request: Request) -> InscrireUtilisateur:
    # Résolu à chaque requête (et non une fois à la création du router) :
    # `DépôtUtilisateurPort` n'est câblé qu'au lifespan de l'app
    # (composition/app.py), après le montage des routers.
    registry = request.app.state.registry
    return InscrireUtilisateur(
        depot=registry.resolve(DépôtUtilisateurPort),
        hacheur=registry.resolve(HacheurMotDePassePort),
    )


def _connecter_utilisateur(request: Request) -> ConnecterUtilisateur:
    registry = request.app.state.registry
    return ConnecterUtilisateur(
        depot=registry.resolve(DépôtUtilisateurPort),
        hacheur=registry.resolve(HacheurMotDePassePort),
        emetteur=registry.resolve(EmetteurJetonPort),
        depot_refresh=registry.resolve(DépôtRefreshTokenPort),
    )


def _rafraichir_jetons(request: Request) -> RafraichirJetons:
    registry = request.app.state.registry
    return RafraichirJetons(
        emetteur=registry.resolve(EmetteurJetonPort),
        depot_refresh=registry.resolve(DépôtRefreshTokenPort),
    )


def _deconnecter_utilisateur(request: Request) -> DeconnecterUtilisateur:
    registry = request.app.state.registry
    return DeconnecterUtilisateur(
        emetteur=registry.resolve(EmetteurJetonPort),
        depot_refresh=registry.resolve(DépôtRefreshTokenPort),
    )


def _emetteur_jeton(request: Request) -> EmetteurJetonPort:
    # `cast`, pas juste `return registry.resolve(...)` : `app.state` est
    # dynamiquement typé (`Any`) côté Starlette, donc `resolve(...)` l'est
    # aussi ici — même idiome que `Registry.resolve` lui-même
    # (composition/registry.py), seul autre endroit qui a besoin d'un cast
    # explicite pour ce même motif.
    return cast(EmetteurJetonPort, request.app.state.registry.resolve(EmetteurJetonPort))


async def get_current_user(
    identifiants: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    emetteur: EmetteurJetonPort = Depends(_emetteur_jeton),
) -> uuid.UUID:
    """Dépendance FastAPI réutilisable pour protéger une route authentifiée (C7).

    Décode et vérifie l'access token du header `Authorization: Bearer`, et
    retourne l'identifiant de l'utilisateur — jamais l'entité `Utilisateur`
    complète : les routes protégées à venir (D, H) ont besoin de scoper
    leurs requêtes par `user_id` (agents.md §7 — le tenant vient du contexte
    authentifié, jamais d'un paramètre de requête), pas de connaître le
    reste du profil. Aucun accès au dépôt utilisateur ici : l'access token
    est volontairement stateless (voir `EmetteurJetonPort.decoder_acces`),
    donc pas de round-trip DB sur chaque requête protégée (agents.md §2, §8).

    Utilisation dans un autre module (jamais en important `adaptateurs.api`
    directement, toujours via la surface publique du module — agents.md §4) :

        from modules.auth.index import get_current_user

        @router.get("/ressource")
        async def route(user_id: uuid.UUID = Depends(get_current_user)) -> ...:
            ...
    """
    if identifiants is None:
        raise NonAuthentifie()

    donnees = emetteur.decoder_acces(identifiants.credentials)
    return donnees.user_id


@router.post(
    "/inscription",
    response_model=UtilisateurReponse,
    status_code=status.HTTP_201_CREATED,
)
async def inscription(
    corps: InscriptionRequete,
    use_case: InscrireUtilisateur = Depends(_inscrire_utilisateur),
) -> UtilisateurReponse:
    try:
        utilisateur = await use_case.executer(corps.email, corps.mot_de_passe)
    except ErreurDomaine as exc:
        # Le `code` stable de l'exception est loggé (utile pour détecter un
        # abus, ex. rafale de `conflit_ressource`) ; jamais le détail exposé
        # au client, qui reste le message générique déjà décidé en C3
        # (agents.md §7). Le formatage de la réponse HTTP elle-même reste
        # centralisé côté B4 (composition/app.py) : on ne fait que logger
        # ici avant de laisser l'exception remonter telle quelle.
        _logger.info("inscription_echouee", extra={"code": exc.code})
        raise

    _logger.info("inscription_reussie", extra={"user_id": str(utilisateur.id)})
    return UtilisateurReponse.depuis_domaine(utilisateur)


@router.post("/connexion", response_model=JetonsReponse)
async def connexion(
    corps: ConnexionRequete,
    use_case: ConnecterUtilisateur = Depends(_connecter_utilisateur),
) -> JetonsReponse:
    try:
        jetons = await use_case.executer(corps.email, corps.mot_de_passe)
    except ErreurDomaine as exc:
        # Même principe qu'à l'inscription : `code` seul en log (ex.
        # `non_authentifie`), jamais la distinction email inconnu / mot de
        # passe incorrect — le use-case (C4) ne la préserve déjà plus en
        # amont, précisément pour ne laisser aucun canal (réponse, log
        # accessible côté client) la révéler.
        _logger.info("connexion_echouee", extra={"code": exc.code})
        raise

    # Pas d'id utilisateur en clair ici : le récupérer nécessiterait de
    # décoder le JWT tout juste émis, une dépendance à un détail
    # d'implémentation de l'adaptateur JWT que ce routeur ne doit pas
    # connaître (agents.md §4). Le correlation_id (shared/correlation.py)
    # suffit à relier cet événement à la requête HTTP complète.
    _logger.info("connexion_reussie")
    return JetonsReponse.depuis_domaine(jetons)


@router.post("/refresh", response_model=JetonsReponse)
async def refresh(
    corps: RafraichissementRequete,
    use_case: RafraichirJetons = Depends(_rafraichir_jetons),
) -> JetonsReponse:
    try:
        jetons = await use_case.executer(corps.refresh_token)
    except RefreshTokenRejoue as exc:
        # Log dédié, distinct du log générique ci-dessous (agents.md §7,
        # ticket C6) : un refresh rejoué signale un vol probable du refresh
        # token (famille déjà révoquée par le use-case à ce stade) — un
        # `WARNING` avec `user_id`/`family_id` en clair, jamais renvoyés au
        # client (`ErreurAPI` ne sérialise que `.code`/`.message`), pour
        # permettre l'investigation côté serveur (agents.md §9 : alerter sur
        # un symptôme qui touche l'utilisateur).
        _logger.warning(
            "refresh_rejoue_alerte",
            extra={
                "code": exc.code,
                "user_id": str(exc.user_id),
                "family_id": str(exc.family_id),
            },
        )
        raise
    except ErreurDomaine as exc:
        # Chemin d'échec ordinaire (jeton expiré, signature invalide,
        # `jti` inconnu...) : même niveau que `connexion_echouee`, aucune
        # distinction de la cause exacte dans le log (agents.md §7).
        _logger.info("refresh_echoue", extra={"code": exc.code})
        raise

    _logger.info("refresh_reussi")
    return JetonsReponse.depuis_domaine(jetons)


@router.post("/deconnexion", status_code=status.HTTP_204_NO_CONTENT)
async def deconnexion(
    corps: DeconnexionRequete,
    use_case: DeconnecterUtilisateur = Depends(_deconnecter_utilisateur),
) -> None:
    # Pas de try/except ici : le use-case (C7) est idempotent par
    # construction, il ne lève jamais sur un refresh déjà invalide — voir
    # `DeconnecterUtilisateur.executer`. Toujours 204, comme le veut la
    # sémantique d'un logout (le client obtient ce qu'il voulait, que le
    # jeton présenté ait pu être révoqué ou non).
    await use_case.executer(corps.refresh_token)
    _logger.info("deconnexion_reussie")
