import uuid
from datetime import UTC, datetime

import pytest

from modules.analyse.adaptateurs.file_jobs_en_processus_immediat import (
    FileJobsEnProcessusImmediat,
)
from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse


def _analyse() -> Analyse:
    return Analyse(
        id=uuid.uuid4(),
        texte_source="texte",
        source=SourceAnalyse.BIO,
        statut=StatutAnalyse.PENDING,
        created_at=datetime.now(UTC),
    )


async def test_dispatcher_execute_le_job_de_facon_synchrone() -> None:
    appels: list[uuid.UUID] = []

    async def executer_job(analyse: Analyse) -> Analyse:
        appels.append(analyse.id)
        return analyse

    adaptateur = FileJobsEnProcessusImmediat(executer_job)
    analyse = _analyse()

    await adaptateur.dispatcher(analyse)

    # Pas de file réelle en dev (F1, backlog.md) : le job est déjà exécuté
    # au moment où `dispatcher` retourne, sans passer par Cloud Tasks.
    assert appels == [analyse.id]


async def test_dispatcher_propage_une_exception_du_job() -> None:
    # Le use-case (D3) compte sur cette propagation pour laisser remonter
    # un échec de génération (E4, circuit breaker) exactement comme avant
    # que ce port n'existe (agents.md §4 — remplacer l'appel direct par le
    # port ne doit rien changer d'observable en dev).
    async def executer_job(analyse: Analyse) -> Analyse:
        raise RuntimeError("échec du job")

    adaptateur = FileJobsEnProcessusImmediat(executer_job)

    with pytest.raises(RuntimeError, match="échec du job"):
        await adaptateur.dispatcher(_analyse())
