from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from shared.config import Settings

# Sans convention explicite, Postgres nomme les contraintes/index de façon
# arbitraire (ex. `historique_user_id_fkey`) et Alembic autogenerate ne peut
# pas les retrouver de façon stable pour un futur ALTER/DROP CONSTRAINT.
# Fixée dès B6 (première migration avec de vraies contraintes/FK/index) :
# la retrofit plus tard coûterait une migration de renommage sur toutes les
# tables existantes (agents.md §2 — payer une fois, tôt, plutôt qu'à chaque
# évolution).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles SQLAlchemy.

    Chaque module possède ses propres modèles dans son `adaptateurs/`
    (agents.md §4 — pas de `models.py` global), mais ils héritent tous de
    cette même Base pour partager une seule `metadata`, utilisée par
    Alembic (migrations/env.py) pour la comparaison/autogénération des
    migrations.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_engine(settings: Settings) -> AsyncEngine:
    """Crée l'engine SQLAlchemy async avec un pool de connexions **borné**.

    Cloud Run peut scale-to-zero puis redémarrer plusieurs instances d'un
    coup sous une pointe de trafic (projets.md, §Base de données) : sans
    borne explicite, N instances x pool illimité peut saturer les
    connexions max de Postgres/Cloud SQL. `pool_size` + `max_overflow`
    plafonnent le nombre de connexions ouvertes par instance ;
    `pool_recycle` évite de réutiliser une connexion qu'un load balancer ou
    Cloud SQL aurait fermée silencieusement côté serveur ; `pool_pre_ping`
    détecte une connexion morte avant de s'en servir plutôt que de laisser
    échouer la requête qui l'utilise.
    """
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Fabrique de sessions, à partager entre tous les adaptateurs Postgres.

    Volontairement indépendante de FastAPI (pas de `Depends` ici) : le
    `worker` (EPIC F) consomme des jobs hors cycle requête/réponse HTTP et a
    besoin du même accès DB. Chaque adaptateur ouvre sa propre session par
    opération via `async with sessionmaker() as session: ...`.
    """
    return async_sessionmaker(engine, expire_on_commit=False)
