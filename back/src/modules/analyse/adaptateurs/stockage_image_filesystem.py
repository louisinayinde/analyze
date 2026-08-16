import asyncio
from pathlib import Path

from modules.analyse.ports.stockage_image import StockageImagePort


class StockageImageFilesystem(StockageImagePort):
    """Implémentation filesystem locale de `StockageImagePort` (E5, backlog.md).

    Adaptateur de dev, câblé au point de composition en l'absence de
    `GCS_BUCKET_IMAGES` (`shared/config.py`, `composition/app.py). Écrit
    chaque image sur `repertoire`, un volume Docker dédié
    (docker-compose.yml, service `api`) plutôt que le bind mount
    `./back:/app` : sans cette isolation, chaque image générée en dev
    finirait committée dans le dépôt git.

    Les fichiers écrits ici sont servis en HTTP par le même processus API,
    via un montage `StaticFiles` sur `/images` (composition/app.py) — c'est
    ce qui permet de renvoyer une véritable URL publique, comme l'exige le
    contrat du port, sans un second service à opérer en dev (agents.md §2).

    Remplacée par `StockageImageGCS` en prod dès qu'un bucket est configuré
    (E5, backlog.md, gating identique à `AdaptateurClaude`/
    `GenerateurIAFactice` pour `GenerateurIAPort`, E1) : aucune ligne du
    use-case `GenererAnalyse` (D3) ne change (agents.md §4).
    """

    def __init__(self, repertoire: Path, url_publique_base: str) -> None:
        self._repertoire = repertoire
        self._url_publique_base = url_publique_base.rstrip("/")

    async def stocker(self, contenu: bytes, cle: str) -> str:
        nom_fichier = f"{cle}.png"
        # Écriture bloquante déportée sur un thread : `contenu` (agents.md
        # §3, une image PNG de quelques dizaines de Ko au plus) n'est jamais
        # gros au point de justifier un flux, mais un write() synchrone
        # bloquerait la boucle d'événements le temps du flush disque.
        await asyncio.to_thread(self._ecrire, nom_fichier, contenu)
        return f"{self._url_publique_base}/images/{nom_fichier}"

    def _ecrire(self, nom_fichier: str, contenu: bytes) -> None:
        # `mkdir` fait ici (au premier appel), pas à l'`__init__` : créer le
        # dossier plus tôt ne sert à rien tant qu'aucune image n'a encore
        # été générée (agents.md §2, YAGNI).
        self._repertoire.mkdir(parents=True, exist_ok=True)
        (self._repertoire / nom_fichier).write_bytes(contenu)
