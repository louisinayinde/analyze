from io import BytesIO

from PIL import Image

from modules.ia.adaptateurs.rendu_image_template import (
    HAUTEUR,
    LARGEUR,
    generer_image_resultat,
)


def _ouvrir(image_bytes: bytes) -> Image.Image:
    return Image.open(BytesIO(image_bytes))


def test_generer_image_resultat_produit_un_png_a_la_taille_attendue() -> None:
    image_bytes = generer_image_resultat("Un roast fun et bienveillant.")

    image = _ouvrir(image_bytes)
    assert image.format == "PNG"
    assert image.size == (LARGEUR, HAUTEUR)


def test_generer_image_resultat_est_deterministe() -> None:
    # Propriété centrale du choix template (E2, backlog.md) : même texte ->
    # mêmes octets, sans appel réseau ni aléa — contrairement à un modèle
    # multimodal.
    premiere = generer_image_resultat("Même texte de résultat")
    seconde = generer_image_resultat("Même texte de résultat")

    assert premiere == seconde


def test_generer_image_resultat_varie_selon_le_texte() -> None:
    premiere = generer_image_resultat("Un premier roast.")
    seconde = generer_image_resultat("Un second roast, complètement différent.")

    assert premiere != seconde


def test_generer_image_resultat_gere_un_texte_tres_long_sans_deborder() -> None:
    # `resultat_texte` n'est borné que par MAX_TOKENS_REPONSE côté Claude
    # (adaptateur_claude.py), pas par un nombre de caractères : ce test
    # couvre le filet de sécurité (_TEXTE_LONGUEUR_MAX + échelle de tailles
    # de police) qui garantit un rendu valide quoi que renvoie le
    # fournisseur IA (agents.md §3 : dégradation gracieuse).
    texte_tres_long = "Un roast interminable qui n'en finit plus. " * 60

    image_bytes = generer_image_resultat(texte_tres_long)

    image = _ouvrir(image_bytes)
    assert image.size == (LARGEUR, HAUTEUR)


def test_generer_image_resultat_gere_un_texte_vide() -> None:
    image_bytes = generer_image_resultat("")

    image = _ouvrir(image_bytes)
    assert image.size == (LARGEUR, HAUTEUR)
