import json
import uuid
from datetime import UTC, datetime

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud import tasks_v2

from modules.analyse.adaptateurs.file_jobs_cloud_tasks import FileJobsCloudTasks
from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse

_URL_WORKER = "https://worker.example.com/internal/jobs/analyses"
_SERVICE_ACCOUNT = "worker@projet-test.iam.gserviceaccount.com"


def _adaptateur() -> FileJobsCloudTasks:
    # Credentials anonymes : construire un `CloudTasksClient` réel sans
    # dépendre d'Application Default Credentials, absentes en test/CI
    # (`CloudTasksClient()` sans argument lèverait `DefaultCredentialsError`)
    # — même motif que `test_stockage_image_gcs.py`.
    client = tasks_v2.CloudTasksClient(credentials=AnonymousCredentials())
    return FileJobsCloudTasks(
        project="projet-test",
        location="europe-west1",
        queue="analyses",
        url_worker=_URL_WORKER,
        service_account_email=_SERVICE_ACCOUNT,
        client=client,
    )


def _analyse() -> Analyse:
    return Analyse(
        id=uuid.uuid4(),
        texte_source="mon profil github",
        source=SourceAnalyse.GITHUB,
        statut=StatutAnalyse.PENDING,
        created_at=datetime.now(UTC),
    )


async def test_dispatcher_enfile_une_tache_http_avec_le_texte_et_le_jeton_oidc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adaptateur = _adaptateur()
    appels: list[tuple[str | None, tasks_v2.Task | None]] = []

    def creer_tache_factice(
        self: tasks_v2.CloudTasksClient,
        parent: str | None = None,
        task: tasks_v2.Task | None = None,
        **kwargs: object,
    ) -> tasks_v2.Task:
        appels.append((parent, task))
        assert task is not None
        return task

    # Monkeypatcher la classe, pas une instance, comme `test_stockage_image_gcs.py`.
    monkeypatch.setattr(tasks_v2.CloudTasksClient, "create_task", creer_tache_factice)

    analyse = _analyse()
    await adaptateur.dispatcher(analyse)

    assert len(appels) == 1
    parent, tache = appels[0]
    assert parent == tasks_v2.CloudTasksClient.queue_path("projet-test", "europe-west1", "analyses")
    assert tache is not None
    assert tache.http_request.http_method == tasks_v2.HttpMethod.POST
    assert tache.http_request.url == _URL_WORKER
    # Le texte source est transporté par la tâche elle-même : `cache_resultat`
    # ne le persiste jamais (D2), c'est le seul endroit où il est encore
    # disponible pour le worker qui recevra cette tâche (F2/F3).
    corps = json.loads(tache.http_request.body)
    assert corps == {
        "analyse_id": str(analyse.id),
        "texte_source": "mon profil github",
        "source": "github",
    }
    # Jeton OIDC vérifié à réception par l'endpoint interne du worker (F3,
    # agents.md §7 — un endpoint interne reste soumis à vérification d'origine).
    assert tache.http_request.oidc_token.service_account_email == _SERVICE_ACCOUNT
    assert tache.http_request.oidc_token.audience == _URL_WORKER
