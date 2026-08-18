from tests.modules.ratelimit.conftest import RateLimiterPortEnMémoire


async def test_autorise_les_requetes_jusqu_a_la_capacite_puis_refuse() -> None:
    horloge = {"maintenant": 0.0}
    limiteur = RateLimiterPortEnMémoire(horloge=lambda: horloge["maintenant"])

    for _ in range(3):
        assert await limiteur.consommer("ip:1.2.3.4", capacite=3, taux_recharge_par_seconde=0.0)

    assert (
        await limiteur.consommer("ip:1.2.3.4", capacite=3, taux_recharge_par_seconde=0.0) is False
    )


async def test_deux_cles_distinctes_ont_des_seaux_independants() -> None:
    limiteur = RateLimiterPortEnMémoire(horloge=lambda: 0.0)

    for _ in range(2):
        assert await limiteur.consommer("ip:1.1.1.1", capacite=2, taux_recharge_par_seconde=0.0)

    # Une autre clé (un autre user, ex. G3) n'a pas épuisé son propre seau,
    # même si "ip:1.1.1.1" est déjà à sec.
    assert await limiteur.consommer("user:abc", capacite=2, taux_recharge_par_seconde=0.0) is True
    assert (
        await limiteur.consommer("ip:1.1.1.1", capacite=2, taux_recharge_par_seconde=0.0) is False
    )


async def test_le_temps_ecoule_recharge_le_seau_et_autorise_de_nouveau() -> None:
    horloge = {"maintenant": 0.0}
    limiteur = RateLimiterPortEnMémoire(horloge=lambda: horloge["maintenant"])

    assert await limiteur.consommer("ip:1.2.3.4", capacite=1, taux_recharge_par_seconde=1.0)
    assert (
        await limiteur.consommer("ip:1.2.3.4", capacite=1, taux_recharge_par_seconde=1.0) is False
    )

    horloge["maintenant"] += 1.0  # une seconde écoulée -> 1 jeton rechargé

    assert await limiteur.consommer("ip:1.2.3.4", capacite=1, taux_recharge_par_seconde=1.0) is True
