import pytest

from modules.ia.adaptateurs.circuit_breaker import CircuitBreaker
from shared.errors import ServiceIndisponible


class _Compteur:
    def __init__(self) -> None:
        self.appels = 0

    async def echoue(self) -> str:
        self.appels += 1
        raise RuntimeError("panne fournisseur")

    async def reussit(self) -> str:
        self.appels += 1
        return "ok"


async def test_le_circuit_reste_ferme_sous_le_seuil_d_echecs() -> None:
    disjoncteur = CircuitBreaker(seuil_echecs=3)
    compteur = _Compteur()

    for _ in range(3):
        with pytest.raises(RuntimeError):
            await disjoncteur.appeler(compteur.echoue)

    # Sous le seuil : chaque appel est réellement tenté, pas de fast-fail.
    assert compteur.appels == 3


async def test_le_circuit_s_ouvre_apres_le_seuil_d_echecs_consecutifs() -> None:
    disjoncteur = CircuitBreaker(seuil_echecs=2)
    compteur = _Compteur()

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await disjoncteur.appeler(compteur.echoue)

    # Seuil atteint : l'appel suivant échoue immédiatement, sans toucher
    # `compteur.echoue` (agents.md §3 — isoler la panne, pas la propager).
    with pytest.raises(ServiceIndisponible):
        await disjoncteur.appeler(compteur.echoue)
    assert compteur.appels == 2


async def test_un_succes_reinitialise_le_compteur_d_echecs_consecutifs() -> None:
    disjoncteur = CircuitBreaker(seuil_echecs=2)
    compteur = _Compteur()

    with pytest.raises(RuntimeError):
        await disjoncteur.appeler(compteur.echoue)
    await disjoncteur.appeler(compteur.reussit)

    # Le compteur est reparti à zéro : il faut de nouveau `seuil_echecs`
    # échecs consécutifs avant que le circuit ne s'ouvre.
    with pytest.raises(RuntimeError):
        await disjoncteur.appeler(compteur.echoue)
    assert compteur.appels == 3  # aucun `ServiceIndisponible` levé ici


async def test_le_circuit_ouvert_laisse_passer_une_sonde_apres_le_delai_de_recuperation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    horloge = {"maintenant": 0.0}
    monkeypatch.setattr(
        "modules.ia.adaptateurs.circuit_breaker.time.monotonic", lambda: horloge["maintenant"]
    )
    disjoncteur = CircuitBreaker(seuil_echecs=1, delai_recuperation_secondes=60.0)
    compteur = _Compteur()

    with pytest.raises(RuntimeError):
        await disjoncteur.appeler(compteur.echoue)
    with pytest.raises(ServiceIndisponible):
        await disjoncteur.appeler(compteur.echoue)
    assert compteur.appels == 1  # le second appel n'a jamais touché `compteur`

    horloge["maintenant"] += 60.0

    # Délai écoulé : l'appel de sonde est laissé passer ; il réussit, le
    # circuit se referme.
    resultat = await disjoncteur.appeler(compteur.reussit)

    assert resultat == "ok"
    assert compteur.appels == 2


async def test_un_echec_de_la_sonde_en_semi_ouvert_rouvre_le_circuit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    horloge = {"maintenant": 0.0}
    monkeypatch.setattr(
        "modules.ia.adaptateurs.circuit_breaker.time.monotonic", lambda: horloge["maintenant"]
    )
    disjoncteur = CircuitBreaker(seuil_echecs=1, delai_recuperation_secondes=60.0)
    compteur = _Compteur()

    with pytest.raises(RuntimeError):
        await disjoncteur.appeler(compteur.echoue)
    horloge["maintenant"] += 60.0

    with pytest.raises(RuntimeError):
        await disjoncteur.appeler(compteur.echoue)  # la sonde échoue aussi

    # Le circuit est reparti pour un tour d'OUVERT (chronomètre relancé) :
    # fast-fail immédiat, sans attendre un nouveau délai complet.
    with pytest.raises(ServiceIndisponible):
        await disjoncteur.appeler(compteur.echoue)
    assert compteur.appels == 2


async def test_service_indisponible_porte_un_message_clair_pour_l_utilisateur() -> None:
    disjoncteur = CircuitBreaker(seuil_echecs=1)
    compteur = _Compteur()
    with pytest.raises(RuntimeError):
        await disjoncteur.appeler(compteur.echoue)

    with pytest.raises(ServiceIndisponible) as exc_info:
        await disjoncteur.appeler(compteur.echoue)

    assert "réessaie" in str(exc_info.value).lower()
