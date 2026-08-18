from modules.ratelimit.domaine.seau_jetons import EtatSeau, recharger_et_consommer


def test_premiere_requete_pour_une_cle_part_d_un_seau_plein() -> None:
    # `etat is None` (aucune ligne encore persistée pour cette clé)
    # équivaut à un seau au plein capacité (docstring de la fonction).
    etat, autorise = recharger_et_consommer(
        None, capacite=5, taux_recharge_par_seconde=1.0, maintenant=0.0
    )

    assert autorise is True
    assert etat.jetons == 4.0


def test_seau_vide_refuse_la_requete_sans_consommer() -> None:
    etat_vide = EtatSeau(jetons=0.0, maj_a=0.0)

    etat, autorise = recharger_et_consommer(
        etat_vide, capacite=5, taux_recharge_par_seconde=0.0, maintenant=0.0
    )

    assert autorise is False
    assert etat.jetons == 0.0


def test_le_temps_ecoule_recharge_le_seau_au_taux_configure() -> None:
    etat_vide = EtatSeau(jetons=0.0, maj_a=0.0)

    # 10 secondes écoulées à 0.5 jeton/s -> 5 jetons rechargés.
    etat, autorise = recharger_et_consommer(
        etat_vide, capacite=5, taux_recharge_par_seconde=0.5, maintenant=10.0
    )

    assert autorise is True
    assert etat.jetons == 4.0  # 5 rechargés, 1 consommé


def test_la_recharge_ne_depasse_jamais_la_capacite() -> None:
    etat_presque_plein = EtatSeau(jetons=4.0, maj_a=0.0)

    # Largement assez de temps écoulé pour recharger bien plus que la
    # capacité si elle n'était pas plafonnée.
    etat, autorise = recharger_et_consommer(
        etat_presque_plein, capacite=5, taux_recharge_par_seconde=10.0, maintenant=100.0
    )

    assert autorise is True
    assert etat.jetons == 4.0  # plafonné à 5, puis 1 consommé


def test_horodatage_avance_meme_quand_la_requete_est_refusee() -> None:
    # Sans ça, un appelant qui martèle un seau vide referait le même
    # calcul de recharge basé sur un horodatage obsolète à chaque appel
    # (docstring de `recharger_et_consommer`).
    etat_vide = EtatSeau(jetons=0.0, maj_a=0.0)

    etat, autorise = recharger_et_consommer(
        etat_vide, capacite=5, taux_recharge_par_seconde=0.0, maintenant=42.0
    )

    assert autorise is False
    assert etat.maj_a == 42.0


def test_seuil_exact_d_un_jeton_disponible_autorise_la_requete() -> None:
    etat_a_un_jeton = EtatSeau(jetons=1.0, maj_a=0.0)

    etat, autorise = recharger_et_consommer(
        etat_a_un_jeton, capacite=5, taux_recharge_par_seconde=0.0, maintenant=0.0
    )

    assert autorise is True
    assert etat.jetons == 0.0
