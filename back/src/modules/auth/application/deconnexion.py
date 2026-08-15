from datetime import UTC, datetime

from modules.auth.ports.depot_refresh_token import DépôtRefreshTokenPort
from modules.auth.ports.emetteur_jeton import EmetteurJetonPort
from shared.errors import NonAuthentifie


class DeconnecterUtilisateur:
    """Use-case Déconnexion (C7, agents.md §4, §7).

    Révoque uniquement le refresh token présenté, jamais toute sa famille :
    contrairement au rejeu (C6), une déconnexion volontaire n'est pas un
    signal de vol — `RafraichirJetons.executer` reste le seul appelant de
    `revoquer_famille`.

    Idempotent par construction : un refresh déjà invalide, expiré ou
    inconnu ne fait pas échouer la déconnexion. Le client qui se déconnecte
    a déjà obtenu ce qu'il voulait (ne plus être authentifié) ; renvoyer une
    erreur ici n'apporterait rien et romprait sans raison la symétrie avec
    les autres endpoints stateless de ce module. Ni PyJWT ni SQLAlchemy ne
    sont importés ici — ce fichier ne connaît que des ports (agents.md §4).
    """

    def __init__(self, emetteur: EmetteurJetonPort, depot_refresh: DépôtRefreshTokenPort) -> None:
        self._emetteur = emetteur
        self._depot_refresh = depot_refresh

    async def executer(self, refresh_token: str) -> None:
        try:
            donnees = self._emetteur.decoder_refresh(refresh_token)
        except NonAuthentifie:
            return

        await self._depot_refresh.revoquer(donnees.jti, datetime.now(UTC))
