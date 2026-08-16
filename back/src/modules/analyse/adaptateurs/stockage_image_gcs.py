import asyncio

from google.cloud import storage

from modules.analyse.ports.stockage_image import StockageImagePort


class StockageImageGCS(StockageImagePort):
    """Implémentation GCS de `StockageImagePort` (E5, backlog.md), prod.

    Câblée au point de composition dès que `GCS_BUCKET_IMAGES`
    (`shared/config.py`) est renseignée — activée seulement après L4
    (backlog.md), qui provisionne le bucket + Cloud CDN par Terraform.
    Tant que L4 n'existe pas, aucune valeur n'est renseignée en prod et
    `StockageImageFilesystem` reste câblée, exactement comme
    `GenerateurIAFactice` le reste tant qu'aucune clé LLM n'est configurée
    (E1) : le point de composition ne force jamais une dépendance qui
    n'est pas encore prête (agents.md §2).

    Authentification via Application Default Credentials (compte de
    service attaché au service Cloud Run, projets.md §Sécurité) : jamais
    de clé JSON en dur ni committée (agents.md §7).

    Le SDK `google-cloud-storage` est synchrone (agents.md §3 : tout appel
    réseau externe doit rester non bloquant pour la boucle d'événements) ;
    `stocker` déporte l'upload sur un thread plutôt que de bloquer.
    """

    def __init__(self, bucket: str, client: storage.Client | None = None) -> None:
        # `client` injectable (défaut : ADC via `storage.Client()`) pour la
        # même raison que `timeout_secondes`/`max_retries` sur
        # `AdaptateurClaude` (E1) : les tests construisent un client avec
        # des credentials anonymes plutôt que de dépendre d'ADC (agents.md
        # §4 — remplaçable sans forker la classe).
        self._client = client if client is not None else storage.Client()
        self._bucket = self._client.bucket(bucket)

    async def stocker(self, contenu: bytes, cle: str) -> str:
        nom_fichier = f"{cle}.png"
        return await asyncio.to_thread(self._televerser, nom_fichier, contenu)

    def _televerser(self, nom_fichier: str, contenu: bytes) -> str:
        blob = self._bucket.blob(nom_fichier)
        # Contenu immuable une fois produit (même `cle` -> mêmes octets,
        # protégé par le cache exact D2/D3) : cache-control longue durée,
        # cohérent avec les "cache headers longs" prévus par L4
        # (backlog.md) — Cloud CDN sert alors l'objet sans revalider auprès
        # de GCS à chaque requête (agents.md §8, cache = coût).
        blob.cache_control = "public, max-age=31536000, immutable"
        blob.upload_from_string(contenu, content_type="image/png")
        return str(blob.public_url)
