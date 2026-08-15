import asyncio
import uuid
from datetime import UTC, datetime

from modules.auth.domaine.enregistrement_refresh import EnregistrementRefresh
from modules.auth.domaine.jeton import Jetons
from modules.auth.ports.depot_refresh_token import DépôtRefreshTokenPort
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from modules.auth.ports.emetteur_jeton import EmetteurJetonPort
from modules.auth.ports.hacheur_mot_de_passe import HacheurMotDePassePort
from shared.errors import NonAuthentifie

# Volontairement générique, quel que soit le cas réel (email inconnu, mot de
# passe incorrect) : ne confirme jamais qu'un compte existe avec cet email
# (agents.md §7 — pas d'énumération d'utilisateurs, y compris dans le
# message renvoyé au client).
_MESSAGE_ECHEC_GENERIQUE = "Email ou mot de passe incorrect."

# Hash Argon2id valide mais rattaché à aucun compte réel, utilisé comme
# leurre quand l'email n'existe pas. Sans lui, un attaquant pourrait
# distinguer "email inconnu" (retour immédiat) de "email connu, mauvais mot
# de passe" (retour après le coût CPU d'Argon2id) par simple mesure du temps
# de réponse — même classe de fuite par timing que celle déjà traitée en C3
# pour l'inscription, ici côté vérification plutôt que hachage.
_HASH_FACTICE = (
    "$argon2id$v=19$m=65536,t=3,p=4$PyXG148Mj7NFVKWULmKatQ$"
    "9dumJcfkfqp9Pi9qV3ITkR/vCme5wonkVZHjJ2oUXh0"  # pragma: allowlist secret
)


class ConnecterUtilisateur:
    """Use-case Connexion (C4, agents.md §4, §7).

    Orchestration pure : vérifie les credentials via les ports
    `DépôtUtilisateurPort`/`HacheurMotDePassePort`, met à jour la dernière
    connexion, émet la paire de jetons via `EmetteurJetonPort`, puis ouvre
    une nouvelle famille de rotation via `DépôtRefreshTokenPort` (C6) : sans
    cet enregistrement initial, le premier `/auth/refresh` suivant ce login
    ne trouverait aucun `jti` connu en base et la rotation serait impossible
    dès le départ. Ni argon2 ni PyJWT ne sont importés ici — ce fichier ne
    connaît que des ports, remplaçables sans le modifier (agents.md §4).
    """

    def __init__(
        self,
        depot: DépôtUtilisateurPort,
        hacheur: HacheurMotDePassePort,
        emetteur: EmetteurJetonPort,
        depot_refresh: DépôtRefreshTokenPort,
    ) -> None:
        self._depot = depot
        self._hacheur = hacheur
        self._emetteur = emetteur
        self._depot_refresh = depot_refresh

    async def executer(self, email: str, mot_de_passe: str) -> Jetons:
        # Simple normalisation de casse pour retrouver l'email tel que
        # stocké par l'inscription (C3) — pas de revalidation complète du
        # format ici : un email malformé ne matchera simplement aucun
        # compte et suivra le même chemin d'échec générique que des
        # credentials incorrects, sans branche dédiée à distinguer
        # (agents.md §7 — un chemin d'échec unique, pas d'oracle de format).
        email_normalise = email.strip().casefold()

        utilisateur = await self._depot.trouver_par_email(email_normalise)
        hash_a_verifier = utilisateur.password_hash if utilisateur is not None else _HASH_FACTICE

        # `to_thread` : la vérification Argon2id est du calcul CPU pur,
        # bloquant pour la boucle d'événements asyncio sinon (agents.md §8 —
        # même raisonnement que le hachage en C3). Exécutée dans tous les
        # cas, y compris email inconnu (voir `_HASH_FACTICE` ci-dessus), pour
        # que le temps de réponse ne trahisse pas l'existence du compte.
        mot_de_passe_valide = await asyncio.to_thread(
            self._hacheur.verifier, mot_de_passe, hash_a_verifier
        )

        if utilisateur is None or not mot_de_passe_valide:
            raise NonAuthentifie(_MESSAGE_ECHEC_GENERIQUE)

        await self._depot.mettre_a_jour_derniere_connexion(utilisateur.id, datetime.now(UTC))

        jetons = self._emetteur.emettre_jetons(utilisateur.id)

        # Nouvelle famille (C6) : `family_id` généré ici, pas par
        # l'émetteur JWT — c'est un concept de suivi côté serveur, jamais
        # encodé dans le jeton lui-même (voir le commentaire de
        # `EmetteurJWT` sur `jti`).
        await self._depot_refresh.creer(
            EnregistrementRefresh(
                jti=jetons.refresh_jti,
                family_id=uuid.uuid4(),
                user_id=utilisateur.id,
                created_at=datetime.now(UTC),
                expires_at=jetons.refresh_expires_at,
            )
        )

        return jetons
