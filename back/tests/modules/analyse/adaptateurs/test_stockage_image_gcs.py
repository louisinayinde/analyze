import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage

from modules.analyse.adaptateurs.stockage_image_gcs import StockageImageGCS


def _adaptateur() -> StockageImageGCS:
    # Credentials anonymes : construire un `storage.Client` réel sans
    # dépendre d'Application Default Credentials, absentes en test/CI
    # (`storage.Client()` sans argument lèverait `DefaultCredentialsError`).
    client = storage.Client(project="projet-test", credentials=AnonymousCredentials())
    return StockageImageGCS(bucket="bucket-test", client=client)


async def test_stocker_televerse_le_contenu_avec_le_bon_type_et_retourne_l_url_publique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adaptateur = _adaptateur()
    appels: list[tuple[str, bytes, str | None]] = []

    def televerser_factice(
        self: storage.Blob, data: bytes, content_type: str | None = None
    ) -> None:
        appels.append((self.name, data, content_type))

    # Un nouveau `Blob` est créé à chaque appel de `stocker` (`bucket.blob`) :
    # monkeypatcher la classe, pas une instance, comme
    # `test_generer_texte_reessaie_apres_une_erreur_serveur_transitoire`
    # patche le transport HTTP plutôt qu'un appel précis (adaptateur_claude).
    monkeypatch.setattr(storage.Blob, "upload_from_string", televerser_factice)

    url = await adaptateur.stocker(b"contenu-image", "cle-abc")

    assert url == "https://storage.googleapis.com/bucket-test/cle-abc.png"
    assert appels == [("cle-abc.png", b"contenu-image", "image/png")]


async def test_stocker_definit_un_cache_control_longue_duree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Contenu immuable une fois produit (même `cle` -> mêmes octets, cache
    # exact D2/D3) : Cloud CDN (L4) ne doit jamais revalider auprès de GCS.
    adaptateur = _adaptateur()
    valeurs_cache_control: list[str | None] = []

    def televerser_factice(
        self: storage.Blob, data: bytes, content_type: str | None = None
    ) -> None:
        valeurs_cache_control.append(self.cache_control)

    monkeypatch.setattr(storage.Blob, "upload_from_string", televerser_factice)

    await adaptateur.stocker(b"contenu", "cle")

    assert valeurs_cache_control == ["public, max-age=31536000, immutable"]
