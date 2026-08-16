from modules.analyse.domaine.analyse import SourceAnalyse
from modules.cache.adaptateurs.input_hash import calculer_input_hash


def test_meme_texte_et_meme_source_donnent_le_meme_hash() -> None:
    premier = calculer_input_hash("Mon profil GitHub", SourceAnalyse.GITHUB)
    second = calculer_input_hash("Mon profil GitHub", SourceAnalyse.GITHUB)

    assert premier == second


def test_meme_texte_avec_une_source_differente_donne_un_hash_different() -> None:
    # Deux sources différentes pour un même texte ne partagent jamais le
    # cache (projets.md, table CACHE_RESULTAT) : un profil GitHub et une
    # bio qui contiendraient accidentellement le même texte ne doivent pas
    # être confondus.
    resultat_github = calculer_input_hash("Même texte", SourceAnalyse.GITHUB)
    resultat_bio = calculer_input_hash("Même texte", SourceAnalyse.BIO)

    assert resultat_github != resultat_bio


def test_texte_different_donne_un_hash_different() -> None:
    premier = calculer_input_hash("Texte A", SourceAnalyse.SPOTIFY)
    second = calculer_input_hash("Texte B", SourceAnalyse.SPOTIFY)

    assert premier != second


def test_espaces_de_bord_et_internes_ne_changent_pas_le_hash() -> None:
    # Deux collages qui ne diffèrent que par une mise en forme cosmétique
    # (espaces de fin de ligne, tabulation, retour à la ligne en trop)
    # doivent tomber sur la même clé de cache (D2, backlog.md).
    sans_espaces = calculer_input_hash("Mon texte collé", SourceAnalyse.BIO)
    avec_espaces = calculer_input_hash("  Mon   texte\ncollé  \n", SourceAnalyse.BIO)

    assert sans_espaces == avec_espaces


def test_hash_est_un_digest_sha256_hexadecimal() -> None:
    empreinte = calculer_input_hash("Texte quelconque", SourceAnalyse.AUTRE)

    assert len(empreinte) == 64
    assert all(caractere in "0123456789abcdef" for caractere in empreinte)
