import asyncio
import uuid

from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from modules.auth.ports.hacheur_mot_de_passe import HacheurMotDePassePort
from shared.errors import NonAuthentifie

# Même message générique que `ConnecterUtilisateur` (C4) : un mot de passe
# incorrect à la suppression suit le même chemin d'échec qu'un mot de passe
# incorrect à la connexion, sans distinction (agents.md §7).
_MESSAGE_ECHEC_GENERIQUE = "Mot de passe incorrect."


class SupprimerCompte:
    """Use-case Compte (H3, agents.md §7).

    Supprimer un compte est une action sensible et irréversible : `user_id`
    (issu du JWT, jamais d'un paramètre de requête) ne suffit pas à
    l'autoriser seul — une vérification renforcée (step-up, agents.md §7 :
    « concevoir la récupération de compte aussi soigneusement que le
    login ») redemande le mot de passe en clair avant toute suppression,
    pour qu'un access token intercepté ou laissé ouvert sur un poste
    partagé ne suffise pas à effacer le compte de sa victime.

    Ne connaît que des ports, jamais SQLAlchemy/Argon2 (agents.md §4).
    """

    def __init__(self, depot: DépôtUtilisateurPort, hacheur: HacheurMotDePassePort) -> None:
        self._depot = depot
        self._hacheur = hacheur

    async def executer(self, user_id: uuid.UUID, mot_de_passe: str) -> None:
        utilisateur = await self._depot.trouver_par_id(user_id)
        if utilisateur is None:
            # Cas limite (compte déjà supprimé entre l'émission du JWT et
            # cette requête) : même exception que le mot de passe incorrect,
            # aucun canal pour distinguer les deux (agents.md §7).
            raise NonAuthentifie(_MESSAGE_ECHEC_GENERIQUE)

        # `to_thread` : même raisonnement que `ConnecterUtilisateur` (C4) —
        # Argon2id est du calcul CPU pur, bloquant pour la boucle asyncio.
        mot_de_passe_valide = await asyncio.to_thread(
            self._hacheur.verifier, mot_de_passe, utilisateur.password_hash
        )
        if not mot_de_passe_valide:
            raise NonAuthentifie(_MESSAGE_ECHEC_GENERIQUE)

        await self._depot.supprimer(user_id)
