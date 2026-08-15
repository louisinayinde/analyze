from datetime import UTC, datetime

from modules.auth.domaine.enregistrement_refresh import EnregistrementRefresh
from modules.auth.domaine.jeton import Jetons, RefreshTokenRejoue
from modules.auth.ports.depot_refresh_token import DépôtRefreshTokenPort
from modules.auth.ports.emetteur_jeton import EmetteurJetonPort
from shared.errors import NonAuthentifie

# Même principe qu'à la connexion (C4) : un seul message, quelle que soit la
# cause exacte (jeton structurellement invalide, `jti` inconnu en base) —
# pas d'oracle distinguant les deux (agents.md §7).
_MESSAGE_ECHEC_GENERIQUE = "Refresh token invalide ou expiré."


class RafraichirJetons:
    """Use-case Refresh rotatif (C6, agents.md §4, §7).

    Implémente la rotation avec détection de rejeu (pattern standard, voir
    OWASP « Refresh Token Automatic Reuse Detection ») :

    1. Le refresh présenté est décodé/vérifié par `EmetteurJetonPort`
       (signature, `alg` allowlist, expiration, claim `type`) — un jeton
       structurellement invalide échoue ici, avant tout accès au dépôt.
    2. Son `jti` est recherché dans `DépôtRefreshTokenPort`. Absent : refuse
       (générique, pas d'alerte — pas de famille identifiable à révoquer).
    3. Trouvé mais déjà **utilisé ou révoqué** : c'est un rejeu. Toute sa
       famille est révoquée d'un coup et `RefreshTokenRejoue` est levée
       (agents.md §7 — un vol de refresh token compromet toute la chaîne de
       rotation, pas seulement le jeton rejoué).
    4. Trouvé et valide : chemin nominal. Il est marqué utilisé, une
       nouvelle paire est émise dans la **même famille**, et le nouveau
       refresh est persisté à son tour.

    Orchestration pure : ni PyJWT ni SQLAlchemy ne sont importés ici — ce
    fichier ne connaît que des ports (agents.md §4).
    """

    def __init__(self, emetteur: EmetteurJetonPort, depot_refresh: DépôtRefreshTokenPort) -> None:
        self._emetteur = emetteur
        self._depot_refresh = depot_refresh

    async def executer(self, refresh_token: str) -> Jetons:
        donnees = self._emetteur.decoder_refresh(refresh_token)

        enregistrement = await self._depot_refresh.trouver_par_jti(donnees.jti)
        if enregistrement is None:
            raise NonAuthentifie(_MESSAGE_ECHEC_GENERIQUE)

        maintenant = datetime.now(UTC)

        if not enregistrement.est_valide:
            # Rejeu : ce `jti` a déjà été consommé par une rotation
            # antérieure (ou déjà révoqué par un rejeu précédent sur cette
            # même famille) et est pourtant représenté — signal fort de vol
            # du refresh token. `revoquer_famille` est idempotente (voir
            # `DépôtRefreshTokenPostgres`), donc sûre à rappeler même si la
            # famille est déjà révoquée.
            await self._depot_refresh.revoquer_famille(enregistrement.family_id, maintenant)
            raise RefreshTokenRejoue(enregistrement.user_id, enregistrement.family_id)

        await self._depot_refresh.marquer_utilise(enregistrement.jti, maintenant)

        jetons = self._emetteur.emettre_jetons(enregistrement.user_id)

        await self._depot_refresh.creer(
            EnregistrementRefresh(
                jti=jetons.refresh_jti,
                # Même famille que le jeton consommé : c'est ce qui permet
                # de révoquer toute la chaîne d'un coup en cas de rejeu
                # futur, plutôt qu'un seul maillon.
                family_id=enregistrement.family_id,
                user_id=enregistrement.user_id,
                created_at=maintenant,
                expires_at=jetons.refresh_expires_at,
            )
        )

        return jetons
