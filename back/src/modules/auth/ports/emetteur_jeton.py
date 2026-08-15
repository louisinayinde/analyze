import uuid
from abc import ABC, abstractmethod

from modules.auth.domaine.jeton import DonneesAcces, DonneesRefresh, Jetons


class EmetteurJetonPort(ABC):
    """Port du domaine Auth vers l'émission de jetons (C4, C6, agents.md §4, §7).

    Défini dans les termes du métier (émettre une paire de jetons pour un
    utilisateur authentifié, vérifier un refresh présenté), pas dans ceux de
    la techno : aucune mention de JWT ni de PyJWT ici. Le format concret est
    un détail d'implémentation de l'adaptateur (`EmetteurJWT`), remplaçable
    sans toucher au domaine ni aux use-cases (`ConnecterUtilisateur`,
    `RafraichirJetons`) si le standard change un jour.

    Une seule méthode d'émission, volontairement : `expires_in` (durée de
    vie de l'access token) doit rester cohérent avec la durée réellement
    encodée dans le jeton. Séparer « émettre l'access token » et « émettre
    le refresh token » en deux appels aurait obligé le use-case à connaître
    aussi cette durée pour construire `Jetons` — une même connaissance
    dupliquée entre l'adaptateur et l'appelant (agents.md §1, DRY).

    Méthodes synchrones et volontairement pas async : contrairement à
    `DépôtUtilisateurPort`, il n'y a ici aucune I/O réseau, et contrairement
    à `HacheurMotDePassePort`, le coût CPU d'une signature/vérification HMAC
    est négligeable (pas besoin de la décharger via `asyncio.to_thread`).
    """

    @abstractmethod
    def emettre_jetons(self, id_utilisateur: uuid.UUID) -> Jetons:
        """Émet un access token (courte durée) et un refresh token pour cet utilisateur.

        `id_utilisateur` est le seul identifiant transmis : aucune PII
        (email compris) ne doit se retrouver dans les claims (agents.md §7).
        """
        ...

    @abstractmethod
    def decoder_refresh(self, refresh_token: str) -> DonneesRefresh:
        """Vérifie un refresh token présenté par le client et retourne son contenu (C6).

        Vérifie la signature (`alg` restreint à l'allowlist épinglée, jamais
        celui prétendu par le jeton — même défense qu'à l'émission), la
        non-expiration, et que le claim `type` vaut bien `refresh` (un
        access token présenté ici doit être rejeté, pas accepté par erreur).
        Lève `NonAuthentifie` pour n'importe laquelle de ces raisons, sans
        jamais distinguer laquelle dans le message (agents.md §7 — un seul
        chemin d'échec, pas d'oracle).
        """
        ...

    @abstractmethod
    def decoder_acces(self, access_token: str) -> DonneesAcces:
        """Vérifie un access token présenté sur une route protégée et retourne son contenu (C7).

        Même défense qu'à `decoder_refresh` : signature vérifiée contre
        l'allowlist `alg` épinglée, expiration contrôlée, claim `type` qui
        doit valoir `access` (un refresh token présenté ici doit être
        rejeté — l'inverse du contrôle déjà fait par `decoder_refresh`).
        Lève `NonAuthentifie` pour n'importe laquelle de ces raisons, sans
        jamais distinguer laquelle (agents.md §7).

        Contrairement à `decoder_refresh`, aucune vérification en base
        derrière : l'access token est volontairement stateless (courte
        durée de vie, voir `shared/config.py`), pas de round-trip DB sur
        chaque requête authentifiée (agents.md §2, §8).
        """
        ...
