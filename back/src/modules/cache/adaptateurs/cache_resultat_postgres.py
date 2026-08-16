from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.analyse.domaine.analyse import Analyse, StatutAnalyse
from modules.analyse.ports.cache import CachePort
from modules.cache.adaptateurs.input_hash import calculer_input_hash
from modules.cache.adaptateurs.models import CacheResultatModel, SourceType, StatutCache


class CacheResultatPostgres(CachePort):
    """Adaptateur Postgres du port `CachePort` (D2, agents.md §4).

    Seul endroit qui connaît à la fois `Analyse` (entité domaine, D1) et
    `CacheResultatModel` (modèle de persistance, B6) : la conversion entre
    les deux, et le calcul de `input_hash`, se font exclusivement ici. Le
    câblage port -> adaptateur est fait une seule fois, au point de
    composition (composition/app.py).
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def inserer_si_absent(self, analyse: Analyse) -> tuple[Analyse, bool]:
        input_hash = calculer_input_hash(analyse.texte_source, analyse.source)
        # `ON CONFLICT (input_hash) DO NOTHING` (projets.md, §Concurrence
        # sur le cache, étape 1) : sous deux insertions concurrentes sur le
        # même hash, Postgres ne laisse passer que la première — c'est ce
        # qui garantit qu'un seul appelant se voit retourner `cree=True` et
        # déclenche donc le job LLM (D3), sans dépendre d'un verrou
        # applicatif.
        stmt = (
            pg_insert(CacheResultatModel)
            .values(
                id=analyse.id,
                input_hash=input_hash,
                source_type=SourceType(analyse.source.value),
                status=StatutCache.PENDING.value,
            )
            .on_conflict_do_nothing(index_elements=["input_hash"])
            .returning(CacheResultatModel)
        )
        async with self._sessionmaker() as session:
            resultat = await session.execute(stmt)
            ligne_creee = resultat.scalar_one_or_none()
            if ligne_creee is not None:
                await session.commit()
                return _vers_domaine(ligne_creee, analyse), True

            # Conflit : une ligne existe déjà pour ce hash (pending, done ou
            # failed) — on n'a jamais accès au texte original depuis
            # `cache_resultat` (seul `input_hash` y est stocké, jamais le
            # texte en clair), donc l'`Analyse` retournée réutilise le
            # texte/source fournis par l'appelant plutôt que de les relire.
            existante = await session.execute(
                select(CacheResultatModel).where(CacheResultatModel.input_hash == input_hash)
            )
            modele = existante.scalar_one()
            return _vers_domaine(modele, analyse), False

    async def marquer_termine(self, analyse: Analyse) -> Analyse:
        async with self._sessionmaker() as session:
            await session.execute(
                update(CacheResultatModel)
                .where(CacheResultatModel.id == analyse.id)
                .values(
                    status=StatutCache.DONE.value,
                    output_text=analyse.resultat_texte,
                    output_image_url=analyse.resultat_image_url,
                )
            )
            await session.commit()
        return Analyse(
            id=analyse.id,
            texte_source=analyse.texte_source,
            source=analyse.source,
            statut=StatutAnalyse.DONE,
            created_at=analyse.created_at,
            resultat_texte=analyse.resultat_texte,
            resultat_image_url=analyse.resultat_image_url,
        )

    async def marquer_echec(self, analyse: Analyse) -> None:
        # Transition directe vers `failed`, jamais de ligne laissée
        # bloquée en `pending` après un job en échec (agents.md §3,
        # complété côté dégradation gracieuse en E4).
        async with self._sessionmaker() as session:
            await session.execute(
                update(CacheResultatModel)
                .where(CacheResultatModel.id == analyse.id)
                .values(status=StatutCache.FAILED.value)
            )
            await session.commit()

    async def incrementer_hit_count(self, analyse: Analyse) -> None:
        # Incrément atomique côté SQL (`hit_count = hit_count + 1`), pas un
        # lire-puis-écrire applicatif : sous forte concurrence de cache-hits
        # sur la même ligne, un aller-retour lire/écrire perdrait des
        # incréments (dernier commit gagnant), faussant la métrique dont le
        # projet tire son argument de coût (projets.md §Observabilité).
        async with self._sessionmaker() as session:
            await session.execute(
                update(CacheResultatModel)
                .where(CacheResultatModel.id == analyse.id)
                .values(hit_count=CacheResultatModel.hit_count + 1)
            )
            await session.commit()


def _vers_domaine(modele: CacheResultatModel, analyse: Analyse) -> Analyse:
    return Analyse(
        id=modele.id,
        texte_source=analyse.texte_source,
        source=analyse.source,
        statut=StatutAnalyse(modele.status.value),
        created_at=modele.created_at,
        resultat_texte=modele.output_text,
        resultat_image_url=modele.output_image_url,
    )
