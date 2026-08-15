import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.auth.adaptateurs.models import RefreshTokenModel
from modules.auth.domaine.enregistrement_refresh import EnregistrementRefresh
from modules.auth.ports.depot_refresh_token import DépôtRefreshTokenPort


class DépôtRefreshTokenPostgres(DépôtRefreshTokenPort):
    """Adaptateur Postgres du port `DépôtRefreshTokenPort` (C6, agents.md §4).

    Seul endroit du module Auth qui connaît à la fois `EnregistrementRefresh`
    (entité domaine) et `RefreshTokenModel` (modèle de persistance) : la
    conversion entre les deux se fait exclusivement ici, comme
    `DépôtUtilisateurPostgres` le fait déjà pour `Utilisateur`.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def creer(self, enregistrement: EnregistrementRefresh) -> None:
        modele = _vers_modele(enregistrement)
        async with self._sessionmaker() as session:
            session.add(modele)
            await session.commit()

    async def trouver_par_jti(self, jti: uuid.UUID) -> EnregistrementRefresh | None:
        async with self._sessionmaker() as session:
            resultat = await session.execute(
                select(RefreshTokenModel).where(RefreshTokenModel.jti == jti)
            )
            modele = resultat.scalar_one_or_none()
        return _vers_domaine(modele) if modele is not None else None

    async def marquer_utilise(self, jti: uuid.UUID, horodatage: datetime) -> None:
        async with self._sessionmaker() as session:
            await session.execute(
                update(RefreshTokenModel)
                .where(RefreshTokenModel.jti == jti)
                .values(used_at=horodatage)
            )
            await session.commit()

    async def revoquer_famille(self, family_id: uuid.UUID, horodatage: datetime) -> None:
        async with self._sessionmaker() as session:
            # `revoked_at.is_(None)` : ne réécrit pas l'horodatage d'un
            # jeton déjà révoqué précédemment (ex. deux rejeux successifs
            # sur la même famille compromise) — la première révocation fait
            # foi pour l'investigation.
            await session.execute(
                update(RefreshTokenModel)
                .where(RefreshTokenModel.family_id == family_id)
                .where(RefreshTokenModel.revoked_at.is_(None))
                .values(revoked_at=horodatage)
            )
            await session.commit()

    async def revoquer(self, jti: uuid.UUID, horodatage: datetime) -> None:
        async with self._sessionmaker() as session:
            # Même garde `revoked_at.is_(None)` que `revoquer_famille` : ne
            # réécrit pas l'horodatage d'une révocation déjà survenue (ex.
            # déconnexion appelée deux fois sur le même jeton).
            await session.execute(
                update(RefreshTokenModel)
                .where(RefreshTokenModel.jti == jti)
                .where(RefreshTokenModel.revoked_at.is_(None))
                .values(revoked_at=horodatage)
            )
            await session.commit()


def _vers_modele(enregistrement: EnregistrementRefresh) -> RefreshTokenModel:
    return RefreshTokenModel(
        jti=enregistrement.jti,
        family_id=enregistrement.family_id,
        user_id=enregistrement.user_id,
        created_at=enregistrement.created_at,
        expires_at=enregistrement.expires_at,
        used_at=enregistrement.used_at,
        revoked_at=enregistrement.revoked_at,
    )


def _vers_domaine(modele: RefreshTokenModel) -> EnregistrementRefresh:
    return EnregistrementRefresh(
        jti=modele.jti,
        family_id=modele.family_id,
        user_id=modele.user_id,
        created_at=modele.created_at,
        expires_at=modele.expires_at,
        used_at=modele.used_at,
        revoked_at=modele.revoked_at,
    )
