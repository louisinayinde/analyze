import asyncio
import uuid
from datetime import UTC, datetime

from email_validator import EmailNotValidError, validate_email

from modules.auth.domaine.mot_de_passe import valider_robustesse
from modules.auth.domaine.utilisateur import Utilisateur
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from modules.auth.ports.hacheur_mot_de_passe import HacheurMotDePassePort
from shared.errors import ConflitRessource, EntreeInvalide

# Volontairement vague : ne confirme jamais explicitement qu'un compte
# existe déjà avec cet email (agents.md §7 — pas d'énumération
# d'utilisateurs). Le détail réel du conflit reste dans l'exception
# capturée plus bas, jamais exposé tel quel côté API.
_MESSAGE_ECHEC_GENERIQUE = "Impossible de créer le compte avec ces informations."


class InscrireUtilisateur:
    """Use-case Inscription (C3, agents.md §4, §7).

    Orchestration pure : valide les entrées, hache le mot de passe via le
    port `HacheurMotDePassePort` puis persiste via `DépôtUtilisateurPort`.
    Ni argon2 ni SQLAlchemy ne sont importés ici — ce fichier ne connaît que
    des ports, remplaçables sans le modifier (agents.md §4).
    """

    def __init__(self, depot: DépôtUtilisateurPort, hacheur: HacheurMotDePassePort) -> None:
        self._depot = depot
        self._hacheur = hacheur

    async def executer(self, email: str, mot_de_passe: str) -> Utilisateur:
        email_normalise = _valider_et_normaliser_email(email)
        valider_robustesse(mot_de_passe, email_normalise)

        # Hash calculé avant tout accès au dépôt, y compris pour un email
        # déjà pris : le coût CPU d'Argon2id (dominant, largement supérieur
        # à celui d'un SELECT/INSERT) est ainsi payé de façon quasi
        # identique sur les deux chemins, pour ne pas laisser le temps de
        # réponse trahir si l'email existe déjà (agents.md §7 — pas
        # d'énumération, y compris par timing).
        # `to_thread` : le hachage est du calcul CPU pur (pas d'I/O), donc
        # bloquant pour la boucle d'événements asyncio s'il est appelé
        # directement (agents.md §8 — ne pas dégrader tout le reste de
        # l'API pendant qu'une inscription hache son mot de passe).
        hash_mot_de_passe = await asyncio.to_thread(self._hacheur.hacher, mot_de_passe)

        utilisateur = Utilisateur(
            id=uuid.uuid4(),
            email=email_normalise,
            password_hash=hash_mot_de_passe,
            created_at=datetime.now(UTC),
        )

        try:
            return await self._depot.creer(utilisateur)
        except ConflitRessource as exc:
            raise ConflitRessource(_MESSAGE_ECHEC_GENERIQUE) from exc


def _valider_et_normaliser_email(email: str) -> str:
    try:
        # `check_deliverability=False` : pas de résolution DNS ici. Un appel
        # réseau externe à ce stade ajouterait une dépendance distribuée non
        # couverte par timeout/retry (agents.md §3) pour un gain marginal —
        # la validation syntaxique suffit à ce ticket.
        resultat = validate_email(email, check_deliverability=False)
    except EmailNotValidError as exc:
        raise EntreeInvalide("L'adresse email n'est pas valide.") from exc
    # Email stocké en minuscules pour éviter les doublons de compte via une
    # simple variation de casse (ex. `Foo@Bar.com` vs `foo@bar.com`) : choix
    # pragmatique majoritaire côté fournisseurs, malgré la sensibilité à la
    # casse permise par la RFC sur la partie locale.
    return resultat.normalized.casefold()
