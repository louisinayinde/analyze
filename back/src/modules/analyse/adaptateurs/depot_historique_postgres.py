import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.analyse.adaptateurs.models import HistoriqueModel
from modules.analyse.domaine.entree_historique import EntreeHistorique
from modules.analyse.ports.historique import DépôtHistoriquePort


class DépôtHistoriquePostgres(DépôtHistoriquePort):
    """Adaptateur Postgres du port `DépôtHistoriquePort` (H3, agents.md §4).

    Seul endroit qui connaît à la fois `EntreeHistorique` (entité domaine)
    et `HistoriqueModel` (modèle de persistance, B6) : la conversion entre
    les deux se fait exclusivement ici. Câblage port -> adaptateur fait une
    seule fois, au point de composition (composition/app.py).
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def enregistrer(
        self, user_id: uuid.UUID, resultat_id: uuid.UUID, input_text: str
    ) -> None:
        async with self._sessionmaker() as session:
            session.add(
                HistoriqueModel(
                    id=uuid.uuid4(), user_id=user_id, resultat_id=resultat_id, input_text=input_text
                )
            )
            await session.commit()

    async def lister_par_utilisateur(
        self, user_id: uuid.UUID, page: int, page_size: int
    ) -> tuple[list[EntreeHistorique], int]:
        async with self._sessionmaker() as session:
            total = await session.scalar(
                select(func.count())
                .select_from(HistoriqueModel)
                .where(HistoriqueModel.user_id == user_id)
            )
            resultat = await session.execute(
                select(HistoriqueModel)
                .where(HistoriqueModel.user_id == user_id)
                # Plus récent d'abord : c'est ce qu'un utilisateur consultant
                # son historique veut voir en premier.
                .order_by(HistoriqueModel.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            modeles = resultat.scalars().all()

        return [_vers_domaine(modele) for modele in modeles], total or 0


def _vers_domaine(modele: HistoriqueModel) -> EntreeHistorique:
    return EntreeHistorique(
        id=modele.id,
        resultat_id=modele.resultat_id,
        input_text=modele.input_text,
        created_at=modele.created_at,
    )
