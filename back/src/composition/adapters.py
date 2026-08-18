from pathlib import Path

from modules.analyse.index import StockageImageFilesystem, StockageImageGCS
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.stockage_image import StockageImagePort
from modules.ia.index import AdaptateurClaude, GenerateurIAAvecCircuitBreaker, GenerateurIAFactice
from shared.config import Settings


def build_generateur_ia(settings: Settings) -> GenerateurIAPort:
    """Choisit l'implémentation de `GenerateurIAPort` selon l'environnement.

    Extrait de `composition/app.py` (F2, backlog.md) pour que
    `composition/worker.py` retienne exactement la même règle de bascule,
    sans la dupliquer (agents.md §1, DRY) : `AdaptateurClaude` si une clé
    API est configurée, sinon `GenerateurIAFactice` (évite d'exiger une
    clé Anthropic payante pour lancer un processus en dev local, agents.md
    §2, budget).

    `GenerateurIAAvecCircuitBreaker` instancie son propre `CircuitBreaker`
    par défaut (E4) : appeler cette fonction depuis `app.py` et depuis
    `worker.py` donne donc à chaque processus sa propre instance et son
    propre état, comme prévu par la docstring de `CircuitBreaker` — un
    incident fournisseur est détecté et isolé indépendamment par chacun,
    sans coordination nécessaire (agents.md §2, budget : pas de store
    partagé type Redis pour ça).
    """
    if settings.llm_api_key:
        return GenerateurIAAvecCircuitBreaker(
            AdaptateurClaude(api_key=settings.llm_api_key, modele=settings.llm_model)
        )
    return GenerateurIAFactice()


def build_stockage_image(settings: Settings) -> StockageImagePort:
    """Choisit l'implémentation de `StockageImagePort` selon l'environnement.

    Même motif que `build_generateur_ia` ci-dessus : `StockageImageGCS` si
    un bucket est configuré, sinon `StockageImageFilesystem`. Le montage
    HTTP `/images` qui sert les fichiers de l'adaptateur filesystem reste
    hors de cette fonction : c'est une préoccupation propre au processus
    `api` (seul `api` sert des requêtes navigateur), pas au `worker`.
    """
    if settings.gcs_bucket_images:
        return StockageImageGCS(bucket=settings.gcs_bucket_images)
    return StockageImageFilesystem(
        repertoire=Path(settings.local_storage_dir), url_publique_base=settings.api_public_url
    )
