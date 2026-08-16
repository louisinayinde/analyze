import pytest

from modules.analyse.domaine.analyse import SourceAnalyse
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.ia.adaptateurs.circuit_breaker import CircuitBreaker
from modules.ia.adaptateurs.generateur_ia_avec_circuit_breaker import (
    GenerateurIAAvecCircuitBreaker,
)
from shared.errors import ServiceIndisponible


class _DelegueControle(GenerateurIAPort):
    def __init__(self) -> None:
        self.appels_texte = 0
        self.appels_image = 0
        self.leve_sur_texte = False

    async def generer_texte(self, texte_source: str, source: SourceAnalyse) -> str:
        self.appels_texte += 1
        if self.leve_sur_texte:
            raise RuntimeError("panne fournisseur")
        return "résultat"

    async def generer_image(self, texte_resultat: str) -> bytes:
        self.appels_image += 1
        return b"image"


async def test_generer_texte_delegue_quand_le_circuit_est_ferme() -> None:
    delegue = _DelegueControle()
    adaptateur = GenerateurIAAvecCircuitBreaker(delegue, CircuitBreaker(seuil_echecs=1))

    resultat = await adaptateur.generer_texte("texte", SourceAnalyse.BIO)

    assert resultat == "résultat"
    assert delegue.appels_texte == 1


async def test_generer_texte_leve_service_indisponible_une_fois_le_circuit_ouvert() -> None:
    delegue = _DelegueControle()
    delegue.leve_sur_texte = True
    adaptateur = GenerateurIAAvecCircuitBreaker(delegue, CircuitBreaker(seuil_echecs=1))

    with pytest.raises(RuntimeError):
        await adaptateur.generer_texte("texte", SourceAnalyse.BIO)

    with pytest.raises(ServiceIndisponible):
        await adaptateur.generer_texte("texte", SourceAnalyse.BIO)
    # Le second appel n'a pas atteint le délégué : le circuit a coupé court.
    assert delegue.appels_texte == 1


async def test_generer_image_ne_passe_jamais_par_le_disjoncteur() -> None:
    # E2 : `generer_image` est un rendu local, jamais concerné par un
    # incident du fournisseur LLM — même une fois le circuit ouvert pour
    # `generer_texte`, `generer_image` doit continuer de fonctionner.
    delegue = _DelegueControle()
    delegue.leve_sur_texte = True
    adaptateur = GenerateurIAAvecCircuitBreaker(delegue, CircuitBreaker(seuil_echecs=1))
    with pytest.raises(RuntimeError):
        await adaptateur.generer_texte("texte", SourceAnalyse.BIO)
    with pytest.raises(ServiceIndisponible):
        await adaptateur.generer_texte("texte", SourceAnalyse.BIO)  # circuit désormais ouvert

    resultat = await adaptateur.generer_image("texte résultat")

    assert resultat == b"image"
    assert delegue.appels_image == 1


async def test_un_disjoncteur_par_defaut_est_cree_si_aucun_n_est_fourni() -> None:
    # Câblage minimal possible au point de composition : `AdaptateurClaude`
    # peut être décoré sans avoir à instancier `CircuitBreaker` soi-même.
    delegue = _DelegueControle()
    adaptateur = GenerateurIAAvecCircuitBreaker(delegue)

    resultat = await adaptateur.generer_texte("texte", SourceAnalyse.BIO)

    assert resultat == "résultat"
