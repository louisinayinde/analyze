import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.auth.adaptateurs.models import UtilisateurModel
from modules.auth.domaine.utilisateur import Utilisateur
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from shared.errors import ConflitRessource


class DépôtUtilisateurPostgres(DépôtUtilisateurPort):
    """Adaptateur Postgres du port `DépôtUtilisateurPort` (C2, agents.md §4).

    Seul endroit du module Auth qui connaît à la fois `Utilisateur` (entité
    domaine, C1) et `UtilisateurModel` (modèle de persistance, B6) : la
    conversion entre les deux se fait exclusivement ici. Le câblage
    port -> adaptateur est fait une seule fois, au point de composition
    (composition/app.py), jamais importé directement par le domaine ou
    l'application.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def creer(self, utilisateur: Utilisateur) -> Utilisateur:
        modele = _vers_modele(utilisateur)
        async with self._sessionmaker() as session:
            session.add(modele)
            try:
                await session.commit()
            except IntegrityError as exc:
                # Seule contrainte d'unicité sur `user` (B6) : l'email. Un
                # conflit ici ne peut donc venir que d'un doublon, traduit en
                # exception de domaine pour que l'appelant (C3) n'ait jamais
                # à connaître IntegrityError/asyncpg (agents.md §4 — le
                # domaine ne dépend d'aucun détail technique).
                raise ConflitRessource("Un compte existe déjà avec cet email.") from exc
        return utilisateur

    async def trouver_par_email(self, email: str) -> Utilisateur | None:
        async with self._sessionmaker() as session:
            resultat = await session.execute(
                select(UtilisateurModel).where(UtilisateurModel.email == email)
            )
            modele = resultat.scalar_one_or_none()
        return _vers_domaine(modele) if modele is not None else None

    async def mettre_a_jour_derniere_connexion(
        self, id_utilisateur: uuid.UUID, horodatage: datetime
    ) -> None:
        async with self._sessionmaker() as session:
            await session.execute(
                update(UtilisateurModel)
                .where(UtilisateurModel.id == id_utilisateur)
                .values(last_login_at=horodatage)
            )
            await session.commit()


def _vers_modele(utilisateur: Utilisateur) -> UtilisateurModel:
    return UtilisateurModel(
        id=utilisateur.id,
        email=utilisateur.email,
        password_hash=utilisateur.password_hash,
        created_at=utilisateur.created_at,
        last_login_at=utilisateur.last_login_at,
    )


def _vers_domaine(modele: UtilisateurModel) -> Utilisateur:
    return Utilisateur(
        id=modele.id,
        email=modele.email,
        password_hash=modele.password_hash,
        created_at=modele.created_at,
        last_login_at=modele.last_login_at,
    )
