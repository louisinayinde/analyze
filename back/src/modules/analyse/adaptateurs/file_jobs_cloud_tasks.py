import asyncio
import json

from google.cloud import tasks_v2

from modules.analyse.domaine.analyse import Analyse
from modules.analyse.ports.file_jobs import FileJobsPort


class FileJobsCloudTasks(FileJobsPort):
    """Implémentation Cloud Tasks de `FileJobsPort` (F1, backlog.md), prod.

    Câblée au point de composition dès que `CLOUD_TASKS_QUEUE`
    (`shared/config.py`) est renseignée — activée seulement après L7
    (backlog.md, provisionnement Terraform de la queue) : même bascule que
    `StockageImageGCS`/`AdaptateurClaude` (agents.md §2 — le point de
    composition ne force jamais une dépendance qui n'est pas encore
    prête). Tant que L7 n'existe pas, `FileJobsEnProcessusImmediat` reste
    câblée.

    Le corps de la tâche transporte `texte_source` et `source` en clair,
    pas seulement `analyse.id` : `cache_resultat` ne persiste jamais le
    texte original (D2, `CachePort.obtenir_par_id`), donc l'enfilage est
    le *seul* endroit où ce texte est encore disponible — sans ce payload,
    l'endpoint interne du worker (F3) n'aurait aucun moyen de retrouver le
    texte à analyser.

    Le jeton OIDC joint à la requête (`oidc_token`) est ce que l'endpoint
    du worker (F3) vérifiera à réception, pour que cet endpoint interne ne
    soit pas appelable par n'importe qui (agents.md §7 — sécurité non
    négociable même sur un endpoint interne).

    Le SDK `google-cloud-tasks` est synchrone (agents.md §3 : jamais
    bloquer la boucle d'événements) ; `dispatcher` déporte l'appel sur un
    thread, comme `StockageImageGCS.stocker`.
    """

    def __init__(
        self,
        project: str,
        location: str,
        queue: str,
        url_worker: str,
        service_account_email: str,
        client: tasks_v2.CloudTasksClient | None = None,
    ) -> None:
        # `client` injectable (défaut : ADC via `CloudTasksClient()`),
        # même motif que `StockageImageGCS.__init__` — les tests
        # construisent un client avec des credentials anonymes plutôt que
        # de dépendre d'ADC.
        self._client = client if client is not None else tasks_v2.CloudTasksClient()
        self._queue_path = self._client.queue_path(project, location, queue)
        self._url_worker = url_worker
        self._service_account_email = service_account_email

    async def dispatcher(self, analyse: Analyse) -> None:
        await asyncio.to_thread(self._creer_tache, analyse)

    def _creer_tache(self, analyse: Analyse) -> None:
        corps = json.dumps(
            {
                "analyse_id": str(analyse.id),
                "texte_source": analyse.texte_source,
                "source": analyse.source.value,
            }
        ).encode()
        tache = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=self._url_worker,
                headers={"Content-Type": "application/json"},
                body=corps,
                oidc_token=tasks_v2.OidcToken(
                    service_account_email=self._service_account_email,
                    audience=self._url_worker,
                ),
            )
        )
        self._client.create_task(parent=self._queue_path, task=tache)
