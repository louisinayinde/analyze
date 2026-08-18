from dataclasses import dataclass


@dataclass(frozen=True)
class EtatSeau:
    """État persisté d'un seau de jetons (token bucket) pour une clé donnée.

    `maj_a` est un horodatage exprimé dans la même unité que le
    `maintenant` passé à `recharger_et_consommer` (epoch secondes pour
    `LimiteurDebitPostgres`, `time.monotonic()` pour un éventuel double en
    mémoire) : cette fonction ne connaît que des flottants, jamais une
    horloge précise — c'est à l'appelant de rester cohérent d'un appel à
    l'autre.
    """

    jetons: float
    maj_a: float


def recharger_et_consommer(
    etat: EtatSeau | None,
    capacite: int,
    taux_recharge_par_seconde: float,
    maintenant: float,
) -> tuple[EtatSeau, bool]:
    """Algorithme du token bucket (G1, backlog.md), pur — aucune I/O, aucun
    accès horloge : `maintenant` est toujours fourni par l'appelant.

    Recharge le seau proportionnellement au temps écoulé depuis
    `etat.maj_a` (plafonné à `capacite`), puis tente de consommer un jeton.
    `etat is None` (première requête pour cette clé) équivaut à un seau
    déjà plein, comme un utilisateur qui n'a encore jamais dépassé son
    quota.

    Partagée telle quelle par `LimiteurDebitPostgres` (le seul endroit qui
    connaît Postgres) et par le double en mémoire utilisé dans les tests
    (`RateLimiterPortEnMémoire`, tests/modules/ratelimit/conftest.py) : la
    même connaissance — comment un seau se recharge et se consomme — ne
    doit exister qu'à un seul endroit (agents.md §1, DRY), le stockage
    restant un détail de chaque adaptateur (agents.md §4).

    Retourne `(nouvel_etat, autorise)`. `nouvel_etat` doit toujours être
    persisté par l'appelant, que la requête soit autorisée ou non : même
    un seau vide continue d'avancer son horodatage de recharge, sinon la
    recharge calculée au prochain appel se baserait sur un horodatage
    obsolète et sur-créditerait le seau.
    """
    jetons_avant = float(capacite) if etat is None else etat.jetons
    maj_a_avant = maintenant if etat is None else etat.maj_a

    ecoule = max(0.0, maintenant - maj_a_avant)
    jetons_recharges = min(float(capacite), jetons_avant + ecoule * taux_recharge_par_seconde)

    autorise = jetons_recharges >= 1.0
    jetons_apres = jetons_recharges - 1.0 if autorise else jetons_recharges

    return EtatSeau(jetons=jetons_apres, maj_a=maintenant), autorise
