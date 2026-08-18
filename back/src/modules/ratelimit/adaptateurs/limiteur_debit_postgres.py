import time
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ratelimit.adaptateurs.models import LimiteDebitModel
from modules.ratelimit.domaine.seau_jetons import EtatSeau, recharger_et_consommer
from modules.ratelimit.ports.rate_limiter import RateLimiterPort


class LimiteurDebitPostgres(RateLimiterPort):
    """Adaptateur Postgres du `RateLimiterPort` (G1, agents.md §4).

    Un seau de jetons par `cle`, partagé entre toutes les instances du
    processus `api` — contrairement à `CircuitBreaker` (E4), dont l'état
    en mémoire *doit* rester isolé par processus (une panne fournisseur
    est détectée indépendamment par chaque instance, sans coordination
    nécessaire), une limite de débit n'a de sens que si elle est vue par
    toutes les instances à la fois : Cloud Run peut démarrer plusieurs
    répliques d'un coup sous une pointe de trafic (shared/db.py), et un
    seau par instance laisserait passer N x la limite réelle — exactement
    le genre d'abus que ce ticket est censé empêcher.

    Adaptateur unique, utilisé aussi bien en dev qu'en prod (pas de
    bascule dev/prod comme `GenerateurIAPort`/`StockageImagePort`/
    `FileJobsPort`) : ces trois-là évitent une dépendance *payante*
    absente en local (clé LLM, bucket GCS, queue Cloud Tasks). Postgres,
    lui, tourne déjà en dev via docker-compose (A5) — dupliquer un second
    adaptateur en mémoire seulement pour l'y éviter n'aurait aucun
    bénéfice de coût réel, juste plus de code à maintenir et à tester
    (agents.md §2, §13 : KISS gagne quand aucun besoin réel ne justifie la
    complexité). `CachePort` suit déjà la même règle (composition/app.py :
    toujours `CacheResultatPostgres`, dev comme prod).

    `SELECT ... FOR UPDATE` verrouille la ligne le temps de la transaction :
    sous deux requêtes concurrentes sur la même `cle` (même IP, même
    user), la seconde attend que la première ait commité avant de lire
    l'état à jour, ce qui évite que les deux consomment le même jeton en
    double. Même risque de course que `CacheResultatPostgres.
    inserer_si_absent` (modules/cache), résolu ici par un verrou de ligne
    plutôt qu'un `ON CONFLICT` : l'opération n'est pas un insert
    conditionnel mais une lecture-modification-écriture (lire le seau,
    le recharger, le décrémenter).
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def consommer(self, cle: str, capacite: int, taux_recharge_par_seconde: float) -> bool:
        maintenant = time.time()
        async with self._sessionmaker() as session:
            # Crée le seau au plein capacité s'il n'existe pas encore ;
            # `DO NOTHING` sous course concurrente pour ne jamais écraser
            # un état déjà entamé par un autre appelant qui aurait gagné
            # la course d'insertion (même motif que `inserer_si_absent`).
            await session.execute(
                pg_insert(LimiteDebitModel)
                .values(cle=cle, jetons=float(capacite), maj_a=_vers_datetime(maintenant))
                .on_conflict_do_nothing(index_elements=["cle"])
            )
            ligne = (
                await session.execute(
                    select(LimiteDebitModel).where(LimiteDebitModel.cle == cle).with_for_update()
                )
            ).scalar_one()

            etat_avant = EtatSeau(jetons=ligne.jetons, maj_a=ligne.maj_a.timestamp())
            etat_apres, autorise = recharger_et_consommer(
                etat_avant, capacite, taux_recharge_par_seconde, maintenant
            )

            # Toujours écrit, même si `autorise` est `False` (voir docstring
            # de `recharger_et_consommer`) : un seau vide doit quand même
            # avancer son horodatage de recharge.
            await session.execute(
                update(LimiteDebitModel)
                .where(LimiteDebitModel.cle == cle)
                .values(jetons=etat_apres.jetons, maj_a=_vers_datetime(etat_apres.maj_a))
            )
            await session.commit()

        return autorise


def _vers_datetime(epoch_secondes: float) -> datetime:
    return datetime.fromtimestamp(epoch_secondes, tz=UTC)
