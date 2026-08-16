from pathlib import Path

from modules.analyse.adaptateurs.stockage_image_filesystem import StockageImageFilesystem


async def test_stocker_ecrit_le_contenu_sur_disque_et_retourne_l_url_publique(
    tmp_path: Path,
) -> None:
    adaptateur = StockageImageFilesystem(
        repertoire=tmp_path, url_publique_base="http://localhost:8000"
    )

    url = await adaptateur.stocker(b"contenu-image", "cle-abc")

    assert url == "http://localhost:8000/images/cle-abc.png"
    assert (tmp_path / "cle-abc.png").read_bytes() == b"contenu-image"


async def test_stocker_cree_le_repertoire_manquant(tmp_path: Path) -> None:
    # `repertoire` n'existe pas encore (aucune image générée depuis le boot,
    # composition/app.py) : `stocker` doit le créer plutôt que lever.
    repertoire = tmp_path / "images" / "sous-dossier"
    adaptateur = StockageImageFilesystem(
        repertoire=repertoire, url_publique_base="http://localhost:8000"
    )

    await adaptateur.stocker(b"contenu", "cle")

    assert (repertoire / "cle.png").read_bytes() == b"contenu"


async def test_stocker_retire_le_slash_final_de_l_url_de_base(tmp_path: Path) -> None:
    adaptateur = StockageImageFilesystem(
        repertoire=tmp_path, url_publique_base="http://localhost:8000/"
    )

    url = await adaptateur.stocker(b"contenu", "cle")

    assert url == "http://localhost:8000/images/cle.png"
