from modules.analyse.domaine.analyse import SourceAnalyse
from modules.ia.adaptateurs.generateur_ia_factice import GenerateurIAFactice


async def test_generer_texte_est_deterministe_pour_un_meme_texte_et_une_meme_source() -> None:
    generateur = GenerateurIAFactice()

    premier = await generateur.generer_texte("Mon profil GitHub", SourceAnalyse.GITHUB)
    second = await generateur.generer_texte("Mon profil GitHub", SourceAnalyse.GITHUB)

    assert premier == second


async def test_generer_texte_varie_selon_la_source_pour_un_meme_texte() -> None:
    generateur = GenerateurIAFactice()

    resultat_github = await generateur.generer_texte("Même texte", SourceAnalyse.GITHUB)
    resultat_spotify = await generateur.generer_texte("Même texte", SourceAnalyse.SPOTIFY)

    assert resultat_github != resultat_spotify


async def test_generer_image_est_deterministe_pour_un_meme_texte_resultat() -> None:
    generateur = GenerateurIAFactice()

    premiere = await generateur.generer_image("Analyse factice")
    seconde = await generateur.generer_image("Analyse factice")

    assert premiere == seconde


async def test_compteurs_appels_incrementes_a_chaque_appel() -> None:
    # Assertion centrale de D6 (backlog.md) : le test de concurrence
    # vérifie qu'un seul appel réel est déclenché pour deux requêtes
    # simultanées sur le même texte, via ces mêmes compteurs.
    generateur = GenerateurIAFactice()

    await generateur.generer_texte("Texte A", SourceAnalyse.BIO)
    await generateur.generer_texte("Texte B", SourceAnalyse.BIO)
    await generateur.generer_image("Résultat")

    assert generateur.appels_texte == 2
    assert generateur.appels_image == 1
